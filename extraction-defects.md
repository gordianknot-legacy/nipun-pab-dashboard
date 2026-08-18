# How extraction fails, and how to record what the page really says

The failure modes seen in real files, the staging traps, and the rule for source pages that genuinely do not add up.

Part of the PAB project. The operating rules are in `../CLAUDE.md`; this file is the detail behind them.

---

## How extraction fails (all seen in real files)

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

## The additions.csv trap

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

## Source-internal inconsistencies: record as printed

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

## The validity gate must accept every read-off-the-page tier

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
