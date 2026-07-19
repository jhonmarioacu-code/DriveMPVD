import { describe, expect, it, vi } from "vitest";

import { ApiClient, readBrowserCookie } from "@/shared/api/client";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function successEnvelope(data: unknown) {
  return {
    data,
    error: null,
    meta: { request_id: "request-1", next_cursor: null },
  };
}

function errorResponse(
  status = 401,
  code = "auth.authentication_required",
  headers: Record<string, string> = {},
) {
  return new Response(
    JSON.stringify({
      data: null,
      error: { code, message: "Authentication required.", details: [] },
      meta: { request_id: "request-auth", next_cursor: null },
    }),
    {
      status,
      headers: { "content-type": "application/json", ...headers },
    },
  );
}

describe("ApiClient", () => {
  it("devuelve los datos del envelope y configura la solicitud", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse(successEnvelope({ status: "ok" })));
    const client = new ApiClient("/api/v1/", fetchMock);

    await expect(
      client.request<{ status: string }>("health", {
        method: "POST",
        body: JSON.stringify({ check: true }),
      }),
    ).resolves.toEqual({ status: "ok" });

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/health",
      expect.objectContaining({ credentials: "include", method: "POST" }),
    );
    const request = fetchMock.mock.calls[0]?.[1];
    const headers = new Headers(request?.headers);
    expect(headers.get("Accept")).toBe("application/json");
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it("conserva cabeceras explícitas y acepta rutas absolutas dentro de la API", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse(successEnvelope({ ok: true })));
    const client = new ApiClient("/api/v1", fetchMock);

    await client.request("/health", {
      headers: { Accept: "application/vnd.api+json" },
    });

    const request = fetchMock.mock.calls[0]?.[1];
    expect(new Headers(request?.headers).get("Accept")).toBe(
      "application/vnd.api+json",
    );
  });

  it("traduce un error uniforme de la API", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse(
        {
          data: null,
          error: {
            code: "auth.invalid_credentials",
            message: "Credenciales inválidas.",
            details: [{ field: "username", message: "Revisa este valor." }],
          },
          meta: { request_id: "request-error", next_cursor: null },
        },
        401,
      ),
    );

    const result = new ApiClient("/api/v1", fetchMock).request("/auth/session");

    await expect(result).rejects.toMatchObject({
      name: "ApiClientError",
      status: 401,
      code: "auth.invalid_credentials",
      requestId: "request-error",
      details: [{ field: "username", message: "Revisa este valor." }],
    });
  });

  it("rechaza respuestas que no son JSON", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response("gateway error", {
        status: 502,
        headers: { "x-request-id": "proxy-1" },
      }),
    );

    await expect(
      new ApiClient("/api/v1", fetchMock).request("health"),
    ).rejects.toMatchObject({
      code: "client.invalid_response",
      requestId: "proxy-1",
      status: 502,
    });
  });

  it("rechaza JSON ajeno al envelope y éxitos sin datos", async () => {
    const invalidFetch = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ status: "ok" }));
    const missingDataFetch = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse(successEnvelope(null)));

    await expect(
      new ApiClient("/api/v1", invalidFetch).request("health"),
    ).rejects.toMatchObject({ code: "client.invalid_envelope" });
    await expect(
      new ApiClient("/api/v1", missingDataFetch).request("health"),
    ).rejects.toMatchObject({ code: "client.missing_data" });
  });

  it("crea un error de respaldo si el estado y el envelope discrepan", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse(successEnvelope({ ignored: true }), 500));

    await expect(
      new ApiClient("/api/v1", fetchMock).request("health"),
    ).rejects.toMatchObject({
      code: "http.500",
      message: "La solicitud no pudo completarse.",
    });
  });

  it("envía el CSRF legible únicamente en métodos mutables", async () => {
    document.cookie = "drivempvd_csrf=token%20seguro; path=/";
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockImplementation(() =>
        Promise.resolve(jsonResponse(successEnvelope({ ok: true }))),
      );
    const client = new ApiClient("/api/v1", fetchMock);

    await client.request("health");
    await client.request("folders", { method: "POST", body: "{}" });

    const safeHeaders = new Headers(fetchMock.mock.calls[0]?.[1]?.headers);
    const mutationHeaders = new Headers(fetchMock.mock.calls[1]?.[1]?.headers);
    expect(safeHeaders.has("X-CSRF-Token")).toBe(false);
    expect(mutationHeaders.get("X-CSRF-Token")).toBe("token seguro");
    expect(readBrowserCookie("drivempvd_csrf")).toBe("token seguro");
  });

  it("respeta una cabecera CSRF explícita y tolera cookies mal codificadas", async () => {
    document.cookie = "drivempvd_csrf=%E0%A4%A; path=/";
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse(successEnvelope({ ok: true })));

    await new ApiClient("/api/v1", fetchMock).request("folders", {
      method: "DELETE",
      headers: { "X-CSRF-Token": "explicit" },
    });

    expect(readBrowserCookie("drivempvd_csrf")).toBeNull();
    expect(new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get("X-CSRF-Token")).toBe(
      "explicit",
    );
  });

  it("renueva una sesión una vez y repite la solicitud original", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(errorResponse())
      .mockResolvedValueOnce(jsonResponse(successEnvelope({ username: "Admin" })));
    const refresh = vi.fn().mockResolvedValue(true);
    const client = new ApiClient("/api/v1", fetchMock);
    client.setUnauthorizedHandler(refresh);

    await expect(client.request("/auth/session")).resolves.toEqual({
      username: "Admin",
    });
    expect(refresh).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("no repite un 401 si la renovación falla o está deshabilitada", async () => {
    const failedRefreshFetch = vi.fn<typeof fetch>().mockResolvedValue(errorResponse());
    const noRetryFetch = vi.fn<typeof fetch>().mockResolvedValue(errorResponse());
    const refresh = vi.fn().mockResolvedValue(false);
    const client = new ApiClient("/api/v1", failedRefreshFetch);
    client.setUnauthorizedHandler(refresh);

    await expect(client.request("/auth/session")).rejects.toMatchObject({
      status: 401,
    });
    await expect(
      new ApiClient("/api/v1", noRetryFetch).request(
        "/auth/login",
        { method: "POST" },
        { retryUnauthorized: false },
      ),
    ).rejects.toMatchObject({ status: 401 });
    expect(failedRefreshFetch).toHaveBeenCalledOnce();
  });

  it("acepta envelopes exitosos sin datos y renueva logout si es necesario", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(errorResponse())
      .mockResolvedValueOnce(jsonResponse(successEnvelope(null)));
    const client = new ApiClient("/api/v1", fetchMock);
    client.setUnauthorizedHandler(vi.fn().mockResolvedValue(true));

    await expect(
      client.requestVoid("/auth/logout", { method: "POST" }),
    ).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("propaga Retry-After como segundos cuando es válido", async () => {
    const limitedFetch = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        errorResponse(429, "auth.rate_limit_exceeded", { "Retry-After": "42" }),
      );
    const invalidFetch = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        errorResponse(429, "auth.rate_limit_exceeded", { "Retry-After": "tomorrow" }),
      );

    await expect(
      new ApiClient("/api/v1", limitedFetch).request("/auth/login"),
    ).rejects.toMatchObject({ retryAfterSeconds: 42 });
    await expect(
      new ApiClient("/api/v1", invalidFetch).request("/auth/login"),
    ).rejects.toMatchObject({ retryAfterSeconds: null });
  });
});
