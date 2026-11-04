def match_profile(paper, profile):
    """
    Conservative metadata match. 'unknown' is not treated as a match.
    Abstract-level keyword extraction is heuristic; this is a triage filter,
    not a reliable determination of study eligibility.
    """
    reasons = []
    age = profile.get("age")
    sex = profile.get("sex", "not specified")
    diseases = [x.lower() for x in profile.get("diseases", [])]

    paper_sexes = paper.get("inferred_sexes", [])
    paper_ages = paper.get("inferred_age_groups", [])
    paper_diseases = [x.lower() for x in paper.get("inferred_diseases", [])]

    if sex in ("female", "male"):
        if sex in paper_sexes:
            reasons.append(f"sex mention: {sex}")
        elif not paper_sexes:
            reasons.append("sex not specified in available text")
        else:
            reasons.append("sex mismatch or mixed population; manual review needed")

    if age is not None:
        if age >= 65 and "older_adult" in paper_ages:
            reasons.append("age group appears relevant: older adults")
        elif 40 <= age < 65 and ("middle_aged" in paper_ages or "adult" in paper_ages):
            reasons.append("age group appears potentially relevant: middle-aged/adult")
        elif age < 40 and "adult" in paper_ages:
            reasons.append("adult population mentioned; exact age match unknown")
        else:
            reasons.append("age match not established from title/abstract")

    if diseases:
        overlap = sorted(set(diseases) & set(paper_diseases))
        if overlap:
            reasons.append("disease terms found: " + ", ".join(overlap))
        else:
            reasons.append("no selected disease term detected; may still be relevant")

    return {"reasons": reasons, "triage_label": "review" if reasons else "unmatched"}
