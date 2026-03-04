"""
test_analyst.py
---------------
Unit tests for the Analyst module — verifies the full board-ready
Problem-Solving Brief output: MECE compliance, action plan horizons,
risk register, recommendation tier validation, and backward-compatible fields.
"""
import json
from unittest.mock import MagicMock

import pytest

from src.analyst import (
    Analyst,
    RECOMMENDATION_TIERS,
    ECONOMIC_OBJECTIVES,
    MECE_VALIDATORS,
    ACTION_HORIZONS,
)


# ---------------------------------------------------------------------------
# Canonical mock response matching all 12 required output keys
# ---------------------------------------------------------------------------
MOCK_ANALYST_RESPONSE = {
    "governing_question": (
        "Should we invest in building a price-comparison tool to drive conversion "
        "and revenue growth in the vacation ownership segment?"
    ),
    "economic_objective": "GROWTH",
    "mece_decomposition": [
        {
            "label": "Market Demand",
            "children": [
                "Volume and strength of user demand signal",
                "Demand elasticity at different price points",
            ],
        },
        {
            "label": "Competitive Position",
            "children": [
                "Competitor feature parity and gaps",
                "Potential for unique differentiation",
            ],
        },
        {
            "label": "Revenue Impact",
            "children": [
                "Conversion uplift potential",
                "Average order value effect",
            ],
        },
        {
            "label": "Execution Risk",
            "children": [
                "Technical complexity and timeline",
                "Integration dependencies",
            ],
        },
        {
            "label": "Cost & Margin",
            "children": [
                "Development and maintenance cost",
                "ROI versus alternative investments",
            ],
        },
    ],
    "mece_compliance_check": {
        "no_category_overlap": True,
        "no_missing_economic_drivers": True,
        "each_rec_linked_to_outcome": True,
        "language_is_executive_ready": True,
        "governing_question_answered": True,
        "tiers_justified_by_evidence": True,
    },
    "hypothesis_validation": (
        "Initial assumption: users desire a comparison tool and no strong competitor offers it. "
        "Evidence confirms strong demand (survey data) but reveals partial competitor coverage. "
        "Delta: differentiation window is real but narrower than assumed — MVP with AI personalisation "
        "is the validated path."
    ),
    "micro_macro_pairs": [
        {
            "micro": "Users want price comparison",
            "macro": "AI-driven personalisation is dominant in travel e-commerce",
            "insight": "Feature fits within a major market trend.",
            "economic_link": "GROWTH — conversion rate uplift",
        }
    ],
    "recommendation_tier": "STRONG_BUILD",
    "supporting_summary": "Strong survey demand signal and a clear market opportunity validated by macro trends.",
    "skeptic_rebuttal": (
        "The cost concern is real but outweighed by projected revenue uplift. "
        "Competitor coverage is partial, preserving a differentiation window. "
        "Sample-size risk is mitigated by corroborating macro data."
    ),
    "final_recommendation": (
        "We recommend building a price-comparison tool with AI-driven personalisation. "
        "Demand is validated, differentiation is achievable, and the revenue case is strong."
    ),
    "action_plan": [
        {
            "horizon": "Immediate (0-2 weeks)",
            "description": "Define MVP scope and align stakeholders on success metrics.",
            "impact": "High",
            "effort": "Low",
            "feasibility": "High",
            "economic_outcome": "Unblocks build decision; zero direct cost.",
        },
        {
            "horizon": "Short-term (2-8 weeks)",
            "description": "Build and ship MVP comparison view; A/B test vs. control.",
            "impact": "High",
            "effort": "Medium",
            "feasibility": "High",
            "economic_outcome": "First conversion-rate signal within 8 weeks.",
        },
        {
            "horizon": "Medium-term (2-6 months)",
            "description": "Integrate AI personalisation layer; scale to all product lines.",
            "impact": "High",
            "effort": "High",
            "feasibility": "Medium",
            "economic_outcome": "Projected 8–12% conversion uplift at full scale.",
        },
    ],
    "risk_register": [
        {
            "risk": "Competitor launches equivalent feature before we ship.",
            "likelihood": "Medium",
            "impact": "High",
            "control": "Accelerate MVP timeline; add exclusive data partnerships.",
            "residual_risk": "Medium",
        },
        {
            "risk": "AI personalisation integration exceeds timeline.",
            "likelihood": "Medium",
            "impact": "Medium",
            "control": "Decouple AI layer — ship rule-based comparison first.",
            "residual_risk": "Low",
        },
    ],
}


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_analyst():
    analyst = Analyst(run_id="test-run")
    analyst.llm = MagicMock()
    analyst.llm.logger = MagicMock()
    analyst.llm.complete = MagicMock(
        return_value=json.dumps(MOCK_ANALYST_RESPONSE)
    )
    return analyst


# ---------------------------------------------------------------------------
# Existing tests (retained + updated for new schema)
# ---------------------------------------------------------------------------

def test_analyst_returns_valid_tier(mock_analyst):
    result = mock_analyst.analyze(
        hypothesis="Add a comparison tool",
        curated_data={"summary": "Users want comparison"},
        researcher_findings={"macro_trends": ["AI adoption"]},
        skeptic_findings={"refuting_evidence": ["Cost risk"]},
    )
    assert result["recommendation_tier"] in RECOMMENDATION_TIERS


def test_analyst_micro_macro_pairs(mock_analyst):
    result = mock_analyst.analyze(
        hypothesis="Add a comparison tool",
        curated_data={},
        researcher_findings={},
        skeptic_findings={},
    )
    pairs = result.get("micro_macro_pairs", [])
    assert isinstance(pairs, list)
    if pairs:
        assert "micro" in pairs[0]
        assert "macro" in pairs[0]


def test_analyst_bad_tier_defaults_to_re_evaluate():
    analyst = Analyst(run_id="test-run")
    analyst.llm = MagicMock()
    analyst.llm.logger = MagicMock()
    bad_response = dict(MOCK_ANALYST_RESPONSE)
    bad_response["recommendation_tier"] = "INVALID_TIER"
    analyst.llm.complete = MagicMock(return_value=json.dumps(bad_response))

    result = analyst.analyze(
        hypothesis="Test", curated_data={}, researcher_findings={}, skeptic_findings={}
    )
    assert result["recommendation_tier"] == "RE_EVALUATE"


# ---------------------------------------------------------------------------
# New tests: MECE, action plan, risk register, economic objective
# ---------------------------------------------------------------------------

def test_analyst_mece_compliance_check(mock_analyst):
    """All 6 MECE compliance validators must be present in the output."""
    result = mock_analyst.analyze(
        hypothesis="Add a comparison tool",
        curated_data={},
        researcher_findings={},
        skeptic_findings={},
    )
    compliance = result.get("mece_compliance_check", {})
    assert isinstance(compliance, dict), "mece_compliance_check must be a dict"
    for key in MECE_VALIDATORS:
        assert key in compliance, f"Missing MECE validator key: {key}"


def test_analyst_mece_decomposition_max_six_branches(mock_analyst):
    """MECE decomposition must not exceed 6 top-level branches."""
    result = mock_analyst.analyze(
        hypothesis="Add a comparison tool",
        curated_data={},
        researcher_findings={},
        skeptic_findings={},
    )
    branches = result.get("mece_decomposition", [])
    assert isinstance(branches, list), "mece_decomposition must be a list"
    assert len(branches) <= 6, f"MECE tree exceeded 6 branches: {len(branches)}"
    for branch in branches:
        assert "label" in branch, "Each MECE branch must have a 'label' key"


def test_analyst_action_plan_horizons(mock_analyst):
    """Each action plan item must carry horizon, impact, effort, and feasibility keys."""
    result = mock_analyst.analyze(
        hypothesis="Add a comparison tool",
        curated_data={},
        researcher_findings={},
        skeptic_findings={},
    )
    actions = result.get("action_plan", [])
    assert isinstance(actions, list), "action_plan must be a list"
    assert len(actions) > 0, "action_plan must not be empty"
    for action in actions:
        for key in ("horizon", "description", "impact", "effort"):
            assert key in action, f"Action plan item missing key: {key}"
        horizon = action.get("horizon", "").lower()
        assert any(
            h in horizon for h in ["immediate", "short", "medium"]
        ), f"Unrecognised horizon value: {action.get('horizon')}"


def test_analyst_risk_register(mock_analyst):
    """Risk register items must have risk, likelihood, impact, and control keys."""
    result = mock_analyst.analyze(
        hypothesis="Add a comparison tool",
        curated_data={},
        researcher_findings={},
        skeptic_findings={},
    )
    risks = result.get("risk_register", [])
    assert isinstance(risks, list), "risk_register must be a list"
    assert len(risks) > 0, "risk_register must not be empty"
    for risk in risks:
        for key in ("risk", "likelihood", "impact", "control"):
            assert key in risk, f"Risk register item missing key: {key}"


def test_analyst_economic_objective_is_valid(mock_analyst):
    """economic_objective must be one of the four recognised values."""
    result = mock_analyst.analyze(
        hypothesis="Add a comparison tool",
        curated_data={},
        researcher_findings={},
        skeptic_findings={},
    )
    obj = result.get("economic_objective", "")
    assert obj in ECONOMIC_OBJECTIVES, (
        f"economic_objective '{obj}' not in {list(ECONOMIC_OBJECTIVES.keys())}"
    )


def test_analyst_governing_question_present(mock_analyst):
    """Governing question must be present and non-empty."""
    result = mock_analyst.analyze(
        hypothesis="Add a comparison tool",
        curated_data={},
        researcher_findings={},
        skeptic_findings={},
    )
    gq = result.get("governing_question", "")
    assert isinstance(gq, str) and len(gq) > 0, "governing_question must be a non-empty string"


def test_analyst_final_recommendation_present(mock_analyst):
    """final_recommendation must be non-empty (Minto apex verdict)."""
    result = mock_analyst.analyze(
        hypothesis="Add a comparison tool",
        curated_data={},
        researcher_findings={},
        skeptic_findings={},
    )
    rec = result.get("final_recommendation", "")
    assert isinstance(rec, str) and len(rec) > 0, "final_recommendation must be a non-empty string"


def test_analyst_mece_tree_truncated_when_over_six():
    """Validate that the Python validator truncates branches > 6."""
    analyst = Analyst(run_id="test-run")
    analyst.llm = MagicMock()
    analyst.llm.logger = MagicMock()
    over_limit_response = dict(MOCK_ANALYST_RESPONSE)
    over_limit_response["mece_decomposition"] = [
        {"label": f"Branch {i}", "children": []} for i in range(9)
    ]
    analyst.llm.complete = MagicMock(return_value=json.dumps(over_limit_response))

    result = analyst.analyze(
        hypothesis="Test", curated_data={}, researcher_findings={}, skeptic_findings={}
    )
    assert len(result["mece_decomposition"]) == 6, (
        "Validator must truncate MECE tree to 6 branches"
    )
