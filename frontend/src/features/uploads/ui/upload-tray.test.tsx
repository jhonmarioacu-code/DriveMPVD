import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  UploadsDispatchContext,
  UploadsStateContext,
  type UploadsDispatchValue,
  type UploadsStateValue,
} from "@/features/uploads/model/uploads-context";
import { UploadTray } from "@/features/uploads/ui/upload-tray";

import type { UploadTask, UploadTaskState } from "@/features/uploads/model/types";

function task(
  id: string,
  state: UploadTaskState,
  options: Partial<Pick<UploadTask, "uploadedBytes" | "error">> = {},
): UploadTask {
  return {
    id,
    file: new File(["contenido"], `${id}.txt`, { type: "text/plain" }),
    parentId: "folder-1",
    state,
    uploadId: "upload-1",
    uploadedBytes: 0,
    error: null,
    completedEntry: null,
    ...options,
  };
}

function renderTray(tasks: UploadTask[]) {
  const actions: UploadsDispatchValue = {
    enqueueFiles: vi.fn(),
    retryUpload: vi.fn(),
    cancelUpload: vi.fn().mockResolvedValue(undefined),
    removeUpload: vi.fn(),
  };
  const stateValue: UploadsStateValue = { tasks };

  return {
    ...render(
      <UploadsDispatchContext.Provider value={actions}>
        <UploadsStateContext.Provider value={stateValue}>
          <UploadTray />
        </UploadsStateContext.Provider>
      </UploadsDispatchContext.Provider>,
    ),
    actions,
  };
}

describe("UploadTray", () => {
  it("no renderiza una bandeja cuando no hay transferencias", () => {
    renderTray([]);

    expect(screen.queryByRole("complementary", { name: "Cola de subidas" })).toBeNull();
  });

  it("presenta todos los estados, progreso y acciones de una cola", async () => {
    const user = userEvent.setup();
    const pending = task("pending", "pending");
    const uploading = task("uploading", "uploading", { uploadedBytes: 4 });
    const completed = task("completed", "completed", { uploadedBytes: 9 });
    const failed = task("failed", "error", { error: "Sin conexión" });
    const cancelled = task("cancelled", "cancelled");
    const { actions } = renderTray([pending, uploading, completed, failed, cancelled]);

    expect(
      screen.getByRole("complementary", { name: "Cola de subidas" }),
    ).toBeVisible();
    expect(screen.getByText("2 en curso")).toBeVisible();
    expect(screen.getByText("Sin conexión")).toHaveRole("alert");
    expect(
      screen.getByLabelText("Progreso de subida de uploading.txt"),
    ).toHaveAttribute("value", "4");
    expect(
      screen.getByLabelText("Progreso de subida de completed.txt"),
    ).toHaveAttribute("value", "9");

    await user.click(screen.getByLabelText("Cancelar subida de pending.txt"));
    await user.click(screen.getByLabelText("Cancelar subida de uploading.txt"));
    await user.click(screen.getByLabelText("Reintentar subida de failed.txt"));
    await user.click(screen.getByLabelText("Reintentar subida de cancelled.txt"));
    await user.click(screen.getByLabelText("Descartar completed.txt de la cola"));

    expect(actions.cancelUpload).toHaveBeenNthCalledWith(1, pending.id);
    expect(actions.cancelUpload).toHaveBeenNthCalledWith(2, uploading.id);
    expect(actions.retryUpload).toHaveBeenNthCalledWith(1, failed.id);
    expect(actions.retryUpload).toHaveBeenNthCalledWith(2, cancelled.id);
    expect(actions.removeUpload).toHaveBeenCalledWith(completed.id);
  });

  it("anuncia que terminó la cola y admite archivos vacíos", () => {
    const empty = task("empty", "completed", {
      uploadedBytes: 0,
    });
    empty.file = new File([], "empty.txt", { type: "text/plain" });
    renderTray([empty]);

    expect(screen.getByText("Todas las subidas terminaron")).toBeVisible();
    expect(screen.getByLabelText("Progreso de subida de empty.txt")).toHaveAttribute(
      "max",
      "1",
    );
  });
});
