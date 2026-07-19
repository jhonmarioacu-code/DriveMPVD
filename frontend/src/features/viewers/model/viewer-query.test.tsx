import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  ViewerContentError,
  useViewerSource,
  viewerErrorMessage,
} from "@/features/viewers/model/viewer-query";
import { ApiClientError } from "@/shared/api/client";

import type { ViewerFile } from "@/features/viewers/model";

const contentApiMock = vi.hoisted(() => ({
  inspectStorageContent: vi.fn(),
  storageContentUrl: vi.fn((fileId: string) => `/inline/${fileId}`),
}));

vi.mock("@/shared/api/storage-content", () => contentApiMock);

const image: ViewerFile = {
  id: "image",
  name: "foto.png",
  size: 12,
  mime_type: "image/png",
  extension: "png",
};

function SourceProbe({ file }: { file: ViewerFile }) {
  const source = useViewerSource(file);
  if (source.isPending) return <p>cargando</p>;
  if (source.isError) return <p>{viewerErrorMessage(source.error)}</p>;
  return <p>{source.data.url}</p>;
}

function renderProbe(file: ViewerFile) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SourceProbe file={file} />
    </QueryClientProvider>,
  );
}

describe("viewer query", () => {
  it("valida el permiso inline antes de entregar la URL de streaming", async () => {
    contentApiMock.inspectStorageContent.mockResolvedValue(
      new Headers({
        "content-disposition": 'inline; filename="foto.png"',
        "content-type": "image/png",
      }),
    );
    renderProbe(image);

    expect(screen.getByText("cargando")).toBeVisible();
    expect(await screen.findByText("/inline/image")).toBeVisible();
    expect(contentApiMock.inspectStorageContent).toHaveBeenCalledWith(
      image.id,
      "inline",
      expect.any(AbortSignal),
    );
  });

  it("rechaza una respuesta que conserva attachment y evita vistas inseguras", async () => {
    contentApiMock.inspectStorageContent.mockResolvedValue(
      new Headers({ "content-disposition": 'attachment; filename="foto.png"' }),
    );
    renderProbe(image);

    expect(
      await screen.findByText(
        "El servidor no permite mostrar este tipo de archivo en el navegador.",
      ),
    ).toBeVisible();
  });

  it("no consulta el contenido cuando el formato no tiene visor", () => {
    contentApiMock.inspectStorageContent.mockReset();
    contentApiMock.inspectStorageContent.mockResolvedValue(new Headers());
    renderProbe({ ...image, id: "text", mime_type: "text/plain", extension: "txt" });

    expect(screen.getByText("cargando")).toBeVisible();
    expect(contentApiMock.inspectStorageContent).not.toHaveBeenCalled();
  });

  it("traduce los errores de permisos y disponibilidad de forma estable", () => {
    expect(viewerErrorMessage(new ViewerContentError("No inline"))).toBe("No inline");
    expect(
      viewerErrorMessage(
        new ApiClientError({ status: 403, code: "forbidden", message: "forbidden" }),
      ),
    ).toBe("No tienes permiso para abrir este archivo.");
    expect(
      viewerErrorMessage(
        new ApiClientError({ status: 404, code: "missing", message: "missing" }),
      ),
    ).toBe("El archivo ya no está disponible.");
    expect(
      viewerErrorMessage(
        new ApiClientError({ status: 500, code: "server", message: "server" }),
      ),
    ).toBe("No fue posible preparar la vista previa. Inténtalo de nuevo.");
    expect(viewerErrorMessage(new Error("network"))).toBe(
      "No fue posible preparar la vista previa. Inténtalo de nuevo.",
    );
  });
});
