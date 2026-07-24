import {
  ArrowDownAZ,
  ArrowDownUp,
  ChevronRight,
  Download,
  Eye,
  ExternalLink,
  FolderPlus,
  Heart,
  LoaderCircle,
  MoreHorizontal,
  Move,
  Pencil,
  RefreshCw,
  Search,
  Trash2,
  Upload,
} from "lucide-react";
import { useDeferredValue, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useRecordRecentOpen, useToggleFavorite } from "@/features/activity";
import {
  useFolderEntries,
  useFolderNavigation,
} from "@/features/explorer/model/explorer-queries";
import {
  explorerErrorMessage,
  formatFileSize,
  formatModifiedDate,
} from "@/features/explorer/model/formatters";
import { downloadFile, openFile } from "@/features/explorer/model/file-actions";
import { useUploadsDispatch } from "@/features/uploads/model/uploads-context";
import { EntryThumbnail, FileViewerDialog, isPreviewable } from "@/features/viewers";
import {
  CreateFolderDialog,
  FileDetailsDialog,
  MoveEntriesDialog,
  RenameEntryDialog,
  TrashEntriesDialog,
} from "@/features/explorer/ui/explorer-dialogs";
import { EntryIcon } from "@/features/explorer/ui/entry-icon";
import { Button } from "@/shared/ui/button";
import { cn } from "@/shared/utils/cn";

import type {
  SortDirection,
  StorageEntry,
  StorageSortField,
} from "@/features/explorer/model/types";

type ActiveDialog = "create" | "rename" | "move" | "trash" | null;

function EntryRow({
  entry,
  onOpen,
  onSelect,
  onToggleFavorite,
  favoritePending,
  selected,
}: {
  entry: StorageEntry;
  onOpen: () => void;
  onSelect: () => void;
  onToggleFavorite: () => void;
  favoritePending: boolean;
  selected: boolean;
}) {
  const favorite = entry.is_favorite ?? false;
  return (
    <div
      aria-selected={selected}
      className={cn("explorer-row group", selected && "explorer-row-selected")}
      onDoubleClick={onOpen}
      onKeyDown={(event) => {
        if (event.target !== event.currentTarget) return;
        if (event.key === "Enter") onOpen();
        if (event.key === " ") {
          event.preventDefault();
          onSelect();
        }
      }}
      role="row"
      tabIndex={0}
    >
      <div className="flex items-center" role="gridcell">
        <input
          aria-label={`Seleccionar ${entry.name}`}
          checked={selected}
          className="size-4 rounded border-border text-brand accent-brand"
          onChange={onSelect}
          onClick={(event) => event.stopPropagation()}
          type="checkbox"
        />
      </div>
      <div role="gridcell">
        <button
          className="flex min-w-0 items-center gap-3 text-left"
          onClick={onOpen}
          type="button"
        >
          <span
            className={cn(
              "grid size-9 shrink-0 place-items-center rounded-xl",
              entry.kind === "folder"
                ? "bg-brand-soft text-brand"
                : "bg-surface-raised text-muted",
            )}
          >
            {entry.kind === "file" ? (
              <EntryThumbnail file={entry} />
            ) : (
              <EntryIcon entry={entry} />
            )}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold">{entry.name}</span>
            <span className="mt-0.5 block text-[0.68rem] text-muted md:hidden">
              {entry.kind === "folder" ? "Carpeta" : formatFileSize(entry.size)}
            </span>
          </span>
        </button>
      </div>
      <span className="hidden truncate text-xs text-muted md:block" role="gridcell">
        {entry.kind === "folder"
          ? "Carpeta"
          : (entry.extension?.toUpperCase() ?? "Archivo")}
      </span>
      <span className="hidden text-right text-xs text-muted md:block" role="gridcell">
        {formatFileSize(entry.size)}
      </span>
      <span className="hidden text-right text-xs text-muted lg:block" role="gridcell">
        {formatModifiedDate(entry.updated_at)}
      </span>
      <div className="flex justify-end" role="gridcell">
        <button
          aria-label={
            favorite
              ? `Quitar ${entry.name} de favoritos`
              : `Añadir ${entry.name} a favoritos`
          }
          aria-pressed={favorite}
          className={cn(
            "grid size-8 place-items-center rounded-lg text-muted hover:bg-surface-raised hover:text-foreground md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100",
            favorite && "text-brand opacity-100",
          )}
          disabled={favoritePending}
          onClick={(event) => {
            event.stopPropagation();
            onToggleFavorite();
          }}
          title={favorite ? "Quitar de favoritos" : "Añadir a favoritos"}
          type="button"
        >
          <Heart
            aria-hidden="true"
            className={favorite ? "size-4 fill-current" : "size-4"}
          />
        </button>
      </div>
      <div className="flex justify-end" role="gridcell">
        <button
          aria-label={`Abrir ${entry.name}`}
          className="grid size-8 place-items-center rounded-lg text-muted opacity-100 hover:bg-surface-raised hover:text-foreground md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100"
          onClick={onOpen}
          type="button"
        >
          {entry.kind === "folder" ? (
            <ChevronRight aria-hidden="true" className="size-4" />
          ) : (
            <MoreHorizontal aria-hidden="true" className="size-4" />
          )}
        </button>
      </div>
    </div>
  );
}

export function FileExplorerPage() {
  const { folderId } = useParams<{ folderId?: string }>();
  const navigate = useNavigate();
  const [sortBy, setSortBy] = useState<StorageSortField>("name");
  const [direction, setDirection] = useState<SortDirection>("asc");
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search.trim());
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [activeDialog, setActiveDialog] = useState<ActiveDialog>(null);
  const [detailsEntry, setDetailsEntry] = useState<StorageEntry | null>(null);
  const [previewEntry, setPreviewEntry] = useState<StorageEntry | null>(null);
  const [isDraggingFiles, setIsDraggingFiles] = useState(false);
  const [uploadNotice, setUploadNotice] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { enqueueFiles } = useUploadsDispatch();
  const toggleFavorite = useToggleFavorite();
  const recordRecentOpen = useRecordRecentOpen();
  const [activityNotice, setActivityNotice] = useState<string | null>(null);

  const navigation = useFolderNavigation(folderId);
  const currentFolderId = navigation.data?.folder.id;
  const listOptions = useMemo(
    () => ({ sortBy, direction, name: deferredSearch }),
    [deferredSearch, direction, sortBy],
  );
  const entriesQuery = useFolderEntries(currentFolderId, listOptions);
  const entries = useMemo(
    () => entriesQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [entriesQuery.data],
  );
  const selectedEntries = useMemo(
    () => entries.filter((entry) => selectedIds.has(entry.id)),
    [entries, selectedIds],
  );
  const singleSelection =
    selectedEntries.length === 1 ? (selectedEntries.at(0) ?? null) : null;
  const canPreviewSelection =
    singleSelection?.kind === "file" && isPreviewable(singleSelection);

  const clearSelection = () => setSelectedIds(new Set());
  const resetLocationState = () => {
    clearSelection();
    setSearch("");
    setActiveDialog(null);
    setDetailsEntry(null);
    setPreviewEntry(null);
  };

  const openEntry = (entry: StorageEntry) => {
    recordRecentOpen.mutate(entry.id, {
      onError: () => {
        setActivityNotice("No fue posible actualizar Recientes. Inténtalo de nuevo.");
      },
    });
    if (entry.kind === "folder") {
      resetLocationState();
      void navigate(`/files/${encodeURIComponent(entry.id)}`);
    } else {
      setDetailsEntry(entry);
    }
  };

  const changeFavorite = (entry: StorageEntry) => {
    setActivityNotice(null);
    toggleFavorite.mutate(
      { entryId: entry.id, isFavorite: entry.is_favorite ?? false },
      {
        onError: (error) => {
          setActivityNotice(explorerErrorMessage(error));
        },
      },
    );
  };

  const toggleSelection = (entryId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(entryId)) next.delete(entryId);
      else next.add(entryId);
      return next;
    });
  };

  const previewFile = (entry: StorageEntry, alreadyRecorded = false) => {
    if (entry.kind !== "file" || !isPreviewable(entry)) return;
    if (!alreadyRecorded) {
      recordRecentOpen.mutate(entry.id, {
        onError: () => {
          setActivityNotice("No fue posible actualizar Recientes. Inténtalo de nuevo.");
        },
      });
    }
    setDetailsEntry(null);
    setPreviewEntry(entry);
  };

  const allSelected =
    entries.length > 0 && entries.every((entry) => selectedIds.has(entry.id));
  const toggleAll = () => {
    setSelectedIds(allSelected ? new Set() : new Set(entries.map((entry) => entry.id)));
  };

  const completeAction = () => {
    setSelectedIds(new Set());
    setActiveDialog(null);
  };

  const queueFiles = (files: FileList | File[]) => {
    if (currentFolderId === undefined) {
      setUploadNotice("Esta carpeta aún no está lista para recibir archivos.");
      return;
    }
    if (files.length === 0) {
      setUploadNotice(
        "No se detectaron archivos. El servidor aún no admite subir carpetas completas.",
      );
      return;
    }
    enqueueFiles(files, currentFolderId);
    setUploadNotice(
      `${String(files.length)} archivo${files.length === 1 ? "" : "s"} añadido${files.length === 1 ? "" : "s"} a la cola.`,
    );
  };

  if (navigation.isPending) {
    return (
      <div className="grid min-h-[55vh] place-items-center" aria-live="polite">
        <div className="text-center">
          <LoaderCircle className="mx-auto size-7 animate-spin text-brand" />
          <p className="mt-3 text-sm font-semibold">Abriendo tus archivos…</p>
        </div>
      </div>
    );
  }

  if (navigation.isError) {
    return (
      <div className="grid min-h-[55vh] place-items-center text-center">
        <div className="max-w-sm">
          <p className="text-lg font-bold">No se pudo abrir esta ubicación</p>
          <p className="mt-2 text-sm leading-6 text-muted">
            {explorerErrorMessage(navigation.error)}
          </p>
          <Button
            className="mt-5"
            onClick={() => void navigation.refetch()}
            variant="secondary"
          >
            <RefreshCw aria-hidden="true" className="size-4" />
            Reintentar
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-enter">
      <nav aria-label="Ruta de carpetas" className="flex flex-wrap items-center gap-1">
        {navigation.data.breadcrumbs.map((item, index) => {
          const current = index === navigation.data.breadcrumbs.length - 1;
          return (
            <span className="flex items-center gap-1" key={item.id}>
              {index > 0 ? (
                <ChevronRight aria-hidden="true" className="size-3.5 text-muted" />
              ) : null}
              {current ? (
                <span aria-current="page" className="px-1.5 py-1 text-sm font-bold">
                  {item.name}
                </span>
              ) : (
                <Link
                  className="rounded-lg px-1.5 py-1 text-sm text-muted hover:bg-surface-raised hover:text-foreground"
                  onClick={resetLocationState}
                  to={index === 0 ? "/files" : `/files/${encodeURIComponent(item.id)}`}
                >
                  {item.name}
                </Link>
              )}
            </span>
          );
        })}
      </nav>

      <div className="mt-5 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="eyebrow">Explorador</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">
            {navigation.data.folder.name}
          </h1>
          <p className="mt-1 text-xs text-muted">
            {selectedEntries.length > 0
              ? `${String(selectedEntries.length)} seleccionado${selectedEntries.length === 1 ? "" : "s"}`
              : `${String(entries.length)} elemento${entries.length === 1 ? "" : "s"} visible${entries.length === 1 ? "" : "s"}`}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <input
            aria-label="Seleccionar archivos para subir"
            className="sr-only"
            multiple
            onChange={(event) => {
              queueFiles(event.target.files ?? []);
              event.target.value = "";
            }}
            ref={fileInputRef}
            type="file"
          />
          <Button
            disabled={currentFolderId === undefined}
            onClick={() => fileInputRef.current?.click()}
            size="sm"
            variant="secondary"
          >
            <Upload aria-hidden="true" className="size-4" />
            Subir archivos
          </Button>
          <Button onClick={() => setActiveDialog("create")} size="sm">
            <FolderPlus aria-hidden="true" className="size-4" />
            Nueva carpeta
          </Button>
          <Button
            disabled={singleSelection === null}
            onClick={() => singleSelection && openEntry(singleSelection)}
            size="sm"
            variant="secondary"
          >
            <ExternalLink aria-hidden="true" className="size-4" />
            Abrir
          </Button>
          <Button
            disabled={!canPreviewSelection}
            onClick={() => singleSelection && previewFile(singleSelection)}
            size="sm"
            variant="secondary"
          >
            <Eye aria-hidden="true" className="size-4" />
            Vista previa
          </Button>
          <Button
            disabled={singleSelection === null}
            onClick={() => setActiveDialog("rename")}
            size="sm"
            variant="secondary"
          >
            <Pencil aria-hidden="true" className="size-4" />
            Renombrar
          </Button>
          <Button
            disabled={selectedEntries.length === 0}
            onClick={() => setActiveDialog("move")}
            size="sm"
            variant="secondary"
          >
            <Move aria-hidden="true" className="size-4" />
            Mover
          </Button>
          <Button
            disabled={singleSelection?.kind !== "file"}
            onClick={() => singleSelection && downloadFile(singleSelection)}
            size="sm"
            variant="secondary"
          >
            <Download aria-hidden="true" className="size-4" />
            Descargar
          </Button>
          <Button
            disabled={selectedEntries.length === 0}
            onClick={() => setActiveDialog("trash")}
            size="sm"
            variant="ghost"
          >
            <Trash2 aria-hidden="true" className="size-4" />
            Papelera
          </Button>
        </div>
      </div>

      <section
        aria-describedby="upload-drop-help"
        aria-label="Subir archivos a esta carpeta"
        className={cn(
          "mt-6 rounded-2xl border border-dashed p-4 transition-colors",
          isDraggingFiles
            ? "border-brand bg-brand-soft/50"
            : "border-border bg-surface-raised/45",
        )}
        onDragEnter={(event) => {
          event.preventDefault();
          setIsDraggingFiles(true);
        }}
        onDragLeave={(event) => {
          if (event.currentTarget === event.target) setIsDraggingFiles(false);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          setIsDraggingFiles(false);
          queueFiles(event.dataTransfer.files);
        }}
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand">
              <Upload aria-hidden="true" className="size-5" />
            </span>
            <div>
              <p className="text-sm font-semibold">Arrastra archivos aquí</p>
              <p className="mt-1 text-xs leading-5 text-muted" id="upload-drop-help">
                Puedes seleccionar varios archivos. Las carpetas completas aún no están
                disponibles en la API.
              </p>
            </div>
          </div>
          <Button
            disabled={currentFolderId === undefined}
            onClick={() => fileInputRef.current?.click()}
            size="sm"
            variant="secondary"
          >
            Elegir archivos
          </Button>
        </div>
        {uploadNotice !== null ? (
          <p aria-live="polite" className="mt-3 text-xs text-muted" role="status">
            {uploadNotice}
          </p>
        ) : null}
      </section>

      <div className="mt-4 grid gap-3 rounded-2xl border border-border bg-surface p-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
        <label className="relative block min-w-0">
          <span className="sr-only">Filtrar esta carpeta</span>
          <Search
            aria-hidden="true"
            className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted"
          />
          <input
            aria-label="Filtrar esta carpeta"
            className="auth-input explorer-search-input"
            onChange={(event) => {
              clearSelection();
              setSearch(event.target.value);
            }}
            placeholder="Filtrar por nombre…"
            type="search"
            value={search}
          />
        </label>
        <div className="grid grid-cols-[minmax(0,1fr)_2.5rem] items-center gap-2 sm:flex">
          <div className="relative min-w-0 flex-1 sm:flex-none">
            <ArrowDownAZ
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted"
            />
            <label className="sr-only" htmlFor="explorer-sort">
              Ordenar por
            </label>
            <select
              className="h-10 w-full min-w-0 rounded-xl border border-border bg-surface py-0 pr-3 pl-9 text-sm outline-none focus:border-brand sm:w-36"
              id="explorer-sort"
              onChange={(event) => {
                clearSelection();
                setSortBy(event.target.value as StorageSortField);
              }}
              value={sortBy}
            >
              <option value="name">Nombre</option>
              <option value="date">Fecha</option>
              <option value="size">Tamaño</option>
              <option value="type">Tipo</option>
            </select>
          </div>
          <button
            aria-label={direction === "asc" ? "Orden ascendente" : "Orden descendente"}
            className="icon-button"
            onClick={() => {
              clearSelection();
              setDirection((value) => (value === "asc" ? "desc" : "asc"));
            }}
            type="button"
          >
            <ArrowDownUp aria-hidden="true" className="size-4" />
          </button>
        </div>
      </div>

      {activityNotice === null ? null : (
        <p className="auth-alert mt-3" role="alert">
          {activityNotice}
        </p>
      )}

      <section aria-label="Contenido de la carpeta" className="mt-4">
        <div aria-label="Archivos y carpetas" role="grid">
          <div role="rowgroup">
            <div className="explorer-grid-header" role="row">
              <div aria-label="Selección" role="columnheader">
                <input
                  aria-label="Seleccionar todos los elementos visibles"
                  checked={allSelected}
                  className="size-4 accent-brand"
                  onChange={toggleAll}
                  type="checkbox"
                />
              </div>
              <span role="columnheader">Nombre</span>
              <span className="hidden md:block" role="columnheader">
                Tipo
              </span>
              <span className="hidden text-right md:block" role="columnheader">
                Tamaño
              </span>
              <span className="hidden text-right lg:block" role="columnheader">
                Modificado
              </span>
              <span
                aria-label="Favoritos"
                className="justify-self-end"
                role="columnheader"
              >
                <Heart aria-hidden="true" className="size-4 text-muted" />
              </span>
              <span aria-label="Abrir" role="columnheader">
                <MoreHorizontal aria-hidden="true" className="size-4 text-muted" />
              </span>
            </div>
          </div>

          <div className="space-y-1" role="rowgroup">
            {entriesQuery.isPending ? (
              <div role="row">
                <div className="p-12 text-center text-sm text-muted" role="gridcell">
                  <div role="status">
                    <LoaderCircle className="mx-auto mb-3 size-6 animate-spin text-brand" />
                    Cargando contenido…
                  </div>
                </div>
              </div>
            ) : entriesQuery.isError ? (
              <div role="row">
                <div className="p-10 text-center" role="gridcell">
                  <p className="font-semibold">No se pudo cargar el contenido</p>
                  <p className="mt-2 text-sm text-muted">
                    {explorerErrorMessage(entriesQuery.error)}
                  </p>
                  <Button
                    className="mt-4"
                    onClick={() => void entriesQuery.refetch()}
                    size="sm"
                    variant="secondary"
                  >
                    <RefreshCw aria-hidden="true" className="size-4" />
                    Reintentar
                  </Button>
                </div>
              </div>
            ) : entries.length === 0 ? (
              <div role="row">
                <div className="p-12 text-center" role="gridcell">
                  <p className="font-semibold">
                    {deferredSearch === ""
                      ? "Esta carpeta está vacía"
                      : "Sin resultados"}
                  </p>
                  <p className="mt-2 text-sm text-muted">
                    {deferredSearch === ""
                      ? "Crea una carpeta para comenzar a organizar tus archivos."
                      : "Prueba con otro nombre dentro de esta carpeta."}
                  </p>
                </div>
              </div>
            ) : (
              entries.map((entry) => (
                <EntryRow
                  entry={entry}
                  key={entry.id}
                  onOpen={() => openEntry(entry)}
                  onSelect={() => toggleSelection(entry.id)}
                  onToggleFavorite={() => changeFavorite(entry)}
                  favoritePending={
                    toggleFavorite.isPending &&
                    toggleFavorite.variables.entryId === entry.id
                  }
                  selected={selectedIds.has(entry.id)}
                />
              ))
            )}
          </div>
        </div>

        {entriesQuery.hasNextPage ? (
          <div className="mt-4 text-center">
            <Button
              disabled={entriesQuery.isFetchingNextPage}
              onClick={() => void entriesQuery.fetchNextPage()}
              variant="secondary"
            >
              {entriesQuery.isFetchingNextPage ? "Cargando…" : "Cargar más"}
            </Button>
          </div>
        ) : null}
      </section>

      {activeDialog === "create" && currentFolderId !== undefined ? (
        <CreateFolderDialog
          folderId={currentFolderId}
          onClose={() => setActiveDialog(null)}
          onComplete={completeAction}
        />
      ) : null}
      {activeDialog === "rename" && singleSelection !== null ? (
        <RenameEntryDialog
          entry={singleSelection}
          onClose={() => setActiveDialog(null)}
          onComplete={completeAction}
        />
      ) : null}
      {activeDialog === "move" && selectedEntries.length > 0 ? (
        <MoveEntriesDialog
          entries={selectedEntries}
          onClose={() => setActiveDialog(null)}
          onComplete={completeAction}
        />
      ) : null}
      {activeDialog === "trash" && selectedEntries.length > 0 ? (
        <TrashEntriesDialog
          entries={selectedEntries}
          onClose={() => setActiveDialog(null)}
          onComplete={completeAction}
        />
      ) : null}
      {detailsEntry === null ? null : (
        <FileDetailsDialog
          canPreview={isPreviewable(detailsEntry)}
          entry={detailsEntry}
          onClose={() => setDetailsEntry(null)}
          onDownload={() => downloadFile(detailsEntry)}
          onOpen={() => openFile(detailsEntry)}
          onPreview={() => previewFile(detailsEntry, true)}
        />
      )}
      {previewEntry === null ? null : (
        <FileViewerDialog
          file={previewEntry}
          onClose={() => setPreviewEntry(null)}
          onDownload={() => downloadFile(previewEntry)}
          onOpenInNewTab={() => openFile(previewEntry, "inline")}
        />
      )}
    </div>
  );
}
