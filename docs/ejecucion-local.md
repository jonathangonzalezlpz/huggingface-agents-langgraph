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

## Frontal web

El modo `frontend` sirve la interfaz solo en el equipo local, en [http://127.0.0.1:7860](http://127.0.0.1:7860). El lanzador activa el extra `multimedia` en `uv run`, para que sus dependencias sigan disponibles aunque uv sincronice el entorno al arrancar. La primera sincronización puede descargar varias dependencias grandes. Usa la API del curso para cargar una pregunta aleatoria con `GET /random-question` o la batería con `GET /questions`.

Cada pregunta aparece en una tarjeta con su `task_id`, el texto y si incluye un adjunto. Si lo tiene, el botón de descarga obtiene el archivo desde el dataset GAIA usando `task_id`. La tarjeta muestra el estado del procesamiento y `submitted_answer` al terminar. En la batería, “Lanzar experimento” recorre las preguntas secuencialmente y actualiza el progreso.

### Experimentos y evaluación

Antes de ejecutar la batería se puede nombrar un experimento, seleccionar el modelo razonador, aplicar perfiles rápidos o configurar cada capacidad por separado: código, Excel, documentos/PDF, multimedia y web/Wikipedia. El selector descubre los modelos anunciados por `LLM_BASE_URL` y por Ollama (`OLLAMA_BASE_URL`); Ollama debe estar ejecutándose y puede cargar el modelo seleccionado al usarlo. “Solo directo” fuerza las veinte tareas a pasar del enunciado al razonador. Si se deshabilita la capacidad asociada a un adjunto, el sistema omite su descarga y procesamiento y entrega la pregunta al razonador sin esa evidencia. Cada lanzamiento captura la configuración, incluido el modelo, para que no cambie durante la batería.

Durante la ejecución se puede detener la batería. El agente termina la pregunta que ya está procesando y se para antes de iniciar la siguiente; al reanudar continúa con las preguntas pendientes y conserva el perfil elegido.

Las ejecuciones completas se guardan en el almacenamiento local del navegador con las respuestas, el modelo y las rutas utilizadas. Cada ejecución se puede desplegar para volver a consultar sus preguntas, respuestas, rutas, tiempos y aciertos locales después de recargar el frontal. El historial también permite seleccionar dos o más experimentos y compararlos por `task_id`; marca si el texto de la pregunta es idéntico, distinto o falta en alguna ejecución. Estos registros no se suben al repositorio.

El panel de ejecuciones permite evaluar localmente una batería completa contra las respuestas del split de validación `2023_level1` de GAIA. Requiere que la cuenta tenga acceso aprobado al dataset y `HF_TOKEN` esté configurado en `.env`. El evaluador aplica comparación exacta sin distinguir mayúsculas y espacios exteriores; guarda solo el porcentaje y el indicador de acierto por `task_id` en el navegador. No muestra ni persiste las respuestas de referencia. Este cálculo local no actualiza la clasificación.

La puntuación oficial es independiente. Solo al pulsar “Enviar y calcular score oficial” se envían usuario, código del agente y las veinte respuestas a `POST /submit`; el servicio devuelve el porcentaje y los aciertos sobre el total y actualiza la clasificación pública del curso. Ejecutar, evaluar localmente o comparar experimentos no hace ese envío. Las búsquedas web necesitan acceso a Internet; no requieren una clave adicional.

Para reducir la latencia, el razonador genera directamente la respuesta final en una llamada, en vez de razonar y hacer después una segunda llamada de reformateo. Las clasificaciones breves del router, código y plan Excel limitan su salida y desactivan el modo de pensamiento extendido de Qwen 3. La extracción de hasta tres páginas web se ejecuta en paralelo. En vídeo, los fotogramas se buscan mediante saltos temporales y solo se activa Whisper/AST si la pregunta pide información de audio; las preguntas visuales no transcriben sonido de fondo.

## Modo terminal

El modo `terminal` pregunta si quieres cargar una pregunta aleatoria o la batería. Para cada tarea muestra el `task_id`, la pregunta, el nombre del adjunto si existe y la respuesta final del grafo. La batería también se procesa secuencialmente. Si una ruta todavía no está implementada, el terminal indica que no se produjo respuesta.

## API del curso

El frontal consulta directamente desde el navegador los endpoints documentados en el [Hands-On de Unit 4](https://huggingface.co/learn/agents-course/unit4/hands-on), cuyo servicio permite el origen local mediante CORS. Así, la carga de preguntas no depende de que el proceso Python local tenga salida a Internet:

- `GET /random-question`: una pregunta aleatoria.
- `GET /questions`: la batería de preguntas.

Los adjuntos se obtienen del repositorio GAIA a través de `huggingface_hub`; no se incluyen en el repositorio del proyecto. Las búsquedas generales usan [DDGS](https://github.com/deedy5/ddgs); las preguntas que mencionan publicaciones también consultan [Europe PMC](https://europepmc.org/RestfulWebService), que puede devolver texto completo de artículos disponibles en acceso abierto. Wikipedia usa la [API de MediaWiki](https://www.mediawiki.org/wiki/API:Search). Estas fuentes requieren conexión a Internet. Europe PMC está especializado en ciencias de la vida y no cubre todos los papers; Wikipedia consulta el contenido actual y no recupera una revisión histórica concreta.

## Estado de los modelos en el frontal

El frontal consulta periodicamente `/api/status` y muestra el estado del LLM razonador y de los tres modelos multimedia: VLM, Whisper y AST. El sondeo usa los endpoints de solo lectura `/health` y `/props` de llama.cpp para distinguir el modelo listo del modelo dormido sin despertarlo. Para cada modelo multimedia se muestra si aun no se ha cargado, esta cargando, en uso, residente en memoria o descargado tras inactividad.
