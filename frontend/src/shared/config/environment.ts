const DEFAULT_API_BASE_URL = "/api/v1";

function normalizeBaseUrl(value: string | undefined) {
  const trimmedValue = value?.trim();
  const candidate =
    trimmedValue === undefined || trimmedValue === ""
      ? DEFAULT_API_BASE_URL
      : trimmedValue;
  return candidate.endsWith("/") ? candidate.slice(0, -1) : candidate;
}

export const environment = Object.freeze({
  apiBaseUrl: normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL),
});
