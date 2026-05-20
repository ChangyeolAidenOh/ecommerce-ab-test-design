"""Bayesian A/B testing using Beta-Binomial conjugate model. No MCMC — analytical posterior via scipy.stats.beta"""

import os
import sys

import numpy as np
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from simulation.config import RANDOM_SEED, GIF_CONFIG
from simulation.data_generator import (
    generate_user_pool, generate_sessions, simulate_experiment,
)


# POSTERIOR COMPUTATION

def compute_posterior(successes, trials, prior_alpha=1, prior_beta=1):
    """Compute Beta posterior parameters"""
    post_alpha = prior_alpha + successes
    post_beta = prior_beta + (trials - successes)
    dist = stats.beta(post_alpha, post_beta)

    return {
        "alpha": post_alpha,
        "beta": post_beta,
        "mean": round(float(dist.mean()), 6),
        "std": round(float(dist.std()), 6),
        "ci_lower": round(float(dist.ppf(0.025)), 6),
        "ci_upper": round(float(dist.ppf(0.975)), 6),
    }


# COMPARISON METRICS

def probability_of_improvement(post_a, post_b, n_samples=100_000,
                               seed=RANDOM_SEED):
    """P(B > A) via Monte Carlo sampling from posteriors"""
    rng = np.random.default_rng(seed)
    samples_a = rng.beta(post_a["alpha"], post_a["beta"], n_samples)
    samples_b = rng.beta(post_b["alpha"], post_b["beta"], n_samples)
    return float(np.mean(samples_b > samples_a))


def expected_loss(post_a, post_b, n_samples=100_000, seed=RANDOM_SEED):
    """Expected loss of choosing B over A"""
    rng = np.random.default_rng(seed)
    samples_a = rng.beta(post_a["alpha"], post_a["beta"], n_samples)
    samples_b = rng.beta(post_b["alpha"], post_b["beta"], n_samples)

    loss_b = float(np.mean(np.maximum(samples_a - samples_b, 0)))
    loss_a = float(np.mean(np.maximum(samples_b - samples_a, 0)))

    return {
        "loss_choose_b": round(loss_b, 6),
        "loss_choose_a": round(loss_a, 6),
    }


def compute_lift_distribution(post_a, post_b, n_samples=100_000,
                              seed=RANDOM_SEED):
    """Distribution of relative lift: (B - A) / A"""
    rng = np.random.default_rng(seed)
    samples_a = rng.beta(post_a["alpha"], post_a["beta"], n_samples)
    samples_b = rng.beta(post_b["alpha"], post_b["beta"], n_samples)

    lift = (samples_b - samples_a) / samples_a

    return {
        "mean_lift": round(float(np.mean(lift)), 6),
        "median_lift": round(float(np.median(lift)), 6),
        "ci_lower": round(float(np.percentile(lift, 2.5)), 6),
        "ci_upper": round(float(np.percentile(lift, 97.5)), 6),
    }


# FULL BAYESIAN AB TEST

def bayesian_ab_test(control_conversions, control_total,
                     treatment_conversions, treatment_total,
                     prior_alpha=1, prior_beta=1,
                     threshold=0.95, seed=RANDOM_SEED):
    """Run complete Bayesian AB test"""
    post_ctrl = compute_posterior(
        control_conversions, control_total, prior_alpha, prior_beta
    )
    post_trt = compute_posterior(
        treatment_conversions, treatment_total, prior_alpha, prior_beta
    )

    prob_imp = probability_of_improvement(post_ctrl, post_trt, seed=seed)
    losses = expected_loss(post_ctrl, post_trt, seed=seed)
    lift = compute_lift_distribution(post_ctrl, post_trt, seed=seed)

    if prob_imp >= threshold:
        decision = "treatment_wins"
    elif prob_imp <= (1 - threshold):
        decision = "control_wins"
    else:
        decision = "inconclusive"

    return {
        "posterior_control": post_ctrl,
        "posterior_treatment": post_trt,
        "prob_treatment_better": round(prob_imp, 4),
        "expected_loss": losses,
        "lift": lift,
        "decision": decision,
        "threshold": threshold,
    }


# MAIN

def main():
    print("Generating experiment data...")
    users = generate_user_pool(10_000)
    sessions = generate_sessions(users, n_days=14)
    exp = simulate_experiment(
        sessions, GIF_CONFIG,
        variant_names=["control", "treatment_a"],
    )

    ctrl = exp[exp["variant"] == "control"]
    trt = exp[exp["variant"] == "treatment_a"]

    c_conv = int(ctrl["converted"].sum())
    c_total = len(ctrl)
    t_conv = int(trt["converted"].sum())
    t_total = len(trt)

    print(f"\n  Control: {c_conv}/{c_total} = {c_conv/c_total:.4f}")
    print(f"  Treatment: {t_conv}/{t_total} = {t_conv/t_total:.4f}")

    print("\n--- Bayesian AB Test ---")
    result = bayesian_ab_test(c_conv, c_total, t_conv, t_total)

    print(f"\n  Posterior Control: mean={result['posterior_control']['mean']:.4f}, "
          f"95% CI=[{result['posterior_control']['ci_lower']:.4f}, "
          f"{result['posterior_control']['ci_upper']:.4f}]")
    print(f"  Posterior Treatment: mean={result['posterior_treatment']['mean']:.4f}, "
          f"95% CI=[{result['posterior_treatment']['ci_lower']:.4f}, "
          f"{result['posterior_treatment']['ci_upper']:.4f}]")
    print(f"\n  P(Treatment > Control): {result['prob_treatment_better']:.4f}")
    print(f"  Expected loss (choose treatment): "
          f"{result['expected_loss']['loss_choose_b']:.6f}")
    print(f"  Expected loss (choose control): "
          f"{result['expected_loss']['loss_choose_a']:.6f}")
    print(f"\n  Lift: mean={result['lift']['mean_lift']*100:.2f}%, "
          f"95% CI=[{result['lift']['ci_lower']*100:.2f}%, "
          f"{result['lift']['ci_upper']*100:.2f}%]")
    print(f"\n  Decision (threshold={result['threshold']}): {result['decision']}")


if __name__ == "__main__":
    main()
