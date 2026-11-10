# Changelog

## 0.2.0 — Evidence extraction and statistical lab

- Added a conservative regex extractor for HR/RR/OR/IRR, common 95% CI formats and p-values.
- Added source-linked candidate records with PMID/DOI, normalized text offsets, context hints, extraction method and mechanical validation flags.
- Added on-demand Europe PMC open-access full-text XML retrieval and local text caching; added a backwards-compatible SQLite `pmcid` migration.
- Added REML and DerSimonian–Laird random-effects synthesis with modified Hartung–Knapp intervals, Q, I², τ², pooled null-hypothesis p-value and a prediction interval when k >= 3.
- Added Benjamini–Hochberg adjusted p-values utility.
- Added an Evidence & statistics tab, CSV export, manual compatibility attestation and source-sentence inspection.
- Updated briefing reports and documentation to distinguish candidate extraction from confirmed evidence.
- Added tests for extraction provenance, parsing warnings, OA JATS text parsing, database migration and meta-analysis.

## Limitations

Extraction and synthesis remain research prototypes. Values require original-source review; compatibility and cohort independence are manually attested; there is no validated personalized survival or life-years model.
