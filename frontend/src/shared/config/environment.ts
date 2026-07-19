const DEFAULT_API_BASE_URL = "/api/v1";

function normalizeBaseUrl(value: string | undefined) {
  const trimmedValue = value?.trim();
  const candidate =
    trimmedValue === undefined || trimmedValue === ""
      ? DEFAULT_API_BASE_URL
      : trimmedValue;
  return candidate.endsWith("/") ? candidate.slice(0, -1) : candidate;
}

function normalizeSetting(value: string | undefined, fallback: string) {
  const trimmedValue = value?.trim();
  return trimmedValue === undefined || trimmedValue === "" ? fallback : trimmedValue;
}

export const environment = Object.freeze({
  apiBaseUrl: normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL),
  csrfCookieName: normalizeSetting(
    import.meta.env.VITE_CSRF_COOKIE_NAME,
    "drivempvd_csrf",
  ),
  csrfHeaderName: normalizeSetting(
    import.meta.env.VITE_CSRF_HEADER_NAME,
    "X-CSRF-Token",
  ),
});
