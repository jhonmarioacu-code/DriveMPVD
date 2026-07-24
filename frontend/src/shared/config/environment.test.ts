import { describe, expect, it } from "vitest";

import { normalizeApiBaseUrl } from "@/shared/config/environment";

describe("normalizeApiBaseUrl", () => {
  it("uses the same-origin API default and normalizes a trailing slash", () => {
    expect(normalizeApiBaseUrl(undefined)).toBe("/api/v1");
    expect(normalizeApiBaseUrl(" /api/v1/ ")).toBe("/api/v1");
  });

  it("accepts another root-relative path for local development", () => {
    expect(normalizeApiBaseUrl("/api/test")).toBe("/api/test");
  });

  it("rejects absolute, scheme-relative, and backslash URL values", () => {
    for (const value of ["https://api.example.test", "//api.example.test", "/\\evil"]) {
      expect(() => normalizeApiBaseUrl(value)).toThrow(
        "VITE_API_BASE_URL must be a same-origin root-relative path.",
      );
    }
  });
});
