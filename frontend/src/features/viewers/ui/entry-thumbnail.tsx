import { File, FileAudio, FileImage, FileText, FileVideo } from "lucide-react";
import { useState } from "react";

import { storageContentUrl } from "@/shared/api/storage-content";
import { cn } from "@/shared/utils/cn";

import {
  getThumbnailStrategy,
  getViewerKind,
  type ViewerFile,
} from "@/features/viewers/model";

function PlaceholderIcon({ file }: { file: ViewerFile }) {
  const kind = getViewerKind(file);
  const Icon =
    kind === "image"
      ? FileImage
      : kind === "video"
        ? FileVideo
        : kind === "audio"
          ? FileAudio
          : kind === "pdf"
            ? FileText
            : File;
  return <Icon aria-hidden="true" className="size-5" />;
}

export function EntryThumbnail({ file }: { file: ViewerFile }) {
  const [failed, setFailed] = useState(false);
  const useSource = getThumbnailStrategy(file) === "source-image" && !failed;

  if (useSource) {
    return (
      <img
        alt=""
        aria-hidden="true"
        className="size-full object-cover"
        decoding="async"
        loading="lazy"
        onError={() => setFailed(true)}
        src={storageContentUrl(file.id, "inline")}
      />
    );
  }

  return (
    <span
      aria-hidden="true"
      className={cn(
        "grid size-full place-items-center",
        getViewerKind(file) === "image" ? "text-brand" : "text-muted",
      )}
    >
      <PlaceholderIcon file={file} />
    </span>
  );
}
