# The ICT extraction (PAB x UDISE+ workbook)

A second extraction over the same corpus. Everything in the other docs applies; this is what is ICT-specific.

Part of the PAB project. The operating rules are in `../CLAUDE.md`; this file is the detail behind them.

---

## The ICT extraction (PAB × UDISE+ workbook)

A second extraction over the SAME pdfs/ corpus, populating the spec at
`Copy of [WIP]_PAB-UDISE mapping for ICT across years.xlsx` as a fresh
generated workbook. Plan and locked decisions: `ICT_PAB_UDISE_scrape_plan.md`.
Everything in §1-§17 applies (same documents); what follows is ICT-specific
structure learned by reading pages, not guessable from the spec.

### Every recent minutes PDF carries TWO ICT tables, with different jobs
1. **The costing sheet** ("State Proposal" / "Recommended by DoSEL"
   columns) — current-year proposed and approved. This is the block the
   NIPUN extraction's sibling lives in.
2. **The "Non Recurring Activities Report"** (columns Total Approval
   Phy/Fin, Total Completed Phy/Fin, Min. Surr. Qty/Amt, Cancelled
   Amount, Balance Amount) — the spillover/execution report. Per the
   spec's off-by-one rule, PAB year Y's report fills year **Y-1**'s
   execution and closing-spillover columns. A state whose costing sheet
   is a scan can still have a fully digital execution report (Delhi
   2026-27: report on p17 text-layer, costing sheet p70 scan).

### The 2026-27 costing sheet stacks modified values INSIDE cells
Where 2025-26 printed three proposal columns (§12), 2026-27 prints two
sides but can stack TWO value triples inside one cell. The page-top
legend names the highlights: yellow = Post PAB New Values, lilac =
Modify PAB Values, green = Less Fund Recommended, pink = Recommended is
0. The printed subtotal uses the lilac (modified) value — but do not key
on colour: capture both triples and let subtotal reconciliation pick the
participating one (`ict_extract_2627.py` does exactly this, brute-forcing
stacked combinations against each printed subtotal).

### Level and nature are printed per block, not per code
"upto Highest Class VIII" = Elementary, "upto Highest Class XII" =
Secondary, on the sub-component heading; the numeric prefixes (1.5.6 /
2.3.5 on AP) vary by state. R/NR is a marker column between the label
and the numbers in variant A; in the execution report it rides inside
the heading text ("- NR").

### Component identification (for the five ICT sheets)
- ICT Lab = "Digital Hardware & Software (Type - I)" banded by enrolment
  (El: C442/C443/C444; Sec: C2385/C2381/C2340), "Additional ICT Lab"
  (C2382 existing / C4698 new), + recurring "Recurring Cost (ICT &
  Digital Initiatives) (Option - I)" (C447 El / C2343 Sec).
- Smart Classroom = "Smart Classroom (Type - II)" NR (C439 El / C2384
  Sec) + "Smart Classroom (Recurring)" (C449 El / C2344 Sec). The
  source prints unit ₹2.4 lakh per SCHOOL for 2 rooms; units printed are
  schools ("(Recuring)" typo is in the source — keep verbatim).
- Digital Library usually has no standalone budget line; where it does
  it can hide under Innovation Projects (Delhi 2026-27: "Digital
  Library( C4358 )" under Funds for Quality → Innovation -NR), i.e.
  OUTSIDE the ICT block — the §15/§16.3 outside-the-anchored-block
  pattern again. Virtual Reality Lab (C4777) likewise.

### 2026-27 costing-sheet layout census (36 states)
26 states parse from the text layer with variant A headers. The 10
NIPUN vision-rebuilt states (Chandigarh, Chhattisgarh, Delhi, Goa,
Gujarat, Lakshadweep, Maharashtra, Nagaland, Odisha, Puducherry) have
scanned costing sheets here too — their NIPUN Budget rows' pdf_page
values locate the annexure ballpark. Gujarat is the exception worth
remembering: its costing sheet IS digital but uses a different header
vocabulary ("Proposed Physical Qty." / "Recom. Financial Amt.") and
"Subtotal (ICT and Digital Initiatives)" with parentheses, plus
"ICT( C4953 )" spacing that defeats a `\(C\d+\)` regex. Lakshadweep has
zero ICT mentions in its text layer — possible genuine no-ask, confirm
by vision before recording it as such.

### Parser geometry that had to be learned
Column x-centres must come from each page's own header words (Phy /
Unit / Amount twice); header words are CENTRED in wide columns, so cell
content starts ~50pt left of the "Sub Activity" header word — anchor
windows on the header but widen leftward. Subtotal labels wrap onto
continuation lines that carry the VALUES ("Subtotal of Digital Hardware
& Software (up to" / "Highest Class VIII) - NR: 1139 ..."), so a
subtotal row must stay open until the next activity/subtotal starts —
flushing it on its first line loses every wrapped subtotal's figures.
Two more, found closing the last 20 reconciliation failures:
- **Some states print no "N -" numbering on activity rows** (Haryana,
  MP, Punjab, Rajasthan). There the R/NR marker word, which appears only
  on an activity row's first line, is the row-start signal.
- **A block's first activity rows inherit the PREVIOUS block's level**
  until the wrapped "Highest Class VIII/XII" heading catches up (Tamil
  Nadu p70 mis-levelled its Secondary Type-I lines as Elementary this
  way). The closing sub-block subtotal's own label prints the class
  span, and it OVERRIDES the running page context for its group; the
  block total ("Subtotal of ICT and Digital Initiatives") names no span
  and overrides nothing. With both fixes: 232/232 sub-block
  reconciliations green across the 26 text-layer states.

### The 2025-26 documents: four table types and two Budget Demand variants
`ict_extract_2526.py` covers the year's costing sheets. What had to be
learned:
- The "Budget Demand" sheet comes in a THREE-group variant (State
  Proposal (Initial) / (Modified) / Recommended by DoSEL — AP, Bihar…)
  and a TWO-group variant (Proposed by State / Recommended — Karnataka,
  Haryana, HP, UP, WB…). Activity rows are "N-Label" single words; the
  §12 modified-else-initial rule is verified per Sub Total (AP Secondary
  ICT: 4044.00 initial-only + 1489.98 modified = printed 5533.98).
- Sub Total / "Total of X" boundary lines must be found by re.SEARCH
  over the whole left zone: heading-column residue ("VIII)", "5.8.1 -")
  prefixes them, and long labels start inside the heading columns. A
  missed "Sub Total" attaches its values to the open activity row; a
  missed "Total of X" lets foreign Sub Totals pile into the next
  segment. Both bugs produced plausible-looking wrong rows before the
  fix; with it, 263/264 ICT sub-block reconciliations close.
- The single open failure resolved itself through the alt copy: **UP
  2025-26 p47 prints a 5.8.1 Sub Total whose proposed side (32023 /
  18872.05) exceeds its own two printed rows by 1545 / 633.45 — and the
  revised download (`minutes_23722.pdf` p27) prints the missing row as
  its own line, a modified-stage Recurring Cost proposal of 633.45 with
  no approved side.** 633.45 + 8438.40 + 9800.20 = 18872.05 exactly. A
  primary document can omit a row from its own table while counting it
  in the printed subtotal, with the revised copy carrying the full
  block — check alt copies before declaring a §9 inconsistency.
  build_ict_workbook.py's document selection therefore prefers, per
  (state, year, level, nature) sub-block: approved side populated, then
  MORE rows, then minutes > addendum > supplementary > alt.
- Several states' ICT costing sheet is NOT in their minutes: Delhi's
  minutes carry only a component summary (its annexure at p16 is a SCAN
  with an OCR layer — the "lnitiatives" lowercase-L tell); Assam, Goa,
  Kerala, Punjab, Tamil Nadu publish via addenda; Gujarat, Jharkhand,
  Rajasthan via alt copies. Extract from EVERY document and select at
  build time (the NIPUN Budget-sheet model).
- Assam, West Bengal and Lakshadweep made no new school-ICT ask in
  their 2025-26 Budget Demand at all — their ICT appears only in the
  year's spillover tables. 2025-26 has TWO spillover formats on top of
  the Budget Demand: "Spill Over - <State>" (Approved / Cummulative
  Spill Over / Actual Expenditure / Surrender / Spill Over) and
  "Spillover Report" (Code | Activity | Sub Activity | Approved /
  Expenditure / Surrender / Spillover, keyed by C-code). Neither is
  parsed yet.

### 2026-27 ICT is complete for all 36 states, anchored on the State Plan summary
Every 2026-27 minutes embeds a "Sub Component wise - State Plan
(F.Y. 2026-2027)" table — PRABANDH-generated, one row per sub-component
with proposed/recommended R, NR and Total. Its ICT row is the
verification anchor (`ict_verify_2627.py` →
`ict_2627_stateplan_check.csv`): **29 extracted states match it
exactly** (A&N within 0.01 — a §9 totals-round-against-components), and
it settles the rest without vision hunts: Chandigarh, Delhi, Goa and
Gujarat print ICT at 0.00; Lakshadweep, Nagaland and Puducherry's
summaries omit the ICT row entirely (they list only sub-components with
figures). Gujarat's summary also carries the "Approval / Expenditure
till Date (F.Y. 2025-2026)" retrospective whose ICT line (397.18)
matches our exec-report extraction to the paisa. Only three states
needed vision reads (Chhattisgarh p68/87, Maharashtra p61/82, Odisha
p71/92 — pages found by `find_ict_pages_ocr.py`); their rows are staged
in `ict_vision_2627.py` (self-verifying against the summary) and every
block closes. Notable prints: Odisha's C447 recurring unit cost is 0.60
(Rs 60,000/school), not the usual 2.40; Odisha proposes C439 at a
printed 0.00 for 555 units; MH C442 and OD C442/C443 stack yellow
Post-PAB values over plain zero rows and the subtotal uses the yellow.

### 2025-26 ICT is complete for all 36 states; the retrospective is CUMULATIVE
The last two gaps were vision reads staged in `ict_vision_2526.py`,
both closing on their printed totals: **Assam** (its entire budget is a
44-page scanned addendum whose Budget Demand carries El R 6950.54 and
Sec R 4001.00 → 3764.96, PLUS a separate "Supplementary Plan — F.Y.
2025-2026" section inside the same file with its own Sec NR ICT block,
17891.50 → 8978.10) and **Delhi** (ICT lives only in its scanned
supplementary volume, 28152.98 → 7455.60; its minutes p16 is a
spillover annexure, "Details of Spill over As on 31st March 2025", not
a costing sheet — useful later for opening-spillover columns). Delhi's
supplementary Smart Classroom line counts CLASSROOMS (9211 classrooms
in 969 schools), the §1.4 unit trap in the wild. West Bengal and
Lakshadweep confirmed no-new-ask (digital Budget Demands, no ICT
block). **Do not verify 2025-26 costing against the 2026-27
retrospective table**: unlike NIPUN (§16), the ICT line there is
CUMULATIVE approvals-to-date including carried spillover, not the
year's new approval — Gujarat retro 397.18 = 278.10 new + 119.08
carried, and it equals the exec report's cumulative Total Approval
exactly (Delhi 12333.16 ≈ 12333.17). It therefore cross-checks the
EXEC extraction, and it did.

### 2024-25 "text" documents are scans wearing doubled OCR layers
30 of 35 2024-25 minutes report 60-150k chars of text, and it is not
trustworthy: the layer holds every word TWICE at near-identical
positions, one render and one OCR guess ("Netaji"/"Netoji",
"37.3"/"3/.3", "0.75"/"0./S") — §2's ministry-OCR warning in a new
costume. Numbers must be vision-read off renders for this year;
the text layer is a locator only. Consistent with NIPUN's 2024-25
being 88% unanchored. The 5 pure scans are AR, MN, MZ, NL, SK.
Rajasthan 2024-25 has NO minutes file at all — only two addendum
downloads.

### The 2025-26 spillover formats, parsed
`ict_extract_spill_2526.py`. Format A "Spill Over - <State>" (18
states): four (Financial, Physical) pairs — Cummulative-Spill-Over-
Approved / Actual Expenditure / Surrender / Spill Over. Format B
"Spillover Report" (11 states): C-code-keyed rows, four (Qty., Amt.)
pairs; the column centres must come from the Qty./Amt. header words —
keying on the "Minsitry"/"Minstry" (sic) labels puts surrender ~30pt
off and fails every row. The reconciliation gate is the per-row
identity approved − expenditure − surrender = spillover, which 269/270
ICT-family rows satisfy (the 48 genuine failures are all in Teacher-
Education blocks with yet another sub-layout, unparsed). These tables
carry the 2024-25 execution/closing position.

### The "Automated Filled Claude_ICT Lab" reference sheet's defect classes
Diffed against the reconciled extraction (2026-27, ICT Lab NR): exact
agreement on most states (Karnataka, Ladakh, Sikkim, Telangana, UP
Elementary, MP Secondary...), and two systematic defect classes where it
disagrees — (1) it took the superseded value of a stacked Modify-PAB
cell (AP proposed El: ref 887.3 = using C442's pre-modification 307.50;
the printed subtotal uses 582.50 → 1162.30); (2) it missed lines
belonging to the component (TN's "Additional ICT Lab (Enrolment > 700)
New", Punjab and UP Secondary under-captures). Same §16 discipline: use
it to LOCATE suspect rows, never to source values.

### 2024-25 is NOT the all-scan year it was written up as
The note above ("30 of 35 2024-25 minutes report 60-150k chars and it is
not trustworthy") is true of a subset, not the year. A page census on
2026-08-18 found **21 of 36 documents carry a fully digital PRABANDH
Budget Demand** with a real `Total of ICT and Digital Initiatives` line
in the text layer, geometry as clean as 2025-26's. Four states read by
vision (Gujarat p52/59, Odisha p47/54, Telangana p56-58, Haryana
p47/56-57) had **every** printed total confirmed to the paisa against
their own text layer afterwards, so on those documents the layer is
sound. Census in one pass:

```python
'Total of ICT and Digital Initiatives' in t and 'Budget Demand' in t
```

Consequence: **the year is largely scriptable.** `ict_extract_2526.py`
is now year-parameterised (`python -X utf8 ict_extract_2526.py 2024-25`,
output `ict_2425_extract.csv` / `_recon.csv`) and parses the 2024-25
two-side Budget Demand with no layout changes at all, 97/97 sub-block
reconciliations green over 17 states. Vision reading is still required
for the pure scans, and vision reads of a digital state remain worth
doing as a free cross-check, but do not budget a vision campaign for the
whole year before running the census.

### The doubled OCR layer is separable on word HEIGHT, and it silently killed whole states
§18 already warns that the 2024-25 text layer holds every word twice.
What it does not say is the consequence for a parser: **the duplication
reaches the labels**, so a block boundary reads `Total Total of of ICT
ICT and and Digital Digital Initiatives Initiatives` and an
`ICT\s+and\s+Digital` segment gate never fires. Jharkhand, Uttarakhand,
Tamil Nadu, Andhra Pradesh and Bihar's Elementary block all parsed
cleanly and were then **discarded without a trace** — no recon row, no
error, just a state absent from the output.

The two layers separate reliably on **word height**. The render layer
sets every word of a row at one exact y0 and one exact height (11.0 pt
on every 2024-25 page seen) while the OCR layer jitters each box, so
bucketing by height and taking the bucket with the fewest distinct y0
values per word picks the render layer every time (coherence 5.3-7.1
against 2.6-3.3) — **including where the OCR layer is the larger
bucket**.

Score it over the whole Budget Demand section, **never per page**: on a
remark-heavy page the render layer can be 66 of 647 words (Uttarakhand
p74), and any per-page size floor throws it away along with that page's
Sub Total. Decide whether a document is doubled at document level too,
on the **median** — Bihar's p49 scores 0.299 against a per-page
threshold of 0.30 while its neighbours run 0.31-0.36, and that one page
carries the state's whole Elementary ICT block. Clean 2025-26 pages
score a flat 0.000, so the test is unambiguous.

Implemented in `ict_extract_2526.py` as `dup_fraction(page)` (share of
words repeating at near-identical coordinates: a flat 0.000 on clean
2025-26 pages, 0.27-0.36 on doubled 2024-25 ones), `render_height(doc,
pages)` (picks the winning height bucket over the whole Budget Demand
section) and `page_rows_doubled(page, height)`.

**Proximity clustering is not a substitute.** The obvious fix — widen
the row band until the two copies merge — cannot work: a heading-column
continuation line can sit 4 pt above the next activity row (Jharkhand
p41), so any tolerance wide enough to merge the layers also merges real
rows and pulls one activity's figures into another's.

### Check a scan's printed page numbers before concluding a block is absent
`Mizoram_2024-25_minutes.pdf` contains only the **odd** printed pages of
its Budget Demand (PDF p25 is "Page no 1 of 48", p26 is 3, … p47 is
45). Half the sheet was never scanned. The tell is a component ending
mid-block on one page while the next page opens midway through a
component two numbers later. Mizoram's Elementary ICT block survives
only by luck, printing entirely on one odd page; its Secondary block
would sit on printed page 38 and is simply not in the file, and no
render DPI recovers it.

OCR the bottom band of each page for `Page no N of M` at the start of
any scan-based pass. It is one cheap loop and it distinguishes "the
state made no ask" from "we do not hold the page" — two conclusions
that look identical from inside the parser and mean opposite things.

### A state's only ICT line can be a Teacher Education line
Goa, Lakshadweep and Delhi print no school-ICT component at all in
2024-25, yet all three mention ICT on Budget Demand pages: Goa p32 and
Lakshadweep p33 under `1.2 - Technology Support to TEIs` (SCERT/DIET),
Delhi p84 for labs at the SCERT and 9 DIETs. Delhi additionally carries
a full ICT table at p18-20 that reads exactly like a live ask and is a
**prior-year spillover annexure**, not a costing sheet.

The reliable test for a genuine no-ask is to enumerate every
`Total of <component>` boundary line across the state's Budget Demand
pages and confirm `Total of ICT and Digital Initiatives` is not among
them. **The word "ICT" alone proves nothing.** The same test settles a
missing *level* rather than a missing state: Kerala prints no Secondary
ICT sub-component and Telangana no Elementary one.

### Two more genuine off-norm prints, and one OCR trap
Per §9, record as printed:

- *Nagaland 2024-25 Elementary* `Recurring Cost (Option - I) (Existing)`
  prints **0.38** lakh/school where the norm is 2.40, and its own remark
  confirms "at the unit cost as proposed by state".
- *Manipur 2024-25 Secondary* `Smart Classroom (Recurring) (Option - II)
  (New)` prints **2.40** where the norm is 0.38.

*Kerala 2024-25 p25* is §2 in miniature: its text layer renders the
Elementary block total as `384.44000` where the page prints
**354.44000**, and only the printed figure closes (44.84 + 309.60). Its
row 1 also carries a proposed 12 @ 0.38 with no approved side and a
remark saying the physical unit "is entered by mistake" and was folded
into the Smart Classroom line — the row still participates in its Sub
Total, so keep it.

### The label zone ends at the band's first FIGURE, not at `num_x0`
The costliest bug of this pass, and it is a geometry bug that
reconciliation cannot catch. `num_x0` is derived from the header as
`phys[0][0] - 25`. 2024-25 right-aligns its `Sub Total` label against
the figures, so on Haryana p57 "Sub" lands at x=346 and "Total" at
x=363.0 against a `num_x0` of **362.7** — a 0.3pt margin. Only "Sub"
reached the label zone, the `\bSub\s+Total\b` test failed, the boundary
went undetected, the label read `...(Option - II) (New) Sub`, and the
Sub Total's approved figure (1505.66) landed in the preceding activity's
empty Not-Recommended cell.

**Haryana Elementary still reconciled with two rows corrupted this
way**, because there the swallowed subtotal happened to equal the
activity's own value. That is §5 mode 3 in a new costume: the arithmetic
gate is necessary and not sufficient, and a clean recon line is not
evidence the rows beneath it are right.

The fix is to end the label zone at the band's own first number rather
than at a header-derived constant:

```python
band_nums = [w[0] for w in ws
             if NUM_RE.match(w[4]) and w[0] >= cols["num_x0"]
             and classify_col(w, cols)]
lab_x1 = min(band_nums) if band_nums else cols["num_x0"]
```

The `classify_col` test is load-bearing and so is the fallback. A first
attempt fell back to `remarks_x - 8`, which looks reasonable and is
wrong: the "Remarks" header word is **centred** over a wide column and
sits well right of where remark text actually starts, so on every
continuation band the label zone swallowed remark prose. That rewrote
**284 of the 2025-26 rows' labels** while leaving every figure and every
recon status untouched — invisible to the reconciliation gate, invisible
to the row count, caught only by diffing the CSV row by row against a
copy taken before the change.

**Copy the other year's output aside and diff it cell by cell whenever
you touch a shared parser.** Row count and recon totals both matched
exactly across that regression.

### Telangana 2024-25 prints no Elementary ICT block at all
Its Budget Demand carries only `3.7 - ICT and Digital Initiatives`
(Secondary). Confirmed by scanning every Budget Demand page for a
`\d+\.\d+ - ICT` heading, which is the cheap way to settle "is this
level missing or absent" and is worth running before hunting pages.

### A fourth spillover layout, in the 2024-25 minutes
Telangana's 2024-25 minutes embed a `Spill Over - Telangana` table for
**F.Y. 2023-2024** (p21) whose columns are neither of the two 2025-26
formats: Budget Approved (Cummulative) Physical/Financial | Cummulative
Progress (Since Inception) Complete / In-progress / Financial | Spill
Over In-progress / Not Started / Total / Financial. Digital text layer.
Unparsed; it carries the 2023-24 execution position.

### The UDISE+ national report volumes, and how to read them
`udise_pdfs/UDISE_<FY>.pdf`, 2021-22 to 2025-26, extracted by
`udise_extract.py` into `udise_ict.csv` (4,625 rows). These are clean
digital exports, real text layers with no OCR over a scan on any table
page, so **§2's warning does not apply to them** and nothing here needs
a vision read.

State-wise school-infrastructure figures live in two repeating table
shapes, each one page carrying exactly **37 rows, India plus 36 states
and UTs**:

- a 16-column `Total Schools | Schools with X | Percentage of Schools
  with X` block split five ways by management (Table 7.1 electricity,
  7.9 computer, 7.10 functional computer, 7.11 internet, x.6 smart
  classroom, x.8 digital library). Table 7.1's percentages sit on a
  separate `(continued)` page, cols 17-26.
- an 11-column Government / Government-Aided ICT-lab table (Table x.9).

**The India row is a printed reconciliation anchor** and the state
values close on it exactly for every count metric in every year, 70 of
70. A second, independent check is available and worth running: 1,993
printed percentages all agree with their own printed count and
denominator, which the sum check cannot reach.

Three things move between volumes and must be read off the page:

- the computers-and-digital section is **Section 10 in the 2021-22
  volume and Section 9 thereafter**, so 10.6/10.8/10.9 become
  9.6/9.8/9.9. Table 7.x numbering is stable.
- Table 7.10 gains "for pedagogical purpose" from 2022-23.
- **the ICT-lab table's scope oscillates** between "Upper Primary,
  Secondary and Higher Secondary sections" (2021-22, 2025-26) and
  "Middle and Secondary sections" (2022-23 to 2024-25). That moves the
  denominator, so the ICT-lab series is **not** a like-for-like trend
  across those boundaries. The app warns on it.

State spellings alternate between `&` and `and` by volume, and the
2025-26 volume reverses the merged UT to "Daman & Diu and Dadra & Nagar
Haveli". Always normalise.

**Do not parse these tables in reading order.** 2025-26's Table 9.6
prints its column-number band as `(1) ( ( ( (` — the digits are missing
from the printed page itself, confirmed on a 200 DPI render — and
Chandigarh's row there leaves a cell genuinely blank, so a sequential
reader silently shifts four values one column left. Read by **column
position**, taking centres from the complete India row, and attach row
labels by vertical span, because state names wrap over two lines with
the value line sitting between them.

Not extracted, but present in the same volumes if wanted: the four
non-"All management" columns of every std16 table, and Tables x.3
tablets, x.5 projector, x.7 mobile phones, x.1 desktops, x.2 laptops.
