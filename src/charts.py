import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from config import BUCKET_ORDER

CHANNEL_COLORS = {
    "Expedia":           "#FF6B35",
    "Hotels.com":        "#E84393",
    "No Rate Code":      "#9B9B9B",
    "Agoda":             "#00A651",
    "Booking.com":       "#003580",
    "Property Direct":   "#7B2D8B",
    "Wholesale/FIT":     "#F5A623",
    "Airbnb/Travelport": "#FF5A5F",
    "IHG / Synxis":      "#1C4E80",
    "Other":             "#CCCCCC",
}


def lead_time_bar(lead_df: pd.DataFrame) -> go.Figure:
    df = lead_df[lead_df["Booking Window"] != "TOTAL"].copy()
    df = df.iloc[::-1]

    colors = []
    for bw in df["Booking Window"]:
        if "Same Day" in bw or "1–7" in bw:
            colors.append("#e05c5c")
        elif "31–60" in bw:
            colors.append("#5ca8e0")
        elif "91–" in bw or "180+" in bw:
            colors.append("#8ecb8e")
        else:
            colors.append("#b0b8c8")

    fig = go.Figure(go.Bar(
        x=df["# Cancellations"],
        y=df["Booking Window"],
        orientation="h",
        marker_color=colors,
        text=df["% of Total"],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>%{x} cancellations<extra></extra>",
    ))
    fig.update_layout(
        title="Cancellation Lead Time Distribution",
        xaxis_title="# Cancellations",
        yaxis_title=None,
        height=380,
        margin=dict(l=10, r=70, t=40, b=30),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#eeeeee")
    return fig


def channel_bar(channel_df: pd.DataFrame) -> go.Figure:
    df = channel_df.copy().sort_values("# CXLs")
    colors = [CHANNEL_COLORS.get(ch, "#CCCCCC") for ch in df["Channel"]]

    fig = go.Figure(go.Bar(
        x=df["# CXLs"],
        y=df["Channel"],
        orientation="h",
        marker_color=colors,
        text=df["% Total"],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>%{x} cancellations<extra></extra>",
    ))
    fig.update_layout(
        title="Cancellations by Channel",
        xaxis_title="# Cancellations",
        yaxis_title=None,
        height=340,
        margin=dict(l=10, r=70, t=40, b=30),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#eeeeee")
    return fig


def monthly_trend_line(monthly_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=monthly_df["Cancel Month"],
        y=monthly_df["# CXLs"],
        name="Cancellations",
        mode="lines+markers+text",
        text=monthly_df["# CXLs"],
        textposition="top center",
        marker=dict(size=7, color="#5ca8e0"),
        line=dict(color="#5ca8e0", width=2),
        hovertemplate="<b>%{x}</b><br>%{y} cancellations<extra></extra>",
        yaxis="y1",
    ))

    fig.add_trace(go.Scatter(
        x=monthly_df["Cancel Month"],
        y=monthly_df["Nights"],
        name="Nights Lost",
        mode="lines+markers",
        marker=dict(size=6, color="#e05c5c", symbol="diamond"),
        line=dict(color="#e05c5c", width=1.5, dash="dot"),
        hovertemplate="<b>%{x}</b><br>%{y} nights lost<extra></extra>",
        yaxis="y2",
    ))

    fig.update_layout(
        title="Monthly Cancellation Trend",
        xaxis_title=None,
        yaxis=dict(title="# Cancellations", showgrid=True, gridcolor="#eeeeee"),
        yaxis2=dict(title="Nights Lost", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=320,
        margin=dict(l=10, r=60, t=50, b=30),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return fig


def last_minute_trend(monthly_df: pd.DataFrame) -> go.Figure:
    """Stacked bar: same-day / 1-7d / 90+d cancellations by month."""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=monthly_df["Cancel Month"],
        y=monthly_df["Same-Day"],
        name="Same Day",
        marker_color="#c0392b",
        hovertemplate="<b>%{x}</b><br>Same Day: %{y}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=monthly_df["Cancel Month"],
        y=monthly_df["1–7d"],
        name="1–7 days",
        marker_color="#e67e22",
        hovertemplate="<b>%{x}</b><br>1–7 days: %{y}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=monthly_df["Cancel Month"],
        y=monthly_df["90+d"],
        name="90+ days (Advanced)",
        marker_color="#8ecb8e",
        hovertemplate="<b>%{x}</b><br>90+ days: %{y}<extra></extra>",
    ))

    fig.update_layout(
        barmode="stack",
        title="Last-Minute vs Advanced Cancellations by Month",
        xaxis_title=None,
        yaxis_title="# Cancellations",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=320,
        margin=dict(l=10, r=20, t=50, b=30),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    fig.update_yaxes(showgrid=True, gridcolor="#eeeeee")
    return fig


def cumulative_lead_time(lead_df: pd.DataFrame) -> go.Figure:
    df = lead_df[lead_df["Booking Window"] != "TOTAL"].copy()
    df["cumul_num"] = df["Cumul. %"].str.replace("%", "").astype(float)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Booking Window"],
        y=df["cumul_num"],
        mode="lines+markers",
        fill="tozeroy",
        fillcolor="rgba(92,168,224,0.15)",
        line=dict(color="#5ca8e0", width=2),
        marker=dict(size=7),
        text=[f"{v:.1f}%" for v in df["cumul_num"]],
        textposition="top center",
        hovertemplate="<b>%{x}</b><br>Cumulative: %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        title="Cumulative Cancellation %",
        xaxis_title="Lead Time Bucket",
        yaxis_title="Cumulative %",
        yaxis=dict(range=[0, 110], ticksuffix="%"),
        height=300,
        margin=dict(l=10, r=20, t=40, b=60),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    fig.update_xaxes(tickangle=-30)
    fig.update_yaxes(showgrid=True, gridcolor="#eeeeee")
    return fig
