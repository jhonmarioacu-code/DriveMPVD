import { ApiClientError } from "@/shared/api/client";

export function formatFileSize(value: number | null) {
  if (value === null) return "—";
  if (value === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(
    Math.floor(Math.log(value) / Math.log(1024)),
    units.length - 1,
  );
  const scaled = value / 1024 ** index;
  return `${new Intl.NumberFormat("es", {
    maximumFractionDigits: index === 0 ? 0 : 1,
  }).format(scaled)} ${units[index] ?? "B"}`;
}

export function formatModifiedDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Fecha desconocida";
  return new Intl.DateTimeFormat("es", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function explorerErrorMessage(error: unknown) {
  if (!(error instanceof ApiClientError)) {
    return "No fue posible completar la operación. Inténtalo de nuevo.";
  }
  const messages: Record<string, string> = {
    "storage.name_conflict": "Ya existe un elemento con ese nombre.",
    "storage.invalid_entry_name": "El nombre contiene caracteres no permitidos.",
    "storage.invalid_move": "No se puede mover el elemento a esa carpeta.",
    "storage.invalid_state_transition": "La operación no es válida para este elemento.",
    "storage.entry_not_found": "El elemento ya no existe o no está disponible.",
    "auth.csrf_validation_failed": "La sesión perdió su validación de seguridad.",
  };
  if (error.status === 403) return "No tienes permiso para realizar esta operación.";
  return messages[error.code] ?? "No fue posible completar la operación.";
}
