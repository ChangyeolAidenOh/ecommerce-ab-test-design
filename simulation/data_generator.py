"""
Synthetic e-commerce data generator for A/B test simulation.
Generates user pools, session behavior, and experiment assignments
with configurable true effects for ground-truth validation.

Usage:
    python simulation/data_generator.py
"""

# stdlib
import os
import sys

# third-party
import numpy as np
import pandas as pd

# local
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from simulation.config import (
    RANDOM_SEED, HEIGHT_DIST, WEIGHT_DIST, AGE_GROUP_PROPORTIONS,
    BASELINE_CVR, GIF_CONFIG, REVIEW_SORT_CONFIG,
)


# ================================================================
# USER POOL GENERATION
# ================================================================

def generate_user_pool(n, seed=RANDOM_SEED):
    """Generate synthetic user population with body type attributes."""
    rng = np.random.default_rng(seed)

    heights = rng.normal(HEIGHT_DIST["mean"], HEIGHT_DIST["std"], n)
    heights = np.clip(heights, HEIGHT_DIST["min"], HEIGHT_DIST["max"])

    weights = rng.normal(WEIGHT_DIST["mean"], WEIGHT_DIST["std"], n)
    weights = np.clip(weights, WEIGHT_DIST["min"], WEIGHT_DIST["max"])

    age_groups = rng.choice(
        list(AGE_GROUP_PROPORTIONS.keys()),
        size=n,
        p=list(AGE_GROUP_PROPORTIONS.values()),
    )

    df = pd.DataFrame({
        "user_id": [f"u_{i:06d}" for i in range(n)],
        "height_cm": np.round(heights, 1),
        "weight_kg": np.round(weights, 1),
        "age_group": age_groups,
    })

    df["height_bucket"] = _assign_bucket(df["height_cm"], step=5, floor=140, ceil=190)
    df["weight_bucket"] = _assign_bucket(df["weight_kg"], step=5, floor=40, ceil=90)

    return df


def _assign_bucket(values, step, floor, ceil):
    """
    Assign values to fixed-width buckets matching Ably app review filter.
    Height: 139cm이하, 140-144, ..., 185-189, 190cm이상 (floor=140, ceil=190)
    Weight: 39kg이하, 40-44, ..., 85-89, 90kg이상 (floor=40, ceil=90)
    """
    labels = []
    for v in values:
        if v < floor:
            labels.append(f"{floor - 1}_below")
        elif v >= ceil:
            labels.append(f"{ceil}_above")
        else:
            idx = int((v - floor) // step)
            lo = floor + idx * step
            hi = lo + step - 1
            labels.append(f"{lo}-{hi}")
    return labels


# ================================================================
# SESSION GENERATION
# ================================================================

def generate_sessions(users, n_days=14, mean_sessions_per_day=1.5, seed=RANDOM_SEED):
    """Generate session-level behavior data for user pool."""
    rng = np.random.default_rng(seed)
    records = []

    for _, user in users.iterrows():
        for day in range(n_days):
            n_sessions = rng.poisson(mean_sessions_per_day)
            for s in range(n_sessions):
                page_views = max(1, int(rng.lognormal(1.5, 0.8)))
                scroll_depth = max(1, int(rng.lognormal(2.0, 0.7)))
                time_on_page = max(5, rng.lognormal(3.5, 0.6))

                records.append({
                    "user_id": user["user_id"],
                    "day": day,
                    "session_idx": s,
                    "page_views": page_views,
                    "scroll_depth": scroll_depth,
                    "time_on_page_sec": round(time_on_page, 1),
                })

    df = pd.DataFrame(records)
    df["session_id"] = [f"s_{i:08d}" for i in range(len(df))]
    return df


# ================================================================
# RANDOMIZED EXPERIMENT SIMULATION
# ================================================================

def simulate_experiment(sessions, config, variant_names=None, seed=RANDOM_SEED):
    """
    Simulate randomized A/B(C) experiment with configurable true effect.
    Assigns users to variants and generates outcomes with known ground truth.
    """
    rng = np.random.default_rng(seed)

    if variant_names is None:
        variant_names = ["control", "treatment"]

    user_ids = sessions["user_id"].unique()
    n_variants = len(variant_names)
    assignments = rng.integers(0, n_variants, size=len(user_ids))
    assignment_map = dict(zip(user_ids, [variant_names[a] for a in assignments]))

    df = sessions.copy()
    df["variant"] = df["user_id"].map(assignment_map)

    baseline = config["baseline_cvr"]
    true_effect = config["true_effect_cvr"]

    conversion_probs = []
    for _, row in df.iterrows():
        if row["variant"] == "control":
            p = baseline
        else:
            p = baseline + true_effect
        conversion_probs.append(p)

    df["converted"] = rng.binomial(1, conversion_probs)

    return df


# ================================================================
# SELF-SELECTION SIMULATION (Case 1: GIF toggle)
# ================================================================

def simulate_self_selection(sessions, users, config, seed=RANDOM_SEED):
    """
    Simulate self-selection environment where users choose their own group.
    Users who opt out (e.g., turn off GIF) have systematically different
    baseline behavior, creating selection bias.
    """
    rng = np.random.default_rng(seed)
    cfg = config

    user_ids = users["user_id"].values
    n_users = len(user_ids)

    # Users with higher visual sensitivity are more likely to opt out
    sensitivity = rng.uniform(0, 1, n_users)
    opt_out_prob = sensitivity * cfg["self_selection_rate"] * 2
    opted_out = rng.binomial(1, np.clip(opt_out_prob, 0, 1))

    user_group = {}
    user_baseline_shift = {}
    for i, uid in enumerate(user_ids):
        if opted_out[i]:
            user_group[uid] = "self_selected_off"
            user_baseline_shift[uid] = cfg["self_selection_baseline_shift"]
        else:
            user_group[uid] = "self_selected_on"
            user_baseline_shift[uid] = 0.0

    df = sessions.copy()
    df["group"] = df["user_id"].map(user_group)
    df["baseline_shift"] = df["user_id"].map(user_baseline_shift)

    baseline = cfg["baseline_cvr"]
    true_effect = cfg["true_effect_cvr"]

    conversion_probs = []
    for _, row in df.iterrows():
        shifted_baseline = baseline + row["baseline_shift"]
        if row["group"] == "self_selected_on":
            p = shifted_baseline + true_effect  # GIF on + effect
        else:
            p = shifted_baseline  # GIF off, no effect
        conversion_probs.append(max(0, min(1, p)))

    df["converted"] = rng.binomial(1, conversion_probs)
    df = df.drop(columns=["baseline_shift"])

    return df


# ================================================================
# BODY TYPE REVIEW SIMULATION (Case 2)
# ================================================================

def simulate_review_counts(n_products, users, bucket_step_cm=5, bucket_step_kg=5,
                           seed=RANDOM_SEED):
    """
    Simulate per-product review counts, total and by body type bucket.
    Used to evaluate bucket size trade-off and sort order experiment.
    """
    rng = np.random.default_rng(seed)

    # Total reviews per product (lognormal: most products have few, some many)
    total_reviews = np.round(rng.lognormal(3.0, 1.2, n_products)).astype(int)
    total_reviews = np.clip(total_reviews, 0, 10000)

    # Bucket distribution among reviewers follows user population distribution
    user_buckets = pd.DataFrame({
        "height_bucket": _assign_bucket(
            users["height_cm"].values, bucket_step_cm, 140, 190
        ),
        "weight_bucket": _assign_bucket(
            users["weight_kg"].values, bucket_step_kg, 40, 90
        ),
    })
    bucket_combos = user_buckets.groupby(
        ["height_bucket", "weight_bucket"]
    ).size()
    bucket_probs = (bucket_combos / bucket_combos.sum()).values
    bucket_labels = [f"{h}_{w}" for h, w in bucket_combos.index]

    products = []
    for pid in range(n_products):
        total = total_reviews[pid]
        if total == 0:
            products.append({
                "product_id": f"p_{pid:05d}",
                "total_reviews": 0,
                "body_type_reviews": {},
            })
            continue

        # Distribute reviews across buckets
        bucket_counts = rng.multinomial(total, bucket_probs)
        body_type_reviews = {
            label: int(count)
            for label, count in zip(bucket_labels, bucket_counts)
            if count > 0
        }
        products.append({
            "product_id": f"p_{pid:05d}",
            "total_reviews": total,
            "body_type_reviews": body_type_reviews,
        })

    return products


# ================================================================
# SORT ORDER OVERLAP ANALYSIS (절대수의 법칙 검증)
# ================================================================

def analyze_sort_overlap(products, target_bucket, top_n=20):
    """
    Compare product rankings between "total review count" sort
    and "target body-type review count" sort.

    This directly tests the "law of large numbers" concern:
    if the two rankings are highly correlated, changing the sort
    order will have minimal effect on what users see.

    Parameters
    ----------
    products : list of dicts
        Output of simulate_review_counts
    target_bucket : str
        Body type bucket key (e.g., "160-164_55-59")
    top_n : int
        Number of top products to compare overlap

    Returns
    -------
    dict with spearman_rho, p_value, top_n_overlap_ratio,
         rank_changes (products that move most)
    """
    from scipy import stats as sp_stats

    records = []
    for p in products:
        total = p["total_reviews"]
        bt_count = p["body_type_reviews"].get(target_bucket, 0)
        records.append({
            "product_id": p["product_id"],
            "total_reviews": total,
            "bt_reviews": bt_count,
        })

    df = pd.DataFrame(records)

    # Exclude products with 0 total reviews
    df = df[df["total_reviews"] > 0].copy()

    # Rank by each criterion (descending)
    df["rank_total"] = df["total_reviews"].rank(ascending=False, method="min")
    df["rank_bt"] = df["bt_reviews"].rank(ascending=False, method="min")
    df["rank_change"] = df["rank_total"] - df["rank_bt"]

    # Spearman correlation
    rho, p_val = sp_stats.spearmanr(df["total_reviews"], df["bt_reviews"])

    # Top-N overlap
    top_total = set(df.nsmallest(top_n, "rank_total")["product_id"])
    top_bt = set(df.nsmallest(top_n, "rank_bt")["product_id"])
    overlap = len(top_total & top_bt)
    overlap_ratio = overlap / top_n

    # Products with biggest rank changes (potential beneficiaries)
    biggest_movers = df.nlargest(5, "rank_change")[
        ["product_id", "total_reviews", "bt_reviews",
         "rank_total", "rank_bt", "rank_change"]
    ]

    # Products with 0 body-type reviews despite many total reviews
    high_total_zero_bt = df[
        (df["total_reviews"] >= df["total_reviews"].quantile(0.75)) &
        (df["bt_reviews"] == 0)
    ]

    return {
        "spearman_rho": round(float(rho), 4),
        "spearman_p": round(float(p_val), 6),
        "top_n": top_n,
        "top_n_overlap": overlap,
        "top_n_overlap_ratio": round(overlap_ratio, 3),
        "biggest_movers": biggest_movers.to_dict("records"),
        "high_total_zero_bt_count": len(high_total_zero_bt),
        "high_total_zero_bt_pct": round(
            len(high_total_zero_bt) /
            len(df[df["total_reviews"] >= df["total_reviews"].quantile(0.75)]),
            3
        ),
        "median_bt_reviews": float(df["bt_reviews"].median()),
        "mean_bt_reviews": round(float(df["bt_reviews"].mean()), 1),
    }


# ================================================================
# MAIN
# ================================================================

def main():
    print("Generating user pool (n=10000)...")
    users = generate_user_pool(10_000)
    print(f"  Users: {len(users)}")
    print(f"  Height: mean={users['height_cm'].mean():.1f}cm, "
          f"std={users['height_cm'].std():.1f}cm, "
          f"range=[{users['height_cm'].min():.0f}, {users['height_cm'].max():.0f}]")
    print(f"  Weight: mean={users['weight_kg'].mean():.1f}kg, "
          f"std={users['weight_kg'].std():.1f}kg, "
          f"range=[{users['weight_kg'].min():.0f}, {users['weight_kg'].max():.0f}]")
    print(f"  Height buckets ({users['height_bucket'].nunique()}): "
          f"{dict(users['height_bucket'].value_counts().head(5))}")
    print(f"  Weight buckets ({users['weight_bucket'].nunique()}): "
          f"{dict(users['weight_bucket'].value_counts().head(5))}")
    print(f"  Age groups: {dict(users['age_group'].value_counts())}")

    print("\nGenerating sessions (14 days)...")
    sessions = generate_sessions(users, n_days=14)
    print(f"  Sessions: {len(sessions)}")
    print(f"  Mean sessions/user: {len(sessions) / len(users):.1f}")

    print("\nSimulating RCT experiment (Case 1: GIF)...")
    rct = simulate_experiment(
        sessions, GIF_CONFIG,
        variant_names=["control", "treatment_a", "treatment_b"],
    )
    for v in ["control", "treatment_a", "treatment_b"]:
        subset = rct[rct["variant"] == v]
        cvr = subset["converted"].mean()
        print(f"  {v}: n={len(subset)}, CVR={cvr:.4f}")

    print("\nSimulating self-selection (Case 1: GIF toggle)...")
    self_sel = simulate_self_selection(sessions, users, GIF_CONFIG)
    for g in ["self_selected_on", "self_selected_off"]:
        subset = self_sel[self_sel["group"] == g]
        cvr = subset["converted"].mean()
        print(f"  {g}: n={len(subset)}, CVR={cvr:.4f}")

    rct_effect = (
        rct[rct["variant"] == "treatment_a"]["converted"].mean()
        - rct[rct["variant"] == "control"]["converted"].mean()
    )
    self_sel_effect = (
        self_sel[self_sel["group"] == "self_selected_on"]["converted"].mean()
        - self_sel[self_sel["group"] == "self_selected_off"]["converted"].mean()
    )
    print(f"\n  RCT estimated effect: {rct_effect:.4f}")
    print(f"  Self-selection estimated effect: {self_sel_effect:.4f}")
    print(f"  Selection bias: {self_sel_effect - rct_effect:.4f}")

    print("\nSimulating review counts (1000 products, 5cm/5kg buckets)...")
    reviews = simulate_review_counts(1000, users)
    total_counts = [r["total_reviews"] for r in reviews]
    print(f"  Products: {len(reviews)}")
    print(f"  Median total reviews: {np.median(total_counts):.0f}")
    print(f"  Mean total reviews: {np.mean(total_counts):.0f}")

    # Sort overlap analysis (절대수의 법칙 검증)
    # Target bucket: most common body type (160-164cm, 55-59kg)
    target = "160-164_55-59"
    print(f"\n--- Sort Overlap Analysis (target: {target}) ---")
    overlap = analyze_sort_overlap(reviews, target, top_n=20)
    print(f"  Spearman rho (total vs body-type): {overlap['spearman_rho']}")
    print(f"  Top-{overlap['top_n']} overlap: "
          f"{overlap['top_n_overlap']}/{overlap['top_n']} "
          f"({overlap['top_n_overlap_ratio']:.0%})")
    print(f"  Median body-type reviews per product: "
          f"{overlap['median_bt_reviews']:.0f}")
    print(f"  High-total products with 0 body-type reviews: "
          f"{overlap['high_total_zero_bt_pct']:.0%}")

    if overlap["spearman_rho"] > 0.9:
        print("  -> High correlation: sort order change will have minimal effect.")
        print("     Consider targeting subgroups where correlation is lower.")
    elif overlap["spearman_rho"] > 0.7:
        print("  -> Moderate correlation: sort order change will affect mid-ranked products.")
    else:
        print("  -> Low correlation: sort order change will meaningfully reorder results.")

    print("\nData generation complete.")


if __name__ == "__main__":
    main()