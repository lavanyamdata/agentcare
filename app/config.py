"""
config.py — Central configuration loaded from environment variables.

Every value that can change between environments lives here.
No config scattered across files. Fails loudly at startup if 
required keys are missing — better to crash early than fail silently.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env file (dev only — in production env vars come from the host)
load_dotenv()


def _require(key: str) -> str:
    """Raise clearly if a required env var is missing."""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            f"Copy .env.example to .env and fill in your values."
        )
    return value


# ── LLM ──────────────────────────────────────────────────────────────
GROQ_API_KEY: str = _require("GROQ_API_KEY")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# ── Database ──────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./agentcare.db")

# ── App ───────────────────────────────────────────────────────────────
SECRET_KEY: str = _require("SECRET_KEY")
APP_ENV: str = os.getenv("APP_ENV", "development")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ── Document storage ──────────────────────────────────────────────────
UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_SIZE_BYTES: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10")) * 1024 * 1024

# ── Agent config ──────────────────────────────────────────────────────
AGENT_MAX_RETRIES: int = int(os.getenv("AGENT_MAX_RETRIES", "3"))
AGENT_TIMEOUT_SECONDS: int = int(os.getenv("AGENT_TIMEOUT_SECONDS", "60"))

# ── Logging setup ─────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("agentcare")
logger.info("Configuration loaded | env=%s | model=%s", APP_ENV, GROQ_MODEL)