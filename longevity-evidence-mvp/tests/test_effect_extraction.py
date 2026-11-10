from longevity.effect_extraction import extract_effect_estimates


def test_extracts_hr_ci_pvalue_and_preserves_provenance():
    paper = {
        "pmid": "12345",
        "doi": "10.1000/example",
        "title": "Physical activity and mortality",
        "pub_date": "2024",
        "url": "https://pubmed.ncbi.nlm.nih.gov/12345/",
        "abstract": (
            "Among 12,345 adults followed for a median follow-up of 10 years, "
            "higher activity was associated with lower all-cause mortality "
            "(HR 0.82, 95% CI 0.74–0.91; p=0.002)."
        ),
    }
    rows = extract_effect_estimates(paper)
    assert len(rows) == 1
    row = rows[0]
    assert row["effect_measure"] == "HR"
    assert row["estimate"] == 0.82
    assert row["ci95_lower"] == 0.74
    assert row["ci95_upper"] == 0.91
    assert row["p_value"] == 0.002
    assert row["standard_error_log_scale"] > 0
    assert row["validation_status"] == "mechanically_consistent"
    assert row["outcome_hint"] == "all_cause_mortality"
    assert row["sample_size_abstract_level"] == 12345
    assert row["follow_up_abstract_level"] == "10 years"
    assert row["source_text"].startswith("Among 12,345")
    assert paper["abstract"][row["source_char_start"]:row["source_char_end"]] == row["source_text"]
    assert row["source_url"] == paper["url"]


def test_extracts_risk_ratio_and_less_than_p_value():
    rows = extract_effect_estimates({
        "pmid": "22",
        "abstract": "The risk ratio was 1.20 (95% confidence interval 1.05 to 1.35), p < 0.01.",
    })
    assert len(rows) == 1
    assert rows[0]["effect_measure"] == "RR"
    assert rows[0]["ci95_lower"] == 1.05
    assert rows[0]["ci95_upper"] == 1.35
    assert rows[0]["p_value_text"] == "p < 0.01"
    assert rows[0]["validation_status"] == "mechanically_consistent"


def test_flags_point_estimate_outside_ci():
    rows = extract_effect_estimates({
        "pmid": "33",
        "abstract": "The hazard ratio was 0.70 (95% CI 0.80–0.95).",
    })
    assert len(rows) == 1
    assert rows[0]["validation_status"] == "review"
    assert any("outside" in x for x in rows[0]["validation_warnings"])


def test_does_not_extract_non_ratio_mean_difference_as_ratio():
    rows = extract_effect_estimates({
        "pmid": "44",
        "abstract": "The mean difference was -2.4 points (95% CI -3.1 to -1.7).",
    })
    assert rows == []


def test_missing_abstract_returns_no_candidates():
    assert extract_effect_estimates({"pmid": "55", "abstract": ""}) == []


def test_full_text_source_is_labeled_and_offsets_point_into_full_text():
    from longevity.effect_extraction import extract_effect_estimates
    full_text = "Results\nThe adjusted hazard ratio was 0.82 (95% CI 0.74–0.91)."
    rows = extract_effect_estimates({
        "pmid": "66", "full_text": full_text,
        "source_type": "Europe PMC OA full text", "full_text_url": "https://europepmc.org/articles/PMC123",
    })
    assert len(rows) == 1
    row = rows[0]
    assert row["source_type"] == "Europe PMC OA full text"
    assert full_text[row["source_char_start"]:row["source_char_end"]] == row["source_text"]
    assert row["source_url"] == "https://europepmc.org/articles/PMC123"


def test_lowercase_english_conjunction_or_is_not_mistaken_for_odds_ratio():
    rows = extract_effect_estimates({
        "pmid": "77",
        "abstract": "Participants were assigned to group A or 0.9 of the sample completed follow-up.",
    })
    assert rows == []


def test_greater_than_p_value_operator_is_retained_for_review():
    rows = extract_effect_estimates({
        "pmid": "78",
        "abstract": "The hazard ratio was 0.82 (95% CI 0.74–0.91), p > 0.05.",
    })
    assert len(rows) == 1
    assert rows[0]["p_value_operator"] == ">"
    assert rows[0]["validation_status"] == "review"


def test_multiple_effects_in_same_sentence_get_their_own_pvalues():
    text = (
        "All-cause mortality was associated with activity (HR 0.82, 95% CI 0.74–0.91; p=0.002) "
        "and the secondary odds analysis was (OR 0.90, 95% CI 0.80–1.05; p=0.20)."
    )
    rows = extract_effect_estimates({"pmid": "79", "abstract": text})
    assert len(rows) == 2
    assert rows[0]["p_value"] == 0.002
    assert rows[1]["p_value"] == 0.20
