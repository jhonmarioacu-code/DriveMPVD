import { useQueryClient } from "@tanstack/react-query";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";

import {
  UPLOAD_CHUNK_SIZE,
  appendUploadChunk,
  cancelUpload,
  completeUpload,
  getUploadStatus,
  startUpload,
} from "@/features/uploads/api/uploads-api";
import {
  UploadsContext,
  type UploadsContextValue,
} from "@/features/uploads/model/uploads-context";
import { createProgressReporter } from "@/features/uploads/model/progress-reporter";
import { ApiClientError } from "@/shared/api/client";

import type { UploadTask } from "@/features/uploads/model/types";

const MAX_CONCURRENT_UPLOADS = 2;

function newTaskId() {
  return crypto.randomUUID();
}

function isWritableSession(state: string) {
  return state === "created" || state === "uploading";
}

function uploadErrorMessage(error: unknown) {
  if (!(error instanceof ApiClientError)) {
    return "No fue posible completar la subida. Inténtalo de nuevo.";
  }
  const messages: Record<string, string> = {
    "storage.name_conflict": "Ya existe un archivo con ese nombre en la carpeta.",
    "storage.upload_not_found": "La sesión de subida ya no está disponible.",
    "storage.upload_state_conflict": "La sesión de subida ya no puede continuar.",
    "storage.upload_validation_error": "El archivo no cumple las reglas de subida.",
    "auth.csrf_validation_failed": "La sesión perdió su validación de seguridad.",
  };
  if (error.status === 413) return "El archivo excede el tamaño permitido.";
  if (error.status === 403) return "No tienes permiso para subir en esta carpeta.";
  if (error.retryAfterSeconds !== null) {
    return `La subida está limitada. Reintenta en ${String(error.retryAfterSeconds)} s.`;
  }
  return messages[error.code] ?? "No fue posible completar la subida.";
}

export function UploadsProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const [tasks, setTasks] = useState<UploadTask[]>([]);
  const [queueTick, setQueueTick] = useState(0);
  const tasksRef = useRef<UploadTask[]>([]);
  const activeTaskIds = useRef(new Set<string>());
  const controllers = useRef(new Map<string, AbortController>());

  const replaceTasks = useCallback((next: UploadTask[]) => {
    tasksRef.current = next;
    setTasks(next);
  }, []);

  const updateTask = useCallback(
    (taskId: string, patch: Partial<UploadTask>) => {
      const current = tasksRef.current.find((task) => task.id === taskId);
      if (current === undefined) return null;
      const nextTask = { ...current, ...patch };
      replaceTasks(
        tasksRef.current.map((task) => (task.id === taskId ? nextTask : task)),
      );
      return nextTask;
    },
    [replaceTasks],
  );

  const processUpload = useCallback(
    async (taskId: string) => {
      const initialTask = tasksRef.current.find((task) => task.id === taskId);
      if (initialTask?.state !== "pending") return;

      const controller = new AbortController();
      const progressReporter = createProgressReporter((uploadedBytes) => {
        updateTask(taskId, {
          uploadedBytes: Math.min(uploadedBytes, initialTask.file.size),
        });
      });
      controllers.current.set(taskId, controller);
      updateTask(taskId, { state: "uploading", error: null });

      try {
        let task: UploadTask = initialTask;
        let uploadId = task.uploadId;
        let offset = task.uploadedBytes;

        if (uploadId === null) {
          const session = await startUpload(
            task.parentId,
            task.file,
            controller.signal,
          );
          uploadId = session.id;
          offset = session.uploaded_bytes;
          const updatedTask = updateTask(taskId, {
            uploadId,
            uploadedBytes: offset,
          });
          if (updatedTask === null) return;
          task = updatedTask;
        } else {
          const status = await getUploadStatus(uploadId, controller.signal);
          if (
            !isWritableSession(status.state) ||
            status.expectedSize !== task.file.size
          ) {
            throw new ApiClientError({
              status: 409,
              code: "storage.upload_state_conflict",
              message: "La sesión de subida no coincide con el archivo.",
            });
          }
          offset = status.uploadedBytes;
          const updatedTask = updateTask(taskId, { uploadedBytes: offset });
          if (updatedTask === null) return;
          task = updatedTask;
        }

        while (offset < task.file.size) {
          const chunk = task.file.slice(offset, offset + UPLOAD_CHUNK_SIZE);
          try {
            const result = await appendUploadChunk(
              uploadId,
              offset,
              chunk,
              controller.signal,
              (uploadedBytes) => {
                progressReporter.report(uploadedBytes);
              },
            );
            // Flush any coalesced browser event before applying the authoritative
            // server offset, so a delayed event cannot move the UI backwards.
            progressReporter.flush();
            offset = result.offset;
            const updatedTask = updateTask(taskId, { uploadedBytes: offset });
            if (updatedTask === null) return;
            task = updatedTask;
          } catch (error) {
            if (
              error instanceof ApiClientError &&
              error.code === "storage.upload_offset_mismatch"
            ) {
              const status = await getUploadStatus(uploadId, controller.signal);
              if (!isWritableSession(status.state)) throw error;
              offset = status.uploadedBytes;
              const updatedTask = updateTask(taskId, { uploadedBytes: offset });
              if (updatedTask === null) return;
              task = updatedTask;
              continue;
            }
            throw error;
          }
        }

        const completedEntry = await completeUpload(uploadId, controller.signal);
        updateTask(taskId, {
          state: "completed",
          uploadedBytes: task.file.size,
          completedEntry,
          error: null,
        });
        await queryClient.invalidateQueries({ queryKey: ["explorer"] });
      } catch (error) {
        const currentTask = tasksRef.current.find((task) => task.id === taskId);
        if (controller.signal.aborted || currentTask?.state === "cancelled") return;
        updateTask(taskId, { state: "error", error: uploadErrorMessage(error) });
      } finally {
        progressReporter.cancel();
        controllers.current.delete(taskId);
      }
    },
    [queryClient, updateTask],
  );

  useEffect(() => {
    const availableSlots = MAX_CONCURRENT_UPLOADS - activeTaskIds.current.size;
    if (availableSlots <= 0) return;
    const pendingTasks = tasks
      .filter((task) => task.state === "pending")
      .slice(0, availableSlots);
    for (const task of pendingTasks) {
      activeTaskIds.current.add(task.id);
      void processUpload(task.id).finally(() => {
        activeTaskIds.current.delete(task.id);
        setQueueTick((value) => value + 1);
      });
    }
  }, [processUpload, queueTick, tasks]);

  useEffect(
    () => () => {
      for (const controller of controllers.current.values()) controller.abort();
    },
    [],
  );

  const enqueueFiles = useCallback(
    (files: FileList | File[], parentId: string) => {
      const additions = Array.from(files).map<UploadTask>((file) => ({
        id: newTaskId(),
        file,
        parentId,
        state: "pending",
        uploadId: null,
        uploadedBytes: 0,
        error: null,
        completedEntry: null,
      }));
      if (additions.length > 0) replaceTasks([...tasksRef.current, ...additions]);
    },
    [replaceTasks],
  );

  const retryUpload = useCallback(
    (taskId: string) => {
      const task = tasksRef.current.find((item) => item.id === taskId);
      if (
        task === undefined ||
        task.state === "pending" ||
        task.state === "uploading" ||
        task.state === "completed"
      ) {
        return;
      }
      const cancelled = task.state === "cancelled";
      updateTask(taskId, {
        state: "pending",
        error: null,
        uploadId: cancelled ? null : task.uploadId,
        uploadedBytes: cancelled ? 0 : task.uploadedBytes,
      });
    },
    [updateTask],
  );

  const cancelTask = useCallback(
    async (taskId: string) => {
      const task = tasksRef.current.find((item) => item.id === taskId);
      if (
        task === undefined ||
        task.state === "completed" ||
        task.state === "cancelled"
      ) {
        return;
      }
      updateTask(taskId, { state: "cancelled", error: null });
      controllers.current.get(taskId)?.abort();
      if (task.uploadId !== null) {
        try {
          await cancelUpload(task.uploadId);
        } catch {
          // The local task remains cancelled even if the server already expired it.
        }
      }
    },
    [updateTask],
  );

  const removeUpload = useCallback(
    (taskId: string) => {
      const task = tasksRef.current.find((item) => item.id === taskId);
      if (task?.state === "uploading" || task?.state === "pending") return;
      replaceTasks(tasksRef.current.filter((task) => task.id !== taskId));
    },
    [replaceTasks],
  );

  const value = useMemo<UploadsContextValue>(
    () => ({
      tasks,
      enqueueFiles,
      retryUpload,
      cancelUpload: cancelTask,
      removeUpload,
    }),
    [cancelTask, enqueueFiles, removeUpload, retryUpload, tasks],
  );

  return <UploadsContext.Provider value={value}>{children}</UploadsContext.Provider>;
}
