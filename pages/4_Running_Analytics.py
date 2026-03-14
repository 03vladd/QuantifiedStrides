"""
Running Analytics — GAP, aerobic decoupling, biomechanics trends, terrain response.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import date

from db import get_connection
from analytics.running_economy import get_running_trends
from analytics.biomechanics import get_biomechanics_trends
from analytics.terrain_response import get_terrain_summary

st.set_page_config(page_title="Running Analytics", page_icon="🏃", layout="wide")
st.title("🏃 Running Analytics")

today = date.today()

DARK_LAYOUT = dict(
    paper_bgcolor="#0e1117",
    plot_bgcolor="#0e1117",
    font_color="#fafafa",
    xaxis=dict(gridcolor="#2a2a2a", showgrid=True),
    yaxis=dict(gridcolor="#2a2a2a", showgrid=True),
    margin=dict(l=40, r=20, t=40, b=40),
)

# ---------------------------------------------------------------------------
# Days selector
# ---------------------------------------------------------------------------
days = st.select_slider(
    "Lookback period",
    options=[90, 180, 365, 548, 730],
    value=365,
    format_func=lambda d: {90: "3 months", 180: "6 months", 365: "1 year",
                           548: "18 months", 730: "2 years"}[d],
)

# ---------------------------------------------------------------------------
# Cached loaders
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600)
def load_economy_trends(days):
    conn = get_connection()
    data = get_running_trends(days=days, conn=conn)
    conn.close()
    return data


@st.cache_data(ttl=600)
def load_biomechanics(days):
    conn = get_connection()
    data = get_biomechanics_trends(days=days, conn=conn)
    conn.close()
    return data


@st.cache_data(ttl=600)
def load_terrain(days):
    conn = get_connection()
    data = get_terrain_summary(days=days, conn=conn)
    conn.close()
    return data


# ---------------------------------------------------------------------------
# 1. Grade-Adjusted Pace & Aerobic Decoupling
# ---------------------------------------------------------------------------
col_hdr, col_btn = st.columns([8, 1])
col_hdr.subheader("Grade-Adjusted Pace & Aerobic Decoupling")
if col_btn.button("🔄", key="ref_econ", help="Refresh"):
    load_economy_trends.clear()
    st.toast("Economy data refreshed", icon="✅")

economy = load_economy_trends(days)
econ_data = [r for r in economy if r["avg_gap"] is not None]

if not econ_data:
    st.info("No running data with gradient information yet.")
else:
    dates    = [r["workout_date"] for r in econ_data]
    avg_pace = [r["avg_pace"]     for r in econ_data]
    avg_gap  = [r["avg_gap"]      for r in econ_data]
    decoup   = [r["decoupling_pct"] for r in econ_data]
    distance = [r["distance_km"]  for r in econ_data]
    sports   = [r["sport"]        for r in econ_data]

    hover_text = [
        f"{d}<br>{s}<br>{dist:.1f} km<br>Pace: {p:.2f} min/km<br>GAP: {g:.2f} min/km"
        for d, s, dist, p, g in zip(dates, sports, distance, avg_pace, avg_gap)
    ]

    col_a, col_b = st.columns(2)

    with col_a:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, y=avg_pace, mode="markers+lines", name="Actual Pace",
            marker=dict(color="#4da6ff", size=6),
            line=dict(color="#4da6ff", width=1, dash="dot"),
            text=hover_text, hoverinfo="text",
        ))
        fig.add_trace(go.Scatter(
            x=dates, y=avg_gap, mode="markers+lines", name="GAP (terrain-adjusted)",
            marker=dict(color="#00cc7a", size=7),
            line=dict(color="#00cc7a", width=2),
            text=hover_text, hoverinfo="text",
        ))
        fig.update_layout(
            title="Pace vs Grade-Adjusted Pace",
            yaxis_title="min/km (lower = faster)",
            yaxis_autorange="reversed",
            legend=dict(orientation="h", y=-0.2),
            **DARK_LAYOUT,
        )
        st.plotly_chart(fig, width="stretch")

    with col_b:
        decoup_clean = [d for d in decoup if d is not None]
        dates_d = [r["workout_date"] for r in econ_data if r["decoupling_pct"] is not None]
        colors_d = [
            "#00cc7a" if d < 5 else "#ffb347" if d < 10 else "#ff4d4d"
            for d in decoup_clean
        ]

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=dates_d, y=decoup_clean, name="Decoupling %",
            marker_color=colors_d, text=[f"{d:.1f}%" for d in decoup_clean],
            textposition="outside",
        ))
        fig2.add_hline(y=5,  line_color="#ffb347", line_dash="dash",
                       annotation_text="5% threshold",    annotation_position="top right")
        fig2.add_hline(y=10, line_color="#ff4d4d", line_dash="dash",
                       annotation_text="10% cardiac drift", annotation_position="top right")
        fig2.update_layout(
            title="Aerobic Decoupling per Run",
            yaxis_title="Pa:HR Drift (%)",
            showlegend=False,
            **DARK_LAYOUT,
        )
        st.plotly_chart(fig2, width="stretch")

    # Summary stats
    valid_d = [d for d in decoup if d is not None]
    if valid_d:
        efficient = sum(1 for d in valid_d if d < 5)
        drift     = sum(1 for d in valid_d if d >= 10)
        st.caption(
            f"Last {len(valid_d)} runs:  "
            f"**{efficient}** aerobically efficient (<5%)  ·  "
            f"**{drift}** cardiac drift (>10%)"
        )

st.divider()

# ---------------------------------------------------------------------------
# 2. Running Economy Index
# ---------------------------------------------------------------------------
col_hdr2, _ = st.columns([8, 1])
col_hdr2.subheader("Running Economy Index")

rei_data = [r for r in economy if r["rei"] is not None]
if not rei_data:
    st.info("Not enough data for running economy index (need pace + power or HR data).")
else:
    dates_r  = [r["workout_date"] for r in rei_data]
    rei_vals = [r["rei"]          for r in rei_data]
    modes    = [r["rei_mode"]     for r in rei_data]

    power_based = [r for r in rei_data if r["rei_mode"] == "power"]
    hr_based    = [r for r in rei_data if r["rei_mode"] == "hr"]

    fig3 = go.Figure()
    if power_based:
        fig3.add_trace(go.Scatter(
            x=[r["workout_date"] for r in power_based],
            y=[r["rei"]          for r in power_based],
            mode="markers+lines", name="Power-based REI",
            marker=dict(color="#ff9933", size=7),
            line=dict(color="#ff9933", width=2),
        ))
    if hr_based:
        fig3.add_trace(go.Scatter(
            x=[r["workout_date"] for r in hr_based],
            y=[r["rei"]          for r in hr_based],
            mode="markers", name="HR-based REI",
            marker=dict(color="#9999ff", size=6, symbol="diamond"),
        ))

    fig3.update_layout(
        title="Running Economy Index (lower = more efficient)",
        yaxis_title="W/(m/s)  or  bpm/(m/s)",
        legend=dict(orientation="h", y=-0.2),
        **DARK_LAYOUT,
    )
    st.plotly_chart(fig3, width="stretch")
    st.caption("Power-based REI: watts per m/s (Stryd/power meter). HR-based: beats per m/s (proxy).")

st.divider()

# ---------------------------------------------------------------------------
# 3. Biomechanics Trends
# ---------------------------------------------------------------------------
col_hdr3, col_btn3 = st.columns([8, 1])
col_hdr3.subheader("Biomechanics Trends")
if col_btn3.button("🔄", key="ref_bio", help="Refresh"):
    load_biomechanics.clear()
    st.toast("Biomechanics refreshed", icon="✅")

bio = load_biomechanics(days)
bio_valid = [r for r in bio if r.get("avg_cadence") is not None]

if not bio_valid:
    st.info("No biomechanics data available.")
else:
    dates_b  = [r["workout_date"] for r in bio_valid]

    col_c, col_d = st.columns(2)

    with col_c:
        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(
            x=dates_b, y=[r["avg_cadence"] for r in bio_valid],
            mode="markers+lines", name="Cadence",
            marker=dict(color="#4da6ff", size=6),
            line=dict(color="#4da6ff", width=1.5),
        ))
        fig4.update_layout(
            title="Avg Cadence (spm)", yaxis_title="Steps/min",
            **DARK_LAYOUT,
        )
        st.plotly_chart(fig4, width="stretch")

    with col_d:
        gct_data = [r for r in bio_valid if r.get("avg_gct")]
        if gct_data:
            fig5 = go.Figure()
            fig5.add_trace(go.Scatter(
                x=[r["workout_date"] for r in gct_data],
                y=[r["avg_gct"]      for r in gct_data],
                mode="markers+lines", name="GCT",
                marker=dict(color="#ff6b6b", size=6),
                line=dict(color="#ff6b6b", width=1.5),
            ))
            fig5.update_layout(
                title="Avg Ground Contact Time (ms)",
                yaxis_title="ms (lower = better)",
                **DARK_LAYOUT,
            )
            st.plotly_chart(fig5, width="stretch")

    # Fatigue signature
    fat_data = [r for r in bio if r.get("fatigue_score") is not None]
    if fat_data:
        col_e, col_f = st.columns(2)
        with col_e:
            fig6 = go.Figure()
            fig6.add_trace(go.Bar(
                x=[r["workout_date"]  for r in fat_data],
                y=[r["fatigue_score"] for r in fat_data],
                name="Fatigue Score",
                marker_color=[
                    "#00cc7a" if r["fatigue_score"] < 20
                    else "#ffb347" if r["fatigue_score"] < 40
                    else "#ff4d4d"
                    for r in fat_data
                ],
            ))
            fig6.update_layout(
                title="Late-Run Fatigue Score (first 20% vs last 20%)",
                yaxis_title="Score (lower = form held better)",
                showlegend=False,
                **DARK_LAYOUT,
            )
            st.plotly_chart(fig6, width="stretch")

        with col_f:
            fig7 = go.Figure()
            fig7.add_trace(go.Scatter(
                x=[r["workout_date"]    for r in fat_data if r.get("gct_drift_pct") is not None],
                y=[r["gct_drift_pct"]   for r in fat_data if r.get("gct_drift_pct") is not None],
                mode="markers+lines", name="GCT Drift %",
                marker=dict(color="#ff9933", size=6),
                line=dict(color="#ff9933", width=1.5),
            ))
            fig7.add_trace(go.Scatter(
                x=[r["workout_date"]       for r in fat_data if r.get("cadence_drift_pct") is not None],
                y=[r["cadence_drift_pct"]  for r in fat_data if r.get("cadence_drift_pct") is not None],
                mode="markers+lines", name="Cadence Drift %",
                marker=dict(color="#9999ff", size=6),
                line=dict(color="#9999ff", width=1.5, dash="dot"),
            ))
            fig7.add_hline(y=0, line_color="gray", line_width=1)
            fig7.update_layout(
                title="Form Drift (end vs start)",
                yaxis_title="% change (GCT: positive=worse | Cadence: negative=worse)",
                legend=dict(orientation="h", y=-0.2),
                **DARK_LAYOUT,
            )
            st.plotly_chart(fig7, width="stretch")

st.divider()

# ---------------------------------------------------------------------------
# 4. Terrain Response
# ---------------------------------------------------------------------------
col_hdr4, col_btn4 = st.columns([8, 1])
col_hdr4.subheader("Terrain Response")
if col_btn4.button("🔄", key="ref_terr", help="Refresh"):
    load_terrain.clear()
    st.toast("Terrain data refreshed", icon="✅")

terrain = load_terrain(days)
curve = terrain.get("hr_gradient_curve", [])
model = terrain.get("grade_cost_model")
optimal = terrain.get("optimal_gradient")

if not curve:
    st.info("Not enough gradient data yet. Needs GPS+altitude data from outdoor runs.")
else:
    col_g, col_h = st.columns(2)

    with col_g:
        band_labels = [b["band"].replace("_", " ") for b in curve]
        avg_hrs     = [b["avg_hr"]  for b in curve]
        grad_mids   = [b["gradient_mid"] for b in curve]

        fig8 = go.Figure()
        fig8.add_trace(go.Bar(
            x=band_labels, y=avg_hrs, name="Avg HR",
            marker_color=["#4da6ff" if g <= 0 else "#ff6b6b" for g in grad_mids],
            text=[f"{h:.0f}" for h in avg_hrs], textposition="outside",
        ))
        fig8.update_layout(
            title="Avg HR by Gradient Band",
            yaxis_title="bpm",
            showlegend=False,
            **DARK_LAYOUT,
        )
        st.plotly_chart(fig8, width="stretch")

    with col_h:
        efficiencies = [b["efficiency"] * 1000 for b in curve]
        opt_grad = optimal["optimal_gradient"] if optimal else None

        fig9 = go.Figure()
        fig9.add_trace(go.Bar(
            x=band_labels, y=efficiencies, name="Efficiency",
            marker_color=[
                "#00cc7a" if (opt_grad is not None and abs(b["gradient_mid"] - opt_grad) < 2) else "#999"
                for b in curve
            ],
            text=[f"{e:.4f}" for e in efficiencies], textposition="outside",
        ))
        fig9.update_layout(
            title="Speed per HR Beat by Gradient (higher = more efficient)",
            yaxis_title="×10⁻³ m/s per bpm",
            showlegend=False,
            **DARK_LAYOUT,
        )
        st.plotly_chart(fig9, width="stretch")

    # Grade cost model summary
    if model:
        st.markdown(
            f"**Your HR cost per 1% gradient:** `{model['slope_bpm_per_pct']:+.2f} bpm/%`  ·  "
            f"Minetti theoretical: `{model['minetti_expected']:+.3f} bpm/%`  ·  "
            f"R²: `{model['r_squared']:.3f}`  ·  "
            f"({model['n_points']:,} data points)"
        )
        ratio = model["slope_bpm_per_pct"] / model["minetti_expected"] if model["minetti_expected"] else None
        if ratio:
            if ratio > 1.2:
                st.warning("You pay more HR cost for gradient than the theoretical model predicts. Uphill running economy is an area to develop.")
            elif ratio < 0.8:
                st.success("Your HR response to gradient is lower than the Minetti model predicts — strong uphill economy.")
            else:
                st.info("Your HR response to gradient tracks the Minetti model closely.")

    if optimal:
        st.caption(f"Optimal gradient (best speed:HR ratio): **{optimal['optimal_gradient']:+.0f}%**")
