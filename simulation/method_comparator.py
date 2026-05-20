"""Cross-method comparison framework. Runs Frequentist, Bayesian, Sequential, and Non-Inferiority tests"""

import os
import sys

import numpy as np
import matplotlib
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from simulation.config import (
    ALPHA, RANDOM_SEED, GIF_CONFIG, REVIEW_SORT_CONFIG,
    FIG_DIR, MATPLOTLIB_RC,
)
from simulation.data_generator import (
    generate_user_pool, generate_sessions, simulate_experiment,
)
from simulation.run_frequentist import z_test_from_groups
from simulation.run_bayesian import bayesian_ab_test
from simulation.run_non_inferiority import non_inferiority_test


# UNIFIED COMPARISON

def compare_all_methods(control_converted, treatment_converted,
                        control_guardrail=None, treatment_guardrail=None,
                        guardrail_nim=0.01, guardrail_direction="upper",
                        alpha=ALPHA, bayesian_threshold=0.95):
    """Run all four methods on the same data and return unified results"""
    c_conv = int(np.sum(control_converted))
    c_total = len(control_converted)
    t_conv = int(np.sum(treatment_converted))
    t_total = len(treatment_converted)

    # 1. Frequentist
    freq = z_test_from_groups(control_converted, treatment_converted, alpha)

    # 2. Bayesian
    bayes = bayesian_ab_test(c_conv, c_total, t_conv, t_total,
                             threshold=bayesian_threshold)

    # 3. Non-inferiority (on guardrail if provided)
    nit_result = None
    if control_guardrail is not None and treatment_guardrail is not None:
        ctrl_rate = np.mean(control_guardrail)
        trt_rate = np.mean(treatment_guardrail)
        nit_result = non_inferiority_test(
            ctrl_rate, trt_rate,
            len(control_guardrail), len(treatment_guardrail),
            nim=guardrail_nim, direction=guardrail_direction,
        )

    # Determine each method's conclusion
    freq_conclusion = "treatment_better" if freq["significant"] and freq["effect"] > 0 \
        else "control_better" if freq["significant"] and freq["effect"] < 0 \
        else "no_difference"

    bayes_conclusion = bayes["decision"]

    # Agreement
    # Normalize conclusions for agreement check
    def _normalize(c):
        if c in ("treatment_better", "treatment_wins"):
            return "treatment_better"
        if c in ("control_better", "control_wins"):
            return "control_better"
        if c in ("no_difference", "inconclusive"):
            return "inconclusive"
        return c

    methods = {
        "frequentist": freq_conclusion,
        "bayesian": bayes_conclusion,
    }
    normalized = [_normalize(c) for c in methods.values()]
    all_agree = len(set(normalized)) == 1

    return {
        "frequentist": {
            "result": freq,
            "conclusion": freq_conclusion,
        },
        "bayesian": {
            "result": {
                "prob_treatment_better": bayes["prob_treatment_better"],
                "expected_loss": bayes["expected_loss"],
                "lift": bayes["lift"],
            },
            "conclusion": bayes_conclusion,
        },
        "non_inferiority": {
            "result": nit_result,
            "conclusion": "non_inferior" if nit_result and nit_result["non_inferior"]
                          else "inferior" if nit_result else "not_tested",
        },
        "agreement": all_agree,
        "summary": methods,
    }


def generate_comparison_table(results):
    """Format comparison results as a readable table"""
    lines = []
    lines.append(f"{'Method':<20} {'Conclusion':<25} {'Key Metric':<30}")
    lines.append("-" * 75)

    # Frequentist
    f = results["frequentist"]
    lines.append(
        f"{'Frequentist':<20} {f['conclusion']:<25} "
        f"p={f['result']['p_value']:.4f}, "
        f"effect={f['result']['effect']*100:+.2f}%p"
    )

    # Bayesian
    b = results["bayesian"]
    lines.append(
        f"{'Bayesian':<20} {b['conclusion']:<25} "
        f"P(B>A)={b['result']['prob_treatment_better']:.4f}, "
        f"lift={b['result']['lift']['mean_lift']*100:+.2f}%"
    )

    # Non-inferiority
    n = results["non_inferiority"]
    if n["result"]:
        lines.append(
            f"{'Non-Inferiority':<20} {n['conclusion']:<25} "
            f"diff={n['result']['observed_diff']*100:+.2f}%p, "
            f"NIM={n['result']['nim']*100:.1f}%p"
        )
    else:
        lines.append(f"{'Non-Inferiority':<20} {'not_tested':<25}")

    lines.append("-" * 75)
    lines.append(f"Agreement: {'YES' if results['agreement'] else 'NO'}")

    return "\n".join(lines)


# BOUNDARY CONDITION FINDER

def find_disagreement_boundary(baseline=0.032, n_per_group=50_000,
                               alpha=ALPHA, bayesian_threshold=0.95,
                               seed=RANDOM_SEED):
    """Find the effect size where Frequentist and Bayesian disagree"""
    rng = np.random.default_rng(seed)
    effects = np.arange(0.0005, 0.005, 0.0002)
    disagreements = []

    for effect in effects:
        ctrl = rng.binomial(1, baseline, n_per_group)
        trt = rng.binomial(1, baseline + effect, n_per_group)

        freq = z_test_from_groups(ctrl, trt, alpha)
        c_conv, c_total = int(ctrl.sum()), len(ctrl)
        t_conv, t_total = int(trt.sum()), len(trt)
        bayes = bayesian_ab_test(c_conv, c_total, t_conv, t_total,
                                 threshold=bayesian_threshold, seed=seed)

        freq_sig = freq["significant"] and freq["effect"] > 0
        bayes_sig = bayes["decision"] == "treatment_wins"

        if freq_sig != bayes_sig:
            disagreements.append({
                "effect": effect,
                "freq_significant": freq_sig,
                "freq_p": freq["p_value"],
                "bayes_significant": bayes_sig,
                "bayes_prob": bayes["prob_treatment_better"],
            })

    return disagreements


# MAIN

def main():
    rng = np.random.default_rng(RANDOM_SEED)

    print("=" * 60)
    print("METHOD COMPARISON: Same Data, Four Methods")
    print("=" * 60)

    # Generate experiment data
    users = generate_user_pool(10_000)
    sessions = generate_sessions(users, n_days=14)
    exp = simulate_experiment(
        sessions, GIF_CONFIG,
        variant_names=["control", "treatment_a"],
    )

    ctrl = exp[exp["variant"] == "control"]
    trt = exp[exp["variant"] == "treatment_a"]

    # Simulate guardrail (bounce rate)
    ctrl_bounce = rng.binomial(1, 0.120, len(ctrl))
    trt_bounce = rng.binomial(1, 0.123, len(trt))

    print(f"\n  Control: n={len(ctrl):,}, "
          f"CVR={ctrl['converted'].mean():.4f}")
    print(f"  Treatment: n={len(trt):,}, "
          f"CVR={trt['converted'].mean():.4f}")
    print(f"  Guardrail (bounce): ctrl={ctrl_bounce.mean():.4f}, "
          f"trt={trt_bounce.mean():.4f}")

    # Run all methods
    results = compare_all_methods(
        ctrl["converted"].values, trt["converted"].values,
        control_guardrail=ctrl_bounce, treatment_guardrail=trt_bounce,
        guardrail_nim=0.01,
    )

    print(f"\n{generate_comparison_table(results)}")

    # Decision matrix application
    print("\n--- Decision Matrix ---")
    freq_c = results["frequentist"]["conclusion"]
    nit_c = results["non_inferiority"]["conclusion"]

    if freq_c == "treatment_better" and nit_c == "non_inferior":
        print("  Primary UP + Guardrail SAFE -> LAUNCH")
    elif freq_c == "treatment_better" and nit_c == "inferior":
        print("  Primary UP + Guardrail VIOLATED -> REDESIGN")
    elif freq_c == "no_difference" and nit_c == "non_inferior":
        print("  Primary FLAT + Guardrail SAFE -> DISCARD")
    elif freq_c == "control_better":
        print("  Primary DOWN -> STOP IMMEDIATELY")
    else:
        print(f"  {freq_c} + {nit_c} -> REVIEW")

    # Disagreement boundary search
    print("\n--- Frequentist vs Bayesian Disagreement Boundary ---")
    disagreements = find_disagreement_boundary()
    if disagreements:
        print(f"  Found {len(disagreements)} disagreement points:")
        for d in disagreements[:3]:
            print(f"    effect={d['effect']*100:.2f}%p: "
                  f"Freq sig={d['freq_significant']} (p={d['freq_p']:.4f}), "
                  f"Bayes sig={d['bayes_significant']} "
                  f"(P(B>A)={d['bayes_prob']:.4f})")
    else:
        print("  No disagreements found in tested range.")
        print("  (Both methods agree across all effect sizes tested)")

    print("\nMethod comparison complete.")


if __name__ == "__main__":
    main()
