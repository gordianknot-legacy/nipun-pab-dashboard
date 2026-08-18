# NIPUN Bharat PAB extraction — operating brief

Two extractions over one corpus of Samagra Shiksha PAB minutes in
`pdfs/`: **NIPUN Bharat** budgets (the original job) and **school ICT**
budgets crossed with UDISE+ (the second). Deliverables are two
workbooks and two Streamlit apps.

This file is the part that applies to every session. The detail behind
each rule lives in `docs/`, and those files are worth opening before a
pass rather than after a bug.

| Doc | Read it when |
|---|---|
| [docs/reading-the-pdfs.md](docs/reading-the-pdfs.md) | Before any extraction pass. Which files lie about their own quality, when the text layer is wrong, how the annexure schemas vary. |
| [docs/extraction-defects.md](docs/extraction-defects.md) | When something looks wrong, or when a page genuinely does not add up. Eight failure modes, all seen in real files. |
| [docs/reconciliation.md](docs/reconciliation.md) | Before comparing any sum to any printed total. Scope rules, the audit history, the open backlog. |
| [docs/nipun-passes.md](docs/nipun-passes.md) | Before declaring a new failure mode. What each year's clean-up actually found. |
| [docs/dashboards.md](docs/dashboards.md) | Before touching either app. Design system and the bugs each has shipped once. |
| [docs/ict-extraction.md](docs/ict-extraction.md) | For anything ICT. Table shapes, parser geometry, per-year state. |

---

## The standard

**Fidelity to print.** Publish what the page prints, flag what it cannot
support, never invent.

Five rules follow from it, and none of them has an exception:

1. **Read the page.** A figure is publishable when someone has seen it
   printed, or when arithmetic on printed components reproduces it. The
   text layer is a locator, not a source — many of these PDFs carry a
   ministry OCR layer that is wrong in individually plausible ways
   (`3275.37` for a printed `3215.37`).
2. **Reconcile against the document's own printed total**, and compare
   like with like. A sum that closes against the wrong anchor is worth
   nothing. See `docs/reconciliation.md` before choosing the anchor.
3. **Absence is a finding, not a gap.** A state that printed no ask, a
   page the scan omits, and a block still unread are three different
   things. Record which, with the evidence. Never fill any of them with
   an estimate.
4. **Record what is printed even when it is wrong.** Source pages
   genuinely fail to add up, clip their own cells, and print off-norm
   unit costs. Say so in the remark; do not silently correct.
5. **Never let a partial year read as a national total.** Label it
   everywhere it appears.

**Chain closure is necessary, not sufficient.** It has failed to catch
an override written to the wrong row, a scope bug, rows swallowed by a
mis-detected boundary, and whole states discarded before output. When a
block reconciles, that is the beginning of the check.

---

## Verification discipline

Run in this order, and do not skip on the grounds that nothing looked
broken:

```
python apply_<year>_pass.py     # idempotent; a re-run must report 0 new adds
python regression_battery.py    # must print BATTERY GREEN
python qa_workbook.py           # MISMATCH files should be none
python check_stale_content.py   # must print STALE CONTENT CHECK: PASS
```

A change touching only `dashboard.py` needs `check_stale_content.py`
alone. The apply passes and the battery both read the workbook, so
re-running them proves nothing when the workbook is untouched.

`qa_workbook.py` **does not recompute anything** — it reports the
`total_check` verdict stored at extraction time. "MISMATCH files: none"
means no row was ever flagged, not that the sums were re-verified. A
fresh recomputation is a separate job; the rule is
`dashboard.py:2136-2145`.

`check_stale_content.py` is a separate concern from whether the numbers
are right: it checks the deployed app matches the working workbook and
does not silently mislabel or hide a state-year. It catches the three
bugs this project has shipped once each. Run it before every commit
touching the workbook or `dashboard.py`, and again immediately before
pushing `deploy_dashboard/`.

**When you touch a shared parser, re-run every year it serves and diff
the outputs cell by cell against copies taken beforehand.** Row counts
and reconciliation totals both survive the mistakes that matter. This
has caught a silent rewrite of 284 rows' labels, and a fix for one year
corrupting another. Twice.

Windows note: always run `python -X utf8`, or printing `→` raises
`UnicodeEncodeError` under cp1252.

---

## Staging workflow

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
- **Verify `row_uid` numbering before writing OVERS.** Dump the state's
  rows first; uids are not contiguous and not in visual order.
- **Never scope a state from a truncated dump.** Uttarakhand 2022-23 was
  planned from a listing cut off by `head`, so rows #5-#9 were invisible
  and the re-added duplicates broke the chain. Dump one state at a time,
  or write to a file and read it whole.
- **A wrong ADD does not disappear when you stop declaring it.** The
  apply script is idempotent for re-running the same modules, not for
  retracting them. Stray rows must be listed in `DROPS` explicitly.
- Back up before writing; `*.bak_before_<year>_pass` is created each run.

The ICT extraction uses the same shape in `ict_vision_<year>.py`, whose
`main()` asserts every block against its printed totals before writing
its CSV. A vision module that does not self-verify is not finished.

**Page location.** Anchor on annexure text rather than a captured-page
window. For pure scans with no captured rows there is no window and no
anchor text, so use `find_pages_ocr.py <pdf>` — it renders each page at
110 DPI, OCRs it, and reports hits. It block-buffers when redirected, so
its output file sits at 0 bytes for the whole run; that is not a hang.

---

## Where the work stands

**NIPUN.** All six years published, 2021-22 to 2026-27. 2021-22 and
2022-23 are fully closed. A fresh recomputation on 2026-08-07 found 7
documents that do not close, one of them a deliberate decision
(Chandigarh 2025-26) and one source rounding; the rest are backlog in
`docs/reconciliation.md`. 2024-25 is 88% unanchored.

**ICT.** 2024-25, 2025-26 and 2026-27 complete, 36 of 36 states each.
UDISE+ complete for five census years. 2023-24 and 2019-21 outstanding.
Detail in `docs/ict-extraction.md`.

**Apps.** `deploy_dashboard/` → nipun-pab.streamlit.app,
`ict_dashboard/` → pab-ict.streamlit.app.

---

## Commit conventions

No AI attribution or co-author trailers in commits or PR bodies. Commit
messages explain *why* a value changed and cite the printed figures.
