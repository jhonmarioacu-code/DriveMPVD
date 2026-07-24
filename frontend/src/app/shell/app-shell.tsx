import {
  Clock3,
  Files,
  FolderHeart,
  HardDrive,
  Home,
  Menu,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { SessionControls } from "@/features/auth/ui/session-controls";
import { UploadTray } from "@/features/uploads";
import { focusFirst, trapFocus } from "@/shared/ui/focus-trap";
import { ThemeSwitcher } from "@/shared/ui/theme-switcher";
import { cn } from "@/shared/utils/cn";

const navigation = [
  { label: "Inicio", icon: Home, href: "/home", available: true },
  { label: "Mis archivos", icon: Files, href: "/files", available: true },
  { label: "Recientes", icon: Clock3, href: "/recents", available: true },
  { label: "Favoritos", icon: FolderHeart, href: "/favorites", available: true },
  { label: "Papelera", icon: Trash2, href: "", available: false },
] as const;

interface SidebarProps {
  mobile?: boolean;
  onNavigate?: () => void;
}

function Sidebar({ mobile = false, onNavigate }: SidebarProps) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-18 items-center gap-3 px-5">
        <span className="grid size-10 place-items-center rounded-2xl bg-brand text-white shadow-brand">
          <HardDrive aria-hidden="true" className="size-5" strokeWidth={2.2} />
        </span>
        <div>
          <p className="text-base font-bold tracking-tight">DriveMPVD</p>
          <p className="text-xs text-muted">Tu espacio privado</p>
        </div>
      </div>

      <nav aria-label="Navegación principal" className="mt-5 flex-1 px-3">
        <p className="mb-2 px-3 text-[0.68rem] font-bold tracking-[0.16em] text-muted uppercase">
          Biblioteca
        </p>
        <ul className="space-y-1">
          {navigation.map(({ label, icon: Icon, href, available }) => (
            <li key={label}>
              {available ? (
                <NavLink
                  className={({ isActive }) =>
                    cn("nav-item", isActive && "nav-item-active")
                  }
                  onClick={onNavigate}
                  to={href}
                >
                  <Icon aria-hidden="true" className="size-4.5" />
                  <span>{label}</span>
                </NavLink>
              ) : (
                <span
                  aria-disabled="true"
                  className="nav-item cursor-not-allowed opacity-55"
                  title="Disponible en un próximo incremento"
                >
                  <Icon aria-hidden="true" className="size-4.5" />
                  <span>{label}</span>
                  <span className="ml-auto size-1.5 rounded-full bg-border-strong" />
                </span>
              )}
            </li>
          ))}
        </ul>
      </nav>

      <div className="m-4 rounded-2xl border border-border bg-surface-raised p-4">
        <p className="text-xs font-semibold text-foreground">Sesión protegida</p>
        <p className="mt-1 text-xs leading-relaxed text-muted">
          El explorador usa tu sesión segura y mantiene la navegación en caché.
        </p>
      </div>
      {mobile ? <div className="h-2" /> : null}
    </div>
  );
}

export function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const mobileSidebarReference = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!sidebarOpen) return;

    const previouslyFocused =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSidebarOpen(false);
    };
    document.addEventListener("keydown", closeOnEscape);
    focusFirst(mobileSidebarReference.current);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      if (previouslyFocused?.isConnected) previouslyFocused.focus();
    };
  }, [sidebarOpen]);

  return (
    <div className="min-h-screen bg-canvas text-foreground">
      <div aria-hidden={sidebarOpen} inert={sidebarOpen}>
        <a className="skip-link" href="#main-content">
          Saltar al contenido
        </a>

        <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 border-r border-border bg-surface lg:block">
          <Sidebar />
        </aside>

        <div className="lg:pl-64">
          <header className="sticky top-0 z-30 border-b border-border/80 bg-canvas/90 backdrop-blur-xl">
            <div className="flex h-18 items-center gap-3 px-4 sm:px-6 lg:px-8">
              <button
                aria-expanded={sidebarOpen}
                aria-label="Abrir menú"
                className="icon-button lg:hidden"
                onClick={() => setSidebarOpen(true)}
                type="button"
              >
                <Menu aria-hidden="true" className="size-5" />
              </button>

              <div className="hidden flex-1 items-center gap-2 text-sm text-muted sm:flex">
                <Search aria-hidden="true" className="size-4" />
                <span>Busca y ordena dentro de cada carpeta</span>
              </div>

              <div className="ml-auto flex items-center gap-2">
                <ThemeSwitcher />
                <span aria-hidden="true" className="mx-1 h-6 w-px bg-border" />
                <SessionControls />
              </div>
            </div>
          </header>

          <main
            className="mx-auto max-w-7xl px-4 py-8 pb-40 sm:px-6 lg:px-8"
            id="main-content"
          >
            <Outlet />
          </main>
        </div>
        <UploadTray />
      </div>

      <div
        aria-hidden="true"
        className={cn(
          "fixed inset-0 z-40 bg-overlay transition-opacity lg:hidden",
          sidebarOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={() => setSidebarOpen(false)}
      />
      <aside
        aria-hidden={!sidebarOpen}
        aria-label="Navegación móvil"
        aria-modal="true"
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-[min(20rem,88vw)] border-r border-border bg-surface shadow-2xl transition-transform duration-200 lg:hidden",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        )}
        inert={!sidebarOpen}
        onKeyDown={(event) => trapFocus(event, mobileSidebarReference.current)}
        ref={mobileSidebarReference}
        role="dialog"
        tabIndex={-1}
      >
        <button
          aria-label="Cerrar menú"
          className="icon-button absolute top-4 right-4"
          onClick={() => setSidebarOpen(false)}
          type="button"
        >
          <X aria-hidden="true" className="size-5" />
        </button>
        <Sidebar mobile onNavigate={() => setSidebarOpen(false)} />
      </aside>
    </div>
  );
}
