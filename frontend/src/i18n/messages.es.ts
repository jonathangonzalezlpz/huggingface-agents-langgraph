/** Spanish catalog. Its keys define `MessageKey`; English must provide all of them. */
export const es = {
  'app.name': 'GAIA Agent Studio',
  'app.tagline': 'Constructor visual y laboratorio de evaluación para agentes GAIA',
  'skip.toContent': 'Saltar al contenido',

  'nav.label': 'Navegación principal',
  'nav.builder': 'Constructor',
  'nav.runs': 'Ejecuciones',
  'nav.experiments': 'Experimentos',
  'nav.system': 'Sistema',

  'status.title': 'Estado',
  'status.backend': 'Backend',
  'status.backend.online': 'Conectado',
  'status.backend.offline': 'Sin conexión',
  'status.model': 'Modelo',
  'status.model.ready': 'Listo',
  'status.model.sleeping': 'En reposo',
  'status.model.loading': 'Cargando',
  'status.model.unavailable': 'No disponible',
  'status.model.unknown': 'Sin datos',

  'controls.theme': 'Tema',
  'controls.theme.system': 'Sistema',
  'controls.theme.light': 'Claro',
  'controls.theme.dark': 'Oscuro',
  'controls.language': 'Idioma',

  'demo.banner': 'Modo demostración: datos de ejemplo; las ejecuciones no son reales.',

  'common.loading': 'Cargando…',
  'common.retry': 'Reintentar',
  'common.legacy': 'Abrir la interfaz anterior',

  'error.title': 'Algo ha fallado',
  'error.network': 'No se puede conectar con el backend.',
  'error.http': 'El backend respondió con un error ({status}).',
  'error.contract': 'El backend devolvió datos inesperados.',

  'diagnostics.errors.one': '{count} error',
  'diagnostics.errors.other': '{count} errores',
  'diagnostics.warnings.one': '{count} aviso',
  'diagnostics.warnings.other': '{count} avisos',
  'diagnostics.infos.one': '{count} nota',
  'diagnostics.infos.other': '{count} notas',

  'category.input': 'Entrada',
  'category.acquisition': 'Adquisición',
  'category.research': 'Investigación',
  'category.reasoning': 'Razonamiento',
  'category.output': 'Salida',
  'category.other': 'Otros',

  'builder.title': 'Constructor',
  'builder.description': 'Diseña, valida y guarda arquitecturas de agente.',
  'builder.library': 'Biblioteca de arquitecturas',
  'builder.library.empty': 'Todavía no hay arquitecturas.',
  'builder.builtin': 'Integrada',
  'builder.readOnly': 'Solo lectura',
  'builder.version': 'Versión {version}',
  'builder.components.one': '{count} componente',
  'builder.components.other': '{count} componentes',
  'builder.validation.valid': 'Válida',
  'builder.validation.invalid': 'Con errores',
  'builder.catalog': 'Catálogo de componentes',
  'builder.catalog.hint': 'Los componentes que podrás colocar en el lienzo, por categoría.',
  'builder.coming': 'El lienzo de edición llega en la siguiente fase.',
  'builder.recoversErrors': 'Recupera errores',

  'component.preprocessing': 'Normaliza espacios y prepara el texto de la pregunta.',
  'component.attachment_resolver': 'Localiza y comprueba el adjunto de la tarea.',
  'component.router': 'Elige la ruta por la extensión del adjunto o, si no hay, con el modelo.',
  'component.code_processing':
    'Inspecciona o ejecuta en un entorno acotado el código Python adjunto.',
  'component.spreadsheet_processing': 'Extrae y analiza datos de hojas de cálculo.',
  'component.document_processing': 'Extrae el texto de documentos PDF y selecciona lo relevante.',
  'component.multimedia_processing':
    'Transcribe audio, clasifica sonidos e inspecciona imágenes y vídeo.',
  'component.web_research': 'Busca en la web y en enciclopedias.',
  'component.review': 'Revisa la evidencia y decide si investigar más o resolver.',
  'component.research_action': 'Ejecuta la acción de investigación elegida por la revisión.',
  'component.reasoning': 'Razona a partir de la evidencia y propone una respuesta.',
  'component.answer_production': 'Da formato a la respuesta final según las reglas de GAIA.',

  'runs.title': 'Ejecuciones',
  'runs.description': 'Lanza una pregunta con una arquitectura y revisa el recorrido.',
  'experiments.title': 'Experimentos',
  'experiments.description': 'Baterías, historial y comparación de resultados.',
  'placeholder.title': 'Disponible en una fase posterior',
  'placeholder.body':
    'Esta sección se construirá siguiendo la hoja de ruta de V4. Mientras tanto, la interfaz anterior sigue disponible.',

  'system.title': 'Sistema',
  'system.description': 'Estado de los servicios y modo de funcionamiento.',
  'system.mode': 'Modo de funcionamiento',
  'system.mode.live': 'Conectado al backend',
  'system.mode.demo': 'Demostración con datos de ejemplo',
  'system.model': 'Modelo razonador',

  'notfound.title': 'Página no encontrada',
  'notfound.body': 'Esa dirección no existe en Studio.',
  'notfound.back': 'Volver al Constructor',
} as const;

export type MessageKey = keyof typeof es;
