import { describe, expect, it } from "vitest";

import {
  getThumbnailStrategy,
  MAX_INLINE_THUMBNAIL_BYTES,
} from "@/features/viewers/model/thumbnail-strategy";
import type { ViewerFile } from "@/features/viewers/model/viewer-types";

function viewerFile(overrides: Partial<ViewerFile> = {}): ViewerFile {
  return {
    id: "file-1",
    name: "foto.png",
    size: 512,
    mime_type: "image/png",
    extension: "png",
    ...overrides,
  };
}

describe("thumbnail strategy", () => {
  it("usa la imagen original hasta el límite inclusivo de 1 MiB", () => {
    expect(MAX_INLINE_THUMBNAIL_BYTES).toBe(1024 * 1024);
    expect(getThumbnailStrategy(viewerFile({ size: MAX_INLINE_THUMBNAIL_BYTES }))).toBe(
      "source-image",
    );
    expect(
      getThumbnailStrategy(
        viewerFile({
          mime_type: null,
          extension: "JPG",
          size: MAX_INLINE_THUMBNAIL_BYTES,
        }),
      ),
    ).toBe("source-image");
  });

  it("evita descargar el original cuando el tamaño es desconocido o excede el límite", () => {
    expect(getThumbnailStrategy(viewerFile({ size: null }))).toBe("placeholder");
    expect(
      getThumbnailStrategy(viewerFile({ size: MAX_INLINE_THUMBNAIL_BYTES + 1 })),
    ).toBe("placeholder");
  });

  it.each([
    viewerFile({ mime_type: "video/mp4", extension: "mp4" }),
    viewerFile({ mime_type: "audio/mpeg", extension: "mp3" }),
    viewerFile({ mime_type: "application/pdf", extension: "pdf" }),
    viewerFile({ mime_type: "application/octet-stream", extension: "bin" }),
  ])("usa un marcador para archivos que no son imágenes: $name", (file) => {
    expect(getThumbnailStrategy(file)).toBe("placeholder");
  });
});
