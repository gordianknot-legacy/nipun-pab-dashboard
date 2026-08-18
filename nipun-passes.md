# The NIPUN passes, year by year

What each year's clean-up actually found. Historical, but the failure modes recur, so check here before declaring a new one.

Part of the PAB project. The operating rules are in `../CLAUDE.md`; this file is the detail behind them.

---

## The 2021-22 pass: the first year has its own failure modes

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

## Closing out the last unverified documents (2023-24 through 2026-27)

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

## What the grade-scope question actually is

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

## The Elementary Head gap — a whole sub-component missing in 2025-26

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
