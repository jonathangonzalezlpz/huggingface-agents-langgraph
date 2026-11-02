# Evaluación y selección de modelos

Qué se midió, cómo, qué resultó y qué se decidió. La arquitectura del agente está en
[pipeline.md](pipeline.md). Todas las puntuaciones son **locales** (split de validación `2023_level1`,
20 tareas, Exact Match); no se ha enviado ninguna de estas pasadas al evaluador oficial. Las preguntas y
respuestas de referencia no se publican; las trazas completas quedan en `.runtime/` (fuera de Git).

## Método

1. Las 20 tareas están congeladas en el registro de la referencia V2. El agente solo recibe
   identificador, pregunta y adjunto; las etiquetas se consultan después, para puntuar.
2. Se cambia un factor cada vez (una mejora, un modelo) y se registra: conjunto de preguntas
   (`task_set_sha256`), hash del código y del lockfile (`source_identity`), configuración, modelos,
   muestreo y semilla.
3. Se comparan aciertos ganados y perdidos por posición, errores técnicos, media, mediana, P95,
   llamadas, truncamientos y recursos. Los errores cuentan en las medias.
4. Cada variante se ejecuta en serie y sin reutilizar respuestas de otra. Un cambio que depende de otra
   capacidad no se presenta como evaluación aislada de esta.

**Límites de todo lo que sigue:** una pasada por variante; fuentes web y cachés cambiantes; la semilla
fija no garantiza identidad numérica. Los resultados describen esas ejecuciones; no demuestran
significación estadística ni superioridad en preguntas no vistas. Nada se corrige con respuestas
específicas del benchmark.

## Serie 1 · V2 y las mejoras de V3

Grupo `v3-ablation-20261030`: ocho baterías (control V2, seis mejoras aisladas y la combinación), 160
respuestas, mismo código y mismas entradas.

| Configuración | Aciertos | Media | Errores técnicos |
|---|---:|---:|---:|
| V2 histórica conservada | 6/20 (30 %) | 47,3 s | 3 |
| V2 control contemporáneo | 5/20 | 49,6 s | 1 |
| V3 solo `reasoning_control` | 4/20 | 31,6 s | 1 |
| V3 solo `answer_contract` | 5/20 | 47,8 s | 2 |
| V3 solo `web_sources` | 3/20 | 45,0 s | 1 |
| V3 solo `spreadsheet_tools` | 4/20 | 49,2 s | 1 |
| V3 solo `multimedia_tools` | 4/20 | 45,0 s | 2 |
| V3 solo `calculation_tools` | 6/20 | 42,4 s | 2 |
| V3 completa | 4/20 | 32,8 s | 3 |

**Decisión.** La combinación reduce un 33,8 % el tiempo medio frente al control, pero pierde un acierto
(dos frente a la referencia histórica). No se promueve V3 completa; V2 sigue siendo el valor por defecto
y V3 queda como alternativa reproducible.

**Hallazgos de las trazas:**

- *Razonamiento:* el control nativo reduce generación y tiempo, pero no demuestra conservar acierto. Los
  dos fallos de truncamiento fatales de V3 completa están en llamadas del revisor (768 tokens), no en la
  resolución.
- *Presentación:* evita errores mecánicos de orden, pero no garantiza exactitud semántica.
- *Fuentes:* conservar páginas completas y permitir relecturas no mejoró la selección ni la
  interpretación de la evidencia; perdió dos aciertos.
- *Excel:* el modelo inventó un filtro de localidad; la validación lo rechazó y pasó a análisis general.
  La recuperación debería corregir el plan de forma acotada antes de recurrir a la aritmética del LLM.
- *Multimedia:* la tarea de diálogo descargó el audio real y la transcripción contenía la respuesta, pero
  el formateador añadió Markdown y falló el Exact Match. Se corrigió la adquisición sin ganar puntuación.
- *Calculadora:* la mejor variante (6/20). Una pasada no demuestra que explique todas las ganancias, porque
  también cambiaron tareas que no usan las operaciones nuevas.
- Las mejoras combinadas no suman sus ventajas: ganan las tareas 6 y 14 y pierden 1, 13 y 20.

Código medido: hash `c3a98a76…5b0853`, revisión de partida `2692fe7`, copia en
`.runtime/v3-evaluation/source-frozen.zip`.

## Serie 2 · Modelos de V3.1

### Por qué estos candidatos

Tras V3 se quiso separar la capacidad del modelo del efecto del pipeline. Hardware: RTX 4060 Ti de
16380 MiB, i5-12400F, 15,8 GiB de RAM, llama.cpp build 11382. La selección combina tres tipos de
evidencia que no se sustituyen entre sí: benchmarks de los autores, tamaño de los artefactos
cuantizados y mediciones locales.

| Candidato | Motivo | Cuantización y tamaño |
|---|---|---|
| **Qwen3.5-9B** | Texto, imagen y vídeo en un modelo; ficha oficial con IFEval 91,5, BFCL-V4 66,1, OCRBench 89,2, CountBench 97,2, VideoMME 78,4. Misma instancia para los dos roles, sin cambiar pesos. | Q5_K_M ≈ 6,58 GB (+ proyector BF16 ≈ 922 MB); Q8_0 ≈ 9,53 GB como contraste |
| **Qwen3-14B** | Contraste de tamaño en la familia anterior. En su reporte el mayor no gana en todo (MATH-500 97,4 frente a 96,8). | Q5_K_M ≈ 10,5 GB |
| **Qwen3-VL-8B-Instruct** | Percepción multimodal (OCR, conteo, relaciones espaciales, vídeo) como VLM separado. | Q4_K_M ≈ 5,03 GB (+ proyector Q8_0 ≈ 752 MB) |

Se excluyeron 27B/32B: Qwen3.5-27B Q4_K_M ocupa ≈ 17,98 GB antes de proyector y memoria de ejecución, y
con 15,8 GiB de RAM no se puede suponer un offload fluido. Los benchmarks publicados no se extrapolan a
modelos cuantizados, al muestreo limitado de vídeo ni a estas 20 tareas.

Memoria: el tamaño del archivo no es el consumo de VRAM (hay que sumar proyector, caché KV, buffers y
escritorio). Para Qwen3-14B la caché KV en FP16 con 16384 tokens es ≈ 2,5 GiB; no aplica tal cual al
estado híbrido de Qwen3.5. Se empezó con 16K de contexto, una secuencia y un modelo residente.

Comprobaciones previas con inferencia real (consultas breves, escritorio incluido): Qwen3-8B 8733 MiB,
Qwen3.5-9B 8576 MiB, Qwen3-14B 13315 MiB, Qwen3-VL-8B 9088 MiB; Q8_0 10875 MiB. Los tres razonadores
fallaron `(17 * 23) - 8` con el pensamiento desactivado, lo que justifica mantener la calculadora exacta.
Los cinco GGUF y los dos proyectores efectivos coinciden por SHA-256 con los metadatos públicos
(`.runtime/v31-evaluation/binary-audit.json`).

### Resultados

Seis baterías, 120 ejecuciones, mismo código y mismas entradas dentro de cada fase. Las cuatro primeras
con caché RAM de prefijos de 8192 MiB (valor por defecto del motor); las dos últimas con 512 MiB.

| Razonador / visión | Caché RAM | Aciertos | Media | Mediana | P95 | Errores | RAM mínima libre |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen3-8B / Qwen3.5-9B Q5 (control) | 8192 | 6/20 | 37,3 s | 31,5 s | 60,5 s | 0 | 244 MiB |
| Qwen3.5-9B Q5 compartido | 8192 | 8/20 | 46,6 s | 42,7 s | 86,0 s | 2 | 219 MiB |
| Qwen3-14B / Qwen3.5-9B Q5 | 8192 | 5/20 | 55,8 s | 52,8 s | 86,6 s | 0 | 266 MiB |
| Qwen3.5-9B Q5 / Qwen3-VL-8B Q4 | 8192 | 10/20 | 50,4 s | 45,4 s | 96,0 s | 2 | 198 MiB |
| **Qwen3.5-9B Q5 compartido** | **512** | **9/20** | **45,9 s** | 40,7 s | 86,1 s | 2 | **1733 MiB** |
| Qwen3.5-9B Q8 compartido | 512 | 8/20 | 58,6 s | 54,5 s | 93,6 s | 4 | 206 MiB |

Hashes de código: primera fase `e0d7fd6c…c750d`, segunda `a03046eb…15291`; conjunto de entrada
`c2187e14…aa04c`. Revisión de partida `5dcd257`. Copias en `.runtime/v31-evaluation/`.

### Qué se concluye (y qué no)

- **El 14B no compensa** en esta configuración: menos aciertos y más tiempo que el 9B Q5. No significa que
  sea peor con otro presupuesto de pensamiento.
- **El VLM dedicado logra la mejor pasada (10/20), pero no por mejor visión:** sus dos ganancias frente al
  modelo compartido (posiciones 8 y 20) son de investigación web, y ninguna variante acierta las tareas
  visuales 2 y 4.
- **Acotar la caché RAM a 512 MiB** sube el mínimo de RAM libre de 219 a 1733 MiB. El tiempo apenas cambia
  (46,6 → 45,9 s). El beneficio demostrado es el margen de memoria; el paso de 8 a 9 aciertos no se
  atribuye a la caché.
- **Q8 no compensa:** más VRAM, ≈ 28 % más lento, 206 MiB de RAM libre y sin mejora de acierto.
- Un piloto con el VLM original (Transformers, CPU) dejó la RAM libre en ≈ 500 MiB y se interrumpió. No se
  puntúa. Que los pesos quepan en VRAM no hace fluido un despliegue.

### Decisión

Perfil recomendado para este equipo: **Qwen3.5-9B Q5_K_M compartido, caché RAM de 512 MiB, contexto 16K,
una secuencia**. El botón «V3.1 · Compartido Q5» del Studio lo prepara y deja el resto editable. Siguen
sin resolverse: truncamientos del revisor en la explicación JSON, y la validación de notación en las
respuestas de ajedrez.

## Reproducir las series

Entorno de la serie (en `.env`):

```dotenv
MODEL_SERVER_MODE=exclusive
MODEL_LOAD_TIMEOUT_SECONDS=180
MODEL_CACHE_RAM_MIB=512
LLM_TIMEOUT_SECONDS=180
PIPELINE_TIMEOUT_SECONDS=360
```

```powershell
.\scripts\start_agent.ps1 -Mode frontend -ModelMode exclusive
uv run --env-file .env python -m huggingface_agents_langgraph.model_server download   # descarga los candidatos
uv run --extra multimedia --env-file .env python -m huggingface_agents_langgraph.model_trials smoke
uv run --extra multimedia --env-file .env python -m huggingface_agents_langgraph.model_trials evaluate --group-id mi-comparacion
uv run python scripts/analyze_model_trials.py --group-id mi-comparacion --output .runtime/mi-comparacion.md
```

`smoke` comprueba compatibilidad con entradas sintéticas y no es una medida de calidad. `evaluate` usa las
20 tareas, elimina las respuestas de las entradas, puntúa localmente al terminar cada batería y guarda
cada respuesta a medida que termina. Cada variante corre en un proceso separado para liberar los modelos
de CPU. La batería de Q8 requiere `model_server download --models unsloth/Qwen3.5-9B-GGUF:Q8_0`.
