"""
report_builder.py
-----------------
Stage 4: Converts the Analyst's structured Problem-Solving Brief into a premium,
board-ready HTML report for Steering Committee review.

Sections (Minto Pyramid order):
  1. Board Recommendation (governing conclusion — Minto apex)
  2. Executive Summary
  3. Problem Framing (governing question + economic objective + hypothesis validation)
  4. MECE Problem Decomposition (max 6 branches) + Compliance Check
  5. Macro-Evidence Synthesis (micro → macro pairs)
  6. Supporting Evidence
  7. Skeptic's Challenges (rebuttal)
  8. Prioritised Action Plan (3 horizons × Impact/Effort/Feasibility)
  9. Risk Register
  10. Sources & References
"""
import json
import re
from datetime import datetime
from pathlib import Path

from src.config.prompts import REPORT_BUILDER_SYSTEM, REPORT_BUILDER_USER
from src.config.settings import AGENT_MODELS, AGENT_TEMPERATURES, OUTPUT_DIR
from src.utils import LLMClient


# ---------------------------------------------------------------------------
# Tier styling
# ---------------------------------------------------------------------------
TIER_STYLES = {
    "STRONG_BUILD":  {"color": "#16a34a", "bg": "#f0fdf4", "label": "✅ Build Now"},
    "BUILD_MVP":     {"color": "#d97706", "bg": "#fffbeb", "label": "⚠️ Build MVP"},
    "RE_EVALUATE":   {"color": "#7c3aed", "bg": "#f5f3ff", "label": "🔄 Re-evaluate"},
    "DEPRIORITIZE":  {"color": "#dc2626", "bg": "#fef2f2", "label": "🚫 Deprioritize"},
}

# Economic objective badge colours
ECON_OBJ_STYLES = {
    "GROWTH":    {"color": "#1d4ed8", "bg": "#eff6ff", "icon": "📈"},
    "MARGIN":    {"color": "#b45309", "bg": "#fffbeb", "icon": "💹"},
    "CASH":      {"color": "#15803d", "bg": "#f0fdf4", "icon": "💰"},
    "VALUATION": {"color": "#7c3aed", "bg": "#f5f3ff", "icon": "🏦"},
}

# H/M/L rating colours for action matrix
RATING_COLORS = {
    "high":   "#22c55e",
    "medium": "#d97706",
    "low":    "#dc2626",
}


class ReportBuilder:
    """
    Uses an LLM to draft the full report body, then injects it into a
    polished HTML shell with guaranteed structure and board-ready styling.
    """

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.llm = LLMClient(run_id=run_id, agent_name="report_builder")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        hypothesis: str,
        curated_results: list[dict],
        analyst_output: dict,
        researcher_findings: dict | None = None,
        skeptic_findings: dict | None = None,
        output_filename: str = "report.html",
    ) -> Path:
        """
        Generate and write the HTML Problem-Solving Brief.
        Returns the Path to the written file.
        """
        self.llm.logger.info("Report Builder generating board-ready Problem-Solving Brief...")

        researcher_findings = researcher_findings or {}
        skeptic_findings = skeptic_findings or {}

        # Ask the LLM to generate the narrative HTML body sections
        narrative = self._generate_narrative(hypothesis, analyst_output)

        # Assemble the full HTML shell
        html = self._build_html(
            hypothesis, analyst_output, narrative,
            researcher_findings, skeptic_findings
        )

        out_path = Path(OUTPUT_DIR) / output_filename
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")

        self.llm.logger.info("Report written to: %s", out_path)
        return out_path

    # ------------------------------------------------------------------
    # Narrative Generation
    # ------------------------------------------------------------------

    def _generate_narrative(self, hypothesis: str, analyst_output: dict) -> dict:
        user_msg = REPORT_BUILDER_USER.format(
            hypothesis=hypothesis,
            analyst_output=json.dumps(analyst_output, indent=2)[:5000],
            run_id=self.run_id,
            timestamp=datetime.utcnow().isoformat(),
        )
        raw = self.llm.complete(
            system=REPORT_BUILDER_SYSTEM,
            user=user_msg,
            model=AGENT_MODELS["report_builder"],
            temperature=AGENT_TEMPERATURES["report_builder"],
            max_tokens=10000,
        )
        try:
            from src.utils import extract_json  # noqa: PLC0415
            data = extract_json(raw)
            # Sanitize narrative text: remove Markdown artifacts like **bold** or *italics*
            for key in ["executive_summary", "problem_framing_section", "mece_section", 
                        "macro_evidence_section", "supporting_section", "skeptic_section",
                        "action_plan_section", "risk_register_section", "recommendation_section"]:
                if key in data and isinstance(data[key], str):
                    # Strip ** and * but keep the text
                    data[key] = re.sub(r'\*\*([^*]+)\*\*', r'\1', data[key])
                    data[key] = re.sub(r'\*([^*]+)\*', r'\1', data[key])
            return data
        except ValueError:
            # Fallback for plain text, strip markdown too
            clean_raw = re.sub(r'\*\*([^*]+)\*\*', r'\1', raw)
            clean_raw = re.sub(r'\*([^*]+)\*', r'\1', clean_raw)
            return {"executive_summary": clean_raw}

    # ------------------------------------------------------------------
    # HTML Shell
    # ------------------------------------------------------------------

    def _build_html(
        self,
        hypothesis: str,
        analyst_output: dict,
        narrative: dict,
        researcher_findings: dict,
        skeptic_findings: dict,
    ) -> str:
        tier = analyst_output.get("recommendation_tier", "RE_EVALUATE")
        tier_style = TIER_STYLES.get(tier, TIER_STYLES["RE_EVALUATE"])
        econ_obj = analyst_output.get("economic_objective", "GROWTH")
        econ_style = ECON_OBJ_STYLES.get(econ_obj, ECON_OBJ_STYLES["GROWTH"])
        timestamp = datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")

        # Pre-render structured components from structured JSON
        mece_tree_html = self._render_mece_tree(
            analyst_output.get("mece_decomposition", [])
        )
        mece_check_html = self._render_mece_compliance(
            analyst_output.get("mece_compliance_check", {})
        )
        micro_macro_rows = self._render_micro_macro(
            analyst_output.get("micro_macro_pairs", [])
        )
        action_matrix_html = self._render_action_matrix(
            analyst_output.get("action_plan", [])
        )
        risk_register_html = self._render_risk_register(
            analyst_output.get("risk_register", [])
        )
        support_sources_html = self._render_sources(
            researcher_findings.get("sources", []), "support"
        )
        refute_sources_html = self._render_sources(
            skeptic_findings.get("sources", []), "refute"
        )
        support_quotes_html = self._render_blockquotes(
            researcher_findings.get("sources", []), "support"
        )
        refute_quotes_html = self._render_blockquotes(
            skeptic_findings.get("sources", []), "refute"
        )
        hypothesis_validation = analyst_output.get("hypothesis_validation", "")
        governing_question = analyst_output.get("governing_question", hypothesis)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Problem-Solving Brief — {hypothesis[:60]}</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet" />
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --bg: #0f1117;
      --surface: #1a1d27;
      --surface2: #22263a;
      --border: #2e3350;
      --text: #e2e8f0;
      --muted: #8892a4;
      --green: #22c55e;
      --red: #ef4444;
      --amber: #d97706;
      --purple: #a78bfa;
      --blue: #60a5fa;
      --accent: #6366f1;
      --sidebar-w: 270px;
    }}
    body {{
      font-family: 'Inter', sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      min-height: 100vh;
    }}
    /* ---- Sidebar ---- */
    nav#sidebar {{
      position: fixed;
      top: 0; left: 0;
      width: var(--sidebar-w);
      height: 100vh;
      background: var(--surface);
      border-right: 1px solid var(--border);
      padding: 2rem 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
      overflow-y: auto;
    }}
    nav#sidebar .brand {{
      font-size: 0.7rem;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 1.25rem;
    }}
    nav#sidebar .section-group {{
      font-size: 0.65rem;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--muted);
      margin: 0.85rem 0 0.25rem 0.25rem;
    }}
    nav#sidebar a {{
      display: block;
      padding: 0.45rem 0.75rem;
      border-radius: 8px;
      color: var(--muted);
      text-decoration: none;
      font-size: 0.82rem;
      font-weight: 500;
      transition: background 0.15s, color 0.15s;
    }}
    nav#sidebar a:hover {{ background: var(--surface2); color: var(--text); }}
    /* ---- Main content ---- */
    main {{
      margin-left: var(--sidebar-w);
      padding: 3rem 3.5rem;
      max-width: 980px;
      width: 100%;
    }}
    /* ---- Recommendation Banner (Minto Apex) ---- */
    .rec-banner {{
      background: {tier_style['bg']};
      border: 2px solid {tier_style['color']};
      border-radius: 14px;
      padding: 1.75rem 2rem;
      margin-bottom: 2.5rem;
    }}
    .rec-banner .tier {{
      font-size: 1.55rem;
      font-weight: 700;
      color: {tier_style['color']};
    }}
    .rec-banner .hyp {{
      font-size: 0.88rem;
      color: #475569;
      margin-top: 0.35rem;
      font-style: italic;
    }}
    .rec-banner .verdict {{
      margin-top: 0.85rem;
      font-size: 1.05rem;
      color: #1e293b;
      line-height: 1.65;
      font-weight: 500;
    }}
    /* ---- Economic Objective Badge ---- */
    .econ-badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      background: {econ_style['bg']};
      color: {econ_style['color']};
      border: 1px solid {econ_style['color']}33;
      border-radius: 999px;
      padding: 0.3rem 0.85rem;
      font-size: 0.8rem;
      font-weight: 700;
      letter-spacing: 0.05em;
      margin-top: 0.75rem;
    }}
    /* ---- Sections ---- */
    section {{ margin-bottom: 3rem; }}
    h1 {{ font-size: 1.85rem; font-weight: 700; margin-bottom: 0.25rem; }}
    h2 {{
      font-size: 1.2rem; font-weight: 600; color: var(--text);
      margin-bottom: 1rem; padding-bottom: 0.5rem;
      border-bottom: 1px solid var(--border);
    }}
    h3 {{ font-size: 1rem; font-weight: 600; color: var(--text); margin-bottom: 0.5rem; }}
    p, li {{ font-size: 0.93rem; line-height: 1.72; color: var(--muted); }}
    ul {{ padding-left: 1.25rem; }}
    /* ---- Governing Question Block ---- */
    .governing-q {{
      background: var(--surface);
      border-left: 4px solid var(--accent);
      border-radius: 0 10px 10px 0;
      padding: 1rem 1.5rem;
      margin-bottom: 1.25rem;
    }}
    .governing-q .label {{
      font-size: 0.68rem;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 0.4rem;
    }}
    .governing-q p {{
      font-size: 1rem;
      font-weight: 600;
      color: var(--text);
      line-height: 1.5;
    }}
    /* ---- Hypothesis Validation ---- */
    .hyp-validation {{
      background: var(--surface2);
      border-radius: 10px;
      padding: 1rem 1.5rem;
      margin-top: 1rem;
      font-size: 0.9rem;
      color: var(--muted);
      line-height: 1.7;
    }}
    /* ---- MECE Tree ---- */
    .mece-tree {{
      background: var(--surface);
      border-radius: 10px;
      padding: 1.25rem 1.5rem;
      margin-bottom: 1.25rem;
    }}
    .mece-tree ul {{ list-style: none; padding: 0; margin: 0; }}
    .mece-tree > ul > li {{
      border-left: 3px solid var(--accent);
      padding: 0.6rem 0 0.6rem 1rem;
      margin-bottom: 0.75rem;
      border-radius: 0 6px 6px 0;
    }}
    .mece-tree > ul > li:last-child {{ margin-bottom: 0; }}
    .mece-branch-label {{
      font-weight: 700;
      font-size: 0.9rem;
      color: var(--text);
      margin-bottom: 0.35rem;
    }}
    .mece-tree > ul > li > ul {{
      list-style: none;
      padding-left: 1rem;
      margin-top: 0.35rem;
    }}
    .mece-tree > ul > li > ul > li {{
      font-size: 0.83rem;
      color: var(--muted);
      padding: 0.2rem 0;
      display: flex;
      align-items: flex-start;
      gap: 0.5rem;
    }}
    .mece-tree > ul > li > ul > li::before {{
      content: "└ ";
      color: var(--border);
      font-family: monospace;
      font-size: 0.9rem;
      flex-shrink: 0;
    }}
    /* ---- MECE Compliance Checklist ---- */
    .mece-check {{ margin-top: 1.25rem; }}
    .mece-check-item {{
      display: flex;
      align-items: center;
      gap: 0.6rem;
      padding: 0.4rem 0;
      border-bottom: 1px solid var(--border);
      font-size: 0.85rem;
      color: var(--muted);
    }}
    .mece-check-item:last-child {{ border-bottom: none; }}
    .check-icon {{ font-size: 1rem; flex-shrink: 0; }}
    /* ---- Evidence Cards ---- */
    .card-grid {{ display: grid; gap: 1rem; }}
    .card {{
      background: var(--surface);
      border-radius: 10px;
      padding: 1.2rem 1.5rem;
      border-left: 4px solid var(--border);
    }}
    .card.support {{ border-left-color: var(--green); }}
    .card.refute  {{ border-left-color: var(--red); }}
    .card .label {{
      font-size: 0.68rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 0.4rem;
    }}
    .card.support .label {{ color: var(--green); }}
    .card.refute  .label {{ color: var(--red); }}
    .card p {{ margin-top: 0.25rem; }}
    /* ---- Macro-Evidence Table ---- */
    table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
    th {{ background: var(--surface2); color: var(--text); padding: 0.65rem 1rem; text-align: left; font-weight: 600; }}
    td {{ padding: 0.65rem 1rem; border-top: 1px solid var(--border); color: var(--muted); vertical-align: top; }}
    td.micro {{ color: var(--purple); font-style: italic; }}
    td.econ-link {{ color: var(--blue); font-size: 0.8rem; font-weight: 600; }}
    /* ---- Horizon Dividers ---- */
    .horizon-heading {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin: 1.75rem 0 0.85rem;
    }}
    .horizon-heading .horizon-label {{
      font-size: 0.75rem;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      padding: 0.3rem 0.85rem;
      border-radius: 999px;
      white-space: nowrap;
    }}
    .horizon-immediate {{ background: #fee2e2; color: #991b1b; }}
    .horizon-short     {{ background: #fef3c7; color: #92400e; }}
    .horizon-medium    {{ background: #dbeafe; color: #1e40af; }}
    .horizon-heading hr {{ flex: 1; border: none; border-top: 1px solid var(--border); }}
    /* ---- Action Matrix ---- */
    .action-matrix-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    .action-matrix-table th {{ background: var(--surface2); color: var(--text); padding: 0.6rem 0.9rem; font-weight: 600; text-align: left; }}
    .action-matrix-table td {{ padding: 0.6rem 0.9rem; border-top: 1px solid var(--border); color: var(--muted); vertical-align: top; }}
    .rating-cell {{
      display: inline-block;
      padding: 0.15rem 0.55rem;
      border-radius: 999px;
      font-size: 0.75rem;
      font-weight: 700;
      color: white;
    }}
    .rating-high   {{ background: #16a34a; }}
    .rating-medium {{ background: #b45309; }}
    .rating-low    {{ background: #b91c1c; }}
    .outcome-cell {{ font-size: 0.8rem; color: var(--blue); font-style: italic; }}
    /* ---- Risk Register ---- */
    .risk-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    .risk-table th {{ background: var(--surface2); color: var(--text); padding: 0.6rem 0.9rem; font-weight: 600; text-align: left; }}
    .risk-table td {{ padding: 0.6rem 0.9rem; border-top: 1px solid var(--border); color: var(--muted); vertical-align: top; }}
    .risk-high   {{ background: #7f1d1d22; border-left: 3px solid #ef4444; }}
    .risk-medium {{ background: #78350f22; border-left: 3px solid #d97706; }}
    .risk-low    {{ background: #14532d22; border-left: 3px solid #22c55e; }}
    .risk-badge {{
      display: inline-block;
      padding: 0.1rem 0.5rem;
      border-radius: 999px;
      font-size: 0.73rem;
      font-weight: 700;
      color: white;
    }}
    .risk-badge-high   {{ background: #b91c1c; }}
    .risk-badge-medium {{ background: #b45309; }}
    .risk-badge-low    {{ background: #15803d; }}
    /* ---- Blockquotes ---- */
    blockquote {{
      border-left: 4px solid var(--accent);
      margin: 1rem 0;
      padding: 0.75rem 1.25rem;
      background: var(--surface2);
      border-radius: 0 8px 8px 0;
      font-style: italic;
      color: var(--muted);
    }}
    blockquote cite {{
      display: block;
      margin-top: 0.5rem;
      font-size: 0.8rem;
      font-style: normal;
      color: var(--accent);
    }}
    blockquote.support-quote {{ border-left-color: var(--green); }}
    blockquote.refute-quote  {{ border-left-color: var(--red); }}
    /* ---- Sources ---- */
    .sources-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.5rem;
      margin-top: 1rem;
    }}
    .sources-col h3 {{
      font-size: 0.82rem;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      margin-bottom: 0.75rem;
    }}
    .sources-col.support h3 {{ color: var(--green); }}
    .sources-col.refute  h3 {{ color: var(--red); }}
    .source-link {{ display: flex; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.6rem; font-size: 0.83rem; }}
    .source-link .dot {{ min-width: 8px; height: 8px; border-radius: 50%; margin-top: 5px; }}
    .source-link .dot.support {{ background: var(--green); }}
    .source-link .dot.refute  {{ background: var(--red); }}
    .source-link a {{ color: var(--muted); text-decoration: none; }}
    .source-link a:hover {{ color: var(--text); text-decoration: underline; }}
    .unverified-link {{ color: var(--muted) !important; text-decoration: line-through !important; opacity: 0.7; }}
    .unverified-label {{ font-size: 0.7rem; color: var(--red); font-style: italic; font-weight: 600; margin-left: 4px; opacity: 0.8; }}
    .meta {{ font-size: 0.8rem; color: var(--muted); margin-bottom: 2rem; }}
    .run-id {{ font-family: monospace; color: var(--accent); }}
  </style>
</head>
<body>

<nav id="sidebar">
  <div class="brand">Problem-Solving Brief</div>
  <span class="section-group">Recommendation</span>
  <a href="#recommendation">🎯 Board Recommendation</a>
  <a href="#executive-summary">📋 Executive Summary</a>
  <span class="section-group">Problem Structure</span>
  <a href="#problem-framing">🔎 Problem Framing</a>
  <a href="#mece">🌲 MECE Decomposition</a>
  <span class="section-group">Evidence</span>
  <a href="#macro-evidence">🔗 Macro-Evidence Synthesis</a>
  <a href="#supporting">✅ Supporting Evidence</a>
  <a href="#skeptic">🚫 Skeptic's Challenges</a>
  <span class="section-group">Execution</span>
  <a href="#action-plan">⚡ Action Plan</a>
  <a href="#risk-register">⚠️ Risk Register</a>
  <span class="section-group">References</span>
  <a href="#sources">📎 Sources</a>
</nav>

<main>
  <h1>Problem-Solving Brief</h1>
  <div class="meta">
    Prepared for Steering Committee &nbsp;|&nbsp; {timestamp} &nbsp;|&nbsp; Run ID: <span class="run-id">{self.run_id}</span>
  </div>

  <!-- ① BOARD RECOMMENDATION (Minto Apex — answer first) -->
  <section id="recommendation">
    <div class="rec-banner">
      <div class="tier">{tier_style['label']}</div>
      <div class="econ-badge">{econ_style['icon']} Primary Economic Objective: {econ_obj}</div>
      <div class="hyp"><strong>Hypothesis under review:</strong> {hypothesis}</div>
      <div class="verdict">{analyst_output.get('final_recommendation', '—')}</div>
    </div>
  </section>

  <!-- ② EXECUTIVE SUMMARY -->
  <section id="executive-summary">
    <h2>📋 Executive Summary</h2>
    {narrative.get('executive_summary', '<p>See full analysis below.</p>')}
  </section>

  <!-- ③ PROBLEM FRAMING -->
  <section id="problem-framing">
    <h2>🔎 Problem Framing</h2>
    <div class="governing-q">
      <div class="label">Governing Question</div>
      <p>{governing_question}</p>
    </div>
    <div class="hyp-validation">
      <strong style="color:var(--text);font-size:0.8rem;letter-spacing:0.06em;text-transform:uppercase;">
        Hypothesis Validation
      </strong>
      <p style="margin-top:0.5rem">{hypothesis_validation if isinstance(hypothesis_validation, str) else json.dumps(hypothesis_validation)}</p>
    </div>
    {narrative.get('problem_framing_section', '')}
  </section>

  <!-- ④ MECE PROBLEM DECOMPOSITION -->
  <section id="mece">
    <h2>🌲 MECE Problem Decomposition</h2>
    <div class="mece-tree">
      {mece_tree_html}
    </div>
    {narrative.get('mece_section', '')}
    <div class="mece-check">
      <h3 style="margin-bottom:0.75rem;font-size:0.85rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--muted);">
        Pre-Recommendation Compliance Check
      </h3>
      {mece_check_html}
    </div>
  </section>

  <!-- ⑤ MACRO-EVIDENCE SYNTHESIS -->
  <section id="macro-evidence">
    <h2>🔗 Macro-Evidence Synthesis</h2>
    <table>
      <thead>
        <tr>
          <th>Micro (User Signal)</th>
          <th>Macro (Market Driver)</th>
          <th>Insight</th>
          <th>Economic Link</th>
        </tr>
      </thead>
      <tbody>
        {micro_macro_rows}
      </tbody>
    </table>
    {narrative.get('macro_evidence_section', '')}
  </section>

  <!-- ⑥ SUPPORTING EVIDENCE -->
  <section id="supporting">
    <h2>✅ Supporting Evidence</h2>
    <div class="card-grid">
      {self._render_evidence_cards(analyst_output.get('supporting_summary', ''), 'support')}
    </div>
    {support_quotes_html}
    {narrative.get('supporting_section', '')}
  </section>

  <!-- ⑦ SKEPTIC'S CHALLENGES -->
  <section id="skeptic">
    <h2>🚫 Skeptic's Challenges &amp; Rebuttal</h2>
    <div class="card-grid">
      {self._render_evidence_cards(analyst_output.get('skeptic_rebuttal', ''), 'refute')}
    </div>
    {refute_quotes_html}
    {narrative.get('skeptic_section', '')}
  </section>

  <!-- ⑧ PRIORITISED ACTION PLAN -->
  <section id="action-plan">
    <h2>⚡ Prioritised Action Plan</h2>
    {action_matrix_html}
    {narrative.get('action_plan_section', '')}
  </section>

  <!-- ⑨ RISK REGISTER -->
  <section id="risk-register">
    <h2>⚠️ Risk Register</h2>
    {risk_register_html}
    {narrative.get('risk_register_section', '')}
  </section>

  <!-- ⑩ SOURCES & REFERENCES -->
  <section id="sources">
    <h2>📎 Sources &amp; References</h2>
    <p style="margin-bottom:1rem">All sources gathered by the Researcher and Skeptic agents. Claims not listed here
    were not cited by the agents and should be treated as unverified context.</p>
    <div class="sources-grid">
      <div class="sources-col support">
        <h3>Supporting Sources</h3>
        {support_sources_html}
      </div>
      <div class="sources-col refute">
        <h3>Refuting Sources</h3>
        {refute_sources_html}
      </div>
    </div>
  </section>

</main>
</body>
</html>"""

    # ------------------------------------------------------------------
    # HTML Rendering Helpers
    # ------------------------------------------------------------------

    def _render_evidence_cards(self, text: str, card_class: str) -> str:
        if not text:
            return '<div class="card {c}"><p>No data.</p></div>'.format(c=card_class)
        items = text if isinstance(text, list) else [text]
        label = "Supporting" if card_class == "support" else "Challenge"
        cards = []
        for item in items:
            cards.append(
                f'<div class="card {card_class}">'
                f'<div class="label">{label}</div>'
                f'<p>{item}</p>'
                f'</div>'
            )
        return "\n".join(cards)

    def _render_mece_tree(self, nodes: list) -> str:
        """Render MECE decomposition as a nested visual tree (max 6 branches)."""
        if not nodes:
            return "<p style='color:var(--muted)'>MECE decomposition not available.</p>"
        nodes = nodes[:6]  # Hard cap at 6 branches
        items = []
        for node in nodes:
            label = node.get("label", "—")
            children = node.get("children", [])
            child_html = ""
            if children:
                child_items = "".join(
                    f"<li>{c if isinstance(c, str) else c.get('label', str(c))}</li>"
                    for c in children[:4]  # Max 4 children per branch
                )
                child_html = f"<ul>{child_items}</ul>"
            items.append(
                f"<li>"
                f'<div class="mece-branch-label">{label}</div>'
                f"{child_html}"
                f"</li>"
            )
        return f'<ul>{"".join(items)}</ul>'

    def _render_mece_compliance(self, check: dict) -> str:
        """Render MECE compliance check as a checklist with ✅/❌ indicators."""
        if not check:
            return "<p style='color:var(--muted);font-size:0.85rem'>Compliance check not available.</p>"

        # Human-readable labels for the 6 validator keys
        labels = {
            "no_category_overlap":          "No category overlap in the MECE decomposition",
            "no_missing_economic_drivers":  "All major economic drivers are covered",
            "each_rec_linked_to_outcome":   "Every recommendation links to a measurable economic outcome",
            "language_is_executive_ready":  "Language is decisive, quantified, and executive-ready",
            "governing_question_answered":  "Governing question is directly answered",
            "tiers_justified_by_evidence":  "Recommendation tier is justified by cited evidence",
        }
        items = []
        for key, human_label in labels.items():
            raw_val = check.get(key, False)
            passed = raw_val is True or (isinstance(raw_val, str) and raw_val.lower() in ("true", "yes", "pass", "passed"))
            icon = "✅" if passed else "❌"
            items.append(
                f'<div class="mece-check-item">'
                f'<span class="check-icon">{icon}</span>'
                f'<span>{human_label}</span>'
                f'</div>'
            )
        return "\n".join(items)

    def _render_micro_macro(self, pairs: list) -> str:
        if not pairs:
            return "<tr><td colspan='4'>No macro-evidence pairs available.</td></tr>"
        rows = []
        for p in pairs:
            micro = p.get("micro", "—")
            macro = p.get("macro", "—")
            insight = p.get("insight", "—")
            econ_link = p.get("economic_link", p.get("economic_objective", "—"))
            rows.append(
                f"<tr>"
                f"<td class='micro'>{micro}</td>"
                f"<td>{macro}</td>"
                f"<td>{insight}</td>"
                f"<td class='econ-link'>{econ_link}</td>"
                f"</tr>"
            )
        return "\n".join(rows)

    def _render_action_matrix(self, actions: list) -> str:
        """Render actions grouped by time horizon with H/M/L colour-coded cells."""
        if not actions:
            return "<p style='color:var(--muted)'>No action plan available.</p>"

        # Group by horizon
        horizons = {
            "immediate": {"label": "Immediate (0–2 weeks)", "css": "horizon-immediate", "actions": []},
            "short":     {"label": "Short-term (2–8 weeks)", "css": "horizon-short",    "actions": []},
            "medium":    {"label": "Medium-term (2–6 months)", "css": "horizon-medium", "actions": []},
        }
        for action in actions:
            horizon_raw = action.get("horizon", "").lower()
            if "immediate" in horizon_raw or "0-2" in horizon_raw or "0–2" in horizon_raw:
                horizons["immediate"]["actions"].append(action)
            elif "short" in horizon_raw or "2-8" in horizon_raw or "2–8" in horizon_raw:
                horizons["short"]["actions"].append(action)
            else:
                horizons["medium"]["actions"].append(action)

        html_parts = []
        for h_key, h_data in horizons.items():
            h_actions = h_data["actions"]
            html_parts.append(
                f'<div class="horizon-heading">'
                f'<span class="horizon-label {h_data["css"]}">{h_data["label"]}</span>'
                f'<hr />'
                f'</div>'
            )
            if not h_actions:
                html_parts.append("<p style='color:var(--muted);font-size:0.85rem;margin-bottom:0.5rem'>No actions in this horizon.</p>")
                continue

            rows = []
            for a in h_actions:
                desc = a.get("description", "—")
                outcome = a.get("economic_outcome", a.get("outcome", "—"))
                impact = a.get("impact", "—").strip()
                effort = a.get("effort", "—").strip()
                feasibility = a.get("feasibility", a.get("execution_feasibility", "—")).strip()
                rows.append(
                    f"<tr>"
                    f"<td>{desc}</td>"
                    f"<td>{self._rating_cell(impact)}</td>"
                    f"<td>{self._rating_cell(effort)}</td>"
                    f"<td>{self._rating_cell(feasibility)}</td>"
                    f"<td class='outcome-cell'>{outcome}</td>"
                    f"</tr>"
                )

            html_parts.append(
                f'<table class="action-matrix-table">'
                f'<thead><tr>'
                f'<th style="width:38%">Action</th>'
                f'<th>Impact</th>'
                f'<th>Effort</th>'
                f'<th>Feasibility</th>'
                f'<th>Economic Outcome</th>'
                f'</tr></thead>'
                f'<tbody>{"".join(rows)}</tbody>'
                f'</table>'
            )

        return "\n".join(html_parts)

    def _rating_cell(self, value: str) -> str:
        """Return a colour-coded badge span for H/M/L ratings."""
        v = value.strip().lower()
        if v in ("high", "h"):
            css = "rating-high"
            label = "High"
        elif v in ("medium", "med", "m"):
            css = "rating-medium"
            label = "Medium"
        elif v in ("low", "l"):
            css = "rating-low"
            label = "Low"
        else:
            return f"<span>{value}</span>"
        return f'<span class="rating-cell {css}">{label}</span>'

    def _render_risk_register(self, risks: list) -> str:
        """Render a risk register table with heat-map row colouring."""
        if not risks:
            return "<p style='color:var(--muted)'>No risks identified.</p>"

        def _risk_row_class(likelihood: str, impact: str) -> str:
            lh = likelihood.strip().lower()
            im = impact.strip().lower()
            if lh == "high" or im == "high":
                return "risk-high"
            elif lh == "medium" or im == "medium":
                return "risk-medium"
            return "risk-low"

        def _badge(value: str) -> str:
            v = value.strip().lower()
            if v in ("high", "h"):
                return f'<span class="risk-badge risk-badge-high">High</span>'
            elif v in ("medium", "med", "m"):
                return f'<span class="risk-badge risk-badge-medium">Medium</span>'
            return f'<span class="risk-badge risk-badge-low">Low</span>'

        rows = []
        for r in risks:
            risk_desc = r.get("risk", "—")
            likelihood = r.get("likelihood", "—")
            impact = r.get("impact", "—")
            control = r.get("control", r.get("control_mechanism", "—"))
            residual = r.get("residual_risk", r.get("residual", "—"))
            row_class = _risk_row_class(likelihood, impact)
            rows.append(
                f'<tr class="{row_class}">'
                f"<td>{risk_desc}</td>"
                f"<td>{_badge(likelihood)}</td>"
                f"<td>{_badge(impact)}</td>"
                f"<td>{control}</td>"
                f"<td>{residual}</td>"
                f"</tr>"
            )

        return (
            f'<table class="risk-table">'
            f'<thead><tr>'
            f'<th style="width:30%">Risk</th>'
            f'<th>Likelihood</th>'
            f'<th>Impact</th>'
            f'<th style="width:28%">Control Mechanism</th>'
            f'<th>Residual Risk</th>'
            f'</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody>'
            f'</table>'
        )

    def _render_sources(self, sources: list, side: str) -> str:
        if not sources:
            return f"<p style='color:var(--muted);font-size:0.85rem'>No external sources recorded for this side.</p>"
        items = []
        for s in sources:
            title = s.get("title") or "Untitled Source"
            url = s.get("url", "")
            pub = s.get("publication", "")
            date = s.get("date", "")
            meta_str = ""
            if pub or date:
                meta_str = f"<br/><small style='color:var(--muted); opacity: 0.8;'>{pub}{' • ' if pub and date else ''}{date}</small>"
            link = (
                f'<a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>{meta_str}'
                if url else f"<span>{title}</span>{meta_str}"
            )
            items.append(
                f'<div class="source-link">'
                f'<div class="dot {side}"></div>'
                f'<div>{link}</div>'
                f'</div>'
            )
        return "\n".join(items)

    def _render_blockquotes(self, sources: list, side: str) -> str:
        quotes = [s for s in sources if s.get("quote") or s.get("snippet")]
        if not quotes:
            return ""
        rendered = []
        for s in quotes[:3]:
            text = s.get("quote") or s.get("snippet", "")
            title = s.get("title", "External Source")
            url = s.get("url", "")
            cite = (
                f'<cite><a href="{url}" target="_blank" rel="noopener noreferrer">'
                f'— {title}</a></cite>'
                if url else f'<cite>— {title}</cite>'
            )
            rendered.append(
                f'<blockquote class="{side}-quote">'
                f'"{text[:300]}{"…" if len(text) > 300 else ""}"'
                f'{cite}'
                f'</blockquote>'
            )
        return "\n".join(rendered)
