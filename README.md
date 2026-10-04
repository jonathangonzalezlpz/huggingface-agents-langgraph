# huggingface-agents-langgraph

Implementación en desarrollo de la asignación final de la Unidad 4 del [Hugging Face Agents Course](https://huggingface.co/learn/agents-course/unit4/introduction). El objetivo es construir con LangGraph un sistema que resuelva tareas GAIA de nivel 1 mediante capacidades especializadas. Las respuestas finales deben respetar la restricción **Exact Match**: devolver la respuesta solicitada sin explicación ni texto adicional.

## Diseño

La arquitectura propuesta es un workflow controlado e híbrido. Usa señales deterministas, como la extensión del adjunto, para seleccionar una capacidad; deja al LLM las decisiones que requieren interpretar la pregunta. El flujo previsto resuelve adjuntos, obtiene evidencias, razona sobre ellas y produce una respuesta final.

El diseño contempla rutas especializadas para código, hojas de cálculo, documentos, investigación web y preguntas resolubles directamente. `Evidence` ya está definido con `content`, `source_type` y `source`, para asociar la información obtenida con su procedencia. La arquitectura y las decisiones están desarrolladas en [docs/analisis-inicial-gaia.md](docs/analisis-inicial-gaia.md); este README resume el estado actual.

## Estado actual

Están implementados los tipos `Evidence` y `AgentState`, el preprocesamiento que valida `task_id` y `question` y recorta espacios de la pregunta, la resolución local de adjuntos y un router determinista para `.py`, `.xlsx` y `.pdf`. Las rutas desconocidas reciben `unimplemented`.

El grafo actual ejecuta `preprocessing`, resuelve el adjunto si `file_name` está presente y pasa el estado al router. Después termina. `code_processing.py` contiene solo la firma del nodo y lanza `NotImplementedError`. Todavía no hay procesamiento de ramas, integración de un LLM en el grafo, razonamiento, producción de respuesta, ni un ejecutor que procese las 20 preguntas. El envío de respuestas al benchmark tampoco está implementado.

## Estructura

```text
src/huggingface_agents_langgraph/
├── attachments.py       # Índice GAIA y descarga local de adjuntos
├── code_processing.py   # Firma inicial del nodo para adjuntos Python
├── graph.py             # Construcción y compilación del StateGraph actual
├── preprocessing.py     # Validación y normalización de la entrada
├── routing.py           # Clasificación por extensión
└── state.py             # Evidence, AgentState y Route
tests/
├── test_attachments.py
└── test_preprocessing.py
scripts/
└── start_local_llm.ps1  # Lanzador local de llama.cpp y Qwen
docs/
└── analisis-inicial-gaia.md
```

## Instalación

El proyecto requiere Python 3.12 y usa `uv` junto con `uv.lock` para gestionar las dependencias:

```powershell
uv sync
```

## Configuración

No hay variables de entorno ni credenciales de modelo configuradas por el proyecto. `attachments.py` consulta el dataset público `gaia-benchmark/GAIA` (configuración `2023_level1`, partición `validation`) mediante `datasets` y `huggingface_hub`; la biblioteca utiliza su caché y configuración local habituales.

El lanzador del modelo acepta estos parámetros:

| Parámetro | Valor predeterminado | Uso |
|---|---|---|
| `Model` | `Qwen/Qwen3-8B-GGUF:Q5_K_M` | Repositorio y cuantización del modelo |
| `HostAddress` | `127.0.0.1` | Interfaz local donde escucha el servidor |
| `Port` | `8080` | Puerto del servidor |
| `SleepIdleSeconds` | `300` | Inactividad antes de descargar el modelo |

El script no selecciona explícitamente backend GPU ni capas para offload; el uso de GPU depende de la instalación de `llama.cpp` disponible en el sistema.

## Ejecución actual

No existe todavía un punto de entrada que ejecute el agente sobre las preguntas del curso. Para observar el grafo parcial con una entrada sin adjunto:

```powershell
uv run python -c "from huggingface_agents_langgraph.graph import build_state_graph; graph = build_state_graph(); print(graph.invoke({'task_id': 'local-example', 'question': '  What is 2 + 2?  ', 'file_name': ''}))"
```

El resultado contiene el estado normalizado y `route: "unimplemented"`; el grafo aún no genera una respuesta.

### Servidor local de Qwen

El script requiere el comando `llama` de `llama.cpp`. Si no está instalado, puede instalarse con:

```powershell
winget install llama.cpp
```

Después, inicia el servidor en primer plano:

```powershell
.\scripts\start_local_llm.ps1
```

De forma predeterminada sirve `Qwen3-8B-GGUF` con cuantización `Q5_K_M` en `127.0.0.1:8080`. Para cambiar el reposo a diez minutos:

```powershell
.\scripts\start_local_llm.ps1 -SleepIdleSeconds 600
```

También se pueden pasar `-Model`, `-HostAddress` y `-Port`. El script configura `llama.cpp` con `--sleep-idle-seconds`: al vencer el periodo sin peticiones, el servidor libera de memoria el modelo y la caché de contexto; una petición posterior los vuelve a cargar. El proceso del servidor permanece activo. Este servidor aún no está conectado al grafo ni a un cliente LLM del proyecto. Consulta la [documentación de opciones del servidor llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).

### Adjuntos GAIA

El análisis del proyecto documenta errores 404 del endpoint oficial de Unit 4 `/files/{task_id}` para algunas tareas con adjuntos. Para el desarrollo local, `attachments.py` obtiene los metadatos desde `gaia-benchmark/GAIA` y descarga el archivo con `hf_hub_download`. El índice de tareas se mantiene en caché durante la ejecución del proceso. El repositorio no incluye archivos del benchmark.

## Desarrollo

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest
```
