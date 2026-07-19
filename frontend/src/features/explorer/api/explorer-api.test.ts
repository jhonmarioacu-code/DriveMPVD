import { beforeEach, describe, expect, it, vi, type MockInstance } from "vitest";

import {
  createFolder,
  fileContentUrl,
  getFileDetails,
  getFolderNavigation,
  listFolderEntries,
  moveEntry,
  renameEntry,
  trashEntry,
} from "@/features/explorer/api/explorer-api";
import { apiClient } from "@/shared/api/client";

let requestSpy: MockInstance<typeof apiClient.request>;
let requestWithMetaSpy: MockInstance<typeof apiClient.requestWithMeta>;

describe("explorer api", () => {
  beforeEach(() => {
    requestSpy = vi.spyOn(apiClient, "request").mockResolvedValue({});
    requestWithMetaSpy = vi.spyOn(apiClient, "requestWithMeta").mockResolvedValue({
      data: { folder_id: "root", items: [{ id: "entry" }] },
      meta: { request_id: "request", next_cursor: "next" },
    });
  });

  it("construye navegación, detalle y listado paginado", async () => {
    await getFolderNavigation("folder / one");
    expect(requestSpy).toHaveBeenLastCalledWith(
      "/storage/navigation?folder_id=folder+%2F+one",
      expect.objectContaining({ signal: undefined }),
    );

    await getFolderNavigation();
    expect(requestSpy).toHaveBeenLastCalledWith(
      "/storage/navigation",
      expect.any(Object),
    );

    await getFileDetails("file/one");
    expect(requestSpy).toHaveBeenLastCalledWith(
      "/storage/files/file%2Fone",
      expect.any(Object),
    );

    const page = await listFolderEntries(
      "folder/one",
      { sortBy: "date", direction: "desc", name: "reporte", kind: "file" },
      "cursor value",
    );
    expect(page).toEqual({ items: [{ id: "entry" }], nextCursor: "next" });
    expect(requestWithMetaSpy).toHaveBeenCalledWith(
      expect.stringContaining("/storage/folders/folder%2Fone/entries?"),
      expect.any(Object),
    );
    const requestedUrl = requestWithMetaSpy.mock.calls.at(-1)?.[0];
    expect(requestedUrl).toContain("sort_by=date");
    expect(requestedUrl).toContain("direction=desc");
    expect(requestedUrl).toContain("name=reporte");
    expect(requestedUrl).toContain("kind=file");
    expect(requestedUrl).toContain("cursor=cursor+value");

    requestWithMetaSpy.mockResolvedValueOnce({
      data: { folder_id: "root", items: [] },
      meta: { request_id: "request", next_cursor: null },
    });
    const emptyPage = await listFolderEntries(
      "root",
      { sortBy: "name", direction: "asc", name: "" },
      null,
    );
    expect(emptyPage).toEqual({ items: [], nextCursor: null });
    const defaultUrl = requestWithMetaSpy.mock.calls.at(-1)?.[0];
    expect(defaultUrl).not.toContain("name=");
    expect(defaultUrl).not.toContain("kind=");
    expect(defaultUrl).not.toContain("cursor=");
  });

  it("envía las mutaciones compatibles con el backend", async () => {
    await createFolder("root", "Viajes");
    expect(requestSpy).toHaveBeenLastCalledWith("/storage/folders", {
      method: "POST",
      body: JSON.stringify({ parent_id: "root", name: "Viajes" }),
    });

    await renameEntry("entry one", "Nuevo nombre");
    expect(requestSpy).toHaveBeenLastCalledWith("/storage/entries/entry%20one", {
      method: "PATCH",
      body: JSON.stringify({ name: "Nuevo nombre" }),
    });

    await moveEntry("entry", "destination");
    expect(requestSpy).toHaveBeenLastCalledWith("/storage/entries/entry/move", {
      method: "POST",
      body: JSON.stringify({ destination_folder_id: "destination" }),
    });

    await trashEntry("entry");
    expect(requestSpy).toHaveBeenLastCalledWith("/storage/entries/entry/trash", {
      method: "POST",
    });
    expect(fileContentUrl("file one")).toContain("/storage/files/file%20one/content");
  });
});
