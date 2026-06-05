import pandas as pd
from config import CHANNEL_MAP, LEAD_TIME_BUCKETS, BAR_PREFIXES


def process(df: pd.DataFrame, exclude_bar: bool = True) -> pd.DataFrame:
    """
    Takes the raw renamed DataFrame from loader and returns a clean,
    enriched DataFrame ready for all report tabs.
    """
    df = df.copy()

    # Parse dates
    df["checkin"] = pd.to_datetime(df["checkin"], errors="coerce")
    df["cancel_date"] = pd.to_datetime(df["cancel_date"], errors="coerce")

    # Parse numeric
    df["nights"] = pd.to_numeric(df["nights"], errors="coerce").fillna(0).astype(int)

    # Clean rate code
    df["rate_code"] = df["rate_code"].fillna("").str.strip()

    # Exclude BAR rate codes
    if exclude_bar:
        bar_mask = df["rate_code"].str.upper().apply(
            lambda rc: any(rc.startswith(p.upper()) for p in BAR_PREFIXES)
        )
        df = df[~bar_mask].copy()

    # Drop rows where either date is missing
    df = df.dropna(subset=["checkin", "cancel_date"]).copy()

    # Days to check-in (can be negative if cancelled after arrival — treat as 0)
    df["days_to_ci"] = (df["checkin"] - df["cancel_date"]).dt.days.clip(lower=0)

    # Channel from rate code prefix
    df["channel"] = df["rate_code"].apply(_map_channel)

    # Lead time bucket
    df["bucket"] = df["days_to_ci"].apply(_assign_bucket)

    # Cancel month label for monthly trend (e.g. "Sep 2025")
    df["cancel_month"] = df["cancel_date"].dt.to_period("M")
    df["cancel_month_label"] = df["cancel_date"].dt.strftime("%b %Y")

    return df.reset_index(drop=True)


def _map_channel(rate_code: str) -> str:
    if not rate_code:
        return "No Rate Code"
    prefix2 = rate_code[:2].upper()
    prefix1 = rate_code[:1].upper()
    if prefix2 in CHANNEL_MAP:
        return CHANNEL_MAP[prefix2]
    if prefix1 in CHANNEL_MAP:
        return CHANNEL_MAP[prefix1]
    return "Other"


def _assign_bucket(days: int) -> str:
    for lo, hi, label in LEAD_TIME_BUCKETS:
        if lo <= days <= hi:
            return label
    return "180+ days"


# ---------------------------------------------------------------------------
# Aggregation helpers used by multiple tabs
# ---------------------------------------------------------------------------

def kpi_summary(df: pd.DataFrame) -> dict:
    total_cxl = len(df)
    total_nights = df["nights"].sum()
    median_days = int(df["days_to_ci"].median()) if total_cxl else 0
    last_min = df[df["days_to_ci"] <= 7]
    advanced = df[df["days_to_ci"] >= 90]
    no_rate = df[df["channel"] == "No Rate Code"]
    top_ch = df["channel"].value_counts()
    top_channel_name = top_ch.index[0] if len(top_ch) else "—"
    top_channel_pct = round(top_ch.iloc[0] / total_cxl * 100, 1) if total_cxl else 0

    return {
        "total_cxl": total_cxl,
        "total_nights": int(total_nights),
        "median_days": median_days,
        "last_min_count": len(last_min),
        "last_min_pct": round(len(last_min) / total_cxl * 100, 1) if total_cxl else 0,
        "advanced_count": len(advanced),
        "advanced_pct": round(len(advanced) / total_cxl * 100, 1) if total_cxl else 0,
        "top_channel": top_channel_name,
        "top_channel_pct": top_channel_pct,
        "no_rate_count": len(no_rate),
        "no_rate_median_days": int(no_rate["days_to_ci"].median()) if len(no_rate) else 0,
    }


def lead_time_table(df: pd.DataFrame) -> pd.DataFrame:
    from config import BUCKET_ORDER, BUCKET_SIGNALS
    total = len(df)
    rows = []
    cumul = 0
    for bucket in BUCKET_ORDER:
        sub = df[df["bucket"] == bucket]
        count = len(sub)
        nights = sub["nights"].sum()
        avg_nights = round(nights / count, 1) if count else 0
        cumul += count
        rows.append({
            "Booking Window": bucket,
            "# Cancellations": count,
            "% of Total": f"{count/total*100:.1f}%" if total else "0%",
            "Room Nights": int(nights),
            "% of Nights": f"{nights/df['nights'].sum()*100:.1f}%" if df['nights'].sum() else "0%",
            "Avg Nights/Res": avg_nights,
            "Cumul. CXLs": cumul,
            "Cumul. %": f"{cumul/total*100:.1f}%" if total else "0%",
            "Signal": BUCKET_SIGNALS.get(bucket, ""),
        })
    rows.append({
        "Booking Window": "TOTAL",
        "# Cancellations": total,
        "% of Total": "100.0%",
        "Room Nights": int(df["nights"].sum()),
        "% of Nights": "100.0%",
        "Avg Nights/Res": round(df["nights"].mean(), 1) if total else 0,
        "Cumul. CXLs": total,
        "Cumul. %": "100.0%",
        "Signal": "",
    })
    return pd.DataFrame(rows)


def channel_summary_table(df: pd.DataFrame) -> pd.DataFrame:
    from config import CHANNEL_ORDER
    total = len(df)
    rows = []
    channels = df["channel"].value_counts().index.tolist()
    # Respect preferred order, then any extras
    ordered = [c for c in CHANNEL_ORDER if c in channels] + [c for c in channels if c not in CHANNEL_ORDER]
    for ch in ordered:
        sub = df[df["channel"] == ch]
        count = len(sub)
        nights = sub["nights"].sum()
        med = int(sub["days_to_ci"].median()) if count else 0
        avg = int(sub["days_to_ci"].mean()) if count else 0
        same_day = len(sub[sub["days_to_ci"] == 0])
        last_min = len(sub[sub["days_to_ci"] <= 7])
        adv = len(sub[sub["days_to_ci"] >= 90])
        rows.append({
            "Channel": ch,
            "# CXLs": count,
            "% Total": f"{count/total*100:.1f}%",
            "Nights": int(nights),
            "Med Days": med,
            "Avg Days": avg,
            "Same-Day": same_day,
            "Last-Min ≤7d": last_min,
            "Last-Min %": f"{last_min/count*100:.1f}%" if count else "0%",
            "Adv 90+d": adv,
            "Adv 90+ %": f"{adv/count*100:.1f}%" if count else "0%",
        })
    return pd.DataFrame(rows)


def channel_bucket_crosstab(df: pd.DataFrame) -> pd.DataFrame:
    from config import BUCKET_ORDER, CHANNEL_ORDER
    ct = pd.crosstab(df["channel"], df["bucket"])
    # Ensure all bucket columns exist
    for b in BUCKET_ORDER:
        if b not in ct.columns:
            ct[b] = 0
    ct = ct[BUCKET_ORDER]
    ct["TOTAL"] = ct.sum(axis=1)
    # Row order
    channels = [c for c in CHANNEL_ORDER if c in ct.index] + [c for c in ct.index if c not in CHANNEL_ORDER]
    ct = ct.loc[channels]
    totals = ct.sum(axis=0).rename("TOTAL")
    ct = pd.concat([ct, totals.to_frame().T])
    return ct


def rate_code_detail(df: pd.DataFrame) -> pd.DataFrame:
    total = len(df)
    rows = []
    for (rc, ch), sub in df.groupby(["rate_code", "channel"]):
        count = len(sub)
        channel_count = len(df[df["channel"] == ch])
        rows.append({
            "Rate Code": rc if rc else "(blank)",
            "Channel": ch,
            "# CXLs": count,
            "Nights": int(sub["nights"].sum()),
            "Med Days": int(sub["days_to_ci"].median()) if count else 0,
            "Avg Days": int(sub["days_to_ci"].mean()) if count else 0,
            "% of Channel": f"{count/channel_count*100:.1f}%" if channel_count else "0%",
        })
    return pd.DataFrame(rows).sort_values(["Channel", "# CXLs"], ascending=[True, False]).reset_index(drop=True)


def room_type_table(df: pd.DataFrame) -> pd.DataFrame:
    from config import ROOM_TYPE_NAMES
    total = len(df)
    rows = []
    for rt, sub in df.groupby("room_type"):
        count = len(sub)
        rows.append({
            "Room Type": ROOM_TYPE_NAMES.get(rt, rt),
            "Code": rt,
            "# CXLs": count,
            "% Total": f"{count/total*100:.1f}%",
            "Nights": int(sub["nights"].sum()),
            "Med Days": int(sub["days_to_ci"].median()) if count else 0,
            "Avg Days": int(sub["days_to_ci"].mean()) if count else 0,
            "Last-Min ≤7d": len(sub[sub["days_to_ci"] <= 7]),
            "Adv 90+d": len(sub[sub["days_to_ci"] >= 90]),
        })
    return pd.DataFrame(rows).sort_values("# CXLs", ascending=False).reset_index(drop=True)


def monthly_detail_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for period, sub in df.groupby("cancel_month"):
        count = len(sub)
        rows.append({
            "Cancel Month": sub["cancel_month_label"].iloc[0],
            "_period": period,
            "# CXLs": count,
            "Nights": int(sub["nights"].sum()),
            "Med Days": int(sub["days_to_ci"].median()) if count else 0,
            "Avg Days": int(sub["days_to_ci"].mean()) if count else 0,
            "Same-Day": len(sub[sub["days_to_ci"] == 0]),
            "1–7d": len(sub[(sub["days_to_ci"] >= 1) & (sub["days_to_ci"] <= 7)]),
            "8–30d": len(sub[(sub["days_to_ci"] >= 8) & (sub["days_to_ci"] <= 30)]),
            "31–90d": len(sub[(sub["days_to_ci"] >= 31) & (sub["days_to_ci"] <= 90)]),
            "90+d": len(sub[sub["days_to_ci"] > 90]),
        })
    return pd.DataFrame(rows).sort_values("_period").drop(columns="_period").reset_index(drop=True)


def statistical_summary(df: pd.DataFrame) -> dict:
    days = df["days_to_ci"]
    total = len(df)
    last_min = len(df[df["days_to_ci"] <= 7])
    advanced = len(df[df["days_to_ci"] >= 90])
    return {
        "min": int(days.min()),
        "p25": int(days.quantile(0.25)),
        "median": int(days.median()),
        "mean": int(days.mean()),
        "p75": int(days.quantile(0.75)),
        "p90": int(days.quantile(0.90)),
        "max": int(days.max()),
        "std": int(days.std()),
        "last_min_count": last_min,
        "last_min_pct": round(last_min / total * 100, 1) if total else 0,
        "advanced_count": advanced,
        "advanced_pct": round(advanced / total * 100, 1) if total else 0,
    }


def checkin_month_table(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["checkin_month"] = df["checkin"].dt.to_period("M")
    df["checkin_month_label"] = df["checkin"].dt.strftime("%b %Y")
    total = len(df)
    rows = []
    for period, sub in df.groupby("checkin_month"):
        count = len(sub)
        nights = int(sub["nights"].sum())
        last_min = len(sub[sub["days_to_ci"] <= 7])
        advanced = len(sub[sub["days_to_ci"] >= 90])
        rows.append({
            "Check-In Month": sub["checkin_month_label"].iloc[0],
            "_period": period,
            "# CXLs": count,
            "Nights Lost": nights,
            "Med Days": int(sub["days_to_ci"].median()) if count else 0,
            "Avg Days": int(sub["days_to_ci"].mean()) if count else 0,
            "% of Total": f"{count/total*100:.1f}%" if total else "0%",
            "Last-Min (≤7d)": last_min,
            "Last-Min %": f"{last_min/count*100:.1f}%" if count else "0%",
            "Adv (90+d)": advanced,
            "Adv %": f"{advanced/count*100:.1f}%" if count else "0%",
        })
    return pd.DataFrame(rows).sort_values("_period").drop(columns="_period").reset_index(drop=True)


def channel_bucket_pct_crosstab(df: pd.DataFrame) -> pd.DataFrame:
    from config import BUCKET_ORDER, CHANNEL_ORDER
    ct = pd.crosstab(df["channel"], df["bucket"])
    for b in BUCKET_ORDER:
        if b not in ct.columns:
            ct[b] = 0
    ct = ct[BUCKET_ORDER]
    ct_pct = ct.div(ct.sum(axis=1), axis=0).mul(100).round(1)
    channels = [c for c in CHANNEL_ORDER if c in ct_pct.index] + [c for c in ct_pct.index if c not in CHANNEL_ORDER]
    return ct_pct.loc[channels]


def insights_findings(df: pd.DataFrame) -> dict:
    from config import ROOM_TYPE_NAMES, OTA_CHANNELS
    total = len(df)
    if total == 0:
        return {"behavior": [], "lead_time": [], "room_seasonal": []}

    ch_counts = df["channel"].value_counts()

    # ── Section 1: Cancellation Behavior ─────────────────────────────────────
    behavior = []

    top_ch = ch_counts.index[0]
    top_ct = int(ch_counts.iloc[0])
    top_pct = round(top_ct / total * 100, 1)
    top_sub = df[df["channel"] == top_ch]
    top_med = int(top_sub["days_to_ci"].median())
    top_lm_pct = round(len(top_sub[top_sub["days_to_ci"] <= 7]) / top_ct * 100, 1)
    behavior.append({
        "Finding": f"{top_ch} dominates at {top_pct}%",
        "Detail": f"{top_ct:,} of {total:,} cancellations | Median {top_med} days lead time | {top_lm_pct}% last-minute (≤7d)",
        "Revenue / Action Implication": "Primary recovery channel but also largest churn driver. Enforce tighter cancellation policies or non-refundable rate incentives.",
    })

    if "No Rate Code" in ch_counts.index:
        nrc = df[df["channel"] == "No Rate Code"]
        nrc_ct = len(nrc)
        nrc_med = int(nrc["days_to_ci"].median())
        nrc_lm_pct = round(len(nrc[nrc["days_to_ci"] <= 7]) / nrc_ct * 100, 1)
        behavior.append({
            "Finding": f"No Rate Code = {round(nrc_ct/total*100,1)}% and overwhelmingly same-day",
            "Detail": f"{nrc_ct:,} records with blank rate code | Median only {nrc_med} days | {nrc_lm_pct}% are last-minute (≤7d)",
            "Revenue / Action Implication": "Likely PMS system cancels, held rooms, or walk-in blocks. Audit and assign rate codes to reduce blind spots in channel analysis.",
        })

    others = [c for c in ch_counts.index if c not in ("No Rate Code", top_ch)]
    if others:
        sec_ch = others[0]
        sec_ct = int(ch_counts[sec_ch])
        sec_sub = df[df["channel"] == sec_ch]
        sec_med = int(sec_sub["days_to_ci"].median())
        sec_lm_pct = round(len(sec_sub[sec_sub["days_to_ci"] <= 7]) / sec_ct * 100, 1)
        ota_total = sum(int(ch_counts.get(c, 0)) for c in OTA_CHANNELS)
        ota_pct = round(ota_total / total * 100, 1)
        behavior.append({
            "Finding": f"{sec_ch} is {round(sec_ct/total*100,1)}% of cancellations",
            "Detail": f"{sec_ct:,} cancellations | Median {sec_med} days | {sec_lm_pct}% last-minute",
            "Revenue / Action Implication": f"Second largest OTA channel. Combined with {top_ch}, OTAs account for {ota_pct}% of all cancellations. Long lead time suggests advance bookings that don't hold.",
        })

    bucket_counts = df["bucket"].value_counts()
    lb = bucket_counts.index[0]
    lb_ct = int(bucket_counts.iloc[0])
    behavior.append({
        "Finding": f"{lb} window is the single largest bucket",
        "Detail": f"{lb_ct:,} cancellations ({round(lb_ct/total*100,1)}%) cancel in this window before check-in",
        "Revenue / Action Implication": "Likely the OTA free-cancellation window. Implement early-booking incentives to lock in rates outside this window.",
    })

    adv_sub = df[df["bucket"] == "91–180 days"]
    if len(adv_sub) > 0:
        adv_ct = len(adv_sub)
        adv_avg = int(adv_sub["days_to_ci"].mean())
        behavior.append({
            "Finding": "91–180 day window is the largest cumulative block",
            "Detail": f"{adv_ct:,} cancellations ({round(adv_ct/total*100,1)}%) | Avg {adv_avg} days",
            "Revenue / Action Implication": "Revenue recognition risk: bookings placed months out are still cancelling 3–6 months before arrival. Tighten deposit requirements on advance bookings.",
        })

    # ── Section 2: Lead Time Breakdown ───────────────────────────────────────
    lead_time = []

    lm_total = len(df[df["days_to_ci"] <= 7])
    same_day = len(df[df["days_to_ci"] == 0])
    lead_time.append({
        "Finding": f"{round(lm_total/total*100,1)}% cancel within 7 days of check-in",
        "Detail": f"{lm_total:,} cancellations | Same-day alone: {same_day:,} ({round(same_day/total*100,1)}%)",
        "Revenue / Action Implication": "Same-day and last-minute cancellations are a walk-in replacement problem. Ensure OTA inventory refresh within 24–48hrs.",
    })

    med_days = int(df["days_to_ci"].median())
    mean_days = int(df["days_to_ci"].mean())
    lead_time.append({
        "Finding": f"Median: {med_days} days | Mean: {mean_days} days",
        "Detail": f"Roughly {round(med_days/30,1)} months before check-in is the typical cancellation decision point",
        "Revenue / Action Implication": f"Run re-booking campaigns and rate promotions at the {max(1, med_days-15)}–{med_days} day mark to replace cancelled inventory.",
    })

    ch_med = df[df["channel"] != "No Rate Code"].groupby("channel")["days_to_ci"].median().sort_values(ascending=False)
    if len(ch_med) > 0:
        adv_ch = ch_med.index[0]
        adv_ch_sub = df[df["channel"] == adv_ch]
        adv_ch_90_pct = round(len(adv_ch_sub[adv_ch_sub["days_to_ci"] >= 90]) / len(adv_ch_sub) * 100, 0)
        lead_time.append({
            "Finding": f"{adv_ch} has the longest advance cancellations",
            "Detail": f"Median {int(ch_med.iloc[0])} days, {int(adv_ch_90_pct)}% cancel 90+ days out",
            "Revenue / Action Implication": f"{adv_ch} bookings are being held and dropped early. Consider non-refundable deals to capture commitment.",
        })

    ch_lm_rate = {
        ch: len(sub[sub["days_to_ci"] <= 7]) / len(sub)
        for ch, sub in df.groupby("channel") if len(sub) >= 10
    }
    if ch_lm_rate:
        worst_lm_ch = max(ch_lm_rate, key=ch_lm_rate.get)
        worst_lm_pct = round(ch_lm_rate[worst_lm_ch] * 100, 1)
        lead_time.append({
            "Finding": f"{worst_lm_ch} has highest last-minute rate",
            "Detail": f"{worst_lm_pct}% of {worst_lm_ch} cancellations are ≤7 days out",
            "Revenue / Action Implication": f"{worst_lm_ch} guests are highest same-week risk. Consider shorter free-cancellation windows on this channel.",
        })

    # ── Section 3: Room Type & Seasonal ──────────────────────────────────────
    room_seasonal = []

    rt_counts = df["room_type"].value_counts()
    top_rt = rt_counts.index[0]
    top_rt_ct = int(rt_counts.iloc[0])
    top_rt_sub = df[df["room_type"] == top_rt]
    top_rt_name = ROOM_TYPE_NAMES.get(top_rt, top_rt)
    room_seasonal.append({
        "Finding": f"{top_rt_name} ({top_rt}) accounts for {round(top_rt_ct/total*100,1)}% of all cancellations",
        "Detail": f"{top_rt_ct:,} cancellations | {int(top_rt_sub['nights'].sum()):,} nights | Median {int(top_rt_sub['days_to_ci'].median())} days out",
        "Revenue / Action Implication": "Primary volume room type and highest churn risk. Flex pricing on non-refundable rates recommended.",
    })

    rt_med_map = {
        rt: int(sub["days_to_ci"].median())
        for rt, sub in df.groupby("room_type") if len(sub) >= 10 and rt != top_rt
    }
    if rt_med_map:
        late_rts = sorted(rt_med_map.items(), key=lambda x: x[1])[:2]
        late_str = " | ".join([f"{ROOM_TYPE_NAMES.get(rt, rt)} ({rt}) median {med}d" for rt, med in late_rts])
        room_seasonal.append({
            "Finding": "Other room types cancel much closer to arrival",
            "Detail": late_str,
            "Revenue / Action Implication": "These room types are being used as tentative holds. Best candidates for same-week re-fill campaigns and last-minute deal codes.",
        })

    df2 = df.copy()
    df2["checkin_month"] = df2["checkin"].dt.to_period("M")
    ci_top = df2["checkin_month"].value_counts().sort_values(ascending=False).head(3)
    if len(ci_top) >= 3:
        top3_pct = round(ci_top.sum() / total * 100, 0)
        top3_str = " | ".join([f"{str(m)}: {c}" for m, c in ci_top.items()])
        room_seasonal.append({
            "Finding": "Cancellation volume peaks in top 3 stay months",
            "Detail": f"{top3_str} — {int(top3_pct)}% of total cancellations",
            "Revenue / Action Implication": "High churn in peak months suggests strong early bookings but poor conversion. Rate integrity and deposit policy changes needed.",
        })

    df2["cancel_month"] = df2["cancel_date"].dt.to_period("M")
    cd_top = df2["cancel_month"].value_counts().sort_values(ascending=False).head(3)
    if len(cd_top) >= 3:
        top3cd_str = " | ".join([f"{str(m)}: {c}" for m, c in cd_top.items()])
        room_seasonal.append({
            "Finding": "Cancel activity peaks early — targeting future stays",
            "Detail": f"Peak cancel months: {top3cd_str}",
            "Revenue / Action Implication": "The 60–90 day pre-arrival window is when decisions are made. Launch retention offers 90 days before planned arrival dates.",
        })

    return {"behavior": behavior, "lead_time": lead_time, "room_seasonal": room_seasonal}


def channel_month_crosstab(df: pd.DataFrame) -> pd.DataFrame:
    from config import CHANNEL_ORDER
    ct = pd.crosstab(df["cancel_month_label"], df["channel"])
    channels = [c for c in CHANNEL_ORDER if c in ct.columns] + [c for c in ct.columns if c not in CHANNEL_ORDER]
    ct = ct[[c for c in channels if c in ct.columns]]
    return ct
