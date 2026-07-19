import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/app";
import {
  getCurrentSession,
  loginWithCookie,
  logoutCurrentSession,
  refreshAccessSession,
} from "@/features/auth/api/auth-api";
import { ApiClientError } from "@/shared/api/client";
import { getHealth } from "@/shared/api/system";

vi.mock("@/features/auth/api/auth-api", () => ({
  getCurrentSession: vi.fn(),
  loginWithCookie: vi.fn(),
  logoutCurrentSession: vi.fn(),
  refreshAccessSession: vi.fn(),
  isAuthenticationFailure: (error: unknown) =>
    typeof error === "object" &&
    error !== null &&
    "status" in error &&
    (error.status === 401 || error.status === 403),
}));

vi.mock("@/shared/api/system", () => ({
  getHealth: vi.fn(),
}));

const health = {
  status: "ok",
  service: "DriveMPVD",
  version: "0.1.0",
};

const admin = {
  adminId: "01912345-6789-7abc-8def-0123456789ab",
  sessionId: "01912345-6789-7abc-8def-0123456789ac",
  username: "Admin",
};

function authenticationError(status = 401, code = "auth.authentication_required") {
  return new ApiClientError({ status, code, message: "Authentication required." });
}

describe("App", () => {
  beforeEach(() => {
    vi.mocked(getCurrentSession).mockReset().mockResolvedValue(admin);
    vi.mocked(loginWithCookie).mockReset().mockResolvedValue({
      session_id: admin.sessionId,
      token_type: "Bearer",
      access_token: null,
      refresh_token: null,
      access_expires_at: "2026-07-18T22:00:00Z",
      refresh_expires_at: "2026-07-25T22:00:00Z",
    });
    vi.mocked(logoutCurrentSession).mockReset().mockResolvedValue(undefined);
    vi.mocked(refreshAccessSession).mockReset().mockResolvedValue(true);
    vi.mocked(getHealth).mockResolvedValue(health);
  });

  it("renderiza el shell y confirma la conexión con la API", async () => {
    render(<App />);

    expect(
      await screen.findByRole("heading", {
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
    const openButton = await screen.findByRole("button", { name: "Abrir menú" });

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

    const systemButton = await screen.findByRole("button", {
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

    expect(await screen.findByText("Comprobando conexión")).toBeInTheDocument();
    resolveHealth?.(health);
    await waitFor(() => expect(screen.getByText("API disponible")).toBeVisible());
  });

  it("renderiza la ruta no encontrada y vuelve al inicio", async () => {
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/ruta-inexistente");
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Esta página no existe" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: /Volver al inicio/ }));
    expect(
      await screen.findByRole("heading", {
        name: "Tu espacio personal, preparado para lo que sigue.",
      }),
    ).toBeVisible();
  });

  it("redirige al login cuando no existe una sesión", async () => {
    vi.mocked(getCurrentSession).mockRejectedValue(authenticationError());
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Inicia sesión" })).toBeVisible();
    expect(window.location.pathname).toBe("/login");
  });

  it("inicia sesión con cookies y recupera el destino privado", async () => {
    const user = userEvent.setup();
    vi.mocked(getCurrentSession)
      .mockRejectedValueOnce(authenticationError())
      .mockResolvedValueOnce(admin);
    window.history.replaceState(null, "", "/ruta-inexistente?origen=login");
    render(<App />);

    await user.type(await screen.findByLabelText("Usuario"), "  Admin  ");
    await user.type(screen.getByLabelText("Contraseña"), "correct password");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(loginWithCookie).toHaveBeenCalledWith({
      username: "Admin",
      password: "correct password",
    });
    expect(
      await screen.findByRole("heading", { name: "Esta página no existe" }),
    ).toBeVisible();
    expect(window.location.search).toBe("?origen=login");
  });

  it("valida el formulario y traduce credenciales incorrectas", async () => {
    const user = userEvent.setup();
    vi.mocked(getCurrentSession).mockRejectedValue(authenticationError());
    vi.mocked(loginWithCookie).mockRejectedValue(
      authenticationError(401, "auth.invalid_credentials"),
    );
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Entrar" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Escribe tu usuario y contraseña.",
    );

    await user.type(screen.getByLabelText("Usuario"), "Admin");
    await user.type(screen.getByLabelText("Contraseña"), "incorrecta");
    await user.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El usuario o la contraseña no son correctos.",
    );
    expect(screen.getByLabelText("Contraseña")).toHaveValue("");
  });

  it("permite mostrar la contraseña y presenta errores de inicialización", async () => {
    const user = userEvent.setup();
    vi.mocked(getCurrentSession).mockRejectedValue(new Error("API down"));
    render(<App />);

    expect(await screen.findByText(/No fue posible comprobar la sesión/)).toBeVisible();
    const password = screen.getByLabelText("Contraseña");
    expect(password).toHaveAttribute("type", "password");
    await user.click(screen.getByRole("button", { name: "Mostrar contraseña" }));
    expect(password).toHaveAttribute("type", "text");
  });

  it("cierra la sesión y vuelve al acceso público", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Cerrar sesión" }));
    expect(logoutCurrentSession).toHaveBeenCalledOnce();
    expect(await screen.findByRole("heading", { name: "Inicia sesión" })).toBeVisible();
  });
});
