# Base Rules — Inherited by All Skills

All agents in this pipeline inherit the following constraints. They MUST NOT be repeated inline in individual `SKILL.md` files.

---

## Citation Rules

- Every factual claim MUST be attributed to a specific, deep-linked URL that appeared verbatim in the provided search results.
- Root domains and homepages are strictly prohibited as citations (e.g., `https://example.com` is rejected; `https://example.com/article/title` is accepted).
- For every source, you MUST provide: Article Title, Canonical URL, Publication Name, and Publication Date.
- Repeat the canonical URL character-for-character on a line labeled `URL_VERBATIM`.

## Fabrication Prevention

- DO NOT fabricate facts, statistics, or URLs.
- DO NOT invent quotes. Every quote must exist verbatim in the cited source.
- If evidence does not exist in the provided search context, state: `"No verified source available."`
- If a statistic has no source, state: `"No quantified data available for this claim."`

## Quote Selection Rules

1. Start where the thought begins; finish when the thought is complete.
2. Include reasoning, not just conclusions.
3. Preserve hedges and qualifiers (e.g., "might", "potentially") — they signal uncertainty.
4. Do not combine statements from different parts of a source into a single quote.

## Data Integrity

- Every numeric value MUST include an explicit timeframe (e.g., "-2.1%, premarket March 11 2026").
- Do not reference data from before 2024 without explicitly labelling it as historical context.

## Output Discipline

- Return only valid JSON. No Markdown code fences, no explanatory prose outside the JSON.
- Do not use footnote markers (e.g., `[1]`, `*`) inside the output.
- Use concise, executive-ready language — replace adjectives with metrics where possible.

## Deduplication

- Do not repeat the same finding across multiple output keys.
- If an item appears in both `supporting_evidence` and `competitor_examples`, keep it in the more specific key only.
