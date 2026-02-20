"""
skeptic.py
----------
Stage 2b (PARALLEL): Searches the internet for evidence to REFUTE the hypothesis.
This agent is fully isolated from the Researcher — no shared context.
"""
import json
import time
from typing import Any

from src.config.prompts import SKEPTIC_SYSTEM, SKEPTIC_USER
from src.config.settings import (
    AGENT_MODELS,
    AGENT_TEMPERATURES,
    MAX_SEARCH_QUERIES,
    MAX_SEARCH_RESULTS,
)
from src.utils import LLMClient, extract_json


class Skeptic:
    """
    Adversarial QA agent. Finds conflicting external data, exposes data gaps,
    and challenges the hypothesis's viability from a contrarian perspective.
    """

    def __init__(self, run_id: str, search_fn=None):
        self.run_id = run_id
        self.llm = LLMClient(run_id=run_id, agent_name="skeptic")
        self._search = search_fn or self._default_search

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def review(self, hypothesis: str, curated_data: dict) -> dict:
        """
        Find refuting evidence against `hypothesis`.

        Returns a dict with keys:
          refuting_evidence, data_gaps, risk_factors, contrarian_macro_trends
        """
        self.llm.logger.info(
            "Skeptic starting adversarial review for: %s", hypothesis[:120]
        )

        queries = self._generate_adversarial_queries(hypothesis, curated_data)
        self.llm.logger.info("Generated %d adversarial queries", len(queries))
        search_context, raw_results = self._run_searches(queries)

        return self._synthesize(hypothesis, curated_data, search_context, raw_results)

    # ------------------------------------------------------------------
    # Query Generation
    # ------------------------------------------------------------------

    def _generate_adversarial_queries(
        self, hypothesis: str, curated_data: dict
    ) -> list[str]:
        prompt = (
            f"You are a product skeptic challenging this hypothesis:\n\"{hypothesis}\"\n\n"
            f"User data context:\n{json.dumps(curated_data, indent=2)[:1500]}\n\n"
            f"Generate up to {MAX_SEARCH_QUERIES} web search queries to find "
            f"evidence that CONTRADICTS the hypothesis. Focus on: failed competitor "
            f"features, market saturation, consumer churn, negative trends. "
            f"Return ONLY a JSON array of query strings."
        )
        raw = self.llm.complete(
            system="You are an adversarial research query generator. Return only a JSON array of strings.",
            user=prompt,
            model=AGENT_MODELS["skeptic"],
            temperature=AGENT_TEMPERATURES["skeptic"],
        )
        try:
            queries = extract_json(raw)
            if isinstance(queries, list):
                return queries[:MAX_SEARCH_QUERIES]
        except ValueError:
            pass
        return [f"problems with {hypothesis} failures market saturation"]

    # ------------------------------------------------------------------
    # Search Execution
    # ------------------------------------------------------------------

    def _run_searches(self, queries: list[str]) -> tuple[str, list[dict]]:
        blocks: list[str] = []
        raw_results: list[dict] = []
        for q in queries:
            results = self._search(q)
            self.llm.logger.debug("Adversarial query '%s' → %d results", q, len(results))
            for r in results[:MAX_SEARCH_RESULTS]:
                title = r.get("title", "")
                url = r.get("url", "")
                snippet = r.get("snippet", "")
                blocks.append(f"SOURCE: {title}\nURL: {url}\nSNIPPET: {snippet}")
                raw_results.append({"title": title, "url": url, "snippet": snippet})
            time.sleep(0.5)
        return "\n\n".join(blocks), raw_results

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    def _synthesize(
        self, hypothesis: str, curated_data: dict, search_context: str, raw_results: list[dict]
    ) -> dict:
        user_msg = SKEPTIC_USER.format(
            hypothesis=hypothesis,
            curated_data=json.dumps(curated_data, indent=2)[:2000],
        ) + (
            f"\n\nSEARCH RESULTS (cite these by URL in your output):\n{search_context[:4000]}"
            "\n\nIMPORTANT: Every refuting claim MUST reference a URL from the above results. "
            "DO NOT fabricate statistics or quotes. If no source refutes a claim, say so."
        )

        raw = self.llm.complete(
            system=SKEPTIC_SYSTEM,
            user=user_msg,
            model=AGENT_MODELS["skeptic"],
            temperature=AGENT_TEMPERATURES["skeptic"],
        )
        result = extract_json(raw)
        # Ensure raw search sources are always preserved in output
        if "sources" not in result or not result["sources"]:
            result["sources"] = raw_results
        return result

    # ------------------------------------------------------------------
    # Default search stub
    # ------------------------------------------------------------------

    def _default_search(self, query: str) -> list[dict]:
        self.llm.logger.warning(
            "Using stub search — no real results for adversarial query: '%s'. "
            "Inject a real search_fn into Skeptic().",
            query,
        )
        return []
