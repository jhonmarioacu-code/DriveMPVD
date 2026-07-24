import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FileViewerDialog } from "@/features/viewers/ui/file-viewer-dialog";

import type { ViewerFile } from "@/features/viewers/model";

const contentApiMock = vi.hoisted(() => ({
  inspectStorageContent: vi.fn(),
  storageContentUrl: vi.fn((fileId: string) => `/inline/${fileId}`),
}));

vi.mock("@/shared/api/storage-content", () => contentApiMock);

function file(overrides: Partial<ViewerFile> = {}): ViewerFile {
  return {
    id: "file-one",
    name: "archivo.png",
    size: 1024,
    mime_type: "image/png",
    extension: "png",
    ...overrides,
  };
}

function renderViewer(viewerFile = file()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const onClose = vi.fn();
  const onDownload = vi.fn();
  const onOpenInNewTab = vi.fn();
  render(
    <QueryClientProvider client={client}>
      <FileViewerDialog
        file={viewerFile}
        onClose={onClose}
        onDownload={onDownload}
        onOpenInNewTab={onOpenInNewTab}
      />
    </QueryClientProvider>,
  );
  return { onClose, onDownload, onOpenInNewTab };
}

describe("FileViewerDialog", () => {
  beforeEach(() => {
    contentApiMock.inspectStorageContent.mockResolvedValue(
      new Headers({
        "content-disposition": 'inline; filename="archivo"',
        "content-type": "application/octet-stream",
      }),
    );
    contentApiMock.storageContentUrl.mockImplementation(
      (fileId: string) => `/inline/${fileId}`,
    );
  });

  it("muestra una imagen autenticada con controles y acciones", async () => {
    const user = userEvent.setup();
    const callbacks = renderViewer();

    const image = await screen.findByRole("img", {
      name: "Vista previa de archivo.png",
    });
    expect(image).toHaveAttribute("src", "/inline/file-one");
    await user.click(screen.getByRole("button", { name: "Acercar imagen" }));
    await user.click(screen.getByRole("button", { name: "Girar imagen" }));
    expect(screen.getByText("125%")).toBeVisible();
    expect(image).toHaveClass("viewer-image-zoom-125", "viewer-image-rotate-90");
    expect(image).not.toHaveAttribute("style");
    await user.click(screen.getByRole("button", { name: "Descargar" }));
    await user.click(screen.getByRole("button", { name: "Abrir aparte" }));
    await user.click(screen.getByRole("button", { name: "Cerrar" }));

    expect(callbacks.onDownload).toHaveBeenCalledOnce();
    expect(callbacks.onOpenInNewTab).toHaveBeenCalledOnce();
    expect(callbacks.onClose).toHaveBeenCalledOnce();
  });

  it.each([
    [
      "vídeo",
      file({ name: "clip.mp4", mime_type: "video/mp4", extension: "mp4" }),
      "video",
      "Reproductor de vídeo: clip.mp4",
    ],
    [
      "audio",
      file({ name: "podcast.mp3", mime_type: "audio/mpeg", extension: "mp3" }),
      "audio",
      "Reproductor de audio: podcast.mp3",
    ],
  ])(
    "reproduce %s con el elemento nativo y metadata inicial",
    async (_label, viewerFile, tag, label) => {
      renderViewer(viewerFile);

      const media = await screen.findByLabelText(label);
      expect(media.tagName.toLowerCase()).toBe(tag);
      expect(media).toHaveAttribute("src", `/inline/${viewerFile.id}`);
      expect(media).toHaveAttribute("preload", "metadata");
    },
  );

  it("integra el visor PDF nativo sin exponer el referrer", async () => {
    renderViewer(
      file({ name: "guia.pdf", mime_type: "application/pdf", extension: "pdf" }),
    );

    const documentFrame = await screen.findByTitle("Documento PDF: guia.pdf");
    expect(documentFrame).toHaveAttribute("src", "/inline/file-one");
    expect(documentFrame).toHaveAttribute("referrerpolicy", "no-referrer");
  });

  it("mantiene el fallback de descarga para formatos sin visor", () => {
    renderViewer(file({ name: "datos.csv", mime_type: "text/csv", extension: "csv" }));

    expect(screen.getByText("No hay vista previa para este formato")).toBeVisible();
    expect(contentApiMock.inspectStorageContent).not.toHaveBeenCalled();
  });

  it("muestra una explicación recuperable si el navegador no puede cargar el medio", async () => {
    renderViewer();
    const image = await screen.findByRole("img", {
      name: "Vista previa de archivo.png",
    });
    fireEvent.error(image);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "El navegador no pudo reproducir este archivo.",
    );
  });

  it("informa cuando el servidor deniega el modo inline", async () => {
    contentApiMock.inspectStorageContent.mockResolvedValue(
      new Headers({ "content-disposition": 'attachment; filename="archivo"' }),
    );
    renderViewer();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El servidor no permite mostrar este tipo de archivo en el navegador.",
    );
  });
});
