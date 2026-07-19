import { createContext, useContext } from "react";

import type { UploadTask, UploadTaskState } from "./types";

export interface UploadsContextValue {
  tasks: UploadTask[];
  enqueueFiles: (files: FileList | File[], parentId: string) => void;
  retryUpload: (taskId: string) => void;
  cancelUpload: (taskId: string) => Promise<void>;
  removeUpload: (taskId: string) => void;
}

export const UploadsContext = createContext<UploadsContextValue | null>(null);

export function useUploads() {
  const value = useContext(UploadsContext);
  if (value === null) {
    throw new Error("useUploads debe usarse dentro de UploadsProvider.");
  }
  return value;
}

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
