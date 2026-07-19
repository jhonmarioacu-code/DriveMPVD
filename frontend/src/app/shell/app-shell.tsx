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
import { useEffect, useState } from "react";
import { Link, Outlet } from "react-router-dom";

import { ThemeSwitcher } from "@/shared/ui/theme-switcher";
import { cn } from "@/shared/utils/cn";

const navigation = [
  { label: "Inicio", icon: Home, available: true },
  { label: "Mis archivos", icon: Files, available: false },
  { label: "Recientes", icon: Clock3, available: false },
  { label: "Favoritos", icon: FolderHeart, available: false },
  { label: "Papelera", icon: Trash2, available: false },
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
          {navigation.map(({ label, icon: Icon, available }) => (
            <li key={label}>
              {available ? (
                <Link className="nav-item nav-item-active" onClick={onNavigate} to="/">
                  <Icon aria-hidden="true" className="size-4.5" />
                  <span>{label}</span>
                </Link>
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
        <p className="text-xs font-semibold text-foreground">Frontend base</p>
        <p className="mt-1 text-xs leading-relaxed text-muted">
          El explorador se habilitará en su incremento correspondiente.
        </p>
      </div>
      {mobile ? <div className="h-2" /> : null}
    </div>
  );
}

export function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!sidebarOpen) return;

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSidebarOpen(false);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [sidebarOpen]);

  return (
    <div className="min-h-screen bg-canvas text-foreground">
      <a className="skip-link" href="#main-content">
        Saltar al contenido
      </a>

      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 border-r border-border bg-surface lg:block">
        <Sidebar />
      </aside>

      <div
        aria-hidden={!sidebarOpen}
        className={cn(
          "fixed inset-0 z-40 bg-overlay transition-opacity lg:hidden",
          sidebarOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={() => setSidebarOpen(false)}
      />
      <aside
        aria-hidden={!sidebarOpen}
        aria-label="Navegación móvil"
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-[min(20rem,88vw)] border-r border-border bg-surface shadow-2xl transition-transform duration-200 lg:hidden",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        )}
        inert={!sidebarOpen}
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

            <div className="relative hidden max-w-md flex-1 sm:block">
              <Search
                aria-hidden="true"
                className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted"
              />
              <input
                aria-label="Buscar"
                className="h-10 w-full rounded-xl border border-border bg-surface px-9 text-sm outline-none placeholder:text-muted focus:border-brand focus:ring-3 focus:ring-brand/12"
                disabled
                placeholder="Buscar próximamente…"
                type="search"
              />
            </div>

            <div className="ml-auto flex items-center gap-2">
              <span className="hidden text-xs text-muted md:inline">
                Acceso local y privado
              </span>
              <ThemeSwitcher />
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8" id="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
