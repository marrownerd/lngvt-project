"""Conservative random-effects synthesis for manually verified log-ratio effects."""
from __future__ import annotations

import math
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import chi2, norm, t

REQUIRED_COMPATIBILITY_FIELDS = ("outcome", "population", "comparator", "follow_up", "design")


def _as_arrays(records):
    if len(records) < 2:
        raise ValueError("At least two independent study estimates are required.")
    measures = {r.get("effect_measure") for r in records}
    if len(measures) != 1 or next(iter(measures)) not in {"HR", "RR", "OR", "IRR"}:
        raise ValueError("All records must use the same ratio effect measure (HR, RR, OR or IRR).")
    missing = [field for field in REQUIRED_COMPATIBILITY_FIELDS if any(not str(r.get(field) or "").strip() for r in records)]
    if missing:
        raise ValueError("Declare and verify common synthesis metadata before pooling: " + ", ".join(missing))
    for field in REQUIRED_COMPATIBILITY_FIELDS:
        if len({str(r[field]).strip().casefold() for r in records}) != 1:
            raise ValueError(f"Records differ on '{field}'. Split the analysis or review compatibility.")
    pmids = [str(r.get("pmid") or "") for r in records]
    if any(not value for value in pmids):
        raise ValueError("Every estimate must retain a PMID for source traceability.")
    if len(set(pmids)) != len(pmids):
        raise ValueError("Duplicate PMID records cannot be treated as independent studies.")
    y = np.asarray([r.get("log_effect") for r in records], dtype=float)
    se = np.asarray([r.get("standard_error_log_scale") for r in records], dtype=float)
    if not np.all(np.isfinite(y)) or not np.all(np.isfinite(se)) or np.any(se <= 0):
        raise ValueError("Every record needs a finite log effect and positive standard error derived from a valid CI.")
    return y, se, next(iter(measures))


def _reml_tau2(y, se):
    variances = se ** 2
    spread = max(float(np.var(y, ddof=1)), float(np.max(variances)), 1e-8)
    upper = max(spread * 1000.0, 1.0)

    def objective(tau2):
        w = 1.0 / (variances + tau2)
        mu = float(np.sum(w * y) / np.sum(w))
        residual = float(np.sum(w * (y - mu) ** 2))
        return float(np.sum(np.log(variances + tau2)) + np.log(np.sum(w)) + residual)

    result = minimize_scalar(objective, bounds=(0.0, upper), method="bounded", options={"xatol": 1e-12})
    candidates = [(0.0, objective(0.0)), (float(result.x), float(result.fun)), (upper, objective(upper))]
    return min(candidates, key=lambda x: x[1])[0]


def pool_effects(records, method="REML", hartung_knapp=True, confirm_compatibility=False):
    """Pool same-scale, manually reviewed estimates. Returns ratio-scale summaries.

    The caller must explicitly attest to endpoint/population/comparator/follow-up/design
    compatibility and independence. This function cannot infer those properties.
    """
    if not confirm_compatibility:
        raise ValueError("Pooling is disabled until you confirm endpoint, population, comparator, follow-up, design and study independence.")
    y, se, measure = _as_arrays(records)
    method = method.upper()
    if method not in {"REML", "DL"}:
        raise ValueError("method must be 'REML' or 'DL'.")
    w_fixed = 1.0 / se ** 2
    fixed = float(np.sum(w_fixed * y) / np.sum(w_fixed))
    q = float(np.sum(w_fixed * (y - fixed) ** 2))
    df = len(y) - 1
    c = float(np.sum(w_fixed) - np.sum(w_fixed ** 2) / np.sum(w_fixed))
    tau2_dl = max(0.0, (q - df) / c) if c > 0 else 0.0
    tau2 = tau2_dl if method == "DL" else _reml_tau2(y, se)
    weights = 1.0 / (se ** 2 + tau2)
    pooled = float(np.sum(weights * y) / np.sum(weights))
    conventional_se = math.sqrt(1.0 / float(np.sum(weights)))

    hk_q = float(np.sum(weights * (y - pooled) ** 2) / df) if df > 0 else 1.0
    if hartung_knapp:
        # Modified Hartung–Knapp: do not allow the variance multiplier below one.
        hk_multiplier = max(1.0, hk_q)
        pooled_se = conventional_se * math.sqrt(hk_multiplier)
        critical = float(t.ppf(0.975, df))
        ci_method = "modified Hartung–Knapp t interval"
    else:
        hk_multiplier = None
        pooled_se = conventional_se
        critical = 1.959963984540054
        ci_method = "normal-approximation interval"
    lo, hi = pooled - critical * pooled_se, pooled + critical * pooled_se
    test_statistic = pooled / pooled_se
    pooled_p_value = (float(2.0 * t.sf(abs(test_statistic), df)) if hartung_knapp
                      else float(2.0 * norm.sf(abs(test_statistic))))

    i2 = max(0.0, (q - df) / q) * 100.0 if q > 0 else 0.0
    p_q = float(chi2.sf(q, df)) if df > 0 else None
    if len(y) > 2:
        pred_critical = float(t.ppf(0.975, len(y) - 2))
        pred_half = pred_critical * math.sqrt(tau2 + pooled_se ** 2)
        prediction_interval = [math.exp(pooled - pred_half), math.exp(pooled + pred_half)]
    else:
        prediction_interval = None

    return {
        "effect_measure": measure,
        "number_of_studies": int(len(y)),
        "method": method,
        "pooled_log_effect": pooled,
        "pooled_ratio": math.exp(pooled),
        "ci95_ratio": [math.exp(lo), math.exp(hi)],
        "ci95_relative_change_percent": [(math.exp(lo) - 1.0) * 100.0, (math.exp(hi) - 1.0) * 100.0],
        "pooled_p_value": pooled_p_value,
        "null_ratio": 1.0,
        "ci_excludes_null": bool(hi < 0.0 or lo > 0.0),
        "standard_error_log_scale": pooled_se,
        "ci_method": ci_method,
        "tau_squared": float(tau2),
        "tau_squared_dl_reference": float(tau2_dl),
        "q": q,
        "q_p_value": p_q,
        "i_squared_percent": float(i2),
        "hartung_knapp_multiplier": hk_multiplier,
        "prediction_interval_95_ratio": prediction_interval,
        "interpretation": f"Pooled {measure} ratio; values below 1 indicate a lower relative {measure} in the exposed/intervention group under the studies' estimands. Not an absolute risk reduction or years of life.",
        "compatibility_attestation": "User-confirmed; not independently verified by software.",
    }


def benjamini_hochberg(p_values):
    """Return BH-adjusted p-values in original order; NaNs remain NaN."""
    p = np.asarray(p_values, dtype=float)
    out = np.full(p.shape, np.nan, dtype=float)
    valid = np.isfinite(p)
    pv = p[valid]
    if np.any((pv < 0) | (pv > 1)):
        raise ValueError("p-values must be between 0 and 1.")
    if pv.size:
        order = np.argsort(pv)
        ranked = pv[order]
        adjusted = ranked * pv.size / np.arange(1, pv.size + 1)
        adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
        restored = np.empty_like(adjusted)
        restored[order] = np.minimum(adjusted, 1.0)
        out[valid] = restored
    return out.tolist()
