import { useQuery } from "@tanstack/react-query";

import { ApiClientError } from "@/shared/api/client";
import { inspectStorageContent, storageContentUrl } from "@/shared/api/storage-content";

import { getViewerKind, type ViewerFile } from "./viewer-types";

export class ViewerContentError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ViewerContentError";
  }
}

export function useViewerSource(file: ViewerFile) {
  const kind = getViewerKind(file);

  return useQuery({
    queryKey: ["viewer-content", file.id, kind],
    enabled: kind !== "unsupported",
    retry: false,
    staleTime: 60_000,
    queryFn: async ({ signal }) => {
      const headers = await inspectStorageContent(file.id, "inline", signal);
      const disposition = headers.get("content-disposition")?.toLocaleLowerCase("en");
      if (!disposition?.startsWith("inline")) {
        throw new ViewerContentError(
          "El servidor no permite mostrar este tipo de archivo en el navegador.",
        );
      }
      return {
        contentType: headers.get("content-type") ?? file.mime_type,
        url: storageContentUrl(file.id, "inline"),
      };
    },
  });
}

export function viewerErrorMessage(error: unknown) {
  if (error instanceof ViewerContentError) return error.message;
  if (!(error instanceof ApiClientError)) {
    return "No fue posible preparar la vista previa. Inténtalo de nuevo.";
  }
  if (error.status === 403) return "No tienes permiso para abrir este archivo.";
  if (error.status === 404) return "El archivo ya no está disponible.";
  return "No fue posible preparar la vista previa. Inténtalo de nuevo.";
}
