import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  CheckCircle2,
  CloudOff,
  Database,
  FolderOpen,
  LoaderCircle,
  LockKeyhole,
  RefreshCw,
} from "lucide-react";

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
            El frontend funciona; inicia el backend para completar la comprobación.
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

const foundations = [
  {
    icon: LockKeyhole,
    title: "Privado por diseño",
    copy: "El cliente está preparado para credenciales HttpOnly y sesiones seguras.",
  },
  {
    icon: Database,
    title: "Contrato central",
    copy: "Todas las respuestas JSON se validan mediante el envelope de la API.",
  },
  {
    icon: FolderOpen,
    title: "Listo para crecer",
    copy: "La estructura por funcionalidades evita acoplar el explorador al shell.",
  },
] as const;

export function DashboardPage() {
  return (
    <div className="animate-enter">
      <div className="max-w-3xl">
        <p className="eyebrow">Fase 4 · Sesión protegida</p>
        <h1 className="mt-3 text-3xl leading-tight font-bold tracking-tight text-balance sm:text-4xl">
          Tu espacio personal, preparado para lo que sigue.
        </h1>
        <p className="mt-4 max-w-2xl text-sm leading-7 text-muted sm:text-base">
          La aplicación ya integra navegación, temas y accesibilidad. Tu sesión
          administradora utiliza cookies seguras, protección CSRF y renovación
          automática.
        </p>
      </div>

      <section aria-labelledby="connection-title" className="mt-8">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold" id="connection-title">
            Estado del sistema
          </h2>
          <span className="text-xs text-muted">Actualización automática</span>
        </div>
        <ApiStatus />
      </section>

      <section aria-labelledby="foundation-title" className="mt-10">
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <p className="eyebrow">Fundamentos</p>
            <h2 className="mt-1 text-xl font-bold" id="foundation-title">
              Una base pequeña y comprobable
            </h2>
          </div>
          <span className="hidden items-center gap-1 text-xs font-semibold text-brand sm:flex">
            Siguiente: explorador
            <ArrowRight aria-hidden="true" className="size-3.5" />
          </span>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {foundations.map(({ copy, icon: Icon, title }) => (
            <article className="foundation-card" key={title}>
              <span className="grid size-9 place-items-center rounded-xl bg-brand-soft text-brand">
                <Icon aria-hidden="true" className="size-4.5" />
              </span>
              <h3 className="mt-5 text-sm font-bold">{title}</h3>
              <p className="mt-2 text-xs leading-5 text-muted">{copy}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
