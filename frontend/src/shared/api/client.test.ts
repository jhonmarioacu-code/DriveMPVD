import { afterEach, describe, expect, it, vi } from "vitest";

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

interface UploadResponsePlan {
  status: number;
  responseText?: string;
  headers?: Record<string, string>;
  event?: "load" | "error";
  progress?: {
    loaded: number;
    total: number;
    lengthComputable: boolean;
  };
}

class UploadXmlHttpRequest {
  static plans: UploadResponsePlan[] = [];
  static instances: UploadXmlHttpRequest[] = [];

  status = 0;
  responseText = "";
  withCredentials = false;
  body: unknown = null;
  readonly requestHeaders = new Map<string, string>();
  readonly upload: { onprogress: ((event: ProgressEvent) => void) | null } = {
    onprogress: null,
  };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  readonly open = vi.fn<(method: string, url: string) => void>();
  readonly setRequestHeader = vi.fn((name: string, value: string) => {
    this.requestHeaders.set(name.toLowerCase(), value);
  });
  readonly getResponseHeader = vi.fn(
    (name: string) => this.#responseHeaders.get(name.toLowerCase()) ?? null,
  );
  readonly abort = vi.fn(() => {
    void Promise.resolve().then(() => this.onabort?.());
  });
  readonly send = vi.fn((body: unknown) => {
    const plan = UploadXmlHttpRequest.plans.shift();
    if (plan === undefined) throw new Error("No se configuró una respuesta XHR.");
    this.body = body;
    this.status = plan.status;
    this.responseText = plan.responseText ?? "";
    this.#responseHeaders = new Map(
      Object.entries(plan.headers ?? {}).map(([name, value]) => [
        name.toLowerCase(),
        value,
      ]),
    );
    void Promise.resolve().then(() => {
      if (plan.progress !== undefined) {
        this.upload.onprogress?.(plan.progress as ProgressEvent);
      }
      if (plan.event === "error") {
        this.onerror?.();
        return;
      }
      this.onload?.();
    });
  });
  #responseHeaders = new Map<string, string>();

  constructor() {
    UploadXmlHttpRequest.instances.push(this);
  }
}

function installUploadResponses(...plans: UploadResponsePlan[]) {
  UploadXmlHttpRequest.plans = plans;
  UploadXmlHttpRequest.instances = [];
  vi.stubGlobal("XMLHttpRequest", UploadXmlHttpRequest);
}

afterEach(() => {
  UploadXmlHttpRequest.plans = [];
  UploadXmlHttpRequest.instances = [];
  vi.unstubAllGlobals();
});

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

  it("obtiene cabeceras de respuestas sin cuerpo y mantiene las cookies", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(null, {
        status: 204,
        headers: {
          "Upload-Offset": "12",
          "Upload-Length": "20",
        },
      }),
    );
    const client = new ApiClient("/api/v1", fetchMock);

    const headers = await client.requestHeaders("/storage/uploads/upload-1", {
      method: "HEAD",
    });

    expect(headers.get("Upload-Offset")).toBe("12");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/storage/uploads/upload-1",
      expect.objectContaining({ credentials: "include", method: "HEAD" }),
    );
  });

  it("traduce los errores JSON de solicitudes que sólo necesitan cabeceras", async () => {
    const client = new ApiClient(
      "/api/v1",
      vi
        .fn<typeof fetch>()
        .mockResolvedValue(
          errorResponse(409, "storage.upload_state_conflict", { "Retry-After": "9" }),
        ),
    );

    await expect(
      client.requestHeaders("/storage/uploads/upload-1"),
    ).rejects.toMatchObject({
      status: 409,
      code: "storage.upload_state_conflict",
      retryAfterSeconds: 9,
    });
  });

  it("carga bloques binarios con progreso, CSRF y credenciales", async () => {
    installUploadResponses({
      status: 204,
      headers: { "content-type": "application/json" },
      responseText: JSON.stringify(successEnvelope({ offset: 3 })),
      progress: { loaded: 2, total: 0, lengthComputable: false },
    });
    document.cookie = "drivempvd_csrf=upload-token; path=/";
    const progress = vi.fn();
    const chunk = new Blob(["abc"]);
    const client = new ApiClient("/api/v1", vi.fn<typeof fetch>());

    await expect(
      client.requestWithUploadProgress(
        "/storage/uploads/upload-1",
        chunk,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/offset+octet-stream",
            "Upload-Offset": "0",
          },
        },
        { onProgress: progress },
      ),
    ).resolves.toEqual({ offset: 3 });

    const request = UploadXmlHttpRequest.instances[0];
    expect(request?.open).toHaveBeenCalledWith(
      "PATCH",
      "/api/v1/storage/uploads/upload-1",
    );
    expect(request?.withCredentials).toBe(true);
    expect(request?.body).toBe(chunk);
    expect(request?.requestHeaders.get("content-type")).toBe(
      "application/offset+octet-stream",
    );
    expect(request?.requestHeaders.get("upload-offset")).toBe("0");
    expect(request?.requestHeaders.get("x-csrf-token")).toBe("upload-token");
    expect(progress).toHaveBeenCalledWith({ loaded: 2, total: chunk.size });
  });

  it("renueva una vez la sesión si un bloque recibe 401", async () => {
    installUploadResponses(
      {
        status: 401,
        headers: { "content-type": "application/json" },
        responseText: JSON.stringify({
          data: null,
          error: {
            code: "auth.authentication_required",
            message: "Authentication required.",
            details: [],
          },
          meta: { request_id: "upload-unauthorized", next_cursor: null },
        }),
      },
      {
        status: 200,
        headers: { "content-type": "application/json" },
        responseText: JSON.stringify(successEnvelope({ offset: 3 })),
      },
    );
    const refresh = vi.fn().mockResolvedValue(true);
    const client = new ApiClient("/api/v1", vi.fn<typeof fetch>());
    client.setUnauthorizedHandler(refresh);

    await expect(
      client.requestWithUploadProgress("/storage/uploads/upload-1", new Blob(["abc"]), {
        method: "PATCH",
      }),
    ).resolves.toEqual({ offset: 3 });

    expect(refresh).toHaveBeenCalledOnce();
    expect(UploadXmlHttpRequest.instances).toHaveLength(2);
  });

  it("traduce fallos de red y envelopes inválidos al subir bloques", async () => {
    installUploadResponses({ status: 0, event: "error" });
    const client = new ApiClient("/api/v1", vi.fn<typeof fetch>());

    await expect(
      client.requestWithUploadProgress("/storage/uploads/upload-1", new Blob(["abc"]), {
        method: "PATCH",
      }),
    ).rejects.toMatchObject({ code: "client.network_error", status: 0 });

    installUploadResponses({
      status: 200,
      headers: { "content-type": "application/json" },
      responseText: "{",
    });
    await expect(
      client.requestWithUploadProgress("/storage/uploads/upload-1", new Blob(["abc"]), {
        method: "PATCH",
      }),
    ).rejects.toMatchObject({ code: "client.invalid_envelope" });
  });

  it("rechaza una carga abortada antes de crear la solicitud", async () => {
    const controller = new AbortController();
    controller.abort();
    const client = new ApiClient("/api/v1", vi.fn<typeof fetch>());

    await expect(
      client.requestWithUploadProgress("/storage/uploads/upload-1", new Blob(["abc"]), {
        method: "PATCH",
        signal: controller.signal,
      }),
    ).rejects.toMatchObject({ code: "client.request_aborted", status: 0 });
    expect(UploadXmlHttpRequest.instances).toHaveLength(0);
  });
});
