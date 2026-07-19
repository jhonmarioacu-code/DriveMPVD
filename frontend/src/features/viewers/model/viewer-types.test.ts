import { describe, expect, it } from "vitest";

import {
  getViewerKind,
  isPreviewable,
  viewerKindLabel,
  type ViewerKind,
} from "@/features/viewers/model/viewer-types";

const supportedMimeKinds: readonly (readonly [string, ViewerKind])[] = [
  ["application/pdf", "pdf"],
  ["audio/aac", "audio"],
  ["audio/flac", "audio"],
  ["audio/m4a", "audio"],
  ["audio/mpeg", "audio"],
  ["audio/mp4", "audio"],
  ["audio/ogg", "audio"],
  ["audio/wav", "audio"],
  ["audio/webm", "audio"],
  ["image/avif", "image"],
  ["image/gif", "image"],
  ["image/jpeg", "image"],
  ["image/png", "image"],
  ["image/webp", "image"],
  ["video/mp4", "video"],
  ["video/ogg", "video"],
  ["video/quicktime", "video"],
  ["video/webm", "video"],
];

const supportedExtensionKinds: readonly (readonly [string, ViewerKind])[] = [
  ["aac", "audio"],
  ["avif", "image"],
  ["flac", "audio"],
  ["gif", "image"],
  ["jpeg", "image"],
  ["jpg", "image"],
  ["m4a", "audio"],
  ["mkv", "video"],
  ["mov", "video"],
  ["mp3", "audio"],
  ["mp4", "video"],
  ["ogg", "audio"],
  ["pdf", "pdf"],
  ["png", "image"],
  ["wav", "audio"],
  ["webm", "video"],
  ["webp", "image"],
];

describe("viewer types", () => {
  it.each(supportedMimeKinds)(
    "clasifica el MIME permitido %s como %s",
    (mimeType, expectedKind) => {
      expect(
        getViewerKind({ mime_type: mimeType.toUpperCase(), extension: "bin" }),
      ).toBe(expectedKind);
    },
  );

  it.each(supportedExtensionKinds)(
    "usa la extensión permitida %s como respaldo para %s",
    (extension, expectedKind) => {
      expect(
        getViewerKind({
          mime_type: "application/octet-stream",
          extension: extension.toUpperCase(),
        }),
      ).toBe(expectedKind);
    },
  );

  it("prefiere un MIME reconocido antes que una extensión contradictoria", () => {
    expect(getViewerKind({ mime_type: "video/mp4", extension: "png" })).toBe("video");
  });

  it("rechaza archivos sin un formato de visualización admitido", () => {
    expect(getViewerKind({ mime_type: "text/html", extension: "html" })).toBe(
      "unsupported",
    );
    expect(getViewerKind({ mime_type: null, extension: null })).toBe("unsupported");
  });

  it.each([
    ["image", true],
    ["video", true],
    ["audio", true],
    ["pdf", true],
    ["unsupported", false],
  ] as const)("indica si %s se puede previsualizar", (kind, expected) => {
    const fileByKind: Record<
      ViewerKind,
      { mime_type: string | null; extension: string | null }
    > = {
      image: { mime_type: "image/png", extension: "png" },
      video: { mime_type: "video/mp4", extension: "mp4" },
      audio: { mime_type: "audio/mpeg", extension: "mp3" },
      pdf: { mime_type: "application/pdf", extension: "pdf" },
      unsupported: { mime_type: "application/octet-stream", extension: "bin" },
    };

    expect(isPreviewable(fileByKind[kind])).toBe(expected);
  });

  it.each([
    ["image", "imagen"],
    ["video", "vídeo"],
    ["audio", "audio"],
    ["pdf", "PDF"],
    ["unsupported", "archivo"],
  ] as const)("etiqueta %s para la interfaz", (kind, label) => {
    expect(viewerKindLabel(kind)).toBe(label);
  });
});
