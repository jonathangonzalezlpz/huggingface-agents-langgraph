# Ejecución local

El lanzador reúne el servidor local de Qwen y las dos formas de usar el agente: un frontal web local o un flujo de terminal.

## Preparación

Instala las dependencias del proyecto y configura el acceso al dataset GAIA:

```powershell
uv sync
Copy-Item .env.example .env
```

Añade un token de lectura de Hugging Face a `HF_TOKEN` en `.env`. La cuenta debe tener acceso al dataset GAIA. `.env` está excluido de Git.

El comando `llama` de `llama.cpp` debe estar instalado. El lanzador carga por defecto `Qwen/Qwen3-8B-GGUF:Q5_K_M` y expone la API compatible con OpenAI en `127.0.0.1:8080`.

## Iniciar el sistema

Para elegir el modo de interacción al arrancar:

```powershell
.\scripts\start_agent.ps1
```

También puedes seleccionar el modo como parámetro:

```powershell
.\scripts\start_agent.ps1 -Mode frontend
.\scripts\start_agent.ps1 -Mode terminal
```

El lanzador consulta `/health` en el puerto configurado. Si Qwen ya responde, lo reutiliza; si no, inicia `start_local_llm.ps1` como proceso oculto y espera hasta diez minutos a que el modelo esté listo. La primera ejecución puede descargar el modelo. La salida del servidor se guarda en `%TEMP%\huggingface-agents-langgraph-llm.stdout.log` y `...-llm.stderr.log`.

Al iniciar el servidor se puede cambiar el modelo, el host, el puerto, el tiempo de inactividad y el plazo de arranque:

```powershell
.\scripts\start_agent.ps1 -Mode frontend -Model "Qwen/Qwen3-8B-GGUF:Q5_K_M" -Port 8080 -SleepIdleSeconds 600
```

Los parámetros disponibles son `Model`, `HostAddress`, `Port`, `SleepIdleSeconds` y `StartupTimeoutSeconds`. Si se usa otro puerto, ajusta también `LLM_BASE_URL` en `.env`. El servidor de Qwen permanece activo al cerrar la interfaz; tras el periodo de inactividad configurado, `llama.cpp` descarga el modelo de memoria.

## Frontal web

El modo `frontend` sirve la interfaz solo en el equipo local, en [http://127.0.0.1:7860](http://127.0.0.1:7860). Usa la API del curso para cargar una pregunta aleatoria con `GET /random-question` o la batería con `GET /questions`.

Cada pregunta aparece en una tarjeta con su `task_id`, el texto y si incluye un adjunto. Si lo tiene, el botón de descarga obtiene el archivo desde el dataset GAIA usando `task_id`. La tarjeta muestra el estado del procesamiento y `submitted_answer` al terminar. En la batería, el botón de procesamiento recorre las preguntas secuencialmente y actualiza el progreso.

El frontal no envía respuestas a `POST /submit`. Ahora mismo la rama `.py` es la única que produce respuestas; las otras rutas se muestran como no implementadas.

## Modo terminal

El modo `terminal` pregunta si quieres cargar una pregunta aleatoria o la batería. Para cada tarea muestra el `task_id`, la pregunta, el nombre del adjunto si existe y la respuesta final del grafo. La batería también se procesa secuencialmente. Si una ruta todavía no está implementada, el terminal indica que no se produjo respuesta.

## API del curso

El proyecto usa los endpoints documentados en el [Hands-On de Unit 4](https://huggingface.co/learn/agents-course/unit4/hands-on):

- `GET /random-question`: una pregunta aleatoria.
- `GET /questions`: la batería de preguntas.

Los adjuntos se obtienen del repositorio GAIA a través de `huggingface_hub`; no se incluyen en el repositorio del proyecto.
