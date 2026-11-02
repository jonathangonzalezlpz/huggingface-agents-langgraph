# GAIA Agent Studio (frontend)

Constructor visual y laboratorio de evaluación para agentes GAIA. Aplicación en `frontend/` (React,
TypeScript estricto, Vite, React Flow, Tailwind, Radix y lucide), servida por el backend en `/app` (`/`
redirige). No tiene afiliación con el benchmark GAIA. Sustituyó a la interfaz anterior en JavaScript, que
sigue en el historial de Git y en la etiqueta `pipeline-v3.1.0`. La seguridad de sus dependencias está en
[frontend-seguridad.md](frontend-seguridad.md).

## Para quién y qué hace

| Perfil | Qué necesita |
|---|---|
| Investigador-desarrollador | Probar variantes de arquitectura sin tocar Python, entender por qué una falla y comparar con rigor. |
| Evaluador de portfolio | Entender el proyecto en minutos y ver el constructor funcionando, normalmente sin GPU ni backend (modo demostración). |
| Usuario futuro | Instalar, abrir y construir su primer agente sin leer el código. |

Criterio rector: **la interfaz no promete más de lo que el backend demuestra.** Una advertencia no es un
error, una ejecución sola no es una conclusión, y un camino hasta el final no garantiza terminación.

## Las cuatro áreas

| Área | Para qué |
|---|---|
| **Constructor** | Biblioteca de arquitecturas con historial de versiones y editor visual con validación en vivo. |
| **Ejecuciones** | Lanzar una pregunta con una versión guardada y ver el recorrido por el grafo, con tiempos y errores. |
| **Experimentos** | Baterías de las 20 preguntas, historial, comparación, puntuación local y envío oficial. |
| **Sistema** | Estado del backend, modelos, GPU y memoria; tema e idioma. |

## El Constructor

Paleta con búsqueda (22 componentes en 8 categorías), lienzo y inspector, con un panel de diagnósticos
debajo.

- **Nodo:** título, componente, franja de categoría (icono y etiqueta además del color), indicador de
  validación y, en los de adquisición, la insignia «recupera errores» (su contrato no garantiza `evidence`:
  el fallo se convierte en una nota). Si el nodo tiene una decisión, tiene una salida por rama; una rama sin
  conectar se dibuja discontinua.
- **Parámetros por nodo:** un componente puede declarar parámetros tipados (texto, número con rango,
  booleano, enumerado). El inspector genera el formulario desde el catálogo, con valor por defecto visible
  y «Restablecer»; la tarjeta resume los valores (`n=3 · mode=slow`).
- **Se impide al momento** (con el motivo en un tooltip): conectar hacia el inicio, una segunda salida
  directa, ramas duplicadas o fuera de la estrategia, ids reservados o repetidos. Lo que depende del flujo
  de datos (campos garantizados, alcanzabilidad, camino al final) no se impide: lo diagnostica el
  validador del backend, que es la única fuente de verdad.
- **Versiones:** la V3.1 integrada es de solo lectura (se duplica para editar). «Guardar como versión» crea
  siempre una versión nueva e inmutable (si no cambió nada, avisa «ya existe»). El historial muestra la
  cadena padre → hijo con hash corto y un resumen de cambios calculado en el cliente. La disposición se
  guarda aparte y no cambia la identidad de la versión.
- **Plantillas para comparar:** «V3.1 + verificador», «Planificar → herramienta → razonar» y
  «Autoconsistencia». Se construyen con los mismos comandos del editor, así que no pueden ser inválidas.
- **Atajos:** `Ctrl+K` paleta, `Ctrl+Z`/`Ctrl+Shift+Z`, `Ctrl+S` guardar, `Ctrl+Enter` validar,
  `Ctrl+D` duplicar, `Supr`, `F` ajustar vista, `L` autodisposición, `?` ayuda. «Conectar con…» es la
  alternativa accesible al arrastre.

### Diagnósticos

El validador devuelve códigos estables; la interfaz los traduce y enfoca el nodo o la arista afectada.

| Código | Gravedad | Significa |
|---|---|---|
| `INVALID_DEFINITION`, `UNKNOWN_IMPLEMENTATION`, `UNKNOWN_ROUTING_STRATEGY`, `UNKNOWN_STATE_TYPE`, `UNKNOWN_STATE_FIELD` | Error | Definición mal formada o que usa algo fuera del catálogo. |
| `UNKNOWN_PARAM`, `INVALID_PARAM_VALUE`, `MISSING_PARAM` | Error | Parámetro inexistente, fuera de rango o ausente. |
| `BRANCH_LABELS_MISMATCH`, `START_EDGE_MISMATCH`, `OUTGOING_EDGE_CONFLICT` | Error | Ramas que no coinciden con la estrategia, entrada incorrecta o varias salidas. |
| `UNREACHABLE_NODE`, `NO_PATH_TO_END` | Error | Nodo al que no se llega, o desde el que no se llega al final. |
| `REQUIRED_INPUT_UNAVAILABLE` | Error | Ningún camino produce un campo necesario. |
| `REQUIRED_INPUT_NOT_GUARANTEED` | Aviso | El campo solo existe en algunos caminos. En la V3.1 es esperado para `file_path` y para la salida de los nodos de adquisición. |
| `CYCLE_DETECTED` | Info | Hay un ciclo; que termine depende de los presupuestos, no se demuestra. |

Reglas de redacción: nunca «inválido» para un aviso ni «correcto» para algo que solo no tiene errores.

## Ejecuciones y experimentos

- **Ejecuciones:** solo versiones guardadas y sin errores. Se elige el modelo y los ajustes (versión del
  pipeline, mejoras, semilla y, en «Avanzado», capacidades, razonamiento, tokens, muestreo y modelo de
  visión) y una pregunta libre o de GAIA. El resultado muestra respuesta, ruta, duración y el recorrido
  sobre el grafo (nodos no visitados atenuados, el que falló marcado), con reproducción paso a paso. La
  petición es síncrona y «Dejar de esperar» no cancela en el servidor; la traza detallada se ve al terminar
  (ver [Observabilidad](#observabilidad)).
- **Baterías:** las ejecuta el servidor (`application/batteries.py`), no el navegador, para que los registros
  sean comparables con los del ejecutor de línea de comandos. Una a la vez, 1 a 20 preguntas, progreso por
  sondeo, detener y reanudar.
- **Historial y comparación:** de 2 a 20 experimentos con una base. Primero un aviso de **comparabilidad**
  (mismas tareas, código y arquitectura, y qué ajustes difieren) y después las métricas. Las diferencias se
  etiquetan «dentro del rango observado», «fuera del rango observado» o «no valorable con una sola
  ejecución»; nunca se pinta una flecha verde o roja sobre una diferencia no valorable.
- **Puntuación:** la local se calcula y se guarda en el servidor con las respuestas del registro guardado
  (el navegador nunca envía respuestas). **El envío oficial** abre un diálogo que explica qué se envía, a
  dónde y que actualiza una clasificación pública, y exige confirmación explícita.

## Observabilidad

La traza se consulta cuando la ejecución ha terminado. No hay progreso en vivo, ni lo necesita el análisis. La
interfaz vive en `ui/observability/` y lee los endpoints descritos en [backend.md](backend.md).

- **Detalle de una ejecución (`/runs/:id`):** dos pestañas, «Recorrido» (el grafo) y «Traza». La traza muestra un
  resumen (duración, llamadas al modelo, tokens de entrada y salida, errores, nodo más lento) y una cascada con
  una fila por span, filtros por tipo y «Solo errores», y la línea de «qué hizo» bajo cada nodo. Al pulsar una fila
  se carga bajo demanda su contenido (la actualización de un nodo o los mensajes, parámetros y salida de una
  llamada) y su error si lo hay.
- **Avisos:** una franja amarilla si una decisión o respuesta cita cifras sin respaldo en la evidencia; una azul si
  las llamadas de un registro antiguo se asignaron a su nodo por estimación; y una amarilla si alguna no pudo
  enlazarse.
- **Detalle de un experimento:** pestañas «Respuestas» y «Observabilidad». La segunda muestra acierto local, tiempo
  medio, tokens de salida y errores técnicos; el tiempo por etapa con su parte del total; las rutas con su acierto;
  los fallos agrupados; y las preguntas más lentas con su etapa más lenta.
- **Exportar:** enlaces con el nombre del formato (JSONL, OTLP, Markdown en una ejecución; CSV en una batería).
  El JSONL y el CSV sirven para analizar con un script o con una IA; el Markdown es el resumen legible.
- **Capas:** `domain/trace.ts` y `domain/insights.ts` (tipos, filas de la cascada, formato de duraciones y enlaces
  de exportación, con pruebas), `TracePort` en `ports/`, esquema zod en `adapters/wire/trace.ts` (tolera atributos
  que no sean escalares) y el adaptador HTTP. En el modo demostración las trazas no están disponibles.

## Arquitectura

Hexagonal pragmática:

```
frontend/src/
├── domain/        Modelo y reglas puras. Sin React ni red.
│   └── editor/    Grafo editable, comandos, historial, conversión y plantillas.
├── application/   Casos de uso que reciben puertos.
├── ports/         Interfaces de salida: catálogo, arquitecturas, sistema, validación, disposición, borradores.
├── adapters/
│   ├── wire/      Contrato JSON del backend (zod), un módulo por recurso. Único sitio que conoce el snake_case.
│   ├── http/      Adaptador contra el backend Python.
│   ├── drafts/    Borradores en localStorage (validados al leer; lo corrupto se descarta).
│   └── memory/    Datos de ejemplo (demo y tests). demo-data.json se genera.
├── ui/            Componentes React: shell, páginas y piezas reutilizables.
├── app/           Raíz de composición: elige adaptadores y monta rutas.
├── i18n/          Catálogos es/en tipados.
├── theme/         Tema (sistema, claro, oscuro).
└── styles/        Tokens de diseño y Tailwind.
```

Regla de dependencias: `ui → application → domain`; los adaptadores implementan los puertos y solo `app`
conoce los concretos. Los puertos existen porque hay dos implementaciones reales (HTTP y memoria), lo que
permite probar sin backend y publicar una demo. ESLint hace cumplir la dirección de dependencias, un máximo
de 450 líneas por fichero y complejidad 20 (sin línea base: ya no queda deuda).

### El editor

El estado del grafo en edición es **código de dominio puro**; React Flow solo dibuja una proyección y emite
eventos que se traducen en comandos, así que las reglas se prueban sin navegador.

- Cada nodo tiene una salida: ninguna, directa o una decisión (estrategia y una rama por etiqueta). Lo que
  el backend no admite no se puede representar.
- Los comandos son funciones `(documento, …) → aceptado | rechazado con motivo`; un comando que no cambia
  nada no registra historial. El historial es una pila de estados inmutables.
- `fromDefinition`/`toDefinition` convierten a la definición del backend; lo que el editor no puede
  representar se informa, nunca se oculta. Las ramas sin conectar no se exportan, para que el validador las
  señale.
- Los borradores son locales al navegador y recuerdan qué versión guardaron. La validación es en vivo con
  retardo (≈ 600 ms) y descarta respuestas ya reemplazadas por otra petición más reciente.
- `EditorWorkspace` solo compone: cada responsabilidad vive en un hook o pieza con nombre.

### Interfaz y accesibilidad

- Objetivo WCAG 2.2 AA: todo el flujo con teclado, color nunca como único portador de información, contraste
  4,5:1 en texto y 3:1 en componentes (comprobado contra `tokens.css` en ambos temas), foco visible,
  anuncios a lectores de pantalla y `prefers-reduced-motion`.
- Bilingüe español/inglés con textos externalizados; tema que sigue al sistema con cambio inmediato.
- Pensada para escritorio (≥ 1280 px). En móvil el lienzo es de solo lectura.
- Fuera de alcance: subgrafos, edición de prompts, colaboración multiusuario, importar o exportar formatos.

### Pruebas y comandos

Pruebas con Vitest y Testing Library: contratos de los adaptadores, aplicación completa con el adaptador en
memoria (navegación, idioma, tema, accesibilidad con axe), dominio del editor (incluida una prueba aleatoria
de invariantes), ejecuciones, experimentos, historial y puntuación (el envío real nunca se ejercita), i18n y
contraste de tokens. jsdom no prueba el arrastre ni el aspecto: eso se comprobó en un Edge real.

```powershell
cd frontend
npm ci              # nunca `npm install`; .npmrc exige versiones exactas
npm run dev         # 127.0.0.1:5173, con proxy de /api al backend :7860
npm run check       # tipos, ESLint (accesibilidad), Prettier y Vitest
npm run build       # → src/huggingface_agents_langgraph/static/app (ignorado por Git)
```

Equivalente: `.\scripts\build_frontend.ps1`. Verificado solo en Windows.

### Cómo extender

- **Texto nuevo o idioma:** claves en `messages.es.ts` y `messages.en.ts` (el compilador exige todas).
- **Componente del catálogo:** `component.<id>` en ambos catálogos (si falta, se muestra la descripción del
  backend) y `param.<componente>.<parámetro>` para sus parámetros.
- **Llamada nueva al backend:** puerto en `ports/`, esquema y traducción en `adapters/wire/`, implementación
  HTTP y en memoria, y prueba de contrato.
- **Colores:** solo en `styles/tokens.css`.
- Tras cambiar el catálogo o la arquitectura, regenerar la demo:
  `uv run python -m huggingface_agents_langgraph.demo_data` (un test falla si se desincroniza).

## Modo demostración

`?demo=1` o `VITE_STUDIO_MODE=demo` usan el adaptador en memoria y rutas por hash (un alojamiento estático
no puede reescribir rutas). Un cartel permanente declara que los datos son de ejemplo. Solo contiene el
catálogo y la arquitectura integrada, con tareas inventadas: nunca preguntas, respuestas ni ejecuciones de
GAIA, cuyo dataset es de acceso restringido. En este modo no se puede guardar, validar grafos editados ni
ejecutar. Publicarlo en el Space es una acción externa que requiere autorización explícita (ver
[ejecucion.md](ejecucion.md)).
