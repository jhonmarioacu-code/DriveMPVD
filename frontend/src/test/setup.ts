import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

const matchMedia = vi.fn((query: string): MediaQueryList => ({
  matches: false,
  media: query,
  onchange: null,
  addListener: vi.fn(),
  removeListener: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  dispatchEvent: vi.fn(() => true),
}));

Object.defineProperty(window, "matchMedia", {
  configurable: true,
  writable: true,
  value: matchMedia,
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  for (const cookie of document.cookie.split(";")) {
    const name = cookie.split("=")[0]?.trim();
    if (name) document.cookie = `${name}=; Max-Age=0; path=/`;
  }
  document.documentElement.className = "";
  delete document.documentElement.dataset.theme;
  window.history.replaceState(null, "", "/");
  vi.clearAllMocks();
});
