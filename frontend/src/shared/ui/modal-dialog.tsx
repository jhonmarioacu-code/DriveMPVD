import { X } from "lucide-react";
import { useEffect, useRef, type PropsWithChildren, type ReactNode } from "react";

import { focusFirst, trapFocus } from "@/shared/ui/focus-trap";
import { cn } from "@/shared/utils/cn";

interface ModalDialogProps extends PropsWithChildren {
  title: string;
  description?: string;
  footer?: ReactNode;
  className?: string;
  bodyClassName?: string;
  onClose: () => void;
}

export function ModalDialog({
  bodyClassName,
  children,
  className,
  description,
  footer,
  onClose,
  title,
}: ModalDialogProps) {
  const dialogReference = useRef<HTMLElement>(null);
  const onCloseReference = useRef(onClose);

  useEffect(() => {
    onCloseReference.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const previouslyFocused =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCloseReference.current();
    };
    document.addEventListener("keydown", closeOnEscape);
    const dialog = dialogReference.current;
    focusFirst(dialog);

    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      if (previouslyFocused?.isConnected) previouslyFocused.focus();
    };
  }, []);

  return (
    <div
      className="fixed inset-0 z-60 grid place-items-center bg-overlay p-4"
      onMouseDown={(event) => {
        if (event.currentTarget === event.target) onClose();
      }}
      role="presentation"
    >
      <section
        aria-describedby={description === undefined ? undefined : "dialog-description"}
        aria-labelledby="dialog-title"
        aria-modal="true"
        className={cn(
          "w-full max-w-md rounded-2xl border border-border bg-surface shadow-2xl",
          className,
        )}
        onKeyDown={(event) => trapFocus(event, dialogReference.current)}
        ref={dialogReference}
        role="dialog"
        tabIndex={-1}
      >
        <header className="flex items-start gap-4 border-b border-border p-5">
          <div className="min-w-0 flex-1">
            <h2 className="font-bold" id="dialog-title">
              {title}
            </h2>
            {description === undefined ? null : (
              <p className="mt-1 text-xs leading-5 text-muted" id="dialog-description">
                {description}
              </p>
            )}
          </div>
          <button
            aria-label="Cerrar"
            className="icon-button -mt-1 -mr-1"
            onClick={onClose}
            type="button"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </header>
        <div className={cn("p-5", bodyClassName)}>{children}</div>
        {footer === undefined ? null : (
          <footer className="flex justify-end gap-2 border-t border-border p-4">
            {footer}
          </footer>
        )}
      </section>
    </div>
  );
}
