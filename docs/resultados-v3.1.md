# Evaluación local de modelos V3.1

Grupo: `v31-native-models-20261030-r1`. Puntuaciones locales; sin envíos oficiales.

| Variante | Estado | Aciertos | Media s | Mediana s | P95 s | Errores | Carga total s | Pico VRAM MiB | RAM disponible mínima MiB |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| V3.1 · Modelos · vision | completed (20/20) | 6/20 | 37.3 | 31.5 | 60.5 | 0 | 42.8 | 8560 | 244 |
| V3.1 · Modelos · shared | completed (20/20) | 8/20 | 46.6 | 42.7 | 86.0 | 2 | 10.9 | 8606 | 219 |
| V3.1 · Modelos · large | completed (20/20) | 5/20 | 55.8 | 52.8 | 86.6 | 0 | 78.6 | 13306 | 266 |
| V3.1 · Modelos · specialist | completed (20/20) | 10/20 | 50.4 | 45.4 | 96.0 | 2 | 57.0 | 13241 | 198 |

## Configuración y trazabilidad

Configuración fija entre variantes: sí.

- `4d579663-e552-41ef-be3b-d20192ebf66f`: V3.1 · Modelos · vision. Razonador: `Qwen/Qwen3-8B-GGUF:Q5_K_M`. Visión: `unsloth/Qwen3.5-9B-GGUF:Q5_K_M`. Posiciones acertadas: [1, 3, 5, 12, 14, 20].
  Frente al primer control: gana []; pierde [].
- `2ea1cf78-34a8-4275-97cf-d251ad73f8c6`: V3.1 · Modelos · shared. Razonador: `unsloth/Qwen3.5-9B-GGUF:Q5_K_M`. Visión: `unsloth/Qwen3.5-9B-GGUF:Q5_K_M`. Posiciones acertadas: [1, 5, 6, 7, 10, 12, 14, 15].
  Frente al primer control: gana [6, 7, 10, 15]; pierde [3, 20].
- `349f07b1-15f3-40bc-b70a-d4aeb1b57e2b`: V3.1 · Modelos · large. Razonador: `Qwen/Qwen3-14B-GGUF:Q5_K_M`. Visión: `unsloth/Qwen3.5-9B-GGUF:Q5_K_M`. Posiciones acertadas: [1, 5, 12, 14, 20].
  Frente al primer control: gana []; pierde [3].
- `1ec7d303-963b-485b-a18f-132b15dc49f3`: V3.1 · Modelos · specialist. Razonador: `unsloth/Qwen3.5-9B-GGUF:Q5_K_M`. Visión: `Qwen/Qwen3-VL-8B-Instruct-GGUF:Q4_K_M`. Posiciones acertadas: [1, 5, 6, 7, 8, 10, 12, 14, 15, 20].
  Frente al primer control: gana [6, 7, 8, 10, 15]; pierde [3].

Hashes de código: 1; conjuntos de entrada: 1.

La carga de modelos está incluida en los tiempos de las preguntas y llamadas LLM. Se informa también por separado. El pico de VRAM es el máximo muestreado a 1 Hz del dispositivo completo, incluido escritorio, otros procesos y el modelo anterior durante el cambio; no es el máximo absoluto ni memoria exclusiva del agente. La RAM disponible corresponde al sistema.
La media y percentiles incluyen también preguntas con error. No equivalen a latencia de respuestas correctas ni a tiempo de kernel.

Una pasada por variante no demuestra significación estadística. Las fuentes web y cachés de descargas pueden variar con el orden. No se reutilizan respuestas.

El control contemporáneo mantiene la misma receta V3.1 que los candidatos. No es una reproducción de la V2 histórica ni de la V3 conjunta. Véase [seleccion-modelos-v3.1.md](seleccion-modelos-v3.1.md).
