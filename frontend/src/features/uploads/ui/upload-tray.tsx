import {
  CheckCircle2,
  CircleAlert,
  Clock3,
  LoaderCircle,
  RotateCcw,
  Trash2,
  XCircle,
} from "lucide-react";

import { uploadTaskLabel, useUploads } from "@/features/uploads/model/uploads-context";
import { Button } from "@/shared/ui/button";
import { cn } from "@/shared/utils/cn";

import { formatUploadBytes, uploadProgressPercentage } from "./upload-formatters";

import type { UploadTask, UploadTaskState } from "@/features/uploads/model/types";

const stateClasses: Record<UploadTaskState, string> = {
  pending: "bg-surface-raised text-muted",
  uploading: "bg-brand-soft text-brand",
  completed: "bg-success-soft text-success",
  error: "bg-danger/10 text-danger",
  cancelled: "bg-surface-raised text-muted",
};

function UploadStateIcon({ state }: { state: UploadTaskState }) {
  if (state === "uploading") {
    return <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />;
  }
  if (state === "completed") {
    return <CheckCircle2 aria-hidden="true" className="size-4" />;
  }
  if (state === "error") {
    return <CircleAlert aria-hidden="true" className="size-4" />;
  }
  if (state === "cancelled") {
    return <XCircle aria-hidden="true" className="size-4" />;
  }
  return <Clock3 aria-hidden="true" className="size-4" />;
}

function UploadTaskItem({ task }: { task: UploadTask }) {
  const { cancelUpload, removeUpload, retryUpload } = useUploads();
  const percentage = uploadProgressPercentage(task.uploadedBytes, task.file.size);
  const canCancel = task.state === "pending" || task.state === "uploading";
  const canRetry = task.state === "error" || task.state === "cancelled";
  const canRemove = !canCancel;
  const status = uploadTaskLabel(task.state);
  const transferred = formatUploadBytes(task.uploadedBytes);
  const total = formatUploadBytes(task.file.size);

  return (
    <li className="rounded-xl border border-border bg-surface-raised/55 p-3">
      <div className="flex min-w-0 items-start gap-2.5">
        <span
          className={cn(
            "mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg",
            stateClasses[task.state],
          )}
        >
          <UploadStateIcon state={task.state} />
        </span>

        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold" title={task.file.name}>
            {task.file.name}
          </p>
          <p className="mt-0.5 text-xs text-muted">
            {status} · {transferred} de {total}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-1">
          {canRetry ? (
            <Button
              aria-label={`Reintentar subida de ${task.file.name}`}
              onClick={() => retryUpload(task.id)}
              size="icon"
              title="Reintentar subida"
              type="button"
              variant="ghost"
            >
              <RotateCcw aria-hidden="true" className="size-4" />
            </Button>
          ) : null}
          {canCancel ? (
            <Button
              aria-label={`Cancelar subida de ${task.file.name}`}
              onClick={() => void cancelUpload(task.id)}
              size="icon"
              title="Cancelar subida"
              type="button"
              variant="ghost"
            >
              <XCircle aria-hidden="true" className="size-4" />
            </Button>
          ) : null}
          {canRemove ? (
            <Button
              aria-label={`Descartar ${task.file.name} de la cola`}
              onClick={() => removeUpload(task.id)}
              size="icon"
              title="Descartar de la cola"
              type="button"
              variant="ghost"
            >
              <Trash2 aria-hidden="true" className="size-4" />
            </Button>
          ) : null}
        </div>
      </div>

      <div className="mt-3">
        <progress
          aria-label={`Progreso de subida de ${task.file.name}`}
          className={cn(
            "upload-progress",
            task.state === "error" && "upload-progress-error",
            task.state === "completed" && "upload-progress-completed",
          )}
          max={task.file.size || 1}
          value={Math.min(task.uploadedBytes, task.file.size || 1)}
        >
          {percentage}%
        </progress>
      </div>

      {task.error !== null ? (
        <p className="mt-2 text-xs leading-5 text-danger" role="alert">
          {task.error}
        </p>
      ) : null}
    </li>
  );
}

export function UploadTray() {
  const { tasks } = useUploads();

  if (tasks.length === 0) return null;

  const activeCount = tasks.filter(
    (task) => task.state === "pending" || task.state === "uploading",
  ).length;

  return (
    <aside
      aria-label="Cola de subidas"
      className="fixed right-3 bottom-3 z-30 w-[calc(100%-1.5rem)] max-w-sm rounded-2xl border border-border bg-surface p-3 shadow-xl shadow-foreground/10 sm:right-5 sm:bottom-5 sm:w-96"
    >
      <div className="flex items-baseline justify-between gap-3 px-1 pb-3">
        <div>
          <h2 className="text-sm font-bold">Subidas</h2>
          <p aria-live="polite" className="mt-0.5 text-xs text-muted">
            {activeCount > 0
              ? `${String(activeCount)} en curso`
              : "Todas las subidas terminaron"}
          </p>
        </div>
        <span className="rounded-full bg-surface-raised px-2 py-0.5 text-xs font-bold text-muted">
          {String(tasks.length)}
        </span>
      </div>

      <ul className="max-h-[min(50vh,25rem)] space-y-2 overflow-y-auto pr-0.5">
        {tasks.map((task) => (
          <UploadTaskItem key={task.id} task={task} />
        ))}
      </ul>
    </aside>
  );
}
