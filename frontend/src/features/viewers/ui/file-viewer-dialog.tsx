import {
  Download,
  ExternalLink,
  FileQuestion,
  LoaderCircle,
  RotateCw,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { useState } from "react";

import {
  getViewerKind,
  useViewerSource,
  viewerErrorMessage,
  viewerKindLabel,
  type ViewerFile,
} from "@/features/viewers/model";
import { Button } from "@/shared/ui/button";
import { ModalDialog } from "@/shared/ui/modal-dialog";
import { cn } from "@/shared/utils/cn";

const imageZoomClasses: Record<number, string> = {
  0.5: "viewer-image-zoom-50",
  0.75: "viewer-image-zoom-75",
  1: "viewer-image-zoom-100",
  1.25: "viewer-image-zoom-125",
  1.5: "viewer-image-zoom-150",
  1.75: "viewer-image-zoom-175",
  2: "viewer-image-zoom-200",
  2.25: "viewer-image-zoom-225",
  2.5: "viewer-image-zoom-250",
  2.75: "viewer-image-zoom-275",
  3: "viewer-image-zoom-300",
};

const imageRotationClasses: Record<number, string> = {
  0: "viewer-image-rotate-0",
  90: "viewer-image-rotate-90",
  180: "viewer-image-rotate-180",
  270: "viewer-image-rotate-270",
};

function MediaSurface({
  file,
  kind,
  onMediaError,
  rotation,
  source,
  zoom,
}: {
  file: ViewerFile;
  kind: ReturnType<typeof getViewerKind>;
  onMediaError: () => void;
  rotation: number;
  source: string;
  zoom: number;
}) {
  if (kind === "image") {
    return (
      <div className="grid min-h-72 max-h-[65vh] place-items-center overflow-auto bg-canvas p-5 sm:min-h-96">
        <img
          alt={`Vista previa de ${file.name}`}
          className={cn(
            "viewer-image max-h-[56vh] max-w-full object-contain transition-transform duration-150",
            imageZoomClasses[zoom],
            imageRotationClasses[rotation],
          )}
          onError={onMediaError}
          src={source}
        />
      </div>
    );
  }
  if (kind === "video") {
    return (
      <div className="bg-black p-3 sm:p-5">
        <video
          aria-label={`Reproductor de vídeo: ${file.name}`}
          className="mx-auto max-h-[60vh] w-full rounded-xl"
          controls
          onError={onMediaError}
          playsInline
          preload="metadata"
          src={source}
        />
      </div>
    );
  }
  if (kind === "audio") {
    return (
      <div className="grid min-h-52 place-items-center bg-surface-raised p-6">
        <audio
          aria-label={`Reproductor de audio: ${file.name}`}
          className="w-full"
          controls
          onError={onMediaError}
          preload="metadata"
          src={source}
        />
      </div>
    );
  }
  if (kind === "pdf") {
    return (
      <iframe
        className="h-[min(65vh,50rem)] w-full bg-surface"
        onError={onMediaError}
        referrerPolicy="no-referrer"
        src={source}
        title={`Documento PDF: ${file.name}`}
      />
    );
  }
  return null;
}

interface FileViewerDialogProps {
  file: ViewerFile;
  onClose: () => void;
  onDownload: () => void;
  onOpenInNewTab: () => void;
}

function FileViewerDialogContent({
  file,
  onClose,
  onDownload,
  onOpenInNewTab,
}: FileViewerDialogProps) {
  const kind = getViewerKind(file);
  const source = useViewerSource(file);
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [mediaError, setMediaError] = useState(false);

  const imageControls =
    kind === "image" ? (
      <div className="flex flex-wrap items-center gap-1 border-b border-border bg-surface px-3 py-2">
        <Button
          aria-label="Alejar imagen"
          onClick={() => setZoom((value) => Math.max(0.5, value - 0.25))}
          size="icon"
          title="Alejar"
          type="button"
          variant="ghost"
        >
          <ZoomOut aria-hidden="true" className="size-4" />
        </Button>
        <span aria-live="polite" className="min-w-12 text-center text-xs text-muted">
          {Math.round(zoom * 100)}%
        </span>
        <Button
          aria-label="Acercar imagen"
          onClick={() => setZoom((value) => Math.min(3, value + 0.25))}
          size="icon"
          title="Acercar"
          type="button"
          variant="ghost"
        >
          <ZoomIn aria-hidden="true" className="size-4" />
        </Button>
        <Button
          aria-label="Girar imagen"
          onClick={() => setRotation((value) => (value + 90) % 360)}
          size="icon"
          title="Girar"
          type="button"
          variant="ghost"
        >
          <RotateCw aria-hidden="true" className="size-4" />
        </Button>
      </div>
    ) : null;

  return (
    <ModalDialog
      bodyClassName="p-0"
      className="max-w-5xl overflow-hidden"
      description={`Vista previa de ${viewerKindLabel(kind)}. El contenido se reproduce por streaming autenticado.`}
      footer={
        <>
          <Button onClick={onDownload} type="button" variant="secondary">
            <Download aria-hidden="true" className="size-4" />
            Descargar
          </Button>
          <Button onClick={onOpenInNewTab} type="button" variant="secondary">
            <ExternalLink aria-hidden="true" className="size-4" />
            Abrir aparte
          </Button>
        </>
      }
      onClose={onClose}
      title={file.name}
    >
      {kind === "unsupported" ? (
        <div className="grid min-h-56 place-items-center p-6 text-center">
          <div>
            <FileQuestion aria-hidden="true" className="mx-auto size-10 text-muted" />
            <p className="mt-4 font-semibold">No hay vista previa para este formato</p>
            <p className="mt-2 max-w-sm text-sm leading-6 text-muted">
              Puedes descargar el archivo para abrirlo con una aplicación compatible.
            </p>
          </div>
        </div>
      ) : source.isPending ? (
        <div className="grid min-h-56 place-items-center p-6" role="status">
          <div className="text-center">
            <LoaderCircle
              aria-hidden="true"
              className="mx-auto size-7 animate-spin text-brand"
            />
            <p className="mt-3 text-sm font-semibold">Preparando vista previa…</p>
          </div>
        </div>
      ) : source.isError || mediaError ? (
        <div className="grid min-h-56 place-items-center p-6 text-center">
          <div className="max-w-sm">
            <p className="font-semibold" role="alert">
              {mediaError
                ? "El navegador no pudo reproducir este archivo."
                : viewerErrorMessage(source.error)}
            </p>
            <p className="mt-2 text-sm leading-6 text-muted">
              Intenta descargarlo o abrirlo con una aplicación compatible.
            </p>
          </div>
        </div>
      ) : (
        <>
          {imageControls}
          <MediaSurface
            file={file}
            kind={kind}
            onMediaError={() => setMediaError(true)}
            rotation={rotation}
            source={source.data.url}
            zoom={zoom}
          />
        </>
      )}
    </ModalDialog>
  );
}

export function FileViewerDialog(props: FileViewerDialogProps) {
  return <FileViewerDialogContent key={props.file.id} {...props} />;
}
