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
