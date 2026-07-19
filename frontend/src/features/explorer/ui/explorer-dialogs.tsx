import { ChevronRight, Folder, LoaderCircle } from "lucide-react";
import { useId, useMemo, useState, type SyntheticEvent } from "react";

import {
  useCreateFolder,
  useFileDetails,
  useFolderEntries,
  useFolderNavigation,
  useMoveEntries,
  useRenameEntry,
  useTrashEntries,
} from "@/features/explorer/model/explorer-queries";
import {
  explorerErrorMessage,
  formatFileSize,
  formatModifiedDate,
} from "@/features/explorer/model/formatters";
import { ExplorerDialog } from "@/features/explorer/ui/explorer-dialog";
import { Button } from "@/shared/ui/button";

import type { StorageEntry } from "@/features/explorer/model/types";

interface BaseDialogProps {
  onClose: () => void;
  onComplete: () => void;
}

export function CreateFolderDialog({
  folderId,
  onClose,
  onComplete,
}: BaseDialogProps & { folderId: string }) {
  const formId = useId();
  const [name, setName] = useState("");
  const mutation = useCreateFolder();

  const submit = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    const normalized = name.trim();
    if (normalized === "") return;
    try {
      await mutation.mutateAsync({ parentId: folderId, name: normalized });
      onComplete();
    } catch {
      // The mutation state renders the stable public error.
    }
  };

  return (
    <ExplorerDialog
      description="La carpeta se creará dentro de la ubicación actual."
      footer={
        <>
          <Button onClick={onClose} type="button" variant="ghost">
            Cancelar
          </Button>
          <Button disabled={mutation.isPending || name.trim() === ""} form={formId}>
            {mutation.isPending ? "Creando…" : "Crear carpeta"}
          </Button>
        </>
      }
      onClose={onClose}
      title="Nueva carpeta"
    >
      <form id={formId} onSubmit={(event) => void submit(event)}>
        <label className="auth-label" htmlFor={`${formId}-name`}>
          Nombre
        </label>
        <input
          autoFocus
          className="auth-input"
          disabled={mutation.isPending}
          id={`${formId}-name`}
          maxLength={255}
          onChange={(event) => setName(event.target.value)}
          value={name}
        />
        {mutation.error === null ? null : (
          <p className="auth-alert mt-3" role="alert">
            {explorerErrorMessage(mutation.error)}
          </p>
        )}
      </form>
    </ExplorerDialog>
  );
}

export function RenameEntryDialog({
  entry,
  onClose,
  onComplete,
}: BaseDialogProps & { entry: StorageEntry }) {
  const formId = useId();
  const [name, setName] = useState(entry.name);
  const mutation = useRenameEntry();

  const submit = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    const normalized = name.trim();
    if (normalized === "" || normalized === entry.name) return;
    try {
      await mutation.mutateAsync({ entryId: entry.id, name: normalized });
      onComplete();
    } catch {
      // The mutation state renders the stable public error.
    }
  };

  return (
    <ExplorerDialog
      description={`Cambia el nombre de “${entry.name}”.`}
      footer={
        <>
          <Button onClick={onClose} type="button" variant="ghost">
            Cancelar
          </Button>
          <Button
            disabled={
              mutation.isPending || name.trim() === "" || name.trim() === entry.name
            }
            form={formId}
          >
            {mutation.isPending ? "Guardando…" : "Guardar"}
          </Button>
        </>
      }
      onClose={onClose}
      title="Renombrar"
    >
      <form id={formId} onSubmit={(event) => void submit(event)}>
        <label className="auth-label" htmlFor={`${formId}-name`}>
          Nombre
        </label>
        <input
          autoFocus
          className="auth-input"
          disabled={mutation.isPending}
          id={`${formId}-name`}
          maxLength={255}
          onChange={(event) => setName(event.target.value)}
          value={name}
        />
        {mutation.error === null ? null : (
          <p className="auth-alert mt-3" role="alert">
            {explorerErrorMessage(mutation.error)}
          </p>
        )}
      </form>
    </ExplorerDialog>
  );
}

export function TrashEntriesDialog({
  entries,
  onClose,
  onComplete,
}: BaseDialogProps & { entries: StorageEntry[] }) {
  const mutation = useTrashEntries();
  const remove = async () => {
    try {
      await mutation.mutateAsync(entries.map((entry) => entry.id));
      onComplete();
    } catch {
      // The mutation state renders the stable public error.
    }
  };

  return (
    <ExplorerDialog
      description={`${String(entries.length)} elemento${entries.length === 1 ? "" : "s"} se moverá${entries.length === 1 ? "" : "n"} a la papelera.`}
      footer={
        <>
          <Button onClick={onClose} type="button" variant="ghost">
            Cancelar
          </Button>
          <Button
            disabled={mutation.isPending}
            onClick={() => void remove()}
            type="button"
            variant="danger"
          >
            {mutation.isPending ? "Moviendo…" : "Mover a papelera"}
          </Button>
        </>
      }
      onClose={onClose}
      title="Eliminar elementos"
    >
      <ul className="max-h-40 space-y-1 overflow-auto text-sm">
        {entries.map((entry) => (
          <li
            className="truncate rounded-lg bg-surface-raised px-3 py-2"
            key={entry.id}
          >
            {entry.name}
          </li>
        ))}
      </ul>
      {mutation.error === null ? null : (
        <p className="auth-alert mt-3" role="alert">
          {explorerErrorMessage(mutation.error)}
        </p>
      )}
    </ExplorerDialog>
  );
}

export function MoveEntriesDialog({
  entries,
  onClose,
  onComplete,
}: BaseDialogProps & { entries: StorageEntry[] }) {
  const [folderId, setFolderId] = useState<string | undefined>();
  const navigation = useFolderNavigation(folderId);
  const options = useMemo(
    () => ({
      sortBy: "name" as const,
      direction: "asc" as const,
      name: "",
      kind: "folder" as const,
    }),
    [],
  );
  const currentId = navigation.data?.folder.id;
  const folders = useFolderEntries(currentId, options);
  const mutation = useMoveEntries();
  const blocked = new Set(entries.map((entry) => entry.id));

  const move = async () => {
    if (currentId === undefined || blocked.has(currentId)) return;
    try {
      await mutation.mutateAsync({
        entryIds: entries.map((entry) => entry.id),
        destinationFolderId: currentId,
      });
      onComplete();
    } catch {
      // The mutation state renders the stable public error.
    }
  };

  const folderItems = folders.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <ExplorerDialog
      description="Elige una carpeta de destino. No se permite mover una carpeta dentro de sí misma."
      footer={
        <>
          <Button onClick={onClose} type="button" variant="ghost">
            Cancelar
          </Button>
          <Button
            disabled={
              currentId === undefined || blocked.has(currentId) || mutation.isPending
            }
            onClick={() => void move()}
            type="button"
          >
            {mutation.isPending ? "Moviendo…" : "Mover aquí"}
          </Button>
        </>
      }
      onClose={onClose}
      title="Mover elementos"
    >
      {navigation.isPending ? (
        <LoaderCircle className="mx-auto size-6 animate-spin text-brand" />
      ) : navigation.isError ? (
        <p className="auth-alert" role="alert">
          {explorerErrorMessage(navigation.error)}
        </p>
      ) : (
        <>
          <nav aria-label="Destino" className="mb-3 flex flex-wrap items-center gap-1">
            {navigation.data.breadcrumbs.map((item, index) => (
              <span className="flex items-center gap-1" key={item.id}>
                {index > 0 ? (
                  <ChevronRight aria-hidden="true" className="size-3 text-muted" />
                ) : null}
                <button
                  className="rounded-md px-1.5 py-1 text-xs font-semibold hover:bg-surface-raised"
                  onClick={() => setFolderId(index === 0 ? undefined : item.id)}
                  type="button"
                >
                  {item.name}
                </button>
              </span>
            ))}
          </nav>
          <div className="max-h-64 space-y-1 overflow-auto rounded-xl border border-border p-2">
            {folders.isPending ? (
              <p className="p-4 text-center text-xs text-muted">Cargando carpetas…</p>
            ) : folderItems.length === 0 ? (
              <p className="p-4 text-center text-xs text-muted">No hay subcarpetas.</p>
            ) : (
              folderItems.map((folder) => (
                <button
                  className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm hover:bg-surface-raised"
                  key={folder.id}
                  onClick={() => setFolderId(folder.id)}
                  type="button"
                >
                  <Folder
                    aria-hidden="true"
                    className="size-4 fill-current text-brand"
                  />
                  <span className="truncate">{folder.name}</span>
                  <ChevronRight
                    aria-hidden="true"
                    className="ml-auto size-4 text-muted"
                  />
                </button>
              ))
            )}
            {folders.hasNextPage ? (
              <Button
                className="mt-2 w-full"
                onClick={() => void folders.fetchNextPage()}
                size="sm"
                type="button"
                variant="ghost"
              >
                Cargar más
              </Button>
            ) : null}
          </div>
          {mutation.error === null ? null : (
            <p className="auth-alert mt-3" role="alert">
              {explorerErrorMessage(mutation.error)}
            </p>
          )}
        </>
      )}
    </ExplorerDialog>
  );
}

export function FileDetailsDialog({
  canPreview,
  entry,
  onClose,
  onDownload,
  onOpen,
  onPreview,
}: {
  canPreview: boolean;
  entry: StorageEntry;
  onClose: () => void;
  onDownload: () => void;
  onOpen: () => void;
  onPreview: () => void;
}) {
  const details = useFileDetails(entry.id);
  return (
    <ExplorerDialog
      footer={
        <>
          <Button onClick={onDownload} type="button" variant="secondary">
            Descargar
          </Button>
          {canPreview ? (
            <Button onClick={onPreview} type="button" variant="secondary">
              Vista previa
            </Button>
          ) : null}
          <Button onClick={onOpen} type="button">
            Abrir
          </Button>
        </>
      }
      onClose={onClose}
      title={entry.name}
    >
      {details.isPending ? (
        <LoaderCircle className="mx-auto size-6 animate-spin text-brand" />
      ) : details.isError ? (
        <p className="auth-alert" role="alert">
          {explorerErrorMessage(details.error)}
        </p>
      ) : (
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 text-sm">
          <dt className="text-muted">Tipo</dt>
          <dd className="truncate text-right">{details.data.mime_type}</dd>
          <dt className="text-muted">Tamaño</dt>
          <dd className="text-right">{formatFileSize(details.data.size)}</dd>
          <dt className="text-muted">Modificado</dt>
          <dd className="text-right">{formatModifiedDate(details.data.updated_at)}</dd>
          <dt className="text-muted">Versión</dt>
          <dd className="text-right">{details.data.current_version_number}</dd>
        </dl>
      )}
    </ExplorerDialog>
  );
}
