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
    try {
      return await this.#request<Data>(path, init, false);
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
      return this.#request<Data>(path, init, false);
    }
  }

  async requestVoid(
    path: string,
    init: RequestInit = {},
    options: ApiRequestOptions = {},
  ): Promise<void> {
    try {
      await this.#request<null>(path, init, true);
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
      await this.#request<null>(path, init, true);
    }
  }

  async #request<Data>(
    path: string,
    init: RequestInit,
    allowNullData: boolean,
  ): Promise<Data> {
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

    return payload.data as Data;
  }
}

function parseRetryAfter(value: string | null) {
  if (value === null) return null;
  const seconds = Number.parseInt(value, 10);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : null;
}

export const apiClient = new ApiClient();
