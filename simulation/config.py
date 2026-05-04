"""
Central configuration for experiment parameters and scenario configs.
All simulation parameters with sources documented in
docs/simulation_parameter_basis.md.
"""

# ================================================================
# GENERAL EXPERIMENT DEFAULTS
# ================================================================

ALPHA = 0.05
POWER = 0.80
N_SIMULATIONS = 10_000
RANDOM_SEED = 42

# ================================================================
# PLATFORM PARAMETERS (Ably-inspired)
# ================================================================

# MAU 9.69M (2026 Q1 disclosure) x ~5% daily activation rate [estimated]
DAILY_ACTIVE_USERS = 50_000

# Fashion e-commerce industry average 2-5% [industry average]
BASELINE_CVR = 0.032

# Online fashion return rate 10-15% [industry average]
BASELINE_RETURN_RATE = 0.12

# Body type filter activation among all users [estimated]
BODY_TYPE_FILTER_RATE = 0.15

# Proportion of products with GIF images in feed [estimated from app]
GIF_PRODUCT_RATIO = 0.30

# ================================================================
# CASE 1: GIF FEED DENSITY EXPERIMENT
# ================================================================

GIF_CONFIG = {
    "baseline_cvr": BASELINE_CVR,
    "true_effect_cvr": 0.003,            # +0.3%p true effect [simulation]
    "daily_traffic": DAILY_ACTIVE_USERS,
    "self_selection_rate": 0.15,          # lab toggle usage rate [estimated]
    "self_selection_baseline_shift": -0.005,  # self-selectors have lower baseline
    "variants": {
        "control": {"max_consecutive_gif": None},  # no limit
        "treatment_a": {"max_consecutive_gif": 3},
        "treatment_b": {"max_consecutive_gif": 2},
    },
    "guardrails": {
        "bounce_rate": {"nim": 0.01, "direction": "upper"},
        "scroll_depth": {"nim": 0.05, "direction": "lower"},
    },
}

# ================================================================
# CASE 2: REVIEW SORT ORDER EXPERIMENT
# ================================================================

REVIEW_SORT_CONFIG = {
    "baseline_cvr": 0.045,               # body type filter users baseline
    "true_effect_cvr": 0.005,            # +0.5%p true effect [simulation]
    "return_rate_baseline": BASELINE_RETURN_RATE,
    "true_effect_return": -0.010,         # -1.0%p return rate reduction
    "return_observation_days": 14,        # post-experiment observation window
    "body_type_bucket": {
        "height_step_cm": 5,              # confirmed from app screenshot
        "weight_step_kg": 5,              # confirmed from app screenshot
    },
    "bucket_comparison_range": [3, 5, 7, 10],  # for trade-off simulation
    "guardrails": {
        "gini_diversity": {"nim": 0.05, "direction": "upper"},
        "abandon_rate": {"nim": 0.02, "direction": "upper"},
    },
}

# ================================================================
# USER POPULATION DISTRIBUTION (for data generator)
# ================================================================

# Age group proportions
# Sources:
#   - 20s: 30.9% (WiseApp/Retail 2025.01-09, Platum 2025.10.29)
#   - 10s-30s total: 73% (VentureSquare 2026.02.22)
#   - 40s+: 27% (= 100% - 73%)
#   - 10s vs 30s split within 42.1%: [estimated]
AGE_GROUP_PROPORTIONS = {
    "10s": 0.12,         # [estimated] within 10s+30s=42.1%
    "20s": 0.309,        # WiseApp/Retail 2025
    "30s": 0.301,        # [estimated] = 0.73 - 0.309 - 0.12
    "40s_plus": 0.27,    # = 1.0 - 0.73
}

# Height distribution (cm) — Korean female, Ably user age mix
# Source: NHIS Health Screening Statistics 2024
#         (KOSIS, National Health Insurance Service, updated 2026-02-26)
#   19y-: 161.86cm, 20s: 161.83cm, 30s: 161.91cm, 40s: 160.93cm
#   Weighted avg by Ably age mix (10s 12%, 20s 30.9%, 30s 30.1%, 40s+ 27%)
#   = 161.7cm
# Range: Ably app review filter buckets (app screenshot confirmed)
#   139cm이하 ~ 190cm이상 (12 buckets, 5cm step)
HEIGHT_DIST = {
    "mean": 161.7,
    "std": 5.0,
    "min": 139,
    "max": 190,
}

# Weight distribution (kg) — Korean female, Ably user age mix
# Source: NHIS Health Screening Statistics 2024
#         (KOSIS, National Health Insurance Service, updated 2026-02-26)
#   19y-: 60.25kg, 20s: 58.57kg, 30s: 60.19kg, 40s: 60.19kg
#   Weighted avg by Ably age mix = 59.7kg
# Range: Ably app review filter buckets (app screenshot confirmed)
#   39kg이하 ~ 90kg이상 (12 buckets, 5kg step)
WEIGHT_DIST = {
    "mean": 59.7,
    "std": 8.0,
    "min": 39,
    "max": 90,
}

# Height bucket edges — from Ably app review filter (screenshot confirmed)
HEIGHT_BUCKETS = [
    "139cm 이하",
    "140cm-144cm", "145cm-149cm", "150cm-154cm",
    "155cm-159cm", "160cm-164cm", "165cm-169cm",
    "170cm-174cm", "175cm-179cm", "180cm-184cm",
    "185cm-189cm", "190cm 이상",
]

# Weight bucket edges — from Ably app review filter (screenshot confirmed)
WEIGHT_BUCKETS = [
    "39kg 이하",
    "40kg-44kg", "45kg-49kg", "50kg-54kg",
    "55kg-59kg", "60kg-64kg", "65kg-69kg",
    "70kg-74kg", "75kg-79kg", "80kg-84kg",
    "85kg-89kg", "90kg 이상",
]

# Clothing size options — from Ably app review filter (screenshot confirmed)
CLOTHING_SIZES = [
    "44 이하", "44반", "55", "55반", "66", "66반",
    "77", "77반", "88", "88반", "99 이상",
]

# ================================================================
# VISUALIZATION DEFAULTS
# ================================================================

FIG_DIR = "figures"
FIG_DPI = 150
FIG_SIZE = (10, 6)

MATPLOTLIB_RC = {
    "font.family": "AppleGothic",
    "axes.unicode_minus": False,
    "figure.dpi": FIG_DPI,
    "figure.figsize": FIG_SIZE,
    "axes.grid": True,
    "grid.alpha": 0.3,
}
