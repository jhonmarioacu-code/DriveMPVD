export type StorageEntryKind = "folder" | "file";
export type StorageSortField = "name" | "date" | "size" | "type";
export type SortDirection = "asc" | "desc";

export interface StorageEntry {
  id: string;
  parent_id: string | null;
  kind: StorageEntryKind;
  name: string;
  size: number | null;
  mime_type: string | null;
  extension: string | null;
  checksum_sha256: string | null;
  current_version_number: number | null;
  created_at: string;
  updated_at: string;
}

export interface FolderBreadcrumb {
  id: string;
  name: string;
}

export interface FolderNavigation {
  folder: StorageEntry;
  breadcrumbs: FolderBreadcrumb[];
}

export interface FileDetails {
  id: string;
  parent_id: string;
  name: string;
  original_name: string;
  size: number;
  mime_type: string;
  extension: string;
  checksum_sha256: string;
  current_version_number: number;
  created_at: string;
  updated_at: string;
}

export interface ExplorerListOptions {
  sortBy: StorageSortField;
  direction: SortDirection;
  name: string;
  kind?: StorageEntryKind;
}

export interface FolderEntriesPage {
  items: StorageEntry[];
  nextCursor: string | null;
}
