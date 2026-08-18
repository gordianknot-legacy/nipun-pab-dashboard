# Reading the source PDFs

How to get a readable page out of these documents and how far to trust it once you have one. Read this before any extraction pass.

Part of the PAB project. The operating rules are in `../CLAUDE.md`; this file is the detail behind them.

---

## The source files lie about their own quality

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

## The text layer is not trustworthy, even in good files

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

## Annexure schemas vary by state and year

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
