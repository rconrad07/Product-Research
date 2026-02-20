"""
report_builder.py
-----------------
Stage 4: Converts the Analyst's structured output into a premium,
self-contained HTML report for executive review.
"""
import json
from datetime import datetime
from pathlib import Path

from src.config.prompts import REPORT_BUILDER_SYSTEM, REPORT_BUILDER_USER
from src.config.settings import AGENT_MODELS, AGENT_TEMPERATURES, OUTPUT_DIR
from src.utils import LLMClient


TIER_STYLES = {
    "STRONG_BUILD":  {"color": "#16a34a", "bg": "#f0fdf4", "label": "✅ Build Now"},
    "BUILD_MVP":     {"color": "#d97706", "bg": "#fffbeb", "label": "⚠️ Build MVP"},
    "RE_EVALUATE":   {"color": "#7c3aed", "bg": "#f5f3ff", "label": "🔄 Re-evaluate"},
    "DEPRIORITIZE":  {"color": "#dc2626", "bg": "#fef2f2", "label": "🚫 Deprioritize"},
}


class ReportBuilder:
    """
    Uses an LLM to draft the full report body, then injects it into a
    polished HTML shell with guaranteed structure and styling.
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
        Generate and write the HTML report.

        Returns the Path to the written file.
        """
        self.llm.logger.info("Report Builder generating report...")

        researcher_findings = researcher_findings or {}
        skeptic_findings = skeptic_findings or {}

        # Ask the LLM to generate the narrative body sections
        narrative = self._generate_narrative(hypothesis, analyst_output)

        # Assemble the structured HTML shell
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
            analyst_output=json.dumps(analyst_output, indent=2)[:4000],
            run_id=self.run_id,
            timestamp=datetime.utcnow().isoformat(),
        ) + (
            "\n\nReturn a JSON object with these HTML string keys:\n"
            "executive_summary, supporting_section, skeptic_section, "
            "micro_macro_section, decision_tree_section, recommendation_section\n\n"
            "IMPORTANT: Where the analyst findings reference external sources, "
            "include at least one HTML <blockquote> per section with a real verbatim "
            "quote and a clickable <a href> citation link from the sources in the findings. "
            "DO NOT fabricate quotes or URLs."
        )
        raw = self.llm.complete(
            system=REPORT_BUILDER_SYSTEM,
            user=user_msg,
            model=AGENT_MODELS["report_builder"],
            temperature=AGENT_TEMPERATURES["report_builder"],
            max_tokens=8000,
        )
        try:
            from src.utils import extract_json  # noqa: PLC0415
            return extract_json(raw)
        except ValueError:
            # Fallback: treat entire completion as a single narrative block
            return {"executive_summary": raw}

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
        timestamp = datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")

        decision_tree_rows = self._render_decision_tree(
            analyst_output.get("decision_tree_path", [])
        )
        micro_macro_rows = self._render_micro_macro(
            analyst_output.get("micro_macro_pairs", [])
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

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Product Research Report — {hypothesis[:60]}</title>
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
      --purple: #a78bfa;
      --accent: #6366f1;
      --sidebar-w: 260px;
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
      gap: 0.4rem;
      overflow-y: auto;
    }}
    nav#sidebar .brand {{
      font-size: 0.75rem;
      font-weight: 600;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 1.25rem;
    }}
    nav#sidebar a {{
      display: block;
      padding: 0.5rem 0.75rem;
      border-radius: 8px;
      color: var(--muted);
      text-decoration: none;
      font-size: 0.875rem;
      font-weight: 500;
      transition: background 0.15s, color 0.15s;
    }}
    nav#sidebar a:hover {{
      background: var(--surface2);
      color: var(--text);
    }}
    /* ---- Main content ---- */
    main {{
      margin-left: var(--sidebar-w);
      padding: 3rem 3.5rem;
      max-width: 960px;
      width: 100%;
    }}
    /* ---- Recommendation Banner ---- */
    .rec-banner {{
      background: {tier_style['bg']};
      border: 2px solid {tier_style['color']};
      border-radius: 14px;
      padding: 1.75rem 2rem;
      margin-bottom: 2.5rem;
    }}
    .rec-banner .tier {{
      font-size: 1.6rem;
      font-weight: 700;
      color: {tier_style['color']};
    }}
    .rec-banner .hyp {{
      font-size: 0.95rem;
      color: #475569;
      margin-top: 0.4rem;
    }}
    .rec-banner .verdict {{
      margin-top: 0.75rem;
      font-size: 1rem;
      color: #1e293b;
      line-height: 1.6;
    }}
    /* ---- Section ---- */
    section {{
      margin-bottom: 3rem;
    }}
    h1 {{ font-size: 1.9rem; font-weight: 700; margin-bottom: 0.25rem; }}
    h2 {{ font-size: 1.25rem; font-weight: 600; color: var(--text); margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border); }}
    p, li {{ font-size: 0.95rem; line-height: 1.7; color: var(--muted); }}
    ul {{ padding-left: 1.25rem; }}
    /* ---- Evidence cards ---- */
    .card-grid {{ display: grid; gap: 1rem; }}
    .card {{
      background: var(--surface);
      border-radius: 10px;
      padding: 1.25rem 1.5rem;
      border-left: 4px solid var(--border);
    }}
    .card.support {{ border-left-color: var(--green); }}
    .card.refute  {{ border-left-color: var(--red); }}
    .card .label {{
      font-size: 0.7rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 0.4rem;
    }}
    .card.support .label {{ color: var(--green); }}
    .card.refute  .label {{ color: var(--red); }}
    .card p {{ margin-top: 0.25rem; }}
    /* ---- Micro-Macro table ---- */
    table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    th {{ background: var(--surface2); color: var(--text); padding: 0.65rem 1rem; text-align: left; font-weight: 600; }}
    td {{ padding: 0.65rem 1rem; border-top: 1px solid var(--border); color: var(--muted); vertical-align: top; }}
    td.micro {{ color: var(--purple); font-style: italic; }}
    /* ---- Decision Tree ---- */
    .tree-step {{
      display: flex;
      align-items: flex-start;
      gap: 1rem;
      margin-bottom: 1rem;
    }}
    .tree-step .num {{
      min-width: 2rem;
      height: 2rem;
      background: var(--accent);
      color: white;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 0.85rem;
    }}
    .tree-step .content {{ flex: 1; }}
    .tree-step .question {{ font-weight: 600; color: var(--text); }}
    .tree-step .answer {{
      display: inline-block;
      margin-top: 0.25rem;
      padding: 0.15rem 0.6rem;
      border-radius: 999px;
      font-size: 0.8rem;
      font-weight: 600;
      background: var(--surface2);
      color: var(--green);
    }}
    /* ---- Blockquotes ---- */
    blockquote {
      border-left: 4px solid var(--accent);
      margin: 1rem 0;
      padding: 0.75rem 1.25rem;
      background: var(--surface2);
      border-radius: 0 8px 8px 0;
      font-style: italic;
      color: var(--muted);
    }
    blockquote cite {
      display: block;
      margin-top: 0.5rem;
      font-size: 0.8rem;
      font-style: normal;
      color: var(--accent);
    }
    blockquote.support-quote { border-left-color: var(--green); }
    blockquote.refute-quote  { border-left-color: var(--red); }
    /* ---- Sources grid ---- */
    .sources-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.5rem;
      margin-top: 1rem;
    }
    .sources-col h3 {
      font-size: 0.85rem;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      margin-bottom: 0.75rem;
    }
    .sources-col.support h3 { color: var(--green); }
    .sources-col.refute  h3 { color: var(--red); }
    .source-link {
      display: flex;
      align-items: flex-start;
      gap: 0.5rem;
      margin-bottom: 0.6rem;
      font-size: 0.85rem;
    }
    .source-link .dot {
      min-width: 8px;
      height: 8px;
      border-radius: 50%;
      margin-top: 5px;
    }
    .source-link .dot.support { background: var(--green); }
    .source-link .dot.refute  { background: var(--red); }
    .source-link a { color: var(--muted); text-decoration: none; }
    .source-link a:hover { color: var(--text); text-decoration: underline; }
    .meta {{ font-size: 0.8rem; color: var(--muted); margin-bottom: 2rem; }}
    .run-id {{ font-family: monospace; color: var(--accent); }}
  </style>
</head>
<body>

<nav id="sidebar">
  <div class="brand">Product Research</div>
  <a href="#recommendation">🎯 Recommendation</a>
  <a href="#executive-summary">📋 Executive Summary</a>
  <a href="#supporting">✅ Supporting Evidence</a>
  <a href="#skeptic">🚫 Skeptic's Challenges</a>
  <a href="#micro-macro">🔗 Micro → Macro</a>
  <a href="#decision-tree">🌳 Decision Tree</a>
  <a href="#final">📢 Final Analysis</a>
  <a href="#sources">📎 Sources</a>
</nav>

<main>
  <h1>Product Research Report</h1>
  <div class="meta">
    Generated on {timestamp} &nbsp;|&nbsp; Run ID: <span class="run-id">{self.run_id}</span>
  </div>

  <!-- Recommendation Banner -->
  <section id="recommendation">
    <div class="rec-banner">
      <div class="tier">{tier_style['label']}</div>
      <div class="hyp"><strong>Hypothesis:</strong> {hypothesis}</div>
      <div class="verdict">{analyst_output.get("final_recommendation", "—")}</div>
    </div>
  </section>

  <!-- Executive Summary -->
  <section id="executive-summary">
    <h2>Executive Summary</h2>
    {narrative.get("executive_summary", "<p>See full analysis below.</p>")}
  </section>

  <!-- Supporting Evidence -->
  <section id="supporting">
    <h2>✅ Supporting Evidence</h2>
    <div class="card-grid">
      {self._render_evidence_cards(analyst_output.get("supporting_summary", ""), "support")}
    </div>
    {support_quotes_html}
    {narrative.get("supporting_section", "")}
  </section>

  <!-- Skeptic's Challenges -->
  <section id="skeptic">
    <h2>🚫 Skeptic's Challenges</h2>
    <div class="card-grid">
      {self._render_evidence_cards(analyst_output.get("skeptic_rebuttal", ""), "refute")}
    </div>
    {refute_quotes_html}
    {narrative.get("skeptic_section", "")}
  </section>

  <!-- Micro-Macro Synthesis -->
  <section id="micro-macro">
    <h2>🔗 Micro → Macro Synthesis</h2>
    <table>
      <thead>
        <tr><th>Micro (User Signal)</th><th>Macro (Market Trend)</th><th>Insight</th></tr>
      </thead>
      <tbody>
        {micro_macro_rows}
      </tbody>
    </table>
    {narrative.get("micro_macro_section", "")}
  </section>

  <!-- Decision Tree -->
  <section id="decision-tree">
    <h2>🌳 Decision Tree Path</h2>
    {decision_tree_rows}
    {narrative.get("decision_tree_section", "")}
  </section>

  <!-- Final Analysis -->
  <section id="final">
    <h2>📢 Final Analyst Recommendation</h2>
    {narrative.get("recommendation_section", f"<p>{analyst_output.get('final_recommendation', '')}</p>")}
  </section>

  <!-- Sources & References -->
  <section id="sources">
    <h2>📎 Sources &amp; References</h2>
    <p style="margin-bottom:1rem">All sources gathered by the Researcher and Skeptic agents. Claims not listed here were not cited by the agents and should be treated as unverified context.</p>
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
        if isinstance(text, list):
            items = text
        else:
            items = [text]
        cards = []
        for item in items:
            label = "Supporting" if card_class == "support" else "Challenge"
            cards.append(
                f'<div class="card {card_class}">'
                f'<div class="label">{label}</div>'
                f'<p>{item}</p>'
                f'</div>'
            )
        return "\n".join(cards)

    def _render_micro_macro(self, pairs: list) -> str:
        if not pairs:
            return "<tr><td colspan='3'>No micro-macro pairs available.</td></tr>"
        rows = []
        for p in pairs:
            micro = p.get("micro", "—")
            macro = p.get("macro", "—")
            insight = p.get("insight", "—")
            rows.append(
                f"<tr><td class='micro'>{micro}</td><td>{macro}</td><td>{insight}</td></tr>"
            )
        return "\n".join(rows)

    def _render_decision_tree(self, path: list) -> str:
        if not path:
            return "<p style='color:var(--muted)'>Decision tree path not available.</p>"
        steps = []
        for i, step in enumerate(path, 1):
            question = step.get("question", step.get("id", f"Step {i}"))
            answer = step.get("answer", step.get("result", ""))
            steps.append(
                f'<div class="tree-step">'
                f'<div class="num">{i}</div>'
                f'<div class="content">'
                f'<div class="question">{question}</div>'
                f'<span class="answer">{answer}</span>'
                f'</div></div>'
            )
        return "\n".join(steps)

    def _render_sources(self, sources: list, side: str) -> str:
        """
        Render a list of source dicts as clickable citation links.
        `side` is either 'support' or 'refute' (controls dot colour).
        """
        if not sources:
            return f"<p style='color:var(--muted);font-size:0.85rem'>No external sources recorded for this side.</p>"
        items = []
        for s in sources:
            title = s.get("title") or "Untitled Source"
            url = s.get("url", "")
            link = (
                f'<a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>'
                if url else f"<span>{title}</span>"
            )
            items.append(
                f'<div class="source-link">'
                f'<div class="dot {side}"></div>'
                f'{link}'
                f'</div>'
            )
        return "\n".join(items)

    def _render_blockquotes(self, sources: list, side: str) -> str:
        """
        Render snippet-based blockquotes under each evidence section.
        Only renders sources that have a non-empty snippet.
        Returns empty string if no quotes are available.
        """
        quotes = [s for s in sources if s.get("quote") or s.get("snippet")]
        if not quotes:
            return ""
        rendered = []
        for s in quotes[:3]:  # Cap at 3 quotes per section to avoid clutter
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
