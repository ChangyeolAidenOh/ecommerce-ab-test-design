"""Streamlit dashboard for interactive experiment design exploration. Serves as an interactive companion to the experiment design documents"""

import sys
import os

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from simulation.config import (
    ALPHA, POWER, DAILY_ACTIVE_USERS, BODY_TYPE_FILTER_RATE,
    GIF_CONFIG, REVIEW_SORT_CONFIG,
)
from simulation.power_analysis import (
    compute_sample_size, compute_mde, compute_power, estimate_duration,
)


# PAGE CONFIG

st.set_page_config(
    page_title="A/B Test Experiment Designer",
    page_icon="🧪",
    layout="wide",
)

st.title("A/B Test Experiment Designer")
st.caption(
    "Interactive tool for experiment design exploration. "
    "Companion to the Experiment Design Documents (docs/)."
)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Power Calculator",
    "Peeking Simulator",
    "NIM Sensitivity",
    "Method Comparison",
    "Bucket Trade-off",
])


# TAB 1: POWER CALCULATOR

with tab1:
    st.header("Power Calculator")
    st.markdown(
        "Compute required sample size, experiment duration, "
        "and minimum detectable effect."
    )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Parameters")
        baseline = st.slider(
            "Baseline CVR (%)", 1.0, 10.0, 3.2, 0.1,
            help="Control group conversion rate"
        ) / 100
        mde = st.slider(
            "MDE (%p)", 0.1, 2.0, 0.3, 0.05,
            help="Minimum Detectable Effect (absolute)"
        ) / 100
        alpha = st.slider("Alpha", 0.01, 0.10, 0.05, 0.01)
        power = st.slider("Power", 0.70, 0.95, 0.80, 0.05)
        dau = st.number_input("DAU", 1000, 500000, 50000, 1000)
        n_variants = st.selectbox("Number of arms", [2, 3, 4], index=0)
        traffic_frac = st.slider("Traffic allocation (%)", 10, 100, 50, 5) / 100

    with col2:
        st.subheader("Results")

        n_required = compute_sample_size(baseline, mde, alpha, power)
        duration = estimate_duration(dau, n_required, n_variants, traffic_frac)
        actual_power = compute_power(baseline, mde, n_required, alpha)

        st.metric("Required n per group", f"{n_required:,}")
        st.metric("Estimated duration", f"{duration} days")
        st.metric("Actual power", f"{actual_power:.1%}")

        # Duration for different MDEs
        st.subheader("MDE vs Duration")
        mde_range = np.arange(0.001, 0.015, 0.0005)
        durations = [
            estimate_duration(
                dau,
                compute_sample_size(baseline, m, alpha, power),
                n_variants, traffic_frac
            )
            for m in mde_range
        ]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=mde_range * 100, y=durations,
            mode="lines", line=dict(color="#2563eb", width=2),
        ))
        fig.add_hline(y=14, line_dash="dash", line_color="#22c55e",
                       annotation_text="2 weeks")
        fig.add_hline(y=28, line_dash="dash", line_color="#f59e0b",
                       annotation_text="4 weeks")
        fig.add_vline(x=mde * 100, line_dash="dot", line_color="#dc2626",
                       annotation_text=f"Current MDE={mde*100:.1f}%p")
        fig.update_layout(
            xaxis_title="MDE (%p)", yaxis_title="Duration (days)",
            height=400, margin=dict(t=30),
        )
        st.plotly_chart(fig, use_container_width=True)


# TAB 2: PEEKING SIMULATOR

with tab2:
    st.header("Peeking Problem Simulator")
    st.markdown(
        "Demonstrates how checking p-values mid-experiment inflates "
        "Type I error rate."
    )

    col1, col2 = st.columns([1, 2])

    with col1:
        n_per_group = st.slider("Final n per group", 1000, 50000, 10000, 1000)
        peek_interval = st.slider("Peek every N", 100, 2000, 500, 100)
        n_sims = st.slider("Simulations", 500, 5000, 2000, 500)
        base_rate = st.slider(
            "Baseline rate (%)", 1.0, 10.0, 3.2, 0.1
        ) / 100

    with col2:
        if st.button("Run Peeking Simulation"):
            with st.spinner("Simulating..."):
                rng = np.random.default_rng(42)
                peek_points = list(range(
                    peek_interval, n_per_group + 1, peek_interval
                ))
                if peek_points[-1] != n_per_group:
                    peek_points.append(n_per_group)

                first_sig = np.full(n_sims, -1, dtype=int)

                progress = st.progress(0)
                for sim in range(n_sims):
                    if sim % 100 == 0:
                        progress.progress(sim / n_sims)
                    ctrl = rng.binomial(1, base_rate, n_per_group)
                    trt = rng.binomial(1, base_rate, n_per_group)

                    for pn in peek_points:
                        if first_sig[sim] >= 0:
                            break
                        c_s, t_s = ctrl[:pn].sum(), trt[:pn].sum()
                        pooled = (c_s + t_s) / (2 * pn)
                        if pooled == 0 or pooled == 1:
                            continue
                        se = np.sqrt(2 * pooled * (1 - pooled) / pn)
                        z = abs(t_s / pn - c_s / pn) / se
                        pv = 2 * (1 - stats.norm.cdf(z))
                        if pv < 0.05:
                            first_sig[sim] = pn
                progress.progress(1.0)

                cum_fp = {}
                for p in peek_points:
                    n_flagged = np.sum(
                        (first_sig >= 0) & (first_sig <= p)
                    )
                    cum_fp[p] = n_flagged / n_sims

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=list(cum_fp.keys()),
                    y=[v * 100 for v in cum_fp.values()],
                    mode="lines+markers",
                    line=dict(color="#dc2626", width=2),
                    name="Cumulative FP rate",
                ))
                fig.add_hline(
                    y=5, line_dash="dash", line_color="#22c55e",
                    annotation_text="Nominal alpha=5%",
                )
                final_fp = list(cum_fp.values())[-1]
                fig.update_layout(
                    xaxis_title="Sample size at peek",
                    yaxis_title="Cumulative False Positive Rate (%)",
                    title=f"Final FP rate: {final_fp:.1%} "
                          f"({final_fp/0.05:.1f}x inflation)",
                    height=450, margin=dict(t=50),
                )
                st.plotly_chart(fig, use_container_width=True)

                st.info(
                    f"Nominal alpha = 5%. "
                    f"With peeking every {peek_interval}: "
                    f"**{final_fp:.1%}** "
                    f"({final_fp/0.05:.1f}x inflation)"
                )


# TAB 3: NIM SENSITIVITY

with tab3:
    st.header("NIM Sensitivity Analysis")
    st.markdown(
        "How does the Non-Inferiority Margin (NIM) setting change "
        "the guardrail decision?"
    )

    col1, col2 = st.columns([1, 2])

    with col1:
        ctrl_rate = st.slider(
            "Control guardrail rate (%)", 5.0, 25.0, 12.0, 0.5
        ) / 100
        trt_rate = st.slider(
            "Treatment guardrail rate (%)", 5.0, 25.0, 12.5, 0.5
        ) / 100
        sample_n = st.number_input(
            "Sample size per group", 1000, 200000, 50000, 1000
        )

        obs_diff = trt_rate - ctrl_rate
        st.markdown(f"**Observed difference: {obs_diff*100:+.1f}%p**")

    with col2:
        nim_range = np.arange(0.001, 0.030, 0.001)
        results = []
        for nim in nim_range:
            se = np.sqrt(
                ctrl_rate * (1 - ctrl_rate) / sample_n +
                trt_rate * (1 - trt_rate) / sample_n
            )
            z_a = stats.norm.ppf(1 - 0.05)
            ci_upper = obs_diff + z_a * se
            non_inf = ci_upper < nim
            results.append({
                "nim": nim * 100,
                "non_inferior": non_inf,
                "ci_upper": ci_upper * 100,
            })

        df_nim = pd.DataFrame(results)

        fig = go.Figure()
        colors = ["#22c55e" if r else "#dc2626" for r in df_nim["non_inferior"]]
        fig.add_trace(go.Bar(
            x=df_nim["nim"], y=[1] * len(df_nim),
            marker_color=colors, name="Decision",
            hovertemplate="NIM=%{x:.1f}%p<br>%{customdata}",
            customdata=["NON-INFERIOR" if r else "INFERIOR"
                         for r in df_nim["non_inferior"]],
        ))
        fig.add_vline(
            x=obs_diff * 100, line_dash="dot", line_color="#2563eb",
            annotation_text=f"Observed diff={obs_diff*100:.1f}%p",
        )

        # Find critical NIM
        for i, row in df_nim.iterrows():
            if row["non_inferior"]:
                fig.add_vline(
                    x=row["nim"], line_dash="dash", line_color="#f59e0b",
                    annotation_text=f"Critical NIM={row['nim']:.1f}%p",
                )
                break

        fig.update_layout(
            xaxis_title="NIM (%p)",
            yaxis_visible=False,
            title="Green = NON-INFERIOR, Red = INFERIOR",
            height=300, margin=dict(t=50),
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Decision matrix:**")
        for nim_val in [0.5, 0.8, 1.0, 1.5, 2.0]:
            se = np.sqrt(
                ctrl_rate * (1 - ctrl_rate) / sample_n +
                trt_rate * (1 - trt_rate) / sample_n
            )
            ci_up = obs_diff + stats.norm.ppf(0.95) * se
            status = "NON-INFERIOR" if ci_up < nim_val / 100 else "INFERIOR"
            icon = "🟢" if status == "NON-INFERIOR" else "🔴"
            st.write(f"{icon} NIM={nim_val}%p: **{status}**")


# TAB 4: METHOD COMPARISON

with tab4:
    st.header("Method Comparison")
    st.markdown(
        "Compare Frequentist and Bayesian conclusions "
        "across different effect sizes."
    )

    col1, col2 = st.columns([1, 2])

    with col1:
        mc_baseline = st.slider(
            "Baseline CVR (%) ", 1.0, 10.0, 3.2, 0.1, key="mc_base"
        ) / 100
        mc_n = st.number_input(
            "Sample size per group ", 5000, 200000, 50000, 5000
        )
        mc_threshold = st.slider(
            "Bayesian threshold", 0.90, 0.99, 0.95, 0.01
        )

    with col2:
        if st.button("Run Comparison"):
            with st.spinner("Computing..."):
                rng = np.random.default_rng(42)
                effects = np.arange(0.0005, 0.006, 0.0003)
                rows = []

                for eff in effects:
                    ctrl = rng.binomial(1, mc_baseline, mc_n)
                    trt = rng.binomial(1, mc_baseline + eff, mc_n)

                    # Frequentist
                    c_conv, t_conv = ctrl.sum(), trt.sum()
                    pooled = (c_conv + t_conv) / (2 * mc_n)
                    se = np.sqrt(2 * pooled * (1 - pooled) / mc_n)
                    if se > 0:
                        z = (t_conv / mc_n - c_conv / mc_n) / se
                        p = 2 * (1 - stats.norm.cdf(abs(z)))
                    else:
                        p = 1.0
                    freq_sig = p < 0.05

                    # Bayesian
                    post_a = stats.beta(1 + c_conv, 1 + mc_n - c_conv)
                    post_b = stats.beta(1 + t_conv, 1 + mc_n - t_conv)
                    samp_a = rng.beta(post_a.args[0], post_a.args[1], 50000)
                    samp_b = rng.beta(post_b.args[0], post_b.args[1], 50000)
                    prob_b = float(np.mean(samp_b > samp_a))
                    bayes_sig = prob_b > mc_threshold

                    rows.append({
                        "effect": eff * 100,
                        "freq_p": p,
                        "freq_sig": freq_sig,
                        "bayes_prob": prob_b,
                        "bayes_sig": bayes_sig,
                        "agree": freq_sig == bayes_sig,
                    })

                df_mc = pd.DataFrame(rows)

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_mc["effect"], y=df_mc["freq_p"],
                    mode="lines+markers", name="Frequentist p-value",
                    line=dict(color="#2563eb"),
                ))
                fig.add_trace(go.Scatter(
                    x=df_mc["effect"], y=1 - df_mc["bayes_prob"],
                    mode="lines+markers", name="Bayesian 1-P(B>A)",
                    line=dict(color="#dc2626"),
                ))
                fig.add_hline(y=0.05, line_dash="dash", line_color="#94a3b8",
                               annotation_text="alpha=0.05")
                fig.update_layout(
                    xaxis_title="True effect (%p)",
                    yaxis_title="p-value / 1-P(B>A)",
                    title="Where do methods disagree?",
                    height=400, margin=dict(t=50),
                )
                st.plotly_chart(fig, use_container_width=True)

                disagreements = df_mc[~df_mc["agree"]]
                if len(disagreements) > 0:
                    st.warning(
                        f"Disagreement at {len(disagreements)} effect sizes: "
                        f"{disagreements['effect'].tolist()}"
                    )
                else:
                    st.success("Both methods agree across all effect sizes.")


# TAB 5: BUCKET TRADE-OFF

with tab5:
    st.header("Body Type Bucket Trade-off")
    st.markdown(
        "How does bucket size affect the number of "
        "body-type reviews per product?"
    )

    col1, col2 = st.columns([1, 2])

    with col1:
        n_products = st.slider("Number of products", 100, 5000, 1000, 100)
        mean_reviews = st.slider("Mean total reviews/product", 10, 200, 40, 5)
        min_useful = st.slider(
            "Minimum useful reviews", 1, 10, 3, 1,
            help="How many body-type reviews needed for the filter to be useful?"
        )

    with col2:
        bucket_sizes = [3, 5, 7, 10]
        rng = np.random.default_rng(42)
        total_reviews = np.clip(
            rng.lognormal(np.log(mean_reviews), 1.0, n_products).astype(int),
            0, 5000,
        )

        results = []
        for bs in bucket_sizes:
            # Number of buckets for height x weight
            h_buckets = max(1, int(50 / bs))  # ~140-190cm range
            w_buckets = max(1, int(50 / bs))  # ~40-90kg range
            n_combos = h_buckets * w_buckets

            # For each product, expected reviews in the target bucket
            # Assuming uniform-ish distribution across buckets
            # (simplified; real distribution is concentrated)
            target_fraction = 1.0 / n_combos
            target_reviews = total_reviews * target_fraction

            pct_useful = np.mean(target_reviews >= min_useful) * 100

            results.append({
                "bucket_size": f"{bs}cm/{bs}kg",
                "n_combos": n_combos,
                "median_target_reviews": round(float(np.median(target_reviews)), 1),
                "pct_useful": round(pct_useful, 1),
            })

        df_bucket = pd.DataFrame(results)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_bucket["bucket_size"],
            y=df_bucket["pct_useful"],
            marker_color=["#dc2626", "#2563eb", "#f59e0b", "#22c55e"],
            text=[f"{v}%" for v in df_bucket["pct_useful"]],
            textposition="outside",
        ))
        fig.update_layout(
            xaxis_title="Bucket size",
            yaxis_title=f"% products with >= {min_useful} target reviews",
            title=f"Bucket Size vs Review Availability (n={n_products})",
            height=400, margin=dict(t=50),
            yaxis_range=[0, 100],
        )
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(df_bucket, use_container_width=True, hide_index=True)

        st.markdown(
            f"**Current Ably setting: 5cm/5kg** — "
            f"{df_bucket[df_bucket['bucket_size']=='5cm/5kg']['pct_useful'].values[0]}% "
            f"of products have >= {min_useful} target body-type reviews."
        )


# SIDEBAR

with st.sidebar:
    st.markdown("### About")
    st.markdown(
        "This dashboard is a companion to the "
        "**E-commerce A/B Test Design** project. "
        "It provides interactive exploration of experiment "
        "design parameters discussed in the design documents."
    )
    st.markdown("---")
    st.markdown("### Project Links")
    st.markdown("- `docs/case1_gif_feed_density.md`")
    st.markdown("- `docs/case2_review_sort_order.md`")
    st.markdown("- `docs/methodology_comparison.md`")
    st.markdown("- `docs/external_validation.md`")
    st.markdown("---")
    st.markdown(
        "**Data Sources**\n"
        "- User params: KOSIS Health Screening 2024\n"
        "- Age ratio: WiseApp/Retail 2025\n"
        "- Bucket structure: Ably app screenshots\n"
        "- Validation: ASOS OCE Dataset (NeurIPS 2021)"
    )
