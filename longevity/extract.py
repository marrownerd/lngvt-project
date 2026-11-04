import re

DISEASE_TERMS = [
    "diabetes", "hypertension", "cardiovascular disease", "heart failure",
    "cancer", "obesity", "dementia", "alzheimer", "parkinson", "chronic kidney disease",
    "copd", "stroke", "coronary artery disease"
]
TOPIC_TERMS = {
    "physical_activity": ["exercise", "physical activity", "fitness", "walking", "resistance training"],
    "sleep": ["sleep", "circadian", "insomnia"],
    "diet": ["diet", "nutrition", "mediterranean", "protein intake", "dietary"],
    "smoking": ["smoking", "tobacco", "smoking cessation"],
    "alcohol": ["alcohol", "drinking"],
    "social_connection": ["social isolation", "loneliness", "social support"]
}
AGE_PATTERNS = {
    "older_adult": [r"older adults", r"elderly", r"aged 65", r"65 years", r"over 60"],
    "middle_aged": [r"middle-aged", r"aged 40", r"aged 45", r"40-65"],
    "adult": [r"adults", r"adult participants"]
}
SEX_TERMS = {
    "female": ["women", "woman", "female", "girls"],
    "male": ["men", "man", "male", "boys"]
}

def infer_metadata(paper):
    text = (paper.get("title","") + " " + paper.get("abstract","") + " " +
            " ".join(paper.get("mesh_terms",[]))).lower()
    diseases = sorted({d for d in DISEASE_TERMS if d in text})
    topics = sorted({topic for topic, terms in TOPIC_TERMS.items()
                     if any(t in text for t in terms)})
    sexes = [s for s, terms in SEX_TERMS.items() if any(t in text for t in terms)]
    ages = [group for group, patterns in AGE_PATTERNS.items()
            if any(re.search(p, text) for p in patterns)]
    pub_types = [x.lower() for x in paper.get("publication_types",[])]
    if any("randomized controlled trial" in x for x in pub_types):
        study_type = "randomized_controlled_trial"
    elif any("meta-analysis" in x for x in pub_types):
        study_type = "meta_analysis"
    elif any("systematic review" in x for x in pub_types):
        study_type = "systematic_review"
    elif any("cohort" in x for x in pub_types):
        study_type = "cohort"
    else:
        study_type = "not_classified"
    return {
        "diseases": diseases, "topics": topics, "sexes": sexes,
        "age_groups": ages, "study_type": study_type,
        "species": "human" if "humans" in [m.lower() for m in paper.get("mesh_terms",[])] else "unknown"
    }

def enrich(paper):
    x = infer_metadata(paper)
    paper["inferred_diseases"] = x["diseases"]
    paper["inferred_topics"] = x["topics"]
    paper["inferred_sexes"] = x["sexes"]
    paper["inferred_age_groups"] = x["age_groups"]
    paper["extraction"] = x
    return paper
