import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ThemeProvider, useTheme } from "@/app/providers/theme-provider";

function ThemeHarness() {
  const { resolvedTheme, setTheme, theme } = useTheme();
  return (
    <div>
      <output>{`${theme}:${resolvedTheme}`}</output>
      <button onClick={() => setTheme("dark")} type="button">
        Oscuro
      </button>
    </div>
  );
}

describe("ThemeProvider", () => {
  it("usa el sistema por defecto y persiste una selección", async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <ThemeHarness />
      </ThemeProvider>,
    );

    expect(screen.getByText("system:light")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Oscuro" }));

    expect(screen.getByText("dark:dark")).toBeInTheDocument();
    expect(document.documentElement).toHaveClass("dark");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(localStorage.getItem("drivempvd.theme")).toBe("dark");
  });

  it("restaura una preferencia válida e ignora valores desconocidos", () => {
    localStorage.setItem("drivempvd.theme", "light");
    const { unmount } = render(
      <ThemeProvider>
        <ThemeHarness />
      </ThemeProvider>,
    );
    expect(screen.getByText("light:light")).toBeInTheDocument();
    unmount();

    localStorage.setItem("drivempvd.theme", "sepia");
    render(
      <ThemeProvider>
        <ThemeHarness />
      </ThemeProvider>,
    );
    expect(screen.getByText("system:light")).toBeInTheDocument();
  });

  it("reacciona al cambio del esquema del sistema", () => {
    let listener: (() => void) | undefined;
    const mediaQuery = {
      matches: true,
      media: "(prefers-color-scheme: dark)",
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn((_event: string, callback: () => void) => {
        listener = callback;
      }),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(() => true),
    } as unknown as MediaQueryList;
    vi.mocked(window.matchMedia).mockReturnValue(mediaQuery);

    render(
      <ThemeProvider>
        <ThemeHarness />
      </ThemeProvider>,
    );
    expect(screen.getByText("system:dark")).toBeInTheDocument();

    Object.defineProperty(mediaQuery, "matches", { value: false });
    act(() => listener?.());
    expect(screen.getByText("system:light")).toBeInTheDocument();
  });

  it("exige el proveedor para consumir el contexto", () => {
    expect(() => render(<ThemeHarness />)).toThrow(
      "useTheme debe utilizarse dentro de ThemeProvider.",
    );
  });
});
