# Arquitectura del frontend (GAIA Agent Studio)

Aplicación en `frontend/` (React, TypeScript estricto, Vite). Convive con la interfaz
anterior, que sigue en `src/huggingface_agents_langgraph/frontend/` y se sirve en `/`, hasta
alcanzar paridad (M3.4). **No confundir ambas carpetas.** La nueva se sirve en `/app`.

El diseño de experiencia está en [DISENO_UX_V4.md](DISENO_UX_V4.md) y las fases en
[ROADMAP_V4.md](ROADMAP_V4.md). La seguridad de las dependencias, en
[frontend-seguridad.md](frontend-seguridad.md).

## Arquitectura hexagonal pragmática

```
frontend/src/
├── domain/        Modelo (Architecture, Catalog, Diagnostic…) y reglas puras. Sin React ni red.
├── application/   Casos de uso que reciben puertos (hoy: loadLibrary).
├── ports/         Interfaces de salida: CatalogPort, ArchitecturePort, SystemPort.
├── adapters/
│   ├── wire.ts    Contrato JSON del backend (zod) y traducción al dominio. Único sitio que
│   │              conoce el snake_case del backend.
│   ├── http/      Adaptador contra el backend Python.
│   └── memory/    Adaptador con datos de ejemplo (demo y tests). demo-data.json se genera.
├── ui/            Componentes React: shell, páginas y piezas reutilizables.
├── app/           Raíz de composición: elige adaptadores y monta rutas y proveedores.
├── i18n/          Catálogos es/en tipados y proveedor de idioma.
├── theme/         Proveedor de tema (sistema, claro, oscuro).
└── styles/        Tokens de diseño (tokens.css) y Tailwind.
```

Regla de dependencias: `ui → application → domain`; los `adapters` implementan `ports`; solo
`app` conoce los adaptadores concretos. Los puertos existen donde hay dos implementaciones
reales (HTTP y memoria), que es lo que permite probar sin backend y publicar una demo en el
Space. La capa `application` crece con cada caso de uso (edición del grafo en M3.1) en lugar
de definirse por adelantado.

## Comandos

```powershell
cd frontend
npm ci              # instalación reproducible desde package-lock.json
npm run dev         # servidor de desarrollo en 127.0.0.1:5173 (proxy de /api al backend :7860)
npm run check       # tipos estrictos, ESLint (incluye accesibilidad), Prettier y Vitest
npm run build       # compila a src/huggingface_agents_langgraph/static/app (ignorado por Git)
```

Equivalente con script: `.\scripts\build_frontend.ps1`. Después, `uv run python -m
huggingface_agents_langgraph.web_app` y `http://127.0.0.1:7860/app/`.

Sin el paquete compilado, `/app` explica cómo construirlo y `/` sigue mostrando la interfaz
anterior. Previsto para macOS y Linux (Node y Vite son multiplataforma), sin verificar: el
proyecto solo se ha probado en Windows.

## Pruebas

- **Adaptadores:** contrato con el backend, errores de red, HTTP y de forma de los datos.
- **Aplicación completa** (Testing Library con el adaptador en memoria): navegación,
  idioma, tema, estados de carga y error, y accesibilidad con axe en ambos idiomas.
- **i18n:** mismas claves y marcadores en ambos idiomas, plurales y detección.
- **Tokens:** todos los pares de color cumplen WCAG (4,5:1 texto, 3:1 componentes) en ambos
  temas. Se comprueba contra `tokens.css`, que es la única fuente de los colores.
- jsdom no calcula diseño, así que el contraste se verifica en los tokens y no en axe.

`demo-data.json` se regenera con `uv run python -m huggingface_agents_langgraph.demo_data`
y un test de Python falla si se desincroniza del backend.

## Cómo extender

- **Idioma nuevo:** añadir `messages.xx.ts` con `Record<MessageKey, string>` (el compilador
  exige todas las claves) y registrarlo en `i18n/index.ts`.
- **Texto nuevo:** añadir la clave en `messages.es.ts` y en `messages.en.ts`.
- **Componente nuevo del catálogo:** añadir `component.<id>` en ambos catálogos; si falta, la
  interfaz muestra la descripción del backend.
- **Llamada nueva al backend:** puerto en `ports/`, esquema y traducción en `adapters/wire.ts`,
  implementación HTTP y en memoria, y prueba de contrato.
- **Colores:** solo en `styles/tokens.css`; el test de contraste los valida.

## Modo demostración

`?demo=1` o `VITE_STUDIO_MODE=demo` usan el adaptador en memoria y enrutado por hash (un
alojamiento estático no puede reescribir rutas). Un cartel permanente declara que los datos
son de ejemplo. Contiene solo el catálogo y la arquitectura integrada: nunca preguntas,
respuestas ni ejecuciones de GAIA. La publicación en el Space es de M6 y requiere
autorización explícita.
