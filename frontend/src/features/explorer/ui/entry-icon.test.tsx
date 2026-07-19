import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EntryIcon } from "@/features/explorer/ui/entry-icon";

import type { StorageEntry } from "@/features/explorer/model/types";

function iconFor(extension: string | null, kind: "file" | "folder" = "file") {
  const entry: StorageEntry = {
    id: extension ?? "folder",
    parent_id: "root",
    kind,
    name: "entry",
    size: kind === "file" ? 1 : null,
    mime_type: null,
    extension,
    checksum_sha256: null,
    current_version_number: kind === "file" ? 1 : null,
    created_at: "2026-07-18T18:00:00Z",
    updated_at: "2026-07-18T18:00:00Z",
  };
  return render(<EntryIcon entry={entry} />).container.querySelector("svg");
}

describe("EntryIcon", () => {
  it.each([
    ["JPG", "lucide-file-image"],
    ["mp3", "lucide-file-audio"],
    ["mp4", "lucide-file-video"],
    ["zip", "lucide-archive"],
    ["pdf", "lucide-file-text"],
    ["xlsx", "lucide-file-spreadsheet"],
    ["pptx", "lucide-presentation"],
    ["docx", "lucide-file-type2"],
    [null, "lucide-file"],
  ])("elige el icono para %s", (extension, expectedClass) => {
    expect(iconFor(extension)).toHaveClass(expectedClass);
  });

  it("presenta las carpetas con su icono propio", () => {
    expect(iconFor(null, "folder")).toHaveClass("lucide-folder");
  });
});
