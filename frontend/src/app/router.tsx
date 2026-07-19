import { createBrowserRouter } from "react-router-dom";

import { AppShell } from "@/app/shell/app-shell";
import { DashboardPage } from "@/pages/dashboard-page";
import { NotFoundPage } from "@/pages/not-found-page";

export function createAppRouter() {
  return createBrowserRouter([
    {
      path: "/",
      element: <AppShell />,
      children: [
        { index: true, element: <DashboardPage /> },
        { path: "*", element: <NotFoundPage /> },
      ],
    },
  ]);
}
