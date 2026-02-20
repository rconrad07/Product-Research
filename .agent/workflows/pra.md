---
description: Start an End-to-End Product Research Analysis
---
# Product Research Analyst (PRA) Workflow

Use this workflow to initiate a comprehensive research and analysis cycle for a product hypothesis.

## Initiation Steps

1. **Submit Hypothesis**
   Provide the product hypothesis or research question you want to investigate.

2. **Collect Inputs**
   Drop any relevant Excel surveys, CSV data, or interview transcripts into the `inputs/` folder.

3. **Execute the Pipeline**
   // turbo
   Run the following command in the terminal to start the orchestrator:

   ```bash
   python -m src.main --hypothesis "YOUR_HYPOTHESIS_HERE" --inputs inputs/YOUR_FILE.xlsx
   ```

   *Note: Replace placeholders with your actual hypothesis and filenames.*

4. **Review Report**
   Once complete, the orchestrator will generate a polished HTML report in the `output/` directory.

## Pipeline Overview

The PRA system follows a 4-stage agentic workflow:

1. **Curate:** Ingests and sanitizes your inputs.
2. **Research (Parallel):**
   - **Researcher:** Finds supporting industry trends and data.
   - **Skeptic:** Adversarially challenges the hypothesis with risks and gaps.
3. **Analyze:** Synthesizes pro/con data using a Decision Tree.
4. **Report:** Generates the final executive HTML dashboard.
