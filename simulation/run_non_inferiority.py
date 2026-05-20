"""Non-inferiority testing for guardrail metrics. Implements NIT with NIM sensitivity analysis, directly addressing"""

import os
import sys

import numpy as np
from scipy import stats
import matplotlib
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from simulation.config import (
    ALPHA, RANDOM_SEED, N_SIMULATIONS,
    FIG_DIR, MATPLOTLIB_RC,
)


# NON-INFERIORITY TEST

def non_inferiority_test(control_rate, treatment_rate,
                         control_n, treatment_n,
                         nim, alpha=ALPHA, direction="upper"):
    """Non-inferiority test for a proportion metric"""
    diff = treatment_rate - control_rate

    se = np.sqrt(control_rate * (1 - control_rate) / control_n +
                 treatment_rate * (1 - treatment_rate) / treatment_n)

    z_alpha = stats.norm.ppf(1 - alpha)  # one-sided

    if direction == "upper":
        # H0: treatment - control >= NIM (treatment is inferior)
        # H1: treatment - control < NIM (treatment is non-inferior)
        ci_upper = diff + z_alpha * se
        non_inferior = ci_upper < nim
        z_stat = (nim - diff) / se if se > 0 else float("inf")
        p_value = 1 - stats.norm.cdf(z_stat)
    else:
        # H0: control - treatment >= NIM (treatment is inferior)
        # H1: control - treatment < NIM (treatment is non-inferior)
        ci_lower = diff - z_alpha * se
        non_inferior = ci_lower > -nim
        z_stat = (diff + nim) / se if se > 0 else float("inf")
        p_value = 1 - stats.norm.cdf(z_stat)

    return {
        "observed_diff": round(diff, 6),
        "se": round(se, 6),
        "nim": nim,
        "direction": direction,
        "non_inferior": non_inferior,
        "p_value": round(float(p_value), 6),
        "ci_bound": round(float(ci_upper if direction == "upper"
                                 else ci_lower), 6),
    }


# NIM SENSITIVITY ANALYSIS

def nim_sensitivity_analysis(control_rate, treatment_rate,
                             control_n, treatment_n,
                             nim_range, direction="upper", alpha=ALPHA):
    """How does the non-inferiority decision change across different NIM values?"""
    results = []
    for nim in nim_range:
        result = non_inferiority_test(
            control_rate, treatment_rate,
            control_n, treatment_n,
            nim, alpha, direction,
        )
        results.append(result)
    return results


def find_critical_nim(control_rate, treatment_rate,
                      control_n, treatment_n,
                      direction="upper", alpha=ALPHA):
    """Find the smallest NIM at which non-inferiority is declared"""
    low, high = 0.0001, 0.10
    for _ in range(100):
        mid = (low + high) / 2
        result = non_inferiority_test(
            control_rate, treatment_rate,
            control_n, treatment_n,
            mid, alpha, direction,
        )
        if result["non_inferior"]:
            high = mid
        else:
            low = mid

    return round(high, 5)


# INFERIORITY vs NON-INFERIORITY COMPARISON

def compare_inferiority_vs_non_inferiority(
    control_rate, treatment_rate, control_n, treatment_n,
    nim, alpha=ALPHA, direction="upper"
):
    """Compare inferiority test (standard two-sided) vs non-inferiority test"""
    diff = treatment_rate - control_rate
    se = np.sqrt(control_rate * (1 - control_rate) / control_n +
                 treatment_rate * (1 - treatment_rate) / treatment_n)

    # Inferiority test (two-sided): is treatment different from control?
    z_inf = diff / se if se > 0 else 0
    p_inf = 2 * (1 - stats.norm.cdf(abs(z_inf)))
    inferior = p_inf < alpha and (
        (direction == "upper" and diff > 0) or
        (direction == "lower" and diff < 0)
    )

    # Non-inferiority test
    nit_result = non_inferiority_test(
        control_rate, treatment_rate, control_n, treatment_n,
        nim, alpha, direction,
    )

    # Identify decision conflict
    if inferior and nit_result["non_inferior"]:
        conflict = "statistically_worse_but_non_inferior"
    elif not inferior and not nit_result["non_inferior"]:
        conflict = "not_worse_but_not_non_inferior"
    else:
        conflict = "no_conflict"

    return {
        "observed_diff": round(diff, 6),
        "inferiority_test": {
            "p_value": round(float(p_inf), 6),
            "significant": p_inf < alpha,
            "inferior": inferior,
        },
        "non_inferiority_test": nit_result,
        "conflict": conflict,
    }


# VISUALIZATION

def plot_nim_sensitivity(results, save_path=None):
    """Plot NIM sensitivity: decision boundary visualization"""
    matplotlib.rcParams.update(MATPLOTLIB_RC)
    fig, ax = plt.subplots()

    nims = [r["nim"] * 100 for r in results]
    decisions = [r["non_inferior"] for r in results]
    p_values = [r["p_value"] for r in results]

    colors = ["#22c55e" if d else "#dc2626" for d in decisions]
    ax.bar(nims, [1 - p for p in p_values], color=colors, width=0.08, alpha=0.8)
    ax.axhline(y=1 - ALPHA, color="#64748b", linestyle="--",
               label=f"1 - alpha = {1 - ALPHA:.2f}")

    # Find tipping point
    for i in range(len(decisions)):
        if decisions[i] and (i == 0 or not decisions[i - 1]):
            ax.axvline(x=nims[i], color="#f59e0b", linestyle=":",
                       linewidth=2, label=f"Critical NIM = {nims[i]:.1f}%p")
            break

    ax.set_xlabel("Non-Inferiority Margin (NIM, %p)")
    ax.set_ylabel("1 - p-value")
    ax.set_title("NIM Sensitivity: When Does Non-Inferiority Hold?")
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
    rng = np.random.default_rng(RANDOM_SEED)

    # Simulate a guardrail metric (bounce rate)
    n_ctrl = 50_000
    n_trt = 50_000
    ctrl_bounce = 0.120  # 12.0% baseline bounce rate
    trt_bounce = 0.125   # 12.5% observed — slightly higher

    print("=" * 60)
    print("NON-INFERIORITY TEST: Bounce Rate Guardrail")
    print("=" * 60)
    print(f"\n  Control bounce rate: {ctrl_bounce:.1%}")
    print(f"  Treatment bounce rate: {trt_bounce:.1%}")
    print(f"  Observed difference: +{(trt_bounce - ctrl_bounce)*100:.1f}%p")

    # Test with different NIMs
    print("\n--- NIM Sensitivity ---")
    nim_values = [0.005, 0.008, 0.010, 0.015, 0.020]
    for nim in nim_values:
        result = non_inferiority_test(
            ctrl_bounce, trt_bounce, n_ctrl, n_trt,
            nim=nim, direction="upper",
        )
        status = "NON-INFERIOR" if result["non_inferior"] else "INFERIOR"
        print(f"  NIM={nim*100:.1f}%p: {status} "
              f"(p={result['p_value']:.4f}, "
              f"CI bound={result['ci_bound']*100:.2f}%p)")

    # Find critical NIM
    critical = find_critical_nim(
        ctrl_bounce, trt_bounce, n_ctrl, n_trt, direction="upper"
    )
    print(f"\n  Critical NIM (tipping point): {critical*100:.2f}%p")

    # Inferiority vs Non-inferiority comparison
    print("\n--- Inferiority vs Non-Inferiority Comparison ---")
    comparison = compare_inferiority_vs_non_inferiority(
        ctrl_bounce, trt_bounce, n_ctrl, n_trt,
        nim=0.01, direction="upper",
    )
    print(f"  Inferiority test: "
          f"p={comparison['inferiority_test']['p_value']:.4f}, "
          f"inferior={comparison['inferiority_test']['inferior']}")
    print(f"  Non-inferiority test (NIM=1.0%p): "
          f"non_inferior={comparison['non_inferiority_test']['non_inferior']}")
    print(f"  Conflict: {comparison['conflict']}")

    if comparison["conflict"] == "statistically_worse_but_non_inferior":
        print("\n  -> Treatment is statistically worse than control,")
        print("     but the deterioration is within the NIM.")
        print("     Under inferiority testing: BLOCK launch.")
        print("     Under non-inferiority testing: ALLOW launch.")
        print("     This is exactly the scenario Ably DA blog discussed.")

    # Generate NIM sensitivity figure
    print("\n--- Generating NIM sensitivity figure ---")
    nim_range = np.arange(0.002, 0.025, 0.001)
    sensitivity = nim_sensitivity_analysis(
        ctrl_bounce, trt_bounce, n_ctrl, n_trt,
        nim_range=nim_range, direction="upper",
    )
    plot_nim_sensitivity(
        sensitivity,
        save_path=os.path.join(FIG_DIR, "nim_sensitivity.png"),
    )

    print("\nNon-inferiority testing complete.")


if __name__ == "__main__":
    main()
