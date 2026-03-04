"""
analyst.py
----------
Stage 3: Synthesizes findings from Researcher (Pro) and Skeptic (Con) using:
  - Minto Pyramid Principle (answer first, then grouped support)
  - MECE Problem Decomposition (6 branches max, no overlap, no gaps)
  - Hypothesis-Driven Analysis anchored in macroeconomic drivers
  - Board-Level Communication Standards (decisive, fact-based, quantified)
"""
import json

from src.config.prompts import ANALYST_SYSTEM, ANALYST_USER
from src.config.settings import AGENT_MODELS, AGENT_TEMPERATURES
from src.utils import LLMClient, extract_json


# ---------------------------------------------------------------------------
# Recommendation tiers (Minto apex verdict)
# ---------------------------------------------------------------------------
RECOMMENDATION_TIERS = {
    "STRONG_BUILD":  "High confidence — build now. Economic case is clear.",
    "BUILD_MVP":     "Moderate confidence — start lean, validate quickly.",
    "RE_EVALUATE":   "Mixed signals — gather more data before committing.",
    "DEPRIORITIZE":  "Insufficient support — focus resources elsewhere.",
}

# ---------------------------------------------------------------------------
# Primary economic objective the Analyst must identify
# ---------------------------------------------------------------------------
ECONOMIC_OBJECTIVES = {
    "GROWTH":      "Revenue growth / market share expansion",
    "MARGIN":      "Profitability / cost efficiency improvement",
    "CASH":        "Cash flow / working capital optimisation",
    "VALUATION":   "Enterprise value / investor confidence",
}

# ---------------------------------------------------------------------------
# MECE compliance validators the LLM must explicitly confirm
# Returned under the key `mece_compliance_check` in the output JSON.
# ---------------------------------------------------------------------------
MECE_VALIDATORS = {
    "no_category_overlap":          "No two branches of the problem decomposition overlap",
    "no_missing_economic_drivers":  "All major economic drivers relevant to the hypothesis are covered",
    "each_rec_linked_to_outcome":   "Every recommendation links to a measurable economic outcome",
    "language_is_executive_ready":  "Language is decisive, quantified, and free of unnecessary hedging",
    "governing_question_answered":  "The governing question is directly answered by the recommendation",
    "tiers_justified_by_evidence":  "The recommendation tier is explicitly justified by cited evidence",
}

# ---------------------------------------------------------------------------
# Action plan time horizons and rating options
# ---------------------------------------------------------------------------
ACTION_HORIZONS = ["Immediate (0-2 weeks)", "Short-term (2-8 weeks)", "Medium-term (2-6 months)"]
RATING_SCALE = ["High", "Medium", "Low"]

# ---------------------------------------------------------------------------
# Full required output schema (12 keys)
# ---------------------------------------------------------------------------
REQUIRED_OUTPUT_KEYS = {
    "governing_question":       "Single decision question the brief must answer",
    "economic_objective":       "Primary driver: GROWTH | MARGIN | CASH | VALUATION",
    "mece_decomposition":       "List of MECE problem tree nodes (max 6 branches), each with 'label' and 'children'",
    "mece_compliance_check":    "Dict with 6 boolean keys confirming MECE / board-readiness",
    "hypothesis_validation":    "Hypothesis vs. evidence: what was assumed, what was found, delta",
    "micro_macro_pairs":        "List of {micro, macro, insight, economic_link} objects",
    "recommendation_tier":      "STRONG_BUILD | BUILD_MVP | RE_EVALUATE | DEPRIORITIZE",
    "supporting_summary":       "Key supporting evidence narrative",
    "skeptic_rebuttal":         "Explicit rebuttal of top 3 skeptic challenges",
    "final_recommendation":     "Minto apex: 1–2 sentence board-ready verdict",
    "action_plan":              "List of {horizon, description, impact, effort, feasibility, economic_outcome}",
    "risk_register":            "List of {risk, likelihood, impact, control, residual_risk}",
}


class Analyst:
    """
    Synthesizes pro/con research findings into a board-ready Problem-Solving Brief.

    Applies:
      - Minto Pyramid Principle (conclusion-first structure)
      - MECE problem decomposition (max 6 branches)
      - Hypothesis-driven analysis anchored in macroeconomic drivers
      - Explicit pre-recommendation compliance checklist
      - Prioritised action plan across three time horizons
      - Risk register with control logic
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
        Produce the final Problem-Solving Brief.

        Returns a dict with the 12 keys defined in REQUIRED_OUTPUT_KEYS.
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

        # Inject framework scaffolding so the LLM can traverse each requirement explicitly
        user_msg += (
            f"\n\nECONOMIC OBJECTIVE OPTIONS:\n"
            f"{json.dumps(ECONOMIC_OBJECTIVES, indent=2)}\n\n"
            f"MECE COMPLIANCE VALIDATORS (you must confirm all 6 before concluding):\n"
            f"{json.dumps(MECE_VALIDATORS, indent=2)}\n\n"
            f"ACTION PLAN HORIZONS: {ACTION_HORIZONS}\n"
            f"RATING SCALE (Impact / Effort / Feasibility): {RATING_SCALE}\n\n"
            f"RECOMMENDATION TIER OPTIONS:\n"
            f"{json.dumps(RECOMMENDATION_TIERS, indent=2)}\n\n"
            f"REQUIRED OUTPUT SCHEMA (return all 12 keys):\n"
            f"{json.dumps(REQUIRED_OUTPUT_KEYS, indent=2)}"
        )

        raw = self.llm.complete(
            system=ANALYST_SYSTEM,
            user=user_msg,
            model=AGENT_MODELS["analyst"],
            temperature=AGENT_TEMPERATURES["analyst"],
            max_tokens=8000,
        )

        result = extract_json(raw)
        self._validate_result(result)
        return result

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_result(self, result: dict) -> None:
        """Enforce schema completeness and log warnings on missing keys or invalid tiers."""
        missing = set(REQUIRED_OUTPUT_KEYS.keys()) - result.keys()
        if missing:
            self.llm.logger.warning(
                "Analyst output missing expected keys: %s", missing
            )

        # Validate recommendation tier
        tier = result.get("recommendation_tier", "")
        if tier not in RECOMMENDATION_TIERS:
            self.llm.logger.warning(
                "Unexpected recommendation_tier '%s'. Defaulting to RE_EVALUATE.", tier
            )
            result["recommendation_tier"] = "RE_EVALUATE"

        # Validate economic objective
        obj = result.get("economic_objective", "")
        if obj not in ECONOMIC_OBJECTIVES:
            self.llm.logger.warning(
                "Unexpected economic_objective '%s'. Defaulting to GROWTH.", obj
            )
            result["economic_objective"] = "GROWTH"

        # Enforce MECE branch cap
        mece = result.get("mece_decomposition", [])
        if isinstance(mece, list) and len(mece) > 6:
            self.llm.logger.warning(
                "MECE decomposition exceeded 6 branches (%d). Truncating.", len(mece)
            )
            result["mece_decomposition"] = mece[:6]

        # Validate action plan horizons
        action_plan = result.get("action_plan", [])
        for action in action_plan:
            horizon = action.get("horizon", "")
            if not any(h.lower() in horizon.lower() for h in ["immediate", "short", "medium"]):
                self.llm.logger.warning(
                    "Action plan item has unrecognised horizon: '%s'", horizon
                )

        # Validate MECE compliance check keys
        compliance = result.get("mece_compliance_check", {})
        missing_compliance = set(MECE_VALIDATORS.keys()) - set(compliance.keys())
        if missing_compliance:
            self.llm.logger.warning(
                "mece_compliance_check is missing keys: %s", missing_compliance
            )
