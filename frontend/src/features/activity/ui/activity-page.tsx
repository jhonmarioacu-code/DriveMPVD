import { Clock3, File, Folder, Heart, LoaderCircle, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  useActivityEntries,
  useRecordRecentOpen,
  useToggleFavorite,
} from "@/features/activity/model/activity-queries";
import {
  explorerErrorMessage,
  formatFileSize,
  formatModifiedDate,
  openFile,
} from "@/features/explorer/public";
import { Button } from "@/shared/ui/button";

import type { ActivityEntry, ActivityKind } from "@/features/activity/api/activity-api";

const pageCopy: Record<
  ActivityKind,
  { title: string; description: string; empty: string }
> = {
  favorites: {
    title: "Favoritos",
    description: "Conserva a mano los archivos y carpetas que más utilizas.",
    empty: "Aún no has marcado elementos como favoritos.",
  },
  recents: {
    title: "Recientes",
    description: "Retoma rápidamente los elementos que abriste hace poco.",
    empty: "Los elementos que abras aparecerán aquí.",
  },
};

function ActivityEntryRow({
  item,
  onOpen,
  onToggleFavorite,
  pending,
}: {
  item: ActivityEntry;
  onOpen: () => void;
  onToggleFavorite: () => void;
  pending: boolean;
}) {
  const { entry } = item;
  const favorite = entry.is_favorite ?? false;
  const Icon = entry.kind === "folder" ? Folder : File;
  const kindLabel = entry.kind === "folder" ? "Carpeta" : formatFileSize(entry.size);

  return (
    <article className="group flex min-w-0 items-center gap-3 rounded-2xl border border-border bg-surface p-3 shadow-[0_10px_30px_-28px_rgb(26_40_70_/_0.7)] transition-colors hover:border-border-strong sm:p-4">
      <button
        aria-label={`Abrir ${entry.name}`}
        className="flex min-w-0 flex-1 items-center gap-3 text-left outline-none focus-visible:ring-3 focus-visible:ring-brand/25"
        onClick={onOpen}
        type="button"
      >
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand">
          <Icon aria-hidden="true" className="size-5" />
        </span>
        <span className="min-w-0">
          <span className="block truncate text-sm font-bold">{entry.name}</span>
          <span className="mt-1 block truncate text-xs text-muted">
            {kindLabel} · {formatModifiedDate(item.occurred_at)}
          </span>
        </span>
      </button>
      <button
        aria-label={
          favorite
            ? `Quitar ${entry.name} de favoritos`
            : `Añadir ${entry.name} a favoritos`
        }
        aria-pressed={favorite}
        className="icon-button size-9 shrink-0"
        disabled={pending}
        onClick={onToggleFavorite}
        title={favorite ? "Quitar de favoritos" : "Añadir a favoritos"}
        type="button"
      >
        <Heart
          aria-hidden="true"
          className={favorite ? "size-4 fill-current text-brand" : "size-4"}
        />
      </button>
    </article>
  );
}

export function ActivityPage({ kind }: { kind: ActivityKind }) {
  const navigate = useNavigate();
  const page = useActivityEntries(kind);
  const toggleFavorite = useToggleFavorite();
  const recordRecentOpen = useRecordRecentOpen();
  const [actionError, setActionError] = useState<string | null>(null);
  const items = useMemo(
    () => page.data?.pages.flatMap((activityPage) => activityPage.items) ?? [],
    [page.data],
  );
  const copy = pageCopy[kind];

  const openEntry = (item: ActivityEntry) => {
    const { entry } = item;
    recordRecentOpen.mutate(entry.id, {
      onError: () => {
        setActionError("No fue posible actualizar Recientes. Inténtalo de nuevo.");
      },
    });
    if (entry.kind === "folder") {
      void navigate(`/files/${encodeURIComponent(entry.id)}`);
      return;
    }
    openFile(entry);
  };

  const changeFavorite = (item: ActivityEntry) => {
    const favorite = item.entry.is_favorite ?? false;
    setActionError(null);
    toggleFavorite.mutate(
      { entryId: item.entry.id, isFavorite: favorite },
      {
        onError: (error) => {
          setActionError(explorerErrorMessage(error));
        },
      },
    );
  };

  return (
    <div className="animate-enter">
      <div className="max-w-2xl">
        <p className="eyebrow">Biblioteca</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">
          {copy.title}
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted sm:text-base">
          {copy.description}
        </p>
      </div>

      <section aria-labelledby="activity-list-title" className="mt-8 max-w-4xl">
        <div className="mb-3 flex items-center gap-2">
          {kind === "favorites" ? (
            <Heart aria-hidden="true" className="size-4 text-brand" />
          ) : (
            <Clock3 aria-hidden="true" className="size-4 text-brand" />
          )}
          <h2 className="text-sm font-bold" id="activity-list-title">
            {kind === "favorites"
              ? "Elementos guardados"
              : "Últimos elementos abiertos"}
          </h2>
        </div>

        {actionError === null ? null : (
          <p className="auth-alert mb-3" role="alert">
            {actionError}
          </p>
        )}

        {page.isPending ? (
          <div
            className="grid min-h-48 place-items-center rounded-2xl border border-border bg-surface"
            role="status"
          >
            <div className="text-center">
              <LoaderCircle
                aria-hidden="true"
                className="mx-auto size-6 animate-spin text-brand"
              />
              <p className="mt-3 text-sm font-semibold">
                Cargando {copy.title.toLowerCase()}…
              </p>
            </div>
          </div>
        ) : page.isError ? (
          <div className="rounded-2xl border border-border bg-surface p-6 text-center">
            <p className="font-semibold">
              No se pudo cargar {copy.title.toLowerCase()}
            </p>
            <p className="mt-2 text-sm text-muted">
              {explorerErrorMessage(page.error)}
            </p>
            <Button
              className="mt-4"
              onClick={() => void page.refetch()}
              size="sm"
              variant="secondary"
            >
              <RefreshCw aria-hidden="true" className="size-4" />
              Reintentar
            </Button>
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border bg-surface-raised/45 p-8 text-center">
            <p className="font-semibold">{copy.empty}</p>
            <p className="mt-2 text-sm text-muted">
              Puedes seguir trabajando desde Mis archivos.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {items.map((item) => (
              <ActivityEntryRow
                item={item}
                key={`${item.entry.id}-${item.occurred_at}`}
                onOpen={() => openEntry(item)}
                onToggleFavorite={() => changeFavorite(item)}
                pending={
                  toggleFavorite.isPending &&
                  toggleFavorite.variables.entryId === item.entry.id
                }
              />
            ))}
          </div>
        )}

        {page.hasNextPage ? (
          <div className="mt-4 text-center">
            <Button
              disabled={page.isFetchingNextPage}
              onClick={() => void page.fetchNextPage()}
              variant="secondary"
            >
              {page.isFetchingNextPage ? "Cargando…" : "Cargar más"}
            </Button>
          </div>
        ) : null}
      </section>
    </div>
  );
}
