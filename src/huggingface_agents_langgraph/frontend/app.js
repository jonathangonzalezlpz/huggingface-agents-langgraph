const randomButton = document.querySelector("#random-button");
const batchButton = document.querySelector("#batch-button");
const runAllButton = document.querySelector("#run-all-button");
const stopAllButton = document.querySelector("#stop-all-button");
const questionList = document.querySelector("#question-list");
const sessionBar = document.querySelector("#session-bar");
const sessionTitle = document.querySelector("#session-title");
const progressLabel = document.querySelector("#progress-label");
const timingSummary = document.querySelector("#timing-summary");
const progressFill = document.querySelector("#progress-fill");
const notice = document.querySelector("#notice");
const modelStatusList = document.querySelector("#model-status-list");
const gpuStatus = document.querySelector("#gpu-status");
const refreshModelsButton = document.querySelector("#refresh-models-button");
const experimentName = document.querySelector("#experiment-name");
const experimentModel = document.querySelector("#experiment-model");
const capabilityInputs = [...document.querySelectorAll("[data-capability]")];
const experimentMode = document.querySelector("#experiment-mode");
const scorePanel = document.querySelector("#score-panel");
const scoreButton = document.querySelector("#score-button");
const scoreResult = document.querySelector("#score-result");
const scoreExperimentSelect = document.querySelector("#score-experiment");
const localScoreButton = document.querySelector("#local-score-button");
const localScoreResult = document.querySelector("#local-score-result");
const localScoreExperimentSelect = document.querySelector("#local-score-experiment");
const experimentHistory = document.querySelector("#experiment-history");
const experimentHistoryList = document.querySelector("#experiment-history-list");
const comparisonPanel = document.querySelector("#comparison-panel");
const comparisonContent = document.querySelector("#comparison-content");
const COURSE_API_URL = "https://agents-course-unit4-scoring.hf.space";
let activeExperimentSnapshot = null;
let sessionExperimentSnapshot = null;
let stopRequested = false;
let currentBatchIndex = null;
let batchLaunched = false;
const MODEL_STATE_LABELS = {
  ready: "En memoria",
  loaded: "En memoria",
  in_use: "En uso",
  loading: "Cargando",
  sleeping: "Dormido",
  unloaded: "Descargado",
  not_loaded: "Bajo demanda",
  unavailable: "Sin conexión",
  error: "Error",
};

function showNotice(message) {
  notice.textContent = message;
  notice.hidden = false;
}

function clearNotice() {
  notice.textContent = "";
  notice.hidden = true;
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `Error HTTP ${response.status}`);
  }
  return payload;
}

async function requestCourseQuestions(endpoint) {
  const response = await fetch(`${COURSE_API_URL}${endpoint}`, { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `Error HTTP ${response.status}`);
  }
  return payload;
}

function setBusy(busy) {
  randomButton.disabled = busy;
  batchButton.disabled = busy;
  runAllButton.disabled = busy || batchLaunched;
  stopAllButton.disabled = !busy || stopRequested;
}

function getExperiment() {
  if (activeExperimentSnapshot) return activeExperimentSnapshot;
  let model = null;
  try {
    model = JSON.parse(experimentModel.value);
  } catch {
    model = null;
  }
  return {
    name: experimentName.value.trim() || "Personalizado",
    force_direct: experimentName.dataset.forceDirect === "true",
    enabled_capabilities: capabilityInputs
      .filter((input) => input.checked)
      .map((input) => input.dataset.capability),
    model,
  };
}

function modelLabel(model) {
  if (!model) return "Endpoint configurado";
  const provider = model.provider === "ollama" ? "Ollama" : "endpoint configurado";
  return `${model.model_id} · ${provider}`;
}

function applyProfile(profile) {
  const allEnabled = profile === "full" || profile === "direct";
  experimentName.dataset.forceDirect = profile === "direct" ? "true" : "false";
  capabilityInputs.forEach((input) => {
    input.checked = allEnabled || (profile === "no-web" && input.dataset.capability !== "web") ||
      (profile === "no-files" && input.dataset.capability === "web");
  });
  experimentName.value = {
    full: "Completo", direct: "Solo directo", "no-web": "Sin web", "no-files": "Sin adjuntos",
  }[profile];
  experimentMode.textContent = profile === "direct"
    ? "Todas las preguntas irán directamente al razonador."
    : "El router decide entre las capacidades habilitadas.";
}

function saveExperimentRecord() {
  const cards = [...questionList.querySelectorAll(".question-card")];
  if (cards.length !== 20 || cards.some((card) => !card._result)) return;
  const configs = cards.map((card) => card._experimentUsed);
  const sameConfig = configs.every(
    (config) => JSON.stringify(config) === JSON.stringify(configs[0]),
  );
  const record = {
    id: crypto.randomUUID(),
    created_at: new Date().toISOString(),
    config: sameConfig
      ? configs[0]
      : { name: "Configuración mixta", force_direct: false, enabled_capabilities: [], model: null },
    answers: cards.map((card) => ({
      task_id: card._question.task_id,
      question: card._question.question,
      file_name: card._question.file_name,
      submitted_answer: card._result.submitted_answer || "",
      error: card._result.error || "",
      route: card._result.route || "error",
      duration_seconds: card._durationSeconds,
      experiment: card._experimentUsed,
    })),
    average_duration_seconds: averageDuration(cards),
  };
  const history = JSON.parse(localStorage.getItem("gaia-experiments") || "[]");
  history.unshift(record);
  localStorage.setItem("gaia-experiments", JSON.stringify(history.slice(0, 20)));
  scorePanel.hidden = false;
  scoreResult.textContent = "Experimento guardado en este navegador; puedes calcular la puntuación oficial cuando quieras.";
  renderExperimentHistory();
}

function renderExperimentHistory() {
  const history = JSON.parse(localStorage.getItem("gaia-experiments") || "[]");
  experimentHistory.hidden = history.length === 0;
  scoreExperimentSelect.replaceChildren();
  localScoreExperimentSelect.replaceChildren();
  experimentHistoryList.replaceChildren();
  history.forEach((record) => {
    const option = document.createElement("option");
    option.value = record.id;
    option.textContent = `${record.config.name} · ${modelLabel(record.config.model)} · ${new Date(record.created_at).toLocaleString()}`;
    scoreExperimentSelect.append(option);
    localScoreExperimentSelect.append(option.cloneNode(true));

    const row = document.createElement("article");
    row.className = "experiment-history-row";
    const selectLabel = document.createElement("label");
    selectLabel.className = "experiment-select-label";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.dataset.experimentId = record.id;
    checkbox.addEventListener("change", renderExperimentComparison);
    selectLabel.append(checkbox, document.createTextNode("Comparar"));
    const title = document.createElement("strong");
    title.textContent = `${record.config.name} · ${modelLabel(record.config.model)}`;
    const details = document.createElement("span");
    const routes = record.answers.reduce((counts, answer) => {
      counts[answer.route] = (counts[answer.route] || 0) + 1;
      return counts;
    }, {});
    details.textContent = `${new Date(record.created_at).toLocaleString()} · ${record.answers.length}/20 respuestas · ${Object.entries(routes).map(([route, count]) => `${route}: ${count}`).join(" · ")}`;
    const score = document.createElement("span");
    score.className = "experiment-score";
    score.textContent = record.score
      ? `${record.score.score}% · ${record.score.correct_count}/${record.score.total_attempted}`
      : "Sin puntuación oficial";
    if (record.local_score) {
      score.textContent += ` · ${record.local_score.score}% local (${record.local_score.correct_count}/${record.local_score.total_attempted})`;
    }
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "button button-secondary experiment-delete-button";
    deleteButton.textContent = "Eliminar";
    deleteButton.setAttribute("aria-label", `Eliminar experimento ${record.config.name}`);
    deleteButton.addEventListener("click", () => deleteExperiment(record.id));
    const reviewDetails = document.createElement("details");
    reviewDetails.className = "experiment-run-review";
    const reviewSummary = document.createElement("summary");
    reviewSummary.textContent = `Ver preguntas y respuestas (${record.answers.length})`;
    const reviewList = document.createElement("ol");
    reviewList.className = "experiment-run-answers";
    record.answers.forEach((answer) => {
      const item = document.createElement("li");
      const question = document.createElement("p");
      question.className = "experiment-run-question";
      question.textContent = answer.question || "Pregunta no guardada";
      const response = document.createElement("p");
      response.className = answer.error ? "experiment-run-error" : "experiment-run-answer";
      response.textContent = answer.error
        ? `Error: ${answer.error}`
        : answer.submitted_answer || "Sin respuesta";
      const metadata = document.createElement("small");
      const timing = Number.isFinite(answer.duration_seconds)
        ? ` · ${formatDuration(answer.duration_seconds)}`
        : "";
      const correctness = answer.locally_correct === true
        ? " · Acierto local"
        : answer.locally_correct === false ? " · Error local" : "";
      metadata.textContent = `${answer.task_id} · Ruta: ${answer.route || "sin dato"}${timing}${correctness}`;
      item.append(question, response, metadata);
      reviewList.append(item);
    });
    reviewDetails.append(reviewSummary, reviewList);
    row.append(selectLabel, title, details, score, deleteButton, reviewDetails);
    experimentHistoryList.append(row);
  });
  renderExperimentComparison();
}

function renderExperimentComparison() {
  const history = JSON.parse(localStorage.getItem("gaia-experiments") || "[]");
  const selectedIds = new Set(
    [...experimentHistoryList.querySelectorAll("input:checked")].map(
      (input) => input.dataset.experimentId,
    ),
  );
  const selected = history.filter((record) => selectedIds.has(record.id));
  comparisonPanel.hidden = selected.length < 2;
  comparisonContent.replaceChildren();
  if (selected.length < 2) return;

  const table = document.createElement("table");
  table.className = "comparison-table";
  const header = document.createElement("tr");
  ["Pregunta", ...selected.map((record) => `${record.config.name} · ${modelLabel(record.config.model)}`)].forEach((label) => {
    const cell = document.createElement("th");
    cell.textContent = label;
    header.append(cell);
  });
  const head = document.createElement("thead");
  head.append(header);
  table.append(head);

  const taskIds = [...new Set(selected.flatMap((record) => record.answers.map((answer) => answer.task_id)))];
  const body = document.createElement("tbody");
  taskIds.forEach((taskId) => {
    const answers = selected.map((record) => record.answers.find((answer) => answer.task_id === taskId));
    const prompts = answers.map((answer) => answer?.question || "");
    const nonemptyPrompts = [...new Set(prompts.filter(Boolean))];
    const row = document.createElement("tr");
    const questionCell = document.createElement("td");
    questionCell.className = "comparison-question";
    const taskLabel = document.createElement("strong");
    taskLabel.textContent = taskId;
    const variation = document.createElement("span");
    variation.className = `question-variation ${nonemptyPrompts.length === 1 && prompts.every(Boolean) ? "same" : "changed"}`;
    variation.textContent = nonemptyPrompts.length === 1 && prompts.every(Boolean)
      ? "Pregunta idéntica"
      : "Pregunta distinta o ausente";
    questionCell.append(taskLabel, variation);
    if (nonemptyPrompts.length === 1) {
      const prompt = document.createElement("p");
      prompt.textContent = nonemptyPrompts[0];
      questionCell.append(prompt);
    } else {
      prompts.forEach((promptText, index) => {
        const prompt = document.createElement("p");
        prompt.textContent = `${selected[index].config.name}: ${promptText || "No disponible"}`;
        questionCell.append(prompt);
      });
    }
    row.append(questionCell);
    answers.forEach((answer) => {
      const cell = document.createElement("td");
      cell.textContent = answer?.submitted_answer || "Sin respuesta";
      const route = document.createElement("small");
      const localStatus = answer?.locally_correct === true
        ? "Acierto local"
        : answer?.locally_correct === false ? "Error local" : "Sin evaluar localmente";
      route.textContent = `Ruta: ${answer?.route || "sin dato"} · ${localStatus}`;
      cell.append(document.createElement("br"), route);
      row.append(cell);
    });
    body.append(row);
  });
  table.append(body);
  comparisonContent.append(table);
}

function setProgress(processed, total) {
  const current = currentBatchIndex === null
    ? ""
    : ` · procesando ${currentBatchIndex}/${total}`;
  progressLabel.textContent = `${processed} / ${total} procesadas${current}`;
  progressFill.style.width = total ? `${(processed / total) * 100}%` : "0%";
}

function averageDuration(cards) {
  const durations = cards.map((card) => card._durationSeconds).filter(Number.isFinite);
  return durations.length
    ? durations.reduce((sum, duration) => sum + duration, 0) / durations.length
    : null;
}

function formatDuration(seconds) {
  return `${seconds.toFixed(1)} s`;
}

function updateTimingSummary() {
  const cards = [...questionList.querySelectorAll(".question-card")];
  const durations = cards.map((card) => card._durationSeconds).filter(Number.isFinite);
  if (!durations.length) {
    timingSummary.textContent = "";
    return;
  }
  const average = durations.reduce((sum, duration) => sum + duration, 0) / durations.length;
  timingSummary.textContent = `Media: ${formatDuration(average)} · ${durations.length} medida${durations.length === 1 ? "" : "s"}`;
}

function setExperimentControlsDisabled(disabled) {
  experimentName.disabled = disabled;
  experimentModel.disabled = disabled;
  capabilityInputs.forEach((input) => { input.disabled = disabled; });
  document.querySelectorAll(".preset-button").forEach((button) => {
    button.disabled = disabled;
  });
}

function renderModelStatus(model) {
  const card = document.createElement("article");
  card.className = "model-status-card";
  const top = document.createElement("div");
  top.className = "model-status-top";
  const name = document.createElement("span");
  name.className = "model-status-name";
  name.textContent = model.name;
  const badge = document.createElement("span");
  badge.className = `model-status-badge ${model.state}`;
  badge.textContent = MODEL_STATE_LABELS[model.state] || model.state;
  top.append(name, badge);
  card.append(top);

  if (model.model) {
    const modelName = document.createElement("span");
    modelName.className = "model-status-model";
    modelName.textContent = model.model;
    modelName.title = model.model;
    card.append(modelName);
  }

  const detail = document.createElement("span");
  detail.className = "model-status-detail";
  if (model.state === "unloaded") {
    detail.textContent = `Inactivo ${model.idle_for_seconds}s · descarga tras ${model.idle_timeout_seconds}s`;
  } else if (model.state === "not_loaded") {
    detail.textContent = "Se carga al necesitarlo";
  } else if (model.idle_timeout_seconds) {
    detail.textContent = `Descarga tras ${model.idle_timeout_seconds}s sin uso`;
  } else {
    detail.textContent = model.state === "sleeping" ? "Descargado por inactividad" : "";
  }
  card.append(detail);
  return card;
}

async function refreshModelStatus() {
  try {
    const status = await requestJson("/api/status", { cache: "no-store" });
    gpuStatus.textContent = status.gpu.available
      ? `GPU disponible · ${status.gpu.name} · CUDA`
      : `GPU no disponible · multimedia en CPU (${status.gpu.backend})`;
    gpuStatus.classList.toggle("gpu-status-active", status.gpu.available);
    gpuStatus.classList.toggle("gpu-status-inactive", !status.gpu.available);
    modelStatusList.replaceChildren(
      renderModelStatus(status.llm),
      ...status.multimedia_models.map(renderModelStatus),
    );
  } catch {
    gpuStatus.textContent = "No se pudo consultar el estado de la GPU";
    gpuStatus.classList.remove("gpu-status-active", "gpu-status-inactive");
    modelStatusList.replaceChildren(
      renderModelStatus({ name: "LLM razonador", state: "unavailable" }),
      renderModelStatus({ name: "VLM", state: "error" }),
      renderModelStatus({ name: "Whisper", state: "error" }),
      renderModelStatus({ name: "AST audio", state: "error" }),
    );
  }
}

async function refreshAvailableModels() {
  const previousValue = experimentModel.value;
  try {
    const payload = await requestJson("/api/models", { cache: "no-store" });
    const models = Array.isArray(payload.models) ? payload.models : [];
    experimentModel.replaceChildren();
    models.forEach((model) => {
      if (!model || !model.model_id || !["configured", "ollama"].includes(model.provider)) {
        return;
      }
      const option = document.createElement("option");
      option.value = JSON.stringify({
        provider: model.provider,
        model_id: model.model_id,
      });
      option.textContent = modelLabel(model);
      experimentModel.append(option);
    });

    if (!experimentModel.options.length) {
      const option = document.createElement("option");
      option.value = "null";
      option.textContent = "Usar el endpoint configurado";
      experimentModel.append(option);
      return;
    }

    const hasPreviousSelection = [...experimentModel.options].some(
      (option) => option.value === previousValue,
    );
    if (hasPreviousSelection) {
      experimentModel.value = previousValue;
    } else {
      const configuredModel = [...experimentModel.options].find((option) => {
        return JSON.parse(option.value).provider === "configured";
      });
      experimentModel.value = (configuredModel || experimentModel.options[0]).value;
    }
  } catch {
    experimentModel.replaceChildren();
    const option = document.createElement("option");
    option.value = "null";
    option.textContent = "Usar el endpoint configurado";
    experimentModel.append(option);
  }
}

function renderQuestion(question, index, total) {
  const card = document.createElement("article");
  card.className = "question-card";
  card.dataset.taskId = question.task_id;

  const cardTop = document.createElement("div");
  cardTop.className = "card-top";
  const identity = document.createElement("div");
  identity.innerHTML = `<span class="card-index">TASK ${String(index + 1).padStart(2, "0")} / ${String(total).padStart(2, "0")}</span>`;
  const taskId = document.createElement("span");
  taskId.className = "task-id";
  taskId.textContent = question.task_id;
  identity.append(taskId);
  const status = document.createElement("span");
  status.className = "card-status ready";
  status.textContent = "Lista";
  cardTop.append(identity, status);

  const body = document.createElement("div");
  body.className = "card-body";
  const prompt = document.createElement("p");
  prompt.className = "question-text";
  prompt.textContent = question.question || "Pregunta no disponible";
  const attachmentRow = document.createElement("div");
  attachmentRow.className = "attachment-row";
  const fileName = typeof question.file_name === "string" ? question.file_name.trim() : "";
  const attachmentBadge = document.createElement("span");
  attachmentBadge.className = fileName ? "attachment-badge has-file" : "attachment-badge";
  attachmentBadge.textContent = fileName ? `▧ Adjunto · ${fileName}` : "○ Sin adjunto";
  attachmentRow.append(attachmentBadge);
  if (fileName) {
    const attachmentLink = document.createElement("a");
    attachmentLink.className = "attachment-link";
    attachmentLink.href = `/api/files/${encodeURIComponent(question.task_id)}`;
    attachmentLink.textContent = "Descargar archivo ↗";
    attachmentLink.setAttribute("download", "");
    attachmentRow.append(attachmentLink);
  }

  const cardActions = document.createElement("div");
  cardActions.className = "card-actions";
  const runButton = document.createElement("button");
  runButton.className = "button run-button";
  runButton.type = "button";
  runButton.textContent = "▶ Ejecutar agente";
  runButton.addEventListener("click", () => processQuestion(card));
  cardActions.append(runButton);
  body.append(prompt, attachmentRow, cardActions);

  const answerPanel = document.createElement("div");
  answerPanel.className = "answer-panel";
  const answerLabel = document.createElement("span");
  answerLabel.className = "answer-label";
  answerLabel.textContent = "RESPUESTA";
  const answerValue = document.createElement("span");
  answerValue.className = "answer-value pending";
  answerValue.textContent = "Pendiente de ejecutar";
  const answerMeta = document.createElement("div");
  answerMeta.className = "answer-meta";
  const duration = document.createElement("span");
  duration.className = "answer-duration";
  answerMeta.append(answerLabel, duration);
  answerPanel.append(answerMeta, answerValue);
  card.append(cardTop, body, answerPanel);
  card._question = {
    task_id: question.task_id,
    question: question.question,
    file_name: fileName,
  };
  card._status = status;
  card._answer = answerValue;
  card._duration = duration;
  card._durationSeconds = null;
  card._runButton = runButton;
  card._result = null;
  return card;
}

function displayQuestions(questions, title) {
  sessionExperimentSnapshot = null;
  batchLaunched = false;
  setExperimentControlsDisabled(false);
  questionList.replaceChildren();
  const fragment = document.createDocumentFragment();
  questions.forEach((question, index) => {
    fragment.append(renderQuestion(question, index, questions.length));
  });
  questionList.append(fragment);
  sessionTitle.textContent = title;
  sessionBar.hidden = false;
  runAllButton.hidden = questions.length < 2;
  runAllButton.disabled = false;
  runAllButton.textContent = "▶ Lanzar experimento";
  stopAllButton.hidden = true;
  stopAllButton.disabled = true;
  setProgress(0, questions.length);
  timingSummary.textContent = "";
}

async function loadRandomQuestion() {
  clearNotice();
  setBusy(true);
  scorePanel.hidden = true;
  try {
    const question = await requestCourseQuestions("/random-question");
    displayQuestions([question], "Pregunta aleatoria");
  } catch (error) {
    showNotice(error.message);
  } finally {
    setBusy(false);
  }
}

async function loadQuestionBatch() {
  clearNotice();
  setBusy(true);
  scorePanel.hidden = true;
  try {
    const questions = await requestCourseQuestions("/questions");
    if (!Array.isArray(questions)) {
      throw new Error("La API no devolvió una lista de preguntas");
    }
    displayQuestions(questions, `Batería GAIA · ${questions.length} preguntas`);
  } catch (error) {
    showNotice(error.message);
  } finally {
    setBusy(false);
  }
}

async function processQuestion(card) {
  const startedAt = performance.now();
  clearNotice();
  card._status.className = "card-status running";
  card._status.textContent = "Procesando";
  card._answer.className = "answer-value pending";
  card._answer.textContent = "El agente está trabajando…";
  card._runButton.disabled = true;
  const experiment = structuredClone(getExperiment());
  card._experimentUsed = experiment;
  try {
    const result = await requestJson("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...card._question, experiment }),
    });
    card._durationSeconds = Number.isFinite(result.duration_seconds)
      ? result.duration_seconds
      : (performance.now() - startedAt) / 1000;
    card._duration.textContent = `Tiempo: ${formatDuration(card._durationSeconds)}`;
    card._result = result;
    card._status.className = "card-status done";
    card._status.textContent = result.submitted_answer ? "Respondida" : "Sin respuesta";
    if (result.submitted_answer) {
      card._answer.className = "answer-value final";
      card._answer.textContent = result.submitted_answer;
    } else {
      card._answer.className = "answer-value pending";
      card._answer.textContent = `Ruta «${result.route || "desconocida"}» todavía no implementada`;
    }
  } catch (error) {
    card._durationSeconds = (performance.now() - startedAt) / 1000;
    card._duration.textContent = `Tiempo: ${formatDuration(card._durationSeconds)}`;
    card._status.className = "card-status";
    card._status.textContent = "Error";
    card._result = { error: error.message, submitted_answer: "", route: "error" };
    card._answer.className = "answer-value error";
    card._answer.textContent = error.message;
  } finally {
    card._runButton.disabled = false;
    updateBatchProgress();
    updateTimingSummary();
    saveExperimentRecord();
    void refreshModelStatus();
  }
}

async function calculateOfficialScore() {
  const history = JSON.parse(localStorage.getItem("gaia-experiments") || "[]");
  const record = history.find((item) => item.id === scoreExperimentSelect.value);
  if (!record || record.answers.length !== 20) {
    showNotice("Primero ejecuta las 20 preguntas de la batería.");
    return;
  }
  scoreButton.disabled = true;
  scoreResult.textContent = "Enviando las respuestas al evaluador oficial…";
  try {
    const result = await requestJson("/api/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: document.querySelector("#hf-username").value,
        agent_code: document.querySelector("#agent-code").value,
        answers: record.answers.map(({ task_id, submitted_answer }) => ({ task_id, submitted_answer })),
      }),
    });
    const correct = result.correct_count;
    const total = result.total_attempted || 20;
    const percentage = result.score;
    scoreResult.textContent = `${percentage}% · ${correct}/${total} aciertos · ${result.message || "Puntuación recibida"}`;
    record.score = { score: percentage, correct_count: correct, total_attempted: total };
    localStorage.setItem("gaia-experiments", JSON.stringify(history));
    renderExperimentHistory();
  } catch (error) {
    scoreResult.textContent = error.message;
  } finally {
    scoreButton.disabled = false;
  }
}

async function calculateLocalScore() {
  const history = JSON.parse(localStorage.getItem("gaia-experiments") || "[]");
  const record = history.find((item) => item.id === localScoreExperimentSelect.value);
  if (!record || record.answers.length !== 20) {
    localScoreResult.textContent = "Selecciona una ejecución completa de 20 preguntas.";
    return;
  }
  localScoreButton.disabled = true;
  localScoreResult.textContent = "Comparando respuestas con GAIA validation…";
  try {
    const result = await requestJson("/api/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        answers: record.answers.map(({ task_id, submitted_answer }) => ({ task_id, submitted_answer })),
      }),
    });
    const correctness = new Map(result.results.map(({ task_id, correct }) => [task_id, correct]));
    record.answers.forEach((answer) => {
      answer.locally_correct = correctness.get(answer.task_id) ?? null;
    });
    record.local_score = {
      score: result.score,
      correct_count: result.correct_count,
      total_attempted: result.total_attempted,
    };
    localStorage.setItem("gaia-experiments", JSON.stringify(history));
    localScoreResult.textContent = `${result.score}% · ${result.correct_count}/${result.total_attempted} aciertos locales. Las respuestas esperadas no se guardan.`;
    renderExperimentHistory();
  } catch (error) {
    localScoreResult.textContent = error.message;
  } finally {
    localScoreButton.disabled = false;
  }
}

function updateBatchProgress() {
  const cards = [...questionList.querySelectorAll(".question-card")];
  const processed = cards.filter((card) => ["Respondida", "Sin respuesta", "Error"].includes(card._status.textContent)).length;
  setProgress(processed, cards.length);
}

async function processAllQuestions() {
  clearNotice();
  if (batchLaunched) return;
  const cards = [...questionList.querySelectorAll(".question-card")];
  const pendingCards = cards.filter((card) => !card._result);
  if (!pendingCards.length) return;

  if (!sessionExperimentSnapshot) {
    sessionExperimentSnapshot = structuredClone(getExperiment());
  }
  activeExperimentSnapshot = sessionExperimentSnapshot;
  batchLaunched = true;
  stopRequested = false;
  setBusy(true);
  setExperimentControlsDisabled(true);
  stopAllButton.hidden = false;
  stopAllButton.disabled = false;
  stopAllButton.textContent = "■ Detener";
  runAllButton.textContent = "Procesando batería…";
  try {
    for (const card of pendingCards) {
      if (stopRequested) break;
      currentBatchIndex = cards.indexOf(card) + 1;
      setProgress(
        cards.filter((item) => item._result).length,
        cards.length,
      );
      await processQuestion(card);
    }
  } finally {
    activeExperimentSnapshot = null;
    currentBatchIndex = null;
    const hasPendingCards = cards.some((card) => !card._result);
    sessionExperimentSnapshot = null;
    if (!hasPendingCards) {
      runAllButton.textContent = "Batería completada";
    } else {
      runAllButton.textContent = "Batería detenida";
      setProgress(cards.filter((card) => card._result).length, cards.length);
    }
    stopAllButton.hidden = true;
    stopAllButton.disabled = true;
    stopAllButton.textContent = "■ Detener";
    setBusy(false);
    setExperimentControlsDisabled(false);
    if (stopRequested && hasPendingCards) {
      progressLabel.textContent += " · detenido tras completar la pregunta en curso";
    } else if (!hasPendingCards) {
      progressLabel.textContent = `${cards.length} / ${cards.length} procesadas · experimento completado`;
    }
  }
}

randomButton.addEventListener("click", loadRandomQuestion);
batchButton.addEventListener("click", loadQuestionBatch);
runAllButton.addEventListener("click", processAllQuestions);
stopAllButton.addEventListener("click", () => {
  stopRequested = true;
  stopAllButton.disabled = true;
  stopAllButton.textContent = "Deteniendo tras esta pregunta…";
  progressLabel.textContent += " · se detendrá al terminar la pregunta en curso";
});
refreshModelsButton.addEventListener("click", () => {
  void refreshModelStatus();
  void refreshAvailableModels();
});
document.querySelectorAll(".preset-button").forEach((button) => {
  button.addEventListener("click", () => applyProfile(button.dataset.profile));
});
capabilityInputs.forEach((input) => input.addEventListener("change", () => {
  experimentName.dataset.forceDirect = "false";
  experimentName.value = "Personalizado";
  experimentMode.textContent = "El router decide entre las capacidades habilitadas.";
}));
scoreButton.addEventListener("click", calculateOfficialScore);
localScoreButton.addEventListener("click", calculateLocalScore);
applyProfile("full");
renderExperimentHistory();
void refreshModelStatus();
void refreshAvailableModels();
window.setInterval(refreshModelStatus, 5000);

function deleteExperiment(experimentId) {
  const history = JSON.parse(localStorage.getItem("gaia-experiments") || "[]");
  localStorage.setItem("gaia-experiments", JSON.stringify(history.filter((record) => record.id !== experimentId)));
  renderExperimentHistory();
}
