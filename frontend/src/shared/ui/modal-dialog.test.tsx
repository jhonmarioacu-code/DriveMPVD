import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { ModalDialog } from "@/shared/ui/modal-dialog";

function DialogHarness() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button onClick={() => setOpen(true)} type="button">
        Abrir diálogo
      </button>
      {open ? (
        <ModalDialog onClose={() => setOpen(false)} title="Confirmar cambio">
          <button type="button">Confirmar</button>
        </ModalDialog>
      ) : null}
    </>
  );
}

describe("ModalDialog", () => {
  it("atrapa el foco y lo devuelve al activador al cerrar", async () => {
    const user = userEvent.setup();
    render(<DialogHarness />);

    const opener = screen.getByRole("button", { name: "Abrir diálogo" });
    await user.click(opener);

    const closeButton = screen.getByRole("button", { name: "Cerrar" });
    const confirmButton = screen.getByRole("button", { name: "Confirmar" });
    expect(closeButton).toHaveFocus();

    await user.tab({ shift: true });
    expect(confirmButton).toHaveFocus();
    await user.tab();
    expect(closeButton).toHaveFocus();

    await user.click(closeButton);
    expect(opener).toHaveFocus();
  });
});
