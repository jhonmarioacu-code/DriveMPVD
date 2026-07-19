import { RouterProvider } from "react-router-dom";
import { useState } from "react";

import { QueryProvider } from "@/app/providers/query-provider";
import { ThemeProvider } from "@/app/providers/theme-provider";
import { createAppRouter } from "@/app/router";
import { AuthProvider } from "@/features/auth";

export function App() {
  const [router] = useState(createAppRouter);

  return (
    <ThemeProvider>
      <QueryProvider>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </QueryProvider>
    </ThemeProvider>
  );
}
