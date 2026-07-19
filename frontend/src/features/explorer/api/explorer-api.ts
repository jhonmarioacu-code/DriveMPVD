import { apiClient } from "@/shared/api/client";
import {
  storageContentUrl,
  type ContentDisposition,
} from "@/shared/api/storage-content";

import type {
  ExplorerListOptions,
  FileDetails,
  FolderEntriesPage,
  FolderNavigation,
  StorageEntry,
} from "@/features/explorer/model/types";

interface FolderEntriesData {
  folder_id: string;
  items: StorageEntry[];
}

export function getFolderNavigation(folderId?: string, signal?: AbortSignal) {
  const search = new URLSearchParams();
  if (folderId !== undefined) search.set("folder_id", folderId);
  const query = search.size > 0 ? `?${search.toString()}` : "";
  return apiClient.request<FolderNavigation>(`/storage/navigation${query}`, {
    signal,
  });
}

export async function listFolderEntries(
  folderId: string,
  options: ExplorerListOptions,
  cursor: string | null,
  signal?: AbortSignal,
): Promise<FolderEntriesPage> {
  const search = new URLSearchParams({
    limit: "50",
    sort_by: options.sortBy,
    direction: options.direction,
  });
  if (options.name !== "") search.set("name", options.name);
  if (options.kind !== undefined) search.set("kind", options.kind);
  if (cursor !== null) search.set("cursor", cursor);
  const result = await apiClient.requestWithMeta<FolderEntriesData>(
    `/storage/folders/${encodeURIComponent(folderId)}/entries?${search.toString()}`,
    { signal },
  );
  return {
    items: result.data.items,
    nextCursor: result.meta.next_cursor,
  };
}

export function getFileDetails(fileId: string, signal?: AbortSignal) {
  return apiClient.request<FileDetails>(
    `/storage/files/${encodeURIComponent(fileId)}`,
    { signal },
  );
}

export function createFolder(parentId: string, name: string) {
  return apiClient.request<StorageEntry>("/storage/folders", {
    method: "POST",
    body: JSON.stringify({ parent_id: parentId, name }),
  });
}

export function renameEntry(entryId: string, name: string) {
  return apiClient.request<StorageEntry>(
    `/storage/entries/${encodeURIComponent(entryId)}`,
    {
      method: "PATCH",
      body: JSON.stringify({ name }),
    },
  );
}

export function moveEntry(entryId: string, destinationFolderId: string) {
  return apiClient.request<StorageEntry>(
    `/storage/entries/${encodeURIComponent(entryId)}/move`,
    {
      method: "POST",
      body: JSON.stringify({ destination_folder_id: destinationFolderId }),
    },
  );
}

export function trashEntry(entryId: string) {
  return apiClient.request<{ id: string }>(
    `/storage/entries/${encodeURIComponent(entryId)}/trash`,
    { method: "POST" },
  );
}

export function fileContentUrl(
  fileId: string,
  disposition: ContentDisposition = "attachment",
) {
  return storageContentUrl(fileId, disposition);
}
