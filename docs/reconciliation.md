# Reconciliation, scope, and the open backlog

What to compare against what, the audit history, the cross-check against an independent extract, and what is still open.

Part of the PAB project. The operating rules are in `../CLAUDE.md`; this file is the detail behind them.

---

## Reconciliation: compare like with like

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

## Cross-checking against an independent extract (2026-08-07)

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

## Open backlog — reconciliation for 2024-25 and earlier

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
