# Document Summarizer

A single-page web app that summarizes English Word, Text and PDF documents with Claude. It shows an
**extractive** summary (key sentences copied from the document) and an **abstractive** summary (main
points in new words) side by side.

## Features

- Upload `.docx`, `.txt` or `.pdf` files up to **1 MB**. Other formats are rejected in the browser and on the server.
- The server checks that the file content matches its extension (a renamed `.png` is rejected).
- Only **English** documents are accepted (detected with `langdetect`).
- A confirmation appears after upload, followed by a **Summarize** button.
- Summaries are written in English and capped at **350 words** each.
- Quality checks:
  - **Correctness of the extractive summary:** every sentence must appear word-for-word in the source. Sentences that don't are dropped.
  - **Word limit and language:** enforced in code.
  - **Relevance, correctness, completeness:** a second Claude call scores each summary from 1 to 5. If any score is below 4, the issues are fed back and the summary is regenerated (2 attempts by default). The best attempt is shown with its scores.
- Documents and summaries are stored in SQLite.

## Tech stack (all open source or free)

| Layer | Choice |
|---|---|
| Backend | Python 3.10+, FastAPI, Uvicorn |
| UI | Plain HTML, CSS and JavaScript (no build step) |
| Database | SQLite |
| Parsing | python-docx, pypdf |
| Language detection | langdetect |
| LLM | Claude Sonnet 5.5 (`claude-sonnet-5-5`), the mid-tier Claude model, via the official `anthropic` SDK |

The Claude API itself is a paid service. Everything else is free.

## Run locally

```powershell
git clone https://github.com/<your-user>/doc-summarizer.git
cd doc-summarizer
python -m venv .venv
.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env               # then put your ANTHROPIC_API_KEY in .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000.

## Run with Docker

```bash
docker build -t doc-summarizer .
docker run -p 8000:8000 --env-file .env -v ./data:/app/data doc-summarizer
```

## Tests

```bash
pytest -q
```

The tests cover format, size and signature validation, text extraction, the verbatim check for
extractive sentences, the word limit, and language detection. They do not call the Claude API.
GitHub Actions runs them on every push (`.github/workflows/tests.yml`).

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/documents` | Multipart upload (`file`). Validates and stores the document; returns its `id`. |
| `POST` | `/api/documents/{id}/summarize` | Returns `abstractive`, `extractive`, `scores`, `issues`, `passed`, `attempts`. |
| `GET` | `/api/health` | Health check. |

## Configuration

Set these in `.env` (see `.env.example`):

| Variable | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | (required) | Claude API key |
| `CLAUDE_MODEL` | `claude-sonnet-5-5` | Model used for summaries and reviews |
| `CLAUDE_EFFORT` | `medium` | Claude effort level |
| `QUALITY_PASS_SCORE` | `4` | Lowest acceptable 1-5 review score |
| `MAX_SUMMARY_ATTEMPTS` | `2` | How many times to generate before showing the best result |
| `DB_PATH` | `data/summarizer.db` | SQLite file location |

## Limitations

- Scanned (image-only) PDFs have no extractable text and are rejected.
- Legacy `.doc` files are not supported. Save them as `.docx` first.
