import { getViewerKind, type ViewerFile } from "./viewer-types";

export const MAX_INLINE_THUMBNAIL_BYTES = 1024 * 1024;

export type ThumbnailStrategy = "source-image" | "placeholder";

export function getThumbnailStrategy(file: ViewerFile): ThumbnailStrategy {
  return getViewerKind(file) === "image" &&
    file.size !== null &&
    file.size <= MAX_INLINE_THUMBNAIL_BYTES
    ? "source-image"
    : "placeholder";
}
