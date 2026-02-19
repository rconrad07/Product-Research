"""
curator.py
----------
Stage 1: Ingests raw source material and returns structured, clean data.

Supported input types:
  - Excel (.xlsx) / CSV
  - Plain text transcripts (.txt / .md)
  - External article URLs (fetches and cleans HTML)
"""
import re
from pathlib import Path
from typing import Any

import requests

from src.config.prompts import CURATOR_SYSTEM, CURATOR_USER
from src.config.settings import (
    AGENT_MODELS,
    AGENT_TEMPERATURES,
    CHUNK_SIZE_CHARS,
    MAX_ARTICLE_CHARS,
    MAX_EXCEL_ROWS_TO_ANALYZE,
)
from src.utils import LLMClient, chunk_text, extract_json


class Curator:
    """
    Reads raw source files or URLs and returns a structured dict
    ready for downstream agents.
    """

    SUPPORTED_EXTENSIONS = {".xlsx", ".csv", ".txt", ".md"}

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.llm = LLMClient(run_id=run_id, agent_name="curator")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def curate(self, source: str | Path) -> dict:
        """
        Main entry point. `source` can be:
          - A local file path (str or Path)
          - A URL string starting with http:// or https://

        Returns a structured dict with keys:
          source_type, summary, key_data_points, verbatim_quotes, metadata
        """
        source_str = str(source)

        if source_str.startswith("http://") or source_str.startswith("https://"):
            return self._curate_url(source_str)

        path = Path(source_str)
        if not path.exists():
            raise FileNotFoundError(f"Source file not found: {path}")

        ext = path.suffix.lower()
        if ext in {".xlsx"}:
            return self._curate_excel(path)
        elif ext == ".csv":
            return self._curate_csv(path)
        elif ext in {".txt", ".md"}:
            return self._curate_text(path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    # ------------------------------------------------------------------
    # Private: File Handlers
    # ------------------------------------------------------------------

    def _curate_excel(self, path: Path) -> dict:
        try:
            import pandas as pd  # noqa: PLC0415
        except ImportError:
            raise ImportError("Install pandas and openpyxl: pip install pandas openpyxl")

        self.llm.logger.info("Curating Excel: %s", path)
        df = pd.read_excel(path)

        schema = df.dtypes.to_string()
        sample_rows = df.head(MAX_EXCEL_ROWS_TO_ANALYZE).to_string(index=False)
        stats = df.describe(include="all").to_string()

        content = (
            f"SCHEMA:\n{schema}\n\n"
            f"SAMPLE ({MAX_EXCEL_ROWS_TO_ANALYZE} rows):\n{sample_rows}\n\n"
            f"STATISTICS:\n{stats}"
        )
        return self._ask_llm("excel_survey", content)

    def _curate_csv(self, path: Path) -> dict:
        try:
            import pandas as pd  # noqa: PLC0415
        except ImportError:
            raise ImportError("Install pandas: pip install pandas")

        self.llm.logger.info("Curating CSV: %s", path)
        df = pd.read_csv(path)
        sample = df.head(MAX_EXCEL_ROWS_TO_ANALYZE).to_string(index=False)
        stats = df.describe(include="all").to_string()
        content = f"SAMPLE:\n{sample}\n\nSTATISTICS:\n{stats}"
        return self._ask_llm("csv_data", content)

    def _curate_text(self, path: Path) -> dict:
        self.llm.logger.info("Curating text file: %s", path)
        text = path.read_text(encoding="utf-8")

        # Chunking strategy for large documents
        if len(text) > CHUNK_SIZE_CHARS:
            self.llm.logger.info(
                "Large transcript (%d chars) — processing in chunks", len(text)
            )
            chunks = chunk_text(text, CHUNK_SIZE_CHARS)
            results = [self._ask_llm("transcript_chunk", chunk) for chunk in chunks]
            return self._merge_curated_results(results)

        return self._ask_llm("transcript", text)

    def _curate_url(self, url: str) -> dict:
        self.llm.logger.info("Fetching article URL: %s", url)
        try:
            response = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Failed to fetch URL {url}: {exc}") from exc

        html = response.text
        # Simple HTML-to-text: strip tags
        clean = re.sub(r"<[^>]+>", " ", html)
        clean = re.sub(r"\s+", " ", clean).strip()
        content = clean[:MAX_ARTICLE_CHARS]

        return self._ask_llm("internet_article", content)

    # ------------------------------------------------------------------
    # LLM Interaction
    # ------------------------------------------------------------------

    def _ask_llm(self, source_type: str, content: str) -> dict:
        user_msg = CURATOR_USER.format(source_type=source_type, content=content)
        raw = self.llm.complete(
            system=CURATOR_SYSTEM,
            user=user_msg,
            model=AGENT_MODELS["curator"],
            temperature=AGENT_TEMPERATURES["curator"],
        )
        return extract_json(raw)

    def _merge_curated_results(self, results: list[dict]) -> dict:
        """Merge multiple chunked curation results into one."""
        merged: dict[str, Any] = {
            "source_type": "transcript_chunked",
            "summary": " ".join(r.get("summary", "") for r in results),
            "key_data_points": [],
            "verbatim_quotes": [],
            "metadata": {},
        }
        for r in results:
            merged["key_data_points"].extend(r.get("key_data_points", []))
            merged["verbatim_quotes"].extend(r.get("verbatim_quotes", []))
        return merged
