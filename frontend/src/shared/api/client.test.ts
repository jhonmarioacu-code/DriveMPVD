import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "@/shared/api/client";

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
});
