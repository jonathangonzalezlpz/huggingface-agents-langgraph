# Ejecución local y publicación

Cómo instalar el proyecto, arrancar el agente y el Studio, y publicar la presentación en Hugging Face.
Solo se ha verificado en Windows 11 con PowerShell.

## Preparación

Requiere Python 3.12 y `uv`:

```powershell
uv sync --extra multimedia
Copy-Item .env.example .env
```

- **Token:** añade a `HF_TOKEN` en `.env` un token de lectura de una cuenta con acceso al dataset
  `gaia-benchmark/GAIA` (configuración `2023_level1`, split `validation`). `.env` está excluido de Git.
  El repositorio no incluye archivos del benchmark.
- **Modelo local:** el comando `llama` de llama.cpp debe estar instalado (`winget install llama.cpp`). Por
  defecto se sirve `Qwen/Qwen3-8B-GGUF:Q5_K_M` en `127.0.0.1:8080`. `LLM_BASE_URL` cambia el endpoint
  principal y `OLLAMA_BASE_URL` (por defecto `127.0.0.1:11434/v1`) permite usar modelos de Ollama si está
  ejecutándose.
- **Frontend:** el paquete compilado no está en Git. La primera vez y tras cambiar `frontend/`:
  `.\scripts\build_frontend.ps1` (necesita Node en una versión parcheada y `npm ci`; ver
  [frontend-seguridad.md](frontend-seguridad.md)). Sin paquete, `/app` explica cómo construirlo.

## Arrancar

```powershell
.\scripts\start_agent.ps1                          # pregunta el modo
.\scripts\start_agent.ps1 -Mode frontend           # Studio en http://127.0.0.1:7860
.\scripts\start_agent.ps1 -Mode frontend -ModelMode exclusive   # un solo modelo nativo residente (V3.1)
.\scripts\start_agent.ps1 -Mode terminal
```

El lanzador consulta `/health`: si el modelo ya responde lo reutiliza; si no, inicia el servidor como
proceso oculto y espera hasta diez minutos (la primera vez puede descargar el modelo). Los registros del
servidor van a `%TEMP%\huggingface-agents-langgraph-llm.*.log`. Parámetros: `Model`, `HostAddress`, `Port`,
`SleepIdleSeconds` (descarga el modelo tras la inactividad; por defecto 300) y `StartupTimeoutSeconds`. Si
cambias el puerto, ajusta `LLM_BASE_URL`. El servidor sigue activo al cerrar la interfaz.

Para solo el servidor de Qwen en primer plano: `.\scripts\start_local_llm.ps1`. Para descargar los
modelos de V3.1 y consultar su estado: `python -m huggingface_agents_langgraph.model_server download` y
`status` (ver [evaluacion.md](evaluacion.md)).

## Usar el Studio

El modo `frontend` sirve el Studio solo en el equipo local; `/` redirige a `/app/`. Las áreas y su
funcionamiento están en [frontend.md](frontend.md). Lo que conviene saber al usarlo:

- **Baterías:** las ejecuta el servidor, así que siguen aunque cierres la pestaña. Solo una a la vez.
  «Detener» termina la pregunta en curso y para antes de la siguiente (no puede interrumpirla). Un
  experimento detenido se reanuda con su configuración y preguntas originales; el servidor lo rechaza si
  el código cambió. Las 20 preguntas son las del registro de la referencia V2: sin él
  (`.runtime/experiments/`) no se puede iniciar una batería.
- **Modelos:** el selector muestra los que anuncian `LLM_BASE_URL` y Ollama en ese momento. Los modelos de
  visión adicionales solo aparecen con `-ModelMode exclusive`.
- **Estado:** el panel consulta `/api/status` con los endpoints de solo lectura `/health` y `/props` de
  llama.cpp, así que no despierta el modelo. Con el modelo apagado puede tardar entre 2 y 7 s. El indicador
  de GPU informa de que PyTorch detecta CUDA, no de que todos los modelos la usen (Whisper va en CPU).
- **Puntuación local:** una batería completa se puntúa sola al terminar contra el split de validación; en
  los demás casos hay un botón «Puntuar localmente». Compara sin distinguir mayúsculas ni espacios
  exteriores y guarda solo el porcentaje y el acierto por `task_id`, nunca las respuestas de referencia.
- **Puntuación oficial:** es independiente y se hace solo desde el detalle de un experimento completo, con
  confirmación. El servidor envía las respuestas guardadas en el registro (no las del navegador) a
  `POST /submit` del curso. Ejecutar, puntuar localmente o comparar nunca hacen ese envío.
- **Datos:** todo se guarda en `.runtime/` (fuera de Git). Las preguntas de la batería las devuelve
  `GET /questions` del servicio del curso, que el navegador consulta directamente.

### Adjuntos y fuentes

Los endpoints oficiales de adjuntos de la Unidad 4 dan 404 para algunas tareas, así que
`pipeline/attachments.py` obtiene los metadatos de `gaia-benchmark/GAIA` y descarga con `hf_hub_download`
(el índice se cachea durante el proceso). Búsqueda general con DDGS, Europe PMC para publicaciones
biomédicas en acceso abierto y la API de MediaWiki para Wikipedia: todas requieren Internet.

### Multimedia

`uv sync --extra multimedia` instala Whisper (`small`, transcripción), AST AudioSet (etiquetas acústicas) y
SmolVLM `256M` (imágenes); la primera ejecución descarga los modelos. Se pueden cambiar con
`MEDIA_ASR_MODEL`, `MEDIA_AUDIO_CLASSIFIER_MODEL` y `MEDIA_VLM_MODEL`. `MEDIA_MODELS_IDLE_SECONDS` (por
defecto 300) controla cuánto permanecen cargados. Descargar vídeos de YouTube depende de la red y del sitio
(se ha visto un `HTTP 403` en una batería).

## Terminal y llamada directa

El modo `terminal` ofrece una pregunta aleatoria o la batería completa, secuencialmente. Para invocar el
grafo directamente con un adjunto Python (con el servidor de Qwen iniciado):

```powershell
uv run --extra multimedia --env-file .env python -c "from huggingface_agents_langgraph.pipeline.graph import build_state_graph; print(build_state_graph().invoke({'task_id': 'f918266a-b3e0-4914-865d-4faa564f1aef', 'question': 'What is the final numeric output from the attached Python code?', 'file_name': 'f918266a-b3e0-4914-865d-4faa564f1aef.py'}))"
```

## Pruebas

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest --basetemp=.runtime/pytest-tmp
```

Las pruebas de frontend están en [frontend.md](frontend.md).

## Publicación en Hugging Face

El Space `jonyglez/huggingface-agents-langgraph` es una **presentación estática** del proyecto y de su
autor, con enlace a su perfil y al código. El agente, el Studio y los modelos se ejecutan en local: la
página pública no llama a servicios del equipo, no ejecuta inferencias y no incluye respuestas del
benchmark, resultados privados ni el historial local. La configuración del Space está en el bloque YAML del
`README.md` (`sdk: static`, `app_file: space/index.html`, `license: mit`). La página es autocontenida, sin
fuentes externas ni analítica.

Preparar y auditar el paquete (no publica nada):

```powershell
uv run --env-file .env python scripts/publish_space.py
```

Usa los archivos versionados de Git más una lista explícita de archivos de presentación, e incluye el
código fuente del Studio (`frontend/`: TypeScript, configuración y `package-lock.json`, sin `node_modules`
ni el paquete compilado). Excluye `.git`,
`.env`, entornos, cachés, modelos, trazas y resultados. Audita patrones de tokens, claves privadas,
credenciales en URLs y rutas personales, y compara el paquete con el token configurado sin imprimirlo. Es
una comprobación automatizada de esos riesgos, no una garantía de ausencia de datos sensibles. El informe
queda en `.runtime/space-publication/audit.json`.

Publicar es una **acción externa que requiere autorización explícita cada vez**. El token de `.env` debe
pertenecer a `jonyglez` y poder escribir en el Space.

```powershell
uv run --env-file .env python scripts/publish_space.py --audit-remote   # revisa lo ya publicado, sin modificar
uv run --env-file .env python scripts/publish_space.py --publish        # publica
```

El script comprueba que el destino sea el Space público estático esperado, audita sus revisiones, sube el
paquete por la API del Hub (crea un commit en el Space, no hace push a GitHub), verifica los hashes de los
archivos publicados y usa la revisión remota como precondición para no pisar cambios concurrentes. No
elimina archivos remotos ajenos al paquete.

Una vez publicado el código, el campo «Código del agente» del envío oficial es
`https://huggingface.co/spaces/jonyglez/huggingface-agents-langgraph/tree/main`.

La demostración interactiva del Studio no está publicada en el Space. Cuando se haga (hito M6), usará datos
sintéticos, nunca preguntas ni respuestas de GAIA.
