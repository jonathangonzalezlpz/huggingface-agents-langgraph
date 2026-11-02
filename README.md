---
title: GAIA LangGraph Agent
emoji: 🧭
colorFrom: indigo
colorTo: green
sdk: static
app_file: space/index.html
license: mit
short_description: LangGraph agent for GAIA tasks and a visual agent studio
tags:
  - agents
  - langgraph
  - gaia
  - evaluation
  - portfolio
---

# GAIA LangGraph Agent y GAIA Agent Studio

Un agente construido con LangGraph para las tareas de nivel 1 del benchmark GAIA (asignación final de la
Unidad 4 del [Hugging Face Agents Course](https://huggingface.co/learn/agents-course/unit4/introduction)),
y una plataforma alrededor para **aprender a construir agentes y pipelines**: un constructor visual, un
motor de experimentos reproducibles y un comparador de resultados. Las respuestas deben cumplir **Exact
Match**: la respuesta pedida, sin explicación ni texto adicional.

GAIA Agent Studio no tiene afiliación con el benchmark GAIA.

## Qué hay

- **El agente** (`pipeline/`): un único grafo de LangGraph con procesadores por capacidad (código, Excel,
  PDF, web y Wikipedia, audio, imagen y vídeo), una revisión que decide si la evidencia basta, y
  razonamiento y presentación separados. Funciona con modelos locales (llama.cpp o Ollama).
- **El Studio** (`frontend/`): constructor visual con 22 componentes (incluidos roles de LLM y herramientas
  vetadas), validación en vivo, versiones inmutables, ejecuciones con recorrido sobre el grafo, baterías de
  20 preguntas y comparación de experimentos.
- **Una capa declarativa** (`graph_definition/`): una arquitectura es un dato que se valida y se compila a
  LangGraph, y solo admite componentes registrados y autorizados.

## Estado

| | |
|---|---|
| Pipeline | V2 (por defecto), V3 y V3.1 como opciones del mismo grafo |
| Mejor resultado local | 10/20 con Qwen3.5-9B y Qwen3-VL-8B; perfil recomendado 9/20 en 45,9 s por pregunta |
| Referencia histórica | V2: 6/20 en 47,3 s |
| Pruebas | 819 de Python y 485 del frontend |
| Plataforma | Windows 11, Python 3.12, RTX 4060 Ti de 16 GB. No verificado en otros sistemas |

Son puntuaciones locales de una sola pasada por configuración, sobre 20 tareas: no demuestran
significación estadística. Los detalles y sus límites están en [docs/evaluacion.md](docs/evaluacion.md).
El proyecto sigue en desarrollo.

## Inicio rápido

Requiere Python 3.12, [`uv`](https://docs.astral.sh/uv/), el comando `llama` de llama.cpp y Node (solo para
compilar el frontend).

```powershell
uv sync --extra multimedia
Copy-Item .env.example .env          # añade HF_TOKEN (con acceso al dataset gaia-benchmark/GAIA)
.\scripts\build_frontend.ps1         # primera vez y tras cambiar frontend/
.\scripts\start_agent.ps1 -Mode frontend
```

Abre <http://127.0.0.1:7860>. El lanzador inicia el servidor del modelo si hace falta. Todos los detalles
(modos, modelos, baterías, puntuación) están en [docs/ejecucion.md](docs/ejecucion.md).

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest --basetemp=.runtime/pytest-tmp
```

## Documentación

Se lee en este orden:

| Documento | Contenido |
|---|---|
| [analisis-inicial-gaia.md](docs/analisis-inicial-gaia.md) | El análisis y el diseño inicial del agente, escritos antes de construirlo |
| [pipeline.md](docs/pipeline.md) | Cómo funciona el agente y qué añadió cada versión |
| [evaluacion.md](docs/evaluacion.md) | Qué se midió, los resultados y por qué se eligieron esos modelos |
| [backend.md](docs/backend.md) | Estructura por capas y la capa declarativa |
| [frontend.md](docs/frontend.md) | El Studio: diseño, arquitectura y cómo extenderlo |
| [frontend-seguridad.md](docs/frontend-seguridad.md) | Seguridad de las dependencias del frontend |
| [ejecucion.md](docs/ejecucion.md) | Instalación, uso y publicación en Hugging Face |

## Publicación y autoría

El [Space público](https://huggingface.co/spaces/jonyglez/huggingface-agents-langgraph) es una presentación
estática del proyecto: el agente y el Studio se ejecutan en local, y la página no ejecuta inferencias ni
recibe credenciales. El repositorio no incluye archivos del benchmark; el dataset GAIA requiere acceso
autorizado.

Autor: [Jonathan González López](https://www.linkedin.com/in/jonathan-gonz%C3%A1lez-l%C3%B3pez-31b578209/).
Código bajo [licencia MIT](LICENSE). Los modelos y datasets conservan sus propias licencias y condiciones
de acceso.
