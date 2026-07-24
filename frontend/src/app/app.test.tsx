import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/app";
import {
  getCurrentSession,
  loginWithCookie,
  logoutCurrentSession,
  refreshAccessSession,
} from "@/features/auth/api/auth-api";
import {
  getFolderNavigation,
  listFolderEntries,
} from "@/features/explorer/api/explorer-api";
import { listActivity, recordRecentOpen } from "@/features/activity/api/activity-api";
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

vi.mock("@/features/activity/api/activity-api", () => ({
  listActivity: vi.fn(),
  setFavorite: vi.fn(),
  removeFavorite: vi.fn(),
  recordRecentOpen: vi.fn(),
}));

vi.mock("@/features/explorer/api/explorer-api", () => ({
  getFolderNavigation: vi.fn(),
  listFolderEntries: vi.fn(),
  getFileDetails: vi.fn(),
  createFolder: vi.fn(),
  renameEntry: vi.fn(),
  moveEntry: vi.fn(),
  trashEntry: vi.fn(),
  fileContentUrl: vi.fn((fileId: string) => `/api/v1/storage/files/${fileId}/content`),
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

const rootFolder = {
  id: "01912345-6789-7abc-8def-012345678900",
  parent_id: null,
  kind: "folder" as const,
  name: "Drive",
  size: null,
  mime_type: null,
  extension: null,
  checksum_sha256: null,
  current_version_number: null,
  created_at: "2026-07-18T18:00:00Z",
  updated_at: "2026-07-18T18:00:00Z",
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
    vi.mocked(getFolderNavigation)
      .mockReset()
      .mockResolvedValue({
        folder: rootFolder,
        breadcrumbs: [{ id: rootFolder.id, name: rootFolder.name }],
      });
    vi.mocked(listFolderEntries).mockReset().mockResolvedValue({
      items: [],
      nextCursor: null,
    });
    vi.mocked(listActivity).mockReset().mockResolvedValue({
      items: [],
      nextCursor: null,
    });
    vi.mocked(recordRecentOpen).mockReset().mockResolvedValue({
      entry_id: rootFolder.id,
    });
  });

  it("abre Inicio como experiencia predeterminada", async () => {
    window.history.replaceState(null, "", "/");
    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "Todo tu espacio, más cerca.",
      }),
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe("/home");
  });

  it("renderiza el shell y confirma la conexión con la API", async () => {
    window.history.replaceState(null, "", "/home");
    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "Todo tu espacio, más cerca.",
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("DriveMPVD")).not.toHaveLength(0);
    expect(await screen.findByText("API disponible")).toBeInTheDocument();
    expect(screen.getByText("DriveMPVD · versión 0.1.0")).toBeInTheDocument();
    const recents = screen.getAllByRole("link", { name: "Recientes" });
    expect(recents).not.toHaveLength(0);
    expect(recents[0]).toHaveAttribute("href", "/recents");
    const favorites = screen.getAllByRole("link", { name: "Favoritos" });
    expect(favorites).not.toHaveLength(0);
    expect(favorites[0]).toHaveAttribute("href", "/favorites");
  });

  it("muestra los accesos y la actividad reciente en el inicio", async () => {
    vi.mocked(listActivity).mockResolvedValue({
      items: [
        {
          entry: {
            ...rootFolder,
            id: "recent-folder",
            name: "Proyecto 2026",
            is_favorite: false,
          },
          occurred_at: "2026-07-20T18:00:00Z",
        },
      ],
      nextCursor: null,
    });
    window.history.replaceState(null, "", "/home");
    render(<App />);

    expect(await screen.findByText("Proyecto 2026")).toBeVisible();
    expect(screen.getAllByRole("link", { name: "Mis archivos" })[0]).toHaveAttribute(
      "href",
      "/files",
    );
    expect(
      screen.getByRole("link", { name: "Ver todos los elementos recientes" }),
    ).toHaveAttribute("href", "/recents");
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "Abrir Proyecto 2026" }));
    await waitFor(() => expect(recordRecentOpen).toHaveBeenCalledWith("recent-folder"));
    expect(window.location.pathname).toBe("/files/recent-folder");
  });

  it("abre un archivo reciente y registra la reapertura", async () => {
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    vi.mocked(listActivity).mockResolvedValue({
      items: [
        {
          entry: {
            ...rootFolder,
            id: "recent-file",
            kind: "file",
            name: "informe.pdf",
            size: 1024,
            mime_type: "application/pdf",
            extension: "pdf",
            current_version_number: 1,
            is_favorite: false,
          },
          occurred_at: "2026-07-20T18:00:00Z",
        },
      ],
      nextCursor: null,
    });
    window.history.replaceState(null, "", "/home");
    render(<App />);

    await userEvent
      .setup()
      .click(await screen.findByRole("button", { name: "Abrir informe.pdf" }));

    await waitFor(() => expect(recordRecentOpen).toHaveBeenCalledWith("recent-file"));
    expect(open).toHaveBeenCalledWith(
      "/api/v1/storage/files/recent-file/content",
      "_blank",
      "noopener,noreferrer",
    );
  });

  it("permite abrir y cerrar la navegación móvil", async () => {
    const user = userEvent.setup();
    render(<App />);
    const openButton = await screen.findByRole("button", { name: "Abrir menú" });
    const main = screen.getByRole("main");

    await user.click(openButton);
    expect(openButton).toHaveAttribute("aria-expanded", "true");
    const mobileNavigation = screen.getByRole("dialog", { name: "Navegación móvil" });
    const closeButton = within(mobileNavigation).getByRole("button", {
      name: "Cerrar menú",
    });
    expect(closeButton).toHaveFocus();
    expect(main.closest("[inert]")).toHaveAttribute("inert");

    await user.keyboard("{Shift>}{Tab}{/Shift}");
    expect(
      within(mobileNavigation).getByRole("link", { name: "Favoritos" }),
    ).toHaveFocus();

    await user.keyboard("{Escape}");
    expect(openButton).toHaveAttribute("aria-expanded", "false");
    expect(openButton).toHaveFocus();

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
    window.history.replaceState(null, "", "/home");
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
    window.history.replaceState(null, "", "/home");
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
        name: "Todo tu espacio, más cerca.",
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
