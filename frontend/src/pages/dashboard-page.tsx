import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  CloudOff,
  FilePlus2,
  Files,
  FolderHeart,
  FolderOpen,
  HardDrive,
  Heart,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useActivityEntries, useRecordRecentOpen } from "@/features/activity";
import { formatModifiedDate, openFile } from "@/features/explorer/public";
import { ApiClientError } from "@/shared/api/client";
import { getHealth } from "@/shared/api/system";
import { Button } from "@/shared/ui/button";

function ApiStatus() {
  const healthQuery = useQuery({
    queryKey: ["system", "health"],
    queryFn: ({ signal }) => getHealth(signal),
  });

  if (healthQuery.isPending) {
    return (
      <div aria-live="polite" className="status-panel">
        <LoaderCircle aria-hidden="true" className="size-5 animate-spin text-brand" />
        <div>
          <p className="status-title">Comprobando conexión</p>
          <p className="status-copy">Consultando el servicio local…</p>
        </div>
      </div>
    );
  }

  if (healthQuery.isError) {
    const requestId =
      healthQuery.error instanceof ApiClientError ? healthQuery.error.requestId : null;
    return (
      <div aria-live="polite" className="status-panel">
        <CloudOff aria-hidden="true" className="size-5 text-warning" />
        <div className="min-w-0 flex-1">
          <p className="status-title">API sin conexión</p>
          <p className="status-copy">
            El frontend sigue disponible; vuelve a intentar cuando el servicio responda.
          </p>
          {requestId === null ? null : (
            <p className="mt-1 truncate font-mono text-[0.65rem] text-muted">
              Solicitud: {requestId}
            </p>
          )}
        </div>
        <Button
          aria-label="Reintentar conexión"
          onClick={() => void healthQuery.refetch()}
          size="icon"
          type="button"
          variant="secondary"
        >
          <RefreshCw aria-hidden="true" className="size-4" />
        </Button>
      </div>
    );
  }

  return (
    <div aria-live="polite" className="status-panel">
      <CheckCircle2 aria-hidden="true" className="size-5 text-success" />
      <div className="min-w-0">
        <p className="status-title">API disponible</p>
        <p className="status-copy">
          {healthQuery.data.service} · versión {healthQuery.data.version}
        </p>
      </div>
      <span className="ml-auto rounded-full bg-success-soft px-2.5 py-1 text-[0.68rem] font-bold tracking-wide text-success uppercase">
        {healthQuery.data.status}
      </span>
    </div>
  );
}

const shortcuts = [
  {
    to: "/files",
    icon: FolderOpen,
    title: "Mis archivos",
    copy: "Explora, organiza y comparte tu espacio.",
    tone: "bg-brand-soft text-brand",
  },
  {
    to: "/recents",
    icon: Clock3,
    title: "Recientes",
    copy: "Vuelve a lo que estabas haciendo.",
    tone: "bg-success-soft text-success",
  },
  {
    to: "/favorites",
    icon: FolderHeart,
    title: "Favoritos",
    copy: "Mantén a la vista lo más importante.",
    tone: "bg-surface-raised text-foreground",
  },
] as const;

function RecentPreview() {
  const navigate = useNavigate();
  const recentQuery = useActivityEntries("recents", 3);
  const recordRecentOpen = useRecordRecentOpen();
  const [actionError, setActionError] = useState<string | null>(null);
  const items = useMemo(
    () => recentQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [recentQuery.data],
  );

  const openRecentEntry = (item: (typeof items)[number]) => {
    setActionError(null);
    recordRecentOpen.mutate(item.entry.id, {
      onError: () => {
        setActionError("No fue posible actualizar Recientes. Inténtalo de nuevo.");
      },
    });
    if (item.entry.kind === "folder") {
      void navigate(`/files/${encodeURIComponent(item.entry.id)}`);
      return;
    }
    openFile(item.entry);
  };

  return (
    <section
      aria-labelledby="recent-preview-title"
      className="rounded-3xl border border-border bg-surface p-5 shadow-[0_18px_45px_-38px_rgb(35_55_100_/_0.72)]"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Continúa donde lo dejaste</p>
          <h2 className="mt-1 text-lg font-bold" id="recent-preview-title">
            Recientes
          </h2>
        </div>
        <Link
          aria-label="Ver todos los elementos recientes"
          className="icon-button size-9"
          to="/recents"
        >
          <ArrowUpRight aria-hidden="true" className="size-4" />
        </Link>
      </div>

      {recentQuery.isPending ? (
        <div className="mt-5 flex items-center gap-2 text-sm text-muted" role="status">
          <LoaderCircle aria-hidden="true" className="size-4 animate-spin text-brand" />
          Cargando actividad…
        </div>
      ) : recentQuery.isError ? (
        <p className="mt-5 text-sm leading-6 text-muted">
          No se pudieron cargar los elementos recientes ahora mismo.
        </p>
      ) : items.length === 0 ? (
        <div className="mt-5 rounded-2xl bg-surface-raised p-4 text-sm leading-6 text-muted">
          Abre un archivo o una carpeta y aparecerá aquí para volver rápidamente.
        </div>
      ) : (
        <>
          <ul className="mt-4 space-y-1">
            {items.map((item) => (
              <li key={`${item.entry.id}-${item.occurred_at}`}>
                <button
                  aria-label={`Abrir ${item.entry.name}`}
                  className="flex w-full min-w-0 items-center gap-3 rounded-xl px-2 py-2 text-left transition-colors hover:bg-surface-raised focus-visible:outline-3 focus-visible:outline-brand/25"
                  onClick={() => openRecentEntry(item)}
                  type="button"
                >
                  <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-brand-soft text-brand">
                    {item.entry.kind === "folder" ? (
                      <FolderOpen aria-hidden="true" className="size-4" />
                    ) : (
                      <Files aria-hidden="true" className="size-4" />
                    )}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold">
                      {item.entry.name}
                    </span>
                    <span className="block truncate text-xs text-muted">
                      {formatModifiedDate(item.occurred_at)}
                    </span>
                  </span>
                  <ArrowRight
                    aria-hidden="true"
                    className="size-4 shrink-0 text-muted"
                  />
                </button>
              </li>
            ))}
          </ul>
          {actionError === null ? null : (
            <p className="auth-alert mt-3" role="alert">
              {actionError}
            </p>
          )}
        </>
      )}
    </section>
  );
}

export function DashboardPage() {
  return (
    <div className="animate-enter space-y-8">
      <section className="relative overflow-hidden rounded-3xl border border-brand/20 bg-surface px-5 py-7 shadow-[0_24px_60px_-46px_rgb(35_55_100_/_0.8)] sm:px-8 sm:py-9">
        <div
          aria-hidden="true"
          className="absolute -top-28 -right-20 size-72 rounded-full bg-brand-soft/70 blur-3xl"
        />
        <div
          aria-hidden="true"
          className="absolute -bottom-36 left-1/3 size-64 rounded-full bg-success-soft/70 blur-3xl"
        />
        <div className="relative grid gap-8 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-end">
          <div className="max-w-2xl">
            <p className="eyebrow">Espacio de trabajo privado</p>
            <h1 className="mt-3 text-3xl leading-tight font-bold tracking-tight text-balance sm:text-4xl">
              Todo tu espacio, más cerca.
            </h1>
            <p className="mt-4 max-w-xl text-sm leading-7 text-muted sm:text-base">
              Organiza tus archivos, retoma lo reciente y fija lo importante sin perder
              el contexto de tu trabajo.
            </p>
            <div className="mt-6 flex flex-col gap-2 sm:flex-row">
              <Button asChild>
                <Link to="/files">
                  <FolderOpen aria-hidden="true" className="size-4" />
                  Abrir mis archivos
                </Link>
              </Button>
              <Button asChild variant="secondary">
                <Link to="/favorites">
                  <Heart aria-hidden="true" className="size-4" />
                  Ver favoritos
                </Link>
              </Button>
            </div>
          </div>

          <div className="rounded-2xl bg-brand p-5 text-white shadow-brand">
            <HardDrive aria-hidden="true" className="size-6" />
            <p className="mt-5 text-sm font-bold">Tu biblioteca está lista</p>
            <p className="mt-2 text-xs leading-5 text-white/80">
              Los accesos directos mantienen tus archivos, favoritos y actividad al
              alcance de un clic.
            </p>
          </div>
        </div>
      </section>

      <section aria-labelledby="shortcuts-title">
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <p className="eyebrow">Accesos rápidos</p>
            <h2 className="mt-1 text-xl font-bold" id="shortcuts-title">
              Empieza por donde lo necesites
            </h2>
          </div>
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          {shortcuts.map(({ copy, icon: Icon, title, to, tone }) => (
            <Link
              className="group rounded-2xl border border-border bg-surface p-5 shadow-[0_14px_36px_-32px_rgb(35_55_100_/_0.72)] transition hover:-translate-y-0.5 hover:border-border-strong hover:shadow-[0_18px_45px_-34px_rgb(35_55_100_/_0.8)] focus-visible:outline-3 focus-visible:outline-brand/25"
              key={to}
              to={to}
            >
              <span className={`grid size-10 place-items-center rounded-xl ${tone}`}>
                <Icon aria-hidden="true" className="size-5" />
              </span>
              <span className="mt-5 flex items-center justify-between gap-3">
                <span className="text-sm font-bold">{title}</span>
                <ArrowRight
                  aria-hidden="true"
                  className="size-4 text-muted transition-transform group-hover:translate-x-0.5"
                />
              </span>
              <span className="mt-2 block text-xs leading-5 text-muted">{copy}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(18rem,0.75fr)]">
        <RecentPreview />
        <div className="space-y-5">
          <section aria-labelledby="connection-title">
            <div className="mb-3 flex items-center gap-2">
              <ShieldCheck aria-hidden="true" className="size-4 text-brand" />
              <h2 className="text-sm font-bold" id="connection-title">
                Estado del sistema
              </h2>
            </div>
            <ApiStatus />
          </section>

          <section className="rounded-3xl border border-border bg-surface-raised/55 p-5">
            <FilePlus2 aria-hidden="true" className="size-5 text-brand" />
            <h2 className="mt-4 text-sm font-bold">Organiza sin fricción</h2>
            <p className="mt-2 text-xs leading-5 text-muted">
              Crea carpetas, mueve elementos y usa Favoritos para mantener tus recursos
              más importantes en un lugar predecible.
            </p>
          </section>
        </div>
      </section>
    </div>
  );
}
