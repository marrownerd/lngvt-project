import json
import os
from .logging_utils import event

SYSTEM_PROMPT = """You are a cautious scientific evidence analyst.
Use only the supplied records and uncertainty diagnostics. Do not invent study results,
effect sizes, subgroup findings, sample sizes, risk-of-bias judgments, or citations.
Do not treat keyword mentions as proof of eligibility or subgroup analysis. Distinguish
association from causation and population-level evidence from individual applicability.
Explain uncertainty explicitly: for every important conclusion state (1) what supports it,
(2) what is missing or could bias it, and (3) what evidence would reduce the uncertainty.
If effect estimates are not supplied as validated structured data, say that quantitative
pooling is unavailable. Never infer an effect from TF-IDF scores or paper counts.
Do not diagnose, prescribe, or estimate an individual's lifespan or extra years of life.
Cite claims with PMID in square brackets, e.g. [PMID: 12345678].
"""


def generate_answer(question, profile, hits, uncertainty=None):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None, "OPENAI_API_KEY is not set; the report includes rule-based uncertainty diagnostics without LLM synthesis."
    try:
        from openai import OpenAI
    except ImportError:
        return None, "Install the optional openai package to enable generated explanations."
    model = os.getenv("OPENAI_MODEL")
    if not model:
        return None, "Set OPENAI_MODEL to enable generated explanations."

    records = []
    for h in hits:
        p = h["paper"]
        records.append({
            "pmid": p["pmid"],
            "title": p["title"],
            "date": p.get("pub_date"),
            "journal": p.get("journal"),
            "url": p.get("url"),
            "study_type_heuristic": (p.get("extraction_json") or {}).get("study_type", "unknown"),
            "age_group_mentions": p.get("inferred_age_groups", []),
            "sex_mentions": p.get("inferred_sexes", []),
            "disease_mentions": p.get("inferred_diseases", []),
            "abstract": (p.get("abstract") or "")[:7000],
            "tfidf_score_is_not_evidence_strength": True,
        })
    user_payload = {
        "question": question,
        "profile": {
            "age": profile.get("age"),
            "sex": profile.get("sex"),
            "conditions": profile.get("diseases", []),
            "interests": profile.get("interests", []),
        },
        "retrieved_records": records,
        "rule_based_uncertainty_diagnostics": uncertainty or {},
        "required_output_sections": [
            "What the retrieved records support",
            "What remains uncertain and why",
            "Population applicability: what is and is not established",
            "Potential biases and missing information",
            "What evidence would reduce uncertainty",
            "Bottom line with calibrated language",
        ],
        "constraints": [
            "The retrieved set is not necessarily a systematic or exhaustive search.",
            "A mention of age/sex/disease does not establish subgroup-specific results.",
            "Do not count papers as independent studies unless independence is established.",
            "Do not pool effects: no validated compatible structured effect estimates are supplied.",
            "Do not produce a single confidence percentage or a personal health prediction.",
        ],
    }
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        )
        answer = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        event("llm_generation", model=model,
              prompt_tokens=getattr(usage, "prompt_tokens", None),
              completion_tokens=getattr(usage, "completion_tokens", None),
              retrieved_papers=len(records))
        return answer, None
    except Exception as exc:
        event("llm_generation_error", error_type=type(exc).__name__)
        return None, f"LLM generation failed ({type(exc).__name__}); rule-based uncertainty diagnostics remain available."
