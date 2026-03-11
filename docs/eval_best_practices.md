# Best Practices: Incorporating Evals into LLM Pipelines

This document outlines a standardized approach for integrating rigorous evaluations (Evals) into LLM-driven systems. These practices maximize reliability, ensure consistent quality, and provide a clear signal for system calibration.

## 1. Modular Binary Judges
Instead of using a single "fuzzy" rubric (e.g., 0-100 score), break down complexity into atomic dimensions.

- **Atomic Criteria**: Define specific "Judges" for distinct dimensions (e.g., Citations, Accuracy, Formatting, Logic).
- **Binary Scoring**: Use absolute `Pass` or `Fail` criteria for each dimension. This removes subjectivity and makes failures easier to debug.
- **Critique then Decision (CoT)**: Enforce a Chain-of-Thought (CoT) pattern where the agent writes a critique *before* rendering a decision. This ensures the evaluation is grounded in logic.
- **Weighted Aggregation**: Calculate a final score by aggregating binary results based on predefined weights, rather than letting the LLM estimate the final score.

## 2. Establishing Gold Standards
System performance is meaningless without a verified baseline.

- **Ground Truth Datasets**: Create a "Gold Standard" directory containing JSON or Markdown files representing the "ideal" or "known failure" outputs.
- **Metric-Driven Validation**: Measure the evaluator's accuracy using **True Positive Rate (TPR)** and **True Negative Rate (TNR)**.
  - *TPR (Sensitivity)*: How often does the judge correctly identify a "Pass"?
  - *TNR (Specificity)*: How often does the judge correctly identify a "Fail"?
- **Evaluator Calibration**: Regular audits of the "Gold Standard" ensure that as the underlying models evolve, the evaluation logic remains accurate.

## 3. Proactive Robustness via Synthetic Scenarios
Testing only on "happy path" data leads to fragility.

- **Scenario Generators**: Develop specialized agents to generate "hostile" or malformed inputs based on specific "Dimensions of Variation" (e.g., broken links, missing data fields, out-of-order narratives).
- **Edge Case Injection**: Proactively inject errors into the pipeline to verify that your "Self-Healing" or "Arbiter" layers correctly catch and report them.
- **Test-Only Utilities**: Keep scenario generators separate from the production pipeline to minimize token overhead while maintaining a robust testing suite.

## 4. Workflow Integration & Continuous Testing
Evaluations should be a core phase of the development lifecycle, not an afterthought.

- **Automated Validation Scripts**: Use scripts (e.g., PowerShell, Python) to compare current agent outputs against the Gold Standard.
- **Evaluation Flags**: Integrate a `--validate` flag in orchestrators to trigger a calibration run.
- **Feedback Loops**: Map evaluation failures directly back to specific prompt sections or data sources to accelerate the "Modify -> Test -> Evaluate" cycle.

---

> [!NOTE]
> This document is designed to be parsed by LLMs for automated implementation planning and system auditing. Maintain high structural integrity in all Eval artifacts.
