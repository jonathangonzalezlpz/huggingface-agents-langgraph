# Selección de modelos para V3.1

## Objetivo y evidencia local

La selección se realiza el 30 de octubre de 2026 y separa tres tipos de evidencia:
resultados publicados por los autores, tamaño de los artefactos cuantizados y
mediciones del sistema local. Ninguno sustituye a los otros dos.

V3 termina con 4/20 aciertos en la combinación completa y 32,8 segundos por pregunta.
El control contemporáneo V2 obtiene 5/20 y 49,6 segundos. La referencia V2 histórica
conserva 6/20. El detalle está en [resultados-v3.md](resultados-v3.md).
Las trazas muestran problemas de percepción visual, planificación, cumplimiento
del formato y truncamientos. Aumentar el modelo no garantiza corregirlos todos.

## Hardware medido

| Recurso | Configuración observada |
|---|---|
| GPU | NVIDIA GeForce RTX 4060 Ti |
| VRAM total | 16380 MiB |
| VRAM ocupada sin modelo residente al medir | 1151 MiB |
| CPU | Intel Core i5-12400F, 6 núcleos y 12 hilos |
| RAM física | 15,8 GiB |
| Motor | llama.cpp 0.5.0-dev, build 11382, commit `11fe02151` |

La RAM disponible no permite asumir que un modelo que no quepa en GPU pueda
descargarse a CPU sin afectar la latencia. El proceso del agente, el sistema
operativo y las cachés también necesitan memoria. Se prioriza mantener las capas
de inferencia en GPU y medir cualquier offload real, en lugar de seleccionar el
modelo con más parámetros que simplemente arranque.

## Candidatos y fundamento

### Qwen3.5-9B: candidato principal para texto y visión

La ficha oficial publica IFEval 91,5, BFCL-V4 66,1, OCRBench 89,2, CountBench 97,2
y VideoMME sin subtítulos 78,4. Cubren seguimiento de instrucciones, herramientas,
lectura visual, conteo y vídeo, capacidades relacionadas con los fallos observados.
Son resultados del autor; no son resultados GAIA de este proyecto ni garantizan
esos valores tras cuantizar. [Ficha oficial y protocolos](https://huggingface.co/Qwen/Qwen3.5-9B).

Su arquitectura combina capas de atención lineal y completa en proporción 3:1 y
admite texto, imagen y vídeo. Es pertinente ensayar la misma instancia en los dos
roles: podría evitar cambios de modelo y reducir la necesidad de mantener dos
backbones residentes. La memoria de estado recurrente, visión y contexto debe
medirse igualmente. [Documentación de arquitectura](https://huggingface.co/docs/transformers/main/model_doc/qwen3_5).

Se selecciona inicialmente Q5_K_M. El artefacto Unsloth ocupa unos 6,58 GB y el
proyector F16 unos 918 MB; Q4_K_M ocupa unos 5,68 GB. La cuantización es de un
distribuidor distinto del autor original. Se registrarán repositorio y revisión.
Q4 queda como comparación de memoria/velocidad si la calidad local lo permite.
[Archivos del cuantizador](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/tree/main).

Tras revisar la caché RAM del motor, se añade un contraste Q8_0 del mismo 9B:
el archivo publicado tiene 9527502048 bytes, aproximadamente 9,53 GB, con el
mismo proyector BF16. Su presupuesto estimado cabe en GPU, pendiente de medir
la ejecución completa. La hipótesis es reducir error de cuantización; no se
presupone una mejora de exact match ni mayor velocidad. Se repetirá Q5 con la
misma caché acotada antes de comparar Q8, evitando mezclar ambos factores.

### Qwen3-14B: contraste de mayor tamaño dentro de la familia anterior

Permite comparar un razonador denso de mayor tamaño con el 8B original y con una
generación posterior de 9B. El reporte de Qwen3 evalúa instrucciones, razonamiento
y herramientas, diferenciando modos de pensamiento. BFCL v3 y BFCL v4 no deben
compararse como si fueran una misma prueba. El reporte usa además condiciones
de contexto y generación distintas de las de este equipo.
[Reporte técnico Qwen3](https://arxiv.org/html/2505.09388v1).

En ese reporte, con pensamiento, 8B/14B obtienen respectivamente IFEval 85,0/85,4
y BFCL v3 68,1/70,4. En MATH-500 son 97,4/96,8: el mayor no gana en todo.
Esto justifica incluir 14B como contraste, no presumir su superioridad.
[Tablas 15 y 17 del reporte](https://arxiv.org/html/2505.09388v1).

Q5_K_M ocupa aproximadamente 10,5 GB; Q4_K_M, 9 GB. Es un candidato viable en
16 GB de VRAM si se acotan contexto, concurrencia y memoria de trabajo. Se validará
con carga exclusiva y se comprobará que no haya offload significativo. Que sus
pesos quepan no demuestra que sea más rápido ni más preciso que Qwen3.5-9B.
[GGUF oficial Qwen3-14B](https://huggingface.co/Qwen/Qwen3-14B-GGUF/tree/main).

### Qwen3-VL-8B-Instruct: contraste de percepción multimodal

Su reporte evalúa OCR, razonamiento visual, percepción fina, conteo, relaciones
espaciales y vídeo. Es una base más apropiada para contrastar el VLM de 256M que
seleccionar un modelo solo por una puntuación de conocimiento textual. Se usará
la variante Instruct; no se le atribuirán resultados de la variante Thinking.
Los benchmarks no prueban que transcriba correctamente un tablero ni que observe
un máximo global en unos pocos fotogramas.
[Reporte técnico Qwen3-VL](https://arxiv.org/html/2511.21631v1).

El GGUF oficial Q4_K_M ocupa unos 5,03 GB. El proyector F16 añade aproximadamente
1,16 GB, sin contar contexto y buffers de imagen. Se probará como VLM separado,
manteniendo fijo el razonador para poder atribuir los cambios.
[Archivos oficiales Qwen3-VL-8B](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF/tree/main).

### Qué permiten inferir esos benchmarks

| Fallo observado | Evidencia publicada pertinente | Límite de la inferencia |
|---|---|---|
| Formato y restricciones ignoradas | IFEval | No equivale al exact match de estas veinte tareas |
| Selección o uso incorrecto de herramientas | BFCL | El proyecto usa planificación textual; no reproduce el protocolo nativo FC |
| Texto o detalles visuales mal leídos | OCR y pruebas espaciales | No validan reconocimiento exacto de un tablero |
| Conteo y preguntas de vídeo | CountBench y VideoMME | Ocho fotogramas no garantizan observar el máximo de un vídeo |

La selección favorece capacidades relevantes y compatibilidad ya verificada.
No es una búsqueda exhaustiva de todas las familias ni una afirmación de que
estos candidatos sean universalmente los mejores para una GPU de 16 GB.

### Presupuesto de memoria: pesos, contexto y ejecución

El tamaño del archivo no equivale al consumo de VRAM. Hay que añadir proyector,
caché KV, buffers, kernels y escritorio. Para Qwen3-14B, una estimación de la
caché KV en FP16 es `2 × capas × cabezas KV × dimensión × tokens × 2 bytes`.
Con 40 capas, 8 cabezas KV, dimensión 128 y 16384 tokens, resulta **2,5 GiB**.
Es una estimación de esa arquitectura y precisión; no se aplica tal cual al
estado híbrido de Qwen3.5. [Configuración oficial Qwen3-14B](https://huggingface.co/Qwen/Qwen3-14B/raw/main/config.json).

Por eso se empieza con 16K de contexto, una secuencia y un solo modelo residente.
Duplicar contexto aumenta esa parte de la memoria aunque los pesos no cambien.
Reducir la precisión de KV sería otra variable experimental, no una optimización
gratuita que se presuponga equivalente en calidad.

### Por qué no comenzar con 27B/32B

Hay candidatos de 27B con benchmarks publicados superiores en varias capacidades,
pero la variante Qwen3.5-27B Q4_K_M de Bartowski ocupa unos 17,98 GB antes de añadir
el proyector y la memoria de ejecución. La alternativa Q3_K_M ronda 14,82 GB.
El margen real de la GPU y los 15,8 GiB de RAM hacen inadecuado presuponer una
ejecución fluida con offload. Se excluyen de la primera serie; no se concluye que
un 27B más comprimido rinda peor sin medirlo.
[Benchmarks del autor](https://huggingface.co/Qwen/Qwen3.5-27B),
[artefactos del cuantizador](https://huggingface.co/bartowski/Qwen_Qwen3.5-27B-GGUF/tree/main).

## Política de memoria

El motor instalado admite un router con `--models-max 1`: las peticiones se dirigen
por identificador y los modelos se cargan bajo demanda. Se verificará la descarga
del anterior con estados y mediciones de VRAM; el límite no controla otros procesos
CUDA ni el coste de las descargas de archivos. La opción más reciente
`--models-memory-margin` no está disponible en esta instalación.
[Documentación del motor](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md#using-multiple-models).

Se comenzará con una secuencia concurrente y contexto acotado. Después se ajustará
el contexto solo si hay evidencia de que es insuficiente y existe margen de memoria.
No se configurará el contexto máximo anunciado por las fichas como valor inicial.
Los indicadores no deben despertar modelos al consultar su estado.

La ayuda del binario instalado confirma además una caché de prompts en RAM de
hasta **8192 MiB** por instancia (`--cache-ram`). No es la caché KV activa en GPU
estimada anteriormente. Durante las baterías se observó RAM disponible inferior
a 300 MiB y los logs muestran expulsión de entradas de varios cientos de MiB
de la caché. Es una causa candidata de presión de memoria que debe contrastarse,
no una medición aislada de toda la memoria del proceso.

Se plantea una segunda fase con **512 MiB** de caché RAM, manteniendo 16K de
contexto y las mismas entradas y presupuestos. Acotar esa caché puede requerir
recalcular prefijos; no elimina evidencias ni reduce el contexto configurado.
Se medirá su efecto por separado de los cambios de modelo.
[Opciones de caché del motor](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).

## Protocolo de selección local

La configuración de inferencia forma parte del experimento. Qwen recomienda evitar
decodificación voraz en modo de pensamiento y publica recetas de muestreo para
modelos cuantizados. Qwen3.5 no admite el cambio suave de modo mediante texto.
Se conservará una receta histórica, otra común entre candidatos y una por familia,
con parámetros y semilla registrados. Comparar recetas específicas mide modelo
y configuración, no únicamente tamaño del modelo.
[Recomendaciones Qwen3](https://huggingface.co/Qwen/Qwen3-14B-GGUF#best-practices),
[recomendaciones Qwen3.5](https://huggingface.co/Qwen/Qwen3.5-9B#best-practices).

1. Comprobar compatibilidad del GGUF, proyector, plantilla e imágenes con el motor.
2. Medir carga, descarga, recarga y uso de GPU/RAM por separado de la inferencia.
3. Hacer pruebas breves de cumplimiento de formato, cálculo, herramientas y
   percepción, usando entradas distintas de las veinte preguntas cuando sea posible.
4. Mantener fijo el pipeline para contrastar razonadores con el mismo VLM y
   contrastar VLM con el mismo razonador. Registrar todos los modelos y parámetros.
5. Contrastar la pareja separada con Qwen3.5-9B compartido en ambos roles: en ese
   caso no es necesario recargar pesos cuando cambia la modalidad.
6. Ejecutar baterías completas de los candidatos que superen las pruebas técnicas,
   preservando preguntas, respuestas, errores, tiempos y trazas en el panel.
7. Seleccionar por acierto, errores, mediana/P95 y recursos. No dar por ganador al
   modelo más grande ni al que tenga mejor cifra en un benchmark ajeno.

Los benchmarks publicados orientan la selección; emplean sus propias plantillas,
presupuestos de generación, resoluciones y número de fotogramas. No se extrapolan
directamente al modo cuantizado, al muestreo limitado de vídeo ni a esta batería
de veinte tareas. Se documentarán cambios de protocolo y no se usarán etiquetas
de referencia en prompts o herramientas del agente.

## Comprobaciones técnicas realizadas

Se ha probado inferencia real con los tres candidatos en el motor instalado,
además del 8B de referencia. La siguiente tabla corresponde a consultas breves;
no es un benchmark de rendimiento sostenido ni un pico absoluto de memoria.
Incluye el consumo del escritorio. Los modelos se intercambiaron con los archivos
ya descargados; no se vació la caché del sistema operativo.

| Modelo | VRAM observada MiB | Carga observada s | Verificación |
|---|---:|---:|---|
| Qwen3-8B Q5_K_M | 8733 | 9,7 | Texto y formato |
| Qwen3.5-9B Q5_K_M | 8576 | 14,0 | Texto; formas, colores y posiciones en imagen |
| Qwen3-14B Q5_K_M | 13315 | 20,6 | Texto y formato |
| Qwen3-VL-8B-Instruct Q4_K_M | 9088 | 13,1 | Formas, colores y posiciones en imagen |

Los dos modelos visuales identificaron el cuadrado rojo a la izquierda del círculo
azul de una imagen sintética. Qwen3.5 tardó 45,4 s, incluidos 13,1 s de carga, y
Qwen3-VL 29,1 s, incluidos 13,1 s de carga. Las respuestas tuvieron distinta
longitud: esos tiempos no demuestran una ventaja de velocidad universal.
El inventario del servidor mostraba una sola instancia cargada en cada consulta.

La comprobación adicional de Q8_0 confirma texto e imagen con 10875 MiB de VRAM
observados, unos 10,6 GiB, usando la caché RAM acotada a 512 MiB. En consultas
breves quedaron entre 1008 y 1254 MiB de RAM disponibles; con Q5, 3592 MiB al
terminar la consulta de cálculo. Son observaciones del sistema completo, no una
reserva garantizada ni una prueba de estabilidad prolongada.

Con pensamiento activado y presupuesto de 512 tokens, tanto Q5 como Q8 responden
correctamente al cálculo sintético anterior. La respuesta cruda queda conservada
en `.runtime/v31-evaluation/precision-smoke.json`. Esto distingue el efecto del
modo de inferencia de una conclusión sobre la capacidad intrínseca del modelo.

Los logs permiten precisar los proyectores que eligió automáticamente el motor:
**BF16** para Qwen3.5-9B, aproximadamente 922 MB, y **Q8_0** para Qwen3-VL-8B,
aproximadamente 752 MB. Los tamaños F16 anteriores describen alternativas
publicadas, no los proyectores efectivamente usados en estas pruebas.

Los tres razonadores fallaron el cálculo sintético `(17 * 23) - 8` con pensamiento
desactivado. También hubo diferencias de espacios en listas. No se usa esta muestra
de tres prompts como ranking: ilustra por qué se mantienen herramientas exactas y
se evalúan cumplimiento, errores y acierto en el pipeline completo.
Los espacios tras comas no constituyen por sí solos un error semántico: los
indicadores del smoke usan comparación literal, sin representar el score GAIA.

La evidencia técnica está en `.runtime/v31-evaluation/smoke.json`. El manifiesto
local registra revisiones públicas y metadatos de los artefactos, distinguiéndolos
de una auditoría de hashes de los binarios locales. Las revisiones consultadas son:

| Repositorio | Revisión pública observada |
|---|---|
| Qwen/Qwen3-8B-GGUF | `7c41481f57cb95916b40956ab2f0b139b296d974` |
| unsloth/Qwen3.5-9B-GGUF | `3885219b6810b007914f3a7950a8d1b469d598a5` |
| Qwen/Qwen3-14B-GGUF | `530227a7d994db8eca5ab5ced2fb692b614357fd` |
| Qwen/Qwen3-VL-8B-Instruct-GGUF | `f982a07559d4a2f6c8744d840bf6fccab30eea96` |

Posteriormente se completó esa auditoría: los cinco GGUF usados —incluido Q8— y
los dos proyectores efectivos coinciden por SHA-256 con los metadatos públicos.
El registro local `.runtime/v31-evaluation/binary-audit.json` conserva los siete
resultados verificados sin publicar rutas personales ni incluir los pesos en Git.

## Serie comparativa del agente

Hay siete configuraciones disponibles con el mismo pipeline V3.1:

| Variante | Razonador | VLM |
|---|---|---|
| control | Qwen3-8B | SmolVLM original |
| reasoner | Qwen3.5-9B | SmolVLM original |
| vision | Qwen3-8B | Qwen3.5-9B |
| shared | Qwen3.5-9B | Qwen3.5-9B |
| large | Qwen3-14B | Qwen3.5-9B |
| specialist | Qwen3.5-9B | Qwen3-VL-8B |
| precision | Qwen3.5-9B Q8 | Qwen3.5-9B Q8 |

Todas habilitan control de razonamiento, contrato de respuesta, selección de
modalidad multimedia y calculadora; no activan las ampliaciones web/Excel que
regresaron en la serie V3. Presupuestos: 512 tokens de pensamiento y 1024 de
solución; receta común, semilla 42, límite de pregunta 360 s y de llamada 180 s.
No se mezclan estos resultados con los de la V3 conjunta anterior.

La política exclusiva se aplica a los modelos nativos de llama.cpp. El VLM original
y AST de Transformers permanecen en CPU en este modo para evitar reservas CUDA
ajenas al router; Whisper conserva CPU/int8. El contraste del VLM original incluye
por tanto ese cambio de despliegue y no aísla únicamente pesos. Para comparar
razonadores se mantiene idéntico VLM y política; para comparar los dos VLM nuevos
se mantiene Qwen3.5-9B como razonador. La referencia histórica V2 se conserva.

El piloto con el VLM antiguo en CPU se interrumpió tras la primera respuesta: la
RAM disponible cayó a unos 500 MiB y la inferencia visual superó el presupuesto
previsto sin recuperar el control a tiempo. No se puntúa ni se presenta como una
batería completada. Esta observación impide considerar fluido un despliegue solo
porque los pesos quepan en VRAM.

La serie principal se limita por ello a `vision`, `shared`, `large` y `specialist`,
en procesos Python separados para liberar las bibliotecas y modelos CPU de cada
variante. `vision` es el control contemporáneo: conserva el razonador 8B y fija
el VLM nativo Qwen3.5. La comparación con SmolVLM queda limitada al antecedente
histórico y al piloto, no permite atribuir una ganancia únicamente a sus pesos.
También se conservó un piloto interrumpido por incompatibilidad de la API de
carga con una instancia dormida; ese problema se corrigió antes de congelar la
serie principal y está cubierto por pruebas automatizadas.

Comando de la serie principal, con la configuración local de límites indicada:

```powershell
uv run --extra multimedia --env-file .env --env-file .runtime/v31.env python -m huggingface_agents_langgraph.model_trials evaluate --group-id v31-native-models-20261030-r1
```

Las respuestas se guardan por pregunta en el panel y las etiquetas se consultan
solo al finalizar para puntuar. Se conserva una copia del código evaluado en
`.runtime/v31-evaluation/source-frozen.zip`, identificada por su manifiesto.
El informe agregado se genera con `scripts/analyze_model_trials.py` y separa
aciertos, errores, tiempo total, carga de modelos, VRAM muestreada y RAM disponible.

La segunda fase repite el modelo compartido Q5 con caché de 512 MiB y después
ejecuta Q8 con la misma política. No cambia el grafo, las herramientas, sus prompts,
la semilla ni los presupuestos de tokens. El catálogo de modelos, el arranque y
la interfaz tienen otra copia de código identificada por su manifiesto; no se
mezclan hashes entre fases. El grupo es `v31-cache512-20261030` y su configuración
se identifica expresamente en los nombres del panel.

## Resultado y decisión tras medir

Se completaron seis baterías, 120 ejecuciones de preguntas. Todas usan el mismo
conjunto conservado de veinte tareas. Las puntuaciones son locales; no se envió
ninguna de estas pasadas al leaderboard.

| Razonador / visión | Caché RAM MiB | Aciertos | Media s | Errores de ejecución o validación |
|---|---:|---:|---:|---:|
| Qwen3-8B / Qwen3.5-9B Q5 | 8192 | 6/20 | 37,3 | 0 |
| Qwen3.5-9B Q5 compartido | 8192 | 8/20 | 46,6 | 2 |
| Qwen3-14B / Qwen3.5-9B Q5 | 8192 | 5/20 | 55,8 | 0 |
| Qwen3.5-9B Q5 / Qwen3-VL-8B Q4 | 8192 | 10/20 | 50,4 | 2 |
| Qwen3.5-9B Q5 compartido | 512 | 9/20 | 45,9 | 2 |
| Qwen3.5-9B Q8 compartido | 512 | 8/20 | 58,6 | 4 |

Los informes completos están en [resultados-v3.1.md](resultados-v3.1.md) y
[resultados-v3.1-memoria.md](resultados-v3.1-memoria.md). Las trazas y respuestas
por pregunta permanecen en el panel.

La recomendación provisional para este equipo es **Qwen3.5-9B Q5_K_M compartido,
caché RAM de 512 MiB, contexto 16K y una secuencia**. Combina un razonador más
capaz en las pruebas observadas con una sola instancia para texto y visión.
El botón del panel prepara ese perfil; siguen disponibles los otros modelos
y las opciones del pipeline para nuevas comparaciones.

La elección se apoya en estos resultados, además de la literatura:

- El 14B no compensa en la configuración medida: obtiene menos aciertos y tarda
  más que el 9B Q5. No se concluye que sea inferior bajo cualquier presupuesto
  de pensamiento o en otros conjuntos.
- La pareja con VLM dedicado alcanza la mejor pasada, 10/20, pero gana frente
  al modelo compartido las posiciones 8 y 20, ambas de investigación web.
  Ninguna de las dos variantes acierta las tareas visuales 2 y 4. El resultado
  agregado no demuestra una ventaja perceptiva del VLM dedicado ni justifica
  atribuirle esos dos aciertos web.
- Acotar la caché del Q5 eleva el mínimo de RAM disponible de 219 a 1733 MiB
  entre las dos pasadas. El tiempo medio pasa de 46,6 a 45,9 s: no se observa
  una aceleración material. El beneficio demostrado es el margen de RAM.
  El cambio de 8 a 9 aciertos no se atribuye causalmente a la caché.
- Q8 deja un mínimo de 206 MiB de RAM disponible, frente a 1733 MiB con Q5;
  ocupa más VRAM, tarda aproximadamente un 28 % más y no mejora el acierto
  observado. Que quepa en GPU no lo convierte en la opción más conveniente.

El límite que queda visible es también del pipeline: hay revisiones truncadas
en la explicación JSON y respuestas de ajedrez que no superan la validación de
notación. Aumentar precisión o tamaño no elimina esos fallos. Se conservan
sin incorporar soluciones particulares a las preguntas del benchmark.

### Reproducibilidad y alcance de la conclusión

Solo hay una pasada por configuración y las páginas, búsquedas y conexiones
externas pueden variar. Una semilla fija no garantiza identidad numérica entre
modelos, procesos y reutilizaciones de prefijos. Tampoco se vacía la caché del
sistema operativo. Los resultados describen estas ejecuciones, sin demostrar
significación estadística ni superioridad general en preguntas no vistas.

La primera fase tiene hash de código
`e0d7fd6c11ad521a9f19e6f2233e6c8a6b0ff7c45f48e35d4dc3cd496abc750d`;
la segunda,
`a03046eb90f3b0daad8d4db88ff3e2caf8c4697d46dbf4dbf4fd5dd031c15291`.
Cada grupo conserva un único hash de código y ambos comparten el conjunto de
entrada `c2187e14c4afe9ae77bc2dea7818d5aaf56c9b695b4494dd988dcba4c84aa04c`.

La revisión Git de partida es `5dcd257`, correspondiente a V3; no es un commit
que ya contenga V3.1. Las copias locales `source-frozen.zip` y
`source-cache512.zip`, con sus manifiestos, conservan los bytes medidos. Los
cambios entre fases son de catálogo, arranque, telemetría e interfaz; el grafo,
las herramientas y sus prompts permanecen iguales en esta comparación.
