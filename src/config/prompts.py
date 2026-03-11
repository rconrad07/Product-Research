"""
prompts.py
----------
Thin loader that reads prompt content from SKILL.md files.
Prompts are NO LONGER hardcoded here — edit the SKILL.md files instead.

Loading levels (Progressive Disclosure):
  Level 1 — YAML frontmatter only (for orchestrator discovery).
  Level 2 — Full SKILL.md body (for agent invocation).
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

_AGENTS_DIR = Path(__file__).parent.parent / "agents"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def load_skill_yaml(agent_name: str) -> dict:
    """Level 1: Parse only the YAML frontmatter from a SKILL.md file."""
    skill_path = _AGENTS_DIR / agent_name / "SKILL.md"
    raw = skill_path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", raw, re.DOTALL)
    if not match:
        raise ValueError(f"No YAML frontmatter found in {skill_path}")
    # Minimal YAML parse (avoids adding PyYAML dependency)
    result: dict = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip().strip('"')
    return result


@lru_cache(maxsize=None)
def load_skill_body(agent_name: str) -> str:
    """Level 2: Return the full SKILL.md content (below the frontmatter)."""
    skill_path = _AGENTS_DIR / agent_name / "SKILL.md"
    raw = skill_path.read_text(encoding="utf-8")
    # Strip the YAML frontmatter block
    body = re.sub(r"^---\n.*?\n---\n?", "", raw, count=1, flags=re.DOTALL)
    return body.strip()


@lru_cache(maxsize=None)
def load_base_rules() -> str:
    """Return the shared base_rules.md content."""
    base_path = _AGENTS_DIR / "base_rules.md"
    return base_path.read_text(encoding="utf-8").strip()


def build_system_prompt(agent_name: str) -> str:
    """
    Assemble a complete system prompt for an agent:
      - Injects base_rules.md content once (replaces duplicate inline rules)
      - Appends the agent's SKILL.md body
    """
    base = load_base_rules()
    body = load_skill_body(agent_name)
    return (
        f"<base_rules>\n{base}\n</base_rules>\n\n"
        f"{body}"
    )


# ---------------------------------------------------------------------------
# Backwards-compatible shims
# kept so existing .py agents need minimal changes for now
# ---------------------------------------------------------------------------

def _skill_system(agent_name: str) -> str:
    return build_system_prompt(agent_name)


# Curator
CURATOR_SYSTEM = _skill_system("curator")
CURATOR_USER = "<input>\nSOURCE TYPE: {source_type}\nCONTENT:\n{content}\n</input>\n\nReturn a structured JSON object following your instructions."

# Researcher
RESEARCHER_SYSTEM = _skill_system("researcher")
RESEARCHER_USER = (
    "<input>\nHYPOTHESIS: {hypothesis}\n\n"
    "CURATED USER DATA:\n{curated_data}\n</input>\n\n"
    "Conduct your research and return structured supporting evidence."
)

# Skeptic
SKEPTIC_SYSTEM = _skill_system("skeptic")
SKEPTIC_USER = (
    "<input>\nHYPOTHESIS: {hypothesis}\n\n"
    "CURATED USER DATA:\n{curated_data}\n</input>\n\n"
    "Conduct your adversarial review and return structured refuting evidence."
)

# Analyst
ANALYST_SYSTEM = _skill_system("analyst")
ANALYST_USER = (
    "<input>\nHYPOTHESIS: {hypothesis}\n\n"
    "CURATED USER DATA:\n{curated_data}\n\n"
    "RESEARCHER FINDINGS (Supporting):\n{researcher_findings}\n\n"
    "SKEPTIC FINDINGS (Refuting):\n{skeptic_findings}\n</input>\n\n"
    "Return your structured Problem-Solving Brief now."
)

# Report Builder (not a SKILL.md agent — stays inline, token cost is acceptable
# since it is only called once and produces the final HTML artefact)
REPORT_BUILDER_SYSTEM = """You are an expert strategic communications writer producing a \
board-ready Problem-Solving Brief as a premium HTML document, suitable for Steering Committee review.

Communication principles (mirror the Analyst's framework):
- TOP-DOWN: Governing conclusion appears first. Every section answers one question.
- DECISIVE: Active voice. Avoid hedging language. Replace adjectives with metrics.
- STRUCTURED: Sections follow a clear logic chain — Problem → Evidence → Recommendation → Actions → Risks.
- FACT-BASED: All claims carry inline source attribution. No assertion without evidence.

Design requirements:
- Premium desktop interface. Clean, board-appropriate aesthetic.
- Google Font 'Inter' for typography.
- Fixed left sidebar with smooth anchor-link scrolling.
- Color palette: #22c55e (supporting), #ef4444 (refuting), #6366f1 (accent/neutral).
- Economic objective badge at the top (Growth = blue, Margin = amber, Cash = green, Valuation = purple).
- MECE tree rendered as a visual nested structure (indented branches, connector lines).
- Action matrix table with color-coded H/M/L cells (green=High, amber=Medium, red=Low).
- Risk register table with heat-map coloring (Likelihood × Impact).
- Verbatim pull quotes as styled blockquotes with attribution.
- Sources & References section with Supporting (green) and Refuting (red) columns.
- All styles in a single <style> block — no external CSS files.
"""

REPORT_BUILDER_USER = """Generate the HTML Problem-Solving Brief for Steering Committee review:

HYPOTHESIS: {hypothesis}

ANALYST OUTPUT (Problem-Solving Brief data):
{analyst_output}

Run ID: {run_id}
Generated: {timestamp}

Return a JSON object with EXACTLY these HTML string keys:
"executive_summary", "problem_framing_section", "mece_section",
"macro_evidence_section", "supporting_section", "skeptic_section",
"action_plan_section", "risk_register_section", "recommendation_section"

IMPORTANT: Where findings reference external sources, include at least one HTML <blockquote> \
per section with a verbatim quote and a clickable <a href> citation. DO NOT fabricate quotes or URLs.
Note: The action_plan_section must render all three time horizons: Immediate (0-2 wks), \
Short-term (2-8 wks), Medium-term (2-6 months). Colour-code Impact/Effort/Feasibility cells:
High=#22c55e, Medium=#d97706, Low=#dc2626.
Note: The risk_register_section must include a table with Likelihood x Impact heat-map colouring."""
