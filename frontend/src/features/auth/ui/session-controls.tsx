import { LoaderCircle, LogOut } from "lucide-react";
import { useState } from "react";

import { useAuth } from "@/features/auth/model/auth-context";

function initials(username: string) {
  return username.slice(0, 2).toLocaleUpperCase("es");
}

export function SessionControls() {
  const { logout, user } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (user === null) return null;

  const handleLogout = async () => {
    setLoggingOut(true);
    setError(null);
    try {
      await logout();
    } catch {
      setError("No se pudo cerrar la sesión. Inténtalo de nuevo.");
      setLoggingOut(false);
    }
  };

  return (
    <div className="relative flex items-center gap-2">
      <div className="hidden text-right md:block">
        <p className="max-w-36 truncate text-xs font-semibold">{user.username}</p>
        <p className="text-[0.65rem] text-muted">Administrador</p>
      </div>
      <span
        aria-hidden="true"
        className="grid size-9 place-items-center rounded-xl bg-brand-soft text-xs font-bold text-brand"
      >
        {initials(user.username)}
      </span>
      <button
        aria-label="Cerrar sesión"
        className="icon-button"
        disabled={loggingOut}
        onClick={() => void handleLogout()}
        title="Cerrar sesión"
        type="button"
      >
        {loggingOut ? (
          <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
        ) : (
          <LogOut aria-hidden="true" className="size-4" />
        )}
      </button>
      {error === null ? null : (
        <p
          className="absolute top-12 right-0 z-40 w-64 rounded-xl border border-danger/30 bg-surface p-3 text-xs text-danger shadow-lg"
          role="alert"
        >
          {error}
        </p>
      )}
    </div>
  );
}
