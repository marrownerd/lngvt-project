# Longevity Evidence — interface and retrieval refresh

## What changed

- Reworked the Streamlit interface into a research workspace with Discover, Library,
  Research brief, Collection and Activity views.
- Added clearer hierarchy, more readable publication cards, source links and topic filters.
- Moved profile settings into a collapsible sidebar section and made their research-triage
  purpose explicit.
- Preserved the local SQLite/PubMed workflow and uncertainty-aware reporting.
- Improved baseline lexical retrieval by combining title and abstract TF-IDF scores.
- Added focused retrieval tests.

## Important limitations

This remains a Streamlit MVP, not a full Elicit clone. Search is lexical TF-IDF, not
semantic retrieval. Automated metadata labels remain heuristic. The score is not evidence
quality. The report and safety limitations remain in place.

## Run

```bash
pip install -r requirements.txt
python -m pytest
streamlit run app.py
```

## Suggested next engineering milestones

1. Build a manually labelled search benchmark and measure Recall@k / Precision@k.
2. Add filters for publication type, date and detected population, with `unknown` preserved.
3. Add a paper detail view and saved research questions.
4. Introduce BM25 + embeddings only after the baseline benchmark exists.
5. Add evidence-span extraction with explicit / inferred / unknown status.
