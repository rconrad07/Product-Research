"""
settings.py
-----------
Central configuration for the Product Research Analyst Agent.

NOTE: This agent runs exclusively within Antigravity's IDE.
There are NO external API keys required — the LLM is provided
by the IDE runtime. Only search limits, context limits, and
output paths should be configured here.
"""
import os

# ---------------------------------------------------------------------------
# LLM Configuration
# ---------------------------------------------------------------------------
# Model name is informational only — actual inference is handled by Antigravity.
DEFAULT_MODEL: str = "antigravity-native"

# Per-agent model selection (can override DEFAULT_MODEL)
AGENT_MODELS: dict = {
    "curator":    DEFAULT_MODEL,
    "researcher": DEFAULT_MODEL,
    "skeptic":    DEFAULT_MODEL,
    "analyst":    DEFAULT_MODEL,
    "report_builder": DEFAULT_MODEL,
}

# ---------------------------------------------------------------------------
# Temperature (controls creativity vs. determinism)
# ---------------------------------------------------------------------------
AGENT_TEMPERATURES: dict = {
    "curator":    0.2,   # Deterministic extraction
    "researcher": 0.4,   # Moderate — factual but thorough
    "skeptic":    0.7,   # High creativity — adversarial framing
    "analyst":    0.1,   # Near-deterministic — logical synthesis
    "report_builder": 0.3,
}

# ---------------------------------------------------------------------------
# Search Configuration
# ---------------------------------------------------------------------------
MAX_SEARCH_RESULTS: int = 8        # Max web results per query
MAX_SEARCH_QUERIES: int = 5        # Max queries per agent run

# ---------------------------------------------------------------------------
# Context Management
# ---------------------------------------------------------------------------
MAX_EXCEL_ROWS_TO_ANALYZE: int = 50      # Rows sampled from large spreadsheets
MAX_ARTICLE_CHARS: int = 15_000          # Max chars extracted from a single article
CHUNK_SIZE_CHARS: int = 3_000            # Size of each transcript/article chunk

# ---------------------------------------------------------------------------
# Retry / Resilience
# ---------------------------------------------------------------------------
MAX_RETRIES: int = 3
RETRY_BACKOFF_SECONDS: float = 2.0

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
OUTPUT_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "output")
LOG_DIR: str    = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
