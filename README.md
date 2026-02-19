# Product Research Analyst Agent

An agentic system that ingests product discovery insights (Excel surveys, transcripts, external articles), performs parallel pro/con research, and generates a premium HTML report for executive decision-making.

> **This agent runs exclusively within Antigravity's IDE.** No external API keys or SDKs are required — the LLM is provided by the IDE runtime.

---

## Architecture

```text
Curate → [Researcher ‖ Skeptic] → Analyst → Report Builder
```

| Module | Role | Temperature |
| --- | --- | --- |
| **Curator** | Parses Excel, CSV, transcripts, and URLs | 0.2 |
| **Researcher** | Seeks supporting macro trends (parallel, isolated) | 0.4 |
| **Skeptic** | Challenges hypothesis with conflicting data (parallel, isolated) | 0.7 |
| **Analyst** | Synthesizes findings via Decision Tree & Micro↔Macro pairing | 0.1 |
| **Report Builder** | Generates a self-contained HTML report | 0.3 |

---

## Setup

```bash
pip install -r requirements.txt
```

No API keys needed — Antigravity's IDE provides the model at runtime.

---

## Usage

```bash
python -m src.main \
  --hypothesis "Should we add a comparison tool?" \
  --inputs inputs/survey.xlsx inputs/transcript.txt \
  --url https://example.com/article \
  --output report.html
```

The report is saved to `output/report.html`.

---

## Web Search Integration

The Researcher and Skeptic include a **stub** search function by default. To enable real web search, inject a `search_fn`:

```python
from src.main import run_pipeline

def my_search(query: str) -> list[dict]:
    # Use Antigravity's built-in search_web tool or any compatible provider
    return [{"title": "...", "url": "...", "snippet": "..."}]

run_pipeline(
    hypothesis="Add a comparison tool",
    input_sources=["inputs/survey.xlsx"],
    search_fn=my_search,
)
```

---

## Testing

```bash
pytest tests/ -v
```

---

## Project Structure

```text
Product-Research/
├── src/
│   ├── config/
│   │   ├── settings.py     # Model labels, temperatures, context limits
│   │   └── prompts.py      # All system prompts (never hardcoded elsewhere)
│   ├── curator.py          # Stage 1: Input ingestion
│   ├── researcher.py       # Stage 2a: Supporting evidence (parallel)
│   ├── skeptic.py          # Stage 2b: Refuting evidence (parallel)
│   ├── analyst.py          # Stage 3: Synthesis + Decision Tree
│   ├── report_builder.py   # Stage 4: HTML report
│   ├── utils.py            # LLM interface, logger, retry, JSON helpers
│   └── main.py             # Orchestrator + CLI
├── tests/
│   ├── test_curator.py
│   └── test_analyst.py
├── inputs/                 # Drop your Excel, CSV, TXT files here
├── output/                 # Generated HTML reports
├── logs/                   # LLM trace logs (per RunID)
└── requirements.txt
```

---

## Logs & Traceability

Every pipeline run generates:

- `logs/<RunID>.log` — human-readable trace of each agent step
- `logs/<RunID>_traces.jsonl` — machine-readable LLM call records (prompt size, model, temperature, timestamp)
