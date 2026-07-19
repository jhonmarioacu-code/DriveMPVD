import { ArrowLeft, FileQuestion } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/shared/ui/button";

export function NotFoundPage() {
  return (
    <div className="grid min-h-[60vh] place-items-center text-center">
      <div>
        <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-brand-soft text-brand">
          <FileQuestion aria-hidden="true" className="size-6" />
        </span>
        <p className="eyebrow mt-6">Error 404</p>
        <h1 className="mt-2 text-2xl font-bold">Esta página no existe</h1>
        <p className="mt-3 text-sm text-muted">
          La dirección puede ser incorrecta o aún no estar disponible.
        </p>
        <Button asChild className="mt-6" variant="secondary">
          <Link to="/">
            <ArrowLeft aria-hidden="true" className="size-4" />
            Volver al inicio
          </Link>
        </Button>
      </div>
    </div>
  );
}
