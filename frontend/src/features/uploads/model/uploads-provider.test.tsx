import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  appendUploadChunk,
  cancelUpload,
  completeUpload,
  getUploadStatus,
  startUpload,
} from "@/features/uploads/api/uploads-api";
import { UploadsProvider } from "@/features/uploads/model/uploads-provider";
import { queryNamespaces } from "@/shared/query-keys";
import { uploadTaskLabel, useUploads } from "@/features/uploads/model/uploads-context";
import { ApiClientError } from "@/shared/api/client";

vi.mock("@/features/uploads/api/uploads-api", () => ({
  UPLOAD_CHUNK_SIZE: 4,
  appendUploadChunk: vi.fn(),
  cancelUpload: vi.fn(),
  completeUpload: vi.fn(),
  getUploadStatus: vi.fn(),
  startUpload: vi.fn(),
}));

const session = {
  id: "upload-1",
  parent_id: "folder-1",
  filename: "archivo.bin",
  expected_size: 8,
  uploaded_bytes: 0,
  declared_mime_type: "application/octet-stream",
  extension: "bin",
  status: "created" as const,
  expires_at: "2026-07-19T18:00:00Z",
  checksum_sha256: null,
};

function UploadHarness({ files }: { files: File[] }) {
  const {
    cancelUpload: cancelTask,
    enqueueFiles,
    removeUpload,
    retryUpload,
    tasks,
  } = useUploads();

  return (
    <>
      <button type="button" onClick={() => enqueueFiles(files, "folder-1")}>
        Encolar archivos
      </button>
      <ul>
        {tasks.map((task) => (
          <li key={task.id} data-testid={`task-${task.file.name}`}>
            {`${task.file.name}:${task.state}:${String(task.uploadedBytes)}:${task.error ?? ""}`}
            <button type="button" onClick={() => retryUpload(task.id)}>
              Reintentar {task.file.name}
            </button>
            <button type="button" onClick={() => void cancelTask(task.id)}>
              Cancelar {task.file.name}
            </button>
            <button type="button" onClick={() => removeUpload(task.id)}>
              Quitar {task.file.name}
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}

function renderUploads(files: File[]) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");
  const view = render(
    <QueryClientProvider client={queryClient}>
      <UploadsProvider>
        <UploadHarness files={files} />
      </UploadsProvider>
    </QueryClientProvider>,
  );
  return { ...view, invalidateQueries };
}

describe("UploadsProvider", () => {
  beforeEach(() => {
    vi.mocked(startUpload).mockReset().mockResolvedValue(session);
    vi.mocked(getUploadStatus).mockReset();
    vi.mocked(appendUploadChunk)
      .mockReset()
      .mockImplementation((_uploadId, offset, chunk, _signal, onProgress) => {
        const nextOffset = offset + chunk.size;
        onProgress(nextOffset);
        return Promise.resolve({
          upload_id: session.id,
          offset: nextOffset,
          received_bytes: chunk.size,
          chunk_sha256: "checksum",
        });
      });
    vi.mocked(completeUpload)
      .mockReset()
      .mockResolvedValue({ id: "file-1", kind: "file" } as never);
    vi.mocked(cancelUpload).mockReset().mockResolvedValue(session);
  });

  it("sube una selección en bloques, publica el archivo e invalida el explorador", async () => {
    const user = userEvent.setup();
    const file = new File(["0123456789"], "archivo.bin", {
      type: "application/octet-stream",
    });
    const { invalidateQueries } = renderUploads([file]);

    await user.click(screen.getByRole("button", { name: "Encolar archivos" }));

    await waitFor(() =>
      expect(screen.getByTestId("task-archivo.bin")).toHaveTextContent(
        "archivo.bin:completed:10:",
      ),
    );
    expect(startUpload).toHaveBeenCalledWith("folder-1", file, expect.any(AbortSignal));
    expect(appendUploadChunk).toHaveBeenCalledTimes(3);
    expect(vi.mocked(appendUploadChunk).mock.calls.map((call) => call[1])).toEqual([
      0, 4, 8,
    ]);
    expect(completeUpload).toHaveBeenCalledWith(session.id, expect.any(AbortSignal));
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: queryNamespaces.explorer,
    });
  });

  it("reanuda una sesión existente después de un error recuperable", async () => {
    const user = userEvent.setup();
    const file = new File(["01234567"], "archivo.bin");
    vi.mocked(appendUploadChunk)
      .mockRejectedValueOnce(
        new ApiClientError({
          status: 503,
          code: "storage.temporarily_unavailable",
          message: "Temporalmente no disponible.",
        }),
      )
      .mockImplementation((_uploadId, offset, chunk, _signal, onProgress) => {
        const nextOffset = offset + chunk.size;
        onProgress(nextOffset);
        return Promise.resolve({
          upload_id: session.id,
          offset: nextOffset,
          received_bytes: chunk.size,
          chunk_sha256: "checksum",
        });
      });
    vi.mocked(getUploadStatus).mockResolvedValue({
      uploadedBytes: 4,
      expectedSize: file.size,
      state: "uploading",
      expiresAt: session.expires_at,
    });
    renderUploads([file]);

    await user.click(screen.getByRole("button", { name: "Encolar archivos" }));
    await waitFor(() =>
      expect(screen.getByTestId("task-archivo.bin")).toHaveTextContent("error"),
    );

    await user.click(screen.getByRole("button", { name: "Reintentar archivo.bin" }));
    await waitFor(() =>
      expect(screen.getByTestId("task-archivo.bin")).toHaveTextContent("completed"),
    );

    expect(startUpload).toHaveBeenCalledTimes(1);
    expect(getUploadStatus).toHaveBeenCalledWith(session.id, expect.any(AbortSignal));
    expect(vi.mocked(appendUploadChunk).mock.calls.map((call) => call[1])).toEqual([
      0, 4,
    ]);
  });

  it("recupera el offset del servidor cuando detecta un conflicto de bloques", async () => {
    const user = userEvent.setup();
    const file = new File(["01234567"], "archivo.bin");
    vi.mocked(appendUploadChunk)
      .mockRejectedValueOnce(
        new ApiClientError({
          status: 409,
          code: "storage.upload_offset_mismatch",
          message: "Offset distinto.",
        }),
      )
      .mockImplementation((_uploadId, offset, chunk, _signal, onProgress) => {
        const nextOffset = offset + chunk.size;
        onProgress(nextOffset);
        return Promise.resolve({
          upload_id: session.id,
          offset: nextOffset,
          received_bytes: chunk.size,
          chunk_sha256: "checksum",
        });
      });
    vi.mocked(getUploadStatus).mockResolvedValue({
      uploadedBytes: 4,
      expectedSize: file.size,
      state: "uploading",
      expiresAt: session.expires_at,
    });
    renderUploads([file]);

    await user.click(screen.getByRole("button", { name: "Encolar archivos" }));

    await waitFor(() =>
      expect(screen.getByTestId("task-archivo.bin")).toHaveTextContent("completed"),
    );
    expect(getUploadStatus).toHaveBeenCalledWith(session.id, expect.any(AbortSignal));
    expect(vi.mocked(appendUploadChunk).mock.calls.map((call) => call[1])).toEqual([
      0, 4,
    ]);
  });

  it("cancela localmente una subida activa y solicita limpiar su sesión", async () => {
    const user = userEvent.setup();
    const file = new File(["01234567"], "archivo.bin");
    vi.mocked(appendUploadChunk).mockImplementation(
      (_uploadId, _offset, _chunk, signal) =>
        new Promise((_, reject) => {
          signal.addEventListener(
            "abort",
            () => reject(new DOMException("Abortado", "AbortError")),
            { once: true },
          );
        }),
    );
    renderUploads([file]);

    await user.click(screen.getByRole("button", { name: "Encolar archivos" }));
    await waitFor(() =>
      expect(screen.getByTestId("task-archivo.bin")).toHaveTextContent("uploading"),
    );

    await user.click(screen.getByRole("button", { name: "Cancelar archivo.bin" }));
    await waitFor(() =>
      expect(screen.getByTestId("task-archivo.bin")).toHaveTextContent("cancelled"),
    );
    expect(cancelUpload).toHaveBeenCalledWith(session.id);
  });

  it.each([
    [
      new Error("network down"),
      "No fue posible completar la subida. Inténtalo de nuevo.",
    ],
    [
      new ApiClientError({
        status: 413,
        code: "storage.upload_validation_error",
        message: "too large",
      }),
      "El archivo excede el tamaño permitido.",
    ],
    [
      new ApiClientError({ status: 403, code: "forbidden", message: "forbidden" }),
      "No tienes permiso para subir en esta carpeta.",
    ],
    [
      new ApiClientError({
        status: 429,
        code: "storage.rate_limited",
        message: "limited",
        retryAfterSeconds: 7,
      }),
      "La subida está limitada. Reintenta en 7 s.",
    ],
    [
      new ApiClientError({
        status: 404,
        code: "storage.upload_not_found",
        message: "missing",
      }),
      "La sesión de subida ya no está disponible.",
    ],
  ])("muestra errores de subida útiles: %s", async (failure, message) => {
    const user = userEvent.setup();
    const file = new File(["contenido"], "error.bin");
    vi.mocked(startUpload).mockRejectedValueOnce(failure);
    renderUploads([file]);

    await user.click(screen.getByRole("button", { name: "Encolar archivos" }));

    await waitFor(() =>
      expect(screen.getByTestId("task-error.bin")).toHaveTextContent(message),
    );
  });

  it.each([
    {
      expectedSize: 8,
      state: "completed" as const,
      label: "está completada",
    },
    {
      expectedSize: 9,
      state: "uploading" as const,
      label: "corresponde a otro tamaño",
    },
  ])("no reanuda una sesión que $label", async ({ expectedSize, state }) => {
    const user = userEvent.setup();
    const file = new File(["01234567"], "mismatch.bin");
    vi.mocked(appendUploadChunk).mockRejectedValueOnce(
      new ApiClientError({
        status: 503,
        code: "storage.temporarily_unavailable",
        message: "retry",
      }),
    );
    vi.mocked(getUploadStatus).mockResolvedValue({
      uploadedBytes: 0,
      expectedSize,
      state,
      expiresAt: session.expires_at,
    });
    renderUploads([file]);

    await user.click(screen.getByRole("button", { name: "Encolar archivos" }));
    await waitFor(() =>
      expect(screen.getByTestId("task-mismatch.bin")).toHaveTextContent("error"),
    );

    await user.click(screen.getByRole("button", { name: "Reintentar mismatch.bin" }));
    await waitFor(() =>
      expect(screen.getByTestId("task-mismatch.bin")).toHaveTextContent(
        "La sesión de subida ya no puede continuar.",
      ),
    );
  });

  it("mantiene en cola una tarea activa, pero permite descartar una cancelada", async () => {
    const user = userEvent.setup();
    const file = new File(["01234567"], "discard.bin");
    vi.mocked(appendUploadChunk).mockImplementation(
      (_uploadId, _offset, _chunk, signal) =>
        new Promise((_, reject) => {
          signal.addEventListener(
            "abort",
            () => reject(new DOMException("Abortado", "AbortError")),
            { once: true },
          );
        }),
    );
    renderUploads([file]);

    await user.click(screen.getByRole("button", { name: "Encolar archivos" }));
    await waitFor(() =>
      expect(screen.getByTestId("task-discard.bin")).toHaveTextContent("uploading"),
    );

    await user.click(screen.getByRole("button", { name: "Reintentar discard.bin" }));
    expect(startUpload).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Quitar discard.bin" }));
    expect(screen.getByTestId("task-discard.bin")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Cancelar discard.bin" }));
    await waitFor(() =>
      expect(screen.getByTestId("task-discard.bin")).toHaveTextContent("cancelled"),
    );
    await user.click(screen.getByRole("button", { name: "Quitar discard.bin" }));
    expect(screen.queryByTestId("task-discard.bin")).toBeNull();
  });

  it("no agrega una tarea cuando la selección está vacía", async () => {
    const user = userEvent.setup();
    renderUploads([]);

    await user.click(screen.getByRole("button", { name: "Encolar archivos" }));

    expect(screen.queryByRole("listitem")).toBeNull();
    expect(startUpload).not.toHaveBeenCalled();
  });

  it("expone etiquetas localizadas para todos los estados", () => {
    expect(uploadTaskLabel("pending")).toBe("Pendiente");
    expect(uploadTaskLabel("uploading")).toBe("Subiendo");
    expect(uploadTaskLabel("completed")).toBe("Completada");
    expect(uploadTaskLabel("error")).toBe("Error");
    expect(uploadTaskLabel("cancelled")).toBe("Cancelada");
  });
});
