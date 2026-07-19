import { RouterProvider } from "react-router-dom";
import { useState } from "react";

import { QueryProvider } from "@/app/providers/query-provider";
import { ThemeProvider } from "@/app/providers/theme-provider";
import { createAppRouter } from "@/app/router";
import { AuthProvider } from "@/features/auth";
import { UploadsProvider } from "@/features/uploads";

export function App() {
  const [router] = useState(createAppRouter);

  return (
    <ThemeProvider>
      <QueryProvider>
        <AuthProvider>
          <UploadsProvider>
            <RouterProvider router={router} />
          </UploadsProvider>
        </AuthProvider>
      </QueryProvider>
    </ThemeProvider>
  );
}
