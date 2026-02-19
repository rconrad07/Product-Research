"""
analyst.py
----------
Stage 3: Synthesizes findings from Researcher (Pro) and Skeptic (Con)
using Micro vs. Macro pairing and Decision Tree logic.
"""
import json

from src.config.prompts import ANALYST_SYSTEM, ANALYST_USER
from src.config.settings import AGENT_MODELS, AGENT_TEMPERATURES
from src.utils import LLMClient, extract_json


# Possible recommendation tiers output by the Analyst
RECOMMENDATION_TIERS = {
    "STRONG_BUILD": "High confidence — build now.",
    "BUILD_MVP": "Moderate confidence — start lean, validate quickly.",
    "RE_EVALUATE": "Mixed signals — gather more data before committing.",
    "DEPRIORITIZE": "Insufficient support — focus resources elsewhere.",
}

# Decision Tree questions the Analyst must traverse
DECISION_TREE = [
    {
        "id": "USER_DEMAND",
        "question": "Is there significant, evidence-backed user demand for this feature?",
        "yes": "COMPETITOR_LANDSCAPE",
        "no": "DEPRIORITIZE",
    },
    {
        "id": "COMPETITOR_LANDSCAPE",
        "question": "Do competitors already offer a clearly superior version of this feature?",
        "yes": "DIFFERENTIATOR",
        "no": "BUILD_MVP",
    },
    {
        "id": "DIFFERENTIATOR",
        "question": "Can we offer a unique differentiator (e.g., AI personalization, total-price transparency)?",
        "yes": "STRONG_BUILD",
        "no": "RE_EVALUATE",
    },
]


class Analyst:
    """
    Synthesizes the pro/con research findings into a final recommendation.
    Applies Micro vs. Macro pairing and traverses the Decision Tree.
    """

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.llm = LLMClient(run_id=run_id, agent_name="analyst")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        hypothesis: str,
        curated_data: dict,
        researcher_findings: dict,
        skeptic_findings: dict,
    ) -> dict:
        """
        Produce the final synthesis.

        Returns a dict with keys:
          recommendation_tier, micro_macro_pairs, decision_tree_path,
          supporting_summary, skeptic_rebuttal, final_recommendation
        """
        self.llm.logger.info("Analyst starting synthesis for: %s", hypothesis[:120])
        self.llm.logger.info(
            "Researcher context size: %d chars | Skeptic context size: %d chars",
            len(json.dumps(researcher_findings)),
            len(json.dumps(skeptic_findings)),
        )

        user_msg = ANALYST_USER.format(
            hypothesis=hypothesis,
            curated_data=json.dumps(curated_data, indent=2)[:2000],
            researcher_findings=json.dumps(researcher_findings, indent=2)[:2500],
            skeptic_findings=json.dumps(skeptic_findings, indent=2)[:2500],
        )

        # Include the Decision Tree definition so the LLM can explicitly traverse it
        user_msg += (
            f"\n\nDECISION TREE (you must traverse this step-by-step):\n"
            f"{json.dumps(DECISION_TREE, indent=2)}\n\n"
            f"RECOMMENDATION TIER OPTIONS:\n"
            f"{json.dumps(RECOMMENDATION_TIERS, indent=2)}"
        )

        raw = self.llm.complete(
            system=ANALYST_SYSTEM,
            user=user_msg,
            model=AGENT_MODELS["analyst"],
            temperature=AGENT_TEMPERATURES["analyst"],
            max_tokens=6000,
        )

        result = extract_json(raw)
        self._validate_result(result)
        return result

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_result(self, result: dict) -> None:
        required = {
            "recommendation_tier",
            "micro_macro_pairs",
            "decision_tree_path",
            "supporting_summary",
            "skeptic_rebuttal",
            "final_recommendation",
        }
        missing = required - result.keys()
        if missing:
            self.llm.logger.warning(
                "Analyst output missing expected keys: %s", missing
            )
        tier = result.get("recommendation_tier", "")
        if tier not in RECOMMENDATION_TIERS:
            self.llm.logger.warning(
                "Unexpected recommendation_tier '%s'. Will default to RE_EVALUATE.", tier
            )
            result["recommendation_tier"] = "RE_EVALUATE"
