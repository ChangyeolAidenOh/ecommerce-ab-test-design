"""
Guardrail metric monitoring during experiment execution.
Tracks safety metrics over time and flags violations.

Usage:
    python -m simulation.guardrail_monitor
"""

import os
import sys

import numpy as np
import matplotlib
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from simulation.config import (
    RANDOM_SEED, GIF_CONFIG, FIG_DIR, MATPLOTLIB_RC,
)
from simulation.run_non_inferiority import non_inferiority_test


# ================================================================
# GUARDRAIL DEFINITION
# ================================================================

def define_guardrail(name, nim, direction, description=""):
    """
    Create a guardrail specification.

    Parameters
    ----------
    name : str
        Metric name (e.g., "bounce_rate")
    nim : float
        Non-inferiority margin (absolute)
    direction : str
        "upper" — metric must not increase beyond NIM
        "lower" — metric must not decrease beyond NIM
    """
    return {
        "name": name,
        "nim": nim,
        "direction": direction,
        "description": description,
    }


# ================================================================
# MONITORING
# ================================================================

def monitor_guardrails(control_metrics, treatment_metrics,
                       guardrails, check_points):
    """
    Monitor guardrail metrics at specified check points during experiment.

    Parameters
    ----------
    control_metrics : dict
        {metric_name: array of per-session values}
    treatment_metrics : dict
        {metric_name: array of per-session values}
    guardrails : list of guardrail dicts
    check_points : list of int
        Sample sizes at which to check (e.g., [1000, 5000, 10000])

    Returns
    -------
    list of dicts, one per check point, each containing per-guardrail results
    """
    timeline = []

    for n in check_points:
        point_results = {"n": n, "guardrails": {}}

        for guard in guardrails:
            name = guard["name"]
            ctrl_vals = control_metrics[name][:n]
            trt_vals = treatment_metrics[name][:n]

            ctrl_rate = np.mean(ctrl_vals)
            trt_rate = np.mean(trt_vals)

            result = non_inferiority_test(
                ctrl_rate, trt_rate, n, n,
                nim=guard["nim"],
                direction=guard["direction"],
            )

            diff = trt_rate - ctrl_rate

            # Distinguish non-inferiority failure reasons:
            # SAFE: NIT confirms non-inferiority
            # UNCONFIRMED: NIT can't confirm, but point estimate is within NIM
            #              (likely due to small sample / wide CI)
            # INFERIOR: NIT can't confirm AND point estimate exceeds NIM
            if result["non_inferior"]:
                status = "SAFE"
            else:
                if guard["direction"] == "upper":
                    status = "INFERIOR" if diff >= guard["nim"] else "UNCONFIRMED"
                else:
                    status = "INFERIOR" if diff <= -guard["nim"] else "UNCONFIRMED"

            point_results["guardrails"][name] = {
                "control_rate": round(float(ctrl_rate), 5),
                "treatment_rate": round(float(trt_rate), 5),
                "diff": round(float(trt_rate - ctrl_rate), 5),
                "non_inferior": result["non_inferior"],
                "status": status,
                "p_value": result["p_value"],
                "nim": guard["nim"],
            }

        # Overall status: all guardrails must pass
        point_results["all_safe"] = all(
            g["non_inferior"]
            for g in point_results["guardrails"].values()
        )
        timeline.append(point_results)

    return timeline


def check_early_stop(timeline, consecutive_violations=2):
    """
    Recommend early stop if guardrails show INFERIOR status consecutively.
    UNCONFIRMED (insufficient sample) does NOT trigger early stop.

    Returns
    -------
    dict with should_stop, reason, violation_point
    """
    violation_streak = 0

    for point in timeline:
        has_inferior = any(
            g["status"] == "INFERIOR"
            for g in point["guardrails"].values()
        )
        if has_inferior:
            violation_streak += 1
            if violation_streak >= consecutive_violations:
                violated = [
                    name for name, g in point["guardrails"].items()
                    if g["status"] == "INFERIOR"
                ]
                return {
                    "should_stop": True,
                    "reason": f"Consecutive INFERIOR at n={point['n']}",
                    "violated_metrics": violated,
                    "violation_point": point["n"],
                }
        else:
            violation_streak = 0

    return {"should_stop": False, "reason": "No consecutive INFERIOR violations"}


# ================================================================
# VISUALIZATION
# ================================================================

def plot_guardrail_timeline(timeline, metric_name, save_path=None):
    """Plot guardrail metric over time with NIM bounds."""
    matplotlib.rcParams.update(MATPLOTLIB_RC)
    fig, ax = plt.subplots()

    ns = [t["n"] for t in timeline]
    diffs = [t["guardrails"][metric_name]["diff"] * 100 for t in timeline]
    safe = [t["guardrails"][metric_name]["non_inferior"] for t in timeline]
    nim = timeline[0]["guardrails"][metric_name]["nim"] * 100

    colors = ["#22c55e" if s else "#dc2626" for s in safe]
    ax.scatter(ns, diffs, c=colors, s=60, zorder=3)
    ax.plot(ns, diffs, color="#64748b", linewidth=1, alpha=0.5)

    ax.axhline(y=0, color="#94a3b8", linestyle="-", linewidth=0.5)
    ax.axhline(y=nim, color="#dc2626", linestyle="--", linewidth=1.5,
               label=f"NIM = +{nim:.1f}%p")
    ax.axhline(y=-nim, color="#dc2626", linestyle="--", linewidth=1.5,
               alpha=0.3)

    ax.fill_between(ns, -nim, nim, alpha=0.05, color="#22c55e")

    ax.set_xlabel("Sample size per group")
    ax.set_ylabel(f"{metric_name} difference (%p)")
    ax.set_title(f"Guardrail: {metric_name}")
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
    rng = np.random.default_rng(RANDOM_SEED)
    n = 50_000

    print("=" * 60)
    print("GUARDRAIL MONITORING SIMULATION")
    print("=" * 60)

    # Simulate guardrail metrics for GIF experiment
    # bounce_rate: treatment slightly worse (+0.3%p)
    ctrl_bounce = rng.binomial(1, 0.120, n)
    trt_bounce = rng.binomial(1, 0.123, n)

    # scroll_depth: treatment slightly better (-2%)
    ctrl_scroll = rng.lognormal(2.0, 0.7, n)
    trt_scroll = rng.lognormal(2.0, 0.7, n) * 0.98

    # Convert scroll to binary (above/below median as proxy)
    median_scroll = np.median(ctrl_scroll)
    ctrl_scroll_binary = (ctrl_scroll >= median_scroll).astype(int)
    trt_scroll_binary = (trt_scroll >= median_scroll).astype(int)

    guardrails = [
        define_guardrail("bounce_rate", nim=0.01, direction="upper",
                         description="Session bounce rate must not increase >1%p"),
        define_guardrail("low_scroll", nim=0.05, direction="upper",
                         description="Low-scroll rate must not increase >5%p"),
    ]

    check_points = [1000, 2000, 5000, 10000, 20000, 30000, 50000]

    control_metrics = {
        "bounce_rate": ctrl_bounce,
        "low_scroll": 1 - ctrl_scroll_binary,
    }
    treatment_metrics = {
        "bounce_rate": trt_bounce,
        "low_scroll": 1 - trt_scroll_binary,
    }

    timeline = monitor_guardrails(
        control_metrics, treatment_metrics,
        guardrails, check_points,
    )

    print("\n--- Guardrail Timeline ---")
    for t in timeline:
        statuses = [g["status"] for g in t["guardrails"].values()]
        if all(s == "SAFE" for s in statuses):
            overall = "SAFE"
        elif any(s == "INFERIOR" for s in statuses):
            overall = "INFERIOR"
        else:
            overall = "UNCONFIRMED"
        print(f"\n  n={t['n']:,}: {overall}")
        for name, g in t["guardrails"].items():
            print(f"    {name}: diff={g['diff']*100:+.2f}%p "
                  f"(NIM={g['nim']*100:.1f}%p) [{g['status']}]")

    # Check early stop recommendation
    stop = check_early_stop(timeline)
    print(f"\n--- Early Stop Check ---")
    print(f"  Should stop: {stop['should_stop']}")
    print(f"  Reason: {stop['reason']}")

    # Generate figure
    plot_guardrail_timeline(
        timeline, "bounce_rate",
        save_path=os.path.join(FIG_DIR, "guardrail_timeline.png"),
    )

    print("\nGuardrail monitoring complete.")


if __name__ == "__main__":
    main()