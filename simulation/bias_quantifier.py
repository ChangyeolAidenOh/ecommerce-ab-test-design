"""
Self-selection bias quantifier.
Compares effect estimates from self-selection (Ably lab toggle)
vs randomized controlled trial to quantify selection bias.

Usage:
    python -m simulation.bias_quantifier
"""

import os
import sys

import numpy as np
import matplotlib
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from simulation.config import (
    RANDOM_SEED, N_SIMULATIONS, GIF_CONFIG,
    FIG_DIR, MATPLOTLIB_RC,
)
from simulation.data_generator import (
    generate_user_pool, generate_sessions,
    simulate_experiment, simulate_self_selection,
)
from simulation.run_frequentist import z_test_from_groups


# ================================================================
# BIAS QUANTIFICATION
# ================================================================

def compare_selection_vs_rct(rct_data, self_sel_data):
    """
    Compare effect estimates from RCT vs self-selection.

    Returns
    -------
    dict with rct_effect, self_selection_effect, bias, bias_ratio
    """
    # RCT effect
    rct_ctrl = rct_data[rct_data["variant"] == "control"]["converted"]
    rct_trt = rct_data[rct_data["variant"] == "treatment_a"]["converted"]
    rct_result = z_test_from_groups(rct_ctrl, rct_trt)

    # Self-selection effect
    ss_on = self_sel_data[self_sel_data["group"] == "self_selected_on"]["converted"]
    ss_off = self_sel_data[self_sel_data["group"] == "self_selected_off"]["converted"]
    ss_result = z_test_from_groups(ss_off, ss_on)

    rct_effect = rct_result["effect"]
    ss_effect = ss_result["effect"]
    bias = ss_effect - rct_effect

    return {
        "rct_effect": rct_effect,
        "rct_p_value": rct_result["p_value"],
        "rct_significant": rct_result["significant"],
        "rct_ci": (rct_result["ci_lower"], rct_result["ci_upper"]),
        "self_selection_effect": ss_effect,
        "ss_p_value": ss_result["p_value"],
        "ss_significant": ss_result["significant"],
        "ss_ci": (ss_result["ci_lower"], ss_result["ci_upper"]),
        "selection_bias": bias,
        "bias_ratio": ss_effect / rct_effect if rct_effect != 0 else float("inf"),
    }


def run_bias_simulations(n_simulations=500, n_users=5_000, n_days=14,
                         config=GIF_CONFIG, seed=RANDOM_SEED):
    """
    Run multiple simulations to get distribution of bias estimates.

    Returns
    -------
    dict with arrays of rct_effects, ss_effects, biases
    """
    rng = np.random.default_rng(seed)
    rct_effects = []
    ss_effects = []

    for i in range(n_simulations):
        sim_seed = rng.integers(0, 1_000_000)
        users = generate_user_pool(n_users, seed=sim_seed)
        sessions = generate_sessions(users, n_days=n_days, seed=sim_seed)

        rct = simulate_experiment(
            sessions, config,
            variant_names=["control", "treatment_a"],
            seed=sim_seed,
        )
        rct_ctrl = rct[rct["variant"] == "control"]["converted"].mean()
        rct_trt = rct[rct["variant"] == "treatment_a"]["converted"].mean()
        rct_effects.append(rct_trt - rct_ctrl)

        ss = simulate_self_selection(sessions, users, config, seed=sim_seed)
        ss_on = ss[ss["group"] == "self_selected_on"]["converted"].mean()
        ss_off = ss[ss["group"] == "self_selected_off"]["converted"].mean()
        ss_effects.append(ss_on - ss_off)

    rct_effects = np.array(rct_effects)
    ss_effects = np.array(ss_effects)

    return {
        "rct_effects": rct_effects,
        "ss_effects": ss_effects,
        "biases": ss_effects - rct_effects,
        "true_effect": config["true_effect_cvr"],
    }


# ================================================================
# VISUALIZATION
# ================================================================

def plot_bias_comparison(sim_results, save_path=None):
    """Plot RCT vs self-selection effect distributions."""
    matplotlib.rcParams.update(MATPLOTLIB_RC)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    rct = sim_results["rct_effects"] * 100
    ss = sim_results["ss_effects"] * 100
    true = sim_results["true_effect"] * 100

    # Left: overlapping histograms
    ax = axes[0]
    ax.hist(rct, bins=40, alpha=0.6, color="#2563eb", label="RCT estimate")
    ax.hist(ss, bins=40, alpha=0.6, color="#dc2626", label="Self-selection estimate")
    ax.axvline(x=true, color="#000000", linestyle="-", linewidth=2,
               label=f"True effect ({true:.1f}%p)")
    ax.axvline(x=np.mean(rct), color="#2563eb", linestyle="--", linewidth=1.5)
    ax.axvline(x=np.mean(ss), color="#dc2626", linestyle="--", linewidth=1.5)
    ax.set_xlabel("Estimated effect (%p)")
    ax.set_ylabel("Count")
    ax.set_title("RCT vs Self-Selection: Effect Estimates")
    ax.legend(fontsize=9)

    # Right: bias distribution
    ax = axes[1]
    biases = sim_results["biases"] * 100
    ax.hist(biases, bins=40, color="#f59e0b", alpha=0.7)
    ax.axvline(x=0, color="#94a3b8", linestyle="-", linewidth=0.5)
    ax.axvline(x=np.mean(biases), color="#dc2626", linestyle="--", linewidth=2,
               label=f"Mean bias: {np.mean(biases):+.2f}%p")
    ax.set_xlabel("Selection bias (%p)")
    ax.set_ylabel("Count")
    ax.set_title("Selection Bias Distribution")
    ax.legend(fontsize=9)

    plt.tight_layout()
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved: {save_path}")
    plt.close(fig)
    return fig


# ================================================================
# MAIN
# ================================================================

def main():
    print("=" * 60)
    print("SELF-SELECTION BIAS QUANTIFICATION")
    print("=" * 60)

    # Single run comparison
    print("\n--- Single Run ---")
    users = generate_user_pool(10_000)
    sessions = generate_sessions(users, n_days=14)

    rct = simulate_experiment(
        sessions, GIF_CONFIG,
        variant_names=["control", "treatment_a"],
    )
    ss = simulate_self_selection(sessions, users, GIF_CONFIG)

    result = compare_selection_vs_rct(rct, ss)

    print(f"  True effect: {GIF_CONFIG['true_effect_cvr']*100:.1f}%p")
    print(f"\n  RCT estimate: {result['rct_effect']*100:+.2f}%p "
          f"(p={result['rct_p_value']:.4f}, sig={result['rct_significant']})")
    print(f"  Self-selection estimate: {result['self_selection_effect']*100:+.2f}%p "
          f"(p={result['ss_p_value']:.4f}, sig={result['ss_significant']})")
    print(f"\n  Selection bias: {result['selection_bias']*100:+.2f}%p")
    print(f"  Bias ratio: {result['bias_ratio']:.1f}x "
          f"(self-selection overestimates by {result['bias_ratio']:.1f}x)")

    # Multiple simulations
    # Multiple simulations (increase n_simulations for more stable estimates)
    print("\n--- Bias Distribution (50 simulations) ---")
    sim_results = run_bias_simulations(n_simulations=50, n_users=2_000,
                                       n_days=7)

    rct_mean = np.mean(sim_results["rct_effects"])
    ss_mean = np.mean(sim_results["ss_effects"])
    bias_mean = np.mean(sim_results["biases"])

    print(f"  True effect: {sim_results['true_effect']*100:.1f}%p")
    print(f"  Mean RCT estimate: {rct_mean*100:+.2f}%p")
    print(f"  Mean self-selection estimate: {ss_mean*100:+.2f}%p")
    print(f"  Mean selection bias: {bias_mean*100:+.2f}%p")
    print(f"  Bias as % of true effect: "
          f"{bias_mean / sim_results['true_effect'] * 100:.0f}%")

    plot_bias_comparison(
        sim_results,
        save_path=os.path.join(FIG_DIR, "selection_bias.png"),
    )

    print("\nBias quantification complete.")


if __name__ == "__main__":
    main()
