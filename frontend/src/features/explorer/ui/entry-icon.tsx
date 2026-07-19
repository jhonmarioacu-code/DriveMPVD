import {
  Archive,
  File,
  FileAudio,
  FileImage,
  FileSpreadsheet,
  FileText,
  FileType2,
  FileVideo,
  Folder,
  Presentation,
} from "lucide-react";

import type { StorageEntry } from "@/features/explorer/model/types";

const imageExtensions = new Set(["avif", "gif", "jpeg", "jpg", "png", "webp"]);
const audioExtensions = new Set(["aac", "flac", "m4a", "mp3", "ogg", "wav"]);
const videoExtensions = new Set(["avi", "mkv", "mov", "mp4", "webm"]);
const archiveExtensions = new Set(["7z", "rar", "tar", "zip"]);

export function EntryIcon({ entry }: { entry: StorageEntry }) {
  if (entry.kind === "folder") {
    return <Folder aria-hidden="true" className="size-5 fill-current" />;
  }
  const extension = entry.extension?.toLocaleLowerCase("en") ?? "";
  const Icon = imageExtensions.has(extension)
    ? FileImage
    : audioExtensions.has(extension)
      ? FileAudio
      : videoExtensions.has(extension)
        ? FileVideo
        : archiveExtensions.has(extension)
          ? Archive
          : extension === "pdf" || extension === "txt"
            ? FileText
            : ["csv", "ods", "xls", "xlsx"].includes(extension)
              ? FileSpreadsheet
              : ["odp", "ppt", "pptx"].includes(extension)
                ? Presentation
                : ["doc", "docx", "odt"].includes(extension)
                  ? FileType2
                  : File;
  return <Icon aria-hidden="true" className="size-5" />;
}
