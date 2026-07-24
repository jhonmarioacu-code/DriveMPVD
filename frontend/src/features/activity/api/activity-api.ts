import { apiClient } from "@/shared/api/client";

import type { StorageEntry } from "@/features/explorer/public";

export type ActivityKind = "favorites" | "recents";

export interface ActivityEntry {
  entry: StorageEntry;
  occurred_at: string;
}

interface ActivityEntriesData {
  items: ActivityEntry[];
}

interface FavoriteStatusData {
  entry_id: string;
  is_favorite: boolean;
}

interface RecentOpenData {
  entry_id: string;
}

export interface ActivityPageData {
  items: ActivityEntry[];
  nextCursor: string | null;
}

function activityPath(kind: ActivityKind) {
  return kind === "favorites" ? "/activity/favorites" : "/activity/recents";
}

export async function listActivity(
  kind: ActivityKind,
  limit: number,
  cursor: string | null,
  signal?: AbortSignal,
): Promise<ActivityPageData> {
  const search = new URLSearchParams({ limit: String(limit) });
  if (cursor !== null) search.set("cursor", cursor);
  const result = await apiClient.requestWithMeta<ActivityEntriesData>(
    `${activityPath(kind)}?${search.toString()}`,
    { signal },
  );
  return { items: result.data.items, nextCursor: result.meta.next_cursor };
}

export function setFavorite(entryId: string) {
  return apiClient.request<FavoriteStatusData>(
    `/activity/favorites/${encodeURIComponent(entryId)}`,
    { method: "PUT" },
  );
}

export function removeFavorite(entryId: string) {
  return apiClient.request<FavoriteStatusData>(
    `/activity/favorites/${encodeURIComponent(entryId)}`,
    { method: "DELETE" },
  );
}

export function recordRecentOpen(entryId: string) {
  return apiClient.request<RecentOpenData>(
    `/activity/recents/${encodeURIComponent(entryId)}`,
    { method: "POST" },
  );
}
