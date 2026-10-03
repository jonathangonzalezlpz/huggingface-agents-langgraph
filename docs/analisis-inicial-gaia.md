
# Objetivo del ejercicio

Construir un sistema que de respuesta a las preguntas GAIA (batería de preguntas para evaluar sistemas IA, uso de distintas herramientas...) Parece que hay distintos niveles de complejidad, se queda en dar respuesta a 20 preguntas del nivel 1 (hay que conseguir más de un 30% de acierto)

## Restricciones

Exact Match en la respuesta, la respuesta debe incluir (nunca mejor dicho) la propia respuesta y nada más, sin florituras ni adornos ni texto adicional.

# Preguntas GAIA

Se proporcionan una serie de endpoint para acceder a las preguntas (https://agents-course-unit4-scoring.hf.space/docs#/default/get_random_question_random_question_get)

De primeras hacemos uso del endpoint GET /random-question, y analizamos un par de preguntar para ver que nos vamos a encontrar:

1. How many studio albums were published by Mercedes Sosa between 2000 and 2009 (included)? You can use the latest 2022 version of english wikipedia.

Parece una pregunta en la que el sistema deberá recurrir a una herramienta de búsqueda web o más en concreto incluso conector de wikipedia. Deberá buscar 'studio albums' de 'Mercedes Sosa' y filtrar a los publicados entre el 2000 y 2009.

Resumen: wikipedia/web + leer wikipedia + extraer studio albums + filtro fechas
Evidencias de entrada: Wikipedia (es una recomendación) asi que por asegurar una vez construída la primera respuesta podría revisarse con búsqueda web de discografía
Indicios de entrada: La query contiene Wikipedia el campo file_name viene vacío

2.
```
{
  "task_id": "f918266a-b3e0-4914-865d-4faa564f1aef",
  "question": "What is the final numeric output from the attached Python code?",
  "Level": "1",
  "file_name": "f918266a-b3e0-4914-865d-4faa564f1aef.py"
}
```

Parece que se nos proporciona un código python y tiene que evaluar su salida numérica. Será necesario contar con un interprete de python y quizás el módulo math.

Resumen: interprete python
Evidencias de entrada: file_name además termina en .py lo que ya nos debe llevar a interprete de python

3.
```
{
  "task_id": "bda648d7-d618-4883-88f4-3466eabd860e",
  "question": "Where were the Vietnamese specimens described by Kuznetzov in Nedoshivina's 2010 paper eventually deposited? Just give me the city name without abbreviations.",
  "Level": "1",
  "file_name": ""
}
```

Se me ocurre que como el fichero no se proporciona necesitará buscar ese paper en la web y si existe tendrá que analizarlo con OCR extrayendo información relevante que irá al llm para intentar dar respuesta a la pregunta (chunks, embedings...)

Creo que hay mecanismos de extracción de info directa que no hay que llegar a algo tipo chunks+embeddings (derivado de la idea de RAG)

Resumen: web + lectura fichero + extraer información
Evidencias de entrada: file_name vacío Abierta

4.
```
{
  "task_id": "7bd855d8-463d-4ed5-93ca-5fe35145f733",
  "question": "The attached Excel file contains the sales of menu items for a local fast-food chain. What were the total sales that the chain made from food (not including drinks)? Express your answer in USD with two decimal places.",
  "Level": "1",
  "file_name": "7bd855d8-463d-4ed5-93ca-5fe35145f733.xlsx"
}
```

Inteprete de documentos excel, tendrá que entenderlo, sumar y excluir filas del total y por último formatear la salida para que se ajuste a USD con 2 decimales. En este caso es un trabajo local en el fichero no necesita búsqueda o ampliación de información.

Resumen: lector excel (estructura tabla) + filtro filas (entender texto filas para poder filtrar drinks) + módulo math + dar formato
Evidencias de entrada: file_name .xlsx

5.

```
{
  "task_id": "4fc2f1ae-8625-45b5-ab34-ad4433bc21f8",
  "question": "Who nominated the only Featured Article on English Wikipedia about a dinosaur that was promoted in November 2016?",
  "Level": "1",
  "file_name": ""
}
```

Conector wikipedia, lector web y extraer la info requerida.

Resumen: wikipedia/web + lector web
Evidencias de entrada: file_name vacío + Wikipedia

## Wikipedia??
Lo he investigado y hay tools específicas de wikipedia, lo que creo que en este caso es que puede venir bien contar directamente con la tool de wikipedia, viendo que en las preguntas de ejemplo un par indicaban Wikipedia explícitamente, ayudaría a ese mayor control y centrar el foco.

## Highligths

Hay preguntas que pueden incluir referencias a fichero, en ese caso necesitaremos utilizar el endpoint /files/{task_id} para obtener dicha información.

Ya podemos apreciar una serie de herramientas requeridas:
- Acceso a búsqueda web (no sé si existe un conector/tool específico de wikipedia)
- Lectura de páginas web
- Lectura de ficheros diferente extensión (pdf, excel)
- Interprete de código
- ...

# Primeras pinceladas de arquitectura

En el curso se presento una serie de nociones relacionadas con la libertad y el control. Según avanzabamos en los framework y complejidad ibamos ganando control y reduciendo libertad en el llm (smolagents==freedom vs LanghGraph >> control)

Apareciendo la idea de Agentes vs Workflow, libertad vs determinismo. Con el primer análisis y viendo que las preguntas necesitan una respuesta lo más concreta y acotada posible, creo que puede venir bien una arquitectura de workflow, en la que los primeros pasos nos lleven a una fuente concreta de forma determinista. Me refiero a que en varias de las preguntas parece observarse que cuando se acompaña de un fichero la respuesta viene en ese fichero o se obtiene de él, por lo que darle grados de libertad permitiría al LLM irse a buscar en otra fuente o ampliar la respuesta con otras fuentes, sib embargo el workflow permitiría deligar los caminos y tirar por el fichero unicamente o por otras (normalmente me imagino que websearch) por ejemplo.

La arquitectura workflow creo que también nos puede ayudar a acotar la forma de la respuesta en relación a limpiar texto y exact match.

```
                 QUESTION
                    │
                    ▼
              deterministic
              preprocessing
                    │
         ┌──────────┴──────────┐
         │                     │
   attached file           no attached file
         │                     │
         ▼                     ▼
   local evidence          agentic research (FREEDOM)
         │                     │
         └──────────┬──────────┘
                    ▼
                evidence (se extrae una información de valor para dar respuesta, si no la hay, incluso quizá habría que volver a darle una vuelta)
                    │
                    ▼
              reasoning (FREEDOM)
                    │
                    ▼
          deterministic output
               formatting
(Todo lo determinista que se pueda, pero vamos a requerir LLM alguien tiene que interpretar que se pide)
                    │
                    ▼
          submitted_answer
```

Una capacidad crítica o crucial del sistema será que sea capaz de seleccionar fuente, es decir en el punto tras el preprocessing deberá ser capaz de determinar si hay un fichero adjunto o no, en caso de que no lo haya tendrá que investigar otras fuentes externas no proporcionadas por la pregunta (me imagino que habrá preguntas que se queden incluso antes, y ya la propia pregunta contenga las entradas de la respuesta. Por ejemplo, una operación matemática donde los operandos vienen como parte de la query)

Para este último claso hablaríamos de algo tipo:
```
no file
  │
  ▼
¿se puede resolver con la información proporcionada? (Razonamiento, no es determinista ya que es dificil de acotar)
  │
 ┌┴────────────┐
 sí            no
 │              │
 ▼              ▼
reasoning      external research
```

## Otras decisioness
### Extensión del fichero
Si viene un fichero este tendrá una extensión y está sería un gran indicativo de por donde seguir:
.py --> Interprete de código (no tiene porque ejecutar, puede ser analizar, calcular...)
.pdf --> lector de documento
...
tengo la duda de si es mejor workflow o llm y que razone que hacer, creo que quizás ambos o que se le indique al llm .py seguramente implique interprete de código, ya que no sé si pueden existir preguntas que busquen confundir. Creo que lo bueno es que no hay elegir que podemos convinar sin malgastar.

Investigando creo que lo mejor es el routing determinista apoyando lo que no sabemos en el llm:
```
                   QUESTION
                      │
                      ▼
         DETERMINISTIC ROUTING
                      │
       ┌──────────────┼──────────────┐──────────────┐
       ▼              ▼              ▼              ▼
     .py            .xlsx          no file         ...
       │              │              │
       ▼              ▼              ▼
      LLM            LLM            LLM
    DECISION       DECISION       DECISION
                                     │
                            ┌────────┴────────┐
                            ▼                 ▼
                     sufficient input     missing info
                            │                 │
                            ▼                 ▼
                         reasoning         research
                                             (open,
                                             certain source for example, wikipedia)
```

LLM decisión será una decisión semántica, ya he decidido de forma determinista que voy a trabajar con un fichero concreto, pero que tengo que hacer con él? necesito algo más? está la evidencia que permite responder ?

# Routing vs Razonamiento

Creo que son los pilares del sistema. Routing en cuanto el camino a seguir, alcanzado un punto y con un mensaje a donde voy; y razonamiento, ahora que tengo una respuesta/información como la utilizo para continuar; y se retroalimentan entre ellas.

En este caso en el que las respuesta ha de contener unicamente la "respuesta" añadiría una última pata de producción/redacción de la misma. Un LLM seguramente dará una respuesta formulada y en este caso hay que devolver lo justo.


# Profundizando en recorrido Pregunta concreta

Tomando como ejemplo:

2.
```
{
  "*task_id*": "f918266a-b3e0-4914-865d-4faa564f1aef",
  "*question*": "What is the final numeric output from the attached Python code?",
  "Level": "1",
  "*file_name*": "f918266a-b3e0-4914-865d-4faa564f1aef.py"
}
```

Tenemos el task_id para la obtención de files si existen (que en este caso sí)
Tenemos la query "question"
Y el nombre del fichero file_name (recordemos que puede venir vacío)

Lo primero al detectar presencia file_name (!= "") procedemos a descarga haciendo uso de /files/{task_id}

> [!warning]
> El endpoint oficial de la Unidad 4 `/files/{task_id}` devuelve actualmente errores 404 para
> las tareas que incluyen archivos adjuntos debido a una incompatibilidad en las rutas
> introducida tras la migración del formato del dataset GAIA.
> Para el desarrollo local, los archivos adjuntos se obtienen directamente desde el dataset
> oficial `gaia-benchmark/GAIA`.

Lo solucionamos con un conector simple para la recuperación de adjuntos. Esto nos lleva a darnos cuenta que la obtención del fichero puede fallar, en ese caso el sistema debería dar respuesta por otras vías, pero indicar que no se pudo obtener el fichero adjunto. En algunos casos la respuesta puede tener sentido, por ejemplo cuando el fichero es un paper y ese paper se puede obtener también de la web y en otras no, por ejemplo análisis de excel concretos que no están públicos, o códigos...

Pero supongamos que obtuvimos ese ficheo (seguramente el path), recordemos .py --> *file_path*

El workflow nos llevará directamente a la rama .py

Analizar código hasta conseguir la evidencia --> *evidence*

Pasar la evidencia al LLM para determinar que sea la respuesta a la pregunta --> *answer*

Normalizar/Limpiar answer --> *final_answer*

Alcanzado este punto, aun no veo ninguna evidencia de pasar al concepto multi-agent visto en el curso. De momento, parece que con un workflow+llm+tools tendríamos un sistema suficiente.

# Diseño incial del Estado - STATE

| Campo | Por que es necesario? | Creado por | Usado por |
|---|---|---|---|
| `task_id` | Identifica la tarea, da acceso a los archivos adjuntos | Dado en la pregunta | Obtención de adjuntos |
| `question` | La query | Dado en la tarea | Creo que todos, es la query principal, me imagino que se arrastrará como contexto |
| `file_name` | la extensión define la ruta | Dado | Router |
| `file_path` | Donde encontrar el fichero, lo utilizará el downloader | Obtenido a partir del task id y el método GET correspondiente (conector propio ante error) en caso de error en obtención actuará también de indicativo de fallo (`Path \| None`, hay `file_name != ""` y `file_path == None` entonces hubo fallo en obtención) |  |
| `route` | Se asocia a la capacidad principal seleccionada (code, document, direct, web, wikipedia...) |  |  |
| `evidence` | Información de valor obtenida de fichero, fuente externa, web... | Tools+LLM | LLM para analizar si es suficiente evidencia y generar la respuesta filtrada y completa |
| `answer_candidate` | Respuesta generada a partir de la evidencia, aplicando filtros, limpiezas y adecuación a la pregunta principal | LLM | LLM |
| `submitted_answer` | Exact match | Normalización, limpieza... | POST `/submit` |

Pero revisando el curso se le puede dar una vuelta más a este estado. Los campos no tienen porque ser tipos básicos (str, int) sino que podemos hablar de estructuras de "Objeto" Por ejemplo, evidence podría tener una estructura:

```
evidence:
[
    {
        content: ...,
        source_type: ...,
        source: ...
    },
    ...
]
```

LLevada a una de las preguntas:
```
[
    {
        content: "Mercedes Sosa released ...",
        source_type: "wikipedia",
        source: "https://en.wikipedia.org/..."
    },
    ...
]
```

Ganamos información que el LLM aprovechará y darán mayor robustez y trazabilidad al sistema, más allá de este caso concreto en el que buscamos una respuesta acotada.

Limpio/Resumido el estado quedaría algo como:
| Campo | Para qué sirve | Creado por | Usado por |
|---|---|---|---|
| `task_id` | Identifica la tarea y permite localizar recursos asociados | Unit 4 | attachment resolver, evaluación |
| `question` | Problema principal que hay que resolver | Unit 4 | routing semántico, tools, reasoning, answer production |
| `file_name` | Indica si se espera adjunto y permite inferir su tipo | Unit 4 | preprocessing/router |
| `file_path` | Ruta local al adjunto cuando se ha podido recuperar | attachment resolver | rama especializada de fichero |
| `route` | Representa la capacidad/ruta seleccionada | router | conditional edges / procesamiento |
| `evidence` | Información recuperada junto con su procedencia | tools/nodes | validación de evidencia y reasoning |
| `answer_candidate` | Conclusión semántica obtenida de la evidencia | reasoning | answer production |
| `submitted_answer` | String final que cumple las restricciones GAIA | answer production | POST `/submit` |

Y ahora que tenemos el estado ya vamos callendo sin querer a un grafo final (arquitectura de Nodo)

## El grafo - Nodos
task_id / question / file_name
              │
              ▼
         preprocessing
              │
      ┌───────┴────────┐
      │                │
file_name != ""     no file
      │                │
      ▼                │
attachment_resolver    │
      │                │
      ▼                │
  file_path            │
      │                │
      └───────┬────────┘
              ▼
            router
              │
              ▼
            route
              │
              ▼
      (conditional edge by type)
              │
              ▼
     evidence acquisition
              │
              ▼
           evidence
              │
              ▼
           reasoning
              │
              ▼
       answer_candidate
              │
              ▼
      answer production
              │
              ▼
      submitted_answer

# STATE - Limpieza en base a uso

Necesitamos saber en concreto que Nodo es el primero en escribir cada propiedad y los siguientes en consumirlo. De la literatura he podido extraer una recomendación, si solo un nodo interactúa con un campo este seguramente se pueda manejar como una variable local y no sea necesario que forme parte del estado.


task_id INPUT-->preprocessing-->attachment_resolver
question INPUT-->preprocessing-->router-->evidence_acquisition-->reasoning-->answer_production (presente en todas las "fases")
file_name INPUT-->preprocessing-->router
file_path attachment_resolver-->router(va también al router, por si no se puede recuperar el archivo y hay que recurrir a la posibilidad de irse a otras fuentes)-->evidence_adquisition
route router
evidence evidence_acquisition-->reasoning
answer_candidate reasoning --> answer_production
submitted_answer answer_production-->POST