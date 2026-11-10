import math
import pytest
from longevity.meta_analysis import pool_effects, benjamini_hochberg


def _records():
    base = {
        "effect_measure": "HR",
        "outcome": "all-cause mortality",
        "population": "community-dwelling adults",
        "comparator": "highest vs lowest activity",
        "follow_up": "long-term cohort follow-up",
        "design": "prospective cohort",
    }
    return [
        {**base, "pmid": "1", "log_effect": math.log(0.82), "standard_error_log_scale": 0.05},
        {**base, "pmid": "2", "log_effect": math.log(0.90), "standard_error_log_scale": 0.07},
        {**base, "pmid": "3", "log_effect": math.log(0.86), "standard_error_log_scale": 0.06},
    ]


def test_pooling_requires_explicit_compatibility_attestation():
    with pytest.raises(ValueError, match="confirm"):
        pool_effects(_records())


def test_reml_pooling_returns_ci_and_heterogeneity():
    result = pool_effects(_records(), method="REML", confirm_compatibility=True)
    assert result["number_of_studies"] == 3
    assert result["effect_measure"] == "HR"
    lo, hi = result["ci95_ratio"]
    assert lo < result["pooled_ratio"] < hi
    assert result["tau_squared"] >= 0
    assert result["i_squared_percent"] >= 0
    assert result["prediction_interval_95_ratio"] is not None


def test_dl_pooling_with_two_studies_has_no_prediction_interval():
    result = pool_effects(_records()[:2], method="DL", confirm_compatibility=True)
    assert result["method"] == "DL"
    assert result["prediction_interval_95_ratio"] is None


def test_pooling_rejects_different_effect_measures_and_metadata():
    records = _records()
    records[1]["effect_measure"] = "RR"
    with pytest.raises(ValueError, match="same ratio effect measure"):
        pool_effects(records, confirm_compatibility=True)
    records = _records()
    records[1]["population"] = "hospital patients"
    with pytest.raises(ValueError, match="population"):
        pool_effects(records, confirm_compatibility=True)


def test_pooling_rejects_duplicate_pmids():
    records = _records()
    records[1]["pmid"] = "1"
    with pytest.raises(ValueError, match="Duplicate PMID"):
        pool_effects(records, confirm_compatibility=True)


def test_benjamini_hochberg_adjustment():
    adjusted = benjamini_hochberg([0.01, 0.04, 0.03, 0.002])
    assert len(adjusted) == 4
    assert adjusted[3] == pytest.approx(0.008)
    assert all(0 <= x <= 1 for x in adjusted)


def test_bh_rejects_invalid_pvalues():
    with pytest.raises(ValueError):
        benjamini_hochberg([0.02, 1.2])


def test_pooling_reports_null_hypothesis_test_and_relative_ci():
    result = pool_effects(_records(), confirm_compatibility=True)
    assert 0 <= result["pooled_p_value"] <= 1
    assert result["null_ratio"] == 1.0
    assert len(result["ci95_relative_change_percent"]) == 2
    assert result["ci_excludes_null"] == (result["ci95_ratio"][1] < 1 or result["ci95_ratio"][0] > 1)


def test_pooling_requires_source_identifiers():
    records = _records()
    records[0]["pmid"] = ""
    with pytest.raises(ValueError, match="PMID"):
        pool_effects(records, confirm_compatibility=True)
