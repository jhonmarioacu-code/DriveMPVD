import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EntryThumbnail } from "@/features/viewers/ui/entry-thumbnail";

import type { ViewerFile } from "@/features/viewers/model";

function file(overrides: Partial<ViewerFile> = {}): ViewerFile {
  return {
    id: "image / one",
    name: "portada.png",
    size: 1024,
    mime_type: "image/png",
    extension: "png",
    ...overrides,
  };
}

describe("EntryThumbnail", () => {
  it("carga perezosamente una imagen pequeña desde el endpoint autenticado inline", () => {
    const { container } = render(<EntryThumbnail file={file()} />);

    const thumbnail = container.querySelector("img");
    if (thumbnail === null) throw new Error("No se renderizó la miniatura de imagen.");
    expect(thumbnail).toHaveAttribute(
      "src",
      "/api/v1/storage/files/image%20%2F%20one/content?disposition=inline",
    );
    expect(thumbnail).toHaveAttribute("alt", "");
    expect(thumbnail).toHaveAttribute("aria-hidden", "true");
    expect(thumbnail).toHaveAttribute("loading", "lazy");
    expect(thumbnail).toHaveAttribute("decoding", "async");
  });

  it("sustituye una imagen que falla por un marcador de posición", () => {
    const { container } = render(<EntryThumbnail file={file()} />);
    const thumbnail = container.querySelector("img");
    if (thumbnail === null) throw new Error("No se renderizó la miniatura de imagen.");

    fireEvent.error(thumbnail);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("span[aria-hidden='true']")).toBeVisible();
  });

  it.each([
    ["vídeo", file({ name: "clip.mp4", mime_type: "video/mp4", extension: "mp4" })],
    ["audio", file({ name: "podcast.mp3", mime_type: "audio/mpeg", extension: "mp3" })],
    ["PDF", file({ name: "guia.pdf", mime_type: "application/pdf", extension: "pdf" })],
    [
      "imagen grande",
      file({ name: "panorama.png", size: 1_048_577, mime_type: "image/png" }),
    ],
    [
      "formato no compatible",
      file({ name: "datos.csv", mime_type: "text/csv", extension: "csv" }),
    ],
  ])("usa un marcador para %s sin descargar el original", (_label, viewerFile) => {
    const { container } = render(<EntryThumbnail file={viewerFile} />);

    expect(container.querySelector("span[aria-hidden='true']")).toBeVisible();
    expect(container.querySelector("img")).toBeNull();
  });
});
