"""
run_calibration.py
------------------
Measures the accuracy of the three binary Arbiter judges against the
Gold Standard dataset in Evals/Gold_Standard/.

Metrics reported:
  TPR (True Positive Rate / Sensitivity):
      How often does the judge correctly return pass=True for a known-good sample?
  TNR (True Negative Rate / Specificity):
      How often does the judge correctly return pass=False for a known-bad sample?

Usage:
    python -m src.scripts.run_calibration

The script uses a rule-based (programmatic) evaluation — no LLM call required.
This matches the "Automated Validation Scripts" best practice from eval_best_practices.md.
"""
import json
import re
import sys
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
GOLD_PASS_DIR = REPO_ROOT / "Evals" / "Gold_Standard" / "pass"
GOLD_FAIL_DIR = REPO_ROOT / "Evals" / "Gold_Standard" / "fail"
CONTRACTS_PATH = REPO_ROOT / "src" / "agents" / "schemas" / "agent_contracts.json"

VALID_ECONOMIC_OBJECTIVES = {"GROWTH", "MARGIN", "CASH", "VALUATION"}
VALID_RECOMMENDATION_TIERS = {"STRONG_BUILD", "BUILD_MVP", "RE_EVALUATE", "DEPRIORITIZE"}
VALID_HORIZONS = {"Immediate", "Short-term", "Medium-term"}
MECE_COMPLIANCE_KEYS = {
    "no_category_overlap", "no_missing_economic_drivers",
    "each_rec_linked_to_outcome", "language_is_executive_ready",
    "governing_question_answered", "tiers_justified_by_evidence",
}
MAX_MECE_BRANCHES = 6


# ---------------------------------------------------------------------------
# Programmatic Judge Implementations
# ---------------------------------------------------------------------------

def _has_url_path(url: str) -> bool:
    """Return True if URL has a non-empty path component beyond the root domain."""
    path = re.sub(r"https?://[^/]+", "", url).strip("/")
    return bool(path)


def judge_url_integrity(pipeline: dict) -> dict:
    """
    Programmatic implementation of the URL Integrity Judge.
    Returns a dict: {pass: bool, findings: list}
    """
    findings = []
    for agent in ("researcher_output", "skeptic_output"):
        responsible = agent.replace("_output", "")
        sources = pipeline.get(agent, {}).get("sources", [])
        evidence = pipeline.get(agent, {}).get("supporting_evidence", []) + \
                   pipeline.get(agent, {}).get("refuting_evidence", [])

        for src in sources:
            url = src.get("url", "")
            url_verbatim = src.get("url_verbatim", "")
            if not _has_url_path(url):
                findings.append({
                    "severity": "critical",
                    "responsible_agent": responsible,
                    "description": f"[URL Integrity] Source URL '{url}' is a root domain with no path component.",
                })
            if url_verbatim != url:
                findings.append({
                    "severity": "critical",
                    "responsible_agent": responsible,
                    "description": f"[URL Integrity] url_verbatim '{url_verbatim}' does not match url '{url}'.",
                })

        for ev in evidence:
            url = ev.get("source_url", "")
            if not _has_url_path(url):
                findings.append({
                    "severity": "critical",
                    "responsible_agent": responsible,
                    "description": f"[URL Integrity] Evidence source_url '{url}' is a root domain with no path component.",
                })

    return {"pass": len(findings) == 0, "findings": findings}


def judge_schema_compliance(pipeline: dict) -> dict:
    """Programmatic implementation of the Schema Compliance Judge."""
    findings = []
    analyst = pipeline.get("analyst_output", {})

    # Required top-level keys
    analyst_required_keys = [
        "governing_question", "economic_objective", "mece_decomposition",
        "mece_compliance_check", "hypothesis_validation", "micro_macro_pairs",
        "recommendation_tier", "supporting_summary", "skeptic_rebuttal",
        "final_recommendation", "action_plan", "risk_register",
    ]
    for key in analyst_required_keys:
        if key not in analyst or analyst[key] is None or analyst[key] == "" or analyst[key] == []:
            findings.append({
                "severity": "critical",
                "responsible_agent": "analyst",
                "description": f"[Schema Compliance] analyst_output missing required key '{key}'.",
            })

    # Enum validation
    eco_obj = analyst.get("economic_objective", "")
    if eco_obj not in VALID_ECONOMIC_OBJECTIVES:
        findings.append({
            "severity": "critical",
            "responsible_agent": "analyst",
            "description": f"[Schema Compliance] 'economic_objective' value '{eco_obj}' is invalid. Must be one of: {sorted(VALID_ECONOMIC_OBJECTIVES)}.",
        })

    rec_tier = analyst.get("recommendation_tier", "")
    if rec_tier not in VALID_RECOMMENDATION_TIERS:
        findings.append({
            "severity": "critical",
            "responsible_agent": "analyst",
            "description": f"[Schema Compliance] 'recommendation_tier' value '{rec_tier}' is invalid. Must be one of: {sorted(VALID_RECOMMENDATION_TIERS)}.",
        })

    # mece_compliance_check keys
    mcc = analyst.get("mece_compliance_check", {})
    missing_mcc = MECE_COMPLIANCE_KEYS - set(mcc.keys())
    for k in missing_mcc:
        findings.append({
            "severity": "critical",
            "responsible_agent": "analyst",
            "description": f"[Schema Compliance] mece_compliance_check missing required boolean key '{k}'.",
        })

    # action_plan sub-keys
    action_plan_keys = {"horizon", "description", "impact", "effort", "feasibility", "economic_outcome"}
    for i, action in enumerate(analyst.get("action_plan", [])):
        missing = action_plan_keys - set(action.keys())
        for k in missing:
            findings.append({
                "severity": "high",
                "responsible_agent": "analyst",
                "description": f"[Schema Compliance] action_plan[{i}] missing required key '{k}'.",
            })

    # risk_register sub-keys
    risk_keys = {"risk", "likelihood", "impact", "control", "residual_risk"}
    for i, risk in enumerate(analyst.get("risk_register", [])):
        missing = risk_keys - set(risk.keys())
        for k in missing:
            findings.append({
                "severity": "high",
                "responsible_agent": "analyst",
                "description": f"[Schema Compliance] risk_register[{i}] missing required key '{k}'.",
            })

    return {"pass": all(f["severity"] not in ("critical", "high") for f in findings), "findings": findings}


def judge_alignment(pipeline: dict) -> dict:
    """Programmatic implementation of the Alignment Judge."""
    findings = []
    analyst = pipeline.get("analyst_output", {})

    # MECE compliance booleans
    mcc = analyst.get("mece_compliance_check", {})
    for key, value in mcc.items():
        if value is False:
            findings.append({
                "severity": "high",
                "responsible_agent": "analyst",
                "description": f"[Alignment] mece_compliance_check['{key}'] is false.",
            })

    # MECE branch cap
    branches = analyst.get("mece_decomposition", [])
    if len(branches) > MAX_MECE_BRANCHES:
        findings.append({
            "severity": "high",
            "responsible_agent": "analyst",
            "description": f"[Alignment] mece_decomposition has {len(branches)} branches, exceeding the cap of {MAX_MECE_BRANCHES}.",
        })

    # Action plan horizons
    for i, action in enumerate(analyst.get("action_plan", [])):
        horizon = action.get("horizon", "")
        if horizon not in VALID_HORIZONS:
            findings.append({
                "severity": "low",
                "responsible_agent": "analyst",
                "description": f"[Alignment] action_plan[{i}] has unrecognised horizon '{horizon}'. Must be one of: {sorted(VALID_HORIZONS)}.",
            })

    passed = all(f["severity"] not in ("critical", "high") for f in findings)
    return {"pass": passed, "findings": findings}


# ---------------------------------------------------------------------------
# Calibration Runner
# ---------------------------------------------------------------------------

JUDGES = {
    "url_integrity": judge_url_integrity,
    "schema_compliance": judge_schema_compliance,
    "alignment": judge_alignment,
}


def _evaluate_sample(
    sample_path: Path, expected_outcome: Literal["pass", "fail"]
) -> dict:
    """Run all judges on a single sample and return per-judge verdicts."""
    data = json.loads(sample_path.read_text(encoding="utf-8"))
    meta = data.get("_meta", {})
    # Remove _meta before passing to judges
    pipeline = {k: v for k, v in data.items() if k != "_meta"}

    results = {}
    for judge_name, judge_fn in JUDGES.items():
        result = judge_fn(pipeline)
        actual = "pass" if result["pass"] else "fail"
        correct = actual == expected_outcome
        results[judge_name] = {
            "expected": expected_outcome,
            "actual": actual,
            "correct": correct,
            "findings_count": len(result["findings"]),
        }
    return {"file": sample_path.name, "meta": meta, "judges": results}


def run_calibration() -> None:
    print("\n" + "=" * 70)
    print("  CALIBRATION RUN — Arbiter Judge Accuracy Report")
    print("=" * 70)

    # Collect samples
    pass_samples = sorted(GOLD_PASS_DIR.glob("*.json")) if GOLD_PASS_DIR.exists() else []
    fail_samples = sorted(GOLD_FAIL_DIR.glob("*.json")) if GOLD_FAIL_DIR.exists() else []

    if not pass_samples and not fail_samples:
        print("\n[ERROR] No Gold Standard samples found.")
        print(f"  Expected pass samples in: {GOLD_PASS_DIR}")
        print(f"  Expected fail samples in: {GOLD_FAIL_DIR}")
        sys.exit(1)

    all_results = []
    for path in pass_samples:
        all_results.append(_evaluate_sample(path, "pass"))
    for path in fail_samples:
        all_results.append(_evaluate_sample(path, "fail"))

    # Compute per-judge metrics
    judge_stats: dict[str, dict] = {name: {"TP": 0, "TN": 0, "FP": 0, "FN": 0} for name in JUDGES}

    for r in all_results:
        for judge_name, verdict in r["judges"].items():
            expected = verdict["expected"]
            actual = verdict["actual"]
            stats = judge_stats[judge_name]
            if expected == "pass" and actual == "pass":
                stats["TP"] += 1
            elif expected == "fail" and actual == "fail":
                stats["TN"] += 1
            elif expected == "pass" and actual == "fail":
                stats["FP"] += 1
            elif expected == "fail" and actual == "pass":
                stats["FN"] += 1

    # Print per-sample detail
    sep = "-" * 60
    print()
    for r in all_results:
        expected = r["judges"][list(JUDGES.keys())[0]]["expected"].upper()
        print(f"  [{expected}] {r['file']}")
        for name in JUDGES:
            verdict = r["judges"][name]
            icon = "PASS" if verdict["correct"] else "FAIL"
            actual = verdict["actual"].upper()
            symbol = "✅" if verdict["correct"] else "❌"
            print(f"    {symbol} {name:<25} -> {icon} (actual={actual}, findings={verdict['findings_count']})")
        print()

    # Print metrics table
    print("=" * 60)
    print("  JUDGE METRICS")
    print("=" * 60)

    for name, stats in judge_stats.items():
        tp, tn, fp, fn = stats["TP"], stats["TN"], stats["FP"], stats["FN"]
        tpr = tp / (tp + fn) if (tp + fn) > 0 else float("nan")
        tnr = tn / (tn + fp) if (tn + fp) > 0 else float("nan")
        acc = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else float("nan")
        print(f"\n  {name.replace('_', ' ').title()}")
        print(f"    TPR (Sensitivity): {tpr:.0%}  ({tp} TP / {fn} FN)")
        print(f"    TNR (Specificity): {tnr:.0%}  ({tn} TN / {fp} FP)")
        print(f"    Accuracy:          {acc:.0%}")

    print()
    total_samples = len(all_results)
    print(f"  Total: {total_samples} samples ({len(pass_samples)} pass, {len(fail_samples)} fail)")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_calibration()
