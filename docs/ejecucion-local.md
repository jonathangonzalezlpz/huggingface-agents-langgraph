# Ejecución local

El lanzador reúne el servidor local de Qwen y las dos formas de usar el agente: un frontal web local o un flujo de terminal.

## Preparación

Instala las dependencias del proyecto y configura el acceso al dataset GAIA:

```powershell
uv sync --extra multimedia
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

## Frontal web (GAIA Agent Studio)

El modo `frontend` sirve el Studio solo en el equipo local, en [http://127.0.0.1:7860](http://127.0.0.1:7860), que redirige a `/app/`. El lanzador activa el extra `multimedia` en `uv run`, para que sus dependencias sigan disponibles aunque uv sincronice el entorno al arrancar. La primera sincronización puede descargar varias dependencias grandes.

**La interfaz se compila aparte.** El paquete compilado no está en Git. La primera vez, y tras cambiar `frontend/`, ejecuta `.\scripts\build_frontend.ps1` (necesita Node en una versión parcheada y `npm ci`; consulta [frontend-seguridad.md](frontend-seguridad.md)). Sin paquete, `/app` explica cómo construirlo y el lanzador lo avisa.

Secciones:

- **Constructor:** biblioteca de arquitecturas con historial de versiones, editor visual con validación en vivo y guardado de versiones.
- **Ejecuciones:** elige una versión guardada, los ajustes del agente (versión del pipeline, mejoras, modelo, semilla y, en «Avanzado», capacidades, razonamiento, tokens, muestreo y modelo de visión) y una pregunta libre o de GAIA, con descarga del adjunto. Muestra la respuesta y dibuja el recorrido por el grafo con tiempos y errores. Cada ejecución se puede abrir luego en `/runs/<id>`.
- **Experimentos:** baterías de las 20 preguntas de validación y el historial.
- **Sistema:** estado del backend, del modelo, de la GPU y de la memoria del equipo.

### Experimentos y evaluación

Una batería la ejecuta el servidor, así que sigue aunque se cierre la pestaña. Se elige la arquitectura, los ajustes y el número de preguntas (1 a 20). Solo hay una batería a la vez. «Detener» termina la pregunta en curso y se para antes de la siguiente; el servidor no puede interrumpir una pregunta. Un experimento detenido o sin terminar se reanuda desde «Experimentos sin terminar» con su configuración y sus preguntas originales; el servidor lo rechaza si el código cambió desde entonces. Las preguntas son las 20 del registro de referencia V2 (`.runtime/experiments/`); sin él no se puede iniciar una batería.

El selector de modelo muestra los que anuncian `LLM_BASE_URL` y Ollama (`OLLAMA_BASE_URL`) en ese momento. Los modelos de visión adicionales solo aparecen con el modo de modelos exclusivo (`-ModelMode exclusive`); sin él solo está el VLM original.

El historial (`/app/experiments/history`) lista los experimentos guardados en el servidor local, con filtro y orden, y permite abrir cada uno (respuestas, rutas, tiempos, aciertos locales y enlace a su recorrido), borrarlo con confirmación o seleccionar de 2 a 20 y compararlos con una base: exactitud y tiempos por grupo, avisos de comparabilidad (mismas preguntas, mismo código, misma arquitectura) y resultado pregunta por pregunta. Estos registros no se suben al repositorio.

Una batería completa de 20 preguntas se puntúa sola al terminar contra las respuestas del split de validación `2023_level1` de GAIA; en los demás casos hay un botón «Puntuar localmente». Requiere que la cuenta tenga acceso aprobado al dataset y `HF_TOKEN` en `.env`. El evaluador aplica comparación exacta sin distinguir mayúsculas y espacios exteriores; guarda solo el porcentaje y el acierto por `task_id`, y no muestra ni persiste las respuestas de referencia. Este cálculo local no actualiza la clasificación.

La puntuación oficial es independiente. Solo desde el detalle de un experimento completo, con «Enviar al evaluador oficial…»: un diálogo avisa de que se publica en un servicio externo con clasificación pública, pide usuario y enlace al código, muestra qué se enviará y exige confirmar. El servidor envía las respuestas guardadas en el registro (no las del navegador) a `POST /submit` y guarda el veredicto en el experimento. Ejecutar, puntuar localmente o comparar no hace ese envío. Las búsquedas web necesitan acceso a Internet; no requieren una clave adicional.

## Modo terminal

El modo `terminal` pregunta si quieres cargar una pregunta aleatoria o la batería. Para cada tarea muestra el `task_id`, la pregunta, el nombre del adjunto si existe y la respuesta final del grafo. La batería también se procesa secuencialmente. Si una ruta todavía no está implementada, el terminal indica que no se produjo respuesta.

## API del curso

El frontal consulta directamente desde el navegador los endpoints documentados en el [Hands-On de Unit 4](https://huggingface.co/learn/agents-course/unit4/hands-on), cuyo servicio permite el origen local mediante CORS. Así, la carga de preguntas no depende de que el proceso Python local tenga salida a Internet:

- `GET /random-question`: una pregunta aleatoria.
- `GET /questions`: la batería de preguntas.

Los adjuntos se obtienen del repositorio GAIA a través de `huggingface_hub`; no se incluyen en el repositorio del proyecto. Las búsquedas generales usan [DDGS](https://github.com/deedy5/ddgs); las preguntas que mencionan publicaciones también consultan [Europe PMC](https://europepmc.org/RestfulWebService), que puede devolver texto completo de artículos disponibles en acceso abierto. Wikipedia usa la [API de MediaWiki](https://www.mediawiki.org/wiki/API:Search). Estas fuentes requieren conexión a Internet. Europe PMC está especializado en ciencias de la vida y no cubre todos los papers; Wikipedia consulta el contenido actual y no recupera una revisión histórica concreta.

## Estado de los modelos en el frontal

El frontal consulta periodicamente `/api/status` y muestra el estado del backend, del LLM razonador, de la GPU (disponible o no, y su nombre) y de la memoria del equipo; `/api/status` informa además de los tres modelos multimedia: VLM, Whisper y AST. El sondeo usa los endpoints de solo lectura `/health` y `/props` de llama.cpp para distinguir el modelo listo del modelo dormido sin despertarlo. Para cada modelo multimedia se muestra si aun no se ha cargado, esta cargando, en uso, residente en memoria o descargado tras inactividad.

## Ejecución con el pipeline v2

Sincroniza con `uv sync --extra multimedia` y reinicia el servidor para aplicar los cambios de Python y las variables nuevas de `.env.example`. El lanzador sigue siendo `./scripts/start_agent.ps1 -Mode frontend`. Recarga la página para usar los enlaces a trazas y recuperar los experimentos del servidor.

El indicador de GPU comprueba CUDA en PyTorch: VLM y AST la utilizan cuando está disponible; Whisper continúa en CPU. Cada pregunta muestra tiempo total y tiempo de llamadas al LLM. Las trazas JSON incluyen las etapas y sus evidencias; se conservan incluso si falla la pregunta. El historial se copia a `.runtime/experiments/`, excluido de Git, y conserva la copia del navegador. Consulta [pipeline-v2.md](pipeline-v2.md) para las variables, el flujo y la interpretación de las mediciones.
