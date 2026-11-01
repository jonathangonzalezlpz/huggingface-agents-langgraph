# Diseño de experiencia — GAIA Agent Studio (V4)

*Visual builder & evaluation lab for GAIA agents.* Borrador revisado: las decisiones de la
sección 17 ya están tomadas. Fija la visión de uso antes de escribir código (M3.0).
Todo lo que se apoya en el backend actual está comprobado contra el código; lo que
requiere cambios en el backend se marca como **[backend]**. Las decisiones que todavía
son tuyas están en la sección final.

## 1. Para quién y para qué

| Perfil | Qué necesita |
|---|---|
| **Tú, investigador-desarrollador** | Probar variantes de arquitectura sin tocar Python, entender por qué una falla y comparar resultados con rigor. |
| **Evaluador de portfolio** (reclutador, compañero técnico) | Entender el proyecto en minutos, ver el constructor funcionando y comprobar que hay criterio de ingeniería. Normalmente sin GPU ni backend. |
| **Usuario futuro del repositorio** | Instalar, abrir y construir su primer agente sin leer el código. |

Tareas principales, en orden de importancia:

1. **Construir o modificar** una arquitectura.
2. **Saber si es válida** y, si no, qué arreglar.
3. **Ejecutarla** con una configuración y ver qué ocurrió.
4. **Comparar** ejecuciones y experimentos con honestidad sobre el ruido.
5. **Volver** a una versión anterior y entender qué cambió.

Un criterio rector: **la interfaz no debe prometer más de lo que el backend demuestra.**
Una advertencia no es un error, una ejecución sola no es una conclusión, y un camino
hasta END no garantiza terminación. El lenguaje y el color deben respetar esas
diferencias.

## 2. Principios de usabilidad y cómo se concretan

| Principio (Nielsen) | Decisión en este producto |
|---|---|
| Visibilidad del estado | Barra de estado permanente: versión, cambios sin guardar, resultado de la última validación, conexión con el backend y con el modelo. |
| Correspondencia con el mundo real | Vocabulario del dominio, no de LangGraph: «componente», «decisión», «rama», «campo del estado». |
| Control y libertad | Deshacer/rehacer ilimitado en la sesión; las versiones guardadas son inmutables, así que «volver» nunca destruye nada. |
| Consistencia | Un único sistema de diseño (tokens, componentes, iconos); mismos verbos y mismos atajos en todas las pantallas. |
| Prevención de errores | Se impide lo que el esquema prohíbe (arista hacia el inicio, segunda salida de un nodo, rama duplicada) antes de que ocurra, con la razón en un tooltip. |
| Reconocer antes que recordar | Paleta con búsqueda y descripciones; el contrato de cada componente a la vista al seleccionarlo. |
| Flexibilidad y eficiencia | Atajos de teclado, paleta de comandos (`Ctrl+K`), duplicar, autodisposición. |
| Diseño minimalista | Divulgación progresiva: el lienzo muestra lo esencial; el detalle vive en el inspector. |
| Ayudar a diagnosticar errores | Cada código del validador tiene mensaje en lenguaje llano, causa y acción sugerida (sección 6). |
| Ayuda y documentación | Estados vacíos con plantillas y un recorrido inicial opcional de tres pasos. |

**Accesibilidad** (objetivo WCAG 2.2 nivel AA):

- Todo el flujo se puede hacer con teclado. Como alternativa al arrastre (criterio 2.5.7),
  «Conectar con…» abre una lista de destinos válidos.
- El color nunca es el único portador de información (1.4.1): estado y categoría llevan
  también icono y texto.
- Contraste de texto 4.5:1 y de componentes de interfaz 3:1 (1.4.3, 1.4.11); objetivos
  táctiles de al menos 24×24 px (2.5.8); foco visible y no tapado (2.4.7, 2.4.11).
- Cambios de estado anunciados a lectores de pantalla (4.1.3), por ejemplo «3 errores, 1
  aviso» tras validar.
- Respeta `prefers-reduced-motion` y `prefers-color-scheme`.
- Los contrastes concretos se comprobarán con una herramienta en M3.0; este documento no
  fija valores de color para no afirmar nada sin medirlo.

## 3. Estructura de la aplicación

Navegación lateral fija, cuatro áreas:

```
┌──────────┬──────────────────────────────────────────────────────────┐
│ ◆ GAIA   │                                                          │
│  Studio  │                 (área de trabajo)                        │
│          │                                                          │
│ ▸ Constructor                                                       │
│ ▸ Ejecuciones                                                       │
│ ▸ Experimentos                                                      │
│ ▸ Sistema     (modelos, estado, preferencias)                       │
│          │                                                          │
│ ● Backend│                                                          │
│ ● Modelo │                                                          │
└──────────┴──────────────────────────────────────────────────────────┘
```

- **Constructor:** biblioteca de arquitecturas y editor. Es la pantalla principal.
- **Ejecuciones:** lanzar una pregunta con una arquitectura y ver el recorrido.
- **Experimentos:** baterías, historial, comparación y puntuación.
- **Sistema:** estado de los modelos, preferencias (tema, idioma) y modo demostración.

## 4. Constructor

### 4.1 Disposición

```
┌ Barra superior ────────────────────────────────────────────────────────────┐
│ gaia_v31 · v3 · a1b2c3d   ● sin guardar   [Deshacer][Rehacer]   [Validar]  │
│                                          [Guardar como versión]  [▶ Ejecutar]│
├ Paleta ───┬ Lienzo ─────────────────────────────────────┬ Inspector ───────┤
│ 🔍 buscar │                                              │ Nodo: router     │
│           │   ┌──────────┐    ┌────────┐                 │ Componente       │
│ ENTRADA   │   │preproces.│───▶│ router │──code──▶ ┌────┐│ router           │
│  ▫ prepro │   └──────────┘    └────────┘          │code││                  │
│  ▫ adjunto│                      │ web              └────┘│ Necesita         │
│ ADQUISIC. │                      ▼                       │  question        │
│  ▫ código │                   ┌──────┐                   │  file_name       │
│  ▫ hoja   │                   │ web  │                   │ Produce          │
│  ▫ doc    │                   └──────┘     [minimapa]    │  route           │
│  ▫ media  │                                              │ Decisión         │
│  ▫ web    │                                              │  route_after_…   │
│ INVESTIG. │                                              │  ● 7 ramas       │
│ RAZONAM.  │                                              │                  │
├ Diagnósticos ──────────────────────────────────────────────────────────────┤
│ ✖ 0 errores   ▲ 4 avisos   ● 1 info          [filtrar]  [ocultar]          │
│ ▲ code_processing necesita «file_path» y no está garantizado en todos…  →  │
└────────────────────────────────────────────────────────────────────────────┘
```

Los paneles se pueden plegar; el lienzo ocupa todo el ancho que quede.

### 4.2 Anatomía de un nodo

Tarjeta con:

- **Título** (el id del nodo, editable) y **subtítulo** con el componente.
- **Icono y franja de categoría** (entrada, adquisición, investigación, razonamiento,
  salida). La categoría se distingue por icono y etiqueta además del color.
- **Insignia «recupera errores»** (escudo) en los nodos de adquisición, porque su
  contrato cambia: no garantizan `evidence`, y el fallo se convierte en una nota en lugar
  de detener la ejecución.
- **Indicador de estado** de la validación: error, aviso o correcto, con icono.
- **Puntos de conexión:** una entrada a la izquierda y una salida a la derecha.

Si el nodo tiene una **decisión** (estrategia de routing), la salida única se convierte
en una **salida por rama**, cada una con su etiqueta (`code`, `web`, `act`, `solve`…).
Una rama sin conectar se dibuja con trazo discontinuo y aviso, porque el validador exige
ramas completas.

### 4.3 Aristas

- **Directa:** línea continua con flecha.
- **Condicional:** una línea por rama, con la etiqueta de la rama sobre el trazo.
- **Ciclo legítimo** (por ejemplo `review ⇄ research_action`): se dibuja normal y el
  diagnóstico `CYCLE_DETECTED` lo explica sin alarmar.

### 4.4 Flujos de edición

| Acción | Cómo |
|---|---|
| Añadir componente | Arrastrar desde la paleta, doble clic en el lienzo (búsqueda rápida) o `Ctrl+K`. |
| Conectar | Arrastrar desde la salida a un nodo; o seleccionar nodo → **Conectar con…** (alternativa accesible). |
| Añadir decisión | Inspector → **Decisión tras este nodo** → elegir estrategia; aparecen sus ramas. |
| Quitar | `Supr`, con deshacer inmediato. Sin diálogo de confirmación, porque deshacer lo cubre. |
| Reordenar | Arrastrar; **Autodisposición** reorganiza en capas de izquierda a derecha. |
| Duplicar | `Ctrl+D`. |

### 4.5 Prevención de errores

Se impide en el momento, con tooltip que explica el motivo:

- Conectar hacia el inicio del grafo.
- Una segunda arista directa (o una directa más una condicional) desde el mismo nodo.
- Dos ramas con la misma etiqueta, o una etiqueta fuera de las que define la estrategia.
- Nombrar un nodo con un id reservado o repetido.

Lo que depende del flujo de datos (campos garantizados, alcanzabilidad, camino a END) **no
se impide**: se diagnostica con el validador del backend, que es la única fuente de
verdad. La interfaz valida con un pequeño retardo tras cada cambio. Así no duplica reglas
semánticas, y las comprobaciones del cliente se limitan a invariantes del esquema.

### 4.6 Biblioteca y versiones

- La arquitectura integrada **V3.1 es de solo lectura**. Un aviso fijo ofrece **Duplicar
  para editar**.
- **Guardar como versión** crea siempre una versión nueva e inmutable; si el contenido no
  cambió, la interfaz lo dice («ya existe como v2») en lugar de fingir un guardado.
- Un panel de **historial** muestra la cadena de versiones (padre → hijo), con el hash
  corto, la fecha y un **resumen de cambios** (nodos y aristas añadidos y quitados),
  calculado en el cliente comparando definiciones.
- La disposición se guarda aparte y no cuenta como cambio de versión (decidido).
- Los borradores sin guardar se conservan localmente y se ofrecen al volver.

## 5. Plantillas y estados vacíos

Al abrir el Constructor sin arquitectura:

1. **Pipeline V3.1** (plantilla integrada, la referencia).
2. **Lineal mínima:** preprocesado → razonamiento → respuesta.
3. **En blanco.**

El estado vacío de cualquier lista explica qué es, cómo se llena y ofrece la acción
principal. Un recorrido inicial de tres pasos (paleta, conexión, validación) es opcional
y se puede descartar para siempre.

## 6. Diagnósticos

Panel inferior, agrupado por gravedad. Cada fila tiene icono, mensaje y un enlace que
**enfoca el nodo o la arista** afectada (el backend ya entrega `node_id`,
`edge_source` y `branch`). Un diagnóstico no resuelto en el lienzo se muestra como
insignia en el nodo.

| Código | Gravedad | Mensaje para el usuario | Acción sugerida |
|---|---|---|---|
| `INVALID_DEFINITION` | Error | La definición no es estructuralmente válida. | Corregir el campo indicado. |
| `UNKNOWN_IMPLEMENTATION` | Error | El nodo usa un componente que no está en el catálogo. | Elegir un componente del catálogo. |
| `UNKNOWN_ROUTING_STRATEGY` | Error | La decisión usa una estrategia que no existe. | Elegir una estrategia registrada. |
| `UNKNOWN_STATE_TYPE` | Error | El tipo de estado no es compatible. | Usar el tipo de estado disponible. |
| `UNKNOWN_STATE_FIELD` | Error | Un contrato menciona un campo que no existe en el estado. | Revisar el catálogo (problema de configuración). |
| `BRANCH_LABELS_MISMATCH` | Error | Las ramas no coinciden con las que define la estrategia (faltan o sobran). | Conectar las ramas que faltan o retirar las sobrantes. |
| `START_EDGE_MISMATCH` | Error | La entrada del grafo apunta a un nodo distinto del inicial. | Usar el nodo inicial como única entrada. |
| `OUTGOING_EDGE_CONFLICT` | Error | El nodo tiene varias salidas; solo se admite una (o una decisión). | Dejar una sola salida o convertirla en decisión. |
| `UNREACHABLE_NODE` | Error | Ningún camino llega a este nodo desde el inicio. | Conectarlo o eliminarlo. |
| `NO_PATH_TO_END` | Error | Desde este nodo no se puede llegar al final. | Añadir un camino al final. |
| `REQUIRED_INPUT_UNAVAILABLE` | Error | El nodo necesita un campo que ningún camino produce. | Añadir antes un componente que lo produzca. |
| `REQUIRED_INPUT_NOT_GUARANTEED` | Aviso | El campo solo existe en algunos caminos. | Revisar si el nodo puede ejecutarse sin él. *(En V3.1 es esperado para `file_path`: solo hay adjunto en algunas tareas.)* |
| `CYCLE_DETECTED` | Info | Hay un ciclo; que termine depende de los presupuestos de ejecución, no se demuestra. | Ninguna; confirmar que los límites son los deseados. |

Reglas de redacción: nunca «inválido» para un aviso; nunca «correcto» para algo que solo
no tiene errores; el aviso esperado de V3.1 lleva una nota explicativa para no
alarmar.

## 7. Inspector

Pestañas, con divulgación progresiva:

- **Nodo:** id, componente, descripción, categoría y el contrato en cuatro bloques
  (entradas requeridas, opcionales, salidas garantizadas, opcionales).
- **Decisión:** estrategia y estado de cada rama.
- **Datos aquí** **[backend]**: qué campos del estado están garantizados y cuáles solo son
  posibles en la entrada de este nodo. Es la forma más directa de entender un aviso. El
  análisis de punto fijo ya lo calcula internamente, pero el informe actual no lo
  devuelve; habría que exponerlo.
- **Diagnósticos:** los de este nodo.

## 8. Ejecutar

Se ejecuta la versión abierta (guardada), nunca un borrador sin guardar; si hay cambios
sin guardar, la interfaz propone guardarlos primero.

```
┌ Configuración ──────────────┬ Recorrido ───────────────────────────────┐
│ Arquitectura  gaia_v31 · v3 │  (lienzo en modo lectura)                │
│ Modelo        Qwen3-8B Q5   │   ✓ preprocessing      0,0 s             │
│ Pregunta      [elegir ▾]    │   ✓ router             1,2 s             │
│               [escribir…]   │   ✓ web_research       9,8 s  (nota)     │
│ [▶ Ejecutar]                │   ✖ review             2,4 s  truncado   │
│                             │  Línea de tiempo  ▓▓░▓▓▓▓▓▓▓░░           │
└─────────────────────────────┴──────────────────────────────────────────┘
```

- El lienzo resalta el **camino recorrido**, con el tiempo y el estado de cada paso, y
  los nodos no visitados atenuados.
- Al seleccionar un paso se ve su actualización resumida y los errores; **Ver traza
  completa** abre el registro de la ejecución.
- Datos disponibles hoy en cada registro de ejecución: pasos (`node`, duración,
  actualización, error), llamadas al modelo, recursos, configuración y arquitectura
  ejecutada. No hace falta backend nuevo para esta pantalla.
- Mientras corre: estado y botón **Cancelar**. Un fallo se muestra en el nodo donde
  ocurrió, con lenguaje llano («el modelo cortó la respuesta por el límite de tokens») y el
  texto técnico a un clic.

## 9. Experimentos

Sustituye al panel actual (paridad completa antes del relevo, M3.4):

- Configuración: perfiles rápidos (V3.1 compartido, completo, solo directo, sin web), y
  capacidades, mejoras, modelos, presupuestos y muestreo en un panel avanzado plegado.
- Batería de 20 tareas con progreso, **parar y reanudar**, y resumen de tiempos.
- Historial con búsqueda, filtros y enlaces a trazas.
- **Comparar:** usa el endpoint de comparación. Muestra primero un banner de
  **comparabilidad** (mismas tareas, mismo código, misma arquitectura, diferencias de
  configuración) y después las métricas. Las diferencias se etiquetan con el vocabulario
  del backend: «dentro del rango observado», «fuera del rango observado» o «no valorable
  con una sola ejecución». Nunca se pinta una flecha verde o roja sobre una diferencia
  no valorable.
- **Puntuación:** la local es una acción normal. **El envío oficial** abre un diálogo que
  explica qué se envía, a dónde y que actualiza la clasificación pública, y exige
  confirmación explícita.

## 10. Sistema y modo demostración

- **Sistema:** estado de los modelos (listo, durmiendo, cargando, descargado), memoria de
  GPU y preferencias de tema e idioma.
- **Modo demostración:** sin backend (el Space público), la aplicación usa un adaptador
  en memoria con la arquitectura V3.1 y una ejecución de ejemplo. Un banner permanente lo
  declara («datos de ejemplo; las ejecuciones no son reales»). Es lo que justifica la
  arquitectura de puertos y adaptadores. Se publicará en el Space dentro de M6, con
  **tareas de ejemplo inventadas**: nunca preguntas ni respuestas de GAIA, cuyo dataset es
  de acceso restringido. La publicación es una acción externa: se prepara y audita según
  `docs/publicacion-space.md` y solo se sube con autorización explícita.

## 11. Diseño visual

- **Carácter:** instrumento de laboratorio sobrio y preciso, no un panel genérico. Mucha
  jerarquía tipográfica, poco ornamento, color con función.
- **Tema:** claro y oscuro con tokens. Sigue el sistema por defecto y el cambio es
  inmediato desde un control siempre visible en la barra lateral (sistema, claro,
  oscuro); la elección manual se recuerda.
- **Idioma:** español e inglés desde el principio. Todos los textos viven en catálogos de
  traducción (nunca en el código de los componentes), el idioma se detecta del
  navegador y se cambia desde el mismo control rápido de la barra lateral. Los códigos
  de diagnóstico del backend son estables y la interfaz los traduce; los textos técnicos
  del backend (por ejemplo un error de traza) se muestran tal cual.
- **Tokens:** roles de color (superficie, texto, acento, bordes, y semánticos de éxito,
  aviso, error e información), escala de espaciado de 4 px, escala tipográfica, radios,
  elevaciones y duraciones de movimiento. Un solo lugar define cada valor.
- **Categorías de nodo:** cinco, cada una con color, icono y etiqueta.
- **Movimiento:** breve (150–200 ms), con función, y desactivado con
  `prefers-reduced-motion`.
- **Iconos:** una sola familia (lucide) con tamaños y trazos coherentes.
- **Tipografía:** una sans-serif de sistema o de alta legibilidad para la interfaz y una
  monoespaciada para ids, hashes y código.

## 12. Atajos de teclado

| Atajo | Acción |
|---|---|
| `Ctrl+K` | Paleta de comandos |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Deshacer / rehacer |
| `Ctrl+S` | Guardar como versión |
| `Ctrl+Enter` | Validar |
| `Ctrl+D` | Duplicar selección |
| `Supr` | Eliminar selección |
| `F` | Ajustar vista al grafo |
| `L` | Autodisposición |
| `?` | Mostrar atajos |

## 13. Responsive

Pensada para escritorio (≥ 1280 px). En tabletas, paletas e inspector pasan a paneles
superpuestos. En móvil, el lienzo es de **solo lectura** con un aviso: editar un grafo
con precisión en una pantalla pequeña no se promete.

## 14. Datos que necesita la interfaz

Lo que ya existe y lo que falta en el backend:

| Necesidad | Estado |
|---|---|
| Validar, guardar, listar y leer arquitecturas | Existe (`/api/architectures…`). |
| Ejecutar con una arquitectura | Existe (`POST /api/run`, `experiment.architecture`). |
| Comparar experimentos | Existe (`POST /api/experiments/compare`). |
| Registro de ejecución con pasos | Existe (`/api/runs/<id>`). |
| **Catálogo** de componentes (contrato, descripción, recupera errores), estrategias de routing y campos del estado | **[backend]** nuevo, `GET /api/catalog`. |
| **Categoría** de cada componente para la paleta | **[backend]** en los metadatos del registro. |
| **Disposición** de nodos por versión | **[backend]** nuevo registro mutable, `layouts`. |
| **Campos garantizados y posibles** por nodo | **[backend]** exponer lo que el análisis ya calcula. |

## 15. Cómo comprobaremos la usabilidad

Escenarios que se recorrerán al cerrar cada fase, con tiempos medidos por ti, no
inventados:

1. Abrir la plantilla V3.1, entender qué hace cada nodo y localizar el aviso de
   `file_path` sin ayuda.
2. Construir desde cero la arquitectura lineal mínima y validarla.
3. Romper una conexión a propósito, entender el error y corregirlo.
4. Guardar una variante, ejecutarla y localizar en qué nodo falló.
5. Comparar dos experimentos e interpretar correctamente un resultado «no valorable».
6. Completar los escenarios 1 y 2 **solo con teclado**.

Además, una revisión heurística (sección 2) y una comprobación automática de
accesibilidad (axe) sobre cada pantalla, sin sustituir a la prueba manual con teclado.

## 16. Fuera de alcance

Subgrafos, edición de prompts, colaboración multiusuario, importar o exportar formatos
externos y comentarios sobre el lienzo.

## 17. Decisiones tomadas

| Tema | Decisión |
|---|---|
| Nombre | **GAIA Agent Studio**, con el subtítulo «Visual builder & evaluation lab for GAIA agents». El README aclarará que no hay afiliación con el benchmark GAIA. |
| Idioma | Bilingüe español e inglés, con textos externalizados y selector rápido. |
| Tema | Sigue el sistema, con cambio fácil e inmediato y elección recordada. |
| Historial de versiones | Resumen de cambios (nodos y aristas añadidos y quitados), calculado en el cliente. La comparación visual lado a lado queda como mejora posterior sobre el resumen. |
| Plantilla V3.1 | Solo lectura, con «Duplicar para editar». |
| «Datos aquí» | Entra en M3.2: el backend expone los campos garantizados y posibles por nodo. |
| Modo demostración | Se publica en el Space en M6, con datos sintéticos y cartel permanente. |
| Pila | React, TypeScript estricto, Vite, React Flow, Tailwind, Radix y lucide. |
| Arquitectura | Hexagonal pragmática: `domain`, `application`, `ports`, `adapters` y `ui`. |
| Ubicación | `frontend/` en la raíz; sustituye a la interfaz actual al alcanzar paridad verificada (M3.4). |
| Disposición | Registro mutable aparte por versión; no altera el hash. |
