import { describe, expect, it } from "vitest";

import {
  formatUploadBytes,
  uploadProgressPercentage,
} from "@/features/uploads/ui/upload-formatters";

describe("upload formatters", () => {
  it("formatea bytes vacíos, pequeños, grandes y por encima de la última unidad", () => {
    expect(formatUploadBytes(0)).toBe("0 B");
    expect(formatUploadBytes(-1)).toBe("0 B");
    expect(formatUploadBytes(12)).toBe("12 B");
    expect(formatUploadBytes(1536)).toBe("1,5 KB");
    expect(formatUploadBytes(1024 ** 6)).toBe("1.048.576 TB");
  });

  it("limita el progreso a un rango seguro y considera completo un archivo vacío", () => {
    expect(uploadProgressPercentage(0, 0)).toBe(100);
    expect(uploadProgressPercentage(-2, 10)).toBe(0);
    expect(uploadProgressPercentage(5, 10)).toBe(50);
    expect(uploadProgressPercentage(12, 10)).toBe(100);
  });
});
