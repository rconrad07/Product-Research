"""
test_analyst.py
---------------
Unit tests for the Analyst module — verifies Decision Tree traversal
and recommendation tier validation using mock LLM responses.
"""
import json
from unittest.mock import MagicMock

import pytest

from src.analyst import Analyst, RECOMMENDATION_TIERS


MOCK_ANALYST_RESPONSE = {
    "recommendation_tier": "STRONG_BUILD",
    "micro_macro_pairs": [
        {
            "micro": "Users want price comparison",
            "macro": "AI personalization is dominant in travel e-commerce",
            "insight": "Feature fits within a major market trend."
        }
    ],
    "decision_tree_path": [
        {"id": "USER_DEMAND", "question": "Significant user demand?", "answer": "Yes"},
        {"id": "COMPETITOR_LANDSCAPE", "question": "Superior competitor feature?", "answer": "No"},
    ],
    "supporting_summary": "Strong survey demand and market opportunity.",
    "skeptic_rebuttal": "Addressed: cost concern outweighed by revenue potential.",
    "final_recommendation": "Build a price comparison tool with AI-driven personalization.",
}


@pytest.fixture()
def mock_analyst():
    analyst = Analyst(run_id="test-run")
    analyst.llm = MagicMock()
    analyst.llm.logger = MagicMock()
    analyst.llm.complete = MagicMock(
        return_value=json.dumps(MOCK_ANALYST_RESPONSE)
    )
    return analyst


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


def test_analyst_decision_tree_path(mock_analyst):
    result = mock_analyst.analyze(
        hypothesis="Add a comparison tool",
        curated_data={},
        researcher_findings={},
        skeptic_findings={},
    )
    path = result.get("decision_tree_path", [])
    assert isinstance(path, list)


def test_analyst_bad_tier_defaults_to_re_evaluate():
    analyst = Analyst(run_id="test-run")
    analyst.llm = MagicMock()
    analyst.llm.logger = MagicMock()
    # Return an invalid tier
    bad_response = dict(MOCK_ANALYST_RESPONSE)
    bad_response["recommendation_tier"] = "INVALID_TIER"
    analyst.llm.complete = MagicMock(return_value=json.dumps(bad_response))

    result = analyst.analyze(
        hypothesis="Test", curated_data={}, researcher_findings={}, skeptic_findings={}
    )
    assert result["recommendation_tier"] == "RE_EVALUATE"
