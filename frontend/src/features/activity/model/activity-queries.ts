import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { queryNamespaces } from "@/shared/query-keys";
import {
  listActivity,
  recordRecentOpen,
  removeFavorite,
  setFavorite,
} from "@/features/activity/api/activity-api";

import type { ActivityKind } from "@/features/activity/api/activity-api";

export const activityKeys = {
  all: queryNamespaces.activity,
  entries: (kind: ActivityKind, limit: number) =>
    [...activityKeys.all, kind, limit] as const,
};

export function useActivityEntries(kind: ActivityKind, limit = 50) {
  return useInfiniteQuery({
    queryKey: activityKeys.entries(kind, limit),
    queryFn: ({ pageParam, signal }) => listActivity(kind, limit, pageParam, signal),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
  });
}

function useInvalidateActivity() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: activityKeys.all }),
      queryClient.invalidateQueries({ queryKey: queryNamespaces.explorer }),
    ]);
}

export function useToggleFavorite() {
  const invalidate = useInvalidateActivity();
  return useMutation({
    mutationFn: ({ entryId, isFavorite }: { entryId: string; isFavorite: boolean }) =>
      isFavorite ? removeFavorite(entryId) : setFavorite(entryId),
    onSuccess: invalidate,
  });
}

export function useRecordRecentOpen() {
  const invalidate = useInvalidateActivity();
  return useMutation({
    mutationFn: (entryId: string) => recordRecentOpen(entryId),
    onSuccess: invalidate,
  });
}
