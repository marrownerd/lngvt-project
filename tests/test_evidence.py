from longevity.evidence import random_effects_dl, normal_normal_update, simulate_uncertainty

def test_random_effects_returns_interval():
    r = random_effects_dl([0.1, 0.2, 0.15], [0.05, 0.08, 0.06])
    assert r["ci95"][0] < r["pooled_effect"] < r["ci95"][1]
    assert r["tau_squared"] >= 0

def test_bayesian_update():
    r = normal_normal_update(0, 1, [-0.1, -0.2], [0.1, 0.1])
    assert r["posterior_mean_log_effect"] < 0

def test_simulation_reproducible():
    a = simulate_uncertainty(-0.1, 0.1, seed=42)
    b = simulate_uncertainty(-0.1, 0.1, seed=42)
    assert a["median_ratio"] == b["median_ratio"]


def test_normal_kl_divergence_is_zero_for_identical_distributions():
    from longevity.evidence import normal_kl_divergence
    assert abs(normal_kl_divergence(0, 1, 0, 1)) < 1e-12


def test_prior_sensitivity_returns_named_scenarios():
    from longevity.evidence import prior_sensitivity
    result = prior_sensitivity([-0.15, -0.2], [0.1, 0.12])
    assert len(result["scenarios"]) == 3
    assert "posterior_mean_range" in result["summary"]
