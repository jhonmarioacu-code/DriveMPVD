import { createContext, useContext } from "react";

import type { UploadTask, UploadTaskState } from "./types";

// ─── State context (mutable — consumers re-render on every task update) ──────

export interface UploadsStateValue {
  tasks: UploadTask[];
}

export const UploadsStateContext =
  createContext<UploadsStateValue | null>(null);

export function useUploadsState() {
  const value = useContext(UploadsStateContext);
  if (value === null) {
    throw new Error("useUploadsState debe usarse dentro de UploadsProvider.");
  }
  return value;
}

// ─── Dispatch context (stable — consumers never re-render from task ticks) ───

export interface UploadsDispatchValue {
  enqueueFiles: (files: FileList | File[], parentId: string) => void;
  retryUpload: (taskId: string) => void;
  cancelUpload: (taskId: string) => Promise<void>;
  removeUpload: (taskId: string) => void;
}

export const UploadsDispatchContext =
  createContext<UploadsDispatchValue | null>(null);

export function useUploadsDispatch() {
  const value = useContext(UploadsDispatchContext);
  if (value === null) {
    throw new Error(
      "useUploadsDispatch debe usarse dentro de UploadsProvider.",
    );
  }
  return value;
}

// ─── Combined hook (backward-compatible — provides both state and dispatch) ──

export interface UploadsContextValue
  extends UploadsStateValue,
    UploadsDispatchValue {}

/**
 * Returns all uploads state and dispatch functions.
 *
 * Prefer `useUploadsDispatch()` in components that only need to enqueue or
 * manage uploads but do not render progress — they will then skip re-renders
 * during active upload ticks.
 */
export function useUploads(): UploadsContextValue {
  const stateCtx = useContext(UploadsStateContext);
  const dispatchCtx = useContext(UploadsDispatchContext);
  if (stateCtx === null || dispatchCtx === null) {
    throw new Error("useUploads debe usarse dentro de UploadsProvider.");
  }
  return { ...stateCtx, ...dispatchCtx };
}

// ─── Utilities ───────────────────────────────────────────────────────────────

/** @deprecated Kept for backward compatibility. Import UploadsContext from here. */
export const UploadsContext = UploadsStateContext;

export function uploadTaskLabel(state: UploadTaskState) {
  const labels: Record<UploadTaskState, string> = {
    pending: "Pendiente",
    uploading: "Subiendo",
    completed: "Completada",
    error: "Error",
    cancelled: "Cancelada",
  };
  return labels[state];
}
