import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  activityKeys,
  useActivityEntries,
  useRecordRecentOpen,
  useToggleFavorite,
} from "@/features/activity/model/activity-queries";
import { queryNamespaces } from "@/shared/query-keys";
import {
  listActivity,
  recordRecentOpen,
  removeFavorite,
  setFavorite,
} from "@/features/activity/api/activity-api";

vi.mock("@/features/activity/api/activity-api", () => ({
  listActivity: vi.fn(),
  setFavorite: vi.fn(),
  removeFavorite: vi.fn(),
  recordRecentOpen: vi.fn(),
}));

function createWrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

function createClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

describe("activity queries", () => {
  beforeEach(() => {
    vi.mocked(listActivity).mockReset();
    vi.mocked(setFavorite).mockReset();
    vi.mocked(removeFavorite).mockReset();
    vi.mocked(recordRecentOpen).mockReset();
  });

  it("pagina la actividad mediante el cursor que devuelve la API", async () => {
    const client = createClient();
    vi.mocked(listActivity)
      .mockResolvedValueOnce({ items: [], nextCursor: "next-page" })
      .mockResolvedValueOnce({ items: [], nextCursor: null });
    const { result } = renderHook(() => useActivityEntries("recents", 20), {
      wrapper: createWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(listActivity).toHaveBeenCalledWith(
      "recents",
      20,
      null,
      expect.any(AbortSignal),
    );
    await act(async () => {
      await result.current.fetchNextPage();
    });
    expect(listActivity).toHaveBeenLastCalledWith(
      "recents",
      20,
      "next-page",
      expect.any(AbortSignal),
    );
  });

  it("sincroniza favoritos y recientes con la caché del explorador", async () => {
    const client = createClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    vi.mocked(setFavorite).mockResolvedValue({
      entry_id: "entry-id",
      is_favorite: true,
    });
    vi.mocked(removeFavorite).mockResolvedValue({
      entry_id: "entry-id",
      is_favorite: false,
    });
    vi.mocked(recordRecentOpen).mockResolvedValue({ entry_id: "entry-id" });
    const wrapper = createWrapper(client);
    const favorite = renderHook(() => useToggleFavorite(), { wrapper });
    const recent = renderHook(() => useRecordRecentOpen(), { wrapper });

    await act(async () => {
      await favorite.result.current.mutateAsync({
        entryId: "entry-id",
        isFavorite: false,
      });
    });
    await act(async () => {
      await favorite.result.current.mutateAsync({
        entryId: "entry-id",
        isFavorite: true,
      });
    });
    await act(async () => {
      await recent.result.current.mutateAsync("entry-id");
    });

    expect(setFavorite).toHaveBeenCalledWith("entry-id");
    expect(removeFavorite).toHaveBeenCalledWith("entry-id");
    expect(recordRecentOpen).toHaveBeenCalledWith("entry-id");
    expect(invalidate).toHaveBeenCalledWith({ queryKey: activityKeys.all });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryNamespaces.explorer });
  });
});
