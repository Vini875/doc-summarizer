"""FastAPI application: upload endpoint, summarize endpoint, and the single-page UI."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .config import BASE_DIR, MAX_FILE_BYTES, MIN_DOCUMENT_WORDS
from .extractors import ExtractionError, extract_text
from .language import is_english
from .summarizer import SummarizationError, count_words, summarize

STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Document Summarizer", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)):
    # Read one byte past the limit so oversized files are detected without reading them fully.
    data = await file.read(MAX_FILE_BYTES + 1)
    try:
        file_type, text = extract_text(file.filename, data)
    except ExtractionError as exc:
        status = 413 if len(data) > MAX_FILE_BYTES else 400
        raise HTTPException(status_code=status, detail=str(exc))

    words = count_words(text)
    if words < MIN_DOCUMENT_WORDS:
        raise HTTPException(
            status_code=400,
            detail=f"The document has only {words} words; at least {MIN_DOCUMENT_WORDS} are needed to summarize.",
        )
    if not is_english(text):
        raise HTTPException(status_code=400, detail="Only English-language documents are accepted.")

    document_id = db.save_document(file.filename, file_type, len(data), words, text)
    return {
        "id": document_id,
        "filename": file.filename,
        "file_type": file_type,
        "size_bytes": len(data),
        "word_count": words,
        "message": "Document uploaded successfully.",
    }


@app.post("/api/documents/{document_id}/summarize")
def summarize_document(document_id: int):
    # Plain `def`: FastAPI runs it in a worker thread, so the blocking Claude call doesn't stall the server.
    document = db.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found. Please upload it again.")
    try:
        result = summarize(document["text"])
    except SummarizationError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    quality = {k: result[k] for k in ("scores", "issues", "passed", "attempts")}
    db.save_summary(document_id, result["abstractive"], result["extractive"], quality, result["model"])
    return result
