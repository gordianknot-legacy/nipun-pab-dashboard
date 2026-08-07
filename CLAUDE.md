# NIPUN Bharat PAB extraction — working notes

Everything here was learned the hard way on real files. Read it before
starting a cleaning pass; most of it is not guessable from the code.

The deliverable is a workbook (`NIPUN_Bharat_PAB_master.xlsx`, sheets
Budget / Narrative / Log / Accuracy) and a Streamlit dashboard
(`deploy_dashboard/`, pushed to `gordianknot-legacy/nipun-pab-dashboard`,
live at nipun-pab.streamlit.app). The standard is **fidelity to print**:
publish what the page prints, flag what it cannot support, never invent.

---

## 1. The source files lie about their own quality

**Check file size against neighbouring years before believing a file is
unreadable.** In Oct 2025 the ministry migrated to `dsel-education.gov.in`
and re-uploaded some minutes downsampled to **72 DPI JPEG with no text
layer**. The signature is a **uniform ~6.1 MB across unrelated states in
one year** while the same states' other years are 12-35 MB.

Eleven files were affected across 2022-23 and 2023-24; the degraded copies
now live in `pdfs/lowres_2025_reupload/`. This is a bad migration, not bad
scanning, and it is recoverable.

**Do not trust the recovery script's WANT list as the census of affected
files.** *Manipur 2022-23* sat at exactly 6,139,904 bytes with every
annexure page a 280x162 pt page holding a 280x162 px bitmap, and it was
never in `fetch_2223_originals.py` — so it stayed unreadable for a year
while its Log row read `OK(reconciled)`. Recovered to 79.3 MB and, better
than the usual outcome, **fully digital with a real text layer**. Sweep
by file size across the whole year, not by the list someone wrote earlier:

```python
# any file within a few KB of 6.1 MB is a re-upload until proven otherwise
sum(1 for f in Path("pdfs").glob("*.pdf") if 6.0e6 < f.stat().st_size < 6.3e6)
```

**Recovery route.** The old `dsel.education.gov.in` copies survive in the
Wayback Machine, and `wayback_manifest.json` (from an earlier coverage
hunt) already holds their URLs. Fetch raw bytes via the `/web/<ts>id_/`
form — see `fetch_2324_originals.py` / `fetch_2223_originals.py`. Results
so far: 6.1 MB → 86-442 MB, 72 DPI → 200-300 DPI.

**Always verify pagination matches before swapping** (`len(doc)` old vs
new). It has matched every time so far, which is what lets existing
`pdf_page` references survive, but a mismatch would silently corrupt every
row's page reference.

### Some states have BOTH a damaged and an intact copy on disk
Where a `_NNNNN.pdf` variant exists it is sometimes the *good* one.
Himachal Pradesh 2023-24 has `..._minutes.pdf` at 6.1 MB (a re-upload,
parses to no NIPUN content) and `..._minutes_9001.pdf` at 194 MB (intact,
and what the workbook cites). Check sizes across variants before assuming
a state is unreadable, and cite the file you actually read in `SF`.

### Files that genuinely cannot be read
If the embedded image is small *in the original too*, stop. Rendering at
higher DPI only upscales a bitmap with no detail. Check with
`page.get_images(full=True)` and compute effective DPI as
`img_width / placed_width_pt * 72`. Do not guess values from arithmetic —
flag the state and say so.

---

## 2. The text layer is not trustworthy, even in good files

Many PDFs carry a **ministry-side OCR text layer**. It looks like a real
text layer to `page.get_text()` and it is wrong in ways that are
individually plausible:

- Assam 2023-24 capacity building: layer said `3275.37`, page prints
  `3215.37` — a 60 lakh error that would have closed nothing
- Renders `2023-2024` as `t2O23-2O24`, `Major` as `Maior`, `PARTICULARS`
  as `PARTICUIIIRS`
- Splits `123232` across lines as `7232 32`

Tell-tale: a page whose image covers >60% of its area but which also
reports text. **Read values off the rendered image.** The text layer is
useful only for *locating* the annexure, never for reading numbers.

---

## 3. Annexure schemas vary by state and year

Do not assume `86.x` / `87.x`. Observed:

| Layout | FLN block | PMU block | Seen in |
|---|---|---|---|
| Standard | `86.0.x` | `87.0.x` | most states |
| Short form | `86.1`, `86.2`, `86.4` | `87.1`, `87.2` | Meghalaya and Sikkim 2022-23 |
| Prabandh | `5.9.x`, `5.8.x`, `4.6.x` … | inside the FS subtotal | 2025-26, 2026-27 |
| Tripura 2023-24 | **`32.x`** | **`34.x`** | one file |
| Himachal 2023-24 | **`21.x`** | **`22.x`** | one file |
| Sl.No. layouts | running numbers (62-66, 86) | same sequence | Punjab, DN&DD |
| 2026-27 FS | no codes at all | folded into FS subtotal | vision-rebuilt states |
| Blank code column | block heading only (`86.0`, `87.0`) | same | Puducherry 2022-23 |

Assume nothing about numbering; read it off the page each time. What
matters downstream is only whether a `87.x`-style PMU marker exists, so
assign one when staging a layout that lacks it.

### Some annexures print only one side
Most print `PROPOSAL` and `FINAL APPROVED OUTLAY` side by side. **Kerala
2022-23 prints only `Final Approved Outlay`** — there are no proposal
columns on the page at all. Record the proposed side as null and say so in
the module docstring, or a later reader will treat the gap as a capture
failure and try to "restore" it. Check the column headers before
concluding a side was lost.

Consequences:

- `OUTSIDE_HEADS` in `dashboard.py` must **not** contain `32` — Tripura's
  NIPUN rows carry that prefix. This bug once made Tripura sum to zero
  against a printed 1564.56.
- For Sl.No. layouts, assign `86.0.x` / `87.0.x` codes when staging, so
  downstream scope detection works. Say so in the module docstring.

---

## 4. Reconciliation: compare like with like

The Log's `fln_total_printed_approved` is the anchor, but **its scope
varies**:

- The 86/87 schema totals FLN and PMU *separately*, so its printed FLN
  figure **excludes** PMU rows that the app still publishes.
- The 2026-27 FS layout folds PMU **into** the subtotal.

Decide per document: PMU is outside the FLN figure **iff** the document has
any `87.x` code *or* prints its own PMU total. Keying only on the printed
PMU total is not enough — Punjab 2022-23 has `87.x` rows but its PMU total
was never captured.

Also exclude heads that no NIPUN total covers: `102` (assessment at state
level), `36`, `37`, `38`, `106`, `134`, `77`, `79`, `48`.

Getting this wrong is expensive: a naive "sum everything vs the FLN total"
check reported 18 false failures on correct data.

### A missing anchor is usually a truncated LABEL, not a missing figure
Six 2022-23 documents (Assam, J&K, Karnataka, Odisha, Tamil Nadu, West
Bengal) reconciled fine yet carried no `fln_total_printed_approved`. In
every case the subtotal row existed with correct values, but its label had
been captured as `Total of Nipun` or `Total of Nipun Bharat`, and the
anchor regex requires the full `total of nipun bharat mission (fln)`. The
apply script then logged "no FLN subtotal row" and skipped the file.

**Repair the label, do not hardcode the figure into the Log.** Completing
the label makes the anchor regenerate itself on every future run; writing
the number in by hand leaves nothing to catch the next regression.

Sometimes the truncation is in the *source*: Karnataka's page genuinely
breaks the label across the p160/p161 boundary, printing "Total of Nipun
Bharat" then "Mission (FLN)". The capture was faithful; the anchor still
needed the full form. Either way the fix is the same.

### The source PDF sometimes clips its own cells
Distinct from OCR damage and from our capture. *Assam 2022-23 p194* prints
its grand total as `14973.` and `1426` — and the PDF's **text layer stores
exactly those truncated strings**, on a page with no images and no OCR
layer. *Tamil Nadu 2022-23 p885* clips its approved grand total to `6254`.
The document was generated that way; there is nothing further to read at
any DPI.

Record the chain, and say in the row's remark that the cell is clipped and
the figure is reconstructed. Check first that the *subtotal the
reconciliation anchors on* is fully printed — in both these cases it was,
so the reconciliation still rests on a real read.

**Before concluding a page is a scan, check image coverage.** `0 images,
0% coverage` means the file is digital and its text layer IS the source;
§2's warning is about OCR layers over scans and does not apply there.

**A subtotal is not the mission total.** `Sub Total (5.1.1 - Nipun Bharat
Mission (FLN))` excludes PMU; `Total of NIPUN Bharat Mission` includes it.
Manipur 2024-25 was wrongly called a defect on exactly this confusion.

---

## 5. How extraction fails (all seen in real files)

1. **Block end never detected** — activity rows fine, every total and the
   whole PMU block lost. *Chhattisgarh 2023-24 (+710 approved), Kerala
   (+302), Gujarat 2022-23.*
2. **Block entered, one middle row survives** — everything above and below
   lost. *Maharashtra 2023-24 published 182.91 against a printed 20085.86;
   Rajasthan 2023-24 published 208.44 against 14740.59.* Both were
   **text-layer files** — this is not an OCR problem.
3. **Wrong values that look plausible** — *Nagaland 2023-24 held 15.410
   and 308.200 where the page prints 15.414 and 308.28, with no approved
   side at all.* Arithmetic cannot catch these.
4. **Duplicate rows re-inserted after a rebuild** — see §6.
5. **Same printed line captured twice** — usually from an embedded OCR
   layer; check the document's own sub-totals to decide (if a row really
   appeared twice, the subtotal would be double).
6. **Proposed total copied into the approved column** — *UP 2021-22 was
   flagged for years as "a genuine source discrepancy". It was not.* The
   page prints proposed 18335.23 / approved 18333.11 and the extractor
   carried the proposed figure on both sides. *West Bengal 2022-23 had it
   on **both** its totals* (FLN 10280.82 and grand 10300.82 shown on each
   side, against printed 10276.6 and 10296.6). The tell is a total row
   whose two sides are identical while the activity rows beneath it are
   not — cheap to test for, so test for it:

   ```python
   # totals identical on both sides but rows differ => suspect mode 6
   t.proposed_financial_lakh.eq(t.approved_financial_lakh) &
   ~acts.proposed_financial_lakh.eq(acts.approved_financial_lakh).all()
   ```
7. **Rows scraped from the narrative body instead of the annexure** — see
   the two-cluster note below. *Haryana, Kerala and Puducherry 2022-23.*
8. **Rows from a different annexure wearing a NIPUN label** — the most
   dangerous mode, because nothing about the row looks wrong. *Sikkim
   2022-23 carried two rows labelled "Capacity building of Teachers of
   Grades I to V" at p172; the page actually prints `151.1` DIKSHA and
   `149.2` DIETs.* They inflated the state's NIPUN proposal by 8.371 lakh
   and no arithmetic check could have caught it — the FLN subtotal closed
   without them. Only opening the page settles it. **When a row's
   `pdf_page` is far from the annexure span, verify what the page actually
   prints before trusting its label.**

### The two-cluster pattern when locating annexures
Anchor-text scans on 2022-23 minutes reliably return **two** clusters: an
early one in the narrative body (roughly pp 7-30, where NIPUN is
discussed in prose) and a late one at the real budget annexure (pp
136-138, 199-200, 374-376, 674-677 …). The original extractor repeatedly
locked onto the *early* cluster and published prose fragments as budget
rows — Haryana's only "total" came from p28, Kerala's from p24,
Puducherry's from p24, while their annexures sat at p375, p199 and p101.

**Always take the late cluster.** `locate_2223_pages.py` prints both so
the choice is visible; `render_2223_pass.py` holds the resolved span per
state.

### Locating the block in a file with no text layer at all
Arunachal (247 MB) and Mizoram (201 MB) 2022-23 are 300 DPI scans with
**zero characters** — no anchor text, and no captured rows to give a
window. Two things that work:

1. **The annexure is a contiguous run of LANDSCAPE pages.** One instant
   pass finds it: Arunachal p180-239, Mizoram p122-201.
   ```python
   [p+1 for p in range(len(doc)) if doc[p].rect.width > doc[p].rect.height]
   ```
2. **Then OCR every page in that band, not a sample.** A step-3 grid over
   Mizoram's 80-page band returned nothing, because the NIPUN block is
   only **two pages wide** inside it. Coarse grids will step straight over
   it. `find_pages_ocr.py` on the full file found Arunachal at p208 and
   Mizoram at p162-163.

Beware also that `find_pages_ocr.py` block-buffers when redirected — its
output file stays 0 bytes for the whole run, which looks like a hang.

### The narrative often states the total, and it is a free second source
Several 2022-23 minutes give the NIPUN outlay in prose in the early
cluster, and it matches the annexure grand total exactly:

| State | Narrative | Printed annexure grand total |
|---|---|---|
| Arunachal Pradesh | p23, "Rs. 627.44 lakh" | 627.44 approved |
| Mizoram | p26, "Rs. 502.19 lakh" | 502.19 approved |
| Ladakh | p29, "Rs.74.9 lakh" | 74.9 approved |

Read it before opening the annexure. It costs nothing, and a vision read
that lands on a different figure is telling you to look again.

---

## 6. The additions.csv trap

`apply_overrides` re-inserts rows from `additions.csv` whose uids are
missing. A vision rebuild that **drops** a file's activity rows deletes
those `#addN` uids — so the next overrides run silently re-adds them **on
top of** the new rows.

This double-counted 14 state-years and inflated the published 2026-27
headline by ₹1,363 Cr (₹5,555 Cr shown against ₹4,196 Cr true).

When removing superseded rows, **prune the matching `additions.csv`
entries too**, or it comes back. The safe removal rule is self-describing
rather than a hardcoded list:

> drop `#add` rows in any `source_file` that also has `#vision-` rows

which correctly spares states whose `#add` rows are their only data.

---

## 7. Verification discipline

**Chain closure is necessary, not sufficient.** It did not catch:

- an override written to the wrong `row_uid`, which overwrote Arunachal's
  capacity-building row while preserving the sum
- the Tripura scope bug, which only surfaced because a state that *should*
  close didn't

Always run, in this order:

```
python apply_<year>_pass.py     # idempotent; re-run must report 0 new adds
python regression_battery.py    # must print BATTERY GREEN
python qa_workbook.py           # MISMATCH files should be none
python check_stale_content.py   # must print STALE CONTENT CHECK: PASS
```

A change that touches only `dashboard.py` needs `check_stale_content.py`
alone. The apply passes and the regression battery both read the workbook,
so re-running them proves nothing when the workbook is untouched.

`check_stale_content.py` is a fourth, separate check: it doesn't touch
whether the *numbers* are right, only whether the deployed app matches
the working workbook and doesn't silently mislabel or hide a state-year.
It catches exactly the three bugs this project has already shipped once
each — `STATUS_LABEL`/`DOC_LABEL` not covering a new status or doc_type
(§10), a state-year falling out of `ACT_MIN` (the Ladakh bug, §10), and
an `OUTSIDE_HEADS` prefix colliding with a real state's content (the
Tripura bug, §3) — plus a drift check between `PAB/` and
`deploy_dashboard/`'s copies of the workbook, a `git status`/ahead-behind
check on `deploy_dashboard`, and a report (not a fail) on
`pdfs/manifest.json` entries that no longer match a Log row. Run it
before every commit that touches the workbook or `dashboard.py`, and
again immediately before pushing `deploy_dashboard/`.

Then the reconciliation audit across all years. As of the 2021-22 pass,
**202 of 202 documents that print a NIPUN subtotal reconcile against it**
(2021-22 31, 2022-23 36, 2023-24 34, 2024-25 21, 2025-26 45, 2026-27 35),
and the workbook has no MISMATCH rows — so any new failure is a regression,
not background noise.

**That claim was re-tested on 2026-08-07 and no longer holds as written;
see §16 and §17.** Two things to know before quoting it. First,
`qa_workbook.py` does not recompute anything — it reports the `total_check`
verdict *stored* in the Log at extraction time, so "MISMATCH files: none"
means no row was ever flagged, not that the sums were re-verified. A fresh
recomputation is a separate job (`dashboard.py:2136-2145` is the rule).
Second, that recomputation now shows **7 documents that do not close**, of
which one (Chandigarh 2025-26) is a deliberate decision and one (Madhya
Pradesh 2022-23, −0.024) is source rounding. The rest sit in 2021-22 to
2024-25 and are listed as backlog in §17.

**2022-23 is fully closed.** All 36 documents carrying NIPUN content
reconcile against their printed subtotal: 30 are `ok(vision-verified)`
and 6 (Andhra Pradesh, Jharkhand, Madhya Pradesh, Maharashtra, Punjab,
Uttar Pradesh) are clean automated parses that already closed and were
left alone — those six have **not** been read off the page, so do not
describe the year as wholly vision-verified. The remaining 15 documents
are addenda, corrigenda and the NCERT/NCPCR papers, which genuinely have
no state annexure. Published 2022-23 approved outlay: **₹2,450.66 Cr
across 36 states**. The year has no `ok-ocr-fallback` or `layout-variant`
documents left, so any reappearing is a regression.

**2021-22 is also fully closed**, the roughest year to date (see §11):
one state's entire figure was a different state's data under a portal
misfiling, two large states were wrongly marked `no-nipun-found` on pure
scans with no text layer, and one document had a column-shifted row that
had to be rebuilt rather than repaired. All 31 documents carrying NIPUN
content now reconcile: 27 are `ok(vision-verified)`, 4 (Bihar, Goa,
Haryana, Tamil Nadu, UP) were clean automated parses left alone. Published
2021-22 approved outlay: **₹2,059.22 Cr across 29 states**, up from an
undercounted, partly-wrong total across only a handful of verified
states. The year has no `ok-partial`, `ok-ocr-fallback` or
`layout-variant` documents left, so any reappearing is a regression.

Other habits that earned their keep:

- **Read the page even when arithmetic pins the answer.** Punjab 2023-24's
  gap was exactly 230.00 on both sides and the district count × rate
  reproduced it. Delhi 2022-23's residual pinned a row at proposed 53.151
  and approved 10.631 and the page printed 53.15 / 10.63. Both were right;
  Nagaland 2023-24's plausible-looking 15.410 and 308.200 were wrong in the
  last digit. The residual tells you *where* to look, never *what* to
  write.
- **When a row appears twice, ask the document.** Its own sub-total settles
  it: if the line really appeared twice the subtotal would be double. That
  resolved Uttarakhand 2023-24 (221, not 442) and Nagaland 2022-23. Where
  one copy carries a code and the other does not, the coded one is
  generally the real capture; where one lacks an approved side, that one is
  the fragment (Chhattisgarh 2022-23, Mizoram 2023-24).
- **Garbled total rows often still carry their digits.** Chhattisgarh
  2022-23's junk grand-total row read `0549.21 … 97557`, which is the
  printed 10549.21 and 9755.7 with a leading digit and a decimal point
  lost. Useful as corroboration once the page is read; never as the source
  of the value.
- **Sanity-check large recoveries against another year.** Maharashtra
  2023-24 jumping to 20,085.86 was believable because its 2026-27 figure
  is 20,714.47.
- **Verify `row_uid` numbering before writing OVERS.** Dump the state's
  rows first; uids are not contiguous and not in visual order.
- **Never scope a state from a truncated dump.** Uttarakhand 2022-23 was
  planned from a listing cut off by `head`, so rows #5-#9 were invisible.
  TRM, both PMU rows and the PMU total already existed; adding them again
  produced duplicates and the check caught it at 2618.677 against a printed
  2208.54. Dump one state at a time, or write to a file and read it whole.
- **A wrong ADD does not disappear when you stop declaring it.** The apply
  script is idempotent for *re-running the same modules*, not for
  retracting them. Stray rows must be listed in `DROPS` explicitly, and
  saying why in a comment keeps the module honest about its own history.

---

## 8. Staging workflow

Per-state modules under `pass<year>_data/<SLUG>.py`, applied by an
idempotent `apply_<year>_pass.py`:

```python
OVERS     = {row_uid: {field: value}}   # repair in place
ADDS      = [row dict with row_uid + after_uid]
DROPS     = [row_uid]
CONFIRMED = [row_uid]                   # read and left as-is, documentation
LOG       = {source_file: {field: value}}   # Log edits for a companion file
```

`LOG` exists because a module sometimes learns something about a file it
adds no rows to. Ladakh 2022-23 is the case: its minutes carry only
narrative, its budget block lives in a separate annexure volume, and the
minutes' standing status of `layout-variant(needs review)` was wrong —
there is no layout to parse. It is applied last, so it overrides the
automatic subtotal registration.

Rules:

- Order inside the apply script is **OVERS → DROPS → ADDS**. Never anchor
  an ADD on a uid the same module DROPS.
- Every module docstring carries the printed totals and the arithmetic
  chain, so a later reader can re-check without reopening the PDF.
- The apply script **also writes recovered printed totals into the Log**
  (`fln_total_printed_approved` / `total_check`). Without that a state is
  merely corrected, not *checkable*, and the dashboard has nothing to
  reconcile it against.
- Back up before writing; `*.bak_before_<year>_pass` is created each run.

Page location: `render_2324_tight.py` anchors on annexure text rather than
the captured-page window (that cut Arunachal from 11 pages to 3). For pure
scans, fall back to the capture window ±1.

When a state has **no captured rows at all** there is no window to fall
back on, and a textless file gives the anchor scan nothing to match. Use
`find_pages_ocr.py <pdf>` — it renders each page at 110 DPI, OCRs it and
reports anchor hits. That located Puducherry 2023-24 at p64-68 in a file
that had produced zero rows, and its OCR of the total line
(`Total of NIPUN Bharat 3121 2814`) matched the printed 312.13 / 281.44
once the decimal point was restored. A module whose first ADD has no
existing row to anchor to will log "anchor missing, appending"; that is
expected for a from-scratch state, not an error.

---

## 9. Source-internal inconsistencies: record as printed

Some pages genuinely do not add up. Do not silently "fix" them, and do not
let the arithmetic test discard them:

- *West Bengal 2023-24 TLM*: prints physical 3931736 × unit 0.002 but
  financial 5897.604 (= 0.0015 × physical). The **financial** is what the
  printed subtotal uses, so record as printed and mark the row
  `vision-verified` so `physical × unit = financial` does not drop it.
- *Manipur 2023-24 87.0.1*: prints proposed physical 16 @ 3.125 against
  approved 1 @ 40. Looks garbled; is genuine.
- *Gujarat 2022-23 TLM*: approved unit cost (0.00382) exceeds proposed
  (0.00300) because a second scheme is blended into the same line.

`vision-verified` on a side means "hand-read off the page and reconciled
against a printed total" and overrides the arithmetic gate. Use it only
when both halves of that are true.

### A moving unit cost is usually the PAB, not an error
Approved and proposed unit costs differing on the same row looks wrong and
almost never is. Read the remark before touching it:

- *Bihar 2022-23 TLM*: physical unchanged at 10,952,303 students, unit cost
  cut from 0.005 to 0.003. The PAB cut the **rate** (Rs 500 to Rs 300),
  not the coverage.
- *Gujarat 2022-23 TLM*: approved unit cost (0.00382) **exceeds** proposed
  (0.00300), because a second scheme is blended into the same line — Rs 300
  per student plus Rs 2,647.77 lakh at Rs 200 per student for Grades 4-5
  under Sabal Shala.

### Totals can round against their own components
Not only can a subtotal round the rows beneath it, a grand total can round
its own subtotals. *Meghalaya 2022-23*: 2122.08 + 230 = 2352.08 but the
page prints **2352.09**, and the same 0.01 on the approved side. Record as
printed and say so in the docstring, or someone will "fix" it later.

---

## 10. Dashboard notes

- `ACT_MIN` = activity rows from the primary minutes, falling back to a
  **companion doc** (`addendum`, `addendum (alt)`, `annexure`) only where
  no minutes rows exist. Duplicate PDF downloads (`*_NNNNN.pdf`) are
  tagged `minutes (alt)` and correctly excluded.
- **The fallback list must cover every companion `doc_type` in the
  workbook.** `annexure` was missing from it, and since
  `Ladakh_2022-23_annexure.pdf` is the only file carrying that doc_type,
  **all of Ladakh 2022-23 was silently absent from the app** — national
  totals, YoY comparisons, state explorer, everything — while its Log row
  cheerfully read `OK(reconciled)`. A doc_type that appears exactly once
  is the easy one to forget; check `BUDGET.doc_type.value_counts()`
  against the filter whenever a new one appears.
- `STATUS_LABEL` must map **every** Log status. `ok(vision-verified)` was
  missing, so 18 state-years fell through to "Partial" and their files were
  listed as needing attention — the most rigorously verified data in the
  workbook displayed as the weakest.
- KGBV rows are quarantined by **C-code span 6483-6496**, not by label:
  "Maintenance", "Miscellaneous" and "Capacity Building" are too generic to
  match by name without hitting genuine NIPUN rows.
- The published accuracy figures are a round-1 sample that predates the
  sweeps and rebuilds. The app states its draw date and says so. Re-running
  certification is a large, separately-gated job.
- App text convention: no em dashes, no colons.
- Playwright: the live app renders **inside an iframe** whose URL ends
  `/~/+/`; `page.inner_text("body")` returns 0 chars. Tabs are
  `[role="tab"]`, not `button[role="tab"]` or `[data-baseweb="tab"]`.
  Running locally there is no iframe, so query the page directly. Streamlit
  renders **every** tab's body into the DOM, so a `:visible` filter is
  needed to hit the widget in the tab you actually opened. Table cells are
  drawn on a canvas and never appear in `inner_text`, so a table can only be
  checked by screenshot.
- The app is four tabs: The Story, National Picture, Explore & Compare,
  Data Quality. It was six until the 2026-08 redesign; Compare States was
  folded into the state explorer behind one shared state multiselect (one
  state selected gives the annexure view, two or more give the comparison),
  and Analytics became a national-scope section of National Picture.
- **Keep `STATUS_LABEL`, `DOC_LABEL`, `OUTSIDE_HEADS` and `_COMPANION` as
  flat literal assignments.** `check_stale_content.py:54` recovers them by
  regex from the source text and `eval`s the match, and the pattern stops at
  the first closing bracket. Nesting a dict inside one of them, or building
  it from a comprehension, makes the check silently skip that constant
  rather than fail loudly.
- `.streamlit/config.toml` carries the theme (CSF blue as `primaryColor`,
  the story page's paper and ink). It is **not** covered by
  `check_stale_content.py`'s drift check, which compares only `dashboard.py`
  and the workbook, so the `PAB/` and `deploy_dashboard/` copies have to be
  kept in step by hand.
- **Three faces, three jobs, no overlap.** Instrument Serif carries
  headlines and nothing else, Inter Tight carries every word of running
  text, label and control, JetBrains Mono carries every digit that means
  something (metric values, axis tick labels). All three load from Google
  Fonts in `inject_css()`, because Streamlit Cloud runs Linux with no
  licensed faces and a system-serif fallback there lands on DejaVu. An
  earlier build used a warm cream ground with Charter and a Source Serif
  fallback and read as a default rather than a decision.
- The canvas is a **cool** near-white (`#fafafa`), not a warm cream. The
  brand navy and yellow are the only saturated things on the page and a
  warm ground fights the navy and muddies the yellow.
- The ink ramp has four steps and they are not interchangeable. `MUTED`
  (`#a1a1aa`) is furniture only, for axis values and eyebrows. Anything a
  reader actually reads, captions included, sits at `QUIET` (`#71717a`) or
  darker; zinc-400 on a near-white ground is below comfortable reading
  contrast and captions set there looked washed out.
- Structure is hairlines and tinted surfaces, never shadow. Radius is 4px on
  controls, 6px on section panels, 2-3px on marks. If you add a component,
  match that.
- **Every section is a `with section(label, tone)` block**, which is a
  bordered `st.container` with an eyebrow inside. Tones come from `TONES`
  and follow the Scouted formula: the hue at 3-7 percent for the fill, the
  same hue at 20-60 percent for the stroke, and a darkened version for the
  label so it stays readable at 0.68rem. Hue is assigned by what a section
  is about, so the same head keeps its colour across tabs.
- The tone reaches the panel through **`:has()`**, because Streamlit owns
  the wrapper and gives no hook to put a class on it. In 1.60 a bordered
  container is `[data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]`.
  The parent restriction is load-bearing: bare `stVerticalBlock` is also the
  generic block element and tints the entire page. If a browser lacks
  `:has()` the panel just falls back to the neutral border.
- **If you script the eyebrow-to-section conversion, compute every section
  boundary before rewriting any line.** Doing it in reverse and detecting
  boundaries as you go silently nests each section inside the one above it,
  because the next `eyebrow(` has already become a `with section(` and the
  boundary test stops matching. The tell is one giant tinted panel per tab
  with everything inside it.
- `st.dataframe` renders on a canvas and takes the single `font` from
  `config.toml`, so table figures cannot be monospaced without making the
  labels monospace too. Tables stay in Inter Tight; the prominent numbers
  (metrics, axis ticks) are where the mono does its work.
- **`st.dataframe` ignores a Styler's `na_rep` and any NaN-handling
  formatter**, painting the cell as a literal `None` from Arrow while
  honouring the format string for every non-null cell in the same column.
  Pre-render such columns to text (`as_text()`) instead. Costs right
  alignment, which is worth it.
- **The Story tab is built natively, not embedded.** `nipun_story.html` was
  never committed to the deploy repo, so the live app never had it at all;
  when it was finally embedded it went in as a fixed-height iframe, which
  meant a scrollbar inside a scrollbar, a hero cut off mid-number, and a
  full-bleed navy block dropped into a warm-paper page. It is now rebuilt
  from the workbook in Streamlit and Altair, so it carries the app's own
  design and recomputes on load rather than shipping frozen JSON. The HTML
  file is kept as the design reference and is no longer read at runtime.
- Story metrics reuse `story_prep.py`'s conventions **unchanged**, because
  the published story quotes them: children covered is the max
  `approved_physical` on TLM rows per state-year, teachers covered is the
  max across Teacher Resource / Handbook and Capacity Building rows (max,
  not sum, since the same cohort is named on both), the per-day basis is 365
  days, and per-child rates are computed only over states whose student
  count is known so an unknown denominator cannot deflate the rate.
- **Do not name a module-level constant `GRID`.** The palette already uses
  it for the hairline colour, and a tile-map dict of the same name shadowed
  it and fed a dict to every chart's `gridColor`, taking down all four tabs
  at once. The cartogram dict is `TILE_GRID`.
- Both story map measures are heavily skewed (Ladakh at Rs 33.94 per child
  per day against a median near Rs 2). A linear colour ramp paints almost
  every tile the same pale blue; the map uses **quantile bins** instead, and
  derives the label colour from the bin rather than the raw value so white
  text never lands on a pale tile.
- There is **no sidebar**. The quality-marks key sits in Data Quality next
  to the grid it explains, and the build note at the foot of that tab.

---

## 11. The 2021-22 pass: the first year has its own failure modes

2021-22 is NIPUN Bharat's launch year and the ministry's document
generation was less standardised than later years. All of the below were
found closing out this year; none showed up in 2022-23 onward.

### `no-nipun-found` from a keyword scan is not proof of absence
The keyword scan that assigns `no-nipun-found` searches the PDF's text
layer. On a pure scan with **zero characters**, that scan finds nothing
by construction, regardless of what the document contains. Three
2021-22 files were wrongly marked this way:

- **Maharashtra** — 12.2 MB, 191 pages, 0 characters. Its real NIPUN
  figure (₹15,051.36 lakh) was sitting in the file the whole time, found
  by a full-file OCR sweep.
- **Telangana** — 46.7 MB, 301 pages, 0 characters. ₹4,176.95 lakh,
  likewise found only by OCR sweep, and independently corroborated by a
  narrative statement of the same figure 230 pages earlier.
- **National Achievement Survey** — genuinely has zero NIPUN content
  (confirmed by full-text scan), but was flagged `layout-variant` rather
  than `no-nipun-found`; there was no layout to parse because it isn't a
  state document at all.

**Before trusting `no-nipun-found` on a textless file, check the image
coverage is real content, then run a full-file OCR sweep before
concluding there is nothing to find.** A 0-character file and an
empty file are not the same thing.

### An image "tagged" 72 DPI is not necessarily unreadable
§1 says a small image in the original stays small at any render DPI —
true, but the DPI figure computed from `img_width / placed_width_pt * 72`
on a single sampled page is not reliable evidence either way. Maharashtra
2021-22's embedded images measured 72 DPI on that formula and rendered
**perfectly legibly at 300 DPI** — full tables, clean text, no artefacts.
Always render and look before writing a file off as unreadable; the
formula is a hint, not a verdict.

### The ministry's own portal can serve the wrong file
`Kerala_2021-22_minutes.pdf` and `Haryana_2021-22_minutes.pdf` were
byte-identical — same md5, 283 pages, cover page reads "for the State of
Haryana." Re-fetching Kerala's own portal URL directly returned the same
Haryana bytes: **this is the ministry's live server serving the wrong
document**, not a stale download or a caching artefact on our side.
Every Kerala 2021-22 figure ever published had been Haryana's, doubling
₹3,345.72 lakh into the national total. The genuine Kerala minutes only
existed in the Wayback archive of the old site. Verify a re-fetch
independently before trusting that "the portal has it" means "the portal
has the right one."

### Byte-identical files across DIFFERENT states need a decision, not both
Distinct from the reupload duplicates in §1 (same state, degraded vs
clean copy), two 2021-22 pairs are identical files **shared by two
different Log entries**:

- `Dadra-and-Nagar-Haveli_2021-22_minutes.pdf` and
  `Daman-and-Diu_2021-22_minutes.pdf` — genuinely the same minutes
  document for the merged UT, filed under both legacy names. Rows belong
  under one filename only, or the UT is double-counted.
- `Maharashtra_2021-22_minutes.pdf` / `_9001` and
  `Telangana_2021-22_minutes.pdf` / `_9001` — same content, alt-copy
  downloads. These already fall out of `ACT_MIN` via the `doc_type`
  fallback, but their Log entries still need to agree with the primary
  file's reconciliation status rather than sitting at `no-nipun-found`.

Run a full md5 sweep across `pdfs/*.pdf` before scoping a pass — it is
one line and it catches this class of bug immediately:
```python
import hashlib, collections
h = collections.defaultdict(list)
for f in Path("pdfs").glob("*.pdf"):
    h[hashlib.md5(f.read_bytes()).hexdigest()].append(f.name)
{k: v for k, v in h.items() if len(v) > 1}
```

### A third annexure shape: the narrative report with a single figure column
Meghalaya, Nagaland, Maharashtra and (for its FLN section specifically)
Telangana 2021-22 are not `86.x`/`87.x` annexures at all. They are prose
reports structured as numbered activity headings ("2) Foundational
Literacy and Numeracy: ... An outlay of Rs. X lakh was estimated..."),
each followed by its own small table. No `86.` or `87.` codes appear
anywhere in the file, so the standard anchor scan finds nothing — this is
what a `layout-variant` flag looks like when it's telling the truth.

These tables print **one** figure column (Physical / Unit Cost /
Financial), not a Proposal/Approved pair — the same approved-only
convention as Kerala, just inside a different document shape. The
narrative sentence right before the table states the same grand total
the table computes to, which is a free corroboration check every time.

### Column-shift garbling: a captured value in the wrong field entirely
Distinct from every failure mode in §5 — not a missing row, not a wrong
row, but a **shifted** row. Delhi 2021-22's 86.1 was captured with its
unit cost (0.003) sitting in the `proposed_financial_lakh` field and its
real proposed financial (2556.975) sitting in `approved_financial_lakh`.
Nothing about the stored row was internally consistent enough to repair
with `OVERS`; both defective rows had to be dropped and rebuilt whole
from the page. The tell was a proposed/approved pair where one side
looks like a unit cost and the other like a value from a different row
entirely — check the shape of the numbers, not just their presence.

### `LOG` targeting the module's own `SF` is fine
The `LOG` hook (see §8) was introduced for a module correcting a
*different* file's Log entry, but it works identically when `SF` and the
`LOG` key are the same file with **zero** `ADDS`/`OVERS` — e.g. National
Achievement Survey, which needed only a status correction and no budget
rows at all. Every module still needs `SF` defined, even a documentation-
only one, because the apply script's auto-registration loop reads
`m.SF` unconditionally across all modules.

---

## 12. Closing out the last unverified documents (2023-24 through 2026-27)

After 2021-22 and 2022-23 were fully closed, 15 documents remained across
later years in the same `ok-ocr-fallback`/`layout-variant` limbo. Closing
them surfaced a few lessons specific to the newer Prabandh portal format
and to distinguishing "needs more reading" from "needs a different file."

### Before trusting a correction request, check what the data actually says
When told these documents were "already verified, just not updated,"
the right first move was checking `p_verified`/`a_verified` on their
rows: every one read `arithmetic`, never `vision` or `vision-verified`,
and every printed total was still a garbled string with no captured
value. Those two fields are written at extraction time and are strong,
checkable evidence — a real disagreement about verification status
should be resolved by reading them, not by re-reading pages on faith
that they must have been missed.

### Not every companion doc affects a published total
Before spending effort on a flagged document, check whether its
state-year already has a `minutes` doc with rows. If it does, the
flagged file (addendum/supplementary) is excluded from `ACT_MIN`
regardless of its own status — cleaning it corrects the Log for
documentation purposes only. Of 2025-26's 12 flagged documents, only
6 (Assam's addendum, and the 5 states whose primary *is* the flagged
file) actually moved a published number; the other 6 were companion
docs whose state already reconciled elsewhere. Worth knowing before
deciding how much rigor a given file needs.

### The 2025-26/2026-27 Prabandh schema has THREE proposal columns, not two
Punjab, Assam and Tamil Nadu 2025-26 print "State Proposal (Initial)" /
"State Proposal (Modified)" / "Recommended by DoSEL" side by side. The
rule that closes every printed total in this batch: **proposed = the
state's final ask, i.e. Modified where given, else Initial.** Several
line items have a genuinely blank Initial cell (not zero — the item was
an "Additional State Proposal" made only at the Modified stage); read
the legend colour key at the top of the table, it names this case
explicitly. Verify the reconciliation both ways before picking one — a
document that closes under "always use Initial" (values identical
throughout, e.g. Jharkhand, Delhi) doesn't tell you which convention is
right; only a document with genuinely different Initial/Modified values
(Tamil Nadu, Manipur) does.

### A "0 characters, 0 hits" file may still be readable — sweep pages, don't grep the metadata
Two 2025-26 documents (Maharashtra-adjacent pattern from §11, recurring
here as Jharkhand and Tamil Nadu 2025-26, plus Assam's addendum) are pure
scans that a keyword `find_pages_ocr.py` sweep returned nothing for —
not because the anchor text isn't there, but because low-DPI OCR noise
missed it on a first pass, or the annexure sits far from where a
capture-window heuristic would look. Where the extractor's own garbled
capture already names a page number (even with corrupted values), start
there directly at full render DPI before re-running a blind sweep.

### A source PDF can omit the annexure it says it contains
Goa 2025-26's minutes explicitly states "the... item-wise costing sheet
for 2025-26 is at Annexure III," and the PDF as downloaded contains only
Annexure I/II (a prior-year spillover statement). No amount of higher-DPI
rendering recovers a page that was never included in the file. This is
the same "genuinely cannot be read" category as §1's small-in-the-
original images, just for a different reason — verify by reading the
minutes' own cross-references, not just its final page count, before
concluding a table must be somewhere in what you have.

### Extending the `_COMPANION` doc_type fallback list preventatively
`supplementary` / `supplementary (alt)` (47 rows total) were never added
to `dashboard.py`'s `_COMPANION` list alongside `addendum`/`annexure`,
even though they follow the identical pattern (Delhi 2025-26 has both a
`minutes` and a `supplementary` file). No state-year currently depends on
`supplementary` alone, so this wasn't yet live like the Ladakh bug — but
rather than wait for it to bite, it was added now. Re-run
`BUDGET.doc_type.value_counts()` against the fallback list at the start
of every new pass; a doc_type introduced by a newly-downloaded year is
easy to miss until a state silently vanishes from the totals.

---

## 13. The validity gate must accept every read-off-the-page tier

`dashboard.py` decides a figure is publishable if `physical x unit cost`
reproduces the printed financial, **or** the figure carries a
read-off-the-page verification tier. For a long time that second clause
tested only `vision-verified`, and the omission was invisible because it
only bites a row that is hand-read *and* has no physical or unit cost to
run the arithmetic on.

Ten rows are exactly that. Nine tenths of the loss is Kerala 2021-22, whose
recovered rows are financial-only. The effect:

| | dashboard, before | story_prep.py and CLAUDE.md |
|---|---|---|
| 2021-22 | 2031.07 | **2059.22** |
| 2022-23 | 2450.37 | **2450.66** |
| 2024-25 | 2349.66 | **2349.71** |
| all years | 16632.29 | **16660.77** |

So the app was quietly 28.48 Cr under its own published figures, and the
state whose data cost the most effort to recover (see §11, the portal
serving Haryana's minutes under Kerala's URL) was the one being dropped.

The gate now accepts `vision`, `vision-verified` and `manual-recovery` on
either side. All three mean someone opened the page. **When a new tier is
added to `p_verified`/`a_verified`, decide explicitly whether it belongs in
`_READ`**, and check the year totals against this table afterwards; a tier
missing from that list fails silently and downward, which is the direction
nobody notices.

`story_prep.py` accepts only the two vision tiers, so it and the app now
differ by `manual-recovery`. That is 2 rows and no rupees today, but the
file claims to replicate the dashboard exactly, so keep them in step.

---

## 14. What the grade-scope question actually is

The dashboard publishes outlay split by the grade span each budget line
names. Before building it the premise was checked against the pages, and
the premise was backwards, so check this section before trusting anyone's
summary of it (including this one).

**The usual assumption is that NIPUN covered Grades 1-3 and was later
broadened to Grade 5. In these documents it runs the other way.** Verified
by rendering the pages at 200 DPI:

| Read | Page | What it prints |
|---|---|---|
| UP 2021-22 | p890 | `86.0.3 Capacity building of Teachers of Grades I to V (New)`, printed verbatim |
| Bihar 2022-23 | p2170 | TLM label names no span; the remark carries it, "10952303 students as per UDISE+ 2020-21 of Grades 1 to 5" |
| Chhattisgarh 2025-26 | p49-50 | the split, side by side: "pre-primary sections in Govt. Schools and Grade 1 and 2" and "in Govt. Schools and Grade 3 to 5" |
| MP 2025-26 | p45 | same split; its Grade 3-5 label is cut at the page boundary in capture but the printed remark holds |
| Tamil Nadu 2025-26 | p38 | `5.6.3` handbook and capacity lines labelled "Class III to V" whose remarks read "Grade I-V" |
| UP 2026-27 | p65 | re-broadened, `TLM ... from Balvatika to Grade 5 (C6777)`, `Grades I to V (C6778/C6779)` |

So the shape is wide (Grades 1-5) through 2024-25, narrowed in **2025-26**
to a Foundational Stage block (pre-primary to Grade 2) with a separate
Grade 3-5 line that only 12 states and UTs printed, then wide again in
**2026-27**. `fetch_udise.py:15-16` already carried this reading and was
the corroborating source.

### Why the chart shows an "unspecified" band instead of an estimate
Most 2021-22 to 2024-25 lines name **no** grade span at all, so a strict
like-for-like series cannot be read off the print. That outlay is shown as
"Not stated on the page" rather than allocated across bands. Resist
closing the gap with a UDISE enrolment deflator and publishing the result
next to printed figures; it would be the one invented number in a workbook
whose whole standard is fidelity to print. If it is ever wanted, it
belongs in its own clearly-labelled estimate, not in this band.

### Tagging precedence, and why the label beats the remark
Printed C-code, then the printed line label, then the coordinator remark.

- The **C-code** wins because 2026-27's `C6800` label names both
  "Pre-Primary/Balvatika" and "Class I to V" in one string and only the
  code settles that it is the full span. Every 2026-27 FLN line carries one.
- The **label** beats the **remark** because the label is the budget line's
  own name and the remark is prose about it. They genuinely disagree in the
  source: Tamil Nadu 2025-26 p38 prints a handbook line for "Class III to
  V" whose remark reads "for 80,495 teachers in Grade I-V". Both are
  printed. That is a §9 source-internal inconsistency to record, not a
  capture error to repair.
- The **remark** is a real fallback, not a guess. Bihar 2022-23's TLM line
  carries its span only there, and MP and Maharashtra 2025-26 have labels
  truncated at a page boundary whose remarks still name Grade III to V.

Two signals that look useful and are not. The printed **Activity** column
names the scope ("5.8.2 - TLM (Pre-Primary to Grade 2)") but the workbook
stores only its code, so that text is unavailable. And the **`-FS`** suffix
on the sub-component is printed in 2026-27 as well as 2025-26, so it
fingerprints the Prabandh layout rather than the grade scope, even though
`component_group` happens to carry it only for 2025-26.

### Counting the carve-out states
Twelve states and UTs print a separate Grade 3-5 line in 2025-26. Two
traps in counting them. **Odisha** prints the line with no recoverable
amount, so it vanishes from any `a_valid` filter while still being a state
that printed it; the caption is built from all primary-document rows for
that reason. **Rajasthan** matches on a label scan of the raw Budget sheet
but its row lives in `Rajasthan_2025-26_minutes_23697.pdf`, a duplicate
download tagged `minutes (alt)`, so `ACT_MIN` correctly drops it.

---

## 15. The Elementary Head gap — a whole sub-component missing in 2025-26

A second, genuinely separate Grade 3-5 FLN sub-component exists in some
2025-26 documents, printed **after** the FLN-FS block the extractor
already anchors on. Its own heading never contains the words
"Foundational Literacy and Numeracy" — it is printed as `5.9 -
Elementary Head`, `5.10 - Elementary Head`, or (Bihar) not named at all,
just sitting as one activity row inside an unrelated component — so the
anchor-text scan that locates "Total of Foundational Literacy and
Numeracy -FS" stops there and never walks forward into the next block.
The document closes cleanly against its own FLN-FS subtotal, which is
exactly what made this invisible to every prior reconciliation pass: the
chain-closure check in section 7 only proves the captured rows sum to the
anchor they were captured against, not that the anchor itself is the
whole story.

**The reliable signature is a standalone printed `Total of Elementary
Head` line** — separate from, and in addition to, `Total of Foundational
Literacy and Numeracy -FS`. Confirmed present in 17 states/UTs for
2025-26:

| Round | States | Why a separate round |
|---|---|---|
| 1 | Andaman & Nicobar Islands, Andhra Pradesh, Arunachal Pradesh, Bihar, Chandigarh, Delhi, Haryana, Jammu & Kashmir, Karnataka, Kerala, Meghalaya, Odisha, Rajasthan, Tripura, Uttar Pradesh | Found by a scripted scan (`ACT_RE` + `G35_RE` co-occurrence, then a check that the printed component number/C-code is not already among the state-year's captured codes) over every 2025-26 primary document |
| 2 | Assam, Punjab | The scripted scan reads the text layer, and both documents are pure image scans from the relevant page onward — "0 hits" on the scan is not proof of absence (the same lesson as section 11's `no-nipun-found` warning, recurring one schema layer up). Found only by individually vision-reading every state the scan had called clean |

Bihar's is the odd one out: no `Total of X` line at all, just one
NIPUN-scoped TLM row (Rs 33,237.065 lakh, 66.47 lakh students @ Rs 500)
sitting as item 8 inside `5.4.2 - Innovation Projects (Elementary)`, a
component that is otherwise non-NIPUN content this workbook correctly
never captures. The row's own printed figure is its own reconciliation
unit; there was no subtotal to anchor a `LOG` update on.

**Combined impact: Rs 825.62 Cr added to the published 2025-26 national
total** (16 states with their own `Total of Elementary Head` line summing
to Rs 493.24 Cr, plus Bihar's Rs 332.37 Cr row) — applied as staging
modules named `<STATE>_EH.py` (suffixed to avoid colliding with an
existing unrelated per-state module of the same two-letter name — `AR.py`,
`DL.py`, `TR.py`, `AS.py`, `PB.py` all already existed), each carrying a
`LOG` override so the printed anchor becomes the FS-plus-Elementary-Head
combined figure, since the FS subtotal alone excludes it.

Two unrelated existing-row defects were found and fixed incidentally
while individually vision-reading round 2's "clean" states — proof that
a state confirmed to have no Elementary Head gap is still worth reading
in full, not just scanned for the one pattern being hunted:

- **Mizoram** — the classic mode-6 defect from section 5 (proposed value
  copied into the approved column). The FLN-FS total's approved figure
  carried the Modified proposal (1320.8955) instead of the printed
  Recommended by DoSEL figure (1315.0755); the row's own captured
  activity figures summed correctly to 1315.0755, confirming which value
  was right.
- **West Bengal** — a pure parsing bug, not a source or capture problem.
  The FLN-FS total row's `proposed_financial_lakh`/`approved_financial_lakh`
  were stored as 8.0/0.0 while the row's own `remarks` text already held
  the correct raw figures (10696.99958/10636.998); only the parsed fields
  were wrong. Applied to both the primary `minutes.pdf` and its identical
  alt-copy for Log consistency, though only the primary feeds `ACT_MIN`.

### 2026-27 does not have this gap
Checked directly rather than assumed from the year's known wide
(Grades 1-5, single combined FS block) schema, because "the schema is
different" is exactly the kind of claim section 11 warns against trusting
without opening files:

1. Every one of the 36 primary 2026-27 documents carries a real, sizeable
   text layer (80,000+ characters), ruling out the pure-scan blind spot
   that caused round 2's misses.
2. Zero occurrences of a standalone `Total of Elementary Head` line across
   all 36 documents' own current-year annexures.

**A false lead worth recording so it isn't re-chased.** Every 2026-27
document embeds a second, unrelated table headed "Sub Component wise
Approval / Expenditure till Date (F.Y. 2025-2026)" — a Prabandh-generated
retrospective summary of the *prior* year, and 11 states show a nonzero
"Elementary Head" line inside it. This looks exactly like a lead on more
missed 2025-26 gaps, and none of it is: every one of those 11 figures
(Maharashtra Rs 109.88 Cr, Chhattisgarh, Himachal Pradesh, Lakshadweep,
Madhya Pradesh, Nagaland, Puducherry, Tamil Nadu, Uttarakhand, and Dadra &
Nagar Haveli and Daman & Diu) was already fully captured — the portal
tags whichever row is Grade-3-5 TLM/CB content as "Elementary Head" for
this summary regardless of whether that row sits inside the state's
already-captured FLN-FS subtotal (all 11 of these) or as the genuinely
separate component the 17 real gaps above have. Confirmed to the rupee in
several cases, e.g. Dadra & Nagar Haveli and Daman & Diu's summary figure
of Rs 112.08 lakh is exactly its two already-captured "TLM ... Class III
to V" rows (Rs 3.5 + Rs 108.58 lakh) added together by the portal, not a
third, missing one. **The only trustworthy signal for this gap, in any
year, is a standalone printed `Total of Elementary Head` subtotal line —
not the phrase alone, and not this retrospective table's per-state
figure.**

### Document revisions supersede only the sections they amend
Settled as a standing rule after a state (Uttar Pradesh, 2025-26) turned
out to have a ministry-issued revised budget PDF alongside its original:
a revision replaces the original's figures **only for the specific
sections it actually amends**, not the whole document. Checked directly
for UP's sub-components 5.9/5.10 (byte-identical text between the
original and the revision, so nothing to change there); do not assume a
revision is wholesale, and do not assume it changes nothing either — read
the sections in question in both copies.

---

## 16. Cross-checking against an independent extract (2026-08-07)

A colleague produced their own copy of the breakdown workbook
(`NIPUN_2026-27_budget_breakdown_JH_070826.xlsx`) carrying an extra
**"FY 2025-26"** sheet — a raw re-extract of that year, 332 rows, 319 of
them keyed by `row_uid`. Diffing it against the master found real defects
on both sides, and the shape of what it got right and wrong is worth
keeping, because someone will do this again.

**Diff BOTH of its sheets.** The first pass compared only its `Data` tab
and found ~20 rows. The `FY 2025-26` tab is a different extract and had to
be diffed separately; it produced 9 numeric and 29 substantive remark
differences that the first pass never saw. Key on `row_uid`, never on row
position.

**Their copy was right about column errors.** It correctly caught that
several states' proposed side had been read off the wrong column (below),
which we had missed. Its remaining differences are transcription slips —
paraphrasing ("Grade 2" where the page prints "Grade II"), dropping a
clause Puducherry does print ("of Grades I to II"), dropping trailing
full stops, truncating a leading "R" ("ecommended").

### The mistake I made grading it, which is the real lesson

Three of their rows — Sikkim `#1` ("Rs. 573.00 lakhs" against the
minutes' "Rs. 916.8 lakhs"), Manipur `#14` ("Rs. 25 lakh" against "Rs.50
lakh") and Manipur `#12` ("Recommended 50% due to change in Total
outlay…" against "Recommended as proposed") — were written up as
fabrications, on the evidence that the strings appear nowhere in the
document. **That was wrong.** They appear in the state's **addendum**,
which is a second, separately-generated full Budget Demand annexure. Our
own workbook already held them verbatim on the addendum rows.

The error was searching only the file the `row_uid` names and treating
absence there as absence from the source set. **When a state has a
companion document, search every document it has before calling anything
invented.** What their file actually did was key an addendum remark to a
minutes `row_uid` — a document mix-up, not invention.

This matters beyond the grading, because it is evidence that **the two
ministry documents genuinely disagree on remark text while agreeing on
every figure.** Sikkim's minutes say the pre-primary support is "Rs.
916.8 lakhs" (the Modified proposal) where the addendum says "Rs. 573.00
lakhs" (what was actually recommended); Manipur's minutes say "Rs.50
lakh" for the state PMU where the addendum says "Rs. 25 lakh". Record
each against its own file, which is what the master does — do not
"reconcile" them to each other.

**So use such a file to LOCATE suspect rows, never to source values.**

The findings were handed back as
`NIPUN_2026-27_budget_breakdown_JH_070826_reviewed.xlsx` — their file
copied, with the offending cells highlighted and annotated and an
`Issues` sheet at the front. Note for anyone regenerating it: openpyxl
round-trips that workbook faithfully (all 6 word-cloud images and all 6
`ArrayFormula` cells survive), but comparing `ArrayFormula` cells with
`!=` compares object identity and will report false differences — compare
`.text` and `.ref`.

**The cheapest way to adjudicate a disputed remark**, before rendering
anything: flatten both strings to `[a-z0-9]` and substring-search the
page's own text layer. The 2025-26 PRABANDH files are digital exports
with no OCR layer over a scan, so there the text layer *is* the print and
§2's warning does not apply. That settled 15 of 24 disputed rows at zero
cost and proved the three fabrications above by absence. Only genuine
scans (Punjab, from p14 on) needed a render.

### The defect classes this surfaced

1. **Proposed side read off `State Proposal (Initial)` instead of
   `(Modified)`** — J&K, Assam, then Punjab (5 FS rows + the FS total).
   §12 already states the rule; what is new is that it recurs, and that a
   file can carry a *third* wrong value: Punjab `#add4`'s proposed
   physical was 1004918, matching neither column (printed 1005198 /
   1004983). Punjab's FS total also had both physicals truncated by the
   page's digit wrap (printed 1807335, captured 180733).

2. **Activity rows missing beneath a correctly-captured subtotal.** The
   document reconciles, because the subtotal it reconciles against was
   captured fine — but `ACT_MIN` sums `row_type=="activity"` only, so the
   published figure is short. Chain closure cannot see this (§7).
   Found in Rajasthan (ECCE + TLM + District PMU, **+₹61.24 Cr**),
   Chandigarh (4 rows, +₹2.43 Cr) and West Bengal (Support to
   Pre-Primary, **+₹7.20 Cr**). In West Bengal the missing row was the
   *first* of its block, which is why its own Sub Total had been captured
   with empty values — that empty subtotal is a tell.

3. **A NIPUN-named line outside the block the extractor anchors on.**
   Rajasthan's minutes print `3-Nipun Bharat Mission - MLE (Language
   Mapping)` at 66.77 under `5.2 - Funds for Quality`. Same family as
   Bihar/Kerala/Meghalaya in §15, but this one *names the mission*, so it
   is not a judgement call. Corroborated by the state's own alt-copy
   download, whose independent capture had picked it up — but alt copies
   are excluded from `ACT_MIN`, so it never published.

4. **A Log anchor taken from the proposal column.** Tripura's anchor held
   1233.799, which the page prints on *both* proposal columns, against
   1230.799 as Recommended by DoSEL. The state read 3.000 lakh short
   against its own reconciliation while the published figure was right
   the whole time. **A state that "does not close" may have a wrong
   anchor rather than wrong data — check which column the anchor came
   from before hunting for missing rows.**

### The external reference that actually exists

Every **2026-27** document embeds a Prabandh-generated retrospective
table, `Sub Component wise Approval / Expenditure till Date (F.Y.
2025-2026)`, giving that state's 2025-26 approvals by sub-component. It
is generated by the ministry's own portal from its own records, so it is
genuinely independent of this project's extraction — and it is the only
such source that exists, since no public source publishes a
NIPUN-specific national figure for these years.

To read it: find the page containing `Sub Component wise Approval`,
flatten whitespace, and take the **3rd** of the 8 numbers following the
label `Foundational Literacy and Numeracy - FS` (and `Elementary Head`).
That is the Budget Approvals *Total* column.

Result: **31 of 36 states agree with the published per-state total to
within 1 lakh, and no state falls below the portal figure.** The
exceptions are all understood — Bihar (+33,237.06), Kerala (+1,728.09)
and Meghalaya (+70.00) are exactly the NIPUN rows those states print
under "Funds for Quality", which the portal tags to that component
instead (§15). **Do not "fix" those.**

Critically, this route independently confirms the **14 states that have
no printed subtotal recorded in the Log**, all to within 0.01 lakh — so
2025-26 has no unverifiable state left.

**When the portal figure is LOWER than the printed minutes, look for a
later re-appropriation PAB before concluding either source is wrong.**
Rajasthan was the only state below, by 762.75 lakh.
`Rajasthan_2025-26_supplementary_41405.pdf` (supplementary PAB
19.03.2026, a 6-page **pure scan**, which is why no keyword sweep had
ever surfaced it) reports exactly that amount as a saving under
"Foundational Literacy and Numeracy (FL&N)-FS", re-appropriated with the
rest of the Elementary savings to MMMER. **A state can surrender approved
FLN money a year later, and the portal reports net of it.** This workbook
publishes what the PAB approved as printed, so the minutes' figure stands
and the Log now carries the explanation so it is not re-chased.

### "Use the most recent document" would lose data, not gain it

Checked directly, because it is a reasonable thing to assume and it is
wrong here. For the 2025-26 state-years where more than one document
carries rows, the later companion (addendum / supplementary) is almost
always a **partial re-issue**, not a supersession: Bihar's minutes carry
58,622.12 lakh against its addendum's 25,385.06, Odisha's 39,071.64
against a supplementary's 6,584.63, Chandigarh's 554.25 against 296.64.
Switching the selection rule to "latest document wins" would silently
drop those rows.

And it would buy nothing. Across both current years, **no ECCE line
differs between two documents of the same state-year, and no companion
document carries an ECCE line the chosen document lacks** (0 and 0 on a
full sweep). Where documents overlap they agree on figures; what they
differ on is remark wording (§16, Sikkim and Manipur). So the existing
`primary_doc_mask` / `ACT_MIN` rule — take the minutes where it has rows,
else the companion — is already selecting the fullest document, and the
standing §15 rule (a revision supersedes only the sections it amends)
remains the right model.

### Chandigarh, deliberately left as it is

Chandigarh's published total includes `18-Role play (class 3 to 5)`
(7.40096), which sits inside a mixed Innovation component among plainly
non-NIPUN neighbours (Vocational Education class 6-8, Literary Fest),
falls outside both printed subtotals, and is excluded from the portal's
FLN tagging. Three independent signals say it is not NIPUN. **The user
decided on 2026-08-07 to leave it in.** It is therefore the only 2025-26
state that does not close on its printed anchor — that is expected, not a
regression, and it should not be "fixed" by a later pass.

### Verification state of the two current years

- **2026-27**: all 36 states close on their printed anchor. No state
  document is non-contributing (the four that are — EdCIL, NCPCR, NIEPA,
  NCERT — are central bodies). The retrospective-table hunt and a sweep
  for mission-named uncaptured lines both returned nothing.
- **2025-26**: **35 of 36 close on their printed anchor, and none is
  left without one.** The single open state is Chandigarh, by the
  decision above. All 19 non-contributing scanned companion documents
  were OCR-triaged for FLN / NIPUN / re-appropriation keywords — every
  one is a revision or supplementary letter amending other heads (RTE
  entitlements and so on), so no 2025-26 FLN figure is superseded.

### The anchor was registered against the wrong file for 14 states

Fourteen 2025-26 state-years reported "no printed total captured" even
though **every one of them already held its own printed `Total of
Foundational Literacy and Numeracy -FS` row in the Budget sheet.** Only
the Log registration was missing, so the reconciliation had nothing to
compare against. For Sikkim and Manipur the anchor was worse than
missing — it sat on the **companion addendum**, while the rows that
publish come from the primary minutes.

**When a state-year reports no printed total, check the Budget sheet for
its own total row and check its companion documents' Log entries before
concluding the figure was never captured.** Registering these turned 14
unverifiable states into 10 that close exactly plus 4 that disclosed a
real defect — the §16.4 Tripura pattern again, a TOTAL row whose approved
side had taken a State Proposal column:

| State | Printed Recommended | Had been held as |
|---|---|---|
| Puducherry | 194.62900 | 195.103 |
| Lakshadweep | 54.48650 | 54.5045 |
| Madhya Pradesh | 27705.89050 | 27651.3465 (Initial col) |
| Maharashtra | 18894.28000 | 18894.29 |

In all four the state's activity rows already summed to the Recommended
figure and the portal agreed, so no published figure moved. Madhya
Pradesh's physicals were also digit-wrap truncated (printed "436767 4" =
4367674, "427374 7" = 4273747). Staged in `ANCHORS_2526.py`.

Published totals after this pass: **2025-26 405,044.65 lakh**,
**2026-27 419,572.58 lakh**, 36 states each.

---

## 17. Open backlog — reconciliation for 2024-25 and earlier

Deferred by the user on 2026-08-07 to focus on the two current years.
Recorded here so it is not rediscovered from scratch. Run
`dashboard.py`'s own reconciliation rule (it honours `outside_block` and
`PMU_OUTSIDE`; see `dashboard.py:2136-2145`) across all years — a naive
sum-vs-anchor comparison reproduces §4's 18 false failures, because for
the 86/87 schema years PMU sits outside the FLN anchor.

Current standing, by that rule:

| Year | States | Close | Do not close | No printed total |
|---|---|---|---|---|
| 2021-22 | 30 | 29 | 1 | 0 |
| 2022-23 | 36 | 35 | 1 | 0 |
| 2023-24 | 35 | 28 | 1 | 6 |
| 2024-25 | 36 | 1 | 3 | **32** |
| 2025-26 | 36 | 21 | 1 | 14 (all externally confirmed) |
| 2026-27 | 36 | 36 | 0 | 0 |

Specific items to work:

- **Andhra Pradesh 2021-22 is double counted.** Both
  `Andhra-Pradesh_2021-22_minutes.pdf` *and*
  `Andhra-Pradesh_2021-22_minutes_9001.pdf` carry `doc_type="minutes"`,
  so both enter `ACT_MIN`. The primary closes exactly (6484.998 against
  its 6485.0 anchor); the alt adds a further 5326.633 for its single TLM
  row, taking the state to 12,121.63. **This is the only state-year in the
  whole workbook drawing on more than one source file** — the duplicate
  should be retagged `minutes (alt)`. Worth roughly **−₹53.27 Cr** on
  2021-22. Detect with: group `ACT_MIN` by state-year, flag any with more
  than one `source_file`.
- **Telangana 2024-25 is short by 2,223.544 lakh** against its printed
  `Total of NIPUN Bharat Mission` (3907.3645). Its captured physical is
  tiny against a printed 1,345,453, so this looks like a missing TLM row
  — the §16.2 class again.
- **Tamil Nadu 2024-25 (+380.00)** and **Andhra Pradesh 2024-25
  (+260.00)** sum above their anchors; **Himachal Pradesh 2023-24
  (−30.38)** below. Madhya Pradesh 2022-23 (−0.024) is source rounding
  (§9), not a defect.
- **2024-25 is 88% unverifiable** — 32 of 36 states have no printed total
  captured, covering 192,516 lakh. The retrospective-table trick does
  **not** help: it exists only in 2026-27 documents. These totals are
  printed on the pages and simply were never captured into the Log, so
  the work is to recover the printed `Total of …` line per document and
  register it.

---

## 18. Commit conventions

No AI attribution or co-author trailers in commits or PR bodies. Commit
messages explain *why* a value changed and cite the printed figures.
