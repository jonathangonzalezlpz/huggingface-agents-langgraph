# Backend: estructura y capa declarativa

Cómo está organizado el código Python, qué reglas lo mantienen ordenado y cómo se componen arquitecturas
de agente sin escribir Python. El pipeline que ejecuta el agente está en [pipeline.md](pipeline.md).

## Estructura por roles

El proyecto nació como la práctica reducida de un curso: unos cuarenta módulos planos en una carpeta.
Creció (experimentos, constructor visual, baterías, comparación) y pedía orden. Se reorganizó en una
arquitectura hexagonal sin puertos formales: lo importante (reglas y datos) no depende de lo accesorio
(modelos, red, ficheros, HTTP), y las dependencias apuntan hacia dentro.

Paquetes bajo `src/huggingface_agents_langgraph/`:

| Paquete | Contiene |
|---|---|
| `domain` | Reglas y datos puros: estado del agente, configuración de experimento, comparación, métricas, contrato de respuesta, evaluación local. |
| `pipeline` | Los nodos del agente (preprocesado, router, procesadores por capacidad, revisión, razonamiento, respuesta) y `graph.py`. |
| `adapters` | Cliente del LLM, registros JSON de `.runtime` y seguimiento de recursos. |
| `application` | Casos de uso: ejecutar un experimento y una pregunta, baterías, puntuación, almacén de arquitecturas, selección de grafo. |
| `studio` | Componentes que ofrece el constructor: roles de LLM y biblioteca de herramientas. |
| `graph_definition` | La capa declarativa (más abajo). |
| `api` | HTTP: primitivas, tabla de rutas y un módulo por recurso. |

`config.py` y `tracing.py` son el núcleo compartido. Los puntos de entrada que se lanzan con `python -m`
quedan en la raíz: `web_app`, `cli`, `demo_data`, `model_server`, `model_trials`, `baseline_archive` y
`experiment_runner`.

**Quién puede importar a quién** lo fija `tests/test_architecture.py` (tabla `ALLOWED`): `domain` solo a sí
mismo; `adapters` a `domain` y `model_server`; `pipeline` a `adapters`, `domain` y `model_server`; `studio` a `pipeline`,
`adapters` y `domain`; `graph_definition` a `studio` y `domain`; `application` a `pipeline`, `adapters`,
`domain` y `graph_definition`. Ya no hay excepciones ni ciclos conocidos.

### Convenciones vigiladas por herramientas

- Líneas de hasta 88 caracteres y descripciones breves de una línea (Ruff).
- Funciones cortas y poco ramificadas: Ruff comprueba complejidad (C901) y tamaño (PLR0912, 0913, 0915).
  La línea base por fichero solo puede reducirse; hoy solo queda `PLR0913` (muchos argumentos) en
  `experiment_run.py`, `adapters/llm.py` y `graph_definition/registry.py`.
- Ficheros de menos de unas 450 líneas, un módulo por razón de cambio.

### Cómo se hizo la reestructuración

Por fases, cada una con parada y revisión, y sin cambiar el comportamiento de la V3.1:

| Fase | Qué hizo |
|---|---|
| F0 | Barandillas: test de dependencias entre módulos y límites de complejidad y tamaño. |
| F1 | Dividir lo añadido en los últimos hitos: `registry.py`, `web_app.py` (662 líneas → adaptador fino sobre `api/`), `architecture_store.py` y las páginas y adaptadores largos del frontend. |
| F2 | Mover los módulos a los paquetes por rol con `git mv` para conservar el historial. |
| F3 | Trocear las funciones largas de la V3.1 (`research.review`, `run_experiment`, hojas de cálculo, `normalize_experiment`, `chat_completion`…), siempre con tests de caracterización antes. |

Mover o editar código cambia el `source_identity` de los experimentos nuevos, como cualquier cambio. La
referencia funcional sigue en la etiqueta `pipeline-v3.1.0`. La equivalencia se apoya en los tests (819
pasan, incluidos los de equivalencia de la V3.1); no se lanzó una batería con modelo tras el refactor.

## HTTP (`api/`)

`web_app.py` convierte la petición en un `api.http.Request`, la busca en la tabla de rutas y escribe la
respuesta; los manejadores devuelven `JsonResponse`, `BytesResponse` o `Redirect` y nunca tocan el socket.
Cada recurso tiene su módulo en `api/handlers/`:

| Recurso | Rutas principales |
|---|---|
| Arquitecturas | `GET /api/catalog`, `GET/POST /api/architectures`, `POST /api/architectures/validate`, `GET/PUT /api/architectures/{id}/layout` |
| Ejecuciones | `POST /api/run`, `GET /api/runs/{id}` |
| Experimentos | `GET/POST /api/experiments`, `POST /api/experiments/compare`, `POST /api/experiments/{id}/evaluate`, `DELETE /api/experiments/{id}` |
| Baterías | `POST /api/batteries`, `GET /api/batteries/current`, `POST /api/batteries/stop` |
| Puntuación | `POST /api/evaluate`, `POST /api/score` (envío oficial) |
| Preguntas y sistema | `GET /api/questions`, `/api/random-question`, `/api/files/{task_id}`, `/api/status`, `/api/models` |

El paquete compilado del frontend se sirve en `/app` (respaldo a `index.html` para las rutas del cliente,
caché inmutable en `assets/`, protección contra salida de directorio). Las llamadas al servicio del curso
están en `api/course_service.py`.

## Capa declarativa (`graph_definition/`)

Permite definir, validar y compilar una arquitectura de agente como datos. Principio rector:
**composición controlada**. El constructor solo usa componentes registrados y autorizados; nunca genera ni
ejecuta Python arbitrario a partir de la configuración visual.

| Pieza | Responsabilidad |
|---|---|
| `AgentDefinition`, `NodeDefinition`, `EdgeDefinition` (`schema.py`) | Topología declarativa y parámetros por nodo. |
| `NodeContract` (`contracts.py`) | Entradas y salidas de cada nodo, tal como el nodo queda realmente compilado (con sus *wrappers* y su recuperación de errores). |
| `NodeRegistry` (`registry.py`) | Implementaciones autorizadas, con contrato, parámetros y manejador. |
| `authorization.py` | Lista blanca de funciones autorizadas, por ruta `paquete.modulo:funcion`. |
| `RoutingRegistry` (`routing_registry.py`) | Estrategias de decisión registradas (`route_on_verdict`, las de la V3.1…). |
| `GraphValidator` (`validator.py`, `diagnostics.py`) | Análisis estático con diagnósticos estructurados. |
| `GraphCompiler` (`compiler.py`) | De una definición validada a un `StateGraph` estándar de LangGraph. |
| `params.py` | Parámetros tipados: texto, número con rango, booleano, enumerado. |
| `components/` | Los catálogos: V3.1 (`v31.py`), roles de LLM, herramientas y el registro de Studio que los combina. |

`AgentDefinition` no duplica a `ExperimentConfig`: la primera es la topología; la segunda, los modelos,
prompts y presupuestos.

**Qué valida.** Estructura, componentes y estrategias conocidos, ramas completas, alcanzabilidad, camino al
final, y la disponibilidad de entradas por análisis de punto fijo (error si ningún camino produce un campo;
aviso si solo algunos). Los ciclos legítimos (`review ⇄ research_action`) se permiten. No admite *fan-out*
paralelo. **Qué no promete:** que un camino al final garantice la terminación (depende de los presupuestos)
ni que los valores sean válidos o la evidencia suficiente.

**Compilación.** Resuelve los componentes autorizados y envuelve cada nodo con `traced_node` y, en los de
adquisición, con la recuperación de errores, en el mismo orden que `pipeline/graph.py`. Los parámetros se
aplican con un `builder(params)` y se guardan resueltos en el registro de la ejecución
(`architecture.node_params`), para que siga siendo reproducible aunque cambie un valor por defecto. No hay
un segundo motor de ejecución. `tests/test_graph_equivalence.py` comprueba que la V3.1 declarativa tiene la
misma topología y comportamiento que `build_state_graph()` (6 escenarios, con nodos sustituidos).

### Catálogo

Hay dos catálogos. Los registros canónicos de la V3.1 (`create_gaia_v3_registry()` y
`create_gaia_v31_routing_registry()`: 12 componentes y 3 rutas) no cambian. El registro de Studio
(`create_studio_registry()`) añade los componentes nuevos y es el que usan el catálogo, la validación y la
compilación: 22 componentes en 8 categorías.

- **Roles de LLM** (sobre `chat_completion`, así heredan trazas, muestreo y presupuestos): `llm_planner`,
  `llm_verifier` (veredicto `ok`/`revise`, con tope de revisiones), `llm_reflect` y `self_consistency` (n
  muestras secuenciales y voto mayoritario). Usan cuatro campos opcionales de `AgentState` (`plan`,
  `verdict`, `candidates`, `revision_count`) que el grafo V3.1 no lee ni escribe. La ruta `route_on_verdict`
  es pura y el bucle verificar/revisar siempre termina.
- **Herramientas vetadas** (`studio/tool_library.py`): `web_search`, `wikipedia`, `fetch_url` y `calculate`,
  como `StructuredTool` de `langchain_core` (ya presente en `uv.lock`). Son código del proyecto, no se
  cargan por nombre ni desde un hub, y todas devuelven `Evidence`. Componentes: `tool_node`, `web_search`,
  `wikipedia_search`, `calculator`, `transcribe_audio` y `describe_image`. Añaden evidencia en vez de
  sustituirla y se registran con recuperación de errores.
- **No adoptados:** `smolagents` y `langchain-community` (su bucle de agente duplica el nuestro y
  `Tool.from_hub` ejecuta código remoto). Un agente ReAct de LangGraph y los subgrafos quedan para más
  adelante.

### Persistencia y reproducibilidad

`application/architecture_store.py` guarda versiones **inmutables** en `.runtime/architectures/`,
identificadas por el SHA-256 del JSON canónico: guardar contenido idéntico devuelve la versión existente.
Los borradores inválidos se guardan y la validación se calcula al leer. La V3.1 es una arquitectura
integrada de solo lectura (`builtin:gaia_v31`). Un campo nuevo del esquema solo se emite si no está vacío,
para no cambiar los hashes ya guardados.

`ExperimentConfig` tiene un campo opcional `architecture`. Si falta, se ejecuta `pipeline/graph.py` igual
que siempre (la clave ni aparece, así que los hashes existentes no cambian); si está, se compila esa
versión. Los registros de ejecución guardan motor, id, versión y `content_sha256`.
`experiment_runner --architecture <id>` y `POST /api/run` con `experiment.architecture` lanzan ejecuciones
sin editar Python.

### Comparación de experimentos

`domain/experiment_comparison.py` informa de la comparabilidad (mismo conjunto de tareas, código y
arquitectura; qué campos de configuración difieren), métricas por experimento (aciertos locales, media,
mediana, P95, errores técnicos, truncamientos) y alineación por tarea (ganadas, perdidas, sin cambio). Los
experimentos con la misma configuración, código y tareas se agrupan como repeticiones; con al menos dos a
cada lado, una diferencia se clasifica como dentro o fuera del rango observado, y con una sola ejecución
como no valorable. No expone textos de respuesta ni respuestas de referencia.

## Pruebas

```powershell
uv sync --extra multimedia
uv run ruff check .
uv run ruff format --check .
uv run pytest --basetemp=.runtime/pytest-tmp
```

`tests/conftest.py` bloquea las llamadas al LLM (los tests deben simularlas); DDGS y Hugging Face no están
bloqueados y cada test debe simularlos. `--basetemp` dentro de `.runtime/` evita un `PermissionError` de
Windows en `%TEMP%\pytest-of-<usuario>`.
