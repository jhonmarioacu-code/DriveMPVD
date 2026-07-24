import type { KeyboardEvent as ReactKeyboardEvent } from "react";

const focusableSelector = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type=hidden])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export function focusableElements(container: HTMLElement) {
  return Array.from(container.querySelectorAll<HTMLElement>(focusableSelector)).filter(
    (element) => element.getAttribute("aria-hidden") !== "true",
  );
}

export function focusFirst(container: HTMLElement | null) {
  if (container === null) return;
  const [firstFocusable] = focusableElements(container);
  (firstFocusable ?? container).focus();
}

export function trapFocus(
  event: ReactKeyboardEvent<HTMLElement>,
  container: HTMLElement | null,
) {
  if (event.key !== "Tab" || container === null) return;
  const elements = focusableElements(container);
  if (elements.length === 0) {
    event.preventDefault();
    container.focus();
    return;
  }
  const first = elements.at(0);
  const last = elements.at(-1);
  if (first === undefined || last === undefined) return;
  const activeElement = document.activeElement;
  if (
    event.shiftKey &&
    (activeElement === first || !container.contains(activeElement))
  ) {
    event.preventDefault();
    last.focus();
  } else if (
    !event.shiftKey &&
    (activeElement === last || !container.contains(activeElement))
  ) {
    event.preventDefault();
    first.focus();
  }
}
