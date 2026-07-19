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

  constructor(options: {
    message: string;
    status: number;
    code: string;
    details?: ApiErrorDetail[];
    requestId?: string | null;
  }) {
    super(options.message);
    this.name = "ApiClientError";
    this.status = options.status;
    this.code = options.code;
    this.details = options.details ?? [];
    this.requestId = options.requestId ?? null;
  }
}

type FetchImplementation = typeof globalThis.fetch;

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

export class ApiClient {
  readonly #baseUrl: string;
  readonly #fetch: FetchImplementation;

  constructor(
    baseUrl = environment.apiBaseUrl,
    fetchImplementation: FetchImplementation = globalThis.fetch.bind(globalThis),
  ) {
    this.#baseUrl = baseUrl.replace(/\/$/, "");
    this.#fetch = fetchImplementation;
  }

  async request<Data>(path: string, init: RequestInit = {}): Promise<Data> {
    const headers = new Headers(init.headers);
    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    if (init.body !== undefined && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
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
      });
    }

    if (payload.data === null) {
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

export const apiClient = new ApiClient();
