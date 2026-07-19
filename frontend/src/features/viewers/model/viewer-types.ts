export type ViewerKind = "image" | "video" | "audio" | "pdf" | "unsupported";

export interface ViewerFile {
  id: string;
  name: string;
  size: number | null;
  mime_type: string | null;
  extension: string | null;
}

const mimeKinds: Record<string, ViewerKind> = {
  "application/pdf": "pdf",
  "audio/aac": "audio",
  "audio/flac": "audio",
  "audio/m4a": "audio",
  "audio/mpeg": "audio",
  "audio/mp4": "audio",
  "audio/ogg": "audio",
  "audio/wav": "audio",
  "audio/webm": "audio",
  "image/avif": "image",
  "image/gif": "image",
  "image/jpeg": "image",
  "image/png": "image",
  "image/webp": "image",
  "video/mp4": "video",
  "video/ogg": "video",
  "video/quicktime": "video",
  "video/webm": "video",
};

const extensionKinds: Record<string, ViewerKind> = {
  aac: "audio",
  avif: "image",
  flac: "audio",
  gif: "image",
  jpeg: "image",
  jpg: "image",
  m4a: "audio",
  mkv: "video",
  mov: "video",
  mp3: "audio",
  mp4: "video",
  ogg: "audio",
  pdf: "pdf",
  png: "image",
  wav: "audio",
  webm: "video",
  webp: "image",
};

export function getViewerKind(file: Pick<ViewerFile, "mime_type" | "extension">) {
  const mime = file.mime_type?.toLocaleLowerCase("en");
  if (mime !== undefined && mimeKinds[mime] !== undefined) return mimeKinds[mime];
  const extension = file.extension?.toLocaleLowerCase("en");
  return extension === undefined
    ? "unsupported"
    : (extensionKinds[extension] ?? "unsupported");
}

export function isPreviewable(file: Pick<ViewerFile, "mime_type" | "extension">) {
  return getViewerKind(file) !== "unsupported";
}

export function viewerKindLabel(kind: ViewerKind) {
  const labels: Record<ViewerKind, string> = {
    image: "imagen",
    video: "vídeo",
    audio: "audio",
    pdf: "PDF",
    unsupported: "archivo",
  };
  return labels[kind];
}
