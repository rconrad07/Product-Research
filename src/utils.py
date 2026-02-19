"""
utils.py
--------
Shared utilities: LLM interface, logger, and retry logic.

NOTE: This agent runs within Antigravity's IDE. There is no
external SDK or API key. The `LLMClient` accepts an injectable
`llm_fn` — Antigravity drives the actual model calls at runtime.
"""
import json
import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config.settings import (
    LOG_DIR,
    MAX_RETRIES,
    RETRY_BACKOFF_SECONDS,
)

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
def get_logger(name: str, run_id: str) -> logging.Logger:
    """Return a logger that writes both to console and to a per-run log file."""
    log_path = Path(LOG_DIR) / f"{run_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(f"{name}.{run_id}")
    if logger.handlers:
        return logger  # Already configured

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("[%(asctime)s] [%(name)s] %(levelname)s :: %(message)s")

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


# ---------------------------------------------------------------------------
# Run ID Generator
# ---------------------------------------------------------------------------
def make_run_id() -> str:
    """Generate a unique RunID for each pipeline execution."""
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    short_uuid = str(uuid.uuid4())[:8]
    return f"PRA-{ts}-{short_uuid}"


# ---------------------------------------------------------------------------
# LLM Client Wrapper
# ---------------------------------------------------------------------------
class LLMClient:
    """
    Thin wrapper around Antigravity's hosted LLM.

    In production (running inside the IDE), `llm_fn` is left as None
    and Antigravity drives inference directly via its runtime.

    For automated testing, inject a mock callable:
        client = LLMClient(run_id, "curator", llm_fn=my_mock)

    The `llm_fn` signature:
        llm_fn(system: str, user: str, model: str, temperature: float) -> str
    """

    def __init__(self, run_id: str, agent_name: str, llm_fn=None):
        self.run_id = run_id
        self.agent_name = agent_name
        self.logger = get_logger(agent_name, run_id)
        # llm_fn is injected at runtime by Antigravity or test mocks.
        # No external SDK is imported or instantiated here.
        self._llm_fn = llm_fn

    def complete(
        self,
        system: str,
        user: str,
        model: str,
        temperature: float,
        max_tokens: int = 4096,
    ) -> str:
        """
        Request a completion from the LLM.

        When running inside Antigravity's IDE, the IDE injects its own
        model at execution time. When testing, provide a mock via `llm_fn`.

        Returns the raw text completion.
        """
        self.logger.debug("PROMPT >>\nSYSTEM: %s\nUSER: %s", system[:300], user[:300])

        if self._llm_fn is None:
            # Antigravity runtime: prompt is emitted to the IDE's model pipeline.
            # This branch is never reached in unit tests (mock is always injected).
            raise RuntimeError(
                f"[{self.agent_name}] No llm_fn provided. "
                "Antigravity must inject its runtime LLM before calling complete()."
            )

        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                completion = self._llm_fn(
                    system=system,
                    user=user,
                    model=model,
                    temperature=temperature,
                )
                self.logger.debug(
                    "COMPLETION (attempt %d) >>\n%s", attempt, completion[:500]
                )
                self._log_trace(system, user, completion, model, temperature)
                return completion

            except Exception as exc:  # noqa: BLE001
                last_error = exc
                wait = RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
                self.logger.warning(
                    "LLM call failed (attempt %d/%d): %s — retrying in %.1fs",
                    attempt, MAX_RETRIES, exc, wait,
                )
                time.sleep(wait)

        raise RuntimeError(
            f"[{self.agent_name}] LLM call failed after {MAX_RETRIES} attempts: {last_error}"
        )

    def _log_trace(
        self, system: str, user: str, completion: str, model: str, temperature: float
    ) -> None:
        """Persist a structured trace of every LLM call to the logs directory."""
        trace = {
            "run_id": self.run_id,
            "agent": self.agent_name,
            "model": model,
            "temperature": temperature,
            "timestamp": datetime.utcnow().isoformat(),
            "system_prompt_chars": len(system),
            "user_prompt_chars": len(user),
            "completion_chars": len(completion),
        }
        trace_path = Path(LOG_DIR) / f"{self.run_id}_traces.jsonl"
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        with open(trace_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace) + "\n")


# ---------------------------------------------------------------------------
# JSON Extraction Helpers
# ---------------------------------------------------------------------------
def extract_json(text: str) -> dict:
    """
    Attempt to parse JSON from LLM output.
    LLMs often wrap JSON in markdown fences — this handles that.
    """
    # Strip markdown fences if present
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        stripped = "\n".join(lines[1:-1])

    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse LLM output as JSON: {exc}\n\nRaw output:\n{text}") from exc


def chunk_text(text: str, chunk_size: int) -> list[str]:
    """Split a long text into overlapping chunks for context management."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start += int(chunk_size * 0.9)  # 10% overlap
    return chunks
