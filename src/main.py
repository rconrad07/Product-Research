"""
main.py
-------
Orchestrator for the Product Research Analyst Agent.

Pipeline:
  1. Curate  — parse all input sources
  2. Research & Skeptic — run in PARALLEL (isolated)
  3. Analyst — synthesize opposing findings
  4. Report Builder — generate HTML report

Usage:
    python -m src.main \\
        --hypothesis "Should we add a comparison tool?" \\
        --inputs inputs/survey.xlsx inputs/article.txt \\
        --url https://example.com/article \\
        --output report.html
"""
import argparse
import concurrent.futures
import re
import sys
from datetime import datetime
from pathlib import Path

from src.curator import Curator
from src.researcher import Researcher
from src.skeptic import Skeptic
from src.analyst import Analyst
from src.report_builder import ReportBuilder
from src.utils import get_logger, make_run_id
from src.scripts.url_validator import URLValidator


def _make_report_filename(hypothesis: str, run_id: str) -> str:
    """
    Generate a unique, human-readable filename.
    Format: YYYY-MM-DD_<hypothesis-slug>_<run-id-short>.html
    Example: 2026-02-19_room-selection-list-vs-grid_PRA-20260219.html
    """
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    slug = re.sub(r"[^a-z0-9]+", "-", hypothesis.lower())[:50].strip("-")
    short_id = run_id.split("-")[0] if "-" in run_id else run_id[:12]
    return f"{date_str}_{slug}_{short_id}.html"


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
        search_fn:      Optional callable for web search. If None, a stub
                        is used — see researcher.py for the expected interface.

    Returns:
        Path to the generated HTML report (auto-named from hypothesis + run_id).
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
    logger.info("\n>> [STAGE 1/4] CURATOR: Ingesting and sanitizing data...")
    curator = Curator(run_id=run_id)
    curated_results: list[dict] = []
    for source in input_sources:
        logger.info("   [In-Progress] Curating: %s", source)
        curated = curator.curate(source)
        curated_results.append(curated)

    # Merge into a single context dict for downstream agents
    combined_curated = _merge_curated(curated_results)
    logger.info("   [Complete] Curation finished for %d sources.", len(curated_results))

    # ------------------------------------------------------------------
    # Stage 2: Research + Skeptic in PARALLEL
    # ------------------------------------------------------------------
    logger.info("\n>> [STAGE 2/4] PARALLEL RESEARCH: Launching Researcher & Skeptic...")
    logger.info("   Launching Researcher (Pro-Hypothesis)...")
    logger.info("   Launching Skeptic (Adversarial)...")
    researcher = Researcher(run_id=run_id, search_fn=search_fn)
    skeptic = Skeptic(run_id=run_id, search_fn=search_fn)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        future_research = pool.submit(
            researcher.research, hypothesis, combined_curated
        )
        future_skeptic = pool.submit(
            skeptic.review, hypothesis, combined_curated
        )

        researcher_findings = future_research.result()
        skeptic_findings = future_skeptic.result()

    logger.info("   [Complete] Both research agents have returned findings.")

    # ------------------------------------------------------------------
    # Stage 3: Analyst Synthesis
    # ------------------------------------------------------------------
    logger.info("\n>> [STAGE 3/4] ANALYST: Synthesizing pros and cons...")
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
    # Stage 4: Report Generation
    # ------------------------------------------------------------------
    logger.info("\n>> [STAGE 4/4] REPORT BUILDER: Generating final HTML...")
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

    # ------------------------------------------------------------------
    # Stage 5: URL Validation & Auto-Fix (Silent Background)
    # ------------------------------------------------------------------
    logger.info("\n>> [STAGE 5/5] VALIDATOR: Checking & fixing citation URLs...")
    validator = URLValidator(str(report_path))
    # We monkey-patch the validator's search_web if we have a real search_fn
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
        required=True,
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
    # --output is optional — if omitted, an auto-generated name is used
    parser.add_argument(
        "--output",
        default=None,
        help="(Optional) Override the auto-generated report filename.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    all_sources = list(args.inputs) + list(args.url)
    if not all_sources:
        print("ERROR: Provide at least one --inputs file or --url.")
        sys.exit(1)

    report_path = run_pipeline(
        hypothesis=args.hypothesis,
        input_sources=all_sources,
    )
    print(f"\n✅ Report generated: {report_path}\n")
