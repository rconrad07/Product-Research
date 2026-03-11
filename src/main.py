"""
main.py
-------
Orchestrator for the Product Research Analyst Agent.

Pipeline:
  1. Curate  — parse all input sources
  2. Research & Skeptic — run in PARALLEL (isolated)
  3. Analyst — synthesize opposing findings
  4. Arbiter — quality gate (schema + citation audit)
  5. RALPH Loop (max 1 retry) — targeted re-invocation for critical/high findings
  6. Report Builder — generate HTML report
  7. URL Validator — silent background check & fix

Usage:
    python -m src.main \\
        --hypothesis "Should we add a comparison tool?" \\
        --inputs inputs/survey.xlsx inputs/article.txt \\
        --url https://example.com/article \\
        --output report.html
"""
import argparse
import concurrent.futures
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from src.curator import Curator
from src.researcher import Researcher
from src.skeptic import Skeptic
from src.analyst import Analyst
from src.report_builder import ReportBuilder
from src.utils import get_logger, make_run_id, LLMClient, extract_json
from src.scripts.url_validator import URLValidator
from src.config.prompts import load_skill_body, load_base_rules
from src.config.settings import AGENT_MODELS, AGENT_TEMPERATURES


# ---------------------------------------------------------------------------
# Arbiter helpers
# ---------------------------------------------------------------------------

def _run_arbiter(logger, run_id: str, pipeline_output: dict) -> dict:
    """Call the Arbiter agent to audit the pipeline output."""
    contracts_path = Path(__file__).parent / "agents" / "schemas" / "agent_contracts.json"
    contracts_text = contracts_path.read_text(encoding="utf-8")

    skill_body = load_skill_body("arbiter")
    base_rules = load_base_rules()
    system = f"<base_rules>\n{base_rules}\n</base_rules>\n\n{skill_body}"

    user = (
        "<input>\nPIPELINE OUTPUT TO AUDIT:\n"
        + json.dumps(pipeline_output, indent=2)[:6000]
        + "\n\nSCHEMA CONTRACTS:\n"
        + contracts_text
        + "\n</input>\n\nReturn your ArbiterOutput JSON now."
    )

    llm = LLMClient(run_id=run_id, agent_name="arbiter")
    raw = llm.complete(
        system=system,
        user=user,
        model=AGENT_MODELS.get("arbiter", AGENT_MODELS["analyst"]),
        temperature=AGENT_TEMPERATURES.get("arbiter", 0.0),
    )
    return extract_json(raw)


def validate_file(file_path: str):
    """Run Arbiter judges against a specific JSON pipeline output file."""
    path = Path(file_path)
    if not path.exists():
        print(f"ERROR: File not found: {file_path}")
        sys.exit(1)

    try:
        pipeline_output = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: Could not parse JSON in {file_path}: {e}")
        sys.exit(1)

    # Remove _meta if present (Gold Standard format)
    if "_meta" in pipeline_output:
        pipeline_output = {k: v for k, v in pipeline_output.items() if k != "_meta"}

    run_id = make_run_id()
    logger = get_logger("validator", run_id)

    print(f"\nAUDITING: {file_path}")
    print("-" * 70)

    arbiter_result = _run_arbiter(logger, run_id, pipeline_output)
    passed = arbiter_result.get("pass", True)
    findings = arbiter_result.get("findings", [])

    if passed:
        print("✅ ARBITER PASSED: Output matches all binary judge criteria.")
    else:
        print(f"❌ ARBITER FAILED: {len(findings)} finding(s) detected.")
        for f in findings:
            print(f"  - [{f['severity'].upper()}] {f['responsible_agent']}: {f['description']}")
    print("-" * 70 + "\n")


# ---------------------------------------------------------------------------
# Re-invocation chains
# ---------------------------------------------------------------------------

# Maps failing agent -> ordered list of agents that must re-run (inclusive)
_REINVOKE_CHAINS: dict[str, list[str]] = {
    "curator":        ["curator", "researcher", "skeptic", "analyst"],
    "researcher":     ["researcher", "analyst"],
    "skeptic":        ["skeptic", "analyst"],
    "analyst":        ["analyst"],
    "report_builder": ["report_builder"],
}


def _upstream_most(agents: list[str]) -> str:
    """Pick the earliest-stage agent in the failing set."""
    order = ["curator", "researcher", "skeptic", "analyst", "report_builder"]
    for a in order:
        if a in agents:
            return a
    return agents[0]


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline(
    hypothesis: str,
    input_sources: list[str],
    search_fn=None,
) -> Path:
    """
    Execute the full research pipeline.

    Args:
        hypothesis:     The product idea or question to research.
        input_sources:  List of file paths or URLs to ingest.
        search_fn:      Optional callable for web search.

    Returns:
        Path to the generated HTML report.
    """
    run_id = make_run_id()
    logger = get_logger("orchestrator", run_id)
    logger.info("\n" + "#"*70 + "\n# [PR ANALYST] - STARTING END-TO-END RESEARCH PIPELINE\n" + "#"*70)
    logger.info("Hypothesis: %s", hypothesis)
    logger.info("Sources: %s", input_sources)
    logger.info("-" * 70)

    # ------------------------------------------------------------------
    # Stage 1: Curate all input sources
    # ------------------------------------------------------------------
    logger.info("\n>> [STAGE 1/6] CURATOR: Ingesting and sanitizing data...")
    curator = Curator(run_id=run_id)
    curated_results: list[dict] = []
    for source in input_sources:
        logger.info("   [In-Progress] Curating: %s", source)
        curated_results.append(curator.curate(source))

    combined_curated = _merge_curated(curated_results)
    logger.info("   [Complete] Curation finished for %d sources.", len(curated_results))

    # ------------------------------------------------------------------
    # Stage 2: Research + Skeptic in PARALLEL
    # ------------------------------------------------------------------
    logger.info("\n>> [STAGE 2/6] PARALLEL RESEARCH: Launching Researcher & Skeptic...")
    researcher = Researcher(run_id=run_id, search_fn=search_fn)
    skeptic = Skeptic(run_id=run_id, search_fn=search_fn)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        future_research = pool.submit(researcher.research, hypothesis, combined_curated)
        future_skeptic = pool.submit(skeptic.review, hypothesis, combined_curated)
        researcher_findings = future_research.result()
        skeptic_findings = future_skeptic.result()

    logger.info("   [Complete] Both research agents have returned findings.")

    # ------------------------------------------------------------------
    # Stage 3: Analyst Synthesis
    # ------------------------------------------------------------------
    logger.info("\n>> [STAGE 3/6] ANALYST: Synthesizing pros and cons...")
    analyst = Analyst(run_id=run_id)
    analyst_output = analyst.analyze(
        hypothesis=hypothesis,
        curated_data=combined_curated,
        researcher_findings=researcher_findings,
        skeptic_findings=skeptic_findings,
    )
    tier = analyst_output.get("recommendation_tier", "UNKNOWN")
    logger.info("   [Complete] Synthesis finished. Recommendation Tier: %s", tier)

    # ------------------------------------------------------------------
    # Stage 4: Arbiter — Quality Gate
    # ------------------------------------------------------------------
    logger.info("\n>> [STAGE 4/6] ARBITER: Auditing pipeline output...")
    pipeline_snapshot = {
        "researcher_output": researcher_findings,
        "skeptic_output": skeptic_findings,
        "analyst_output": analyst_output,
    }
    arbiter_result = _run_arbiter(logger, run_id, pipeline_snapshot)
    arbiter_passed = arbiter_result.get("pass", True)
    findings = arbiter_result.get("findings", [])
    logger.info("   Arbiter pass=%s | findings=%d", arbiter_passed, len(findings))

    # ------------------------------------------------------------------
    # Stage 5: RALPH Loop — max 1 retry for critical/high findings
    # ------------------------------------------------------------------
    if not arbiter_passed:
        actionable = [
            f for f in findings if f.get("severity") in ("critical", "high")
        ]
        if actionable:
            failing_agents = list({f["responsible_agent"] for f in actionable})
            anchor = _upstream_most(failing_agents)
            chain = _REINVOKE_CHAINS.get(anchor, [anchor])
            logger.info(
                "\n>> [STAGE 5/6] RALPH LOOP: Re-invoking chain %s for %d finding(s)...",
                chain, len(actionable),
            )

            if "researcher" in chain:
                researcher_findings = researcher.research(hypothesis, combined_curated)

            if "skeptic" in chain:
                skeptic_findings = skeptic.review(hypothesis, combined_curated)

            if "analyst" in chain:
                analyst_output = analyst.analyze(
                    hypothesis=hypothesis,
                    curated_data=combined_curated,
                    researcher_findings=researcher_findings,
                    skeptic_findings=skeptic_findings,
                )

            logger.info("   [Complete] RALPH retry finished. Chain re-run: %s", chain)
        else:
            logger.info(
                "\n>> [STAGE 5/6] RALPH LOOP: Low-severity findings only — no retry triggered."
            )
    else:
        logger.info(
            "\n>> [STAGE 5/6] RALPH LOOP: Skipped — Arbiter passed on first attempt."
        )

    # ------------------------------------------------------------------
    # Stage 6: Report Generation
    # ------------------------------------------------------------------
    logger.info("\n>> [STAGE 6/6] REPORT BUILDER: Generating final HTML...")
    report_filename = _make_report_filename(hypothesis, run_id)
    report_builder = ReportBuilder(run_id=run_id)
    report_path = report_builder.build(
        hypothesis=hypothesis,
        curated_results=combined_curated,
        analyst_output=analyst_output,
        researcher_findings=researcher_findings,
        skeptic_findings=skeptic_findings,
        output_filename=report_filename,
    )

    # URL Validation (silent, background)
    logger.info("\n>> URL VALIDATOR: Checking & fixing citation URLs...")
    validator = URLValidator(str(report_path))
    if search_fn:
        import src.scripts.url_validator as uv
        uv.search_web = search_fn
    validator.validate_and_fix()

    logger.info("\n" + "="*70)
    logger.info("REPORT READY: %s", report_path)
    logger.info("="*70 + "\n")

    return report_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_report_filename(hypothesis: str, run_id: str) -> str:
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    slug = re.sub(r"[^a-z0-9]+", "-", hypothesis.lower())[:50].strip("-")
    short_id = run_id.split("-")[0] if "-" in run_id else run_id[:12]
    return f"{date_str}_{slug}_{short_id}.html"


def _merge_curated(results: list[dict]) -> dict:
    """Flatten multiple curated source dicts into one combined context."""
    merged = {
        "source_type": "combined",
        "summary": [],
        "key_data_points": [],
        "verbatim_quotes": [],
        "metadata": {},
    }
    for r in results:
        if r.get("summary"):
            merged["summary"].append(r["summary"])
        merged["key_data_points"].extend(r.get("key_data_points", []))
        merged["verbatim_quotes"].extend(r.get("verbatim_quotes", []))
    merged["summary"] = " ".join(merged["summary"])
    return merged


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Product Research Analyst Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--hypothesis",
        help='The product idea to research. E.g. "Should we add a comparison tool?"',
    )
    parser.add_argument(
        "--inputs",
        nargs="*",
        default=[],
        help="One or more local file paths (.xlsx, .csv, .txt, .md)",
    )
    parser.add_argument(
        "--url",
        nargs="*",
        default=[],
        help="One or more article URLs to ingest",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="(Optional) Override the auto-generated report filename.",
    )
    parser.add_argument(
        "--validate",
        help="Run Arbiter judges against a specific JSON pipeline output file.",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run the system calibration against the Gold Standard dataset.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.benchmark:
        from src.scripts.run_calibration import run_calibration
        run_calibration()
        sys.exit(0)

    if args.validate:
        validate_file(args.validate)
        sys.exit(0)

    if not args.hypothesis:
        print("ERROR: --hypothesis is required for the research pipeline.")
        sys.exit(1)

    all_sources = list(args.inputs) + list(args.url)
    if not all_sources:
        print("ERROR: Provide at least one --inputs file or --url.")
        sys.exit(1)

    report_path = run_pipeline(
        hypothesis=args.hypothesis,
        input_sources=all_sources,
    )
    print(f"\n✅ Report generated: {report_path}\n")
