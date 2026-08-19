import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_DIR = DATA_DIR / "db"
LOG_DIR = BASE_DIR / "logs"
WEB_SEARCH_RESULTS_DIR = DATA_DIR / "web_search_results"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
WEB_SEARCH_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

APP_NAME = os.getenv("APP_NAME", "RAG MVP Backend")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300"))

VECTOR_DB_MODE = os.getenv("VECTOR_DB_MODE", "lite")
MILVUS_LITE_PATH = os.getenv("MILVUS_LITE_PATH", str(DATA_DIR / "milvus_lite.db"))
MILVUS_URI = os.getenv("MILVUS_URI", "http://localhost:19530")

SEARXNG_BASE_URL = os.getenv("SEARXNG_BASE_URL", "http://localhost:8080").rstrip("/")
SEARXNG_TIMEOUT = float(os.getenv("SEARXNG_TIMEOUT", "30"))

SQLITE_FILENAME = os.getenv("SQLITE_FILENAME", "app.db")
SQLITE_PATH = str(DB_DIR / SQLITE_FILENAME)
