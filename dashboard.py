"""NIPUN Bharat Mission PAB Minutes dashboard (local Streamlit app).

Source-faithful: terms, column order and units mirror the annexures
(Proposal / Final Approved Outlay; Physical, Unit Cost, Financial in Rs. lakh).

Run:  streamlit run dashboard.py
"""
import altair as alt
import pandas as pd
import streamlit as st

WB = "NIPUN_Bharat_PAB_master.xlsx"
YEARS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26", "2026-27"]

# ---- dataviz reference palette (light mode, validated) ----
SURFACE = "#fcfcfb"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE = "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4",
          "#008300", "#4a3aa7", "#e34948"]
STATUS = {"good": "#0ca30c", "warning": "#fab219",
          "serious": "#ec835a", "critical": "#d03b3b"}

STATUS_LABEL = {
    "ok": "✓ Clean",
    "ok-ocr-fallback(verify numbers)": "◐ OCR, verify numbers",
    "ok-partial(no totals captured)": "◔ Partial",
    "ok-partial(block end not detected)": "◔ Partial",
    "layout-variant(needs review)": "✗ Unparsed (layout)",
    "needs-ocr": "✗ Unparsed (scan)",
    "no-nipun-found": "No NIPUN content",
}
DOC_LABEL = {"minutes": "Minutes (primary)", "minutes (alt)": "Minutes (revised copy)",
             "addendum": "Addendum", "addendum (alt)": "Addendum (second)",
             "corrigendum": "Corrigendum", "supplementary": "Supplementary",
             "supplementary (alt)": "Supplementary (second)",
             "annexure": "Annexure volume", "other": "Other"}

CATEGORIES = [  # (label, keyword regex), fixed palette order
    ("Teaching Learning Materials", r"teaching learning|tlm"),
    ("Teacher Resource / Handbook", r"teacher resource|handbook"),
    ("Teacher Capacity Building", r"capacity building|training|mentor"),
    ("Assessments & Learning Study", r"assessment|learning study|\bfls\b"),
    ("PMU (State & District)",
     r"\bpmu\b|formation of|^\s*\d?\s*-?\s*(district|state) level"),
    ("Pre-Primary / ECCE",
     r"pre[\s-]*primary|balvatika|bala |furniture|play material"
     r"|school readiness|vidya pravesh"),
]
LEAK_RE = (r"head cook|assistant cook|\bwarden\b|part time teacher"
           r"|electricity|water charges|food/?lodging|boundary wall|toilet"
           r"|preparatory camp|\bkgbv\b|\bhostel\b|medical care")
LEAK_CAT = "Non-NIPUN row (leaked, excluded from totals)"

st.set_page_config(page_title="NIPUN Bharat PAB Minutes",
                   layout="wide", page_icon="📗")


@st.cache_data
def load(mtime=None):
    budget = pd.read_excel(WB, sheet_name="Budget")
    narrative = pd.read_excel(WB, sheet_name="Narrative")
    log = pd.read_excel(WB, sheet_name="Log")
    budget = budget.merge(log[["source_file", "status", "total_check"]],
                          on="source_file", how="left")
    budget["_order"] = range(len(budget))

    def side_ok(phy, unit, fin):
        return (phy.notna() & unit.notna() & fin.notna()
                & ((phy * unit - fin).abs()
                   <= (0.05 * fin.abs()).clip(lower=0.5)))

    budget["p_valid"] = side_ok(budget["proposed_physical"],
                                budget["proposed_unit_cost"],
                                budget["proposed_financial_lakh"])
    budget["a_valid"] = side_ok(budget["approved_physical"],
                                budget["approved_unit_cost"],
                                budget["approved_financial_lakh"])

    import re as _re
    def categorize(label, code, remarks):
        s = str(label).lower()
        if _re.search(LEAK_RE, s):
            return LEAK_CAT
        if str(code).startswith("87"):
            return "PMU (State & District)"
        for name, pat in CATEGORIES:
            if _re.search(pat, s):
                return name
        # generic OCR labels usually carry their identity in remarks
        r = str(remarks).lower()
        if r and r != "nan":
            if _re.search(LEAK_RE, r.split(";")[0]):
                return LEAK_CAT
            for name, pat in CATEGORIES:
                if _re.search(pat, r):
                    return name + " (from remarks)"
        return "Other / unidentified"
    budget["category"] = [categorize(l, c, r) for l, c, r in
                          zip(budget["activity"], budget["code"],
                              budget["remarks"])]
    budget["category_base"] = budget["category"].str.replace(
        " (from remarks)", "", regex=False)
    leaked = budget["category_base"] == LEAK_CAT
    budget.loc[leaked, "p_valid"] = False
    budget.loc[leaked, "a_valid"] = False
    # extractor-generated placeholder labels (not source text) lose em dashes
    budget["activity"] = budget["activity"].astype(str).str.replace(
        "(OCR — identify", "(OCR, identify", regex=False)
    budget["quality"] = budget["status"].map(STATUS_LABEL).fillna(budget["status"])
    budget["doc_label"] = budget["doc_type"].map(DOC_LABEL).fillna(budget["doc_type"])
    try:
        import json
        man = json.load(open("pdfs/manifest.json", encoding="utf-8"))
        url_map = {e["local_file"]: e["url"] for e in man if e.get("url")}
    except Exception:
        url_map = {}
    log["source_url"] = log["source_file"].map(url_map)
    for col in ("p_verified", "a_verified"):
        if col not in budget.columns:
            budget[col] = ""
    budget["p_verified"] = budget["p_verified"].fillna("")
    budget["a_verified"] = budget["a_verified"].fillna("")
    return budget, narrative, log


import os as _os
BUDGET, NARRATIVE, LOG = load(_os.path.getmtime(WB))
ACT_MIN = BUDGET[(BUDGET.row_type == "activity") & (BUDGET.doc_type == "minutes")]
CAT_ORDER = [c for c, _ in CATEGORIES] + ["Other / unidentified"]
CAT_COLOR = dict(zip(CAT_ORDER, SERIES[:6] + [MUTED]))


def themed(chart):
    return (chart.configure(background=SURFACE, font="system-ui")
            .configure_view(stroke=None)
            .configure_axis(labelColor=MUTED, titleColor=INK2, gridColor=GRID,
                            domainColor=BASELINE, tickColor=BASELINE,
                            labelFontSize=12, titleFontSize=12)
            .configure_legend(labelColor=INK2, titleColor=INK2))


def lakh(v):
    return f"₹{v:,.0f} lakh"


def crore(v):
    return f"₹{v / 100:,.0f} Cr"


# ---------------------------------------------------------------- header
st.title("NIPUN Bharat Mission PAB Minutes")
st.caption("What the Project Approval Board proposed and approved for "
           "foundational literacy & numeracy, state by state, from the "
           "Samagra Shiksha AWP&B minutes (2021-22 → 2026-27). "
           "All figures in Rs. lakh, as printed in the source.")

with st.sidebar:
    st.header("About this data")
    st.markdown(
        f"- **{LOG.shape[0]} PAB documents** parsed from the Ministry of "
        f"Education (DoSEL) portal\n"
        f"- **{ACT_MIN['state'].nunique()} states/UTs**, 6 budget years\n"
        f"- Figures are shown **as printed**; national aggregates count a "
        f"row only when *Physical × Unit Cost = Financial* checks out\n"
        f"- Some minutes exist only as poor scans, so their rows are marked "
        f"**◐ OCR, verify numbers**")
    st.divider()
    st.markdown("**Reading the quality marks**\n\n"
                "✓ parsed clean · ◐ parsed via OCR (verify before quoting) · "
                "◔ partial · ✗ unparsed scan")
    st.divider()
    st.caption("Built from NIPUN_Bharat_PAB_master.xlsx · "
               "re-run `python parallel_extract.py` after new downloads")

tab_over, tab_state, tab_comp, tab_cov, tab_ana = st.tabs(
    ["🇮🇳 National Picture", "🏛️ State Explorer", "📊 Compare States",
     "🧭 Coverage & Quality", "📈 Analytics"])

# ------------------------------------------------------------ national
with tab_over:
    P = ACT_MIN[ACT_MIN.p_valid]
    A = ACT_MIN[ACT_MIN.a_valid]
    tot_p, tot_a = P.proposed_financial_lakh.sum(), A.approved_financial_lakh.sum()
    data_years = [y for y in YEARS if (A.year == y).any()]
    latest = data_years[-1] if data_years else YEARS[-1]
    prev = data_years[-2] if len(data_years) > 1 else latest
    a_latest = A[A.year == latest].approved_financial_lakh.sum()
    # YoY on the common-state subset only, so coverage changes between the
    # two years can't masquerade as budget changes
    st_latest = set(A[A.year == latest].state)
    st_prev = set(A[A.year == prev].state)
    common = st_latest & st_prev
    c_latest = A[(A.year == latest)
                 & A.state.isin(common)].approved_financial_lakh.sum()
    c_prev = A[(A.year == prev)
               & A.state.isin(common)].approved_financial_lakh.sum()
    yoy = (c_latest - c_prev) / c_prev * 100 if c_prev else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Approved, all years", crore(tot_a), help=lakh(tot_a))
    c2.metric(f"Approved, {latest}", crore(a_latest),
              delta=f"{yoy:+.0f}% vs {prev} (same {len(common)} states)",
              help=lakh(a_latest))
    c3.metric("Approved vs proposed",
              f"{tot_a / tot_p * 100:,.0f}%" if tot_p else "n/a",
              help="Across validated rows, how much of what states asked "
                   "for was approved")
    c4.metric("States / UTs in data", f"{ACT_MIN.state.nunique()}")

    top_cat = (A[A.year == latest].groupby("category")
               .approved_financial_lakh.sum().sort_values(ascending=False))
    if len(top_cat):
        share = top_cat.iloc[0] / top_cat.sum() * 100
        n_latest = len(st_latest)
        n_missing = ACT_MIN.state.nunique() - n_latest
        ocr_states = sorted(set(
            ACT_MIN[(ACT_MIN.year == latest)
                    & (ACT_MIN.quality != "✓ Clean")].state))
        miss_note = (f" {n_missing} state(s) have no usable {latest} data "
                     f"and are not counted." if n_missing else "")
        ocr_note = (f" Figures for {len(ocr_states)} state(s) "
                    f"({', '.join(ocr_states[:4])}"
                    f"{'…' if len(ocr_states) > 4 else ''}) come from "
                    f"OCR-read scans and are partial." if ocr_states else "")
        st.markdown(
            f"**In {latest}, the PAB approved {crore(a_latest)} "
            f"({lakh(a_latest)}) for NIPUN Bharat across {n_latest} "
            f"states, {'up' if yoy >= 0 else 'down'} {abs(yoy):.0f}% on "
            f"{prev} comparing the same {len(common)} states. "
            f"“{top_cat.index[0]}” is the largest head at {share:.0f}% of "
            f"approvals.**")
        st.caption(f"Validated rows only (Physical × Unit Cost = Financial)."
                   f"{miss_note}{ocr_note}")

    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("Proposal vs Final Approved Outlay")
        by = pd.DataFrame({
            "Proposal": P.groupby("year").proposed_financial_lakh.sum(),
            "Final Approved Outlay": A.groupby("year").approved_financial_lakh.sum(),
        }).reindex(YEARS).reset_index(names="year").melt(
            "year", var_name="measure", value_name="lakh")
        ch = (alt.Chart(by)
              .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
                        size=22, stroke=SURFACE, strokeWidth=2)
              .encode(x=alt.X("year:N", title=None, sort=YEARS),
                      xOffset=alt.XOffset("measure:N", sort=[
                          "Proposal", "Final Approved Outlay"]),
                      y=alt.Y("lakh:Q", title="Rs. lakh"),
                      color=alt.Color("measure:N", title=None,
                                      sort=["Proposal", "Final Approved Outlay"],
                                      scale=alt.Scale(domain=[
                                          "Proposal", "Final Approved Outlay"],
                                          range=SERIES[:2])),
                      tooltip=[alt.Tooltip("year:N", title="Year"),
                               alt.Tooltip("measure:N", title="Measure"),
                               alt.Tooltip("lakh:Q", title="Rs. lakh",
                                           format=",.0f")])
              .properties(height=330))
        st.altair_chart(themed(ch), width="stretch")
    with col_r:
        st.subheader("Where approvals go, by activity")
        mix = (A[A.category_base != LEAK_CAT]
           .groupby(["year", "category_base"]).approved_financial_lakh.sum()
           .rename_axis(["year", "category"]).reset_index())
        ch2 = (alt.Chart(mix)
               .mark_bar(size=26, stroke=SURFACE, strokeWidth=2)
               .encode(x=alt.X("year:N", title=None, sort=YEARS),
                       y=alt.Y("approved_financial_lakh:Q", title="Rs. lakh"),
                       color=alt.Color("category:N", title=None,
                                       sort=CAT_ORDER,
                                       scale=alt.Scale(domain=CAT_ORDER,
                                                       range=[CAT_COLOR[c] for c in CAT_ORDER])),
                       order=alt.Order("color_category_sort_index:Q"),
                       tooltip=[alt.Tooltip("year:N", title="Year"),
                                alt.Tooltip("category:N", title="Activity"),
                                alt.Tooltip("approved_financial_lakh:Q",
                                            title="Approved (Rs. lakh)",
                                            format=",.0f")])
               .properties(height=330))
        st.altair_chart(themed(ch2), width="stretch")
    st.caption("Primary minutes only; validated rows only. Activity heads "
               "are grouped from the printed activity names; '87 / PMU' "
               "codes count as PMU.")

# --------------------------------------------------------- state explorer
with tab_state:
    states = sorted(BUDGET.state.dropna().unique())
    csel1, csel2 = st.columns([2, 1])
    sel_state = csel1.selectbox("State / UT", states, index=states.index(
        "Uttar Pradesh") if "Uttar Pradesh" in states else 0)
    s_act = ACT_MIN[(ACT_MIN.state == sel_state) & ACT_MIN.a_valid]

    # at-a-glance trend
    trend = (s_act.groupby("year").approved_financial_lakh.sum()
             .reindex(YEARS).rename_axis("year").reset_index())
    spark = (alt.Chart(trend)
             .mark_bar(color=SERIES[0], cornerRadiusTopLeft=4,
                       cornerRadiusTopRight=4, size=30)
             .encode(x=alt.X("year:N", title=None, sort=YEARS),
                     y=alt.Y("approved_financial_lakh:Q",
                             title="Approved (Rs. lakh)"),
                     tooltip=[alt.Tooltip("year:N", title="Year"),
                              alt.Tooltip("approved_financial_lakh:Q",
                                          title="Approved (Rs. lakh)",
                                          format=",.1f")])
             .properties(height=180))
    st.altair_chart(themed(spark), width="stretch")
    have_yrs = [y for y in YEARS if trend.set_index("year")
                .approved_financial_lakh.get(y, 0) > 0]
    gap_yrs = [y for y in YEARS if y not in have_yrs]
    qual = sorted(set(ACT_MIN[ACT_MIN.state == sel_state].quality))
    st.caption(
        f"Validated NIPUN approvals by year for {sel_state}. "
        f"Data available for {', '.join(have_yrs) if have_yrs else 'no years'}"
        + (f"; no usable data for {', '.join(gap_yrs)}" if gap_yrs else "")
        + (f". Extraction quality {', '.join(qual)}." if qual else "."))

    yrs = sorted(BUDGET[BUDGET.state == sel_state].year.dropna().unique())
    sel_year = csel2.selectbox("AWP&B year", yrs,
                               index=len(yrs) - 1 if yrs else 0)

    sub = BUDGET[(BUDGET.state == sel_state) & (BUDGET.year == sel_year)]
    doc_choices = sub.doc_label.unique().tolist()
    show_docs = st.multiselect("Documents", doc_choices,
                               default=[d for d in doc_choices
                                        if d.startswith("Minutes")] or doc_choices)
    sub = sub[sub.doc_label.isin(show_docs)]

    numcols = ["proposed_physical", "proposed_unit_cost",
               "proposed_financial_lakh", "approved_physical",
               "approved_unit_cost", "approved_financial_lakh"]
    for src, doc in sub.groupby("source_file", sort=True):
        lg = LOG[LOG.source_file == src].iloc[0]
        q = STATUS_LABEL.get(str(lg["status"]), str(lg["status"]))
        chk = {"OK": "sums match", "OK(reconciled)": "sums match",
               "MISMATCH": "⚠ totals do not sum, see remarks"}.get(
            str(lg["total_check"]), "")
        st.markdown(f"##### {doc.doc_label.iloc[0]} · {q}"
                    + (f" · {chk}" if chk else ""))
        url = lg.get("source_url")
        if pd.notna(url) and url:
            st.caption(f"{src} · [open source PDF on the ministry portal]"
                       f"({url})")
        else:
            st.caption(f"{src} · retrieved from an archived copy")
        doc = doc.sort_values("_order")
        doc = doc[~((doc.row_type == "total")
                    & doc[numcols].isna().all(axis=1))]
        table = pd.DataFrame({
            "Code": doc.code.fillna(""),
            "Particulars / Activity Master": doc.activity,
            "Proposal · Physical": doc.proposed_physical,
            "Proposal · Unit Cost": doc.proposed_unit_cost,
            "Proposal · Financial": doc.proposed_financial_lakh,
            "Approved · Physical": doc.approved_physical,
            "Approved · Unit Cost": doc.approved_unit_cost,
            "Approved · Financial": doc.approved_financial_lakh,
            "Remarks": doc.remarks.fillna(""),
        }).reset_index(drop=True)
        is_total = (doc.row_type == "total").tolist()
        fmt = {"Proposal · Physical": "{:,.0f}", "Approved · Physical": "{:,.0f}",
               "Proposal · Unit Cost": "{:.5f}", "Approved · Unit Cost": "{:.5f}",
               "Proposal · Financial": "{:,.2f}", "Approved · Financial": "{:,.2f}"}
        sty = (table.style.format(fmt, na_rep="")
               .apply(lambda r: ["font-weight:700; background-color:#f0efec"
                                 if is_total[r.name] else "" for _ in r], axis=1))
        st.dataframe(sty, hide_index=True, width="stretch")

    narr = NARRATIVE[(NARRATIVE.state == sel_state)
                     & (NARRATIVE.year == sel_year)]
    if len(narr):
        import re as _re
        has_meta = "scope" in narr.columns

        def render_excerpt(r):
            head = (f" · *{r.section_heading}*"
                    if pd.notna(r.section_heading) and r.section_heading
                    else "")
            st.markdown(f"**p.{r.pdf_page}**{head}")
            if has_meta and getattr(r, "text_quality", "ok") == "low":
                st.caption("⚠ scanned text of low quality, read with care")
            txt = str(r.excerpt).replace("*", r"\*").replace("_", r"\_")
            txt = _re.sub(r"(n[il1]pun[a-z]*|foundational\s+l[ei]\w+)",
                          lambda m: f"**{m.group(0)}**", txt, flags=_re.I)
            st.markdown(txt)
            st.divider()

        if has_meta:
            spec = narr[narr.scope == "state-specific"]
            tmpl = narr[narr.scope != "state-specific"]
        else:
            spec, tmpl = narr, narr.iloc[0:0]
        if len(spec):
            with st.expander(f"📜 What the minutes say about NIPUN, specific "
                             f"to {sel_state} ({len(spec)})", expanded=False):
                for _, r in spec.iterrows():
                    render_excerpt(r)
        if len(tmpl):
            with st.expander(f"📋 Standard national guidance repeated across "
                             f"states ({len(tmpl)})"):
                st.caption("The ministry includes near-identical NIPUN "
                           "guidance paragraphs in most states' minutes. "
                           "They are grouped here so state-specific text "
                           "stands out above.")
                for _, r in tmpl.iterrows():
                    render_excerpt(r)

# ------------------------------------------------------------ comparisons
with tab_comp:
    f1, f2, f3 = st.columns([1, 1, 2])
    sel_yr = f1.selectbox("AWP&B year", YEARS, index=YEARS.index("2026-27"),
                          key="compare_year")
    measure = f2.selectbox("Measure", ["Final Approved Outlay", "Proposal"])
    cats = f3.multiselect("Activity heads", CAT_ORDER, default=CAT_ORDER)
    mcol, vmask = (("approved_financial_lakh", ACT_MIN.a_valid)
                   if measure == "Final Approved Outlay"
                   else ("proposed_financial_lakh", ACT_MIN.p_valid))
    comp = (ACT_MIN[vmask & (ACT_MIN.year == sel_yr)
                    & ACT_MIN.category_base.isin(cats)]
            .groupby("state")[mcol].sum().sort_values(ascending=False)
            .reset_index())
    comp = comp[comp[mcol] > 0]
    st.subheader(f"{measure}, {sel_yr}, in Rs. lakh")
    ch3 = (alt.Chart(comp)
           .mark_bar(color=SERIES[0], cornerRadiusEnd=4, size=14)
           .encode(y=alt.Y("state:N", sort="-x", title=None,
                           axis=alt.Axis(labelOverlap=False, labelLimit=220)),
                   x=alt.X(f"{mcol}:Q", title="Rs. lakh"),
                   tooltip=[alt.Tooltip("state:N", title="State/UT"),
                            alt.Tooltip(f"{mcol}:Q", title="Rs. lakh",
                                        format=",.1f")])
           .properties(height=max(300, 22 * len(comp))))
    st.altair_chart(themed(ch3), width="stretch")
    st.caption("Validated rows from primary minutes. States absent here "
               "either had no usable data for this year (see Coverage) or "
               "approved nothing under the selected heads.")
    st.download_button("Download this view (CSV)",
                       comp.to_csv(index=False).encode(),
                       f"nipun_{sel_yr}_{measure.replace(' ', '_')}.csv",
                       "text/csv")

# ---------------------------------------------------------------- coverage
with tab_cov:
    st.subheader("Which state-years have usable data")
    st.caption("A cell counts as covered when at least one document for that "
               "state and year produced NIPUN budget rows. ◇ means the data "
               "came from a companion document (addendum or annexure volume) "
               "rather than the minutes themselves.")
    marks = {"✓ Clean": "✓", "◐ OCR, verify numbers": "◐", "◔ Partial": "◔"}
    act_all = BUDGET[BUDGET.row_type == "activity"]
    src_status = act_all.groupby(["state", "year"]).quality.apply(set)
    from_minutes = (act_all[act_all.doc_label.str.startswith("Minutes")]
                    .groupby(["state", "year"]).size())
    states_all = sorted(ACT_MIN.state.unique())
    grid = pd.DataFrame(index=states_all, columns=YEARS)
    for (s, y), qs in src_status.items():
        if s not in grid.index or y not in YEARS:
            continue
        if (s, y) not in from_minutes.index:
            grid.loc[s, y] = "◇"          # via companion document only
            continue
        for label, mk in marks.items():
            if label in qs:
                grid.loc[s, y] = mk
                break
        else:
            grid.loc[s, y] = "◔"
    grid = grid.fillna("✗")
    counts = grid.stack().value_counts()
    covered = int(counts.get("✓", 0) + counts.get("◐", 0)
                  + counts.get("◔", 0) + counts.get("◇", 0))
    total_cells = len(states_all) * len(YEARS)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("State-years covered", f"{covered} of {total_cells}",
              help="At least one parsed document with NIPUN rows")
    m2.metric("Parsed clean", f"{int(counts.get('✓', 0))}")
    m3.metric("Via OCR or partial",
              f"{int(counts.get('◐', 0) + counts.get('◔', 0) + counts.get('◇', 0))}",
              help="Usable but verify before quoting")
    m4.metric("Missing", f"{int(counts.get('✗', 0))}")

    # quality mix per year
    peryear = []
    for y in YEARS:
        col = grid[y].value_counts()
        for mk, name in [("✓", "Clean"), ("◐", "OCR"), ("◔", "Partial"),
                         ("◇", "Companion doc"), ("✗", "Missing")]:
            peryear.append({"year": y, "mark": name,
                            "cells": int(col.get(mk, 0))})
    py = pd.DataFrame(peryear)
    mark_order = ["Clean", "OCR", "Partial", "Companion doc", "Missing"]
    mark_color = {"Clean": STATUS["good"], "OCR": STATUS["warning"],
                  "Partial": STATUS["serious"], "Companion doc": SERIES[0],
                  "Missing": STATUS["critical"]}
    chq = (alt.Chart(py)
           .mark_bar(size=30, stroke=SURFACE, strokeWidth=2)
           .encode(x=alt.X("year:N", title=None, sort=YEARS),
                   y=alt.Y("cells:Q", title="State-years"),
                   color=alt.Color("mark:N", title=None, sort=mark_order,
                                   scale=alt.Scale(domain=mark_order,
                                                   range=[mark_color[m]
                                                          for m in mark_order])),
                   order=alt.Order("color_mark_sort_index:Q"),
                   tooltip=[alt.Tooltip("year:N", title="Year"),
                            alt.Tooltip("mark:N", title="Quality"),
                            alt.Tooltip("cells:Q", title="State-years")])
           .properties(height=220))
    st.altair_chart(themed(chq), width="stretch")

    colors = {"✓": STATUS["good"], "◐": STATUS["warning"],
              "◔": STATUS["serious"], "◇": SERIES[0],
              "✗": STATUS["critical"]}
    sty = grid.style.map(lambda v: f"color:{colors.get(v, INK)}; "
                                   f"font-weight:700; text-align:center")
    st.dataframe(sty, width="stretch", height=38 * len(grid))

    with st.expander(f"Why cells are missing ({int(counts.get('✗', 0))})"):
        st.caption("Two causes. Either the ministry never published that "
                   "year's minutes on its portal (checked against the "
                   "Wayback Machine archive too), or the published file is "
                   "an unreadable scan.")
        import re as _re2
        def safe_name(s):
            return _re2.sub(r"[^A-Za-z0-9&]+", "-", s).strip("-")
        # source files for the merged UT keep the portal's pre-merger names
        prev_names = {"Dadra & Nagar Haveli and Daman & Diu":
                      ["Dadra and Nagar Haveli", "Daman and Diu"]}
        reasons = []
        have_files = set(LOG.source_file.astype(str))
        for s in states_all:
            for y in YEARS:
                if grid.loc[s, y] != "✗":
                    continue
                prefs = [f"{safe_name(n)}_{y}_"
                         for n in [s] + prev_names.get(s, [])]
                matches = [f for f in have_files
                           if any(f.startswith(p) for p in prefs)]
                if matches:
                    sts = LOG[LOG.source_file.isin(matches)].status.map(
                        STATUS_LABEL).fillna("").tolist()
                    reason = "document exists but is unreadable, " + \
                             ", ".join(sorted(set(x for x in sts if x)))
                else:
                    reason = "never published on the ministry portal"
                reasons.append({"State / UT": s, "Year": y, "Reason": reason})
        st.dataframe(pd.DataFrame(reasons), hide_index=True, width="stretch")

    with st.expander("Files needing attention"):
        flg = LOG[~LOG.status.isin(["ok", "no-nipun-found"])].copy()
        flg["quality"] = flg.status.map(STATUS_LABEL).fillna(flg.status)
        st.dataframe(flg[["source_file", "quality", "total_check",
                          "budget_rows", "source_url"]],
                     hide_index=True, width="stretch",
                     column_config={"source_url": st.column_config.LinkColumn(
                         "Source PDF", display_text="open")})
    with st.expander("Full processing log"):
        st.dataframe(LOG, hide_index=True, width="stretch")

    st.subheader("Value verification tiers")
    st.caption("Every published number carries how it was confirmed. "
               "Arithmetic means Physical times Unit Cost reproduces the "
               "printed Financial. Totals chain means the value closes "
               "against printed totals. Dual OCR means two independent OCR "
               "passes agree. Vision means adjudicated against the page "
               "image. Unverified values are queued for adjudication.")
    tiers = pd.concat([
        ACT_MIN.loc[ACT_MIN.proposed_financial_lakh.notna(), "p_verified"],
        ACT_MIN.loc[ACT_MIN.approved_financial_lakh.notna(), "a_verified"],
    ]).replace("", "unverified").value_counts()
    if len(tiers):
        tdf = tiers.rename_axis("tier").reset_index(name="values")
        tdf["share"] = (tdf["values"] / tdf["values"].sum() * 100).round(1)
        c1, c2 = st.columns([1, 2])
        with c1:
            st.dataframe(tdf, hide_index=True, width="stretch")
        with c2:
            verified = tdf[tdf.tier != "unverified"]["values"].sum()
            st.metric("Independently verified numeric sides",
                      f"{verified:,} of {tdf['values'].sum():,}",
                      help="Target is 99.5 percent measured accuracy over "
                           "everything published; see accuracy_report.json "
                           "after certification")
    try:
        import json as _json
        rep = _json.load(open("accuracy_report.json", encoding="utf-8"))
        st.markdown("**Certified accuracy (stratified sample, Wilson 95 "
                    "percent lower bounds)**")
        st.dataframe(pd.DataFrame(rep), hide_index=True, width="content")
    except Exception:
        st.caption("Certification measurement not yet run.")

# ------------------------------------------------------------ analytics
with tab_ana:
    a1, a2 = st.columns([1, 2])
    ana_scope = a1.radio("Scope", ["National", "One state / UT"],
                         horizontal=True)
    ana_years = a2.multiselect("AWP&B years", YEARS,
                               default=[YEARS[-2], YEARS[-1]])
    df_ana = ACT_MIN[ACT_MIN.a_valid].copy()
    if ana_scope == "One state / UT":
        ana_states = sorted(df_ana.state.dropna().unique())
        ana_state = st.selectbox("State / UT", ana_states)
        df_ana = df_ana[df_ana.state == ana_state]
    df_ana = df_ana[df_ana.year.isin(ana_years)]
    n_years = max(len(ana_years), 1)

    tot_lakh = df_ana.approved_financial_lakh.sum()
    tot_rs = tot_lakh * 1e5
    per_day = tot_rs / (365 * n_years) if tot_rs else 0

    t_mask = df_ana.activity.str.contains(
        r"teacher|mentor|capacity|training", case=False, na=False)
    s_mask = df_ana.activity.str.contains(
        r"student|child|pupil|\btlm\b|teaching learning|balvatika",
        case=False, na=False)
    t_fin = df_ana[t_mask].approved_financial_lakh.sum() * 1e5
    t_phy = df_ana[t_mask].approved_physical.sum()
    s_fin = df_ana[s_mask].approved_financial_lakh.sum() * 1e5
    s_phy = df_ana[s_mask].approved_physical.sum()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Approved spend, selection", crore(tot_lakh),
              help=lakh(tot_lakh))
    k2.metric("Spend per day", f"₹{per_day:,.0f}",
              help=f"Approved spend spread over 365 days x {n_years} "
                   f"selected year(s)")
    k3.metric("Teacher-facing spend per unit",
              f"₹{t_fin / t_phy:,.0f}" if t_phy else "n/a",
              help=f"₹{t_fin / 1e7:,.1f} Cr on teacher-matched rows over "
                   f"{t_phy:,.0f} physical units. Units mix teachers and "
                   f"teacher-training days in some states, so read as an "
                   f"order of magnitude")
    k4.metric("Student-facing spend per unit",
              f"₹{s_fin / s_phy:,.0f}" if s_phy else "n/a",
              help=f"₹{s_fin / 1e7:,.1f} Cr on student-matched rows over "
                   f"{s_phy:,.0f} physical units (mostly students)")
    st.caption("Validated activity rows from minutes only. Teacher and "
               "student figures divide each group's own spend by its own "
               "physical targets, not the total outlay.")

    st.subheader("Top 10 line items by approved outlay")
    top10 = (df_ana.groupby(["activity", "category_base"])
             .agg(phy=("approved_physical", "sum"),
                  fin=("approved_financial_lakh", "sum"),
                  states=("state", "nunique"))
             .reset_index()
             .sort_values("fin", ascending=False).head(10))
    top10["unit_rs"] = (top10.fin / top10.phy * 1e5).where(top10.phy > 0)
    top10 = top10.rename(columns={
        "activity": "Line item", "category_base": "Head",
        "phy": "Physical (approved)", "unit_rs": "Effective unit cost (Rs.)",
        "fin": "Approved (Rs. lakh)", "states": "States"})
    st.dataframe(
        top10[["Line item", "Head", "Physical (approved)",
               "Effective unit cost (Rs.)", "Approved (Rs. lakh)", "States"]]
        .style.format({"Physical (approved)": "{:,.0f}",
                       "Effective unit cost (Rs.)": "₹{:,.0f}",
                       "Approved (Rs. lakh)": "₹{:,.2f}"}, na_rep="n/a"),
        hide_index=True, use_container_width=True)
    st.caption("Effective unit cost is total approved financial over total "
               "approved physical for the grouped rows, converted to "
               "rupees.")

    st.subheader("TLM spend by unit cost band")
    tlm = df_ana[df_ana.category_base == "Teaching Learning Materials"].copy()
    if len(tlm):
        tlm["unit_rs"] = tlm.approved_unit_cost * 1e5
        bands = [0, 100, 200, 300, 400, 500, float("inf")]
        labels = ["Up to ₹100", "₹101-200", "₹201-300", "₹301-400",
                  "₹401-500", "Above ₹500"]
        tlm["band"] = pd.cut(tlm.unit_rs, bins=bands, labels=labels,
                             include_lowest=True)
        bsum = (tlm.groupby("band", observed=False)
                .agg(fin=("approved_financial_lakh", "sum"),
                     phy=("approved_physical", "sum"),
                     rows=("activity", "count")).reset_index())
        cb1, cb2 = st.columns([2, 1])
        with cb1:
            ch_tlm = (alt.Chart(bsum)
                      .mark_bar(color=SERIES[2], cornerRadiusTopLeft=4,
                                cornerRadiusTopRight=4)
                      .encode(
                          x=alt.X("band:N", sort=labels,
                                  title="Approved unit cost per student"),
                          y=alt.Y("fin:Q",
                                  title="Approved outlay (Rs. lakh)"),
                          tooltip=[
                              alt.Tooltip("band:N", title="Band"),
                              alt.Tooltip("fin:Q", format=",.1f",
                                          title="Approved (Rs. lakh)"),
                              alt.Tooltip("phy:Q", format=",.0f",
                                          title="Students"),
                              alt.Tooltip("rows:Q", title="Rows")])
                      .properties(height=320))
            st.altair_chart(themed(ch_tlm), use_container_width=True)
        with cb2:
            st.dataframe(
                bsum.rename(columns={"band": "Band",
                                     "fin": "Approved (Rs. lakh)",
                                     "phy": "Students", "rows": "Rows"})
                .style.format({"Approved (Rs. lakh)": "₹{:,.1f}",
                               "Students": "{:,.0f}"}),
                hide_index=True, use_container_width=True)
        st.caption("Unit costs are stored in Rs. lakh in the annexures and "
                   "converted to rupees per student here.")
    else:
        st.info("No validated TLM rows in the current selection.")
