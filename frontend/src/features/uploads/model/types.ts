import type { StorageEntry } from "@/features/explorer/public";

export type UploadTaskState =
  "pending" | "uploading" | "completed" | "error" | "cancelled";

export interface UploadSession {
  id: string;
  parent_id: string;
  filename: string;
  expected_size: number;
  uploaded_bytes: number;
  declared_mime_type: string | null;
  extension: string;
  status: "created" | "uploading" | "completed" | "cancelled" | "expired";
  expires_at: string;
  checksum_sha256: string | null;
}

export interface UploadChunkResult {
  upload_id: string;
  offset: number;
  received_bytes: number;
  chunk_sha256: string;
}

export interface UploadTask {
  id: string;
  file: File;
  parentId: string;
  state: UploadTaskState;
  uploadId: string | null;
  uploadedBytes: number;
  error: string | null;
  completedEntry: StorageEntry | null;
}

export interface UploadStatus {
  uploadedBytes: number;
  expectedSize: number;
  state: UploadSession["status"];
  expiresAt: string;
}
