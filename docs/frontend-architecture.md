# Arquitectura del frontend

## Principios

La SPA usa React y TypeScript en modo estricto, Vite, Tailwind CSS y componentes
shadcn/ui accesibles. Se organiza por feature y no replica entidades del backend
como estado global mutable. El contrato OpenAPI genera tipos y cliente base;
adaptadores por feature traducen DTOs a modelos de vista.

## Composición visual

```text
App shell
├── barra lateral: Inicio, Mis archivos, Recientes, Favoritos, Papelera
├── barra superior: búsqueda, acciones, selector de tema y sesión
└── área principal
    ├── breadcrumb y toolbar
    ├── lista o cuadrícula virtualizada
    ├── panel/diálogo de preview
    └── bandeja persistente de subidas y reproductor de audio
```

En pantallas pequeñas, la barra lateral es un drawer, la toolbar agrupa acciones
y la vista conserva targets táctiles adecuados. Lista/cuadrícula, tema y
preferencias no sensibles se guardan localmente.

## Features

| Feature | Responsabilidad |
|---|---|
| `auth` | Estado de sesión, login, logout, refresh y CSRF |
| `explorer` | Navegación, breadcrumb, selección, orden, lista/cuadrícula |
| `file-actions` | Crear, renombrar, mover, copiar, eliminar y descargar |
| `uploads` | Drag-and-drop, carpetas, cola, chunks, pausa/reanudación y progreso |
| `search` | Consulta con debounce, filtros y resultados paginados |
| `previews` | Router de preview por tipo, zoom, rotación y fullscreen |
| `player` | Video HTML5 y reproductor de audio con playlist |
| `activity` | Recientes y favoritos |
| `trash` | Listado, restauración, borrado definitivo y vaciado |
| `jobs` | Progreso de operaciones asíncronas y notificaciones |

Las features `auth` y `explorer` quedaron implementadas en las Fases 4 y 5.
`auth` mantiene la identidad solo en memoria, usa cookies HttpOnly, inyecta CSRF
en mutaciones, serializa refresh y protege rutas. `explorer` consulta la raíz y
los breadcrumbs, pagina hijos mediante cursor, invalida su caché tras mutaciones
y nunca descarga contenido para mostrar metadatos. Las demás features continúan
sujetas a sus fases correspondientes.

Cada feature exporta una superficie pública. No se importan internals de otra
feature; la coordinación ocurre en layouts o mediante contratos de aplicación.

## Estado y datos

- Estado remoto: TanStack Query con cache de navegación por carpeta y páginas
  por carpeta/filtros/cursor, invalidación tras mutaciones y cancelación con
  `AbortController`.
- Estado de UI: selección, menú contextual, modales, vista y preferencias.
- Estado de transferencias: máquina de estados por archivo, persistida de forma
  local sin guardar credenciales ni bytes.
- No se almacena el árbol ni archivos completos en memoria.

La búsqueda aplica debounce corto y descarta respuestas obsoletas. El scroll
solicita la siguiente página por cursor. Mutaciones optimistas solo se usan
cuando existe rollback inequívoco; operaciones destructivas esperan al servidor.

## Tipos e iconos

La API entrega `media_type`, `extension` y una categoría canónica. El frontend
mapea categorías a iconos: carpeta, PDF, Word, Excel, PowerPoint, texto, imagen,
video, audio, ZIP, RAR, 7Z y genérico. La extensión solo cambia presentación;
no autoriza preview ni ejecución.

## Preview y reproducción

- Imágenes: objeto URL/remoto confinado, zoom, rotación visual, fullscreen y
  navegación entre imágenes de la página actual.
- Video: elemento HTML5 con URL autenticada, Range y controles nativos/mejorados.
- Audio: reproductor persistente con cola derivada de la selección/listado; no
  intenta cargar toda la biblioteca.
- PDF: visor integrado cargado dinámicamente, worker separado y solicitudes por
  rango. No se usa un iframe público al almacenamiento.
- Office y archivos comprimidos: icono/metadatos y descarga; no se promete
  renderizado de formatos para los que no se solicitó visualizador.

## Interacción

El menú contextual y la toolbar invocan los mismos commands. Atajos previstos:
crear carpeta, renombrar, copiar/mover, papelera, descargar, búsqueda, cambiar
vista, seleccionar todo visible y cerrar preview. Los atajos se deshabilitan en
inputs y respetan convenciones del sistema.

Drag-and-drop distingue archivos, carpetas y movimientos internos. La subida
de carpetas conserva rutas relativas validadas. Una bandeja muestra progreso en
bytes, velocidad, error recuperable, pausa, reintento y cancelación.

## Accesibilidad y temas

Tema claro, oscuro y preferencia del sistema usan tokens CSS semánticos. Se
mantiene contraste WCAG AA, navegación completa por teclado, foco visible,
labels, anuncios de progreso y reducción de movimiento. La cuadrícula conserva
semántica y no depende solo de color o icono.

## Errores y notificaciones

Problem Details se traduce mediante `code`, no por texto. Los errores de campo
aparecen junto al control; resultados de commands usan toast; fallos persistentes
o destructivos usan diálogo. Una renovación de sesión se serializa para evitar
tormentas de refresh; si falla, se limpia el estado y se vuelve a login.
