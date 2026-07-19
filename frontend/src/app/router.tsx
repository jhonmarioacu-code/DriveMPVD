import { createBrowserRouter } from "react-router-dom";

import { AppShell } from "@/app/shell/app-shell";
import { PublicOnlyRoute, RequireAuth } from "@/features/auth";
import { DashboardPage } from "@/pages/dashboard-page";
import { LoginPage } from "@/pages/login-page";
import { NotFoundPage } from "@/pages/not-found-page";

export function createAppRouter() {
  return createBrowserRouter([
    {
      element: <PublicOnlyRoute />,
      children: [
        {
          path: "/login",
          element: <LoginPage />,
        },
      ],
    },
    {
      element: <RequireAuth />,
      children: [
        {
          path: "/",
          element: <AppShell />,
          children: [
            { index: true, element: <DashboardPage /> },
            { path: "*", element: <NotFoundPage /> },
          ],
        },
      ],
    },
  ]);
}
