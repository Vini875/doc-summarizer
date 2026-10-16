"""Central configuration, read from environment variables (or a .env file)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Claude Sonnet 5.5 is the medium tier of the Claude family (between Haiku and Opus).
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
CLAUDE_EFFORT = os.getenv("CLAUDE_EFFORT", "medium")

MAX_FILE_BYTES = 1 * 1024 * 1024  # 1 MB, applies to .docx, .txt and .pdf alike
ALLOWED_EXTENSIONS = {".docx", ".txt", ".pdf"}

MAX_SUMMARY_WORDS = 350
MIN_DOCUMENT_WORDS = 40
ENGLISH_MIN_PROBABILITY = float(os.getenv("ENGLISH_MIN_PROBABILITY", "0.80"))

# Quality gate: every relevance/correctness/completeness score (1-5) must reach this.
QUALITY_PASS_SCORE = int(os.getenv("QUALITY_PASS_SCORE", "4"))
MAX_SUMMARY_ATTEMPTS = int(os.getenv("MAX_SUMMARY_ATTEMPTS", "2"))

DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "data" / "summarizer.db"))
