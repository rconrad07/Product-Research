# Best Practices for Writing AI Skills & Orchestration

This document captures the full pattern library for building high-performance, token-efficient AI agent pipelines. It is designed to be shared across teams and adapted to any multi-agent workflow.

---

## 1. The Skill File Standard

Every agent should be a `SKILL.md` file with the following structure:

### 1.1 YAML Frontmatter (Progressive Disclosure — Level 1)

The frontmatter is the *only* thing loaded when the orchestrator decides which skill to use. Keep it tight.

```yaml
---
name: "Agent Name"
description: "One sentence: what this agent does and when to invoke it."
capabilities: ["web_search", "file_read", "file_write"]
output_schema: "SchemaName"
inherits: "../base_rules.md"
---
```

**Rules:**

- `description` must be under 25 words.
- `capabilities` constrains what tools this agent may use — enforce at the orchestrator level.
- `output_schema` links to a JSON schema that validates the agent's output.
- `inherits` points to a shared `base_rules.md` — never repeat shared constraints inline.

---

### 1.2 XML Tag Structure (Instruction Clarity)

Use XML tags to separate distinct sections of the prompt. This eliminates ambiguity between instructions, data, and examples.

| Tag | Purpose |
| :--- | :--- |
| `<instructions>` | Core task definition and reasoning order |
| `<rules>` | Hard constraints — the agent cannot violate these |
| `<examples>` | Good/bad examples that calibrate output format and tone |
| `<context>` | Background or historical information passed in at runtime |
| `<input>` | The live data to process in this invocation |
| `<correction>` | Injected by the orchestrator during a RALPH loop re-invocation |

**Example:**

```xml
<instructions>
You are the Content Curator. Before producing output, use a <thinking> block to...
</instructions>

<rules>
- Never fabricate URLs.
- Every numeric value must include an explicit timeframe.
</rules>

<examples>
GOOD: "-2.1% (premarket, 8:45 AM ET)"
BAD: "down recently"
</examples>
```

---

### 1.3 Mandatory Thinking Block

Always instruct agents to reason before outputting. This dramatically improves performance on structured tasks like citation auditing, data formatting, and deduplication.

```
Before producing output, use a <thinking> block to:
1. Step 1 (e.g., "Check each URL appears verbatim in search results")
2. Step 2 (e.g., "Verify each numeric value has a timeframe")
3. Step 3 (e.g., "Confirm no item was covered in a prior report")
```

> [!TIP]
> Make the thinking steps *sequential* and *verifiable* — if you can't check whether the agent did Step 2, it won't be consistently followed.

---

## 2. Shared Base Rules

Create a single `base_rules.md` that all skills `inherit`. This avoids repeating constraints across every file, reducing both token cost and maintenance burden.

Typical contents for an information-retrieval pipeline:

- **Citation rules**: URL sourcing, deep-link requirements, no fabrication.
- **Deduplication rules**: How to compare against history.
- **Data integrity rules**: Timeframe requirements for numeric data.
- **Output discipline**: Conciseness, format constraints, no footnote markers.

---

## 3. Output Schemas (I/O Contracts)

Define a `schemas/agent_contracts.json` with a named schema for every agent's output. Reference these in:

- The agent's YAML frontmatter (`output_schema`).
- The orchestrator's workflow step definitions.
- The Arbiter's evaluation criteria.

This creates a machine-verifiable contract between agents, reducing silent failures.

---

## 4. The RALPH Loop — Agentic Self-Correction

The RALPH loop is an orchestration pattern that enables a pipeline to self-correct without human intervention.

| Phase | Action |
| :--- | :--- |
| **Read** | Ingest the evaluation report (e.g., Arbiter findings). |
| **Analyze** | Identify failures and their `responsible_agent`. |
| **Log** | Write the failure to a retry log (prevents infinite loops). |
| **Plan** | Determine the minimum re-invocation chain (only re-run what's needed). |
| **Help** | Inject a `<correction>` block into the re-invoked agent's prompt. |

### 4.1 Targeted Re-invocation Chains - Example

| Failure Source | Re-invocation Chain |
| :--- | :--- |
| Formatter only | `Formatter` |
| Curator (bad data) | `Curator → Summarizer → Filter → Formatter` |
| Multiple agents | Start from the upstream-most failing agent |

### 4.2 Cost Control

- **Limit to 1 retry.** After the retry, the Arbiter runs once more. Do not loop again.
- Only re-run for `critical` or `high` severity findings. Ignore `low` severity on the retry pass.

### 4.3 Correction Prompt Pattern

When re-invoking a failing agent, inject this block into the prompt:

```xml
<correction>
The previous run produced the following failures:
{arbiter_findings_for_this_agent}
Please address these specific issues in your output.
</correction>
```

---

## 5. Calibration Agent (i.e. Arbiter Pattern)

For pipelines producing structured output, include an independent Arbiter that:

- Has its own calibration examples (GOOD/BAD) wrapped in `<calibration>` tags.
- Uses a `<thinking>` block to audit each dimension before scoring.
- Produces a `pass` boolean and `findings[]` with a `responsible_agent` field on every finding.
- Does NOT generate or fix content — it audits only.

---

## 6. Token Optimization Summary

| Strategy | Impact |
| :--- | :--- |
| Shared `base_rules.md` | Eliminate repeat rule blocks across agents |
| YAML frontmatter | Load agent identity without the full SKILL.md |
| XML tags | Reduce ambiguity = fewer follow-up clarifications |
| Output schemas | Catch errors early, no re-runs for format failures |
| RALPH loop (1 retry) | Self-correct without human cost, capped at 1 extra pass |
| Thinking blocks | Higher first-pass accuracy = fewer total retries |
