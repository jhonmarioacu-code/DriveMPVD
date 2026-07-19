import { apiClient, ApiClientError } from "@/shared/api/client";

import type {
  UploadChunkResult,
  UploadSession,
  UploadStatus,
} from "@/features/uploads/model/types";
import type { StorageEntry } from "@/features/explorer/model/types";

export const UPLOAD_CHUNK_SIZE = 4 * 1024 * 1024;

function uploadPath(uploadId: string) {
  return `/storage/uploads/${encodeURIComponent(uploadId)}`;
}

function readNonNegativeInteger(headers: Headers, name: string) {
  const value = headers.get(name);
  const parsed = value === null ? Number.NaN : Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 0) {
    throw new ApiClientError({
      status: 502,
      code: "client.invalid_upload_status",
      message: "El servidor devolvió un estado de subida inválido.",
    });
  }
  return parsed;
}

export function startUpload(parentId: string, file: File, signal?: AbortSignal) {
  return apiClient.request<UploadSession>("/storage/uploads", {
    method: "POST",
    signal,
    body: JSON.stringify({
      parent_id: parentId,
      filename: file.name,
      size: file.size,
      mime_type: file.type || "application/octet-stream",
    }),
  });
}

export async function getUploadStatus(uploadId: string, signal?: AbortSignal) {
  const headers = await apiClient.requestHeaders(uploadPath(uploadId), {
    method: "HEAD",
    signal,
  });
  const state = headers.get("Upload-Status");
  const expiresAt = headers.get("Upload-Expires");
  if (
    state === null ||
    expiresAt === null ||
    !["created", "uploading", "completed", "cancelled", "expired"].includes(state)
  ) {
    throw new ApiClientError({
      status: 502,
      code: "client.invalid_upload_status",
      message: "El servidor devolvió un estado de subida inválido.",
    });
  }
  return {
    uploadedBytes: readNonNegativeInteger(headers, "Upload-Offset"),
    expectedSize: readNonNegativeInteger(headers, "Upload-Length"),
    state,
    expiresAt,
  } as UploadStatus;
}

export function appendUploadChunk(
  uploadId: string,
  offset: number,
  chunk: Blob,
  signal: AbortSignal,
  onProgress: (uploadedBytes: number) => void,
) {
  return apiClient.requestWithUploadProgress<UploadChunkResult>(
    uploadPath(uploadId),
    chunk,
    {
      method: "PATCH",
      signal,
      headers: {
        "Content-Type": "application/offset+octet-stream",
        "Upload-Offset": String(offset),
      },
    },
    {
      onProgress: ({ loaded }) => onProgress(offset + loaded),
    },
  );
}

export function completeUpload(uploadId: string, signal?: AbortSignal) {
  return apiClient.request<StorageEntry>(`${uploadPath(uploadId)}/complete`, {
    method: "POST",
    signal,
  });
}

export function cancelUpload(uploadId: string) {
  return apiClient.request<UploadSession>(uploadPath(uploadId), {
    method: "DELETE",
  });
}
