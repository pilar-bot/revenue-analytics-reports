import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd

from src.loader import load_file
from src.store import has_stored_data, load_stored, merge_and_save, get_upload_log, delete_upload
from src.processor import (
    process,
    kpi_summary,
    lead_time_table,
    channel_summary_table,
    channel_bucket_crosstab,
    channel_bucket_pct_crosstab,
    rate_code_detail,
    room_type_table,
    monthly_detail_table,
    channel_month_crosstab,
    statistical_summary,
    checkin_month_table,
    insights_findings,
)
from src.charts import (
    lead_time_bar,
    channel_bar,
    monthly_trend_line,
    last_minute_trend,
    cumulative_lead_time,
)

st.set_page_config(
    page_title="Cancellation Report",
    page_icon="📊",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("📊 Cancellation Report")
    st.caption("Revenue Analytics — LIGHTSON")
    st.divider()

    property_name = st.text_input("Property name", value="Skyline at Island Colony")
    st.divider()

    uploaded = st.file_uploader(
        "Add / update data (RoomMaster export)",
        type=["csv", "xlsx", "xls"],
        help="Upload a new export to merge with existing data. Duplicates are removed automatically.",
    )

    upload_log = get_upload_log()
    if upload_log:
        with st.expander(f"📂 Upload history ({len(upload_log)} uploads)", expanded=False):
            for entry in reversed(upload_log):
                col_info, col_btn = st.columns([4, 1])
                col_info.markdown(
                    f"**{entry['filename']}**  \n"
                    f"{entry['uploaded_at']} · +{entry['records_added']:,} records"
                )
                if col_btn.button("🗑️", key=f"del_{entry['id']}", help="Delete this upload"):
                    delete_upload(entry["id"])
                    st.rerun()

    exclude_bar = st.toggle("Exclude BAR rate codes", value=True)

    st.divider()
    st.caption("Filters applied after upload")
    date_filter_start = None
    date_filter_end = None
    channel_filter = []

# ---------------------------------------------------------------------------
# Load & process data
# ---------------------------------------------------------------------------
if uploaded is not None:
    try:
        new_raw = load_file(uploaded)
    except ValueError as e:
        st.error(str(e))
        st.stop()

    merged_raw, added, total = merge_and_save(new_raw, uploaded.name)
    st.sidebar.success(f"+{added:,} new records merged ({total:,} total)")
    raw_df = merged_raw

elif has_stored_data():
    raw_df = load_stored()

else:
    st.markdown("## Cancellation Analysis")
    st.info("Upload a RoomMaster export from the sidebar to get started.")
    st.stop()

try:
    df = process(raw_df, exclude_bar=exclude_bar)
except Exception as e:
    st.error(f"Error processing data: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar filters (populated after data loads)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.subheader("Date Range")
    min_date = df["cancel_date"].min().date()
    max_date = df["cancel_date"].max().date()
    date_filter_start = st.date_input("From", value=min_date, min_value=min_date, max_value=max_date)
    date_filter_end = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date)

    st.subheader("Channels")
    all_channels = sorted(df["channel"].unique().tolist())
    channel_filter = st.multiselect("Show channels", options=all_channels, default=all_channels)

# Apply filters
mask = (
    (df["cancel_date"].dt.date >= date_filter_start) &
    (df["cancel_date"].dt.date <= date_filter_end) &
    (df["channel"].isin(channel_filter))
)
df = df[mask].copy()

if df.empty:
    st.warning("No records match the current filters.")
    st.stop()

# ---------------------------------------------------------------------------
# Shared period label
# ---------------------------------------------------------------------------
period_label = (
    f"{date_filter_start.strftime('%b %d, %Y')} – {date_filter_end.strftime('%b %d, %Y')}"
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_insights, tab_dash, tab_lt, tab_ch, tab_rm, tab_raw = st.tabs([
    "Insights", "Dashboard", "Lead Time Analysis", "Channel Analysis", "Room Type & Monthly", "Raw Data"
])

# ── Tab 1: Insights ───────────────────────────────────────────────────────
with tab_insights:
    kpi = kpi_summary(df)
    bar_note = "BAR excluded" if exclude_bar else "BAR included"

    st.markdown(f"### {property_name}  —  Cancellation Analysis  |  Executive Summary")
    st.caption(
        f"Data period: {period_label}  |  {kpi['total_cxl']:,} cancellations  |  "
        f"{kpi['total_nights']:,} room nights  |  {bar_note}"
    )

    findings = insights_findings(df)

    def render_findings_table(rows: list, key: str):
        if not rows:
            st.info("Not enough data to generate findings.")
            return
        fdf = pd.DataFrame(rows)

        def highlight_implication(row):
            return ["", "", "background-color: #f0f4ff"] * 1 if False else [""] * len(row)

        st.dataframe(
            fdf.style.set_properties(
                subset=["Revenue / Action Implication"],
                **{"font-style": "italic", "color": "#1a4a7a"}
            ),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Finding": st.column_config.TextColumn("Finding", width="medium"),
                "Detail": st.column_config.TextColumn("Detail", width="medium"),
                "Revenue / Action Implication": st.column_config.TextColumn(
                    "Revenue / Action Implication", width="large"
                ),
            },
        )

    st.markdown("#### 🔑 Top Findings — Cancellation Behavior")
    render_findings_table(findings["behavior"], "behavior")

    st.markdown("#### 📅 Lead Time Breakdown")
    render_findings_table(findings["lead_time"], "lead_time")

    st.markdown("#### 🏠 Room Type & Seasonal Patterns")
    render_findings_table(findings["room_seasonal"], "room_seasonal")

# ── Tab 2: Dashboard ──────────────────────────────────────────────────────
with tab_dash:
    kpi = kpi_summary(df)
    bar_note = "BAR excluded" if exclude_bar else "BAR included"

    st.markdown(f"### {property_name}  |  Cancellation Analysis  |  {period_label}")
    st.caption(
        f"{bar_note}  |  Channels mapped by first 2 letters of rate code  |  "
        f"Total cancellations analyzed: {kpi['total_cxl']:,}  |  Total room nights lost: {kpi['total_nights']:,}"
    )

    # KPI cards row 1
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Cancellations", f"{kpi['total_cxl']:,}")
    c2.metric("Room Nights Lost", f"{kpi['total_nights']:,}")
    c3.metric("Median Days to Check-In", f"{kpi['median_days']}d")
    c4.metric("Top Channel", f"{kpi['top_channel']} ({kpi['top_channel_pct']}%)")

    avg_nights = round(df["nights"].mean(), 1) if len(df) else 0
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Last-Minute ≤7d", f"{kpi['last_min_count']:,}", f"{kpi['last_min_pct']}% of total")
    c6.metric("Advanced 90+d", f"{kpi['advanced_count']:,}", f"{kpi['advanced_pct']}% of total")
    c7.metric("No Rate Code", f"{kpi['no_rate_count']:,}", f"Median {kpi['no_rate_median_days']}d")
    c8.metric("Avg Nights / CXL", f"{avg_nights}")

    st.divider()

    # ── Charts (primary view) ──────────────────────────────────────────────
    lt_df = lead_time_table(df)
    ch_df = channel_summary_table(df)
    mo_df = monthly_detail_table(df)

    col_l, col_r = st.columns(2)
    with col_l:
        st.plotly_chart(lead_time_bar(lt_df), use_container_width=True)
    with col_r:
        st.plotly_chart(channel_bar(ch_df), use_container_width=True)

    col_l2, col_r2 = st.columns(2)
    with col_l2:
        st.plotly_chart(monthly_trend_line(mo_df), use_container_width=True)
    with col_r2:
        st.plotly_chart(last_minute_trend(mo_df), use_container_width=True)

    # ── Summary tables (detail, collapsed by default) ──────────────────────
    with st.expander("📋 Summary tables", expanded=False):
        col_tl, col_tr = st.columns(2)
        with col_tl:
            st.markdown("**Cancellation Lead Time Distribution**")
            st.dataframe(
                lt_df[["Booking Window", "# Cancellations", "% of Total", "Room Nights"]],
                use_container_width=True, hide_index=True,
            )
        with col_tr:
            st.markdown("**Cancellations by Channel**")
            st.dataframe(
                ch_df[["Channel", "# CXLs", "% Total", "Nights", "Med Days", "Avg Days"]],
                use_container_width=True, hide_index=True,
            )

# ── Tab 3: Lead Time Analysis ─────────────────────────────────────────────
with tab_lt:
    kpi = kpi_summary(df)
    st.markdown(f"### {property_name}  |  Cancellation Lead Time Analysis")
    st.caption(
        f"Total: {kpi['total_cxl']:,} cancellations | {kpi['total_nights']:,} room nights | "
        f"Median {kpi['median_days']} days before check-in | Mean {int(df['days_to_ci'].mean())} days"
    )

    # A. Distribution table
    st.markdown("#### A. Overall Cancellation Lead Time Distribution")
    lt_df = lead_time_table(df)

    def highlight_signal(row):
        s = row.get("Signal", "")
        if "Last-Minute" in s:
            return ["background-color: #fde8e8"] * len(row)
        if "Peak" in s:
            return ["background-color: #e8f4fb"] * len(row)
        if "Advanced" in s:
            return ["background-color: #edf7ed"] * len(row)
        if row["Booking Window"] == "TOTAL":
            return ["font-weight: bold; background-color: #f5f5f5"] * len(row)
        return [""] * len(row)

    styled = lt_df.style.apply(highlight_signal, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.divider()
    st.plotly_chart(cumulative_lead_time(lt_df), use_container_width=True)

    # B. Statistical Summary
    st.markdown("#### B. Statistical Summary — Days from Cancellation to Check-In")
    stats = statistical_summary(df)
    stat_rows = [
        {"Statistic": "Minimum (earliest same-day)", "Value": stats["min"], "Note": "days"},
        {"Statistic": "25th Percentile", "Value": stats["p25"], "Note": "days"},
        {"Statistic": "Median (50th Pct)", "Value": stats["median"], "Note": "days — half cancel within this window"},
        {"Statistic": "Mean (Average)", "Value": stats["mean"], "Note": "days"},
        {"Statistic": "75th Percentile", "Value": stats["p75"], "Note": "days"},
        {"Statistic": "90th Percentile", "Value": stats["p90"], "Note": "days"},
        {"Statistic": "Maximum", "Value": stats["max"], "Note": "days (furthest advance cancel)"},
        {"Statistic": "Std Deviation", "Value": stats["std"], "Note": "days"},
        {"Statistic": "Last-Minute ≤7d", "Value": stats["last_min_count"], "Note": f"cancellations ({stats['last_min_pct']}%)"},
        {"Statistic": "Advanced ≥90d", "Value": stats["advanced_count"], "Note": f"cancellations ({stats['advanced_pct']}%)"},
    ]
    st.dataframe(pd.DataFrame(stat_rows), use_container_width=True, hide_index=True)

    # C. By Check-In Month
    st.markdown("#### C. Cancellations by Intended Check-In Month (demand lost per stay period)")
    ci_df = checkin_month_table(df)
    st.dataframe(ci_df, use_container_width=True, hide_index=True)

# ── Tab 4: Channel Analysis ───────────────────────────────────────────────
with tab_ch:
    st.markdown(f"### {property_name}  |  Cancellations by Channel & Lead Time")
    st.caption(
        "Rate code prefix mapping: EX=Expedia | HB/HI/HP/HT=Hotels.com | AG=Agoda | "
        "BK/BO=Booking.com | AT=Airbnb/Travelport | D*=Property Direct | "
        "NW/TF/WB=Wholesale | IH=IHG/Synxis | No Code=blank rate"
    )

    # A. Channel Summary
    st.markdown("#### A. Channel Summary — Volume, Nights, Lead Time Behavior")
    ch_df = channel_summary_table(df)
    st.dataframe(ch_df, use_container_width=True, hide_index=True)

    # B. Channel × Booking Window Cross-Tab (count)
    st.markdown("#### B. Channel × Booking Window Cross-Tab (count)")
    ct = channel_bucket_crosstab(df)

    def color_scale(val):
        try:
            v = float(val)
            if v == 0:
                return ""
            intensity = min(v / 200, 1.0)
            return f"background-color: rgba({255-int(intensity*80)},{255-int(intensity*50)},{255},0.6)"
        except Exception:
            return ""

    st.dataframe(ct.style.map(color_scale), use_container_width=True)

    # C. % Distribution within each channel
    st.markdown("#### C. Channel × Booking Window — % Distribution Within Channel")
    pct_ct = channel_bucket_pct_crosstab(df)

    def color_pct(val):
        try:
            v = float(val)
            if v == 0:
                return ""
            intensity = min(v / 50, 1.0)
            return f"background-color: rgba(100,149,{255-int(intensity*100)},{0.2 + intensity*0.5})"
        except Exception:
            return ""

    st.dataframe(
        pct_ct.style.map(color_pct).format("{:.1f}%"),
        use_container_width=True,
    )

    # D. Rate Code Detail
    st.markdown("#### D. Rate Code Detail")
    rc_df = rate_code_detail(df)
    st.dataframe(rc_df, use_container_width=True, hide_index=True)

# ── Tab 5: Room Type & Monthly ────────────────────────────────────────────
with tab_rm:
    st.markdown(f"### {property_name}  |  Room Type & Monthly Detail")

    # A. Room Type Summary
    st.markdown("#### A. Room Type Summary")
    rt_df = room_type_table(df)
    st.dataframe(rt_df, use_container_width=True, hide_index=True)

    # B. Monthly Cancellation Detail
    st.markdown("#### B. Monthly Cancellation Detail — By Cancel Date")
    mo_df = monthly_detail_table(df)
    st.dataframe(mo_df, use_container_width=True, hide_index=True)

    # C. Channel × Month Matrix
    st.markdown("#### C. Cancel Month × Channel (count of cancellations per channel per month)")
    cm_df = channel_month_crosstab(df)
    st.dataframe(cm_df, use_container_width=True)

# ── Tab 6: Raw Data ───────────────────────────────────────────────────────
with tab_raw:
    bar_note = "BAR excluded" if exclude_bar else "BAR included"
    st.markdown(f"### {property_name}  —  Cancellation Raw Data")
    st.caption(f"{len(df):,} records  |  {bar_note}  |  {period_label}")

    display_df = df[[
        "conf_num", "name", "room_type", "nights",
        "checkin", "cancel_date", "days_to_ci",
        "rate_code", "channel", "bucket", "cancelled_by",
    ]].copy()

    display_df.columns = [
        "Conf #", "Name", "Room Type", "Nights",
        "Check-In", "Cancel Date", "Days to CI",
        "Rate Code", "Channel", "Lead Time Bucket", "Cancelled By",
    ]

    display_df["Check-In"] = display_df["Check-In"].dt.strftime("%m/%d/%Y")
    display_df["Cancel Date"] = display_df["Cancel Date"].dt.strftime("%m/%d/%Y")

    st.dataframe(display_df, use_container_width=True, hide_index=True)
