---
title: GAIA LangGraph Agent
emoji: 🧭
colorFrom: indigo
colorTo: green
sdk: static
app_file: space/index.html
license: mit
short_description: Local LangGraph agent for GAIA tasks and experiment tracking
tags:
  - agents
  - langgraph
  - gaia
  - evaluation
  - portfolio
---

# huggingface-agents-langgraph

Implementación en desarrollo de la asignación final de la Unidad 4 del [Hugging Face Agents Course](https://huggingface.co/learn/agents-course/unit4/introduction). El objetivo es construir con LangGraph un sistema que resuelva tareas GAIA de nivel 1 mediante capacidades especializadas. Las respuestas finales deben respetar la restricción **Exact Match**: devolver la respuesta solicitada sin explicación ni texto adicional.

## Diseño

La arquitectura es un workflow controlado e híbrido. Usa señales deterministas, como la extensión del adjunto, para seleccionar capacidades conocidas; deja al LLM las decisiones que requieren interpretar la pregunta. El pipeline v2 revisa la suficiencia de las evidencias y puede encadenar herramientas dentro de límites configurables antes de resolver y producir la respuesta final en etapas separadas.

El diseño contempla rutas especializadas para código, hojas de cálculo, documentos, investigación web y preguntas resolubles directamente. `Evidence` ya está definido con `content`, `source_type` y `source`, para asociar la información obtenida con su procedencia. La arquitectura y las decisiones están desarrolladas en [docs/analisis-inicial-gaia.md](docs/analisis-inicial-gaia.md); este README resume el estado actual.

## Estado actual

La referencia V2 y el protocolo de evaluación individual y conjunta de las mejoras
se conservan en [docs/evolucion-pipeline.md](docs/evolucion-pipeline.md).

El panel permite seleccionar V2 o la V3 experimental y activar mejoras por separado
para comparar sus resultados. La implementación y sus límites están descritos en
[docs/pipeline-v3.md](docs/pipeline-v3.md); los resultados medidos se recogen en
[docs/resultados-v3.md](docs/resultados-v3.md). Las respuestas y trazas completas
permanecen en el historial local y no forman parte de la publicación del portfolio.

Están implementados los tipos `Evidence` y `AgentState`, el preprocesamiento, la resolución local de adjuntos y las ramas `.py`, `.xlsx`, `.pdf`, web, Wikipedia, multimedia y directa. La rama `.py` consulta al LLM para decidir si debe inspeccionar o ejecutar el archivo; `.xlsx` usa planes de cálculo deterministas con análisis general del LLM como respaldo; `.pdf` extrae texto con número de página y usa el selector común. Las tareas sin adjunto se clasifican con el LLM. El revisor puede continuar investigando, abrir enlaces, calcular sin adjuntos o examinar otros instantes de un vídeo. El perfil Solo directo deshabilita las herramientas. `answer_production` presenta la solución y comprueba restricciones mecánicas del formato.

El selector común divide y prioriza evidencias de cualquier fuente textual, mantiene referencias a páginas o URLs y limita el contexto con `DOCUMENT_MAX_EVIDENCE_CHARACTERS`. La búsqueda usa coincidencias léxicas, por lo que puede no encontrar pasajes relacionados expresados con términos distintos. La ruta web usa DDGS y, cuando la pregunta menciona papers o artículos, añade Europe PMC para buscar publicaciones biomédicas y recuperar texto completo cuando está disponible en acceso abierto. No todos los artículos ni disciplinas están cubiertos por Europe PMC; DDGS sigue como búsqueda general. La ruta Wikipedia consulta la Wikipedia inglesa actual, no una revisión histórica concreta. La extracción PDF requiere una capa de texto; los PDF escaneados todavía necesitan OCR. El frontal permite lanzar experimentos sobre la batería de 20 preguntas y comparar sus resultados.

## Estructura

```text
src/huggingface_agents_langgraph/
├── attachments.py       # Índice GAIA y descarga local de adjuntos
├── code_processing.py   # Decisión entre inspeccionar y ejecutar adjuntos Python
├── config.py            # URL y límites de ejecución
├── document_processing.py # Extracción de texto de adjuntos PDF
├── experiments.py       # Configuración de capacidades por experimento
├── evidence_selection.py # Selección compartida de evidencias relevantes
├── graph.py             # Construcción y compilación del StateGraph actual
├── llm.py               # Cliente del endpoint local de chat completions
├── multimedia_processing.py # Audio, imágenes y vídeo
├── preprocessing.py     # Validación y normalización de la entrada
├── reasoning.py         # Respuesta final desde evidencias o pregunta directa
├── routing.py           # Clasificación por extensión o intención semántica
├── spreadsheet_processing.py # Análisis híbrido de libros Excel
├── web_research.py      # Búsqueda web, académica y Wikipedia
└── state.py             # Evidence, AgentState y Route
tests/
├── test_attachments.py
├── test_document_processing.py
├── test_evidence_selection.py
├── test_graph.py
├── test_preprocessing.py
├── test_reasoning.py
├── test_routing.py
├── test_spreadsheet_processing.py
└── test_web_research.py
scripts/
└── start_local_llm.ps1  # Lanzador local de llama.cpp y Qwen
docs/
└── analisis-inicial-gaia.md
```

## Instalación

El proyecto requiere Python 3.12 y usa `uv` junto con `uv.lock` para gestionar las dependencias:

```powershell
uv sync --extra multimedia
```

## Configuración

`LLM_BASE_URL` configura el endpoint OpenAI-compatible principal y, por defecto, apunta a `http://127.0.0.1:8080/v1`. `OLLAMA_BASE_URL` permite descubrir y usar modelos locales de Ollama desde el selector de experimentos; su valor predeterminado es `http://127.0.0.1:11434/v1`. Ollama debe estar ejecutándose para que sus modelos aparezcan. El dataset GAIA requiere acceso autorizado en Hugging Face; configura un token de lectura en `HF_TOKEN`. Copia `.env.example` como `.env` y añade el token. `.env` está excluido de Git. `attachments.py` consulta `gaia-benchmark/GAIA` (configuración `2023_level1`, partición `validation`) mediante `datasets` y `huggingface_hub`.

El lanzador del modelo acepta estos parámetros:

| Parámetro | Valor predeterminado | Uso |
|---|---|---|
| `Model` | `Qwen/Qwen3-8B-GGUF:Q5_K_M` | Repositorio y cuantización del modelo |
| `HostAddress` | `127.0.0.1` | Interfaz local donde escucha el servidor |
| `Port` | `8080` | Puerto del servidor |
| `SleepIdleSeconds` | `300` | Inactividad antes de descargar el modelo |

El script no selecciona explícitamente backend GPU ni capas para offload; el uso de GPU depende de la instalación de `llama.cpp` disponible en el sistema.

## Ejecución del grafo

El lanzador ofrece modo terminal y frontal web; el frontal permite ejecutar la batería de 20 tareas bajo perfiles de capacidades y seleccionar, por experimento, un modelo del endpoint principal o de Ollama. Para invocar directamente el grafo con una pregunta de ejemplo y un adjunto Python, inicia primero el servidor local de Qwen y ejecuta:

```powershell
uv run --extra multimedia --env-file .env python -c "from huggingface_agents_langgraph.graph import build_state_graph; graph = build_state_graph(); print(graph.invoke({'task_id': 'f918266a-b3e0-4914-865d-4faa564f1aef', 'question': 'What is the final numeric output from the attached Python code?', 'file_name': 'f918266a-b3e0-4914-865d-4faa564f1aef.py'}))"
```

El resultado incluye `evidence` y `submitted_answer`. La ejecución del adjunto tiene un límite de sesenta segundos.

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
uv run --extra multimedia --env-file .env python -m huggingface_agents_langgraph.web_app
```

Abre `http://127.0.0.1:7860`. Permite cargar una pregunta aleatoria o la batería que devuelve `GET /questions`, descargar adjuntos, elegir el modelo razonador y ejecutar preguntas con capacidades configurables. El historial local permite comparar experimentos alineados por `task_id` y calcular el acierto por pregunta con el split de validación GAIA. El score oficial sigue siendo una acción separada que envía explícitamente las respuestas al evaluador del curso y actualiza su clasificación. Consulta [docs/ejecucion-local.md](docs/ejecucion-local.md) para los detalles.

## Desarrollo

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

### Rama multimedia

La rama `multimedia_processing` reconoce adjuntos de audio, imagen y video, y enlaces directos de YouTube. Instala sus dependencias opcionales con `uv sync --extra multimedia`. La primera ejecucion descarga los modelos locales: Whisper `small` para transcripcion, AST AudioSet para etiquetas acusticas y SmolVLM `256M` para imagenes. La inferencia usa CPU e int8 para Whisper; las imagenes de video se muestrean a intervalos de al menos cinco segundos con un maximo de ocho frames. El reconocimiento acustico se ejecuta solo si la pregunta menciona sonidos, musica u otros eventos.

Se pueden cambiar `MEDIA_ASR_MODEL`, `MEDIA_AUDIO_CLASSIFIER_MODEL` y `MEDIA_VLM_MODEL` en `.env`. Descargar videos de YouTube requiere acceso de red y puede depender de la disponibilidad del sitio y del contenido. El muestreo limitado puede no capturar eventos visuales breves.

`MEDIA_MODELS_IDLE_SECONDS` controla cuanto tiempo permanecen cargados Whisper, AST y el VLM despues de terminar su uso; por defecto son cinco minutos. Al vencer el periodo se liberan de memoria y se vuelven a cargar cuando se necesitan otra vez.

## Pipeline v2

El agente puede encadenar investigación, seguir enlaces y papers, calcular sin adjuntos y revisar fotogramas adicionales dentro de límites configurables. La resolución dispone de un presupuesto propio y la respuesta final tiene validación de formato. Las trazas y los experimentos se conservan en el servidor local, además de la copia del navegador. Consulta [docs/pipeline-v2.md](docs/pipeline-v2.md) para el grafo, la configuración, las métricas y sus límites.

## Publicación y autoría

El [Space público](https://huggingface.co/spaces/jonyglez/huggingface-agents-langgraph) presenta el proyecto y su código. El agente y el panel de experimentos se ejecutan en local; la presentación estática no ejecuta inferencias ni recibe las credenciales del entorno local. Consulta [docs/publicacion-space.md](docs/publicacion-space.md) para preparar y auditar las publicaciones.

Autor: [Jonathan González López](https://www.linkedin.com/in/jonathan-gonz%C3%A1lez-l%C3%B3pez-31b578209/). Código distribuido bajo la [licencia MIT](LICENSE). Los modelos y datasets conservan sus propias licencias y condiciones de acceso.
