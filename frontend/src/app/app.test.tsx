import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/app";
import { ApiClientError } from "@/shared/api/client";
import { getHealth } from "@/shared/api/system";

vi.mock("@/shared/api/system", () => ({
  getHealth: vi.fn(),
}));

const health = {
  status: "ok",
  service: "DriveMPVD",
  version: "0.1.0",
};

describe("App", () => {
  beforeEach(() => {
    vi.mocked(getHealth).mockResolvedValue(health);
  });

  it("renderiza el shell y confirma la conexión con la API", async () => {
    render(<App />);

    expect(
      screen.getByRole("heading", {
        name: "Tu espacio personal, preparado para lo que sigue.",
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("DriveMPVD")).not.toHaveLength(0);
    expect(await screen.findByText("API disponible")).toBeInTheDocument();
    expect(screen.getByText("DriveMPVD · versión 0.1.0")).toBeInTheDocument();
  });

  it("permite abrir y cerrar la navegación móvil", async () => {
    const user = userEvent.setup();
    render(<App />);
    const openButton = screen.getByRole("button", { name: "Abrir menú" });

    await user.click(openButton);
    expect(openButton).toHaveAttribute("aria-expanded", "true");
    await user.keyboard("{Escape}");
    expect(openButton).toHaveAttribute("aria-expanded", "false");

    await user.click(openButton);
    await user.click(screen.getByRole("button", { name: "Cerrar menú" }));
    expect(openButton).toHaveAttribute("aria-expanded", "false");
  });

  it("recorre los tres modos de tema", async () => {
    const user = userEvent.setup();
    render(<App />);

    const systemButton = screen.getByRole("button", {
      name: /Tema del sistema/,
    });
    await user.click(systemButton);
    const lightButton = screen.getByRole("button", { name: /Tema claro/ });
    expect(localStorage.getItem("drivempvd.theme")).toBe("light");

    await user.click(lightButton);
    expect(screen.getByRole("button", { name: /Tema oscuro/ })).toBeVisible();
    expect(document.documentElement).toHaveClass("dark");
  });

  it("muestra un error correlacionado y permite reintentar", async () => {
    const user = userEvent.setup();
    vi.mocked(getHealth)
      .mockRejectedValueOnce(
        new ApiClientError({
          status: 503,
          code: "database.unavailable",
          message: "No disponible.",
          requestId: "request-down",
        }),
      )
      .mockRejectedValueOnce(
        new ApiClientError({
          status: 503,
          code: "database.unavailable",
          message: "No disponible.",
          requestId: "request-down",
        }),
      )
      .mockResolvedValueOnce(health);
    render(<App />);

    expect(
      await screen.findByText("API sin conexión", undefined, { timeout: 2500 }),
    ).toBeInTheDocument();
    expect(screen.getByText("Solicitud: request-down")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar conexión" }));
    expect(await screen.findByText("API disponible")).toBeInTheDocument();
  });

  it("muestra el estado de carga mientras espera la API", async () => {
    let resolveHealth: ((value: typeof health) => void) | undefined;
    vi.mocked(getHealth).mockReturnValue(
      new Promise((resolve) => {
        resolveHealth = resolve;
      }),
    );
    render(<App />);

    expect(screen.getByText("Comprobando conexión")).toBeInTheDocument();
    resolveHealth?.(health);
    await waitFor(() => expect(screen.getByText("API disponible")).toBeVisible());
  });

  it("renderiza la ruta no encontrada y vuelve al inicio", async () => {
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/ruta-inexistente");
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "Esta página no existe" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: /Volver al inicio/ }));
    expect(
      await screen.findByRole("heading", {
        name: "Tu espacio personal, preparado para lo que sigue.",
      }),
    ).toBeVisible();
  });
});
