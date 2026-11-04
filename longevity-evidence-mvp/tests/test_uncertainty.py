from longevity.uncertainty import assess_uncertainty, render_uncertainty_markdown


def test_empty_corpus_explains_no_evidence_is_not_no_effect():
    result = assess_uncertainty([], {})
    text = render_uncertainty_markdown(result)
    assert result["retrieved_records"] == 0
    assert "не означает" in text.lower() or "отсутствии эффекта" in text.lower()
    assert result["statistical_pooling_ready"] is False


def test_population_mentions_are_not_claimed_as_subgroup_results():
    hits = [{"paper": {
        "pmid": "1", "title": "Study", "abstract": "Adults and women",
        "inferred_sexes": ["female"], "inferred_age_groups": ["adult"],
        "inferred_diseases": [], "extraction_json": {"study_type": "cohort"}
    }}]
    result = assess_uncertainty(hits, {"age": 70, "sex": "female", "diseases": []})
    text = render_uncertainty_markdown(result)
    assert "не подтверждение анализа подгруппы" in text
    assert "не подтверждены" in text


def test_does_not_enable_pooling_without_validated_effect_data():
    hits = [{"paper": {"pmid": "1", "title": "A", "abstract": "text"}},
            {"paper": {"pmid": "2", "title": "B", "abstract": "text"}}]
    result = assess_uncertainty(hits, {})
    assert result["statistical_pooling_ready"] is False
    assert "оценок эффекта" in result["statistical_readiness_reason"]
