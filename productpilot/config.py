"""Central configuration, loaded from environment / .env file."""
from __future__ import annotations

import os
import warnings
from pathlib import Path

from dotenv import load_dotenv

warnings.filterwarnings("ignore", message="The default value of `allowed_objects`")

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.getenv("PP_DATA_DIR", ROOT / "data"))
DB_DIR = DATA_DIR / "db"
SOURCES_DIR = DATA_DIR / "sources"
SEED_DIR = DATA_DIR / "memory_seed"
DB_DIR.mkdir(parents=True, exist_ok=True)

SQLITE_PATH = Path(os.getenv("PP_SQLITE_PATH", DB_DIR / "productpilot.db"))
CHROMA_DIR = Path(os.getenv("PP_CHROMA_DIR", DB_DIR / "chroma"))

# --- behavior ---
MOCK = os.getenv("PRODUCTPILOT_MOCK", "1") not in ("0", "false", "False")
MODEL_SONNET = os.getenv("PP_MODEL_SONNET", "claude-sonnet-4-5")
MODEL_HAIKU = os.getenv("PP_MODEL_HAIKU", "claude-3-5-haiku-latest")
EMBEDDING_MODEL = os.getenv("PP_EMBEDDING_MODEL", "text-embedding-3-small")
CRITIC_THRESHOLD = float(os.getenv("PP_CRITIC_THRESHOLD", "7.0"))
MAX_REVISIONS = int(os.getenv("PP_MAX_REVISIONS", "2"))
TOP_THEMES = int(os.getenv("PP_TOP_THEMES", "6"))
TOP_OPTIONS = int(os.getenv("PP_TOP_OPTIONS", "3"))
MAX_SYNTHESIS_REVISIONS = 2
MAX_PRD_FEEDBACK_REVISIONS = 1

RUBRIC_DIMENSIONS = [
    "problem_clarity",
    "user_segment",
    "measurable_metric",
    "opportunity_size",
    "risk_articulation",
    "dependencies",
    "assumptions",
]
