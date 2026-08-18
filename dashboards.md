# The two Streamlit apps

Design system, data rules and the bugs each app has already shipped once. Read before touching either app.

Part of the PAB project. The operating rules are in `../CLAUDE.md`; this file is the detail behind them.

---

## Dashboard notes

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
- The app is five tabs: The Story, National Picture, Explore & Compare,
  CSF Focus States, Data Quality. It was six until the 2026-08 redesign;
  Compare States was folded into the state explorer behind one shared state
  multiselect (one state selected gives the annexure view, two or more give
  the comparison), and Analytics became a national-scope section of National
  Picture. CSF Focus States was added 2026-08-17: the 2026-27 budget
  breakdown workbook's Headline view live, defaulting to the 9 CSF FLN
  focus states (`CSF_FLN_STATES`) with an editable multiselect. Its
  six-line-item bucketing (`bucket_category`, `pmu_split`, `LINE_ITEMS`)
  lives in `dashboard.py` and `build_budget_breakdown.py` imports it, so
  the tab and the workbook cannot bucket a row differently. The tab's
  line-item tables are six-item scope; its headline and state-trend table
  are all-NIPUN scope (both say so on the page), and the line-item table
  carries both totals to bridge them.
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

## The ICT Streamlit app

`ict_dashboard/`, deployed from `gordianknot-legacy/pab-ict-dashboard`.
Six tabs: The Story, National Picture, Explore & Compare, Approved vs
Spent, Schools on the Ground, Data Quality.

- **`ui.py` is generated, not written.** `build_ict_ui.py` slices the
  palette, `TONES`, `inject_css`, `section`/`eyebrow` and the table
  helpers straight out of `dashboard.py` by line range. The two apps
  deploy from separate repos so the ICT app cannot import at runtime,
  and a hand-retyped copy would drift the moment either app is touched.
  Regenerate rather than editing `ict_dashboard/ui.py`. This does not
  touch `dashboard.py`, so `check_stale_content.py` is unaffected.
- **`YEARS_COMPLETE` is a separate constant from the years present in
  the workbook**, and that separation is the whole point. A year earns a
  national headline only when all 36 states are either read or confirmed
  to print no ask. Everything else is labelled "IN PROGRESS, N of 36"
  every place it appears. Do not let a part-extracted year into a
  headline by adding it to the workbook alone.
- **`NO_ASK` carries the evidence, not just the fact.** Nine state-years
  print no school ICT ask; each entry holds the line that settles it, so
  the app can say "asked for nothing" instead of showing a hole, and the
  Data Quality tab renders them as a table anyone can recheck.
- **The execution report's approval column is CUMULATIVE** (§18), so it
  is larger than the year's approved outlay and differencing the two
  means nothing. The tab is labelled "Approved to date" throughout and
  says so in prose above the first figure. 2025-26 shows Rs 5,253 Cr
  approved-to-date against the budget tab's Rs 3,392 Cr approved outlay;
  a reader who is not told will treat that gap as a finding.
- `bar()` accepts either a field string or an already-built `alt.X`.
  Wrapping a built channel in `alt.X()` again yields a spec whose
  `field` is a channel object, and Vega-Lite rejects it with a message
  naming `repeat` that points nowhere near the cause.
- Verify with `shot_ict.py` against a local run (no iframe locally,
  unlike the deployed app whose body sits inside a `/~/+/` frame).
