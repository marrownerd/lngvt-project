# Architecture notes

## Design principle

Keep deterministic data handling separate from language generation. The MVP does not depend on an LLM API: the initial workflow is reproducible and inexpensive. This makes it possible to measure the value of better extraction and retrieval before introducing generative components.

## Recommended evolution

### 1. Data ingestion
PubMed E-utilities -> normalized paper records -> deduplication by PMID/DOI -> immutable source metadata.

### 2. Enrichment
Replace keyword heuristics with a schema-constrained extractor. Store the source sentence for every extracted value and a confidence/status field (`explicit`, `inferred`, `unknown`). Keep the original abstract unchanged.

### 3. Retrieval
Move from TF-IDF to hybrid retrieval:
- BM25 for exact terms;
- dense embeddings for semantic similarity;
- metadata filters for species, age, sex, disease, design and date;
- reranking on a limited candidate set.

### 4. Evidence synthesis
Create claim records with a defined PICO-like question and estimand. Only pool compatible estimates. Track cohort overlap and multiple reports from the same trial. Use random-effects models when heterogeneity is expected, and report prediction intervals where appropriate.

### 5. Sequential updates
When a new eligible estimate arrives:
- identify the affected claim;
- recompute the synthesis;
- compare the new and previous posterior/pooled estimate;
- store a versioned change record;
- alert only when a pre-defined rule is met.

### 6. Personalization
Treat profile matching as relevance ranking, not as an individual treatment-effect model. To estimate individualized benefit, the system would need validated effect modifiers and external validation. Otherwise display population-level findings with a clear applicability note.

## Why no life-years estimate in v0

A life-years estimate is not obtained by multiplying an association by a person's profile. It requires a calibrated survival model, a defined counterfactual intervention, baseline hazards, competing-risk handling, censoring assumptions and external validation. Most longevity publications do not provide individual-level data or the causal estimates required for this.


## Uncertainty-aware reporting (current iteration)

The report now separates retrieval relevance from evidence strength and adds a deterministic uncertainty ledger. It describes coverage, missing abstracts, heuristic study-design classification, profile/population transfer limits, causal limitations, unknown cohort overlap, and the absence of validated effect estimates. No aggregate confidence percentage is produced.

The statistical module additionally exposes prior-sensitivity analysis for the normal-normal update and KL divergence between normal posterior approximations. These are research utilities only: the current paper pipeline does not extract validated effect estimates, so the report intentionally does not pool retrieved papers.

## Numerical extraction and manual synthesis (v0.2 iteration)

`effect_extraction.py` scans abstracts or locally cached Europe PMC OA text for a limited set of ratio effects (HR/RR/OR/IRR), 95% CIs and p-values. Every candidate keeps a source sentence and text offsets. It is a conservative baseline parser; values must be checked in the source article. `open_access.py` resolves PubMed IDs through Europe PMC and fetches XML only for records marked open access, then converts prose and table rows to cached text. Source licences still govern reuse.

`meta_analysis.py` pools only log-ratio estimates with standard errors and common, explicitly declared synthesis metadata. The calling UI requires a user attestation covering estimand/outcome, population, comparator, follow-up, design and independence. This attestation is not machine-verified. REML and DL are available; the reported modified Hartung–Knapp interval and prediction interval are approximations appropriate for methodological exploration, not a substitute for a protocol-defined analysis. BH correction is available as a utility and requires a prespecified hypothesis family.

The next quality gate is a benchmark with manually double-annotated abstracts/full texts, adjudicated effect measure/estimate/CI/p-value/outcome/contrast/population/follow-up/design, cohort-overlap labels and text spans. Report field-level precision, recall and exact-match accuracy; do not infer trust from the parser's own validation flags.
