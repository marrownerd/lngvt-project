import math
import numpy as np
from scipy.stats import norm

def normal_normal_update(prior_mean=0.0, prior_sd=1.0, observed_effects=None, observed_ses=None):
    """
    Simple fixed-effect normal-normal illustration on log effect sizes.
    Input effects should be log(RR), log(HR), or another compatible metric.
    This is not a full meta-analysis and must not combine unlike outcomes/designs.
    """
    observed_effects = observed_effects or []
    observed_ses = observed_ses or []
    if len(observed_effects) != len(observed_ses) or not observed_effects:
        return None
    prior_precision = 1 / (prior_sd ** 2)
    likelihood_precision = sum(1 / (s ** 2) for s in observed_ses if s > 0)
    if likelihood_precision == 0:
        return None
    post_var = 1 / (prior_precision + likelihood_precision)
    post_mean = post_var * (
        prior_mean * prior_precision +
        sum(y / (s ** 2) for y, s in zip(observed_effects, observed_ses) if s > 0)
    )
    post_sd = math.sqrt(post_var)
    lo, hi = post_mean - 1.96*post_sd, post_mean + 1.96*post_sd
    return {
        "posterior_mean_log_effect": post_mean,
        "posterior_sd": post_sd,
        "interval_95_log_scale": [lo, hi],
        "probability_effect_below_zero": float(norm.cdf(0, loc=post_mean, scale=post_sd)),
        "note": "Illustrative fixed-effect normal-normal calculation; not a validated personal prognosis."
    }

def random_effects_dl(effects, standard_errors):
    """
    DerSimonian-Laird random-effects meta-analysis.
    Effects must be commensurable (same estimand and scale).
    Returns pooled estimate, SE, CI and estimated between-study variance.
    """
    y = np.asarray(effects, dtype=float)
    se = np.asarray(standard_errors, dtype=float)
    if len(y) < 2 or len(y) != len(se) or np.any(se <= 0):
        raise ValueError("Provide at least two effects and positive standard errors.")
    w = 1 / se**2
    fixed = np.sum(w*y)/np.sum(w)
    q = np.sum(w*(y-fixed)**2)
    df = len(y)-1
    c = np.sum(w) - np.sum(w**2)/np.sum(w)
    tau2 = max(0.0, (q-df)/c) if c > 0 else 0.0
    wr = 1/(se**2 + tau2)
    pooled = np.sum(wr*y)/np.sum(wr)
    pooled_se = math.sqrt(1/np.sum(wr))
    return {
        "pooled_effect": float(pooled),
        "standard_error": float(pooled_se),
        "ci95": [float(pooled-1.96*pooled_se), float(pooled+1.96*pooled_se)],
        "tau_squared": float(tau2),
        "q": float(q),
        "degrees_freedom": int(df),
        "interpretation": "Effect estimate on the input scale. Do not interpret as years of life."
    }

def simulate_uncertainty(mean_log_effect, sd_log_effect, draws=10000, seed=7):
    """
    Draws from a normal approximation to uncertainty in a log effect.
    This is a stochastic uncertainty model, not a survival model.
    """
    rng = np.random.default_rng(seed)
    draws_arr = rng.normal(mean_log_effect, sd_log_effect, draws)
    ratios = np.exp(draws_arr)
    return {
        "median_ratio": float(np.median(ratios)),
        "ratio_95_interval": [float(np.quantile(ratios, .025)), float(np.quantile(ratios, .975))],
        "probability_ratio_below_1": float(np.mean(ratios < 1)),
        "draws": int(draws),
        "warning": "Posterior simulation only; not an individual life-expectancy estimate."
    }


def normal_kl_divergence(mean_p, sd_p, mean_q, sd_q):
    """KL divergence KL(P || Q) for two univariate normal distributions.

    Useful for comparing versioned posterior approximations. It is directional
    and is not, by itself, a measure of evidence quality or clinical importance.
    """
    values = [mean_p, sd_p, mean_q, sd_q]
    if not all(math.isfinite(float(x)) for x in values) or sd_p <= 0 or sd_q <= 0:
        raise ValueError("Means must be finite and standard deviations positive.")
    return float(
        math.log(sd_q / sd_p)
        + (sd_p ** 2 + (mean_p - mean_q) ** 2) / (2 * sd_q ** 2)
        - 0.5
    )


def prior_sensitivity(observed_effects, observed_ses, prior_scenarios=None):
    """Repeat the normal-normal update under explicit alternative priors.

    This is a sensitivity diagnostic, not a substitute for a hierarchical model.
    Inputs must be commensurable estimates on the same scale.
    """
    prior_scenarios = prior_scenarios or [
        {"name": "skeptical", "mean": 0.0, "sd": 0.25},
        {"name": "weakly_informative", "mean": 0.0, "sd": 1.0},
        {"name": "wide", "mean": 0.0, "sd": 2.5},
    ]
    results = []
    for scenario in prior_scenarios:
        result = normal_normal_update(
            prior_mean=scenario["mean"],
            prior_sd=scenario["sd"],
            observed_effects=observed_effects,
            observed_ses=observed_ses,
        )
        results.append({"prior": scenario["name"], "result": result})
    valid = [x["result"] for x in results if x["result"] is not None]
    if len(valid) > 1:
        means = [x["posterior_mean_log_effect"] for x in valid]
        interval_lowers = [x["interval_95_log_scale"][0] for x in valid]
        interval_uppers = [x["interval_95_log_scale"][1] for x in valid]
        summary = {
            "posterior_mean_range": [float(min(means)), float(max(means))],
            "interval_lower_range": [float(min(interval_lowers)), float(max(interval_lowers))],
            "interval_upper_range": [float(min(interval_uppers)), float(max(interval_uppers))],
            "interpretation": "Large variation across priors indicates prior sensitivity; inspect assumptions before interpreting the result.",
        }
    else:
        summary = {"interpretation": "Insufficient valid posterior results to assess prior sensitivity."}
    return {"scenarios": results, "summary": summary}
