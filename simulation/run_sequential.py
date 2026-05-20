"""Sequential testing and peeking problem simulation. Demonstrates why checking p-values mid-experiment inflates Type I error,"""

import os
import sys

import numpy as np
from scipy import stats
import matplotlib
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from simulation.config import (
    ALPHA, N_SIMULATIONS, RANDOM_SEED,
    FIG_DIR, MATPLOTLIB_RC,
)


# PEEKING PROBLEM SIMULATION

def simulate_peeking(n_per_group=10_000, n_simulations=N_SIMULATIONS,
                     peek_interval=500, baseline_rate=0.032,
                     true_effect=0.0, alpha=ALPHA, seed=RANDOM_SEED):
    """Simulate the peeking problem: checking p-values at regular intervals"""
    rng = np.random.default_rng(seed)
    peek_points = list(range(peek_interval, n_per_group + 1, peek_interval))
    if peek_points[-1] != n_per_group:
        peek_points.append(n_per_group)

    # Track at which peek each simulation first becomes significant
    first_significant_at = np.full(n_simulations, -1, dtype=int)

    for sim in range(n_simulations):
        control = rng.binomial(1, baseline_rate, n_per_group)
        treatment = rng.binomial(1, baseline_rate + true_effect, n_per_group)

        for peek_n in peek_points:
            if first_significant_at[sim] >= 0:
                break  # already flagged, skip remaining peeks

            c_conv = control[:peek_n].sum()
            t_conv = treatment[:peek_n].sum()
            pooled = (c_conv + t_conv) / (2 * peek_n)

            if pooled == 0 or pooled == 1:
                continue

            se = np.sqrt(2 * pooled * (1 - pooled) / peek_n)
            z = abs(t_conv / peek_n - c_conv / peek_n) / se
            p_val = 2 * (1 - stats.norm.cdf(z))

            if p_val < alpha:
                first_significant_at[sim] = peek_n

    # Compute cumulative FP rate at each peek point
    cumulative_fp = {}
    for p in peek_points:
        n_flagged = np.sum((first_significant_at >= 0) &
                           (first_significant_at <= p))
        cumulative_fp[p] = n_flagged / n_simulations

    return {
        "peek_points": peek_points,
        "cumulative_fp_rates": cumulative_fp,
        "final_fp_rate": cumulative_fp[peek_points[-1]],
        "nominal_alpha": alpha,
        "n_simulations": n_simulations,
    }


# SPRT (Sequential Probability Ratio Test)

def sprt(control_outcomes, treatment_outcomes, h0_rate=0.032,
         h1_rate=0.035, alpha=ALPHA, beta=0.20):
    """Sequential Probability Ratio Test for two proportions"""
    A = np.log((1 - beta) / alpha)      # upper boundary (reject H0)
    B = np.log(beta / (1 - alpha))      # lower boundary (accept H0)

    n = min(len(control_outcomes), len(treatment_outcomes))
    log_lr = 0.0
    log_lrs = []
    decision = "continue"
    stopping_point = n

    for i in range(n):
        c = control_outcomes[i]
        t = treatment_outcomes[i]

        # Log-likelihood ratio for this observation pair
        if t == 1:
            log_lr += np.log(h1_rate / h0_rate)
        else:
            log_lr += np.log((1 - h1_rate) / (1 - h0_rate))

        if c == 1:
            log_lr -= np.log(h1_rate / h0_rate)
        else:
            log_lr -= np.log((1 - h1_rate) / (1 - h0_rate))

        log_lrs.append(log_lr)

        if log_lr >= A:
            decision = "reject_h0"
            stopping_point = i + 1
            break
        elif log_lr <= B:
            decision = "accept_h0"
            stopping_point = i + 1
            break

    return {
        "decision": decision,
        "stopping_point": stopping_point,
        "total_observations": n,
        "log_likelihood_ratios": log_lrs,
        "upper_boundary": A,
        "lower_boundary": B,
    }


# VISUALIZATION

def plot_peeking_inflation(result, save_path=None):
    """Plot cumulative false positive rate across peek points"""
    matplotlib.rcParams.update(MATPLOTLIB_RC)
    fig, ax = plt.subplots()

    peeks = result["peek_points"]
    fp_rates = [result["cumulative_fp_rates"][p] for p in peeks]

    ax.plot(peeks, fp_rates, color="#dc2626", linewidth=2, label="Peeking FP rate")
    ax.axhline(y=result["nominal_alpha"], color="#22c55e", linestyle="--",
               linewidth=1.5, label=f"Nominal alpha={result['nominal_alpha']}")
    ax.set_xlabel("Sample size per group at peek")
    ax.set_ylabel("Cumulative False Positive Rate")
    ax.set_title("Peeking Problem: Type I Error Inflation")
    ax.legend()

    final_fp = result["final_fp_rate"]
    ax.annotate(f"Final FP rate: {final_fp:.1%}\n"
                f"(vs nominal {result['nominal_alpha']:.0%})",
                xy=(peeks[-1], final_fp),
                xytext=(peeks[-1] * 0.6, final_fp + 0.03),
                fontsize=10,
                arrowprops=dict(arrowstyle="->", color="#64748b"))

    plt.tight_layout()
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved: {save_path}")
    plt.close(fig)
    return fig


def plot_sprt_path(result, save_path=None):
    """Plot SPRT log-likelihood ratio path with decision boundaries"""
    matplotlib.rcParams.update(MATPLOTLIB_RC)
    fig, ax = plt.subplots()

    lrs = result["log_likelihood_ratios"]
    ax.plot(range(1, len(lrs) + 1), lrs, color="#2563eb", linewidth=1.5,
            label="Log-LR path")
    ax.axhline(y=result["upper_boundary"], color="#dc2626", linestyle="--",
               label=f"Reject H0 (A={result['upper_boundary']:.2f})")
    ax.axhline(y=result["lower_boundary"], color="#22c55e", linestyle="--",
               label=f"Accept H0 (B={result['lower_boundary']:.2f})")

    if result["decision"] != "continue":
        color = "#dc2626" if result["decision"] == "reject_h0" else "#22c55e"
        ax.axvline(x=result["stopping_point"], color=color, linestyle=":",
                   alpha=0.5)
        ax.annotate(f"Stop at n={result['stopping_point']}\n{result['decision']}",
                    xy=(result["stopping_point"], lrs[result["stopping_point"] - 1]),
                    fontsize=9)

    ax.set_xlabel("Observation pairs")
    ax.set_ylabel("Cumulative Log-Likelihood Ratio")
    ax.set_title("SPRT Decision Path")
    ax.legend(fontsize=9)
    plt.tight_layout()

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved: {save_path}")
    plt.close(fig)
    return fig


# MAIN

def main():
    print("=" * 60)
    print("=" * 60)
    print("Simulating 10,000 experiments where H0 is TRUE (no effect)...")
    print("Checking p-value every 500 observations per group...\n")

    result = simulate_peeking(
        n_per_group=10_000,
        n_simulations=10_000,
        peek_interval=500,
        baseline_rate=0.032,
        true_effect=0.0,
    )

    peeks = result["peek_points"]
    print(f"  Nominal alpha: {result['nominal_alpha']:.2%}")
    print(f"  Final cumulative FP rate: {result['final_fp_rate']:.2%}")
    print(f"  Inflation factor: {result['final_fp_rate'] / result['nominal_alpha']:.1f}x")
    print(f"\n  FP rate at selected peek points:")
    for p in [1000, 2000, 5000, 10000]:
        if p in result["cumulative_fp_rates"]:
            print(f"    n={p:,}: {result['cumulative_fp_rates'][p]:.2%}")

    plot_peeking_inflation(
        result,
        save_path=os.path.join(FIG_DIR, "peeking_inflation.png"),
    )

    print("\n" + "=" * 60)
    print("=" * 60)

    rng = np.random.default_rng(RANDOM_SEED)

    # Case A: H1 is true (larger effect for clear demonstration)
    print("\n--- SPRT with true effect (H1 true) ---")
    ctrl_a = rng.binomial(1, 0.032, 50_000)
    trt_a = rng.binomial(1, 0.042, 50_000)  # +1.0%p for clear demo
    sprt_a = sprt(ctrl_a, trt_a, h0_rate=0.032, h1_rate=0.042)
    print(f"  Decision: {sprt_a['decision']}")
    print(f"  Stopped at: {sprt_a['stopping_point']:,} / "
          f"{sprt_a['total_observations']:,} pairs")

    plot_sprt_path(
        sprt_a,
        save_path=os.path.join(FIG_DIR, "sprt_path_h1_true.png"),
    )

    # Case B: H0 is true (no effect)
    print("\n--- SPRT with no effect (H0 true) ---")
    ctrl_b = rng.binomial(1, 0.032, 50_000)
    trt_b = rng.binomial(1, 0.032, 50_000)
    sprt_b = sprt(ctrl_b, trt_b, h0_rate=0.032, h1_rate=0.042)
    print(f"  Decision: {sprt_b['decision']}")
    print(f"  Stopped at: {sprt_b['stopping_point']:,} / "
          f"{sprt_b['total_observations']:,} pairs")

    plot_sprt_path(
        sprt_b,
        save_path=os.path.join(FIG_DIR, "sprt_path_h0_true.png"),
    )

    print("\nSequential testing complete.")


if __name__ == "__main__":
    main()
