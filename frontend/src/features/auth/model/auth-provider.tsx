import { useQueryClient } from "@tanstack/react-query";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import {
  getCurrentSession,
  isAuthenticationFailure,
  loginWithCookie,
  logoutCurrentSession,
  refreshAccessSession,
} from "@/features/auth/api/auth-api";
import {
  AuthContext,
  type AuthContextValue,
  type AuthStatus,
  type AuthUser,
  type LoginCredentials,
} from "@/features/auth/model/auth-context";
import { apiClient } from "@/shared/api/client";

interface AuthState {
  status: AuthStatus;
  user: AuthUser | null;
  initializationError: string | null;
}

const initialState: AuthState = {
  status: "loading",
  user: null,
  initializationError: null,
};

export function AuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<AuthState>(initialState);

  const clearSession = useCallback(() => {
    queryClient.clear();
    setState({
      status: "unauthenticated",
      user: null,
      initializationError: null,
    });
  }, [queryClient]);

  useEffect(() => {
    apiClient.setUnauthorizedHandler(async () => {
      const refreshed = await refreshAccessSession();
      if (!refreshed) clearSession();
      return refreshed;
    });
    return () => apiClient.setUnauthorizedHandler(null);
  }, [clearSession]);

  useEffect(() => {
    let active = true;
    void getCurrentSession()
      .then((user) => {
        if (active) {
          setState({
            status: "authenticated",
            user,
            initializationError: null,
          });
        }
      })
      .catch((error: unknown) => {
        if (!active) return;
        setState({
          status: "unauthenticated",
          user: null,
          initializationError: isAuthenticationFailure(error)
            ? null
            : "No fue posible comprobar la sesión. Verifica que la API esté disponible.",
        });
      });
    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (credentials: LoginCredentials) => {
    await loginWithCookie(credentials);
    const user = await getCurrentSession();
    setState({
      status: "authenticated",
      user,
      initializationError: null,
    });
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutCurrentSession();
    } catch (error) {
      if (!isAuthenticationFailure(error)) throw error;
    }
    clearSession();
  }, [clearSession]);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, login, logout }),
    [login, logout, state],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}
