import streamlit as st
import numpy as np
import pandas as pd
import plotly.figure_factory as ff
import plotly.graph_objects as go
import time

st.set_page_config(page_title="CRO Business Case Calculator", layout="wide")

st.title("Yellowgrape's Business Case Calculator")
st.markdown("""
    <style>
    /* Ensure text on primary buttons (yellow) is black and readable */
    button[kind="primary"] {
        color: #000000 !important;
    }
    button[kind="primary"] p {
        color: #000000 !important;
        font-weight: 600;
    }
    
    /* Multiselect tag styling */
    span[data-baseweb="tag"], 
    div[data-testid="stMultiSelectTag"],
    div[data-baseweb="tag"] {
        background-color: #FFFF00 !important;
    }
    span[data-baseweb="tag"] *, 
    div[data-testid="stMultiSelectTag"] *,
    div[data-baseweb="tag"] * {
        color: #000000 !important;
        fill: #000000 !important;
    }
    </style>
""", unsafe_allow_html=True)
st.markdown("""
This tool calculates the impact of your A/B test using Bayesian statistics. 
The calculator simulates 100,000 scenarios to not only determine the 'winner', 
but also project the expected long-term financial impact.
""")

st.header("Test Data")

col_head1, col_head2 = st.columns(2)
with col_head1:
    num_challengers = st.number_input("Number of Challenger Variants", min_value=1, max_value=5, value=1, help="How many variants are you testing against the Control (Variant A)?")

st.divider()

cols = st.columns(num_challengers + 1)
variants_data = []

with cols[0]:
    st.subheader("Variant A (Control)")
    users = st.number_input("Visitors A", value=1000, min_value=0, step=1, key="users_0", help="The total number of visitors that have seen Variant A.")
    conv = st.number_input("Conversions A", value=123, min_value=0, step=1, key="conv_0", help="The total number of transactions or goal completions for Variant A.")
    aov = st.number_input("AOV A (€)", value=10.00, key="aov_0", help="The Average Order Value for Variant A.")
    std = st.number_input("StdDev AOV A", value=1.00, key="std_0", help="The Standard Deviation of the order value for A.")
    variants_data.append({"name": "Variant A", "users": users, "conv": conv, "aov": aov, "std": std})

letters = ["B", "C", "D", "E", "F"]
default_users = [1000, 0, 0, 0, 0]
default_convs = [134, 0, 0, 0, 0]
default_aovs = [10.50, 0.0, 0.0, 0.0, 0.0]
default_stds = [2.00, 0.0, 0.0, 0.0, 0.0]

for i in range(num_challengers):
    with cols[i+1]:
        letter = letters[i]
        st.subheader(f"Variant {letter}")
        users = st.number_input(f"Visitors {letter}", value=default_users[i], min_value=0, step=1, key=f"users_{i+1}")
        conv = st.number_input(f"Conversions {letter}", value=default_convs[i], min_value=0, step=1, key=f"conv_{i+1}")
        aov = st.number_input(f"AOV {letter} (€)", value=default_aovs[i], key=f"aov_{i+1}")
        std = st.number_input(f"StdDev AOV {letter}", value=default_stds[i], key=f"std_{i+1}")
        variants_data.append({"name": f"Variant {letter}", "users": users, "conv": conv, "aov": aov, "std": std})

st.divider()
st.subheader("Seasonality & Projection Settings")

use_seasonality = st.checkbox("Enable Seasonality Logic", value=False, help="Adjust the projected traffic based on high-season periods.")

all_months_list = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

seasonality_data = {"enabled": False}

if use_seasonality:
    col_seas1, col_seas2 = st.columns(2)
    with col_seas1:
        test_months_selected = st.multiselect("Months the test was active", options=all_months_list, default=[], help="This helps us calculate the baseline traffic based on when the test took place.")
        high_season_months_selected = st.multiselect("High Season Months", options=all_months_list, default=[], help="Which months generally experience peak traffic?")
    with col_seas2:
        proj_start_month = st.selectbox("Projection Starting Month", options=all_months_list, index=0, help="From which month does your projection start?")
        season_multiplier = st.number_input("High Season Traffic Multiplier", value=1.0, min_value=1.0, step=0.1, help="E.g., 1.5 means high season months generate 50% more traffic than regular months.")

    seasonality_data = {
        "enabled": True,
        "high_months": high_season_months_selected,
        "test_months": test_months_selected,
        "start_month": proj_start_month,
        "multiplier": season_multiplier
    }

col_proj1, col_proj2 = st.columns(2)
with col_proj1:
    months = st.slider("Projection period (months)", 1, 12, 6, help="Over how many months do you want to calculate the impact? (e.g., the rest of the year)")
with col_proj2:
    duration_days = st.number_input("Test duration (days)", value=42, min_value=1, help="Total number of days the A/B test has been running. Needed to forecast monthly traffic.")

bc_aov = np.mean([v["aov"] for v in variants_data])

def run_simulation(variants_data, bc_aov, samples=100000):
    results = {"std": [], "adv": []}
    for v in variants_data:
        cr_samples = np.random.beta(v["conv"] + 1, v["users"] - v["conv"] + 1, samples)
        se = v["std"] / np.sqrt(max(1, v["conv"]))
        aov_samples = np.random.normal(v["aov"], se, samples)
        
        rpv_std = cr_samples * bc_aov
        rpv_adv = cr_samples * aov_samples
        
        results["std"].append({
            "name": v["name"], 
            "rpv": rpv_std, 
            "chart_data": cr_samples * 100, 
            "aov_samples": None
        })
        results["adv"].append({
            "name": v["name"], 
            "rpv": rpv_adv, 
            "chart_data": rpv_adv, 
            "aov_samples": aov_samples
        })
    return results

def get_total_period_traffic(variants_data, duration_days, months, seasonality_data=None):
    total_visitors = sum([v["users"] for v in variants_data])
    est_monthly_traffic_raw = (total_visitors / duration_days) * 30.44
    
    if seasonality_data and seasonality_data.get("enabled"):
        high_months = seasonality_data["high_months"]
        test_months = seasonality_data["test_months"]
        start_month = seasonality_data["start_month"]
        multiplier = seasonality_data["multiplier"]
        
        if len(test_months) > 0:
            avg_test_mult = np.mean([multiplier if m in high_months else 1.0 for m in test_months])
        else:
            avg_test_mult = 1.0
        
        base_monthly_traffic = est_monthly_traffic_raw / avg_test_mult
        start_idx = all_months_list.index(start_month)
        projected_months_list = [all_months_list[(start_idx + i) % 12] for i in range(months)]
        
        proj_traffic = 0
        for m in projected_months_list:
            if m in high_months:
                proj_traffic += base_monthly_traffic * multiplier
            else:
                proj_traffic += base_monthly_traffic
        return proj_traffic
    else:
        return est_monthly_traffic_raw * months

def display_results(control_data, challenger_data, chart_label, months, total_period_traffic):
    st.markdown(f"## Comparison: {challenger_data['name']} vs {control_data['name']}")
    
    diff = challenger_data["rpv"] - control_data["rpv"]
    prob_b_better = np.mean(diff > 0) * 100
    prob_a_better = 100 - prob_b_better
    
    loss_rpv = np.mean(np.maximum(0, control_data["rpv"] - challenger_data["rpv"]))
    uplift_rpv = np.mean(np.maximum(0, challenger_data["rpv"] - control_data["rpv"]))
    
    risk_euro = loss_rpv * total_period_traffic
    gain_euro = uplift_rpv * total_period_traffic
    net_contribution = gain_euro - risk_euro

    c1, c2 = st.columns(2)
    with c1:
        st.write(f"**Probability {challenger_data['name']} is better:**")
        st.title(f"{prob_b_better:.1f}%")
        st.progress(prob_b_better / 100)
    with c2:
        st.write(f"**Probability {control_data['name']} is better:**")
        st.title(f"{prob_a_better:.1f}%")
        st.progress(prob_a_better / 100)

    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Expected Uplift", f"€{gain_euro:,.0f}")
    m2.metric("Expected Risk", f"-€{risk_euro:,.0f}", delta_color="inverse")
    m3.metric("Net Contribution", f"€{net_contribution:,.0f}")

    chart_data_a = control_data["chart_data"]
    chart_data_b = challenger_data["chart_data"]
    aov_samples_a = control_data["aov_samples"]
    aov_samples_b = challenger_data["aov_samples"]

    if aov_samples_a is not None and aov_samples_b is not None:
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.subheader(f"Density Plot ({chart_label})")
            if np.var(chart_data_a) > 0 and np.var(chart_data_b) > 0:
                fig_curve = ff.create_distplot([chart_data_a, chart_data_b], [control_data["name"], challenger_data["name"]], 
                                         show_hist=False, colors=['#FFFFFF', '#FFFF00'])
                fig_curve.update_layout(xaxis_title=chart_label, yaxis_title="Probability Density", height=400, margin=dict(l=20, r=20, t=30, b=20))
                st.plotly_chart(fig_curve, use_container_width=True)
            else:
                st.info("Not enough data variance to generate density plot.")
        
        with col_c2:
            st.subheader("Density Plot (Order Value €)")
            if np.var(aov_samples_a) > 0 and np.var(aov_samples_b) > 0:
                fig_aov = ff.create_distplot([aov_samples_a, aov_samples_b], [control_data["name"], challenger_data["name"]], 
                                         show_hist=False, colors=['#FFFFFF', '#FFFF00'])
                fig_aov.update_layout(xaxis_title="Average AOV (€)", yaxis_title="Probability Density", height=400, margin=dict(l=20, r=20, t=30, b=20))
                st.plotly_chart(fig_aov, use_container_width=True)
            else:
                st.info("Not enough data variance to generate density plot.")
    else:
        st.subheader(f"Density Plot ({chart_label})")
        if np.var(chart_data_a) > 0 and np.var(chart_data_b) > 0:
            fig_curve = ff.create_distplot([chart_data_a, chart_data_b], [control_data["name"], challenger_data["name"]], 
                                     show_hist=False, colors=['#FFFFFF', '#FFFF00'])
            fig_curve.update_layout(xaxis_title=chart_label, yaxis_title="Probability Density", height=400)
            st.plotly_chart(fig_curve, use_container_width=True)
        else:
            st.info("Not enough data variance to generate density plot.")

    color_bg = "#22c55e" if net_contribution >= 0 else "#ef4444"
    color_txt = "#ffffff"
    
    st.markdown(f"""
        <div style="background-color:{color_bg}; padding:30px; border-radius:15px; text-align:center; color:{color_txt}; margin-top:20px; margin-bottom:60px;">
            <p style="margin:0; font-weight:bold; text-transform:uppercase; font-size:14px; opacity:0.9;">Total contribution ({challenger_data['name']} vs {control_data['name']}) over {months} months</p>
            <h1 style="margin:0; font-size:56px;">€{net_contribution:,.0f}</h1>
        </div>
    """, unsafe_allow_html=True)
    
if "sim_results" not in st.session_state:
    st.session_state.sim_results = None
    st.session_state.total_traffic = 0
    st.session_state.bc_aov = 0

st.write("") 
start_sim = st.button("Start Simulation", type="primary", use_container_width=True)

if start_sim:
    progress_bar = st.progress(0)
    
    st.session_state.sim_results = run_simulation(variants_data, bc_aov)
    st.session_state.total_traffic = get_total_period_traffic(variants_data, duration_days, months, seasonality_data)
    st.session_state.bc_aov = bc_aov
    
    progress_bar.progress(100)
    time.sleep(0.3)
    progress_bar.empty()

if st.session_state.sim_results is not None:
    st.divider()
    st.header("Results & Comparison")
    st.write("Choose which variants you want to compare against each other below. The business case will instantly update to reflect your selection.")
    
    variant_names = [v["name"] for v in variants_data]
    col_comp1, col_comp2 = st.columns(2)
    with col_comp1:
        control_name = st.selectbox("Select Baseline Variant (Control)", options=variant_names, index=0)
    with col_comp2:
        challenger_name = st.selectbox("Select Challenger Variant", options=variant_names, index=min(1, len(variant_names)-1))
        
    if control_name == challenger_name:
        st.warning("Please select two different variants to compare.")
    else:
        results = st.session_state.sim_results
        total_period_traffic = st.session_state.total_traffic
        current_bc_aov = st.session_state.bc_aov

        # Tabs for methods
        tab_adv, tab_std = st.tabs(["Advanced (Recommended)", "Original"])
        
        with tab_adv:
            control_adv = next(v for v in results["adv"] if v["name"] == control_name)
            challenger_adv = next(v for v in results["adv"] if v["name"] == challenger_name)
            
            display_results(control_adv, challenger_adv, "Revenue Per Visitor (€)", months, total_period_traffic)

            st.divider()

            # Explanation
            st.header("How it works")
            st.markdown("""
            ### Why focus on Revenue Per Visitor (RPV)?
            Instead of only looking at conversion rates, this method focuses heavily on the overall **Revenue Per Visitor (RPV)**. 
            This is crucial because an A/B test variant could theoretically decrease your apparent conversion rate, while simultaneously increasing your total revenue by attracting larger, more valuable orders. By looking at RPV, you make business decisions based on real financial impact, not just superficial conversion events.
            """)
        
            st.subheader("Calculation Components")
            col_exp1, col_exp2 = st.columns(2)
            with col_exp1:
                st.write("**1. Conversion Rate Uncertainty**")
                st.write("We model the uncertainty of how often a visitor converts using Bayesian statistics. "
                         "Instead of assuming the observed conversion rate is the absolute truth, this creates a probability distribution curve showing all realistic conversion rates for both variants, based purely on the number of visitors and transactions.")
            with col_exp2:
                st.write("**2. Average Order Value Uncertainty**")
                st.write("We also model the uncertainty surrounding the Average Order Value (AOV). "
                         "By using the specific Standard Deviation (StdDev) you provided, we calculate a probability curve representing where the true AOV most likely lies. Higher Standard Deviations result in a broader, flatter curve (more uncertainty).")
            
            st.write("**3. Business Case & Financial Risk**")
            st.write("Beyond declaring a 'winner', we calculate the financial weight of the decision:")
            st.markdown("""
            - **Expected Uplift:** The average additional revenue you stand to gain across all 100,000 simulations where the Challenger outperforms the Control.
            - **Expected Risk:** The average revenue you might *lose* in scenarios where the Control actually turns out to be better. This is a crucial reality check—even if a variant has a 70% probability of winning, the 'Risk' shows you the potential cost of that 30% chance of being wrong.
            - **Net Contribution:** The final balance (Uplift minus Risk). This represents the most realistic 'bottom line' impact you can expect over the projection period, accounting for all uncertainties.
            """)

            st.write("**4. Monte Carlo Simulation & Seasonality**")
            st.write("By combining the probabilistic models for Conversion Rate and Average Order Value, we simulate **100,000 potential outcomes** ($RPV = Conversion Rate \\times AOV$). "
                     "If enabled, we also deflate the raw test traffic if the test took place during a peak season, and re-inflate the projected traffic strictly for the upcoming peak months you expect. "
                     "This robust combination allows us to determine the exact probability that the selected Challenger is a winner compared to the selected Baseline, and project the expected net financial uplift over your timeframe.")

        with tab_std:
            control_std = next(v for v in results["std"] if v["name"] == control_name)
            challenger_std = next(v for v in results["std"] if v["name"] == challenger_name)
            
            display_results(control_std, challenger_std, "Conversion Rate (%)", months, total_period_traffic)
                
            st.divider()
            st.header("How it works (Original)")
            st.markdown(f"""
            In this original method, we solely focus on the uncertainty surrounding the **conversion rate**. 
            
            To calculate the long-term financial impact, we multiply these simulated conversion rates by a single, fixed Average Order Value for all variants (in this scenario, the combined mean AOV: **€{current_bc_aov:,.2f}**).
            
            *Note: This method is simpler, but it completely ignores the potential reality where a variant impacts the Average Order Value. Because we treat AOV as a static number across all variants, we highly recommend looking at the Advanced tab instead for a more accurate business case.*
            """)
else:
    st.info("Fill in the data above and click 'Start Simulation' to begin.")