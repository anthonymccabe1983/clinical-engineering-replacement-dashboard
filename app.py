
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

def minutes_to_dhm(minutes):
    if pd.isna(minutes):
        return "0d 0h 0m"
    minutes = int(minutes)
    days = minutes // 1440
    hours = (minutes % 1440) // 60
    mins = minutes % 60
    return f"{days}d {hours}h {mins}m"

st.set_page_config(page_title="Clinical Engineering Replacement Planning Dashboard", layout="wide")

st.title("Clinical Engineering Asset Replacement Planning")
st.caption("Interactive replacement prioritization, budgeting, and scenario planning")

# -----------------------------
# Upload Data
# -----------------------------
uploaded_file = st.file_uploader("Upload Nuvolo Clinical Engineering Asset Export (Excel)", type=["xlsx"])

if uploaded_file is None:
    st.info("Please upload your Nuvolo export to begin.")
    st.stop()

df = pd.read_excel(uploaded_file)

# -----------------------------
# Data Preparation
# -----------------------------
today = pd.Timestamp.today()

df["Created"] = pd.to_datetime(df["Created"], errors="coerce")
df["Age (Years)"] = ((today - df["Created"]).dt.days / 365).round(2)

numeric_cols = [
    "Fault Count",
    "Total Unplanned Downtime",
    "Total Cost of Ownership",
    "Acquisition Cost"
]

for col in numeric_cols:
    if col not in df.columns:
        df[col] = 0
    df[col] = df[col].fillna(0)

def normalize(series):
    if series.max() == series.min():
        return 0
    return (series - series.min()) / (series.max() - series.min())

df["Age Score"] = normalize(df["Age (Years)"])
df["Fault Score"] = normalize(df["Fault Count"])
df["Downtime Score"] = normalize(df["Total Unplanned Downtime"])
df["Cost Score"] = normalize(df["Total Cost of Ownership"])
df["Unplanned Downtime (D:H:M)"] = df["Total Unplanned Downtime"].apply(minutes_to_dhm)

# -----------------------------
# Sidebar Controls
# -----------------------------
st.sidebar.header("Planning Controls")

budget = st.sidebar.number_input("Replacement Budget ($)", min_value=0.0, value=5_000_000.0, step=100_000.0)

st.sidebar.subheader("Priority Weighting")
w_age = st.sidebar.slider("Age Weight", 0.0, 1.0, 0.35)
w_fault = st.sidebar.slider("Fault Weight", 0.0, 1.0, 0.25)
w_down = st.sidebar.slider("Downtime Weight", 0.0, 1.0, 0.25)
w_cost = st.sidebar.slider("Cost Weight", 0.0, 1.0, 0.15)

# Normalize weights
weight_sum = w_age + w_fault + w_down + w_cost
w_age, w_fault, w_down, w_cost = [w/weight_sum for w in [w_age, w_fault, w_down, w_cost]]

# -----------------------------
# Filters
# -----------------------------
st.sidebar.subheader("Filters")

manufacturer = st.sidebar.multiselect("Manufacturer", sorted(df["Asset Manufacturer"].dropna().unique()))
modality = st.sidebar.multiselect("Modality", sorted(df["Modality"].dropna().unique()))
site = st.sidebar.multiselect("Site", sorted(df["Site"].dropna().unique()))

if manufacturer:
    df = df[df["Asset Manufacturer"].isin(manufacturer)]
if modality:
    df = df[df["Modality"].isin(modality)]
if site:
    df = df[df["Site"].isin(site)]
    
priority_filter = st.sidebar.multiselect(
    "Priority Status",
    ["Urgent", "Due for Replacement", "Good"],
    default=["Urgent", "Due for Replacement", "Good"]
)

df = df[df["Priority Status"].isin(priority_filter)]

# -----------------------------
# Priority Score
# -----------------------------
df["Replacement Priority Score"] = (
    w_age * df["Age Score"] +
    w_fault * df["Fault Score"] +
    w_down * df["Downtime Score"] +
    w_cost * df["Cost Score"]
)

df = df.sort_values("Replacement Priority Score", ascending=False)
def priority_status(score):
    if score >= 0.70:
        return "Urgent"
    elif score >= 0.40:
        return "Due for Replacement"
    else:
        return "Good"

df["Priority Status"] = df["Replacement Priority Score"].apply(priority_status)

# -----------------------------
# Budget Simulation
# -----------------------------
df["Estimated Replacement Cost"] = np.where(
    df["Acquisition Cost"].fillna(0) > 0,
    df["Acquisition Cost"],
    df["Total Cost of Ownership"].fillna(0) * 1.2
)

df["Estimated Replacement Cost ($)"] = df["Estimated Replacement Cost"].apply(
    lambda x: f"${x:,.0f}"
)

df["Cumulative Cost"] = df["Estimated Replacement Cost"].cumsum()
df["Within Budget"] = df["Cumulative Cost"] <= budget

# -----------------------------
# KPIs
# -----------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Assets Analyzed", len(df))
col2.metric("Assets Within Budget", df["Within Budget"].sum())
col3.metric("Budget Used", f"${df[df['Within Budget']]['Estimated Replacement Cost'].sum():,.0f}")
col4.metric("Avg Priority Score", f"{df['Replacement Priority Score'].mean():.2f}")

# -----------------------------
# Data Table
# -----------------------------
st.subheader("Replacement Prioritization Table")

display_cols = [
    "Control Number",
    "Asset Manufacturer",
    "Model Name",
    "Modality",
    "Age (Years)",
    "Fault Count",
    "Unplanned Downtime (D:H:M)",
    "Estimated Replacement Cost ($)",
    "Replacement Priority Score",
    "Priority Status",
    "Within Budget"
]

def color_priority(val):
    if val == "Urgent":
        return "background-color: #ffcccc; color: #990000; font-weight: bold"
    elif val == "Due for Replacement":
        return "background-color: #fff0cc; color: #a65c00; font-weight: bold"
    else:
        return "background-color: #e6ffe6; color: #006600"

styled_df = df[display_cols + [
    "Priority Status",
    "Unplanned Downtime (D:H:M)",
    "Estimated Replacement Cost ($)"
]].style.applymap(color_priority, subset=["Priority Status"])

st.dataframe(styled_df, use_container_width=True, height=600)

# -----------------------------
# Download
# -----------------------------
st.download_button(
    "Download Replacement Plan (Excel)",
    data=df.to_excel(index=False),
    file_name="clinical_engineering_replacement_plan.xlsx"
)

st.success("Dashboard ready. Adjust filters, weights, and budget to build scenarios.")
