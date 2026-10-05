const randomButton = document.querySelector("#random-button");
const batchButton = document.querySelector("#batch-button");
const runAllButton = document.querySelector("#run-all-button");
const questionList = document.querySelector("#question-list");
const sessionBar = document.querySelector("#session-bar");
const sessionTitle = document.querySelector("#session-title");
const progressLabel = document.querySelector("#progress-label");
const progressFill = document.querySelector("#progress-fill");
const notice = document.querySelector("#notice");

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

function setBusy(busy) {
  randomButton.disabled = busy;
  batchButton.disabled = busy;
  runAllButton.disabled = busy;
}

function setProgress(processed, total) {
  progressLabel.textContent = `${processed} / ${total} procesadas`;
  progressFill.style.width = total ? `${(processed / total) * 100}%` : "0%";
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
  answerPanel.append(answerLabel, answerValue);
  card.append(cardTop, body, answerPanel);
  card._question = {
    task_id: question.task_id,
    question: question.question,
    file_name: fileName,
  };
  card._status = status;
  card._answer = answerValue;
  card._runButton = runButton;
  return card;
}

function displayQuestions(questions, title) {
  questionList.replaceChildren();
  const fragment = document.createDocumentFragment();
  questions.forEach((question, index) => {
    fragment.append(renderQuestion(question, index, questions.length));
  });
  questionList.append(fragment);
  sessionTitle.textContent = title;
  sessionBar.hidden = false;
  runAllButton.hidden = questions.length < 2;
  setProgress(0, questions.length);
}

async function loadRandomQuestion() {
  clearNotice();
  setBusy(true);
  try {
    const question = await requestJson("/api/random-question");
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
  try {
    const questions = await requestJson("/api/questions");
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
  clearNotice();
  card._status.className = "card-status running";
  card._status.textContent = "Procesando";
  card._answer.className = "answer-value pending";
  card._answer.textContent = "El agente está trabajando…";
  card._runButton.disabled = true;
  try {
    const result = await requestJson("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(card._question),
    });
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
    card._status.className = "card-status";
    card._status.textContent = "Error";
    card._answer.className = "answer-value error";
    card._answer.textContent = error.message;
  } finally {
    card._runButton.disabled = false;
    updateBatchProgress();
  }
}

function updateBatchProgress() {
  const cards = [...questionList.querySelectorAll(".question-card")];
  const processed = cards.filter((card) => ["Respondida", "Sin respuesta", "Error"].includes(card._status.textContent)).length;
  setProgress(processed, cards.length);
}

async function processAllQuestions() {
  clearNotice();
  setBusy(true);
  try {
    const cards = [...questionList.querySelectorAll(".question-card")];
    for (const card of cards) {
      await processQuestion(card);
    }
  } finally {
    setBusy(false);
  }
}

randomButton.addEventListener("click", loadRandomQuestion);
batchButton.addEventListener("click", loadQuestionBatch);
runAllButton.addEventListener("click", processAllQuestions);
