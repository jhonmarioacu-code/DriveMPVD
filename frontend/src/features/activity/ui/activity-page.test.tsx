import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ActivityPage } from "@/features/activity/ui/activity-page";
import {
  listActivity,
  recordRecentOpen,
  removeFavorite,
  setFavorite,
} from "@/features/activity/api/activity-api";

vi.mock("@/features/activity/api/activity-api", () => ({
  listActivity: vi.fn(),
  setFavorite: vi.fn(),
  removeFavorite: vi.fn(),
  recordRecentOpen: vi.fn(),
}));

const folderEntry = {
  id: "folder-id",
  parent_id: null,
  kind: "folder" as const,
  name: "Proyecto",
  size: null,
  mime_type: null,
  extension: null,
  checksum_sha256: null,
  current_version_number: null,
  created_at: "2026-07-20T12:00:00Z",
  updated_at: "2026-07-20T12:00:00Z",
  is_favorite: true,
};

function Location() {
  return <output data-testid="location">{useLocation().pathname}</output>;
}

function renderPage(kind: "favorites" | "recents") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/${kind}`]}>
        <Location />
        <Routes>
          <Route path={`/${kind}`} element={<ActivityPage kind={kind} />} />
          <Route path="/files/:folderId" element={<p>Destino de carpeta</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ActivityPage", () => {
  beforeEach(() => {
    vi.mocked(listActivity).mockReset();
    vi.mocked(setFavorite).mockReset();
    vi.mocked(removeFavorite).mockReset();
    vi.mocked(recordRecentOpen).mockReset();
    vi.mocked(setFavorite).mockResolvedValue({
      entry_id: folderEntry.id,
      is_favorite: true,
    });
    vi.mocked(removeFavorite).mockResolvedValue({
      entry_id: folderEntry.id,
      is_favorite: false,
    });
    vi.mocked(recordRecentOpen).mockResolvedValue({ entry_id: folderEntry.id });
  });

  it("muestra favoritos, permite quitarlos y abre una carpeta registrando actividad", async () => {
    const user = userEvent.setup();
    vi.mocked(listActivity).mockResolvedValue({
      items: [{ entry: folderEntry, occurred_at: "2026-07-20T13:00:00Z" }],
      nextCursor: null,
    });
    renderPage("favorites");

    expect(await screen.findByRole("heading", { name: "Favoritos" })).toBeVisible();
    expect(await screen.findByText("Proyecto")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Quitar Proyecto de favoritos" }),
    );
    await waitFor(() => expect(removeFavorite).toHaveBeenCalledWith(folderEntry.id));

    await user.click(screen.getByRole("button", { name: "Abrir Proyecto" }));
    await waitFor(() => expect(recordRecentOpen).toHaveBeenCalledWith(folderEntry.id));
    expect(screen.getByTestId("location")).toHaveTextContent("/files/folder-id");
  });

  it("explica estados vacío y recuperable de actividad", async () => {
    vi.mocked(listActivity).mockResolvedValueOnce({ items: [], nextCursor: null });
    const empty = renderPage("recents");
    expect(
      await screen.findByText("Los elementos que abras aparecerán aquí."),
    ).toBeVisible();
    empty.unmount();

    vi.mocked(listActivity).mockRejectedValueOnce(new Error("offline"));
    renderPage("recents");
    expect(await screen.findByText("No se pudo cargar recientes")).toBeVisible();
  });

  it("marca un elemento reciente como favorito", async () => {
    const user = userEvent.setup();
    vi.mocked(listActivity).mockResolvedValue({
      items: [
        {
          entry: { ...folderEntry, is_favorite: false },
          occurred_at: "2026-07-20T13:00:00Z",
        },
      ],
      nextCursor: null,
    });
    renderPage("recents");

    expect(await screen.findByText("Proyecto")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Añadir Proyecto a favoritos" }),
    );
    await waitFor(() => expect(setFavorite).toHaveBeenCalledWith(folderEntry.id));
  });
});
