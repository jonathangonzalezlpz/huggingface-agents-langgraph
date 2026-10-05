# huggingface-agents-langgraph

Implementación en desarrollo de la asignación final de la Unidad 4 del [Hugging Face Agents Course](https://huggingface.co/learn/agents-course/unit4/introduction). El objetivo es construir con LangGraph un sistema que resuelva tareas GAIA de nivel 1 mediante capacidades especializadas. Las respuestas finales deben respetar la restricción **Exact Match**: devolver la respuesta solicitada sin explicación ni texto adicional.

## Diseño

La arquitectura propuesta es un workflow controlado e híbrido. Usa señales deterministas, como la extensión del adjunto, para seleccionar una capacidad; deja al LLM las decisiones que requieren interpretar la pregunta. El flujo previsto resuelve adjuntos, obtiene evidencias, razona sobre ellas y produce una respuesta final.

El diseño contempla rutas especializadas para código, hojas de cálculo, documentos, investigación web y preguntas resolubles directamente. `Evidence` ya está definido con `content`, `source_type` y `source`, para asociar la información obtenida con su procedencia. La arquitectura y las decisiones están desarrolladas en [docs/analisis-inicial-gaia.md](docs/analisis-inicial-gaia.md); este README resume el estado actual.

## Estado actual

Están implementados los tipos `Evidence` y `AgentState`, el preprocesamiento, la resolución local de adjuntos y un router determinista para `.py`, `.xlsx` y `.pdf`. La rama `.py` consulta al LLM para decidir si debe inspeccionar o ejecutar el archivo, obtiene evidencia, razona sobre ella y produce `submitted_answer`.

Las demás ramas todavía terminan después del router. Tampoco hay un ejecutor que procese las 20 preguntas ni envío de respuestas al benchmark.

## Estructura

```text
src/huggingface_agents_langgraph/
├── answer_production.py # Formato de la respuesta final
├── attachments.py       # Índice GAIA y descarga local de adjuntos
├── code_processing.py   # Decisión entre inspeccionar y ejecutar adjuntos Python
├── config.py            # URL y tiempos límite del LLM y de ejecución
├── graph.py             # Construcción y compilación del StateGraph actual
├── llm.py               # Cliente del endpoint local de chat completions
├── preprocessing.py     # Validación y normalización de la entrada
├── reasoning.py         # Respuesta candidata basada en la evidencia
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

`LLM_BASE_URL` permite configurar el endpoint OpenAI-compatible del modelo y, por defecto, apunta a `http://127.0.0.1:8080/v1`. El dataset GAIA requiere acceso autorizado en Hugging Face; configura un token de lectura en `HF_TOKEN`. Copia `.env.example` como `.env` y añade el token. `.env` está excluido de Git. `attachments.py` consulta `gaia-benchmark/GAIA` (configuración `2023_level1`, partición `validation`) mediante `datasets` y `huggingface_hub`.

El lanzador del modelo acepta estos parámetros:

| Parámetro | Valor predeterminado | Uso |
|---|---|---|
| `Model` | `Qwen/Qwen3-8B-GGUF:Q5_K_M` | Repositorio y cuantización del modelo |
| `HostAddress` | `127.0.0.1` | Interfaz local donde escucha el servidor |
| `Port` | `8080` | Puerto del servidor |
| `SleepIdleSeconds` | `300` | Inactividad antes de descargar el modelo |

El script no selecciona explícitamente backend GPU ni capas para offload; el uso de GPU depende de la instalación de `llama.cpp` disponible en el sistema.

## Ejecución actual

No existe todavía un punto de entrada que recorra el benchmark completo. Para ejecutar la pregunta de ejemplo con un adjunto Python, inicia primero el servidor local de Qwen y ejecuta:

```powershell
uv run --env-file .env python -c "from huggingface_agents_langgraph.graph import build_state_graph; graph = build_state_graph(); print(graph.invoke({'task_id': 'f918266a-b3e0-4914-865d-4faa564f1aef', 'question': 'What is the final numeric output from the attached Python code?', 'file_name': 'f918266a-b3e0-4914-865d-4faa564f1aef.py'}))"
```

El resultado incluye `evidence`, `answer_candidate` y `submitted_answer`. La ejecución del adjunto tiene un límite de sesenta segundos.

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

También se pueden pasar `-Model`, `-HostAddress` y `-Port`. El script configura `llama.cpp` con `--sleep-idle-seconds`: al vencer el periodo sin peticiones, el servidor libera de memoria el modelo y la caché de contexto; una petición posterior los vuelve a cargar. El proceso del servidor permanece activo. El grafo usa el servidor llama.cpp mediante su API compatible con OpenAI. Consulta la [documentación de opciones del servidor llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).

### Adjuntos GAIA

El análisis del proyecto documenta errores 404 del endpoint oficial de Unit 4 `/files/{task_id}` para algunas tareas con adjuntos. Para el desarrollo local, `attachments.py` obtiene los metadatos desde `gaia-benchmark/GAIA` y descarga el archivo con `hf_hub_download`. El índice de tareas se mantiene en caché durante la ejecución del proceso. El repositorio no incluye archivos del benchmark.

### Arrancar el sistema

El lanzador inicia Qwen si aún no está activo, espera a que su API responda y permite elegir el modo:

```powershell
.\scripts\start_agent.ps1
```

También se puede indicar directamente `-Mode frontend` o `-Mode terminal`. El modo terminal permite escoger una pregunta aleatoria o procesar la batería completa. Consulta [docs/ejecucion-local.md](docs/ejecucion-local.md) para preparación, opciones del lanzador y funcionamiento de ambos modos.

### Frontal GAIA

Con el servidor de Qwen iniciado y `.env` configurado, arranca el frontal local:

```powershell
uv run --env-file .env python -m huggingface_agents_langgraph.web_app
```

Abre `http://127.0.0.1:7860`. Permite cargar una pregunta aleatoria o la batería que devuelve `GET /questions`, descargar el adjunto y ejecutar una o todas las preguntas. La batería se procesa en orden y muestra la respuesta por pregunta. Las rutas que aún no están implementadas se indican en la tarjeta sin respuesta.

## Desarrollo

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest
```
