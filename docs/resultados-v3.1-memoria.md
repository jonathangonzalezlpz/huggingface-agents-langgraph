# Evaluación local de modelos V3.1

Grupo: `v31-cache512-20261030`. Puntuaciones locales; sin envíos oficiales.

| Variante | Estado | Aciertos | Media s | Mediana s | P95 s | Errores | Carga total s | Pico VRAM MiB | RAM disponible mínima MiB |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| V3.1 - Cache 512 MiB · shared | completed (20/20) | 9/20 | 45.9 | 40.7 | 86.1 | 2 | 12.7 | 8468 | 1733 |
| V3.1 - Cache 512 MiB · precision | completed (20/20) | 8/20 | 58.6 | 54.5 | 93.6 | 4 | 16.5 | 10907 | 206 |

## Configuración y trazabilidad

Configuración fija entre variantes: sí.

- `e714beff-1035-4607-9228-47b36e4224b6`: V3.1 - Cache 512 MiB · shared. Razonador: `unsloth/Qwen3.5-9B-GGUF:Q5_K_M`. Visión: `unsloth/Qwen3.5-9B-GGUF:Q5_K_M`. Posiciones acertadas: [1, 5, 6, 7, 10, 11, 12, 14, 20].
  Frente al primer control: gana []; pierde [].
- `ed248734-ca8d-47e1-87c6-2901523bd601`: V3.1 - Cache 512 MiB · precision. Razonador: `unsloth/Qwen3.5-9B-GGUF:Q8_0`. Visión: `unsloth/Qwen3.5-9B-GGUF:Q8_0`. Posiciones acertadas: [1, 5, 6, 7, 10, 12, 14, 20].
  Frente al primer control: gana []; pierde [11].

Hashes de código: 1; conjuntos de entrada: 1.

La carga de modelos está incluida en los tiempos de las preguntas y llamadas LLM. Se informa también por separado. El pico de VRAM es el máximo muestreado a 1 Hz del dispositivo completo, incluido escritorio, otros procesos y el modelo anterior durante el cambio; no es el máximo absoluto ni memoria exclusiva del agente. La RAM disponible corresponde al sistema.
La media y percentiles incluyen también preguntas con error. No equivalen a latencia de respuestas correctas ni a tiempo de kernel.

Una pasada por variante no demuestra significación estadística. Las fuentes web y cachés de descargas pueden variar con el orden. No se reutilizan respuestas.

El control contemporáneo mantiene la misma receta V3.1 que los candidatos. No es una reproducción de la V2 histórica ni de la V3 conjunta. Véase [seleccion-modelos-v3.1.md](seleccion-modelos-v3.1.md).
