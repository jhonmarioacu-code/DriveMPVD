import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  listActivity,
  recordRecentOpen,
  removeFavorite,
  setFavorite,
} from "@/features/activity/api/activity-api";

const apiClientMock = vi.hoisted(() => ({
  request: vi.fn(),
  requestWithMeta: vi.fn(),
}));

vi.mock("@/shared/api/client", () => ({
  apiClient: apiClientMock,
}));

describe("activity API", () => {
  beforeEach(() => {
    apiClientMock.request.mockReset();
    apiClientMock.requestWithMeta.mockReset();
  });

  it("lista cada fuente de actividad con cursor opaco y señal de cancelación", async () => {
    const signal = new AbortController().signal;
    apiClientMock.requestWithMeta.mockResolvedValue({
      data: { items: [{ entry: { id: "one" }, occurred_at: "2026-07-20T12:00:00Z" }] },
      meta: { next_cursor: "next" },
    });

    const result = await listActivity("favorites", 25, "previous", signal);

    expect(apiClientMock.requestWithMeta).toHaveBeenCalledWith(
      "/activity/favorites?limit=25&cursor=previous",
      { signal },
    );
    expect(result).toEqual({
      items: [{ entry: { id: "one" }, occurred_at: "2026-07-20T12:00:00Z" }],
      nextCursor: "next",
    });
  });

  it("envía las mutaciones idempotentes a sus contratos protegidos", async () => {
    apiClientMock.request.mockResolvedValue({ entry_id: "entry-id" });

    await setFavorite("entry id");
    await removeFavorite("entry id");
    await recordRecentOpen("entry id");

    expect(apiClientMock.request).toHaveBeenNthCalledWith(
      1,
      "/activity/favorites/entry%20id",
      { method: "PUT" },
    );
    expect(apiClientMock.request).toHaveBeenNthCalledWith(
      2,
      "/activity/favorites/entry%20id",
      { method: "DELETE" },
    );
    expect(apiClientMock.request).toHaveBeenNthCalledWith(
      3,
      "/activity/recents/entry%20id",
      { method: "POST" },
    );
  });
});
