import { LoaderCircle } from "lucide-react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "@/features/auth/model/auth-context";

function SessionLoader() {
  return (
    <div
      aria-live="polite"
      className="grid min-h-screen place-items-center bg-canvas text-foreground"
    >
      <div className="text-center">
        <LoaderCircle
          aria-hidden="true"
          className="mx-auto size-7 animate-spin text-brand"
        />
        <p className="mt-4 text-sm font-semibold">Comprobando sesión…</p>
      </div>
    </div>
  );
}

export function RequireAuth() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") return <SessionLoader />;
  if (status === "unauthenticated") {
    return (
      <Navigate
        replace
        state={{ from: `${location.pathname}${location.search}${location.hash}` }}
        to="/login"
      />
    );
  }
  return <Outlet />;
}

export function PublicOnlyRoute() {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <SessionLoader />;
  if (status === "authenticated") {
    const candidate = (location.state as { from?: unknown } | null)?.from;
    const destination =
      typeof candidate === "string" &&
      candidate.startsWith("/") &&
      !candidate.startsWith("//")
        ? candidate
        : "/";
    return <Navigate replace to={destination} />;
  }
  return <Outlet />;
}
