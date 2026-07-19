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
    ├── diálogo de visualización de archivo
    └── bandeja persistente de subidas y reproductor de audio
```

En pantallas pequeñas, la barra lateral es un drawer, la toolbar agrupa acciones
y la vista conserva targets táctiles adecuados. Lista/cuadrícula, tema y
preferencias no sensibles se guardan localmente.

## Features

| Feature        | Responsabilidad                                                                        |
| -------------- | -------------------------------------------------------------------------------------- |
| `auth`         | Estado de sesión, login, logout, refresh y CSRF                                        |
| `explorer`     | Navegación, breadcrumb, selección, orden, lista/cuadrícula                             |
| `file-actions` | Crear, renombrar, mover, copiar, eliminar y descargar                                  |
| `uploads`      | Archivos por selección o drag-and-drop, cola, chunks, reintento/reanudación y progreso |
| `search`       | Consulta con debounce, filtros y resultados paginados                                  |
| `viewers`      | Clasificación segura, visores nativos, miniaturas acotadas y descarga de fallback      |
| `activity`     | Recientes y favoritos                                                                  |
| `trash`        | Listado, restauración, borrado definitivo y vaciado                                    |
| `jobs`         | Progreso de operaciones asíncronas y notificaciones                                    |

Las features `auth`, `explorer`, `uploads` y `viewers` quedaron implementadas
en las Fases 4 a 7. `auth` mantiene la identidad solo en memoria, usa cookies
HttpOnly, inyecta CSRF en mutaciones, serializa refresh y protege rutas.
`explorer` consulta la raíz y los breadcrumbs, pagina hijos mediante cursor,
invalida su caché tras mutaciones y nunca descarga contenido para mostrar
metadatos. `uploads` conserva una cola en memoria, usa sesiones y offsets del
backend para reintentar un archivo seleccionado y refresca la carpeta al
publicarlo. `viewers` hace un `HEAD` de preflight para la entrega `inline` y
delega los bytes al navegador con elementos nativos, en vez de guardarlos en
TanStack Query o en estado React.

Cada feature exporta una superficie pública. No se importan internals de otra
feature; la coordinación ocurre en layouts o mediante contratos de aplicación.

## Estado y datos

- Estado remoto: TanStack Query con cache de navegación por carpeta y páginas
  por carpeta/filtros/cursor, invalidación tras mutaciones y cancelación con
  `AbortController`.
- Estado de UI: selección, menú contextual, modales, vista y preferencias.
- Estado de transferencias: máquina de estados por archivo en memoria, sin
  guardar credenciales ni bytes. El offset se reconcilia con el servidor al
  reintentar; una recarga completa no conserva el `File` ni la sesión local.
- Estado de visualización: el diálogo mantiene solo el archivo seleccionado y
  controles de presentación; TanStack Query conserva temporalmente las
  cabeceras del `HEAD`, nunca el cuerpo del archivo.
- No se almacena el árbol ni archivos completos en memoria.

La búsqueda aplica debounce corto y descarta respuestas obsoletas. El scroll
solicita la siguiente página por cursor. Mutaciones optimistas solo se usan
cuando existe rollback inequívoco; operaciones destructivas esperan al servidor.

## Tipos e iconos

La API entrega `mime_type`, `extension` y una categoría canónica. El frontend
mapea categorías a iconos: carpeta, PDF, Word, Excel, PowerPoint, texto,
imagen, vídeo, audio, ZIP, RAR, 7Z y genérico. La extensión solo cambia
presentación y puede orientar el control de UI; no autoriza una vista previa ni
la ejecución. La cabecera de entrega del backend es la autoridad final.

## Visualización y reproducción

- Imágenes: `<img>` autenticado con zoom entre 50 % y 300 % y rotación visual.
- Vídeo: `<video controls>` con `preload="metadata"`; el navegador solicita
  rangos al endpoint de contenido cuando lo necesita.
- Audio: `<audio controls>` con `preload="metadata"`, sin cargar la biblioteca
  completa ni mantener una playlist global.
- PDF: `<iframe>` con el visor nativo que ofrezca el navegador,
  `referrerPolicy="no-referrer"` y entrega por rangos. La descarga es el
  fallback si el navegador no proporciona visor PDF.
- Las URLs se construyen sobre el mismo origen y usan cookies HttpOnly. Antes
  de mostrarlas, un `HEAD` exige `Content-Disposition: inline`; HTML, SVG y
  MIME no permitidos no se incrustan.
- Office y archivos comprimidos: icono/metadatos y descarga; no se promete
  renderizado de formatos para los que no se solicitó visualizador.

Las miniaturas del explorador no son derivados de servidor todavía: una imagen
raster de hasta 1 MiB usa la fuente de forma perezosa; todos los demás casos
usan un placeholder. Esto evita descargar vídeo, PDF o blobs grandes durante
el render del listado. El contrato futuro de miniaturas deberá añadir un worker
y un endpoint de derivados explícitos.

## Interacción

El menú contextual y la toolbar invocan los mismos commands. Atajos previstos:
crear carpeta, renombrar, copiar/mover, papelera, descargar, búsqueda, cambiar
vista, seleccionar todo visible y cerrar preview. Los atajos se deshabilitan en
inputs y respetan convenciones del sistema.

Drag-and-drop de archivos se dirige a la carpeta abierta. La API vigente no
admite carpetas completas ni rutas relativas, por lo que esa selección no se
ofrece todavía. Una bandeja muestra progreso en bytes, error recuperable,
reintento y cancelación; la pausa y la persistencia entre recargas requieren un
incremento posterior.

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
