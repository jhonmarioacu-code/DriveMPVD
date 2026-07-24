import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createFolder,
  getFileDetails,
  getFolderNavigation,
  listFolderEntries,
  moveEntry,
  renameEntry,
  trashEntry,
} from "@/features/explorer/api/explorer-api";
import {
  recordRecentOpen,
  removeFavorite,
  setFavorite,
} from "@/features/activity/api/activity-api";
import { FileExplorerPage } from "@/features/explorer/ui/file-explorer-page";
import { ApiClientError } from "@/shared/api/client";

import type { StorageEntry } from "@/features/explorer/model/types";

vi.mock("@/features/explorer/api/explorer-api", () => ({
  getFolderNavigation: vi.fn(),
  listFolderEntries: vi.fn(),
  getFileDetails: vi.fn(),
  createFolder: vi.fn(),
  renameEntry: vi.fn(),
  moveEntry: vi.fn(),
  trashEntry: vi.fn(),
  fileContentUrl: vi.fn((fileId: string) => `/content/${fileId}`),
}));

vi.mock("@/features/activity/api/activity-api", () => ({
  listActivity: vi.fn(),
  setFavorite: vi.fn(),
  removeFavorite: vi.fn(),
  recordRecentOpen: vi.fn(),
}));

const uploadsMock = vi.hoisted(() => ({ enqueueFiles: vi.fn() }));

vi.mock("@/features/uploads/model/uploads-context", async (importOriginal) => {
  const actual = await importOriginal<
    typeof import("@/features/uploads/model/uploads-context")
  >();
  return {
    ...actual,
    useUploadsDispatch: () => uploadsMock,
  };
});

vi.mock("@/features/viewers", () => ({
  EntryThumbnail: () => <span aria-hidden="true" />,
  FileViewerDialog: ({
    file,
    onClose,
    onDownload,
    onOpenInNewTab,
  }: {
    file: { name: string };
    onClose: () => void;
    onDownload: () => void;
    onOpenInNewTab: () => void;
  }) => (
    <section aria-label={`Vista previa: ${file.name}`} role="dialog">
      <button onClick={onClose} type="button">
        Cerrar vista previa
      </button>
      <button onClick={onDownload} type="button">
        Descargar desde vista previa
      </button>
      <button onClick={onOpenInNewTab} type="button">
        Abrir aparte desde vista previa
      </button>
    </section>
  ),
  isPreviewable: (file: { extension: string | null }) => file.extension !== "bin",
}));

const root = entry("root", "folder", "Drive", null);
const photos = entry("photos", "folder", "Fotos", root.id);
const report = entry("report", "file", "reporte.pdf", root.id, 1536, "pdf");
const image = entry("image", "file", "portada.jpg", root.id, 4096, "jpg");

function entry(
  id: string,
  kind: "folder" | "file",
  name: string,
  parentId: string | null,
  size: number | null = null,
  extension: string | null = null,
): StorageEntry {
  return {
    id,
    parent_id: parentId,
    kind,
    name,
    size,
    mime_type: kind === "file" ? "application/octet-stream" : null,
    extension,
    checksum_sha256: null,
    current_version_number: kind === "file" ? 1 : null,
    created_at: "2026-07-18T18:00:00Z",
    updated_at: "2026-07-18T19:00:00Z",
  };
}

function renderExplorer(initialEntry = "/files") {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0 },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/files" element={<FileExplorerPage />} />
          <Route path="/files/:folderId" element={<FileExplorerPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("FileExplorerPage", () => {
  beforeEach(() => {
    vi.mocked(getFolderNavigation).mockImplementation((folderId) =>
      Promise.resolve(
        folderId === photos.id
          ? {
              folder: photos,
              breadcrumbs: [
                { id: root.id, name: root.name },
                { id: photos.id, name: photos.name },
              ],
            }
          : {
              folder: root,
              breadcrumbs: [{ id: root.id, name: root.name }],
            },
      ),
    );
    vi.mocked(listFolderEntries).mockImplementation((folderId, options, cursor) => {
      if (folderId === photos.id) {
        return Promise.resolve({ items: [], nextCursor: null });
      }
      const allItems = options.kind === "folder" ? [photos] : [photos, report];
      return Promise.resolve(
        cursor === "next"
          ? { items: [image], nextCursor: null }
          : { items: allItems, nextCursor: "next" },
      );
    });
    vi.mocked(getFileDetails).mockResolvedValue({
      ...report,
      parent_id: root.id,
      original_name: report.name,
      size: report.size ?? 0,
      mime_type: "application/pdf",
      extension: "pdf",
      checksum_sha256: "a".repeat(64),
      current_version_number: 1,
    });
    vi.mocked(createFolder).mockResolvedValue(photos);
    vi.mocked(renameEntry).mockResolvedValue(report);
    vi.mocked(moveEntry).mockResolvedValue(report);
    vi.mocked(trashEntry).mockResolvedValue({ id: report.id });
    vi.mocked(setFavorite).mockReset().mockResolvedValue({
      entry_id: report.id,
      is_favorite: true,
    });
    vi.mocked(removeFavorite).mockReset().mockResolvedValue({
      entry_id: report.id,
      is_favorite: false,
    });
    vi.mocked(recordRecentOpen).mockReset().mockResolvedValue({
      entry_id: report.id,
    });
    uploadsMock.enqueueFiles.mockReset();
  });

  it("lista, pagina, filtra, ordena y navega con breadcrumbs", async () => {
    const user = userEvent.setup();
    renderExplorer();

    expect(await screen.findByRole("heading", { name: "Drive" })).toBeVisible();
    expect(await screen.findByText("reporte.pdf")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Cargar más" }));
    expect(await screen.findByText("portada.jpg")).toBeVisible();

    await user.type(screen.getByLabelText("Filtrar esta carpeta"), "reporte");
    expect(screen.getByLabelText("Filtrar esta carpeta")).toHaveClass(
      "explorer-search-input",
    );
    await waitFor(() =>
      expect(listFolderEntries).toHaveBeenCalledWith(
        root.id,
        expect.objectContaining({ name: "reporte" }),
        null,
        expect.any(AbortSignal),
      ),
    );
    await user.selectOptions(screen.getByLabelText("Ordenar por"), "size");
    await user.click(screen.getByRole("button", { name: "Orden ascendente" }));

    await user.click(screen.getByRole("button", { name: /^Fotos/ }));
    expect(await screen.findByRole("heading", { name: "Fotos" })).toBeVisible();
    expect(screen.getByText("Esta carpeta está vacía")).toBeVisible();
    await user.click(screen.getByRole("link", { name: "Drive" }));
    expect(await screen.findByRole("heading", { name: "Drive" })).toBeVisible();
  });

  it("actualiza favoritos y recientes desde las acciones del explorador", async () => {
    const user = userEvent.setup();
    renderExplorer();

    await screen.findByText("reporte.pdf");
    await user.click(
      screen.getByRole("button", { name: "Añadir reporte.pdf a favoritos" }),
    );
    await waitFor(() => expect(setFavorite).toHaveBeenCalledWith(report.id));

    await user.click(screen.getByRole("button", { name: /^reporte\.pdf/ }));
    await waitFor(() => expect(recordRecentOpen).toHaveBeenCalledWith(report.id));
  });

  it("mantiene las acciones de teclado de la fila separadas de sus controles", async () => {
    const user = userEvent.setup();
    renderExplorer();

    await screen.findByText("reporte.pdf");
    const grid = screen.getByRole("grid", { name: "Archivos y carpetas" });
    expect(within(grid).getByRole("columnheader", { name: "Nombre" })).toBeVisible();

    const row = screen.getByRole("row", { name: /reporte\.pdf/ });
    const selection = screen.getByLabelText("Seleccionar reporte.pdf");
    row.focus();
    await user.keyboard(" ");
    expect(selection).toBeChecked();

    await user.click(selection);
    expect(selection).not.toBeChecked();

    const favorite = screen.getByRole("button", {
      name: "Añadir reporte.pdf a favoritos",
    });
    favorite.focus();
    await user.keyboard(" ");
    await waitFor(() => expect(setFavorite).toHaveBeenCalledWith(report.id));
    expect(selection).not.toBeChecked();

    const open = screen.getByRole("button", { name: "Abrir reporte.pdf" });
    open.focus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(recordRecentOpen).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole("dialog", { name: "reporte.pdf" })).toBeVisible();
  });

  it("crea, renombra, mueve y envía elementos a la papelera", async () => {
    const user = userEvent.setup();
    renderExplorer();
    await screen.findByText("reporte.pdf");

    await user.click(screen.getByRole("button", { name: "Nueva carpeta" }));
    let dialog = screen.getByRole("dialog", { name: "Nueva carpeta" });
    await user.type(within(dialog).getByLabelText("Nombre"), "  Viajes  ");
    await user.click(within(dialog).getByRole("button", { name: "Crear carpeta" }));
    await waitFor(() => expect(createFolder).toHaveBeenCalledWith(root.id, "Viajes"));

    await user.click(screen.getByLabelText("Seleccionar reporte.pdf"));
    await user.click(screen.getByRole("button", { name: "Renombrar" }));
    dialog = screen.getByRole("dialog", { name: "Renombrar" });
    const nameInput = within(dialog).getByLabelText("Nombre");
    await user.clear(nameInput);
    await user.type(nameInput, "informe.pdf");
    await user.click(within(dialog).getByRole("button", { name: "Guardar" }));
    await waitFor(() =>
      expect(renameEntry).toHaveBeenCalledWith(report.id, "informe.pdf"),
    );

    await user.click(screen.getByLabelText("Seleccionar reporte.pdf"));
    await user.click(screen.getByRole("button", { name: "Mover" }));
    dialog = screen.getByRole("dialog", { name: "Mover elementos" });
    await user.click(within(dialog).getByRole("button", { name: "Fotos" }));
    await waitFor(() =>
      expect(within(dialog).getByRole("button", { name: "Mover aquí" })).toBeEnabled(),
    );
    await user.click(within(dialog).getByRole("button", { name: "Mover aquí" }));
    await waitFor(() => expect(moveEntry).toHaveBeenCalledWith(report.id, photos.id));

    await user.click(screen.getByLabelText("Seleccionar reporte.pdf"));
    await user.click(screen.getByRole("button", { name: "Papelera" }));
    dialog = screen.getByRole("dialog", { name: "Eliminar elementos" });
    await user.click(within(dialog).getByRole("button", { name: "Mover a papelera" }));
    await waitFor(() => expect(trashEntry).toHaveBeenCalledWith(report.id));
  });

  it("muestra detalles y permite abrir o descargar sin cargar el archivo en memoria", async () => {
    const user = userEvent.setup();
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    renderExplorer();

    await user.click(await screen.findByRole("button", { name: /^reporte\.pdf/ }));
    const dialog = await screen.findByRole("dialog", { name: "reporte.pdf" });
    expect(await within(dialog).findByText("application/pdf")).toBeVisible();
    await user.click(within(dialog).getByRole("button", { name: "Abrir" }));
    expect(open).toHaveBeenCalledWith(
      `/content/${report.id}`,
      "_blank",
      "noopener,noreferrer",
    );
    await user.click(within(dialog).getByRole("button", { name: "Descargar" }));
    expect(click).toHaveBeenCalledOnce();
  });

  it("abre una vista previa compatible desde la barra y los detalles", async () => {
    const user = userEvent.setup();
    renderExplorer();
    await screen.findByText("reporte.pdf");

    await user.click(screen.getByLabelText("Seleccionar reporte.pdf"));
    await user.click(screen.getByRole("button", { name: "Vista previa" }));
    expect(
      await screen.findByRole("dialog", { name: "Vista previa: reporte.pdf" }),
    ).toBeVisible();
    await waitFor(() => expect(recordRecentOpen).toHaveBeenCalledWith(report.id));
    await user.click(screen.getByRole("button", { name: "Cerrar vista previa" }));

    await user.click(screen.getByRole("button", { name: /^reporte\.pdf/ }));
    const details = await screen.findByRole("dialog", { name: "reporte.pdf" });
    await user.click(within(details).getByRole("button", { name: "Vista previa" }));
    expect(
      await screen.findByRole("dialog", { name: "Vista previa: reporte.pdf" }),
    ).toBeVisible();
  });

  it("añade una selección múltiple a la cola de la carpeta abierta", async () => {
    const user = userEvent.setup();
    renderExplorer();
    await screen.findByRole("heading", { name: "Drive" });
    const files = [
      new File(["uno"], "uno.txt", { type: "text/plain" }),
      new File(["dos"], "dos.txt", { type: "text/plain" }),
    ];

    await user.upload(screen.getByLabelText("Seleccionar archivos para subir"), files);

    expect(uploadsMock.enqueueFiles).toHaveBeenCalledWith(
      expect.any(FileList),
      root.id,
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "2 archivos añadidos a la cola.",
    );
  });

  it("acepta archivos arrastrados en la zona de la carpeta abierta", async () => {
    renderExplorer();
    await screen.findByRole("heading", { name: "Drive" });
    const dropZone = screen.getByRole("region", {
      name: "Subir archivos a esta carpeta",
    });
    const files = [new File(["contenido"], "arrastrado.txt", { type: "text/plain" })];

    fireEvent.dragEnter(dropZone);
    expect(dropZone).toHaveClass("border-brand");
    fireEvent.drop(dropZone, { dataTransfer: { files } });

    expect(uploadsMock.enqueueFiles).toHaveBeenCalledWith(files, root.id);
    expect(await screen.findByRole("status")).toHaveTextContent(
      "1 archivo añadido a la cola.",
    );
  });

  it("presenta errores de navegación y permisos de forma recuperable", async () => {
    vi.mocked(getFolderNavigation).mockRejectedValueOnce(
      new ApiClientError({
        status: 404,
        code: "storage.entry_not_found",
        message: "not found",
      }),
    );
    const user = userEvent.setup();
    renderExplorer("/files/missing");
    expect(await screen.findByText("No se pudo abrir esta ubicación")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByRole("heading", { name: "Drive" })).toBeVisible();

    vi.mocked(listFolderEntries).mockRejectedValue(
      new ApiClientError({ status: 403, code: "forbidden", message: "no" }),
    );
    renderExplorer();
    expect(
      await screen.findByText("No tienes permiso para realizar esta operación."),
    ).toBeVisible();
  });
});
