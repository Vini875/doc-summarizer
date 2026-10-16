const MAX_BYTES = 1024 * 1024;
const ALLOWED = [".docx", ".txt", ".pdf"];
const PASS_SCORE = 4;

const $ = (id) => document.getElementById(id);
const form = $("upload-form");
const fileInput = $("file-input");
const uploadBtn = $("upload-btn");
const message = $("message");
const summarizeSection = $("summarize-section");
const summarizeBtn = $("summarize-btn");
const progress = $("progress");
const results = $("results");

let documentId = null;

function showMessage(text, kind) {
  message.textContent = text;
  message.className = `message ${kind}`;
  message.hidden = false;
}

function resetSummary() {
  documentId = null;
  summarizeSection.hidden = true;
  results.hidden = true;
}

async function readError(response) {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
  } catch (_) { /* not JSON */ }
  return `Request failed (${response.status}).`;
}

function formatSize(bytes) {
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`;
}

fileInput.addEventListener("change", () => {
  resetSummary();
  message.hidden = true;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  resetSummary();
  const file = fileInput.files[0];
  if (!file) return showMessage("Please choose a file first.", "error");

  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!ALLOWED.includes(ext)) {
    return showMessage("Only Word (.docx), Text (.txt) and PDF (.pdf) files are accepted.", "error");
  }
  if (file.size > MAX_BYTES) {
    return showMessage(`The file is ${formatSize(file.size)}; the limit is 1 MB.`, "error");
  }

  uploadBtn.disabled = true;
  showMessage("Uploading...", "ok");
  try {
    const body = new FormData();
    body.append("file", file);
    const response = await fetch("/api/documents", { method: "POST", body });
    if (!response.ok) return showMessage(await readError(response), "error");

    const doc = await response.json();
    documentId = doc.id;
    showMessage(
      `✓ "${doc.filename}" uploaded successfully (${formatSize(doc.size_bytes)}, ${doc.word_count.toLocaleString()} words).`,
      "ok",
    );
    summarizeSection.hidden = false;
  } catch (_) {
    showMessage("Could not reach the server. Is it running?", "error");
  } finally {
    uploadBtn.disabled = false;
  }
});

function renderScores(containerId, scores) {
  const container = $(containerId);
  container.replaceChildren();
  for (const [name, value] of Object.entries(scores)) {
    const pill = document.createElement("span");
    pill.className = value < PASS_SCORE ? "score low" : "score";
    pill.textContent = `${name[0].toUpperCase()}${name.slice(1)}: ${value}/5`;
    container.appendChild(pill);
  }
}

function renderQuality(result) {
  const quality = $("quality");
  quality.replaceChildren();
  quality.className = result.passed ? "quality pass" : "quality warn";

  const headline = document.createElement("div");
  const tries = result.attempts === 1 ? "1 attempt" : `${result.attempts} attempts`;
  headline.textContent = result.passed
    ? `✓ Quality check passed (relevance, correctness, completeness) after ${tries}. Model: ${result.model}.`
    : `Quality check did not fully pass after ${tries}; showing the best result. Model: ${result.model}.`;
  quality.appendChild(headline);

  if (!result.passed && result.issues.length) {
    const list = document.createElement("ul");
    for (const issue of result.issues) {
      const item = document.createElement("li");
      item.textContent = issue;
      list.appendChild(item);
    }
    quality.appendChild(list);
  }
}

summarizeBtn.addEventListener("click", async () => {
  if (documentId === null) return;
  summarizeBtn.disabled = true;
  uploadBtn.disabled = true;
  progress.hidden = false;
  results.hidden = true;
  try {
    const response = await fetch(`/api/documents/${documentId}/summarize`, { method: "POST" });
    if (!response.ok) return showMessage(await readError(response), "error");

    const result = await response.json();
    $("extractive").value = result.extractive;
    $("abstractive").value = result.abstractive;
    $("extractive-words").textContent = `${result.extractive_words} / 350 words`;
    $("abstractive-words").textContent = `${result.abstractive_words} / 350 words`;
    renderScores("extractive-scores", result.scores.extractive);
    renderScores("abstractive-scores", result.scores.abstractive);
    renderQuality(result);
    results.hidden = false;
  } catch (_) {
    showMessage("Could not reach the server. Is it running?", "error");
  } finally {
    summarizeBtn.disabled = false;
    uploadBtn.disabled = false;
    progress.hidden = true;
  }
});
