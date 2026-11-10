"""Conservative regex extraction of numerical effect estimates from abstracts.

This is a triage extractor, not a clinically validated NLP system. Every result
retains its exact source span and must be checked against the original paper.
"""
from __future__ import annotations

import math
import re
from typing import Any

MEASURE_ALIASES = {
    "hr": "HR", "hazard ratio": "HR", "hazard ratios": "HR",
    "rr": "RR", "risk ratio": "RR", "relative risk": "RR",
    "or": "OR", "odds ratio": "OR", "odds ratios": "OR",
    "irr": "IRR", "incidence rate ratio": "IRR", "rate ratio": "IRR",
}
MEASURE_RE = re.compile(
    r"(?P<measure>hazard ratios?|(?-i:\bHR\b)|risk ratio|relative risk|(?-i:\bRR\b)|"
    r"odds ratios?|(?-i:\bOR\b)|incidence rate ratio|(?-i:\bIRR\b)|rate ratio)"
    r"\s*(?:was|were|of|=|:)?\s*(?P<estimate>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)",
    re.IGNORECASE,
)
CI_RE = re.compile(
    r"95\s*%\s*(?:CI|confidence interval)\s*[:=,]?\s*[\[(]?\s*"
    r"(?P<lower>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*(?:-|–|—|to|,)\s*"
    r"(?P<upper>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*[\])]?\s*",
    re.IGNORECASE,
)
P_RE = re.compile(r"\bp\s*(?P<operator><=|>=|=|<|>|≤|≥)\s*(?P<value>0?\.\d+|1(?:\.0+)?)", re.IGNORECASE)
N_RE = re.compile(r"\b(?:n|N)\s*=\s*([\d,]+)")
N_CONTEXT_RE = re.compile(r"\b(?:among|in)\s+([\d,]+)\s+(?:adults|participants|patients|individuals|persons|men|women|people)\b", re.IGNORECASE)
FOLLOWUP_RE = re.compile(
    r"(?:median\s+)?follow[- ]?up(?:\s+of|\s+was|:)?\s*(\d+(?:\.\d+)?)\s*(years?|yrs?|months?|mos?)",
    re.IGNORECASE,
)

OUTCOME_TERMS = [
    ("all_cause_mortality", ("all-cause mortality", "all cause mortality", "overall mortality")),
    ("cardiovascular_mortality", ("cardiovascular mortality", "cardiac mortality")),
    ("mortality_unspecified", ("mortality", "death", "deaths")),
    ("cardiovascular_incidence", ("cardiovascular disease incidence", "incident cardiovascular disease", "cardiovascular events")),
    ("cancer_incidence", ("cancer incidence", "incident cancer")),
]


def _sentences_with_spans(text: str):
    for match in re.finditer(r".*?(?:[.!?]+(?=\s+[A-Z0-9(])|\n+|$)", text, re.DOTALL):
        raw = match.group(0)
        start = match.start()
        left = len(raw) - len(raw.lstrip())
        sentence = raw.strip()
        if sentence:
            yield sentence, start + left, start + left + len(sentence)


def _p_value(sentence: str):
    match = P_RE.search(sentence)
    if not match:
        return None, None, None
    operator = match.group("operator") or "="
    try:
        value = float(match.group("value"))
    except ValueError:
        return None, None, None
    if operator in {"<", "≤"}:
        return value, f"p {operator} {value:g}", operator
    if operator in {">", "≥"}:
        return value, f"p {operator} {value:g}", operator
    return value, f"p = {value:g}", "="


def _p_significance(p_value, p_operator, alpha=0.05):
    if p_value is None or p_operator is None:
        return None
    if p_operator in {"<", "≤"}:
        return True if p_value <= alpha else None
    if p_operator in {">", "≥"}:
        return False if p_value >= alpha else None
    return p_value < alpha


def _outcome(sentence: str):
    lower = sentence.lower()
    for label, terms in OUTCOME_TERMS:
        if any(term in lower for term in terms):
            return label
    return None


def _validate(measure: str, estimate: float, lower, upper, p_value, p_operator=None):
    errors, warnings = [], []
    ratio_measure = measure in {"HR", "RR", "OR", "IRR"}
    if not math.isfinite(estimate) or estimate <= 0:
        errors.append("Effect estimate must be finite and positive for a ratio measure.")
    if (lower is None) != (upper is None):
        errors.append("Only one confidence-interval bound was parsed.")
    if lower is not None and upper is not None:
        if not (math.isfinite(lower) and math.isfinite(upper) and lower > 0 and lower < upper):
            errors.append("Confidence interval bounds are invalid for a ratio measure.")
        elif not lower <= estimate <= upper:
            warnings.append("Point estimate lies outside the reported 95% CI; verify parsing and source.")
        elif p_value is not None:
            excludes_null = upper < 1 or lower > 1
            significant = _p_significance(p_value, p_operator)
            if significant is not None and excludes_null != significant:
                warnings.append("Approximate CI/p-value significance mismatch; check model, rounding and extraction.")
    se = None
    if ratio_measure and lower is not None and upper is not None and lower > 0 and upper > lower:
        se = (math.log(upper) - math.log(lower)) / (2 * 1.959963984540054)
        if not math.isfinite(se) or se <= 0:
            se = None
            errors.append("Could not derive a valid standard error from the confidence interval.")
    status = "invalid" if errors else ("review" if warnings or se is None else "mechanically_consistent")
    return status, errors, warnings, se


def extract_effect_estimates(paper: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract ratio effect candidates from abstract/full text, preserving provenance."""
    source_body = (paper.get("full_text") or paper.get("abstract") or "").replace("\r", "")
    if not source_body.strip():
        return []
    is_full_text = bool(paper.get("full_text"))
    source_type = paper.get("source_type") or ("Europe PMC OA full text" if is_full_text else "PubMed abstract")
    sample_match = N_RE.search(source_body) or N_CONTEXT_RE.search(source_body)
    follow_match = FOLLOWUP_RE.search(source_body)
    sample_size = int(sample_match.group(1).replace(",", "")) if sample_match else None
    follow_up = f"{follow_match.group(1)} {follow_match.group(2)}" if follow_match else None
    source_url = paper.get("url") or (f"https://pubmed.ncbi.nlm.nih.gov/{paper.get('pmid')}/" if paper.get("pmid") else None)

    results = []
    for sentence, start, end in _sentences_with_spans(source_body):
        effect_matches = list(MEASURE_RE.finditer(sentence))
        for match_index, match in enumerate(effect_matches):
            segment_end = effect_matches[match_index + 1].start() if match_index + 1 < len(effect_matches) else len(sentence)
            local_segment = sentence[match.end():segment_end]
            raw_measure = re.sub(r"\s+", " ", match.group("measure").lower()).strip()
            measure = MEASURE_ALIASES.get(raw_measure)
            if not measure:
                continue
            try:
                estimate = float(match.group("estimate"))
            except ValueError:
                continue
            # Only associate a CI that follows this estimate in the same sentence.
            tail = local_segment[:115]
            ci_match = CI_RE.search(tail)
            lower = float(ci_match.group("lower")) if ci_match else None
            upper = float(ci_match.group("upper")) if ci_match else None
            p_value, p_text, p_operator = _p_value(local_segment)
            status, errors, warnings, se = _validate(measure, estimate, lower, upper, p_value, p_operator)
            results.append({
                "pmid": str(paper.get("pmid") or ""),
                "doi": paper.get("doi"),
                "title": paper.get("title"),
                "publication_date": paper.get("pub_date"),
                "effect_measure": measure,
                "estimate": estimate,
                "ci95_lower": lower,
                "ci95_upper": upper,
                "p_value": p_value,
                "p_value_operator": p_operator,
                "p_value_text": p_text,
                "log_effect": math.log(estimate) if estimate > 0 else None,
                "standard_error_log_scale": se,
                "outcome_hint": _outcome(sentence),
                "sample_size_abstract_level": sample_size if not is_full_text else None,
                "sample_size_source_mention": sample_size,
                "follow_up_abstract_level": follow_up if not is_full_text else None,
                "follow_up_source_mention": follow_up,
                "source_type": source_type,
                "source_url": paper.get("full_text_url") or source_url,
                "source_text": sentence,
                "source_char_start": start,
                "source_char_end": end,
                "extraction_method": "regex_effect_extraction_v1",
                "validation_status": status,
                "validation_errors": errors,
                "validation_warnings": warnings,
                "review_note": "Mechanical consistency checks only; verify every value in the original article.",
            })
    return results


def extract_from_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prefer a locally cached Europe PMC OA full text; otherwise use the abstract."""
    from .open_access import load_cached_full_text, load_cached_pmcid

    output = []
    for paper in papers:
        prepared = dict(paper)
        cached = load_cached_full_text(paper)
        if cached:
            prepared["full_text"] = cached
            prepared["source_type"] = "Europe PMC OA full text (cached)"
            pmcid = paper.get("pmcid") or load_cached_pmcid(str(paper.get("pmid") or ""))
            prepared["full_text_url"] = f"https://europepmc.org/articles/{pmcid}" if pmcid else prepared.get("url")
        output.extend(extract_effect_estimates(prepared))
    return output
