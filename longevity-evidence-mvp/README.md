# Longevity Evidence — MVP

A small research-monitoring app for longevity and healthy-aging literature.

It collects recent PubMed records, extracts a few searchable metadata fields, stores them locally, and lets you search the local library and generate source-linked research briefings.

This is an early prototype. It is designed to test the data pipeline and user workflow, not to make medical decisions.

## What it does

- Searches PubMed for recent publications in selected topics.
- Stores publication metadata and abstracts in SQLite.
- Detects topic, disease, sex and broad age-group mentions using transparent keyword rules.
- Keeps a user profile for research triage.
- Searches the local collection using TF-IDF retrieval.
- Generates a Markdown briefing with links to original PubMed records.
- Optionally sends retrieved abstracts to an OpenAI-compatible chat model to produce a grounded synthesis (RAG); generation is off unless credentials and a model are configured.
- Logs collection runs and application events.
- Includes statistical utilities for random-effects meta-analysis, normal-normal Bayesian updating, prior-sensitivity checks and KL divergence between normal posterior approximations.
- Research briefings include a transparent uncertainty section: what is supported, why evidence is limited, and what would reduce uncertainty.
- The report explicitly disables quantitative pooling when validated, compatible effect estimates and standard errors are unavailable.

## What it does not do

- It does not read every full text. PubMed abstracts are used where available.
- It does not reliably determine study eligibility from an abstract.
- It does not establish causality from observational associations.
- It does not recommend medication or treatment.
- It does not estimate how many years a person will live or how many years a habit will add.
- It does not continuously train or fine-tune a neural network. New knowledge enters through scheduled collection, extraction and indexing.

The age, sex and disease matching is a screening aid. A term found in an abstract does not prove that the paper reports a subgroup result for that person. A missing term does not prove that the subgroup was excluded.

## Requirements

- Python 3.10 or newer
- Internet access for PubMed collection

## Run locally

```bash
python -m venv .venv
```

Activate it:

macOS/Linux:
```bash
source .venv/bin/activate
```

Windows PowerShell:
```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Optional: set `NCBI_EMAIL` for polite use of NCBI E-utilities. To enable generated explanations, also set `OPENAI_API_KEY` and `OPENAI_MODEL` in your shell. When enabled, the configured provider receives the question, selected profile fields, retrieved publication metadata and abstracts. Do not enable this for sensitive health information unless you have reviewed the provider, its data controls and your applicable privacy obligations. The app reads environment variables directly; it does not automatically load `.env`. Without an LLM key, collection and retrieval still work and the app produces a retrieval-only briefing.

Initialize the database and start the app:

```bash
python -c "from longevity.db import init_db; init_db()"
streamlit run app.py
```

Open the local address printed by Streamlit, usually `http://localhost:8501`.

## First use

1. Set age, sex, conditions and research interests in the sidebar.
2. Open **Collect papers**.
3. Select a look-back window and run the import.
4. Open **Overview** to inspect the imported records.
5. Open **Ask the library** to search abstracts and generate a briefing.

The collector uses the PubMed E-utilities API. It searches publication dates, not necessarily the date a record first appeared online. A query may return fewer results than expected, especially when condition filters are narrow.

## Weekly automatic collection

The app has a manual collector and a script intended for a weekly scheduler.

Run once:

```bash
python weekly.py
```

On macOS/Linux, a cron entry for every Monday at 07:00 could be:

```cron
0 7 * * 1 cd /path/to/longevity-evidence-mvp && /path/to/.venv/bin/python weekly.py >> data/weekly.log 2>&1
```

On Windows, create a Task Scheduler task that runs:

- Program: `C:\path\to\python.exe`
- Arguments: `weekly.py`
- Start in: project directory

The weekly script currently monitors a fixed set of broad topics. Edit `weekly.py` to change them. For a real deployment, store each user's subscriptions separately and run deduplicated searches for all active subscriptions.

## How the matching works

The first version uses title, abstract and MeSH terms. It detects broad mentions of:

- selected conditions;
- male/female terms;
- broad adult age categories;
- longevity-related topics.

This is deliberately simple and inspectable. It is not a validated clinical cohort classifier. In particular, it cannot reliably infer exact age distributions, subgroup-specific outcomes, or whether an effect differs by sex.

The next iteration should use structured extraction with evidence spans: every extracted field should point to the sentence or table from which it was obtained. Keep `unknown` as a valid value rather than guessing.

## Uncertainty-aware reporting

Every briefing now contains a structured uncertainty assessment. It reports limitations in corpus coverage, missing abstracts, heuristic study classification, population applicability, causal interpretation, cohort independence and missing effect estimates. It does not collapse these different dimensions into one arbitrary confidence score.

The rule-based diagnostics are triage notes, not a formal GRADE assessment or a validated risk-of-bias assessment. Mention of age, sex or disease is not treated as proof of a subgroup result. The optional LLM receives the same diagnostics and is instructed to explain supporting evidence, missing information and what could reduce uncertainty. If the LLM is unavailable, the deterministic uncertainty report still works.

## Statistical module

`longevity/evidence.py` contains:

- DerSimonian–Laird random-effects pooling;
- a basic normal-normal Bayesian update;
- prior-sensitivity analysis under explicit alternative priors;
- KL divergence between normal posterior approximations (for comparing versioned updates);
- Monte Carlo draws from a normal approximation to log-effect uncertainty.

These utilities are for research-methods prototyping. The report does not automatically run them on retrieved abstracts because the MVP does not yet extract and validate effect estimates and standard errors from papers. The inputs must be compatible effect estimates, such as log risk ratios with standard errors. Do not combine different endpoints, incompatible designs, overlapping cohorts or incomparable effect measures.

The current app does not calculate personal survival probabilities. A defensible survival model would require a defined endpoint, a suitable validated baseline hazard, calibrated covariates, external validation, and careful handling of competing risks and censoring. A general-purpose RAG pipeline cannot supply those ingredients by itself.

## Logging

Application events are appended to `data/events.jsonl`.

The SQLite database also records pipeline runs, including:

- start and finish time;
- query;
- number of records found;
- number of new records inserted;
- success/error status.

Do not put names, emails, raw medical records or other direct identifiers into logs. If this becomes a hosted service, add access controls, retention rules, encryption and a privacy review before collecting health information.

## Tests

```bash
python -m pytest
```

## Project layout

```text
app.py                  Streamlit interface
weekly.py               Weekly collection entry point
longevity/
  config.py             Local paths
  db.py                 SQLite schema and persistence
  pubmed.py             PubMed E-utilities client
  extract.py            Heuristic metadata extraction
  matching.py           Profile-to-paper triage
  retrieval.py          Local TF-IDF retrieval
  report.py             Source-linked briefing builder
  llm.py                Optional grounded answer generation
  evidence.py           Statistical prototypes and posterior diagnostics
  uncertainty.py        Transparent uncertainty assessment for reports
  pipeline.py           Collection workflow
  logging_utils.py      JSONL event logging
tests/
  test_evidence.py      Basic statistical tests
```

## Suggested next steps

1. Replace keyword-only population matching with structured extraction and evidence spans.
2. Add Europe PMC and Crossref as secondary sources, with source provenance and deduplication.
3. Add a proper study-design and risk-of-bias schema.
4. Add a hybrid retriever (BM25 + embeddings + reranker).
5. Build a benchmark of manually reviewed questions and relevant papers.
6. Add claim-level evidence records: supports, contradicts, or does not directly address.
7. Add versioned evidence summaries so each weekly run can explain what changed and why.
8. Only after that, consider a survival-analysis module using a well-defined endpoint and validated external data.

## Data and source policy

Keep the original source identifiers and links. Respect PubMed/NCBI usage policies and the licences and terms of any full-text provider. Do not assume that a PubMed record grants permission to download or redistribute the publisher's full text.
