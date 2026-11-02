# Reestructuración del backend

## Por qué

El proyecto nació como la práctica reducida de un curso y se organizó como un monolito sencillo: unos
cuarenta módulos planos en una sola carpeta. Después creció en alcance (experimentos, constructor
visual, baterías, comparación) y en idea (una plataforma para aprender a construir agentes y jugar con
el determinismo y el razonamiento). Esa complejidad pide más orden y más legibilidad. El frontend ya
se organizó así; el backend, no.

## Qué buscamos

**Arquitectura hexagonal, muy modular**, igual que el frontend: lo importante (reglas y datos) no
depende de lo accesorio (modelos, red, ficheros, HTTP). Las dependencias apuntan siempre hacia dentro.

| Capa | Contiene |
|---|---|
| `domain` | reglas y datos puros: estado, configuración de experimento, comparación, métricas |
| `application` | casos de uso: ejecutar, baterías, puntuar, guardar arquitecturas |
| `adapters` | cliente del LLM, ficheros de `.runtime`, seguimiento de recursos |
| `studio` | componentes del constructor: roles de LLM y herramientas |
| `api` | HTTP |
| `pipeline` | los nodos de la V3.1 |
| `graph_definition` | la capa declarativa (ya existe y es el modelo a seguir) |

Es un esquema objetivo: los nombres definitivos se confirman en cada fase.

**Convenciones de código limpio**, vigiladas por herramientas y no solo por costumbre:
- Nombres que dicen qué hace cada función y una descripción breve de una línea.
- Líneas de hasta 88 caracteres (Ruff, desde el principio).
- Funciones cortas y poco ramificadas (complejidad y tamaño limitados por Ruff y ESLint).
- Ficheros de menos de unas 450 líneas, y un módulo por cada razón de cambio.
- Más segmentación: carpetas por rol en lugar de una carpeta plana.

## Cómo lo aplicamos

Poco a poco, con revisión de los tests y de la funcionalidad previa en cada paso, para no romper nada y
dejar una base sólida.

| Fase | Qué hace |
|---|---|
| F0 | Barandillas: un test que fija las dependencias entre módulos y límites de complejidad y tamaño con una línea base. Solo pueden reducirse |
| F1 | Ordenar lo añadido en los últimos hitos: dividir `registry.py`, `web_app.py`, `architecture_store.py`, `wire.ts` y las páginas más largas |
| F2 | Mover el backend a su estructura (carpetas por rol; sin puertos formales, las reglas de `tests/test_architecture.py` fijan quién puede importar a quién). Toca los imports del runtime V3.1, sin cambiar su comportamiento |
| F3 | Trocear las funciones largas de la V3.1, un commit por módulo y con tests de caracterización antes |

Reglas de cada paso:
- Los tests y las comprobaciones pasan antes y después; no se avanza si algo falla.
- Un cambio por commit, con movimientos hechos con `git mv` para conservar el historial.
- Sin cambios de comportamiento: la V3.1 sigue pasando sus tests de equivalencia y sus resultados.
- Las barandillas solo se estrechan: lo nuevo respeta los límites y la línea base solo disminuye.
- Cada fase termina con una parada para revisión; las que tocan el runtime V3.1 requieren autorización
  expresa.

Nota: mover o editar código cambia la identidad de código (`source_identity`) de los experimentos
nuevos, como ya ocurre con cualquier cambio. La referencia sigue en la etiqueta `pipeline-v3.1.0`.

El estado de cada fase está en [ROADMAP_V4.md](ROADMAP_V4.md), sección R.
