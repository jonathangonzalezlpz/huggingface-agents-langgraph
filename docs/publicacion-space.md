# Publicación del portfolio en Hugging Face

El Space `jonyglez/huggingface-agents-langgraph` es una presentación estática del proyecto y de su autor, Jonathan González López. Incluye un enlace a su perfil de LinkedIn y acceso al código y a las instrucciones de ejecución. El agente, el panel de experimentos y los modelos se ejecutan en local. La página pública no llama a servicios del equipo local ni permite ejecutar inferencias.

La configuración del Space está en el bloque YAML del README principal: `sdk: static`, `app_file: space/index.html` y `license: mit`. La página es autocontenida, responsive y no incorpora fuentes externas, analítica ni llamadas de red automáticas. El código original del proyecto se distribuye bajo MIT; las dependencias, modelos y datasets mantienen sus propias condiciones.

## Preparación y auditoría

Desde la raíz del repositorio:

```powershell
uv run --env-file .env python scripts/publish_space.py
```

Por defecto solo prepara y audita el listado de publicación. Utiliza los archivos fuente versionados y una lista explícita de nuevos archivos de presentación. Excluye las instrucciones locales de desarrollo, `.git`, `.env`, entornos, cachés, modelos descargados, trazas y resultados de experimentos. La plantilla `.env.example` se incluye con credenciales vacías.

La auditoría busca patrones de tokens, claves privadas, credenciales en URLs y rutas personales de sistema de archivos. También compara el paquete con el token configurado, sin imprimir su valor. Es una comprobación automatizada orientada a estos riesgos; no demuestra la ausencia de cualquier posible dato sensible. El informe de archivos y hashes se conserva localmente en `.runtime/space-publication/audit.json`, excluido de Git.

## Publicación autorizada

El token de `.env` debe pertenecer a `jonyglez` y permitir escribir en este Space. No se añade al paquete ni al código HTML. Para revisar también las versiones ya publicadas, sin modificarlas:

```powershell
uv run --env-file .env python scripts/publish_space.py --audit-remote
```

Para publicar, una vez autorizado el envío:

```powershell
uv run --env-file .env python scripts/publish_space.py --publish
```

El script comprueba que el destino sea el Space público estático esperado y audita sus revisiones y versiones de archivos. Si detecta contenido sospechoso se detiene para revisión. Sube el paquete explícito mediante la API del Hub, sin transferir el historial Git local, y verifica los hashes de todos los archivos publicados. La revisión remota inicial se usa como precondición del commit para evitar sobrescribir modificaciones concurrentes. No elimina archivos remotos ajenos al paquete ni modifica ramas del repositorio local.

Publicar mediante la API crea un commit en el Space. No crea un commit Git local ni hace push al remoto de GitHub. Las publicaciones deben mantener una correspondencia documentada con la versión del pipeline que generó las respuestas evaluadas.

## Enlace para el evaluador del curso

Cuando el código esté publicado, el campo «Código del agente» del panel local es:

```text
https://huggingface.co/spaces/jonyglez/huggingface-agents-langgraph/tree/main
```

El envío de respuestas al evaluador oficial sigue siendo una acción independiente de la publicación del código. La página estática no incluye las respuestas correctas del benchmark, resultados privados ni el historial local de experimentos.
