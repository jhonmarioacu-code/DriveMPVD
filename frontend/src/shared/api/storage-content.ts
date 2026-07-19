import { apiClient } from "@/shared/api/client";
import { environment } from "@/shared/config/environment";

export type ContentDisposition = "attachment" | "inline";

function contentPath(fileId: string, disposition: ContentDisposition) {
  const path = `/storage/files/${encodeURIComponent(fileId)}/content`;
  return disposition === "inline" ? `${path}?disposition=inline` : path;
}

export function storageContentUrl(
  fileId: string,
  disposition: ContentDisposition = "attachment",
) {
  return `${environment.apiBaseUrl}${contentPath(fileId, disposition)}`;
}

export function inspectStorageContent(
  fileId: string,
  disposition: ContentDisposition = "inline",
  signal?: AbortSignal,
) {
  return apiClient.requestHeaders(contentPath(fileId, disposition), {
    method: "HEAD",
    signal,
    cache: "no-store",
  });
}
