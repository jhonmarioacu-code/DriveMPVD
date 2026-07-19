import { Eye, EyeOff, HardDrive, LockKeyhole, ShieldCheck } from "lucide-react";
import { useState, type SyntheticEvent } from "react";

import { useAuth } from "@/features/auth/model/auth-context";
import { ApiClientError } from "@/shared/api/client";
import { Button } from "@/shared/ui/button";
import { ThemeSwitcher } from "@/shared/ui/theme-switcher";

function loginErrorMessage(error: unknown) {
  if (!(error instanceof ApiClientError)) {
    return "No fue posible conectar con el servidor. Inténtalo de nuevo.";
  }
  if (error.code === "auth.invalid_credentials") {
    return "El usuario o la contraseña no son correctos.";
  }
  if (
    error.code === "auth.rate_limit_exceeded" ||
    error.code === "auth.account_temporarily_locked"
  ) {
    const wait =
      error.retryAfterSeconds === null
        ? "Inténtalo más tarde."
        : `Espera ${String(error.retryAfterSeconds)} segundos.`;
    return `Se alcanzó el límite de intentos. ${wait}`;
  }
  if (error.code === "auth.account_disabled") {
    return "La cuenta administradora está deshabilitada.";
  }
  if (error.status === 401) {
    return "La sesión no pudo establecerse. Verifica la configuración de cookies seguras.";
  }
  return "No fue posible iniciar sesión. Inténtalo de nuevo.";
}

export function LoginPage() {
  const { initializationError, login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    const normalizedUsername = username.trim();
    if (normalizedUsername === "" || password === "") {
      setError("Escribe tu usuario y contraseña.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await login({ username: normalizedUsername, password });
      setPassword("");
    } catch (loginError: unknown) {
      setPassword("");
      setError(loginErrorMessage(loginError));
      setSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      <div className="absolute top-5 right-5 z-10">
        <ThemeSwitcher />
      </div>

      <aside className="login-visual" aria-label="Información de seguridad">
        <div className="relative z-10 max-w-md">
          <span className="grid size-12 place-items-center rounded-2xl bg-white/12 text-white ring-1 ring-white/20">
            <HardDrive aria-hidden="true" className="size-6" />
          </span>
          <p className="mt-10 text-xs font-bold tracking-[0.18em] text-blue-200 uppercase">
            DriveMPVD
          </p>
          <h1 className="mt-3 text-4xl leading-tight font-bold tracking-tight text-white">
            Tus archivos permanecen bajo tu control.
          </h1>
          <p className="mt-5 text-sm leading-7 text-blue-100/80">
            Acceso privado para una única cuenta administradora. La sesión utiliza
            cookies seguras y renovación rotatoria.
          </p>
          <div className="mt-10 flex items-center gap-3 text-sm text-blue-100">
            <ShieldCheck aria-hidden="true" className="size-5" />
            <span>Protección CSRF y credenciales HttpOnly</span>
          </div>
        </div>
      </aside>

      <main className="grid min-h-screen place-items-center px-5 py-20 sm:px-10">
        <div className="w-full max-w-sm animate-enter">
          <div className="mb-8 lg:hidden">
            <span className="grid size-11 place-items-center rounded-2xl bg-brand text-white shadow-brand">
              <HardDrive aria-hidden="true" className="size-5" />
            </span>
          </div>
          <p className="eyebrow">Área privada</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight">Inicia sesión</h2>
          <p className="mt-3 text-sm leading-6 text-muted">
            Usa las credenciales de la cuenta administradora configurada en el servidor.
          </p>

          {initializationError === null ? null : (
            <div className="auth-alert mt-6" role="status">
              {initializationError}
            </div>
          )}

          <form
            className="mt-7 space-y-5"
            noValidate
            onSubmit={(event) => void handleSubmit(event)}
          >
            <div>
              <label className="auth-label" htmlFor="username">
                Usuario
              </label>
              <input
                autoCapitalize="none"
                autoComplete="username"
                autoFocus
                className="auth-input"
                disabled={submitting}
                id="username"
                maxLength={100}
                onChange={(event) => setUsername(event.target.value)}
                required
                spellCheck={false}
                type="text"
                value={username}
              />
            </div>

            <div>
              <label className="auth-label" htmlFor="password">
                Contraseña
              </label>
              <div className="relative">
                <input
                  autoComplete="current-password"
                  className="auth-input pr-11"
                  disabled={submitting}
                  id="password"
                  maxLength={1024}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  type={showPassword ? "text" : "password"}
                  value={password}
                />
                <button
                  aria-label={
                    showPassword ? "Ocultar contraseña" : "Mostrar contraseña"
                  }
                  className="absolute top-1/2 right-2 grid size-8 -translate-y-1/2 place-items-center rounded-lg text-muted hover:bg-surface-raised hover:text-foreground focus-visible:outline-3 focus-visible:outline-brand/25"
                  disabled={submitting}
                  onClick={() => setShowPassword((visible) => !visible)}
                  type="button"
                >
                  {showPassword ? (
                    <EyeOff aria-hidden="true" className="size-4" />
                  ) : (
                    <Eye aria-hidden="true" className="size-4" />
                  )}
                </button>
              </div>
            </div>

            {error === null ? null : (
              <div className="auth-alert" role="alert">
                {error}
              </div>
            )}

            <Button className="w-full" disabled={submitting} type="submit">
              {submitting ? (
                <>
                  <span
                    aria-hidden="true"
                    className="size-4 animate-spin rounded-full border-2 border-white/35 border-t-white"
                  />
                  Iniciando sesión…
                </>
              ) : (
                <>
                  <LockKeyhole aria-hidden="true" className="size-4" />
                  Entrar
                </>
              )}
            </Button>
          </form>

          <p className="mt-8 text-center text-xs leading-5 text-muted">
            No existe registro público ni recuperación por correo.
          </p>
        </div>
      </main>
    </div>
  );
}
