"""NIPUN Bharat Mission PAB Minutes dashboard (local Streamlit app).

Source-faithful: terms, column order and units mirror the annexures
(Proposal / Final Approved Outlay; Physical, Unit Cost, Financial in Rs. lakh).

The visual language follows nipun_story.html, the editorial story page this
app grew out of: warm paper, serif prose, sans-serif data furniture, CSF
blue and yellow leading the series palette. The story itself is now rebuilt
natively in the first tab rather than embedded, so it shares that language
rather than sitting inside it as an iframe.

Run:  streamlit run dashboard.py
"""
from contextlib import contextmanager
from pathlib import Path
import re

import altair as alt
import pandas as pd
import streamlit as st

WB = "NIPUN_Bharat_PAB_master.xlsx"
YEARS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26", "2026-27"]

# ---- palette. A cool neutral canvas, not a warm cream one: the brand navy
# and yellow are the only saturated things on the page, and a warm ground
# fights the navy and muddies the yellow. Structure is carried by hairlines
# and by the white of the surfaces, never by shadow.
PAPER, CARD = "#fafafa", "#ffffff"
# Four steps of ink, each with a job. MUTED is deliberately light and is for
# furniture only (axis values, eyebrows, chart labels); anything a reader has
# to actually read, captions included, sits at QUIET or darker, because
# zinc-400 on a near-white ground is below comfortable reading contrast.
INK, INK2, QUIET, MUTED = "#0a0a0a", "#52525b", "#71717a", "#a1a1aa"
GRID, BASELINE, CHALK = "#e4e4e7", "#d4d4d8", "#f4f4f5"
# CSF_BLUE / CSF_YELLOW are the foundation's brand colors and lead the series;
# the rest carry no brand meaning and exist to separate categories.
CSF_BLUE, CSF_YELLOW = "#00316b", "#ffd400"
SERIES = [CSF_BLUE, CSF_YELLOW, "#3b82f6", "#f59e0b", "#ec4899",
          "#10b981", "#71717a"]
SEQ0 = "#dbeafe"  # palest step of the sequential ramp that ends at CSF_BLUE
SEQ = [SEQ0, "#93c5fd", "#60a5fa", "#2563eb", CSF_BLUE]
STATUS = {"good": "#16a34a", "warning": "#eab308",
          "serious": "#f97316", "critical": "#dc2626"}
# Section tones. Each is (surface wash, border, label and rule colour), built
# on the Scouted formula: the hue at a few percent for the fill, the same hue
# at mid alpha for the stroke, and a darkened version for type so the label
# stays readable at 0.68rem. Colour is assigned by what a section is about,
# not decoratively, so the same head keeps the same hue across tabs.
TONES = {
    "navy":    ("rgba(0,49,107,0.030)",   "rgba(0,49,107,0.20)",   "#00316b"),
    "gold":    ("rgba(255,212,0,0.070)",  "rgba(255,212,0,0.60)",  "#8a6d00"),
    "blue":    ("rgba(59,130,246,0.038)", "rgba(59,130,246,0.26)", "#1d4ed8"),
    "emerald": ("rgba(16,185,129,0.035)", "rgba(16,185,129,0.26)", "#047857"),
    "amber":   ("rgba(245,158,11,0.045)", "rgba(245,158,11,0.30)", "#b45309"),
    "pink":    ("rgba(236,72,153,0.032)", "rgba(236,72,153,0.24)", "#be185d"),
    "plain":   ("#ffffff",                "#e4e4e7",               "#71717a"),
}
# Three faces, three jobs, no overlap. A display serif carries the headlines
# and nothing else; a tight grotesque carries every word of running text,
# label and control; a monospace carries every digit, so figures align in a
# column and read as measured rather than written. All three are Google
# Fonts because Streamlit Cloud runs Linux with no licensed faces installed,
# and a system-serif fallback there lands on DejaVu, which is what made the
# previous build read as a default rather than a decision.
DISPLAY = '"Instrument Serif", "Iowan Old Style", Georgia, serif'
SANS = '"Inter Tight", Inter, system-ui, -apple-system, sans-serif'
MONO = '"JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace'

STATUS_LABEL = {
    "ok": "✓ Clean",
    # hand-read off the rendered page and reconciled against the printed
    # totals, so at least as trustworthy as a clean automated parse
    "ok(vision-verified)": "✓ Clean (vision-verified)",
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
KGBV_CODES = (6483, 6496)  # inclusive C-code span of the KGBV block

# ---------------------------------------------------------- grade scope
# Which grades a budget line names, read off the printed page. Verified
# against the source before this was built, because the common assumption
# (NIPUN started at Grades 1-3 and was later widened to 5) is backwards for
# these documents. What the pages actually print:
#
#   UP 2021-22 p890      86.0.3 "Capacity building of Teachers of Grades I
#                        to V (New)" printed verbatim, so the I-V label is
#                        the source's own, not an extractor normalisation.
#                        Its TLM line names no grade span at all.
#   Bihar 2022-23 p2170  86.0.1 label names no span; the remark carries it,
#                        "10952303 students as per UDISE+ 2020-21 of Grades
#                        1 to 5". This is why remarks are a real fallback.
#   Chhattisgarh 2025-26 The Prabandh layout splits the block in two, and
#     p49-p50            prints both halves: "TLM ... pre-primary sections
#                        in Govt. Schools and Grade 1 and 2" alongside
#                        "TLM ... in Govt. Schools and Grade 3 to 5".
#   MP 2025-26 p45       Same split. Its Grade 3 to 5 label is truncated in
#                        capture at the page boundary but the printed remark
#                        "Recommended as proposed for Grade III to V" holds.
#   UP 2026-27 p65       Re-broadened under C-codes, "TLM ... from Balvatika
#                        to Grade 5 (C6777)", "Grades I to V (C6778/C6779)".
#
# So the timeline is wide (Grades 1-5) through 2024-25, narrowed to a
# Foundational Stage block in 2025-26 with a Grade 3-5 carve-out printed by
# only some states, then widened again in 2026-27. fetch_udise.py carries
# the same reading.
#
# Two things deliberately NOT used as signals. The printed "Activity" column
# names the scope ("5.8.2 - TLM (Pre-Primary to Grade 2)") but the workbook
# stores only its code, so that text is not available. And the "-FS" suffix
# on the sub-component is printed in 2026-27 as well as 2025-26, so it
# fingerprints the Prabandh layout, not the grade scope.
SCOPE_UPTO5 = "Grades 1 to 5"
SCOPE_PPG2 = "Pre-primary to Grade 2"
SCOPE_G35 = "Grades 3 to 5"
SCOPE_PP = "Pre-primary only"
SCOPE_NONE = "Not stated on the page"
SCOPE_ORDER = [SCOPE_UPTO5, SCOPE_PPG2, SCOPE_G35, SCOPE_PP, SCOPE_NONE]
SCOPE_COLOR = {SCOPE_UPTO5: CSF_BLUE, SCOPE_PPG2: "#3987e5",
               SCOPE_G35: "#eda100", SCOPE_PP: CSF_YELLOW, SCOPE_NONE: MUTED}
# 2026-27 prints a C-code on every FLN line and the code disambiguates what
# the label cannot: C6800 names both "Pre-Primary/Balvatika" and "Class I to
# V" in one string, and only the code settles that it is the full span.
CCODE_SCOPE = {"6777": SCOPE_UPTO5, "6778": SCOPE_UPTO5,
               "6779": SCOPE_UPTO5, "6800": SCOPE_UPTO5,
               "6039": SCOPE_PP, "6040": SCOPE_PP, "6041": SCOPE_PP,
               "6042": SCOPE_PP, "6043": SCOPE_PP, "6162": SCOPE_PP}
# 2025-26 writes "Class" as often as "Grade", and "Grades I and II" as often
# as "I to II", so both nouns and the "and" separator are required.
RE_G35 = r"(?:grade|class)e?s?\s*[-.\s]*(?:iii|3)\s*(?:to|-|–|and|&)\s*(?:v\b|5)"
RE_UPTO5 = (r"(?:grade|class)e?s?\s*[-.\s]*(?:i\b|1)\s*(?:to|-|–)\s*(?:v\b|5)"
            r"|balvatika\s*to\s*grade\s*[5v]"
            r"|pre[-\s]*primary\s*/?\s*balvatika\s*,?\s*class\s*i\s*to\s*v")
RE_PPG2 = (r"(?:grade|class)e?s?\s*[-.\s]*(?:i\b|1)\s*(?:to|and|&|,)\s*(?:ii\b|2)"
           r"|pre[\s.-]*primary\s*to\s*grade[-\s]*(?:ii\b|2)"
           r"|\bpp\s*to\s*grade[-\s]*ii|from\s*pre[-\s]*primary")
RE_PP = (r"pre[\s.-]*primary|balvatika|\bbala\b|child\s*friendly\s*furniture"
         r"|out\s*door\s*play|khel\s*pitara|school\s*readiness|vidya\s*pravesh")
# Order matters. Grade 3-5 is tested first so "Class III to V" is never read
# as a pre-primary line, and Pre-primary-to-Grade-2 before pre-primary-only
# so "Pre-Primary to Grade 2" keeps its upper bound.
_SCOPE_RULES = ((RE_G35, SCOPE_G35), (RE_UPTO5, SCOPE_UPTO5),
                (RE_PPG2, SCOPE_PPG2), (RE_PP, SCOPE_PP))


def scope_band(activity, remarks):
    """Return (band, how it was determined) for one printed budget line.

    Precedence is code, then the printed line label, then the coordinator
    remark. The label beats the remark because the label is the budget
    line's own name while the remark is prose about it, and the two do
    genuinely disagree in the source. Tamil Nadu 2025-26 p38 prints
    "Teachers Resource Material/ Activity Handbook for Class III to V"
    against a remark reading "for 80,495 teachers in Grade I-V"; both are
    printed, so this is a source-internal inconsistency to record, not a
    capture error to repair.
    """
    lab = str(activity).lower()
    cc = re.search(r"\(c(\d{4})\)", lab)
    if cc and cc.group(1) in CCODE_SCOPE:
        return CCODE_SCOPE[cc.group(1)], "printed C-code"
    for pat, band in _SCOPE_RULES:
        if re.search(pat, lab):
            return band, "printed line label"
    rem = str(remarks).lower()
    if rem and rem != "nan":
        for pat, band in _SCOPE_RULES:
            if re.search(pat, rem):
                return band, "coordinator remark"
    return SCOPE_NONE, "not stated"


# Scope of the printed NIPUN subtotal, which varies by annexure layout. The
# 86/87 schema totals FLN and PMU separately, so its printed FLN figure
# excludes PMU; the 2026-27 FS layout folds PMU into one subtotal. These
# heads are budgeted elsewhere and no NIPUN total covers them.
# "32" is deliberately absent: Tripura 2023-24 numbers its NIPUN block 32.x,
# so excluding that prefix would drop real NIPUN rows. The only other 32.x
# rows in the workbook are Gujarat header rows, which carry no value.
OUTSIDE_HEADS = ("102", "36", "37", "38", "106", "134", "77", "79", "48")
PMU_ROW_RE = r"\bpmu\b|formation of|^\s*\d?\s*-?\s*(?:district|state) level"
PMU_TOTAL_RE = r"total.*(?:pmu|formation of)"

st.set_page_config(page_title="NIPUN Bharat PAB Minutes",
                   layout="wide", page_icon="📗")


def inject_css():
    """Apply the story page's typography and card treatment to Streamlit.

    Kept additive on purpose. These are [data-testid] / [data-baseweb]
    hooks rather than a supported API, so a Streamlit release can rename
    one; when that happens the rule simply stops applying and the element
    falls back to default styling rather than disappearing.
    """
    # A bordered st.container renders as stVerticalBlock sitting directly
    # inside an stLayoutWrapper. The parent restriction matters: bare
    # stVerticalBlock is also the generic block element and would tint the
    # whole page. Columns and expanders nested inside a section do not
    # contain its eyebrow, so :has() cannot leak the tint down into them.
    wrap = ('[data-testid="stLayoutWrapper"] > '
            '[data-testid="stVerticalBlock"]')
    TONE_CSS = "\n".join(
        f"{wrap}:has(.tone-{name}) {{"
        f" background: {bg}; border-color: {bd} !important; }}\n"
        f".eyebrow.tone-{name} {{ color: {ac}; }}"
        for name, (bg, bd, ac) in TONES.items())
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter+Tight:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

    .stApp {{ background: {PAPER}; }}
    html, body, [data-testid="stAppViewContainer"] {{ color: {INK}; }}

    /* headlines are the only serif on the page */
    h1, h2, h3, h4, h5, h6 {{
        font-family: {DISPLAY} !important;
        font-weight: 400 !important;
        color: {INK} !important;
        letter-spacing: -0.015em;
        line-height: 1.14;
        text-wrap: balance;
    }}
    h1 {{ font-size: clamp(2.1rem, 4.4vw, 3rem) !important; }}
    h5 {{ font-size: 1.5rem !important; margin-bottom: 0.15rem !important; }}

    /* everything that is read as text, rather than as a headline, is the
       grotesque. Prose sits at 16px with a generous measure. */
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li {{
        font-family: {SANS};
        font-size: 1rem;
        line-height: 1.62;
        color: {INK2};
    }}
    [data-testid="stMarkdownContainer"] strong {{
        color: {INK};
        font-weight: 600;
    }}
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p {{
        font-family: {SANS} !important;
        color: {QUIET} !important;
        font-size: 0.83rem !important;
        line-height: 1.58;
    }}
    /* digits are monospace and tabular wherever they carry meaning */
    [data-testid="stMetricValue"], [data-testid="stDataFrame"],
    .mono {{ font-variant-numeric: tabular-nums; }}

    /* eyebrow section label, hairline rule then uppercase tracking */
    .eyebrow {{
        font-family: {SANS};
        font-size: 0.68rem;
        font-weight: 600;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: {QUIET};
        display: flex;
        align-items: center;
        gap: 0.65rem;
        margin: 2.2rem 0 0.8rem 0;
    }}
    .eyebrow::before {{
        content: "";
        width: 18px;
        height: 2px;
        background: currentColor;
        flex: 0 0 18px;
        opacity: 0.85;
    }}
    .eyebrow:first-child {{ margin-top: 0; }}

    /* Section panels. Streamlit owns the border wrapper and offers no way to
       put a class on it, so each panel reads its tone off the eyebrow inside
       it via :has(). Supported everywhere current; if a browser lacks it the
       panel simply falls back to the neutral border, which is the same
       result as before this treatment existed. */
    {TONE_CSS}

    [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"] {{
        border-radius: 6px;
        padding: 1.2rem 1.4rem 1.3rem;
    }}
    [data-testid="stLayoutWrapper"] {{ margin-bottom: 1.15rem; }}

    /* metrics: flat white panel, hairline, no shadow, figure in monospace */
    [data-testid="stMetric"] {{
        background: {CARD};
        border: 1px solid {GRID};
        border-radius: 4px;
        padding: 0.85rem 1rem;
    }}
    [data-testid="stMetricValue"] {{
        font-family: {MONO} !important;
        font-size: 1.55rem !important;
        letter-spacing: -0.03em;
        color: {CSF_BLUE};
        font-weight: 500;
    }}
    [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p {{
        font-family: {SANS} !important;
        font-size: 0.68rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.09em;
        text-transform: uppercase;
        color: {QUIET} !important;
    }}
    [data-testid="stMetricDelta"] {{
        font-family: {MONO} !important;
        font-size: 0.76rem !important;
    }}

    .stTabs [data-baseweb="tab-list"] {{
        gap: 1.9rem;
        border-bottom: 1px solid {GRID};
    }}
    .stTabs [data-baseweb="tab"] {{
        font-family: {SANS};
        font-weight: 500;
        font-size: 0.78rem;
        letter-spacing: 0.09em;
        text-transform: uppercase;
        color: {QUIET};
        padding: 0.45rem 0;
    }}
    .stTabs [aria-selected="true"] {{ color: {CSF_BLUE}; }}
    /* the selected-tab underline. Streamlit 1.60 renders it via React Aria;
       the older baseweb node is kept so this survives either version */
    .stTabs .react-aria-SelectionIndicator,
    .stTabs [data-baseweb="tab-highlight"] {{ background: {CSF_BLUE} !important; }}

    /* the top toolbar strip sits above the app and defaults to white */
    [data-testid="stHeader"] {{ background: {PAPER}; }}

    [data-testid="stExpander"] details {{
        border: 1px solid {GRID};
        border-radius: 4px;
        background: {CARD};
    }}
    [data-testid="stExpander"] summary {{
        font-family: {SANS};
        font-size: 0.86rem;
        font-weight: 600;
        color: {INK2};
    }}
    [data-testid="stExpander"] summary:hover {{ color: {CSF_BLUE}; }}

    /* the story's opening line, the largest display moment in the app */
    .hero-kicker {{
        font-family: {DISPLAY};
        font-size: clamp(2.6rem, 6.4vw, 4.6rem);
        font-weight: 400;
        line-height: 1.0;
        letter-spacing: -0.03em;
        color: {INK};
        margin: 0.35rem 0 1rem 0;
        text-wrap: balance;
    }}

    /* controls: sans labels, hairline borders, no stock-Streamlit chrome */
    [data-testid="stWidgetLabel"] p {{
        font-family: {SANS} !important;
        font-size: 0.72rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: {INK2} !important;
    }}
    [data-baseweb="select"] > div,
    [data-testid="stMultiSelect"] > div > div {{
        font-family: {SANS};
        font-size: 0.86rem;
        background: {CARD};
        border-color: {GRID};
        border-radius: 4px;
    }}
    [data-baseweb="select"] > div:hover {{ border-color: {CSF_BLUE}; }}
    [data-baseweb="tag"] {{
        border-radius: 3px !important;
        font-family: {SANS};
        font-weight: 500;
        font-size: 0.78rem;
    }}
    [data-testid="stRadio"] label p,
    [data-testid="stCheckbox"] label p {{
        font-family: {SANS} !important;
        font-size: 0.86rem !important;
        color: {INK2} !important;
    }}
    [data-testid="stDownloadButton"] button,
    [data-testid="stBaseButton-secondary"] {{
        font-family: {SANS};
        font-size: 0.72rem;
        font-weight: 500;
        letter-spacing: 0.07em;
        text-transform: uppercase;
        border-radius: 4px;
        border: 1px solid {GRID};
        color: {INK2};
        background: {CARD};
    }}
    [data-testid="stDownloadButton"] button:hover {{
        border-color: {CSF_BLUE};
        color: {CSF_BLUE};
        background: {CARD};
    }}

    /* tables: hairline frame, square corners, figures in monospace */
    [data-testid="stDataFrame"] {{
        border: 1px solid {GRID};
        border-radius: 4px;
        overflow: hidden;
    }}
    [data-testid="stAlertContainer"] {{
        border-radius: 4px;
        font-family: {SANS};
    }}
    hr {{ border-color: {GRID}; }}
    </style>
    """, unsafe_allow_html=True)


inject_css()


def eyebrow(text, tone="plain"):
    st.markdown(f'<div class="eyebrow tone-{tone}">{text}</div>',
                unsafe_allow_html=True)


@contextmanager
def section(label, tone="plain"):
    """One titled, bordered panel.

    The tone reaches the panel through CSS :has() rather than through a class
    on the panel itself, because Streamlit owns the wrapper element and gives
    no hook to put a class on it. The eyebrow inside carries tone-<name> and
    the wrapper styles itself from that.
    """
    with st.container(border=True):
        eyebrow(label, tone)
        yield


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

    # A figure read directly off the rendered source page is stronger
    # evidence than the phy*unit=fin arithmetic test, so trust it even when
    # phy/unit were never captured alongside the amount. All three of these
    # tiers mean someone opened the page: "vision" read it, "vision-verified"
    # also reconciled it against a printed total, "manual-recovery" rebuilt
    # it from a companion document.
    #
    # Accepting only "vision-verified" here held 10 rows worth Rs 28.48 Cr
    # out of every published total, almost all of it Kerala 2021-22, whose
    # rows carry a financial figure and nothing to run the arithmetic on.
    # That put the app 28 Cr under the totals recorded in CLAUDE.md and
    # computed by story_prep.py, and made Kerala 2021-22 read as "no data".
    _READ = ["vision", "vision-verified", "manual-recovery"]
    p_read = budget.get("p_verified", "").isin(_READ) & budget["proposed_financial_lakh"].notna()
    a_read = budget.get("a_verified", "").isin(_READ) & budget["approved_financial_lakh"].notna()

    budget["p_valid"] = side_ok(budget["proposed_physical"],
                                budget["proposed_unit_cost"],
                                budget["proposed_financial_lakh"]) | p_read
    budget["a_valid"] = side_ok(budget["approved_physical"],
                                budget["approved_unit_cost"],
                                budget["approved_financial_lakh"]) | a_read

    def categorize(label, code, remarks):
        s = str(label).lower()
        # The KGBV / residential block sits in the same annexure and its line
        # items carry C6483-C6496 codes. Several of them ("Maintenance",
        # "Miscellaneous", "Capacity Building") are too generic to quarantine
        # by name without catching genuine NIPUN rows, so key on the code.
        cc = re.search(r"\(c(\d{4})\)", s)
        if cc and KGBV_CODES[0] <= int(cc.group(1)) <= KGBV_CODES[1]:
            return LEAK_CAT
        if re.search(LEAK_RE, s):
            return LEAK_CAT
        if str(code).startswith("87"):
            return "PMU (State & District)"
        for name, pat in CATEGORIES:
            if re.search(pat, s):
                return name
        # generic OCR labels usually carry their identity in remarks
        r = str(remarks).lower()
        if r and r != "nan":
            if re.search(LEAK_RE, r.split(";")[0]):
                return LEAK_CAT
            for name, pat in CATEGORIES:
                if re.search(pat, r):
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

    bands = [scope_band(a, r) for a, r in
             zip(budget["activity"], budget["remarks"])]
    budget["scope"] = [b for b, _ in bands]
    budget["scope_source"] = [s for _, s in bands]
    # a quarantined row is not a NIPUN line, so it has no NIPUN grade scope
    budget.loc[leaked, "scope"] = SCOPE_NONE
    budget.loc[leaked, "scope_source"] = "not stated"

    _pre = budget["code"].astype(str).str.split(".").str[0]
    _lab = budget["activity"].astype(str).str.lower()
    budget["outside_block"] = _pre.isin(OUTSIDE_HEADS)
    budget["is_pmu_row"] = _pre.eq("87") | _lab.str.contains(
        PMU_ROW_RE, regex=True, na=False)
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


import datetime as _dt
import os as _os

# Documents whose current portal upload is a 72 DPI re-encode that cannot be
# read. These are parsed from an archived copy of the original instead, so
# the "open the source" link must not imply the portal file is what we used.
# Listed explicitly rather than read from disk: the replaced originals live
# in pdfs/lowres_2025_reupload/, which is not part of the deployed app.
RECOVERED_SOURCES = {
    "Assam_2023-24_minutes.pdf",
    "Chhattisgarh_2022-23_minutes.pdf",
    "Himachal-Pradesh_2022-23_minutes.pdf",
    "Manipur_2023-24_minutes.pdf",
    "Meghalaya_2023-24_minutes.pdf",
    "Mizoram_2022-23_minutes.pdf",
    "Mizoram_2023-24_minutes.pdf",
    "Nagaland_2022-23_minutes.pdf",
    "Tripura_2023-24_minutes.pdf",
    "West-Bengal_2023-24_minutes.pdf",
}
BUDGET, NARRATIVE, LOG = load(_os.path.getmtime(WB))
_ACT_ALL = BUDGET[BUDGET.row_type == "activity"]
# A handful of state-years (e.g. Kerala/Tamil Nadu/Goa/Assam 2025-26) have no
# primary "minutes" doc at all — their approval was only ever recorded in an
# addendum. Fall back to the addendum for those state-years only, so they
# aren't silently dropped from national totals and YoY comparisons; states
# that already have a minutes doc keep using it exclusively (addenda there
# are incremental top-ups, not replacements, and must not be double-counted).
# "annexure" belongs in the same fallback: Ladakh 2022-23 publishes its
# budget block in a separate annexure volume while its minutes carry only
# narrative. Leaving it out dropped that UT from national totals entirely.
# "supplementary"/"supplementary (alt)" are the same pattern under a
# different label (e.g. Delhi's 2025-26 supplementary volume) -- added
# proactively during the 2023-26 cleanup pass, since no state-year
# happened to depend solely on one yet, but the next one might.
_COMPANION = ["addendum", "addendum (alt)", "annexure",
              "supplementary", "supplementary (alt)"]
_minutes_pairs = set(map(tuple,
    _ACT_ALL.loc[_ACT_ALL.doc_type == "minutes", ["state", "year"]].values))
_is_primary = (_ACT_ALL.doc_type == "minutes") | (
    _ACT_ALL.doc_type.isin(_COMPANION)
    & ~_ACT_ALL[["state", "year"]].apply(tuple, axis=1).isin(_minutes_pairs))
ACT_MIN = _ACT_ALL[_is_primary]
# A document that carries 87.x codes, or prints its own PMU total, is telling
# us PMU is totalled separately from the FLN figure the Log records. Without
# either signal the PMU lines sit inside that figure.
PMU_OUTSIDE = (
    set(BUDGET.loc[BUDGET.code.astype(str).str.split(".").str[0].eq("87"),
                   "source_file"])
    | set(BUDGET.loc[(BUDGET.row_type == "total")
                     & BUDGET.activity.astype(str).str.lower().str.contains(
                         PMU_TOTAL_RE, regex=True, na=False), "source_file"]))
CAT_ORDER = [c for c, _ in CATEGORIES] + ["Other / unidentified"]
# Keyed by name rather than by position so reordering CATEGORIES cannot
# silently recolour every chart. The two brand colors take the two heads
# that carry most of the money.
CAT_COLOR = {
    "Teaching Learning Materials": CSF_BLUE,
    "Teacher Resource / Handbook": "#10b981",
    "Teacher Capacity Building": "#3b82f6",
    "Assessments & Learning Study": "#f59e0b",
    "PMU (State & District)": "#ec4899",
    "Pre-Primary / ECCE": CSF_YELLOW,
    "Other / unidentified": MUTED,
}


# ------------------------------------------------------------ story data
# The Story tab used to be a self-contained HTML page in an iframe. It is
# rebuilt from the workbook here so it carries the app's own design and
# cannot drift from the other tabs. The denominator conventions are
# story_prep.py's, unchanged, because the published story quotes them:
#   students covered = max approved_physical on TLM rows, per state-year
#   teachers covered = max approved_physical across Teacher Resource /
#     Handbook and Capacity Building rows (max, not sum, since the same
#     cohort is named on both lines)
#   per-day basis    = 365 calendar days
#   per-child rates  = computed only over states whose student count is
#     known, so an unknown denominator cannot deflate the rate
_TLM = "Teaching Learning Materials"
_TEACH = ["Teacher Resource / Handbook", "Teacher Capacity Building"]
# India tile cartogram, (column, row, abbreviation). Same layout as the
# story page so anyone comparing the two sees the same map.
# Named TILE_GRID, not GRID: GRID is the hairline colour in the palette and
# shadowing it fed a dict to every chart's gridColor.
TILE_GRID = {
    "Jammu & Kashmir": (1, 0, "JK"), "Ladakh": (2, 0, "LA"),
    "Punjab": (1, 1, "PB"), "Himachal Pradesh": (2, 1, "HP"),
    "Chandigarh": (3, 1, "CH"),
    "Haryana": (1, 2, "HR"), "Delhi": (2, 2, "DL"), "Uttarakhand": (3, 2, "UK"),
    "Rajasthan": (0, 3, "RJ"), "Uttar Pradesh": (2, 3, "UP"),
    "Bihar": (3, 3, "BR"), "Sikkim": (4, 3, "SK"),
    "Arunachal Pradesh": (6, 3, "AR"),
    "Gujarat": (0, 4, "GJ"), "Madhya Pradesh": (1, 4, "MP"),
    "Jharkhand": (3, 4, "JH"), "West Bengal": (4, 4, "WB"),
    "Assam": (5, 4, "AS"), "Nagaland": (6, 4, "NL"),
    "Dadra & Nagar Haveli and Daman & Diu": (0, 5, "DN"),
    "Maharashtra": (1, 5, "MH"), "Chhattisgarh": (2, 5, "CG"),
    "Odisha": (3, 5, "OD"), "Meghalaya": (5, 5, "ML"), "Manipur": (6, 5, "MN"),
    "Goa": (0, 6, "GA"), "Telangana": (1, 6, "TG"),
    "Andhra Pradesh": (2, 6, "AP"), "Tripura": (5, 6, "TR"),
    "Mizoram": (6, 6, "MZ"),
    "Karnataka": (1, 7, "KA"),
    "Kerala": (0, 8, "KL"), "Tamil Nadu": (1, 8, "TN"), "Puducherry": (2, 8, "PY"),
    "Lakshadweep": (0, 9, "LD"), "Andaman & Nicobar Islands": (3, 9, "AN"),
}


@st.cache_data
def story_metrics(mtime=None):
    av = ACT_MIN[ACT_MIN.a_valid]
    rows = []
    for (stt, yr), g in av.groupby(["state", "year"]):
        prop = ACT_MIN[(ACT_MIN.state == stt) & (ACT_MIN.year == yr)
                       & ACT_MIN.p_valid].proposed_financial_lakh.sum()
        rows.append({
            "state": stt, "year": yr,
            "lakh": g.approved_financial_lakh.sum(),
            "proposed_lakh": prop if prop else None,
            "students": g.loc[g.category_base == _TLM, "approved_physical"].max(),
            "teachers": g.loc[g.category_base.isin(_TEACH),
                              "approved_physical"].max()})
    sy = pd.DataFrame(rows)
    nat = []
    for yr in YEARS:
        g = sy[sy.year == yr]
        if not len(g):
            continue
        known = g[g.students.notna()]
        stu = known.students.sum()
        nat.append({
            "year": yr, "cr": g.lakh.sum() / 100,
            "states": len(g),
            "students": int(g.students.dropna().sum()),
            "teachers": int(g.teachers.dropna().sum()),
            "rpd": (known.lakh.sum() * 1e5 / stu / 365) if stu else None})
    return sy, pd.DataFrame(nat)


SY, NAT = story_metrics(_os.path.getmtime(WB))


def themed(chart):
    # Axis values are digits, so they take the monospace and line up
    # column-wise; titles and legends are words, so they take the grotesque.
    # No serif reaches Vega, which keeps the display face out of SVG text
    # measurement entirely.
    return (chart.configure(background="transparent", font=SANS)
            .configure_view(stroke=None)
            .configure_axis(labelColor=MUTED, titleColor=INK2, gridColor=GRID,
                            gridDash=[2, 3], domainColor=BASELINE,
                            tickColor=BASELINE, labelFont=MONO, titleFont=SANS,
                            labelFontSize=11, titleFontSize=11,
                            titleFontWeight=500, titlePadding=10)
            .configure_legend(labelColor=INK2, titleColor=MUTED,
                              labelFont=SANS, titleFont=SANS,
                              labelFontSize=12, titleFontSize=10,
                              titlePadding=6))


def lakh(v):
    return f"₹{v:,.0f} lakh"


def crore(v):
    return f"₹{v / 100:,.0f} Cr"


def indian(n):
    """Count in Indian units, which is how these figures are discussed."""
    if n is None or pd.isna(n):
        return "n/a"
    if n >= 1e7:
        return f"{n / 1e7:,.1f} crore"
    if n >= 1e5:
        return f"{n / 1e5:,.1f} lakh"
    return f"{n:,.0f}"


@st.cache_data
def load_udise():
    """UDISE+ enrolment, the one outside source the story checks against.

    Optional. The story degrades to omitting the cross-check rather than
    failing if the file is not deployed alongside the app.
    """
    try:
        import json
        return json.loads(
            Path("udise_2023_24_state_enrollment.json").read_text(
                encoding="utf-8"))
    except Exception:
        return None


def as_text(df, cols, spec, blank="no data", prefix=""):
    """Return a display copy with `cols` pre-rendered as text.

    A missing figure has to read as missing. Neither Styler.na_rep nor a
    callable formatter survives the trip through st.dataframe (the cell
    arrives from Arrow and paints as a literal "None"), so the substitution
    is done in the values themselves. The caller keeps the numeric frame for
    its CSV, which is what anyone recomputing should be using anyway.
    """
    out = df.copy()
    for c in cols:
        out[c] = df[c].map(
            lambda v: blank if pd.isna(v) else f"{prefix}{format(v, spec)}")
    return out


def right_align(styler, cols):
    return styler.set_properties(subset=cols, **{"text-align": "right"})


def table_csv(df, name, label="Download this table as CSV"):
    """Offer any displayed table as a CSV.

    Always pass the underlying DataFrame, never a Styler. utf-8-sig keeps
    the quality glyphs readable when the file is opened in Excel.
    """
    key = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
    st.download_button(label, df.to_csv(index=False).encode("utf-8-sig"),
                       f"{name}.csv", "text/csv", key=f"dl_{key}")


# ---------------------------------------------------------------- header
st.markdown('<div class="eyebrow">Samagra Shiksha AWP&amp;B minutes</div>',
            unsafe_allow_html=True)
st.title("NIPUN Bharat Mission PAB Minutes")
st.caption("What the Project Approval Board proposed and approved for "
           "foundational literacy & numeracy, state by state, from the "
           "Samagra Shiksha AWP&B minutes (2021-22 → 2026-27). "
           "All figures in Rs. lakh, as printed in the source.")

# The sidebar is gone. Its quality-marks key now sits in Data Quality next
# to the grid it explains, and its build note at the foot of that tab, which
# is where anyone asking "how current is this" is already looking.
QUALITY_KEY = ("✓ parsed clean, or hand-read off the page and reconciled "
               "against its printed total · ◐ parsed via OCR, verify before "
               "quoting · ◔ partial · ◇ from a companion document · "
               "✗ unparsed scan")
BUILD_NOTE = (f"Built from NIPUN_Bharat_PAB_master.xlsx, last updated "
              f"{_dt.date.fromtimestamp(_os.path.getmtime(WB)):%d %B %Y}. "
              f"{len(RECOVERED_SOURCES)} documents are read from archived "
              f"copies of their original uploads, because the files now on "
              f"the portal were re-uploaded at an unreadable resolution.")

tab_story, tab_nat, tab_exp, tab_qual = st.tabs(
    ["The Story", "National Picture", "Explore & Compare", "Data Quality"])

# ---------------------------------------------------------------- story
with tab_story:
    # Rebuilt natively rather than embedded. It used to be nipun_story.html in
    # a fixed-height iframe, which meant a scrollbar inside a scrollbar, a
    # hero cut off mid-number, and a dark full-bleed block dropped into a
    # warm-paper page. Every figure below is recomputed from the workbook, so
    # the story cannot drift from the tabs beside it.
    _n = NAT.set_index("year")
    _last, _first = NAT.year.iloc[-1], NAT.year.iloc[0]
    cur, first = _n.loc[_last], _n.loc[_first]
    per_state = cur.cr / cur.states
    per_child_year = cur.rpd * 365

    with section("A budget story from the PAB minutes", "navy"):
        st.markdown('<div class="hero-kicker">Two rupees a day</div>',
                    unsafe_allow_html=True)
        st.markdown(
            "What it costs to teach five crore children to read. Every figure on "
            "this page is read from the Government of India's Project Approval "
            "Board minutes for the NIPUN Bharat mission.")

        h1, h2, h3, h4 = st.columns(4)
        h1.metric(f"Approved for {_last}", f"₹{cur.cr:,.0f} Cr",
                  help=lakh(cur.cr * 100))
        h2.metric("Per state or UT", f"₹{per_state:,.0f} Cr",
                  help=f"Spread evenly across the {int(cur.states)} states and "
                       f"UTs with usable {_last} data. Real shares vary widely")
        h3.metric("Per covered child, per year", f"₹{per_child_year:,.0f}")
        h4.metric("Per covered child, per day", f"₹{cur.rpd:,.2f}",
                  help="365 day basis, over the states whose covered-child "
                       "count is printed")
        st.caption("Left to right, that is the same money divided down. The "
                   "daily figure is small because the denominator is very large.")

    # ------------------------------------------------------- the scale
    with section("The scale", "gold"):
        st.markdown("##### Small rupees, enormous reach")
        st.markdown(
            f"In {_last} the approved plans put teaching and learning materials "
            f"in the hands of **{indian(cur.students)} children** and equip "
            f"**{indian(cur.teachers)} teachers** across every state and union "
            f"territory. That is the denominator the daily figure divides by.")
        ud = load_udise()
        s1, s2, s3 = st.columns(3)
        s1.metric("Children reached", indian(cur.students),
                  help=f"{int(cur.students):,} children on approved teaching and "
                       f"learning material lines")
        s2.metric("Teachers reached", indian(cur.teachers),
                  help=f"{int(cur.teachers):,} teachers. Counted as the larger of "
                       f"the handbook and capacity-building lines in each state, "
                       f"not their sum, because the same cohort is named on both")
        if ud:
            nat_f = ud["national"]["foundational_enrolment"]
            s3.metric("Against all foundational enrolment",
                      f"{cur.students / nat_f * 100:,.0f}%",
                      help=f"{nat_f:,} children were enrolled at the foundational "
                           f"stage nationally in {ud['year']}")
            st.caption(f"That last figure is the closest outside check this page "
                       f"can offer. {ud['source']} counted {nat_f:,} children at "
                       f"the foundational stage in {ud['year']}, and {_last} "
                       f"approvals reach {cur.students / nat_f * 100:,.0f} "
                       f"percent of that count. The two are measured "
                       f"differently, so read it as a sense check rather than a "
                       f"coverage rate.")
        else:
            s3.metric("Against all foundational enrolment", "n/a")

    # -------------------------------------------------------- the climb
    with section("Six approval cycles", "navy"):
        st.markdown("##### The budget doubled in six years")
        st.markdown(
            f"From its launch year to {_last}, the mission's target year, the "
            f"Board's approved outlay grew from **₹{first.cr:,.0f} crore** to "
            f"**₹{cur.cr:,.0f} crore**. The jump after 2024-25 is not simply more "
            f"of the same money. From 2025-26 the approvals fold in large support "
            f"for pre-primary Balvatika classes while the materials budget "
            f"narrows to the youngest cohort. The grade section on the National "
            f"Picture tab shows that shift directly.")
        cl, cr_ = st.columns([3, 2])
        with cl:
            ch_cl = (alt.Chart(NAT)
                     .mark_bar(color=CSF_BLUE, cornerRadiusTopLeft=4,
                               cornerRadiusTopRight=4, size=44)
                     .encode(x=alt.X("year:N", title=None, sort=YEARS),
                             y=alt.Y("cr:Q", title="Approved (₹ crore)"),
                             tooltip=[alt.Tooltip("year:N", title="Year"),
                                      alt.Tooltip("cr:Q", title="₹ crore",
                                                  format=",.2f"),
                                      alt.Tooltip("states:Q", title="States")])
                     .properties(height=300))
            st.altair_chart(themed(ch_cl), width="stretch")
            st.caption("Approved outlay by year, all states and UTs, as printed "
                       "in the PAB minutes.")
        with cr_:
            ch_rpd = (alt.Chart(NAT.dropna(subset=["rpd"]))
                      .mark_line(color=CSF_BLUE, point=True, strokeWidth=2.5)
                      .encode(x=alt.X("year:N", title=None, sort=YEARS),
                              y=alt.Y("rpd:Q", title="₹ per child per day"),
                              tooltip=[alt.Tooltip("year:N", title="Year"),
                                       alt.Tooltip("rpd:Q", title="₹ per day",
                                                   format=",.2f")])
                      .properties(height=300))
            st.altair_chart(themed(ch_rpd), width="stretch")
            st.caption("Per covered child per day, 365 day basis. The 2025-26 "
                       "rise reflects a narrower pre-primary to Grade 2 cohort, "
                       "not a spending surge.")
        with st.expander("The year by year figures"):
            ntab = NAT.rename(columns={
                "year": "Year", "cr": "Approved (₹ crore)", "states": "States",
                "students": "Children", "teachers": "Teachers",
                "rpd": "₹ per child per day"})
            ncols = ["Approved (₹ crore)", "Children", "Teachers",
                     "₹ per child per day"]
            ndisp = as_text(ntab, ["Approved (₹ crore)"], ",.2f")
            ndisp = as_text(ndisp, ["Children", "Teachers"], ",.0f")
            ndisp = as_text(ndisp, ["₹ per child per day"], ",.2f")
            st.dataframe(right_align(ndisp.style, ncols),
                         hide_index=True, width="stretch")
            table_csv(NAT, "nipun_story_national_by_year", "These figures (CSV)")

    # ------------------------------------------------ where each rupee goes
    with section("Follow the rupee", "blue"):
        st.markdown("##### Where each rupee goes")
        st.markdown(
            "Take one rupee of the approved budget and split it into 100 paise. "
            "For most of the mission's life roughly 80 paise in every rupee went "
            "straight into children's hands as teaching and learning materials. "
            "From 2025-26 pre-primary support takes a large share for the first "
            "time.")
        AVc = ACT_MIN[ACT_MIN.a_valid & (ACT_MIN.category_base != LEAK_CAT)]
        paise = (AVc.groupby(["year", "category_base"])
                 .approved_financial_lakh.sum()
                 .rename_axis(["year", "category"]).reset_index())
        paise["paise"] = (paise.approved_financial_lakh
                          / paise.groupby("year").approved_financial_lakh
                          .transform("sum") * 100)
        ch_p = (alt.Chart(paise)
                .mark_bar(size=42, stroke=CARD, strokeWidth=1.5)
                .encode(x=alt.X("year:N", title=None, sort=YEARS),
                        y=alt.Y("paise:Q", title="Paise in every rupee",
                                scale=alt.Scale(domain=[0, 100])),
                        color=alt.Color("category:N", title=None, sort=CAT_ORDER,
                                        scale=alt.Scale(domain=CAT_ORDER,
                                                        range=[CAT_COLOR[c]
                                                               for c in CAT_ORDER])),
                        order=alt.Order("color_category_sort_index:Q"),
                        tooltip=[alt.Tooltip("year:N", title="Year"),
                                 alt.Tooltip("category:N", title="Head"),
                                 alt.Tooltip("paise:Q", title="Paise",
                                             format=".1f"),
                                 alt.Tooltip("approved_financial_lakh:Q",
                                             title="₹ lakh", format=",.0f")])
                .properties(height=340))
        st.altair_chart(themed(ch_p), width="stretch")
        st.caption("Each column is one rupee of that year's approved outlay, "
                   "split by activity head.")
        with st.expander("The rupee split as a table"):
            ptab = (paise.pivot(index="year", columns="category", values="paise")
                    .reindex(YEARS).reindex(columns=CAT_ORDER).round(1)
                    .reset_index(names="Year"))
            st.dataframe(right_align(as_text(ptab, CAT_ORDER, ",.1f", "0.0").style,
                                     CAT_ORDER), hide_index=True, width="stretch")
            table_csv(ptab, "nipun_story_rupee_split", "Rupee split (CSV)")

    # ------------------------------------------------------ the rate card
    with section("The price list", "amber"):
        st.markdown("##### The mission has a rate card")
        st.markdown(
            f"PAB approvals are built from per-unit rates, printed line by line "
            f"in the annexures. These are the most common approved rates in the "
            f"{_last} minutes. They read like a receipt for a child's "
            f"foundational education.")
        rc = ACT_MIN[(ACT_MIN.year == _last) & ACT_MIN.a_valid
                     & ACT_MIN.approved_unit_cost.notna()
                     & (ACT_MIN.approved_unit_cost > 0)
                     & (ACT_MIN.category_base != LEAK_CAT)].copy()
        rc["rs"] = (rc.approved_unit_cost * 1e5).round(0)
        card = [{"Head": c,
                 "Most common rate": rc[rc.category_base == c].rs.mode().iloc[0],
                 "Median rate": rc[rc.category_base == c].rs.median(),
                 "States on this line": int(rc[rc.category_base == c].state.nunique())}
                for c in CAT_ORDER if len(rc[rc.category_base == c]) >= 3]
        rcard = pd.DataFrame(card)
        if len(rcard):
            rc1, rc2 = st.columns([3, 2])
            with rc1:
                st.dataframe(right_align(
                    as_text(rcard, ["Most common rate", "Median rate"], ",.0f",
                            prefix="₹").style,
                    ["Most common rate", "Median rate", "States on this line"]),
                    hide_index=True, width="stretch")
                table_csv(rcard, f"nipun_story_rate_card_{_last}",
                          "Rate card (CSV)")
            with rc2:
                st.caption(
                    "Rates are printed in ₹ lakh per unit in the annexures and "
                    "converted to rupees here. A unit means per child per year "
                    "for materials, per teacher for handbooks and training, and "
                    "per district or state for a project management unit, so the "
                    "rows are not comparable with one another. Where a median "
                    "sits well above the most common rate, a few states were "
                    "approved above the norm.")

    # --------------------------------------------------------- state map
    with section(f"{int(cur.states)} states, one mission", "emerald"):
        st.markdown("##### Small states pay more per child")
        sy_last = SY[SY.year == _last].copy()
        sy_last["rpd"] = sy_last.lakh * 1e5 / sy_last.students / 365
        sy_last["cr"] = sy_last.lakh / 100
        ranked = sy_last.dropna(subset=["rpd"]).sort_values("rpd")
        if len(ranked):
            lo_s, hi_s = ranked.iloc[0], ranked.iloc[-1]
            st.markdown(
                f"The same mission costs very different amounts per child "
                f"depending on where the child lives. **{lo_s.state}** reaches "
                f"{indian(lo_s.students)} children at **₹{lo_s.rpd:,.2f} a day**. "
                f"**{hi_s.state}**, with {indian(hi_s.students)} children, spends "
                f"**₹{hi_s.rpd:,.2f} a day**. Fixed costs such as project units "
                f"and training infrastructure do not shrink with enrolment.")
        map_metric = st.radio("Shade the map by",
                              ["₹ per child per day", "Total ₹ crore"],
                              horizontal=True, key="story_map_metric")
        mcol_ = "rpd" if map_metric.startswith("₹ per") else "cr"
        tdf = pd.DataFrame([
            {"state": stt, "col": c, "row": r, "ab": ab,
             "value": (float(sy_last.loc[sy_last.state == stt, mcol_].iloc[0])
                       if (sy_last.state == stt).any()
                       and pd.notna(sy_last.loc[sy_last.state == stt,
                                                mcol_].iloc[0]) else None)}
            for stt, (c, r, ab) in TILE_GRID.items()])
        # Both measures are heavily skewed: most states sit near the bottom while
        # one or two run away with it (Ladakh at Rs 33.94 a day against a median
        # near Rs 2). A linear ramp paints almost every tile the same pale blue
        # and says nothing. Quantile bins spread the states across the ramp, and
        # deriving the label colour from the bin (rather than from the raw value)
        # keeps white text off pale tiles.
        known = tdf.value.dropna()
        nbins = min(5, known.nunique()) if len(known) else 0
        if nbins >= 2:
            tdf["bin"] = pd.qcut(tdf.value, nbins, labels=False, duplicates="drop")
            edges = pd.qcut(known, nbins, duplicates="drop").cat.categories
            names = [f"{e.left:,.2f} to {e.right:,.2f}" for e in edges]
            nb = len(names)
            ramp = SEQ[-nb:] if nb <= len(SEQ) else [SEQ0, CSF_BLUE]
            tdf["band"] = [names[int(b)] if pd.notna(b) else None
                           for b in tdf["bin"]]
            # ink fails on the darkest two steps, so the label flips there
            tdf["txt"] = ["light" if pd.notna(b) and int(b) >= nb - 2 else "dark"
                          for b in tdf["bin"]]
            color_enc = alt.Color("band:N", title=map_metric, sort=names,
                                  scale=alt.Scale(domain=names, range=ramp),
                                  legend=alt.Legend(orient="right", symbolType="square",
                                                    symbolSize=170))
        else:
            tdf["band"] = None
            tdf["txt"] = "dark"
            color_enc = alt.value(SEQ0)
        _pos = dict(x=alt.X("col:O", axis=None,
                            scale=alt.Scale(paddingInner=0.09)),
                    y=alt.Y("row:O", axis=None,
                            scale=alt.Scale(paddingInner=0.09)))
        _tip = [alt.Tooltip("state:N", title="State/UT"),
                alt.Tooltip("value:Q", title=map_metric, format=",.2f")]
        rects = (alt.Chart(tdf)
                 .mark_rect(cornerRadius=3, stroke=PAPER, strokeWidth=3)
                 .encode(color=color_enc, tooltip=_tip, **_pos))
        labels = (alt.Chart(tdf)
                  .mark_text(fontSize=11, fontWeight=600, font=SANS)
                  .encode(text="ab:N", tooltip=_tip,
                          color=alt.Color("txt:N", legend=None,
                                          scale=alt.Scale(
                                              domain=["light", "dark"],
                                              range=["#ffffff", INK2])),
                          **_pos))
        st.altair_chart(themed(alt.layer(rects, labels)
                               .properties(height=560, width=430)
                               .resolve_scale(color="independent")),
                        width="content")
        st.caption(f"{_last} approvals by state and UT. A blank tile means the "
                   f"figure is not available, usually because no covered-child "
                   f"count was printed on that state's lines.")
        with st.expander("Every state's figure"):
            mtab = (sy_last[["state", "cr", "students", "rpd"]]
                    .sort_values("cr", ascending=False)
                    .rename(columns={"state": "State / UT",
                                     "cr": "Approved (₹ crore)",
                                     "students": "Children covered",
                                     "rpd": "₹ per child per day"}))
            mcols = ["Approved (₹ crore)", "Children covered",
                     "₹ per child per day"]
            mdisp = as_text(mtab, ["Approved (₹ crore)"], ",.2f")
            mdisp = as_text(mdisp, ["Children covered"], ",.0f", "not printed")
            mdisp = as_text(mdisp, ["₹ per child per day"], ",.2f", "not printed")
            st.dataframe(right_align(mdisp.style, mcols),
                         hide_index=True, width="stretch")
            table_csv(mtab, f"nipun_story_states_{_last}", "State figures (CSV)")

    # ----------------------------------------------------- the negotiation
    with section("The negotiation", "pink"):
        st.markdown("##### What states asked for, and what they got")
        hc = sy_last.dropna(subset=["proposed_lakh"]).copy()
        hc["prop_cr"] = hc.proposed_lakh / 100
        hc = hc[hc.prop_cr > 0]
        hc["cut_pct"] = (1 - hc.cr / hc.prop_cr) * 100
        # The deepest cut of all is on a tiny plan (a few crore), where a small
        # absolute change reads as a huge percentage and draws a bar too short
        # to see. Call out the hardest cut among plans large enough for the
        # percentage to mean something instead, and say where the line is drawn.
        MATERIAL_CR = 25
        big = hc[hc.prop_cr >= MATERIAL_CR]
        worst = big.sort_values("cut_pct", ascending=False).head(1)
        show = pd.concat([hc.sort_values("cr", ascending=False).head(12), worst]
                         ).drop_duplicates(subset=["state"])
        if len(worst):
            w = worst.iloc[0]
            st.markdown(
                f"A PAB approval is the end of a negotiation. Most {_last} "
                f"proposals came through nearly whole. **{w.state}**'s did not. "
                f"It asked for ₹{w.prop_cr:,.1f} crore and was approved "
                f"₹{w.cr:,.1f} crore, a cut of {w.cut_pct:,.0f} percent.")
        melt = show.melt(id_vars="state", value_vars=["prop_cr", "cr"],
                         var_name="measure", value_name="crore")
        melt["measure"] = melt.measure.map({"prop_cr": "Proposed",
                                            "cr": "Approved"})
        ch_h = (alt.Chart(melt)
                .mark_bar(size=11, cornerRadiusEnd=2)
                .encode(y=alt.Y("state:N", title=None, sort="-x",
                                axis=alt.Axis(labelLimit=220)),
                        yOffset=alt.YOffset("measure:N",
                                            sort=["Proposed", "Approved"]),
                        x=alt.X("crore:Q", title="₹ crore"),
                        color=alt.Color("measure:N", title=None,
                                        sort=["Proposed", "Approved"],
                                        scale=alt.Scale(
                                            domain=["Proposed", "Approved"],
                                            range=[CSF_YELLOW, CSF_BLUE])),
                        tooltip=[alt.Tooltip("state:N", title="State/UT"),
                                 alt.Tooltip("measure:N", title="Measure"),
                                 alt.Tooltip("crore:Q", title="₹ crore",
                                             format=",.2f")])
                .properties(height=max(320, 30 * show.state.nunique())))
        st.altair_chart(themed(ch_h), width="stretch")
        st.caption(f"The twelve largest {_last} state plans by approved outlay, "
                   f"plus the hardest cut among plans of ₹{MATERIAL_CR} crore or "
                   f"more. Validated rows only, so a proposal side that was never "
                   f"captured is left out rather than shown as a zero. The table "
                   f"below carries every state, including the small plans whose "
                   f"percentage cuts are the steepest of all.")
        with st.expander("Proposed against approved, every state"):
            htab = (hc[["state", "prop_cr", "cr", "cut_pct"]]
                    .sort_values("cr", ascending=False)
                    .rename(columns={"state": "State / UT",
                                     "prop_cr": "Proposed (₹ crore)",
                                     "cr": "Approved (₹ crore)",
                                     "cut_pct": "Cut (%)"}))
            hcols = ["Proposed (₹ crore)", "Approved (₹ crore)", "Cut (%)"]
            hdisp = as_text(htab, ["Proposed (₹ crore)", "Approved (₹ crore)"],
                            ",.2f")
            hdisp = as_text(hdisp, ["Cut (%)"], ",.1f")
            st.dataframe(right_align(hdisp.style, hcols),
                         hide_index=True, width="stretch")
            table_csv(htab, f"nipun_story_proposed_vs_approved_{_last}",
                      "Proposed against approved (CSV)")

    # ------------------------------------------------------------- method
    with section("How these numbers were made", "plain"):
        st.markdown(
            "Every figure here is recomputed from the workbook on load, so this "
            "page cannot drift from the tabs beside it. The rules behind it:")
        st.markdown(
            "- Figures come from the primary PAB minutes for each state and "
            "year, falling back to an addendum or annexure volume only where no "
            "minutes exist. Duplicate portal downloads are excluded.\n"
            "- A row counts once it is validated, meaning Physical times Unit "
            "Cost reproduces the printed Financial, or the figure was read off "
            "the rendered page. Non-NIPUN lines that share the annexure, such as "
            "the KGBV residential block, are quarantined.\n"
            "- Children covered is the approved physical count on teaching and "
            "learning material lines. Teachers covered is the larger of the "
            "handbook and capacity-building lines in each state, not their sum, "
            "because the same cohort is named on both.\n"
            "- Per-day figures use a 365 day year and are computed only over the "
            "states whose covered-child count is printed, so an unknown "
            "denominator cannot deflate the rate.\n"
            "- Nothing here is estimated. Where a page does not print a figure, "
            "the app says so rather than filling the gap.")
        st.caption("Coverage is not complete in every year. The Data Quality tab "
                   "shows which state-years are missing and why, and how each "
                   "published number was verified.")

# ------------------------------------------------------------ national
with tab_nat:
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

    with section("The headline", "navy"):
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

        # "Approved, all years" and "Approved vs proposed" sum across every
        # year in ACT_MIN, so a year with a large state-coverage gap quietly
        # pulls both figures down without saying so. 2021-22 is missing 7
        # states/UTs (no PAB minutes ever surfaced for them, confirmed by an
        # independent Wayback sweep, not just an extraction gap) and 2023-24
        # is missing 1 (Jharkhand). Name them here rather than let the totals
        # imply full national coverage.
        all_states = set(ACT_MIN.state.unique())
        gap_notes = []
        for gap_year in ("2021-22", "2023-24"):
            if gap_year not in set(ACT_MIN.year.unique()):
                continue
            have = set(ACT_MIN[ACT_MIN.year == gap_year].state.unique())
            missing = sorted(all_states - have)
            if missing:
                gap_notes.append(f"**{gap_year}** ({len(missing)} missing: "
                                  f"{', '.join(missing)})")
        if gap_notes:
            st.caption(
                "“Approved, all years” and “Approved vs proposed” above sum "
                "every year in the data, including years with incomplete state "
                "coverage: " + "; ".join(gap_notes) + ". No PAB minutes have "
                "been found for these state-years despite a dedicated search "
                "(including a Wayback Machine sweep for 2021-22), so they are "
                "excluded rather than estimated. The all-years totals above are "
                "therefore a floor, not a national total.")

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

    with section("Proposal and approval", "blue"):
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("##### Proposal vs Final Approved Outlay")
            by = pd.DataFrame({
                "Proposal": P.groupby("year").proposed_financial_lakh.sum(),
                "Final Approved Outlay": A.groupby("year").approved_financial_lakh.sum(),
            }).reindex(YEARS).reset_index(names="year").melt(
                "year", var_name="measure", value_name="lakh")
            ch = (alt.Chart(by)
                  .mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2,
                            size=22, stroke=CARD, strokeWidth=2)
                  .encode(x=alt.X("year:N", title=None, sort=YEARS),
                          xOffset=alt.XOffset("measure:N", sort=[
                              "Proposal", "Final Approved Outlay"]),
                          y=alt.Y("lakh:Q", title="Rs. lakh"),
                          # approved is the headline measure, so it takes the
                          # brand blue and the proposal sits behind it in yellow
                          color=alt.Color("measure:N", title=None,
                                          sort=["Proposal", "Final Approved Outlay"],
                                          scale=alt.Scale(domain=[
                                              "Proposal", "Final Approved Outlay"],
                                              range=[CSF_YELLOW, CSF_BLUE])),
                          tooltip=[alt.Tooltip("year:N", title="Year"),
                                   alt.Tooltip("measure:N", title="Measure"),
                                   alt.Tooltip("lakh:Q", title="Rs. lakh",
                                               format=",.0f")])
                  .properties(height=330))
            st.altair_chart(themed(ch), width="stretch")
        with col_r:
            st.markdown("##### Where approvals go, by activity")
            mix = (A[A.category_base != LEAK_CAT]
               .groupby(["year", "category_base"]).approved_financial_lakh.sum()
               .rename_axis(["year", "category"]).reset_index())
            ch2 = (alt.Chart(mix)
                   .mark_bar(size=26, stroke=CARD, strokeWidth=2)
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
        st.caption("Primary minutes (or, where no minutes exist for a state-year, "
                   "its addendum) only; validated rows only. Activity heads "
                   "are grouped from the printed activity names; '87 / PMU' "
                   "codes count as PMU.")
        with st.expander("The numbers behind these two charts"):
            d1, d2 = st.columns(2)
            with d1:
                table_csv(by.rename(columns={"year": "Year", "measure": "Measure",
                                             "lakh": "Rs. lakh"}),
                          "nipun_proposal_vs_approved_by_year",
                          "Proposal vs approved (CSV)")
            with d2:
                table_csv(mix.rename(columns={
                    "year": "Year", "category": "Activity head",
                    "approved_financial_lakh": "Approved (Rs. lakh)"}),
                    "nipun_approvals_by_activity_head", "Activity mix (CSV)")

    # ------------------------------------------------ grade scope parity
    with section("Which grades the money names", "gold"):
        SC = A[A.category_base != LEAK_CAT]
        scope_year = (SC.groupby(["year", "scope"]).approved_financial_lakh.sum()
                      .reset_index())
        if len(scope_year):
            base = alt.Chart(scope_year)
            bars = (base.mark_bar(size=44, stroke=CARD, strokeWidth=2)
                    .encode(x=alt.X("year:N", title=None, sort=YEARS),
                            y=alt.Y("approved_financial_lakh:Q",
                                    title="Approved (Rs. lakh)"),
                            color=alt.Color("scope:N", title="Grades the line names",
                                            sort=SCOPE_ORDER,
                                            scale=alt.Scale(
                                                domain=SCOPE_ORDER,
                                                range=[SCOPE_COLOR[s]
                                                       for s in SCOPE_ORDER])),
                            order=alt.Order("color_scope_sort_index:Q"),
                            tooltip=[alt.Tooltip("year:N", title="Year"),
                                     alt.Tooltip("scope:N", title="Grades named"),
                                     alt.Tooltip("approved_financial_lakh:Q",
                                                 title="Approved (Rs. lakh)",
                                                 format=",.0f")])
                    .properties(height=380))
            seam = pd.DataFrame([{"year": "2025-26", "note":
                                  "2025-26 recast as a Foundational Stage block"}])
            mark = (alt.Chart(seam)
                    .mark_text(align="center", dy=-10, fontSize=11,
                               font=SANS, fontWeight=600, color=INK2)
                    .encode(x=alt.X("year:N", sort=YEARS),
                            y=alt.value(0), text="note:N"))
            st.altair_chart(themed(alt.layer(bars, mark).resolve_scale(
                color="independent")), width="stretch")
            st.caption(
                "Each bar is that year's approved outlay split by the grade span "
                "the printed budget line actually names. Nothing here is "
                "estimated or reallocated. Read left to right, the scope moves "
                "the opposite way to the usual assumption. The PABs funded "
                "Grades 1 to 5 from 2021-22, then 2025-26 recast the block as a "
                "Foundational Stage (pre-primary to Grade 2) with a separate "
                "Grade 3 to 5 line that only some states printed, and 2026-27 "
                "widened it again to Balvatika to Grade 5.")
            st.caption(
                "“Not stated on the page” is large in the early years because "
                "most 2021-22 to 2024-25 lines simply name no grade span, so a "
                "strict like-for-like series cannot be read off the print. That "
                "band is shown rather than allocated. Scope is taken from the "
                "printed C-code first, then the line label, then the coordinator "
                "remark. Where a label and a remark disagree the label is used "
                "and both are printed in the source, for example Tamil Nadu "
                "2025-26 prints a handbook line for Class III to V whose remark "
                "reads Grade I-V.")

            # taken from every primary-document row, not only validated ones, so
            # a state that prints the line but whose amount was never captured
            # (Odisha) is still named as having printed it
            _carve_src = ACT_MIN[(ACT_MIN.year == "2025-26")
                                 & (ACT_MIN.scope == SCOPE_G35)
                                 & (ACT_MIN.category_base != LEAK_CAT)]
            carve = sorted(_carve_src.state.unique())
            if carve:
                no_fig = sorted(_carve_src.groupby("state")
                                .approved_financial_lakh.apply(
                                    lambda s: s.notna().sum() == 0)
                                .loc[lambda s: s].index)
                note = (f" {', '.join(no_fig)} prints the line but no amount for "
                        f"it was recoverable, so it carries no bar above."
                        if no_fig else "")
                st.caption(f"States and UTs printing a separate Grade 3 to 5 "
                           f"line in 2025-26 ({len(carve)}), {', '.join(carve)}."
                           + note)

            with st.expander("Scope tables and how each row was tagged"):
                pivot = (scope_year.pivot(index="year", columns="scope",
                                          values="approved_financial_lakh")
                         .reindex(YEARS).reindex(columns=SCOPE_ORDER)
                         .fillna(0).round(2).reset_index(names="Year"))
                st.dataframe(pivot.style.format(
                    {c: "{:,.2f}" for c in SCOPE_ORDER}),
                    hide_index=True, width="stretch")
                table_csv(pivot, "nipun_outlay_by_grade_scope",
                          "Outlay by grade scope (CSV)")
                prov = (SC.groupby(["year", "scope_source"])
                        .approved_financial_lakh.sum().reset_index()
                        .rename(columns={"year": "Year",
                                         "scope_source": "Tagged from",
                                         "approved_financial_lakh":
                                             "Approved (Rs. lakh)"}))
                st.dataframe(prov.style.format({"Approved (Rs. lakh)": "{:,.2f}"}),
                             hide_index=True, width="stretch")
                rows = (SC[["state", "year", "code", "activity", "scope",
                            "scope_source", "approved_financial_lakh",
                            "pdf_page", "source_file"]]
                        .rename(columns={"state": "State / UT", "year": "Year",
                                         "code": "Code", "activity": "Line item",
                                         "scope": "Grades named",
                                         "scope_source": "Tagged from",
                                         "approved_financial_lakh":
                                             "Approved (Rs. lakh)",
                                         "pdf_page": "PDF page",
                                         "source_file": "Source file"}))
                table_csv(rows, "nipun_rows_with_grade_scope",
                          "Every tagged row (CSV)")

    # -------------------------------------------------------- cost lenses
    with section("Cost lenses", "emerald"):
        ana_years = st.multiselect("AWP&B years", YEARS,
                                   default=[YEARS[-2], YEARS[-1]],
                                   key="lens_years")
        df_ana = ACT_MIN[ACT_MIN.a_valid & ACT_MIN.year.isin(ana_years)].copy()
        n_years = max(len(ana_years), 1)

        tot_lakh = df_ana.approved_financial_lakh.sum()
        per_day = tot_lakh * 1e5 / (365 * n_years) if tot_lakh else 0

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
        k1.metric("Approved spend, selection", crore(tot_lakh), help=lakh(tot_lakh))
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
        st.caption("National totals from validated activity rows in the primary "
                   "minutes (or addendum, where no minutes exist for a "
                   "state-year). Teacher and student figures divide each group's "
                   "own spend by its own physical targets, not the total outlay. "
                   "For a single state use the Explore & Compare tab.")

        st.markdown("##### Top 10 line items by approved outlay")
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
        top10 = top10[["Line item", "Head", "Physical (approved)",
                       "Effective unit cost (Rs.)", "Approved (Rs. lakh)",
                       "States"]]
        _t = as_text(top10, ["Physical (approved)"], ",.0f", "n/a")
        _t = as_text(_t, ["Effective unit cost (Rs.)"], ",.0f", "n/a", prefix="₹")
        _t = as_text(_t, ["Approved (Rs. lakh)"], ",.2f", "n/a", prefix="₹")
        _tnum = ["Physical (approved)", "Effective unit cost (Rs.)",
                 "Approved (Rs. lakh)"]
        st.dataframe(right_align(_t.style, _tnum),
                     hide_index=True, width="stretch")
        st.caption("Effective unit cost is total approved financial over total "
                   "approved physical for the grouped rows, converted to "
                   "rupees.")
        table_csv(top10, "nipun_top_line_items", "Top line items (CSV)")

        st.markdown("##### TLM spend by unit cost band")
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
                st.altair_chart(themed(ch_tlm), width="stretch")
            with cb2:
                btab = bsum.rename(columns={"band": "Band",
                                            "fin": "Approved (Rs. lakh)",
                                            "phy": "Students", "rows": "Rows"})
                st.dataframe(
                    btab.style.format({"Approved (Rs. lakh)": "₹{:,.1f}",
                                       "Students": "{:,.0f}"}),
                    hide_index=True, width="stretch")
                table_csv(btab, "nipun_tlm_unit_cost_bands", "Bands (CSV)")
            st.caption("Unit costs are stored in Rs. lakh in the annexures and "
                       "converted to rupees per student here.")
        else:
            st.info("No validated TLM rows in the current selection.")

# --------------------------------------------------- explore and compare
with tab_exp:
    all_states = sorted(BUDGET.state.dropna().unique())
    default_state = ("Uttar Pradesh" if "Uttar Pradesh" in all_states
                     else all_states[0])
    e1, e2, e3 = st.columns([3, 1, 1])
    sel_states = e1.multiselect(
        "States / UTs", all_states, default=[default_state],
        key="exp_states",
        help="Pick one for the full annexure and narrative. Pick two or "
             "more to compare them side by side.")
    if not sel_states:
        sel_states = [default_state]
    yrs_avail = [y for y in YEARS
                 if ((BUDGET.state.isin(sel_states)) & (BUDGET.year == y)).any()]
    yrs_avail = yrs_avail or YEARS
    sel_year = e2.selectbox("AWP&B year", yrs_avail,
                            index=len(yrs_avail) - 1, key="exp_year")
    measure = e3.selectbox("Measure", ["Final Approved Outlay", "Proposal"],
                           key="exp_measure")
    mcol, vmask = (("approved_financial_lakh", ACT_MIN.a_valid)
                   if measure == "Final Approved Outlay"
                   else ("proposed_financial_lakh", ACT_MIN.p_valid))

    # ------------------------------------------------ single state detail
    if len(sel_states) == 1:
        sel_state = sel_states[0]
        s_act = ACT_MIN[(ACT_MIN.state == sel_state) & vmask]

        with section(f"{sel_state} across the years", "navy"):
            trend = (s_act.groupby("year")[mcol].sum()
                     .reindex(YEARS).rename_axis("year").reset_index())
            spark = (alt.Chart(trend)
                     .mark_bar(color=CSF_BLUE, cornerRadiusTopLeft=4,
                               cornerRadiusTopRight=4, size=34)
                     .encode(x=alt.X("year:N", title=None, sort=YEARS),
                             y=alt.Y(f"{mcol}:Q", title="Rs. lakh"),
                             tooltip=[alt.Tooltip("year:N", title="Year"),
                                      alt.Tooltip(f"{mcol}:Q", title="Rs. lakh",
                                                  format=",.1f")])
                     .properties(height=190))
            st.altair_chart(themed(spark), width="stretch")
            have_yrs = [y for y in YEARS
                        if trend.set_index("year")[mcol].get(y, 0) > 0]
            gap_yrs = [y for y in YEARS if y not in have_yrs]
            qual = sorted(set(ACT_MIN[ACT_MIN.state == sel_state].quality))
            st.caption(
                f"Validated NIPUN figures by year for {sel_state}. "
                f"Data available for {', '.join(have_yrs) if have_yrs else 'no years'}"
                + (f"; no usable data for {', '.join(gap_yrs)}" if gap_yrs else "")
                + (f". Extraction quality {', '.join(qual)}." if qual else "."))
            table_csv(trend.rename(columns={"year": "Year",
                                            mcol: f"{measure} (Rs. lakh)"}),
                      f"nipun_{sel_state}_by_year".replace(" ", "_"),
                      "This trend (CSV)")

            sub = BUDGET[(BUDGET.state == sel_state) & (BUDGET.year == sel_year)]
            doc_choices = sub.doc_label.unique().tolist()
            show_docs = st.multiselect("Documents", doc_choices,
                                       default=[d for d in doc_choices
                                                if d.startswith("Minutes")] or doc_choices,
                                       key="exp_docs")
            sub = sub[sub.doc_label.isin(show_docs)]

        with section(f"The {sel_year} annexure, as printed", "plain"):
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
                if src in RECOVERED_SOURCES:
                    note = ("read from an archived copy of the original upload, "
                            "because the file now on the portal was re-uploaded at "
                            "a resolution too low to read")
                    if pd.notna(url) and url:
                        st.caption(f"{src} · {note} · "
                                   f"[current portal file]({url})")
                    else:
                        st.caption(f"{src} · {note}")
                elif pd.notna(url) and url:
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
                    "Grades named": doc.scope,
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
                       .apply(lambda r: [f"font-weight:700; background-color:{CHALK}"
                                         if is_total[r.name] else "" for _ in r], axis=1))
                st.dataframe(sty, hide_index=True, width="stretch")
                table_csv(table, src[:-4] if src.endswith(".pdf") else src,
                          "This annexure (CSV)")

            narr = NARRATIVE[(NARRATIVE.state == sel_state)
                             & (NARRATIVE.year == sel_year)]
            if len(narr):
                has_meta = "scope" in narr.columns

                def render_excerpt(r):
                    head = (f" · *{r.section_heading}*"
                            if pd.notna(r.section_heading) and r.section_heading
                            else "")
                    st.markdown(f"**p.{r.pdf_page}**{head}")
                    if has_meta and getattr(r, "text_quality", "ok") == "low":
                        st.caption("⚠ scanned text of low quality, read with care")
                    txt = str(r.excerpt).replace("*", r"\*").replace("_", r"\_")
                    txt = re.sub(r"(n[il1]pun[a-z]*|foundational\s+l[ei]\w+)",
                                 lambda m: f"**{m.group(0)}**", txt, flags=re.I)
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

    # --------------------------------------------------- multi-state view
    else:
        with section("Selected states across the years", "navy"):
            multi = (ACT_MIN[vmask & ACT_MIN.state.isin(sel_states)]
                     .groupby(["state", "year"])[mcol].sum().reset_index())
            line = (alt.Chart(multi)
                    .mark_line(point=True, strokeWidth=2.5)
                    .encode(x=alt.X("year:N", title=None, sort=YEARS),
                            y=alt.Y(f"{mcol}:Q", title="Rs. lakh"),
                            color=alt.Color("state:N", title=None,
                                            scale=alt.Scale(range=SERIES)),
                            tooltip=[alt.Tooltip("state:N", title="State/UT"),
                                     alt.Tooltip("year:N", title="Year"),
                                     alt.Tooltip(f"{mcol}:Q", title="Rs. lakh",
                                                 format=",.1f")])
                    .properties(height=380))
            st.altair_chart(themed(line), width="stretch")
            st.caption(f"{measure} by year for the selected states. A gap in a "
                       f"line means no usable data for that state-year, not a "
                       f"zero approval. See Data Quality for why.")
            wide = (multi.pivot(index="state", columns="year", values=mcol)
                    .reindex(columns=YEARS).round(2).reset_index(names="State / UT"))
            st.dataframe(right_align(as_text(wide, YEARS, ",.2f").style, YEARS),
                         hide_index=True, width="stretch")
            table_csv(wide, f"nipun_selected_states_{measure}".replace(" ", "_"),
                      "This comparison (CSV)")

    # ------------------------------------------- ranking, both modes
    with section(f"Ranking for {sel_year}", "blue"):
        r1, r2 = st.columns([3, 1])
        cats = r1.multiselect("Activity heads", CAT_ORDER, default=CAT_ORDER,
                              key="exp_cats")
        scope_all = r2.toggle("Show all states", value=(len(sel_states) == 1),
                              key="exp_all",
                              help="Off ranks only the states selected above")
        rank_mask = vmask & (ACT_MIN.year == sel_year) & ACT_MIN.category_base.isin(cats)
        if not scope_all:
            rank_mask &= ACT_MIN.state.isin(sel_states)
        comp = (ACT_MIN[rank_mask].groupby("state")[mcol].sum()
                .sort_values(ascending=False).reset_index())
        comp = comp[comp[mcol] > 0]
        if len(comp):
            # computed in pandas rather than a Vega expression so state names
            # carrying quotes or ampersands cannot break the encoding
            comp["highlight"] = comp.state.isin(sel_states).map(
                {True: "selected", False: "other"})
            ch3 = (alt.Chart(comp)
                   .mark_bar(cornerRadiusEnd=2, size=14)
                   .encode(y=alt.Y("state:N", sort="-x", title=None,
                                   axis=alt.Axis(labelOverlap=False, labelLimit=220)),
                           x=alt.X(f"{mcol}:Q", title="Rs. lakh"),
                           color=alt.Color(
                               "highlight:N", legend=None,
                               scale=alt.Scale(domain=["selected", "other"],
                                               range=[CSF_BLUE, "#c9d6e8"])),
                           tooltip=[alt.Tooltip("state:N", title="State/UT"),
                                    alt.Tooltip(f"{mcol}:Q", title="Rs. lakh",
                                                format=",.1f")])
                   .properties(height=max(280, 22 * len(comp))))
            st.altair_chart(themed(ch3), width="stretch")
            st.caption("Validated rows from primary minutes (or its addendum, for "
                       "the few state-years with no minutes on file). States "
                       "absent here either had no usable data for this year or "
                       "approved nothing under the selected heads.")
            table_csv(comp.rename(columns={"state": "State / UT",
                                           mcol: f"{measure} (Rs. lakh)"}),
                      f"nipun_{sel_year}_{measure}".replace(" ", "_"),
                      "This ranking (CSV)")
        else:
            st.info("No validated rows for this year under the selected heads.")

# ---------------------------------------------------------------- quality
with tab_qual:
    with section("Coverage", "navy"):
        st.markdown("##### Which state-years have usable data")
        st.caption("A cell counts as covered when at least one document for that "
                   "state and year produced NIPUN budget rows. ◇ means the data "
                   "came from a companion document (addendum or annexure volume) "
                   "rather than the minutes themselves.")
        st.caption(f"**Reading the marks** {QUALITY_KEY}")
        marks = {"✓ Clean": "✓", "✓ Clean (vision-verified)": "✓",
                 "◐ OCR, verify numbers": "◐", "◔ Partial": "◔"}
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
        m2.metric("Parsed clean", f"{int(counts.get('✓', 0))}",
                  help="Parsed cleanly from the document text, or hand-read off "
                       "the rendered page and reconciled against its printed "
                       "totals")
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
                      "Partial": STATUS["serious"], "Companion doc": CSF_BLUE,
                      "Missing": STATUS["critical"]}
        chq = (alt.Chart(py)
               .mark_bar(size=30, stroke=CARD, strokeWidth=2)
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
                  "◔": STATUS["serious"], "◇": CSF_BLUE,
                  "✗": STATUS["critical"]}
        sty = grid.style.map(lambda v: f"color:{colors.get(v, INK)}; "
                                       f"font-weight:700; text-align:center")
        st.dataframe(sty, width="stretch", height=38 * len(grid))
        table_csv(grid.reset_index(names="State / UT"), "nipun_coverage_grid",
                  "Coverage grid (CSV)")

        with st.expander(f"Why cells are missing ({int(counts.get('✗', 0))})"):
            st.caption("Three causes. The ministry never published that year's "
                       "minutes on its portal (checked against the Wayback "
                       "Machine archive too), or the published file is an "
                       "unreadable scan, or the scan was legible enough to find "
                       "the annexure but not to recover any activity line, "
                       "leaving only a garbled total.")
            def safe_name(s):
                return re.sub(r"[^A-Za-z0-9&]+", "-", s).strip("-")
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
                        # some of these scans did yield rows, but only unusable
                        # total lines with no recoverable activity detail
                        stub = BUDGET[BUDGET.source_file.isin(matches)]
                        if len(stub):
                            reason = ("annexure located but no activity line "
                                      "could be recovered, only "
                                      f"{len(stub)} unusable total row(s)")
                        else:
                            reason = "document exists but is unreadable, " + \
                                     ", ".join(sorted(set(x for x in sts if x)))
                    else:
                        reason = "never published on the ministry portal"
                    reasons.append({"State / UT": s, "Year": y, "Reason": reason})
            rsn = pd.DataFrame(reasons)
            st.dataframe(rsn, hide_index=True, width="stretch")
            table_csv(rsn, "nipun_missing_cell_reasons", "Reasons (CSV)")

        with st.expander("Files needing attention"):
            flg = LOG[~LOG.status.isin(["ok", "ok(vision-verified)",
                                        "no-nipun-found"])].copy()
            flg["quality"] = flg.status.map(STATUS_LABEL).fillna(flg.status)
            fcols = ["source_file", "quality", "total_check", "budget_rows",
                     "source_url"]
            st.dataframe(flg[fcols], hide_index=True, width="stretch",
                         column_config={"source_url": st.column_config.LinkColumn(
                             "Source PDF", display_text="open")})
            table_csv(flg[fcols], "nipun_files_needing_attention",
                      "Flagged files (CSV)")
        with st.expander("Full processing log"):
            st.dataframe(LOG, hide_index=True, width="stretch")
            table_csv(LOG, "nipun_processing_log", "Processing log (CSV)")

    with section("Reconciliation", "amber"):
        st.markdown("##### Do the published rows add up to the printed total")
        st.caption("For every document that prints a NIPUN subtotal, this re-adds "
                   "the validated rows that figure is supposed to cover and "
                   "compares them with it. Rows budgeted under a head the "
                   "subtotal does not span are left out, and where the annexure "
                   "totals PMU separately its PMU lines are left out too. It is "
                   "recomputed on load, so a row added or duplicated after "
                   "extraction shows up here rather than sitting silently in the "
                   "headline.")
        rec_yr = st.selectbox("AWP&B year", YEARS, index=len(YEARS) - 1,
                              key="rec_year")
        printed = LOG.set_index("source_file")["fln_total_printed_approved"]
        _rec_src = ACT_MIN[(ACT_MIN.year == rec_yr) & ACT_MIN.a_valid]
        rec = []
        for src, g in _rec_src.groupby("source_file"):
            pv = printed.get(src)
            keep = ~g.outside_block
            if src in PMU_OUTSIDE:
                keep &= ~g.is_pmu_row
            summed = g.loc[keep, "approved_financial_lakh"].sum()
            rec.append({"State / UT": g.state.iloc[0],
                        "Rows covered": int(keep.sum()),
                        "Sum of those rows": round(summed, 2),
                        "Printed total": round(pv, 2) if pd.notna(pv) else None,
                        "Difference": round(summed - pv, 2) if pd.notna(pv) else None})
        rdf = pd.DataFrame(rec).sort_values("State / UT")
        if len(rdf):
            def verdict(d):
                if pd.isna(d):
                    return "no printed total captured"
                if abs(d) <= 0.02:
                    return "closes exactly"
                return "does not close"
            rdf["Check"] = rdf["Difference"].map(verdict)
            n_close = int((rdf.Check == "closes exactly").sum())
            n_open = int((rdf.Check == "does not close").sum())
            n_none = int((rdf.Check == "no printed total captured").sum())
            r1, r2, r3 = st.columns(3)
            r1.metric("Close on the printed total", n_close)
            r2.metric("Do not close", n_open,
                      help="A gap here means the rows shown and the printed "
                           "subtotal disagree, so at least one of them is wrong")
            r3.metric("No printed total to check against", n_none,
                      help="Usually a scan where the subtotal line itself was "
                           "not recoverable")
            if n_open:
                st.warning(f"{n_open} document(s) in {rec_yr} do not reconcile. "
                           "Treat those state totals as unconfirmed.")
            _num = ["Sum of those rows", "Printed total", "Difference"]
            rdisp = as_text(rdf, ["Sum of those rows", "Printed total"],
                            ",.2f", "not captured")
            rdisp = as_text(rdisp, ["Difference"], "+,.2f", "not captured")
            st.dataframe(
                right_align(
                    rdisp.style
                    .map(lambda v: f"color:{STATUS['critical']}; font-weight:700"
                         if v == "does not close" else
                         (f"color:{STATUS['good']}" if v == "closes exactly"
                          else f"color:{MUTED}"), subset=["Check"]), _num),
                hide_index=True, width="stretch", height=38 * min(len(rdf) + 1, 20))
            table_csv(rdf, f"nipun_reconciliation_{rec_yr}",
                      "Reconciliation (CSV)")

    with section("Verification tiers", "emerald"):
        st.markdown("##### How each published number was confirmed")
        st.caption("Every published number carries how it was confirmed. "
                   "Arithmetic means Physical times Unit Cost reproduces the "
                   "printed Financial. Totals chain means the value closes "
                   "against printed totals. Vision means the figure was read "
                   "off the rendered page, and vision-verified means it was "
                   "also reconciled against a printed total. Manual recovery "
                   "covers the handful rebuilt from a companion document. "
                   "Unverified means no independent check has been recorded "
                   "for that side.")
        tiers = pd.concat([
            ACT_MIN.loc[ACT_MIN.proposed_financial_lakh.notna(), "p_verified"],
            ACT_MIN.loc[ACT_MIN.approved_financial_lakh.notna(), "a_verified"],
        ]).replace("", "unverified").value_counts()
        if len(tiers):
            tdf = tiers.rename_axis("tier").reset_index(name="values")
            total_sides = int(tdf["values"].sum())
            tdf["share"] = (tdf["values"] / total_sides * 100).round(1)
            # every side carries some tier, so a "verified out of total" count
            # always reads 100 percent and says nothing about confidence. What
            # matters is which tier, so report the mix instead.
            TIER_RANK = {"vision-verified": "read off the page",
                         "vision": "read off the page",
                         "manual-recovery": "read off the page",
                         "totals-chain": "closes against printed totals",
                         "arithmetic": "internal arithmetic only",
                         "unverified": "not yet adjudicated"}
            tdf["strength"] = tdf.tier.map(TIER_RANK).fillna("other")
            STR_ORDER = ["read off the page", "closes against printed totals",
                         "internal arithmetic only", "not yet adjudicated"]
            by_strength = (tdf.groupby("strength")["values"].sum()
                           .reindex(STR_ORDER).dropna())
            v1, v2 = st.columns([3, 2])
            with v1:
                bs = by_strength.rename_axis("strength").reset_index(name="sides")
                bs["share"] = (bs.sides / total_sides * 100).round(1)
                ch_t = (alt.Chart(bs)
                        .mark_bar(cornerRadiusTopRight=2, cornerRadiusBottomRight=2)
                        .encode(
                            y=alt.Y("strength:N", sort=STR_ORDER, title=None),
                            x=alt.X("sides:Q", title="Published numeric sides"),
                            color=alt.Color("strength:N", sort=STR_ORDER,
                                            legend=None,
                                            scale=alt.Scale(
                                                domain=STR_ORDER,
                                                range=[STATUS["good"], CSF_BLUE,
                                                       STATUS["warning"],
                                                       STATUS["critical"]])),
                            tooltip=[alt.Tooltip("strength:N", title="Evidence"),
                                     alt.Tooltip("sides:Q", title="Sides"),
                                     alt.Tooltip("share:Q", format=".1f",
                                                 title="Share of published")])
                        .properties(height=170))
                st.altair_chart(themed(ch_t), width="stretch")
            with v2:
                direct = int(by_strength.get("read off the page", 0)
                             + by_strength.get("closes against printed totals", 0))
                st.metric("Checked against the source",
                          f"{direct / total_sides * 100:.0f} percent",
                          help=f"{direct:,} of {total_sides:,} published sides "
                               f"were either read off the rendered page or close "
                               f"against a printed total. The rest rely on "
                               f"internal arithmetic, which catches a mistyped "
                               f"digit but not a value copied from the wrong "
                               f"column")
                st.caption("Arithmetic alone is the weakest tier. It confirms "
                           "Physical times Unit Cost equals Financial, which a "
                           "whole row lifted from the wrong column can still "
                           "satisfy.")
            with st.expander("Tier detail"):
                tshow = tdf[["tier", "values", "share", "strength"]]
                st.dataframe(tshow, hide_index=True, width="stretch")
                table_csv(tshow, "nipun_verification_tiers", "Tier detail (CSV)")

    with section("Certified accuracy", "plain"):
        try:
            import json as _json
            rep = _json.load(open("accuracy_report.json", encoding="utf-8"))
            stamp = _dt.date.fromtimestamp(
                _os.path.getmtime("accuracy_report.json")).strftime("%d %B %Y")
            st.markdown("**Stratified sample, Wilson 95 percent lower bounds**")
            st.caption(
                f"Measured on a sample drawn {stamp}. Two systematic sweeps, the "
                "2026-27 rebuild and the 2023-24 and 2022-23 cleaning passes all "
                "landed after that date, so these bounds describe the workbook as "
                "it stood then, not as it is published today. Every error the "
                "sample turned up was corrected here, and the passes since have "
                "corrected many more, so they read low rather than high. A fresh "
                "round has not yet run.")
            acc = pd.DataFrame(rep)
            st.dataframe(acc, hide_index=True, width="content")
            table_csv(acc, "nipun_accuracy_certification", "Accuracy sample (CSV)")
        except Exception:
            st.caption("Certification measurement not yet run.")

        st.divider()
        st.caption(BUILD_NOTE)
