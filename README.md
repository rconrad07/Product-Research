# Product Research Analyst Agent

An agentic system that ingests product discovery insights (Excel surveys, transcripts, external articles, Markdown), performs parallel pro/con research with programmatic URL verification, and generates a premium, board-ready HTML report.

> **This agent runs exclusively within Antigravity's IDE.** No external API keys or SDKs are required — the LLM is provided by the IDE runtime as well as any extensions (i.e. Python).

---

## Architecture

```text
Curate → [Researcher ‖ Skeptic] → Analyst → Report Builder → URL Validator
```

| Module | Role | Temperature |
| --- | --- | --- |
| **Curator** | Parses Excel, CSV, transcripts, .md, and URLs | 0.2 |
| **Researcher** | Seeks supporting macro trends & competitor wins (parallel) | 0.4 |
| **Skeptic** | Challenges hypothesis with conflicting data & failures (parallel) | 0.7 |
| **Analyst** | Synthesizes via Minto Pyramid, MECE, and Economic Drivers | 0.1 |
| **Report Builder** | Generates a self-contained, interactive HTML report | 0.3 |
| **URL Validator** | Performs post-generation deep-link verification & auto-fixes | 0.0 |

---

## Setup

```bash
pip install -r requirements.txt
```

No API keys needed — Antigravity's IDE provides the model at runtime.

---

## Usage

### CLI

```bash
python -m src.main \
  --hypothesis "Should we add a comparison tool?" \
  --inputs inputs/survey.xlsx inputs/transcript.txt \
  --url https://example.com/article
```

**Output:**
The report is saved to the `output/` directory. By default, it uses a unique name:
`YYYY-MM-DD_<hypothesis-slug>_PRA-<run-id>.html`

To override the filename:
`--output custom_report.html`

### Programmatic

```python
from src.main import run_pipeline

# Provide an optional search_fn to enable live web search
def my_search(query: str) -> list[dict]:
    # Use Antigravity's built-in search_web tool or any provider
    return [{"title": "...", "url": "...", "snippet": "..."}]

run_pipeline(
    hypothesis="Add a comparison tool",
    input_sources=["inputs/survey.xlsx"],
    search_fn=my_search,
)
```

---

## GroundCite 2.0 & URL Validation

The system includes **GroundCite 2.0**, a programmatic verification layer:

1. **Researcher/Skeptic**: Performs initial "Insight-First" search and basic URL verification.
2. **URL Validator**: A final pass that:
   - Verifies all citations in the generated HTML via `HEAD/GET` requests.
   - Replaces dead links with fresh results if a search function is provided.
   - Fixes canonical URL redirects.

Best practices are documented in [`docs/url_validation_best_practices.md`](docs/url_validation_best_practices.md).

---

## Testing & Quality

### Unit Tests

```bash
pytest tests/ -v
```

### Manual Evaluations

Historic quality evaluations and "Arbiter" reports are stored in:
`Evals/Manual/`

---

## Project Structure

```text
Product-Research/
├── src/
│   ├── config/
│   │   ├── settings.py     # Agent parameters, chunking limits
│   │   └── prompts.py      # Minto/MECE scaffolds (no hardcoding elsewhere)
│   ├── scripts/
│   │   ├── url_validator.py # Stage 5: Citation verification logic
│   │   └── generate_final_report.py # Asset compilation
│   ├── curator.py          # Stage 1: Input ingestion (.xlsx, .txt, .md, URL)
│   ├── researcher.py       # Stage 2a: Supporting evidence (GroundCite 2.0)
│   ├── skeptic.py          # Stage 2b: Adversarial research
│   ├── analyst.py          # Stage 3: Board-ready synthesis (12-key schema)
│   ├── report_builder.py   # Stage 4: Premium HTML generation
│   ├── utils.py            # IDE runtime interface, JSON parsing, logging
│   └── main.py             # Pipeline Orchestrator
├── tests/
│   ├── test_curator.py
│   └── test_analyst.py
├── docs/                   # Engineering guidelines & best practices
├── Evals/                  # Quality audit reports (Manual/Arbiter)
├── inputs/                 # Data drop zone
├── output/                 # Generated Reports
├── logs/                   # Human-readable & JSONL trace logs
└── requirements.txt
```

---

## Logs & Traceability

Every pipeline run generates:

- `logs/<RunID>.log` — detailed trace of each agent and validator step.
- `logs/<RunID>_traces.jsonl` — machine-readable records (token counts, models, latency).
