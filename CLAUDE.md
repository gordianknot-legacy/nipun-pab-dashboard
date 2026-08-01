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
```

Then the reconciliation audit across all years. As of the 2022-23 pass,
**177 of 177 documents that print a NIPUN subtotal reconcile against it**
(2021-22 6, 2022-23 36, 2023-24 34, 2024-25 21, 2025-26 45, 2026-27 35),
and the workbook has no MISMATCH rows — so any new failure is a regression,
not background noise.

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

---

## 11. Commit conventions

No AI attribution or co-author trailers in commits or PR bodies. Commit
messages explain *why* a value changed and cite the printed figures.
