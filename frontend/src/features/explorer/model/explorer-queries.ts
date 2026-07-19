import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  createFolder,
  getFileDetails,
  getFolderNavigation,
  listFolderEntries,
  moveEntry,
  renameEntry,
  trashEntry,
} from "@/features/explorer/api/explorer-api";

import type { ExplorerListOptions } from "@/features/explorer/model/types";

export const explorerKeys = {
  all: ["explorer"] as const,
  navigation: (folderId?: string) =>
    [...explorerKeys.all, "navigation", folderId ?? "root"] as const,
  entries: (folderId: string, options: ExplorerListOptions) =>
    [...explorerKeys.all, "entries", folderId, options] as const,
  file: (fileId: string) => [...explorerKeys.all, "file", fileId] as const,
};

export function useFolderNavigation(folderId?: string) {
  return useQuery({
    queryKey: explorerKeys.navigation(folderId),
    queryFn: ({ signal }) => getFolderNavigation(folderId, signal),
  });
}

export function useFolderEntries(
  folderId: string | undefined,
  options: ExplorerListOptions,
) {
  return useInfiniteQuery({
    queryKey: explorerKeys.entries(folderId ?? "pending", options),
    queryFn: ({ pageParam, signal }) =>
      listFolderEntries(folderId ?? "", options, pageParam, signal),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
    enabled: folderId !== undefined,
  });
}

export function useFileDetails(fileId: string | null) {
  return useQuery({
    queryKey: explorerKeys.file(fileId ?? "pending"),
    queryFn: ({ signal }) => getFileDetails(fileId ?? "", signal),
    enabled: fileId !== null,
  });
}

function useInvalidateExplorer() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: explorerKeys.all });
}

export function useCreateFolder() {
  const invalidate = useInvalidateExplorer();
  return useMutation({
    mutationFn: ({ parentId, name }: { parentId: string; name: string }) =>
      createFolder(parentId, name),
    onSuccess: invalidate,
  });
}

export function useRenameEntry() {
  const invalidate = useInvalidateExplorer();
  return useMutation({
    mutationFn: ({ entryId, name }: { entryId: string; name: string }) =>
      renameEntry(entryId, name),
    onSuccess: invalidate,
  });
}

export function useMoveEntries() {
  const invalidate = useInvalidateExplorer();
  return useMutation({
    mutationFn: async ({
      entryIds,
      destinationFolderId,
    }: {
      entryIds: string[];
      destinationFolderId: string;
    }) => {
      for (const entryId of entryIds) {
        await moveEntry(entryId, destinationFolderId);
      }
    },
    onSuccess: invalidate,
  });
}

export function useTrashEntries() {
  const invalidate = useInvalidateExplorer();
  return useMutation({
    mutationFn: async (entryIds: string[]) => {
      for (const entryId of entryIds) await trashEntry(entryId);
    },
    onSuccess: invalidate,
  });
}
