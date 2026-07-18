# Frontend

La aplicación será una SPA React/TypeScript organizada por funcionalidades,
con una capa de aplicación compartida mínima:

```text
src/
  app/          Providers, router, layouts y bootstrap
  features/     auth, explorer, uploads, previews, player y search
  entities/     entry, upload y media-job
  shared/       API client, UI shadcn, hooks, tipos y utilidades puras
```

Los componentes visuales no llamarán a `fetch` directamente. Cada feature
expone su API pública y usa un cliente HTTP central que maneja Problem Details,
CSRF, cancelación y renovación de sesión. El estado remoto se paginará; nunca
se conservará en memoria el árbol completo.
