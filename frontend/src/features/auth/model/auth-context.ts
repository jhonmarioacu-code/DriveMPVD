import { createContext, useContext } from "react";

export interface AuthUser {
  adminId: string;
  sessionId: string;
  username: string;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

export interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  initializationError: string | null;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth debe utilizarse dentro de AuthProvider.");
  }
  return context;
}
