import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ExplorerDialog } from "@/features/explorer/ui/explorer-dialog";

describe("ExplorerDialog", () => {
  it("expone título, descripción y pie y permite cerrar", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const { container } = render(
      <ExplorerDialog
        description="Descripción segura"
        footer={<button type="button">Confirmar</button>}
        onClose={onClose}
        title="Acción"
      >
        Contenido
      </ExplorerDialog>,
    );

    const dialog = screen.getByRole("dialog", { name: "Acción" });
    expect(dialog).toHaveAccessibleDescription("Descripción segura");
    expect(screen.getByRole("button", { name: "Confirmar" })).toBeVisible();
    fireEvent.mouseDown(dialog);
    expect(onClose).not.toHaveBeenCalled();
    const backdrop = container.firstElementChild;
    if (backdrop === null) throw new Error("No se renderizó el fondo del diálogo.");
    fireEvent.mouseDown(backdrop);
    expect(onClose).toHaveBeenCalledOnce();
    await user.click(screen.getByRole("button", { name: "Cerrar" }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("admite contenido mínimo y solo responde a Escape", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <ExplorerDialog onClose={onClose} title="Mínimo">
        Contenido
      </ExplorerDialog>,
    );
    const dialog = screen.getByRole("dialog", { name: "Mínimo" });
    expect(dialog).not.toHaveAttribute("aria-describedby");
    await user.keyboard("a");
    expect(onClose).not.toHaveBeenCalled();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
  });
});
