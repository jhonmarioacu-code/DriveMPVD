import { describe, expect, it, vi } from "vitest";

import {
  getCurrentSession,
  isAuthenticationFailure,
  loginWithCookie,
  logoutCurrentSession,
  refreshAccessSession,
} from "@/features/auth/api/auth-api";
import { apiClient, ApiClientError } from "@/shared/api/client";

const authenticationData = {
  session_id: "01912345-6789-7abc-8def-0123456789ac",
  token_type: "Bearer" as const,
  access_token: null,
  refresh_token: null,
  access_expires_at: "2026-07-18T22:00:00Z",
  refresh_expires_at: "2026-07-25T22:00:00Z",
};

describe("auth-api", () => {
  it("inicia sesión por cookies sin permitir renovación recursiva", async () => {
    const request = vi
      .spyOn(apiClient, "request")
      .mockResolvedValue(authenticationData);

    await loginWithCookie({ username: "Admin", password: "secret" });

    expect(request).toHaveBeenCalledWith(
      "/auth/login",
      expect.objectContaining({
        method: "POST",
        cache: "no-store",
        body: JSON.stringify({
          username: "Admin",
          password: "secret",
          delivery: "cookie",
        }),
      }),
      { retryUnauthorized: false },
    );
  });

  it("traduce la sesión HTTP al usuario global", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValue({
      admin_id: "admin-id",
      session_id: "session-id",
      username: "Admin",
    });

    await expect(getCurrentSession()).resolves.toEqual({
      adminId: "admin-id",
      sessionId: "session-id",
      username: "Admin",
    });
  });

  it("no intenta renovar sin prueba CSRF", async () => {
    const request = vi.spyOn(apiClient, "request");

    await expect(refreshAccessSession()).resolves.toBe(false);
    expect(request).not.toHaveBeenCalled();
  });

  it("serializa renovaciones concurrentes y rota por cookies", async () => {
    document.cookie = "drivempvd_csrf=csrf-token; path=/";
    let resolveRequest: ((value: typeof authenticationData) => void) | undefined;
    const request = vi.spyOn(apiClient, "request").mockReturnValue(
      new Promise((resolve) => {
        resolveRequest = resolve;
      }),
    );

    const first = refreshAccessSession();
    const second = refreshAccessSession();
    expect(request).toHaveBeenCalledOnce();
    resolveRequest?.(authenticationData);

    await expect(Promise.all([first, second])).resolves.toEqual([true, true]);
    expect(request).toHaveBeenCalledWith(
      "/auth/refresh",
      expect.objectContaining({ method: "POST", cache: "no-store" }),
      { retryUnauthorized: false },
    );
  });

  it("distingue una sesión expirada de un fallo de red", async () => {
    document.cookie = "drivempvd_csrf=csrf-token; path=/";
    const expired = new ApiClientError({
      status: 401,
      code: "auth.session_revoked",
      message: "Expired",
    });
    vi.spyOn(apiClient, "request").mockRejectedValueOnce(expired);
    await expect(refreshAccessSession()).resolves.toBe(false);
    expect(isAuthenticationFailure(expired)).toBe(true);

    const networkError = new TypeError("Network error");
    vi.spyOn(apiClient, "request").mockRejectedValueOnce(networkError);
    await expect(refreshAccessSession()).rejects.toBe(networkError);
    expect(isAuthenticationFailure(networkError)).toBe(false);
  });

  it("cierra la sesión mediante un POST protegido", async () => {
    const requestVoid = vi.spyOn(apiClient, "requestVoid").mockResolvedValue(undefined);

    await logoutCurrentSession();

    expect(requestVoid).toHaveBeenCalledWith("/auth/logout", {
      method: "POST",
      cache: "no-store",
    });
  });
});
