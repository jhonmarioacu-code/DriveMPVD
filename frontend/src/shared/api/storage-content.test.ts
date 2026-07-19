import { beforeEach, describe, expect, it, vi, type MockInstance } from "vitest";

import { inspectStorageContent, storageContentUrl } from "@/shared/api/storage-content";
import { apiClient } from "@/shared/api/client";

let requestHeadersSpy: MockInstance<typeof apiClient.requestHeaders>;

describe("storage content api", () => {
  beforeEach(() => {
    requestHeadersSpy = vi
      .spyOn(apiClient, "requestHeaders")
      .mockResolvedValue(new Headers());
  });

  it("construye URLs codificadas para descarga e inline", () => {
    expect(storageContentUrl("file / one")).toBe(
      "/api/v1/storage/files/file%20%2F%20one/content",
    );
    expect(storageContentUrl("file / one", "inline")).toBe(
      "/api/v1/storage/files/file%20%2F%20one/content?disposition=inline",
    );
  });

  it("inspecciona el contenido con HEAD sin reutilizar una respuesta cacheada", async () => {
    const controller = new AbortController();

    await inspectStorageContent("file/one", "inline", controller.signal);
    expect(requestHeadersSpy).toHaveBeenCalledWith(
      "/storage/files/file%2Fone/content?disposition=inline",
      {
        method: "HEAD",
        signal: controller.signal,
        cache: "no-store",
      },
    );

    await inspectStorageContent("download-default");
    expect(requestHeadersSpy).toHaveBeenLastCalledWith(
      "/storage/files/download-default/content?disposition=inline",
      expect.objectContaining({ method: "HEAD", signal: undefined }),
    );
  });
});
