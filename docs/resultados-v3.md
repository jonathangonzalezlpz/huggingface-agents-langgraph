# Evaluación de componentes V3

Grupo: `v3-ablation-20261030`. Todas las puntuaciones de esta serie son locales; no se han realizado envíos oficiales.

La referencia V2 histórica conserva 6/20 (30 %) y 47,3 segundos de media. Las variantes se comparan también con un control V2 contemporáneo.

| Variante | Estado | Aciertos | Media (s) | Mediana (s) | P95 (s) | Errores técnicos |
|---|---|---:|---:|---:|---:|---:|
| V2 · Control repetido | completed | 5/20 | 49.6 | 51.7 | 75.9 | 1 |
| V3 · Solo reasoning_control | completed | 4/20 | 31.6 | 30.2 | 48.3 | 1 |
| V3 · Solo answer_contract | completed | 5/20 | 47.8 | 43.3 | 86.9 | 2 |
| V3 · Solo web_sources | completed | 3/20 | 45.0 | 43.6 | 78.7 | 1 |
| V3 · Solo spreadsheet_tools | completed | 4/20 | 49.2 | 48.1 | 73.1 | 1 |
| V3 · Solo multimedia_tools | completed | 4/20 | 45.0 | 36.8 | 75.4 | 2 |
| V3 · Solo calculation_tools | completed | 6/20 | 42.4 | 43.9 | 75.4 | 2 |
| V3 · Completo | completed | 4/20 | 32.8 | 28.1 | 47.5 | 3 |

## Comparación por pregunta frente al control

Los números identifican el orden de las veinte preguntas conservadas. No se publican preguntas, respuestas de referencia ni credenciales.

### V3 · Solo reasoning_control

Experimento: `df882809-1979-4e7b-8f19-4e5307d50b82`.

Aciertos ganados: ninguno medido. Aciertos perdidos: [5]. Entradas diferentes: ninguna.

Llamadas LLM: 102; truncamientos: 2; tokens de salida comunicados: 18054.

Etapas con mayor tiempo acumulado: `reasoning` 413.3 s; `review` 93.2 s; `research_action` 55.1 s.

### V3 · Solo answer_contract

Experimento: `a074a85a-ccbb-46c6-b6f3-302505523c01`.

Aciertos ganados: [14]. Aciertos perdidos: [1]. Entradas diferentes: ninguna.

Llamadas LLM: 107; truncamientos: 7; tokens de salida comunicados: 30993.

Etapas con mayor tiempo acumulado: `reasoning` 724.2 s; `review` 104.5 s; `research_action` 53.5 s.

### V3 · Solo web_sources

Experimento: `c0e3471d-f5b0-4516-92ee-36e72f48a8a1`.

Aciertos ganados: ninguno medido. Aciertos perdidos: [1, 5]. Entradas diferentes: ninguna.

Llamadas LLM: 114; truncamientos: 6; tokens de salida comunicados: 27344.

Etapas con mayor tiempo acumulado: `reasoning` 629.3 s; `review` 117.7 s; `research_action` 70.4 s.

### V3 · Solo spreadsheet_tools

Experimento: `57f8e96b-bf11-4b18-87ea-ce6b1ad47916`.

Aciertos ganados: [19]. Aciertos perdidos: [12, 13]. Entradas diferentes: ninguna.

Llamadas LLM: 105; truncamientos: 4; tokens de salida comunicados: 30004.

Etapas con mayor tiempo acumulado: `reasoning` 638.0 s; `review` 96.6 s; `spreadsheet_processing` 74.1 s.

### V3 · Solo multimedia_tools

Experimento: `2e7e0c94-4841-4a1e-b0e3-a0427bd68959`.

Aciertos ganados: ninguno medido. Aciertos perdidos: [1]. Entradas diferentes: ninguna.

Llamadas LLM: 103; truncamientos: 4; tokens de salida comunicados: 28234.

Etapas con mayor tiempo acumulado: `reasoning` 658.2 s; `review` 88.4 s; `multimedia_processing` 48.2 s.

### V3 · Solo calculation_tools

Experimento: `6cfe1211-4372-40c4-8282-c49fbf6d57ed`.

Aciertos ganados: [3, 15]. Aciertos perdidos: [1]. Entradas diferentes: ninguna.

Llamadas LLM: 106; truncamientos: 4; tokens de salida comunicados: 25459.

Etapas con mayor tiempo acumulado: `reasoning` 562.8 s; `review` 118.1 s; `research_action` 54.7 s.

### V3 · Completo

Experimento: `546d0085-d7a0-4724-8435-0baea9ea996e`.

Aciertos ganados: [6, 14]. Aciertos perdidos: [1, 13, 20]. Entradas diferentes: ninguna.

Llamadas LLM: 98; truncamientos: 2; tokens de salida comunicados: 17074.

Etapas con mayor tiempo acumulado: `reasoning` 333.6 s; `review` 155.1 s; `research_action` 68.1 s.

## Condiciones y límites

Hashes de código presentes: 1. Conjuntos de entrada presentes: 1.

Se conserva el mismo modelo y capacidades y se ejecutan las variantes en serie. Los pesos y adjuntos pueden estar en caché; no se reutilizan respuestas de otra variante. El razonamiento usa muestreo y las fuentes externas pueden cambiar. Una repetición por variante no demuestra significación estadística ni permite separar todo el efecto del orden y las cachés.

Los cambios de nombre no alteran la configuración ni respuestas de la referencia histórica. Las trazas y respuestas completas permanecen en el historial local del panel.

La interpretación y las decisiones de cierre están en [evolucion-pipeline.md](evolucion-pipeline.md).
