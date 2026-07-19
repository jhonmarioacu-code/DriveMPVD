import { RouterProvider } from "react-router-dom";
import { useState } from "react";

import { QueryProvider } from "@/app/providers/query-provider";
import { ThemeProvider } from "@/app/providers/theme-provider";
import { createAppRouter } from "@/app/router";

export function App() {
  const [router] = useState(createAppRouter);

  return (
    <ThemeProvider>
      <QueryProvider>
        <RouterProvider router={router} />
      </QueryProvider>
    </ThemeProvider>
  );
}
