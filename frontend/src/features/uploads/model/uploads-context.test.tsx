import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useUploads } from "@/features/uploads/model/uploads-context";

function MissingUploadsProvider() {
  useUploads();
  return null;
}

describe("useUploads", () => {
  it("explica cuándo se usa fuera de su proveedor", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);

    expect(() => render(<MissingUploadsProvider />)).toThrow(
      "useUploads debe usarse dentro de UploadsProvider.",
    );

    consoleError.mockRestore();
  });
});
