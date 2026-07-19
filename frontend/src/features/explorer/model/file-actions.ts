import { fileContentUrl } from "@/features/explorer/api/explorer-api";

import type { StorageEntry } from "@/features/explorer/model/types";

export function openFile(entry: StorageEntry) {
  window.open(fileContentUrl(entry.id), "_blank", "noopener,noreferrer");
}

export function downloadFile(entry: StorageEntry) {
  const link = document.createElement("a");
  link.href = fileContentUrl(entry.id);
  link.download = entry.name;
  link.rel = "noopener noreferrer";
  document.body.append(link);
  link.click();
  link.remove();
}
