"""Frequentist hypothesis testing for A/B experiments. Two-proportion z-test (conversion rate), Welch's t-test (continuous metrics),"""

import os
import sys

import numpy as np
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from simulation.config import ALPHA, RANDOM_SEED, GIF_CONFIG
from simulation.data_generator import (
    generate_user_pool, generate_sessions, simulate_experiment,
)


# PROPORTION TESTS (conversion rate)

def z_test_proportions(control_conversions, control_total,
                       treatment_conversions, treatment_total,
                       alpha=ALPHA):
    """Two-proportion z-test for conversion rate comparison"""
    p1 = control_conversions / control_total
    p2 = treatment_conversions / treatment_total
    effect = p2 - p1

    pooled = (control_conversions + treatment_conversions) / (
        control_total + treatment_total
    )
    se_pooled = np.sqrt(pooled * (1 - pooled) *
                        (1 / control_total + 1 / treatment_total))

    if se_pooled == 0:
        return {"z_stat": 0, "p_value": 1.0, "significant": False,
                "effect": effect, "ci_lower": 0, "ci_upper": 0}

    z_stat = effect / se_pooled
    p_value = 2 * (1 - stats.norm.cdf(abs(z_stat)))

    se_effect = np.sqrt(p1 * (1 - p1) / control_total +
                        p2 * (1 - p2) / treatment_total)
    z_crit = stats.norm.ppf(1 - alpha / 2)
    ci_lower = effect - z_crit * se_effect
    ci_upper = effect + z_crit * se_effect

    return {
        "z_stat": round(z_stat, 4),
        "p_value": round(p_value, 6),
        "significant": p_value < alpha,
        "effect": round(effect, 6),
        "ci_lower": round(ci_lower, 6),
        "ci_upper": round(ci_upper, 6),
    }


def z_test_from_groups(control_converted, treatment_converted, alpha=ALPHA):
    """
    Convenience wrapper: takes binary arrays (0/1) directly.
    """
    c_conv = int(np.sum(control_converted))
    c_total = len(control_converted)
    t_conv = int(np.sum(treatment_converted))
    t_total = len(treatment_converted)
    return z_test_proportions(c_conv, c_total, t_conv, t_total, alpha)


# CONTINUOUS METRIC TESTS (time on page, scroll depth, etc.)

def welch_t_test(control_values, treatment_values, alpha=ALPHA):
    """Welch's t-test for comparing means of continuous metrics"""
    control = np.asarray(control_values)
    treatment = np.asarray(treatment_values)

    t_stat, p_value = stats.ttest_ind(treatment, control, equal_var=False)
    effect = treatment.mean() - control.mean()

    se = np.sqrt(treatment.var(ddof=1) / len(treatment) +
                 control.var(ddof=1) / len(control))
    df = _welch_df(control, treatment)
    t_crit = stats.t.ppf(1 - alpha / 2, df)
    ci_lower = effect - t_crit * se
    ci_upper = effect + t_crit * se

    return {
        "t_stat": round(float(t_stat), 4),
        "p_value": round(float(p_value), 6),
        "significant": float(p_value) < alpha,
        "effect": round(float(effect), 4),
        "ci_lower": round(float(ci_lower), 4),
        "ci_upper": round(float(ci_upper), 4),
    }


def _welch_df(a, b):
    """Welch-Satterthwaite degrees of freedom"""
    va, vb = a.var(ddof=1), b.var(ddof=1)
    na, nb = len(a), len(b)
    num = (va / na + vb / nb) ** 2
    den = (va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1)
    return num / den if den > 0 else 1


# MAIN

def main():
    print("Generating experiment data...")
    users = generate_user_pool(10_000)
    sessions = generate_sessions(users, n_days=14)
    exp = simulate_experiment(
        sessions, GIF_CONFIG,
        variant_names=["control", "treatment_a", "treatment_b"],
    )

    ctrl = exp[exp["variant"] == "control"]
    trt_a = exp[exp["variant"] == "treatment_a"]
    trt_b = exp[exp["variant"] == "treatment_b"]

    print("\n--- Z-test: Treatment A vs Control ---")
    result_a = z_test_from_groups(ctrl["converted"], trt_a["converted"])
    for k, v in result_a.items():
        print(f"  {k}: {v}")

    print("\n--- Z-test: Treatment B vs Control ---")
    result_b = z_test_from_groups(ctrl["converted"], trt_b["converted"])
    for k, v in result_b.items():
        print(f"  {k}: {v}")

    print("\n--- Welch t-test: Time on Page (Treatment A vs Control) ---")
    result_t = welch_t_test(ctrl["time_on_page_sec"], trt_a["time_on_page_sec"])
    for k, v in result_t.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
