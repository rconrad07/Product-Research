"""
researcher.py
-------------
Stage 2a (PARALLEL): Searches the internet for evidence to SUPPORT the hypothesis.
This agent is isolated — it does not communicate with the Skeptic.
"""
import json
import time
from typing import Any

from src.config.prompts import RESEARCHER_SYSTEM, RESEARCHER_USER
from src.config.settings import (
    AGENT_MODELS,
    AGENT_TEMPERATURES,
    MAX_SEARCH_QUERIES,
    MAX_SEARCH_RESULTS,
    RETRY_BACKOFF_SECONDS,
)
from src.utils import LLMClient, extract_json


class Researcher:
    """
    Generates and executes web search queries aimed at validating
    the user's hypothesis with macro-trend data and competitor examples.
    """

    def __init__(self, run_id: str, search_fn=None):
        """
        Args:
            run_id: Unique pipeline run identifier.
            search_fn: Callable that takes a query string and returns a list of
                       result dicts with keys: 'title', 'url', 'snippet'.
                       Defaults to a stub that logs and returns empty results
                       (replace with real integration at runtime).
        """
        self.run_id = run_id
        self.llm = LLMClient(run_id=run_id, agent_name="researcher")
        self._search = search_fn or self._default_search

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def research(self, hypothesis: str, curated_data: dict) -> dict:
        """
        Find supporting evidence for `hypothesis`.

        Returns a dict with keys:
          macro_trends, supporting_evidence, competitor_examples
        """
        self.llm.logger.info("Researcher starting for hypothesis: %s", hypothesis[:120])

        # Ask LLM to generate targeted search queries
        queries = self._generate_queries(hypothesis, curated_data)
        self.llm.logger.info("Generated %d search queries", len(queries))

        # Execute searches and collect snippets + raw source metadata
        search_context, raw_results = self._run_searches(queries)

        # Ask LLM to synthesize supporting findings
        return self._synthesize(hypothesis, curated_data, search_context, raw_results)

    # ------------------------------------------------------------------
    # Query Generation
    # ------------------------------------------------------------------

    def _generate_queries(self, hypothesis: str, curated_data: dict) -> list[str]:
        prompt = (
            f"You are helping research the following hypothesis:\n\"{hypothesis}\"\n\n"
            f"User data context:\n{json.dumps(curated_data, indent=2)[:1500]}\n\n"
            f"Generate up to {MAX_SEARCH_QUERIES} targeted web search queries to find "
            f"supporting evidence, macro trends, and competitor success stories. "
            f"Return ONLY a JSON array of query strings."
        )
        raw = self.llm.complete(
            system="You are a research query generator. Return only a JSON array of strings.",
            user=prompt,
            model=AGENT_MODELS["researcher"],
            temperature=AGENT_TEMPERATURES["researcher"],
        )
        try:
            queries = extract_json(raw)
            if isinstance(queries, list):
                return queries[:MAX_SEARCH_QUERIES]
        except ValueError:
            pass
        # Fallback: single generic query
        return [f"market trends supporting {hypothesis}"]

    # ------------------------------------------------------------------
    # Search Execution
    # ------------------------------------------------------------------

    def _run_searches(self, queries: list[str]) -> tuple[str, list[dict]]:
        """
        Execute each query, return:
          - a formatted text block for LLM context
          - the raw result list for citation tracking
        """
        blocks: list[str] = []
        raw_results: list[dict] = []
        for q in queries:
            results = self._search(q)
            self.llm.logger.debug("Query '%s' → %d results", q, len(results))
            for r in results[:MAX_SEARCH_RESULTS]:
                title = r.get("title", "")
                url = r.get("url", "")
                snippet = r.get("snippet", "")
                blocks.append(f"SOURCE: {title}\nURL: {url}\nSNIPPET: {snippet}")
                raw_results.append({"title": title, "url": url, "snippet": snippet})
            time.sleep(0.5)  # Polite rate limiting
        return "\n\n".join(blocks), raw_results

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    def _synthesize(
        self, hypothesis: str, curated_data: dict, search_context: str, raw_results: list[dict]
    ) -> dict:
        user_msg = RESEARCHER_USER.format(
            hypothesis=hypothesis,
            curated_data=json.dumps(curated_data, indent=2)[:2000],
        ) + (
            f"\n\nSEARCH RESULTS (cite these by URL in your output):\n{search_context[:4000]}"
            "\n\nIMPORTANT: Every claim you make MUST reference a URL from the above results. "
            "DO NOT fabricate statistics or quotes. If no source supports a claim, say so."
        )

        raw = self.llm.complete(
            system=RESEARCHER_SYSTEM,
            user=user_msg,
            model=AGENT_MODELS["researcher"],
            temperature=AGENT_TEMPERATURES["researcher"],
        )
        result = extract_json(raw)
        # Ensure raw search sources are always preserved in output
        if "sources" not in result or not result["sources"]:
            result["sources"] = raw_results
        return result

    # ------------------------------------------------------------------
    # Default search stub (replace with real implementation)
    # ------------------------------------------------------------------

    def _default_search(self, query: str) -> list[dict]:
        """
        Stub search function. In production, replace this with a live
        web search integration (e.g., SerpAPI, Brave Search, Tavily).
        """
        self.llm.logger.warning(
            "Using stub search — no real results returned for query: '%s'. "
            "Inject a real search_fn into Researcher().",
            query,
        )
        return []
