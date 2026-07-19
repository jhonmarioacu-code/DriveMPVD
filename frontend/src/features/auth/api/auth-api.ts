import { apiClient, ApiClientError, readBrowserCookie } from "@/shared/api/client";
import { environment } from "@/shared/config/environment";

import type { AuthUser, LoginCredentials } from "@/features/auth/model/auth-context";

interface AuthenticationData {
  session_id: string;
  token_type: "Bearer";
  access_token: null;
  refresh_token: null;
  access_expires_at: string;
  refresh_expires_at: string;
}

interface SessionData {
  admin_id: string;
  session_id: string;
  username: string;
}

let activeRefresh: Promise<boolean> | null = null;

export function isAuthenticationFailure(error: unknown) {
  return (
    error instanceof ApiClientError &&
    (error.status === 401 ||
      error.status === 403 ||
      error.code === "auth.session_revoked")
  );
}

export async function loginWithCookie(credentials: LoginCredentials) {
  return apiClient.request<AuthenticationData>(
    "/auth/login",
    {
      method: "POST",
      cache: "no-store",
      body: JSON.stringify({ ...credentials, delivery: "cookie" }),
    },
    { retryUnauthorized: false },
  );
}

export async function getCurrentSession(): Promise<AuthUser> {
  const session = await apiClient.request<SessionData>("/auth/session", {
    cache: "no-store",
  });
  return {
    adminId: session.admin_id,
    sessionId: session.session_id,
    username: session.username,
  };
}

export function refreshAccessSession() {
  if (readBrowserCookie(environment.csrfCookieName) === null) {
    return Promise.resolve(false);
  }
  if (activeRefresh !== null) return activeRefresh;

  activeRefresh = apiClient
    .request<AuthenticationData>(
      "/auth/refresh",
      {
        method: "POST",
        cache: "no-store",
        body: JSON.stringify({ delivery: "cookie" }),
      },
      { retryUnauthorized: false },
    )
    .then(() => true)
    .catch((error: unknown) => {
      if (isAuthenticationFailure(error)) return false;
      throw error;
    })
    .finally(() => {
      activeRefresh = null;
    });
  return activeRefresh;
}

export function logoutCurrentSession() {
  return apiClient.requestVoid("/auth/logout", {
    method: "POST",
    cache: "no-store",
  });
}
