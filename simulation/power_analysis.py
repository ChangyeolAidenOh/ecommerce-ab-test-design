"""
Power analysis for A/B test experiment design.
Computes sample size, MDE, power, and experiment duration
for proportion-based metrics (e.g., conversion rate).

Usage:
    python -m simulation.power_analysis
"""

import os
import sys

import numpy as np
from scipy import stats
import matplotlib
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from simulation.config import (
    ALPHA, POWER, DAILY_ACTIVE_USERS, BODY_TYPE_FILTER_RATE,
    GIF_CONFIG, REVIEW_SORT_CONFIG,
    FIG_DIR, MATPLOTLIB_RC,
)


# ================================================================
# CORE FUNCTIONS
# ================================================================

def compute_sample_size(baseline, mde, alpha=ALPHA, power=POWER):
    """
    Compute required sample size per group for two-proportion z-test.

    Parameters
    ----------
    baseline : float
        Control group conversion rate (e.g., 0.032)
    mde : float
        Minimum detectable effect in absolute terms (e.g., 0.003)
    alpha : float
        Significance level (two-sided)
    power : float
        Statistical power (1 - beta)

    Returns
    -------
    int
        Required sample size per group
    """
    p1 = baseline
    p2 = baseline + mde
    pooled = (p1 + p2) / 2

    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_beta = stats.norm.ppf(power)

    numerator = (z_alpha * np.sqrt(2 * pooled * (1 - pooled))
                 + z_beta * np.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    denominator = (p2 - p1) ** 2

    return int(np.ceil(numerator / denominator))


def compute_mde(baseline, n_per_group, alpha=ALPHA, power=POWER):
    """
    Compute minimum detectable effect for given sample size.
    Uses iterative search since closed-form is not straightforward.

    Parameters
    ----------
    baseline : float
        Control group conversion rate
    n_per_group : int
        Sample size per group
    alpha : float
        Significance level (two-sided)
    power : float
        Statistical power

    Returns
    -------
    float
        Minimum detectable effect (absolute)
    """
    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_beta = stats.norm.ppf(power)

    low, high = 0.0001, 0.5
    for _ in range(100):
        mid = (low + high) / 2
        n_required = compute_sample_size(baseline, mid, alpha, power)
        if n_required > n_per_group:
            low = mid
        else:
            high = mid

    return round(high, 6)


def compute_power(baseline, mde, n_per_group, alpha=ALPHA):
    """
    Compute statistical power for given parameters.

    Parameters
    ----------
    baseline : float
        Control group conversion rate
    mde : float
        Expected effect size (absolute)
    n_per_group : int
        Sample size per group
    alpha : float
        Significance level (two-sided)

    Returns
    -------
    float
        Statistical power (0 to 1)
    """
    p1 = baseline
    p2 = baseline + mde
    pooled = (p1 + p2) / 2

    z_alpha = stats.norm.ppf(1 - alpha / 2)

    se_null = np.sqrt(2 * pooled * (1 - pooled) / n_per_group)
    se_alt = np.sqrt((p1 * (1 - p1) + p2 * (1 - p2)) / n_per_group)

    z_stat = (abs(p2 - p1) - z_alpha * se_null) / se_alt

    return float(stats.norm.cdf(z_stat))


def estimate_duration(daily_traffic, required_n_per_group, n_variants=2,
                      traffic_fraction=1.0):
    """
    Estimate experiment duration in days.

    Parameters
    ----------
    daily_traffic : int
        Daily active users eligible for experiment
    required_n_per_group : int
        Required sessions per group from power analysis
    n_variants : int
        Number of variants (including control)
    traffic_fraction : float
        Fraction of traffic allocated to experiment (e.g., 0.5 for 50%)

    Returns
    -------
    int
        Estimated days to reach required sample size
    """
    daily_per_group = (daily_traffic * traffic_fraction) / n_variants
    if daily_per_group <= 0:
        return float("inf")
    return int(np.ceil(required_n_per_group / daily_per_group))


# ================================================================
# MULTI-ARM ADJUSTMENT
# ================================================================

def bonferroni_alpha(alpha, n_comparisons):
    """Bonferroni-corrected alpha for multiple comparisons."""
    return alpha / n_comparisons


def benjamini_hochberg(p_values, alpha=ALPHA):
    """
    Benjamini-Hochberg procedure for controlling FDR.

    Parameters
    ----------
    p_values : list of float
        Raw p-values from multiple tests
    alpha : float
        Desired FDR level

    Returns
    -------
    list of bool
        Whether each test is significant after BH correction
    """
    n = len(p_values)
    sorted_indices = np.argsort(p_values)
    sorted_p = np.array(p_values)[sorted_indices]

    thresholds = [(i + 1) / n * alpha for i in range(n)]

    significant = [False] * n
    max_significant = -1
    for i in range(n):
        if sorted_p[i] <= thresholds[i]:
            max_significant = i

    if max_significant >= 0:
        for i in range(max_significant + 1):
            significant[sorted_indices[i]] = True

    return significant


# ================================================================
# VISUALIZATION
# ================================================================

def plot_power_curve(baseline, alpha=ALPHA, power=POWER,
                     mde_range=None, save_path=None):
    """
    Plot required sample size vs MDE.
    Shows the trade-off: smaller effects require larger samples.
    """
    if mde_range is None:
        mde_range = np.arange(0.001, 0.015, 0.0005)

    sample_sizes = [compute_sample_size(baseline, mde, alpha, power)
                    for mde in mde_range]

    matplotlib.rcParams.update(MATPLOTLIB_RC)
    fig, ax = plt.subplots()
    ax.plot(mde_range * 100, sample_sizes, color="#2563eb", linewidth=2)
    ax.set_xlabel("Minimum Detectable Effect (%p)")
    ax.set_ylabel("Required Sample Size per Group")
    ax.set_title(f"Power Curve (baseline={baseline*100:.1f}%, "
                 f"alpha={alpha}, power={power})")

    # annotate key MDE points
    for target_mde in [0.003, 0.005, 0.01]:
        if mde_range[0] <= target_mde <= mde_range[-1]:
            n = compute_sample_size(baseline, target_mde, alpha, power)
            ax.axvline(x=target_mde * 100, color="#94a3b8", linestyle="--",
                       alpha=0.5)
            ax.annotate(f"MDE={target_mde*100:.1f}%p\nn={n:,}",
                        xy=(target_mde * 100, n),
                        xytext=(target_mde * 100 + 0.15, n * 1.1),
                        fontsize=9, ha="left",
                        arrowprops=dict(arrowstyle="->", color="#64748b"))

    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    plt.tight_layout()

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved: {save_path}")

    plt.close(fig)
    return fig


def plot_duration_vs_mde(baseline, daily_traffic, n_variants=2,
                         traffic_fraction=0.5, alpha=ALPHA, power=POWER,
                         mde_range=None, save_path=None):
    """
    Plot experiment duration vs MDE.
    Directly answers "how long will this experiment take?"
    """
    if mde_range is None:
        mde_range = np.arange(0.001, 0.015, 0.0005)

    durations = []
    for mde in mde_range:
        n = compute_sample_size(baseline, mde, alpha, power)
        d = estimate_duration(daily_traffic, n, n_variants, traffic_fraction)
        durations.append(d)

    matplotlib.rcParams.update(MATPLOTLIB_RC)
    fig, ax = plt.subplots()
    ax.plot(mde_range * 100, durations, color="#dc2626", linewidth=2)
    ax.set_xlabel("Minimum Detectable Effect (%p)")
    ax.set_ylabel("Experiment Duration (days)")
    ax.set_title(f"Duration vs MDE (DAU={daily_traffic:,}, "
                 f"{n_variants} arms, {traffic_fraction*100:.0f}% traffic)")

    # 2-week and 4-week reference lines
    ax.axhline(y=14, color="#22c55e", linestyle="--", alpha=0.5, label="2 weeks")
    ax.axhline(y=28, color="#f59e0b", linestyle="--", alpha=0.5, label="4 weeks")
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
    print("CASE 1: GIF Feed Density Experiment")
    print("=" * 60)

    cfg1 = GIF_CONFIG
    b1 = cfg1["baseline_cvr"]
    mde1 = cfg1["true_effect_cvr"]
    dau1 = cfg1["daily_traffic"]

    n1 = compute_sample_size(b1, mde1)
    print(f"\n  Baseline CVR: {b1*100:.1f}%")
    print(f"  MDE: {mde1*100:.1f}%p")
    print(f"  Required n per group: {n1:,}")

    # 3-arm: Bonferroni correction
    n_comparisons = 2  # treatment_a vs control, treatment_b vs control
    adj_alpha = bonferroni_alpha(ALPHA, n_comparisons)
    n1_adj = compute_sample_size(b1, mde1, alpha=adj_alpha)
    print(f"\n  Bonferroni-adjusted alpha: {adj_alpha:.4f}")
    print(f"  Adjusted n per group: {n1_adj:,}")

    # duration at 50% traffic allocation
    d1 = estimate_duration(dau1, n1_adj, n_variants=3, traffic_fraction=0.5)
    print(f"\n  DAU: {dau1:,}")
    print(f"  Traffic allocation: 50%")
    print(f"  Estimated duration: {d1} days")

    # MDE achievable in 2 weeks
    n_2weeks = int(dau1 * 0.5 / 3 * 14)
    mde_2w = compute_mde(b1, n_2weeks, alpha=adj_alpha)
    print(f"\n  2-week achievable n per group: {n_2weeks:,}")
    print(f"  2-week achievable MDE: {mde_2w*100:.2f}%p")

    # power at planned MDE
    pwr = compute_power(b1, mde1, n1_adj)
    print(f"\n  Power at n={n1_adj:,}, MDE={mde1*100:.1f}%p: {pwr:.3f}")

    print("\n" + "=" * 60)
    print("CASE 2: Review Sort Order Experiment")
    print("=" * 60)

    cfg2 = REVIEW_SORT_CONFIG
    b2 = cfg2["baseline_cvr"]
    mde2 = cfg2["true_effect_cvr"]
    dau2 = int(dau1 * BODY_TYPE_FILTER_RATE)  # only body type filter users

    n2 = compute_sample_size(b2, mde2)
    print(f"\n  Baseline CVR (body type filter users): {b2*100:.1f}%")
    print(f"  MDE: {mde2*100:.1f}%p")
    print(f"  Required n per group: {n2:,}")

    # 2-arm: no multiple comparison adjustment needed
    d2 = estimate_duration(dau2, n2, n_variants=2, traffic_fraction=0.5)
    print(f"\n  Eligible DAU: {dau2:,} (={dau1:,} x {BODY_TYPE_FILTER_RATE*100:.0f}%)")
    print(f"  Traffic allocation: 50%")
    print(f"  Estimated duration: {d2} days")
    print(f"  + Return observation window: "
          f"{cfg2['return_observation_days']} days")
    print(f"  Total calendar time: {d2 + cfg2['return_observation_days']} days")

    # MDE achievable in 4 weeks
    n_4weeks = int(dau2 * 0.5 / 2 * 28)
    mde_4w = compute_mde(b2, n_4weeks)
    print(f"\n  4-week achievable n per group: {n_4weeks:,}")
    print(f"  4-week achievable MDE: {mde_4w*100:.2f}%p")

    # power at planned MDE
    pwr2 = compute_power(b2, mde2, n2)
    print(f"\n  Power at n={n2:,}, MDE={mde2*100:.1f}%p: {pwr2:.3f}")

    # ============================================================
    # Generate figures
    # ============================================================
    print("\n" + "=" * 60)
    print("Generating figures...")
    print("=" * 60)

    plot_power_curve(
        b1, mde_range=np.arange(0.001, 0.015, 0.0005),
        save_path=os.path.join(FIG_DIR, "power_curve_case1.png"),
    )

    plot_power_curve(
        b2, mde_range=np.arange(0.001, 0.015, 0.0005),
        save_path=os.path.join(FIG_DIR, "power_curve_case2.png"),
    )

    plot_duration_vs_mde(
        b1, dau1, n_variants=3, traffic_fraction=0.5,
        save_path=os.path.join(FIG_DIR, "duration_vs_mde_case1.png"),
    )

    plot_duration_vs_mde(
        b2, dau2, n_variants=2, traffic_fraction=0.5,
        save_path=os.path.join(FIG_DIR, "duration_vs_mde_case2.png"),
    )

    print("\nPower analysis complete.")


if __name__ == "__main__":
    main()
