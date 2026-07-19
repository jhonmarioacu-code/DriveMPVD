import { describe, expect, it } from "vitest";

import {
  explorerErrorMessage,
  formatFileSize,
  formatModifiedDate,
} from "@/features/explorer/model/formatters";
import { ApiClientError } from "@/shared/api/client";

describe("explorer formatters", () => {
  it("presenta tamaños y fechas con valores seguros", () => {
    expect(formatFileSize(null)).toBe("—");
    expect(formatFileSize(0)).toBe("0 B");
    expect(formatFileSize(1536)).toMatch(/1[,.]5 KB/);
    expect(formatModifiedDate("invalid")).toBe("Fecha desconocida");
    expect(formatModifiedDate("2026-07-18T18:00:00Z")).not.toBe("Fecha desconocida");
  });

  it("traduce errores públicos sin exponer detalles internos", () => {
    expect(explorerErrorMessage(new Error("secret"))).toContain(
      "No fue posible completar",
    );
    expect(
      explorerErrorMessage(
        new ApiClientError({
          status: 409,
          code: "storage.name_conflict",
          message: "internal",
        }),
      ),
    ).toContain("Ya existe");
    expect(
      explorerErrorMessage(
        new ApiClientError({ status: 403, code: "forbidden", message: "no" }),
      ),
    ).toContain("No tienes permiso");
    expect(
      explorerErrorMessage(
        new ApiClientError({ status: 500, code: "unknown", message: "secret" }),
      ),
    ).toBe("No fue posible completar la operación.");
  });
});
