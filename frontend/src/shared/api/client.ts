import { environment } from "@/shared/config/environment";

export interface ApiErrorDetail {
  field: string | null;
  message: string;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  details: ApiErrorDetail[];
}

export interface ApiMeta {
  request_id: string;
  next_cursor: string | null;
}

export interface ApiEnvelope<Data> {
  data: Data | null;
  error: ApiErrorBody | null;
  meta: ApiMeta;
}

export interface ApiResult<Data> {
  data: Data;
  meta: ApiMeta;
}

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ApiErrorDetail[];
  readonly requestId: string | null;
  readonly retryAfterSeconds: number | null;

  constructor(options: {
    message: string;
    status: number;
    code: string;
    details?: ApiErrorDetail[];
    requestId?: string | null;
    retryAfterSeconds?: number | null;
  }) {
    super(options.message);
    this.name = "ApiClientError";
    this.status = options.status;
    this.code = options.code;
    this.details = options.details ?? [];
    this.requestId = options.requestId ?? null;
    this.retryAfterSeconds = options.retryAfterSeconds ?? null;
  }
}

type FetchImplementation = typeof globalThis.fetch;
type UnauthorizedHandler = () => Promise<boolean>;

export interface ApiRequestOptions {
  retryUnauthorized?: boolean;
}

export interface UploadProgress {
  loaded: number;
  total: number;
}

export interface UploadRequestOptions extends ApiRequestOptions {
  onProgress?: (progress: UploadProgress) => void;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isApiEnvelope(value: unknown): value is ApiEnvelope<unknown> {
  if (!isRecord(value) || !("data" in value) || !("error" in value)) {
    return false;
  }
  const meta = value.meta;
  return isRecord(meta) && typeof meta.request_id === "string";
}

function joinUrl(baseUrl: string, path: string) {
  return `${baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
}

function isSafeMethod(method: string) {
  return ["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase());
}

export function readBrowserCookie(name: string) {
  const prefix = `${encodeURIComponent(name)}=`;
  const item = document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith(prefix));
  if (item === undefined) return null;
  try {
    return decodeURIComponent(item.slice(prefix.length));
  } catch {
    return null;
  }
}

export class ApiClient {
  readonly #baseUrl: string;
  readonly #fetch: FetchImplementation;
  #unauthorizedHandler: UnauthorizedHandler | null = null;

  constructor(
    baseUrl = environment.apiBaseUrl,
    fetchImplementation: FetchImplementation = globalThis.fetch.bind(globalThis),
  ) {
    this.#baseUrl = baseUrl.replace(/\/$/, "");
    this.#fetch = fetchImplementation;
  }

  setUnauthorizedHandler(handler: UnauthorizedHandler | null) {
    this.#unauthorizedHandler = handler;
  }

  async request<Data>(
    path: string,
    init: RequestInit = {},
    options: ApiRequestOptions = {},
  ): Promise<Data> {
    const result = await this.#withUnauthorizedRetry(
      () => this.#request<Data>(path, init, false),
      options,
    );
    return result.data;
  }

  requestWithMeta<Data>(
    path: string,
    init: RequestInit = {},
    options: ApiRequestOptions = {},
  ): Promise<ApiResult<Data>> {
    return this.#withUnauthorizedRetry(
      () => this.#request<Data>(path, init, false),
      options,
    );
  }

  requestWithUploadProgress<Data>(
    path: string,
    body: Blob,
    init: Omit<RequestInit, "body"> = {},
    options: UploadRequestOptions = {},
  ): Promise<Data> {
    return this.#withUnauthorizedRetry(
      () => this.#upload<Data>(path, body, init, options.onProgress),
      options,
    ).then((result) => result.data);
  }

  requestHeaders(
    path: string,
    init: RequestInit = {},
    options: ApiRequestOptions = {},
  ): Promise<Headers> {
    return this.#withUnauthorizedRetry(async () => {
      const headers = this.#buildHeaders(init);
      const response = await this.#fetch(joinUrl(this.#baseUrl, path), {
        ...init,
        credentials: "include",
        headers,
      });
      if (response.ok) return new Headers(response.headers);
      return this.#throwResponseError(response);
    }, options);
  }

  async requestVoid(
    path: string,
    init: RequestInit = {},
    options: ApiRequestOptions = {},
  ): Promise<void> {
    await this.#withUnauthorizedRetry(
      () => this.#request<null>(path, init, true),
      options,
    );
  }

  async #withUnauthorizedRetry<Result>(
    operation: () => Promise<Result>,
    options: ApiRequestOptions,
  ): Promise<Result> {
    try {
      return await operation();
    } catch (error) {
      const unauthorizedHandler = this.#unauthorizedHandler;
      const shouldRefresh =
        options.retryUnauthorized !== false &&
        error instanceof ApiClientError &&
        error.status === 401 &&
        unauthorizedHandler !== null;
      if (!shouldRefresh) throw error;

      const refreshed = await unauthorizedHandler();
      if (!refreshed) throw error;
      return operation();
    }
  }

  async #request<Data>(
    path: string,
    init: RequestInit,
    allowNullData: boolean,
  ): Promise<ApiResult<Data>> {
    const headers = this.#buildHeaders(init);

    const response = await this.#fetch(joinUrl(this.#baseUrl, path), {
      ...init,
      credentials: "include",
      headers,
    });

    const contentType = response.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) {
      throw new ApiClientError({
        status: response.status,
        code: "client.invalid_response",
        message: "El servidor devolvió una respuesta inesperada.",
        requestId: response.headers.get("x-request-id"),
      });
    }

    const payload: unknown = await response.json();
    if (!isApiEnvelope(payload)) {
      throw new ApiClientError({
        status: response.status,
        code: "client.invalid_envelope",
        message: "La respuesta no cumple el contrato de la API.",
        requestId: response.headers.get("x-request-id"),
      });
    }

    if (!response.ok || payload.error !== null) {
      const error = payload.error;
      throw new ApiClientError({
        status: response.status,
        code: error?.code ?? `http.${String(response.status)}`,
        message: error?.message ?? "La solicitud no pudo completarse.",
        details: error?.details ?? [],
        requestId: payload.meta.request_id,
        retryAfterSeconds: parseRetryAfter(response.headers.get("retry-after")),
      });
    }

    if (payload.data === null && !allowNullData) {
      throw new ApiClientError({
        status: response.status,
        code: "client.missing_data",
        message: "La API no devolvió los datos esperados.",
        requestId: payload.meta.request_id,
      });
    }

    return { data: payload.data as Data, meta: payload.meta };
  }

  #buildHeaders(init: RequestInit) {
    const headers = new Headers(init.headers);
    const method = init.method ?? "GET";
    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    if (init.body !== undefined && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    if (!isSafeMethod(method) && !headers.has(environment.csrfHeaderName)) {
      const csrfToken = readBrowserCookie(environment.csrfCookieName);
      if (csrfToken !== null) {
        headers.set(environment.csrfHeaderName, csrfToken);
      }
    }
    return headers;
  }

  async #throwResponseError(response: Response): Promise<never> {
    const contentType = response.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) {
      throw new ApiClientError({
        status: response.status,
        code: "client.invalid_response",
        message: "El servidor devolvió una respuesta inesperada.",
        requestId: response.headers.get("x-request-id"),
      });
    }
    const payload: unknown = await response.json();
    if (!isApiEnvelope(payload)) {
      throw new ApiClientError({
        status: response.status,
        code: "client.invalid_envelope",
        message: "La respuesta no cumple el contrato de la API.",
        requestId: response.headers.get("x-request-id"),
      });
    }
    const error = payload.error;
    throw new ApiClientError({
      status: response.status,
      code: error?.code ?? `http.${String(response.status)}`,
      message: error?.message ?? "La solicitud no pudo completarse.",
      details: error?.details ?? [],
      requestId: payload.meta.request_id,
      retryAfterSeconds: parseRetryAfter(response.headers.get("retry-after")),
    });
  }

  #upload<Data>(
    path: string,
    body: Blob,
    init: Omit<RequestInit, "body">,
    onProgress: ((progress: UploadProgress) => void) | undefined,
  ): Promise<ApiResult<Data>> {
    return new Promise((resolve, reject) => {
      const signal = init.signal;
      if (signal?.aborted) {
        reject(
          new ApiClientError({
            status: 0,
            code: "client.request_aborted",
            message: "La solicitud fue cancelada.",
          }),
        );
        return;
      }

      const request = new XMLHttpRequest();
      const cleanup = () => signal?.removeEventListener("abort", abortRequest);
      const abortRequest = () => request.abort();
      const fail = (error: ApiClientError) => {
        cleanup();
        reject(error);
      };

      request.open(init.method ?? "POST", joinUrl(this.#baseUrl, path));
      request.withCredentials = true;
      this.#buildHeaders({ ...init, body }).forEach((value, name) => {
        request.setRequestHeader(name, value);
      });
      request.upload.onprogress = (event) => {
        onProgress?.({
          loaded: event.loaded,
          total: event.lengthComputable ? event.total : body.size,
        });
      };
      request.onload = () => {
        cleanup();
        try {
          resolve(this.#parseUploadResponse<Data>(request));
        } catch (error) {
          reject(
            error instanceof Error
              ? error
              : new Error("No fue posible procesar la respuesta de subida."),
          );
        }
      };
      request.onerror = () => {
        fail(
          new ApiClientError({
            status: request.status,
            code: "client.network_error",
            message: "No fue posible conectar con el servidor.",
            requestId: request.getResponseHeader("x-request-id"),
          }),
        );
      };
      request.onabort = () => {
        fail(
          new ApiClientError({
            status: 0,
            code: "client.request_aborted",
            message: "La solicitud fue cancelada.",
          }),
        );
      };
      signal?.addEventListener("abort", abortRequest, { once: true });
      request.send(body);
    });
  }

  #parseUploadResponse<Data>(request: XMLHttpRequest): ApiResult<Data> {
    const contentType = request.getResponseHeader("content-type") ?? "";
    if (!contentType.includes("application/json")) {
      throw new ApiClientError({
        status: request.status,
        code: "client.invalid_response",
        message: "El servidor devolvió una respuesta inesperada.",
        requestId: request.getResponseHeader("x-request-id"),
      });
    }
    let payload: unknown;
    try {
      payload = JSON.parse(request.responseText) as unknown;
    } catch {
      throw new ApiClientError({
        status: request.status,
        code: "client.invalid_envelope",
        message: "La respuesta no cumple el contrato de la API.",
        requestId: request.getResponseHeader("x-request-id"),
      });
    }
    if (!isApiEnvelope(payload)) {
      throw new ApiClientError({
        status: request.status,
        code: "client.invalid_envelope",
        message: "La respuesta no cumple el contrato de la API.",
        requestId: request.getResponseHeader("x-request-id"),
      });
    }
    if (!(request.status >= 200 && request.status < 300) || payload.error !== null) {
      const error = payload.error;
      throw new ApiClientError({
        status: request.status,
        code: error?.code ?? `http.${String(request.status)}`,
        message: error?.message ?? "La solicitud no pudo completarse.",
        details: error?.details ?? [],
        requestId: payload.meta.request_id,
        retryAfterSeconds: parseRetryAfter(request.getResponseHeader("retry-after")),
      });
    }
    if (payload.data === null) {
      throw new ApiClientError({
        status: request.status,
        code: "client.missing_data",
        message: "La API no devolvió los datos esperados.",
        requestId: payload.meta.request_id,
      });
    }
    return { data: payload.data as Data, meta: payload.meta };
  }
}

function parseRetryAfter(value: string | null) {
  if (value === null) return null;
  const seconds = Number.parseInt(value, 10);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : null;
}

export const apiClient = new ApiClient();
