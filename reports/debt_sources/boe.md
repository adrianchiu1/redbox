# BoE source family — verification report

Fetched 2026-09-09 via `python3 -m ggfiscal.cli debt fetch --family boe`.
All 18 parts across the three registered sources (`BOE_APF`,
`BOE_YIELD_CURVES`, `BOE_IADB`) returned HTTP 200 on the first attempt with
a plain GET plus `BROWSER_HEADERS` (bare `requests` default User-Agent gets
403'd by BoE's media CDN; no other bespoke handling was needed — no
`get()` override in `families/boe.py`).

## BOE_APF

| part | HTTP | bytes | sha256[:12] | format | rows (post-parse) | first date | last date |
|---|---|---|---|---|---|---|---|
| gilt_purchases | 200 | 1,241,457 | `b6b595a21e41` | xlsx, sheet "APF Gilts" | 7,680 | 2009-03-11 | 2021-12-15 |
| gilt_sales | 200 | 779,219 | `bc1e64332201` | xlsx, sheet "APF gilt sales" | 1,493 | 2022-11-01 | 2026-08-17 |
| maturity_profile | 200 | 680,942 | `644edb256db8` | xlsx, sheet "Maturity Profile of APF (Table)" | 40 gilts | maturity 2026-10-22 | maturity 2071-10-22 |
| fs_long_dated_purchases | 200 | 33,786 | `42d50bee228d` | xlsx, sheet "UK Government Bonds" | 241 | 2022-09-28 | 2022-10-14 |
| fs_index_linked_purchases | 200 | 19,356 | `5d406edfefae` | xlsx, sheet "Web report" | 92 | 2022-10-11 | 2022-10-14 |
| fs_gilt_sales | 200 | 498,023 | `df4403edfca0` | xlsx, sheet "APF FS portfolio gilt sales" | 360 | 2022-11-29 | 2023-01-12 |

Quirks:
- Every workbook's data header sits at Excel row 2 (`header=1` in pandas);
  three of the six (`gilt_sales`, `fs_long_dated_purchases`, `fs_gilt_sales`)
  carry a leading blank column A, so column names collide with `Unnamed: 0`
  and are dropped rather than relied on positionally.
- Column names drift slightly release to release: `Bond` vs `Bond\n`,
  `Allocated at highest price (%)` vs `Allocated at lowest price (%)` (a
  genuine BoE labelling inconsistency between the purchase and sale
  sheets — not used by the reader), and `fs_gilt_sales` lacks the
  `Comments`/rejected-offers columns the others have. The reader keys off
  a fixed rename table and only pulls the eight columns the unified schema
  needs.
- `fs_gilt_sales` carries one trailing footnote row ("*transactions in Blue
  reflect sales of remaining...") with `Operation date` as free text — it
  fails `to_datetime` and `isin` is blank, so it is dropped and logged
  (1 row of 361).
- `gilt_purchases` includes ~2,600 rows with zero accepted allocation (a
  gilt was offered into the operation but nothing was bought). These are
  kept in `apf_operations()` as real, published zero-fill operation rows,
  not treated as missing data — dropping them would put purchase-row counts
  below 7,000 and would misrepresent what BoE published for that operation.
- `maturity_profile`: two non-security header/summary rows precede the 40
  actual gilts (a units subheader and a "Current stock of holdings" total
  row with no gilt name or maturity date) — dropped, logged.
- The BoE-side filename typo "finanical-stability-gilt-sales-time-series.xlsx"
  (should read "financial") is real, present in BoE's own URL as of
  2026-09-09; recorded verbatim per the task brief, not a bug in our code.

## BOE_YIELD_CURVES

| part | HTTP | bytes | sha256[:12] | zip contents | first date | last date | max maturity |
|---|---|---|---|---|---|---|---|
| nominal_daily | 200 | 39,110,776 | `312d4a0efaf9` | 8 xlsx (era-split, 1979–present) | 1979-01-02 | 2026-08-28 | 40y |
| real_daily | 200 | 25,065,089 | `9d9c88aabbb2` | 7 xlsx (1985–present) | 1985-01-02 | 2026-08-28 | 40y |
| inflation_daily | 200 | 24,733,422 | `458ef13d1787` | 7 xlsx (1985–present) | 1985-01-02 | 2026-08-28 | 40y |
| ois_daily | 200 | 11,715,140 | `19a3133a8e6d` | 3 xlsx (2009–present) | 2009-01-02 | 2026-08-28 | 25y |
| nominal_monthend | 200 | 2,563,251 | `98856ebb9487` | 3 xlsx (1970–present) | 1970-01-31 | 2026-08-28 | 40y |
| real_monthend | 200 | 1,307,402 | `3253fe39957d` | 3 xlsx (1979–present, real values start 1985) | 1985-01-31 | 2026-08-28 | 40y |
| inflation_monthend | 200 | 1,291,765 | `978f719ceac3` | 3 xlsx (1979–present) | 1985-01-31 | 2026-08-28 | 40y |
| ois_monthend | 200 | 928,406 | `69e5c30227d3` | 3 xlsx (2009–present) | 2009-01-31 | 2026-08-28 | 25y |
| latest | 200 | 262,339 | `1fe03140b062` | 4 xlsx, one per kind, current month only | 2026-09-01 | 2026-09-08 | — |

Quirks / sheet layout (documented in `readers/boe.py::_spot_sheet_name` and
`_parse_spot_workbook`):
- Every workbook holds five sheets for nominal/real/inflation
  (`info`, `1. fwds short end`, `2. fwd curve`, `3. spot short end`,
  `4. spot curve`) and three for OIS (`info`, `1. fwd curve`,
  `2. spot curve` — OIS has no short-end sheets). `yield_curve()` always
  reads the sheet whose name ends in "spot curve" — the zero-coupon curve —
  never the forward or par short-end sheets, which are a different curve
  and would silently give a wrong yield if picked up by mistake.
- Within the chosen sheet, column A row 4 (1-indexed) reads exactly
  `years:` in every kind and every era-split file, including OIS (which has
  an extra `months:` row above it) — confirmed across all nine parts, not
  assumed. Maturities run across that row; dates start at row 6 down
  column A. This matches the brief's expected layout exactly.
  - `nominal_monthend`'s first workbook ("1970 to 2015") actually starts
    1970-01-31, two years before nominal's own registered start of 1979 in
    `config/debt_sources.yaml` — 1970–1978 cells are present but blank
    (dropped as unparseable/NaN), so the effective first observation with a
    value is still 1970-01-31 for the earliest maturities and the curve
    only becomes fully populated by 1979 for the reasons the config note
    lower quality pre-1979 gilt data. No config change needed — the
    "1979-" note describes when the curve is usable, not the workbook's
    file boundary.
  - `real_monthend`/`inflation_monthend`'s first workbook nominally spans
    "1979 to 2015" but has no non-blank cells before 1985-01-31 (matching
    `config/debt_sources.yaml`'s "real (1985-)"); those blank cells are
    dropped, not fabricated.
- Daily files are large (up to 39MB); the shared `ingest.fetch` 300s
  timeout was sufficient for all four.

## BOE_IADB

| part | HTTP | bytes | sha256[:12] | format | first date | last date | rows |
|---|---|---|---|---|---|---|---|
| IUDSOIA | 200 | 148,577 | `965f39b19a6a` | CSV (`DATE,IUDSOIA`) | 1997-01-02 | 2026-09-07 | 7,499 |
| IUDBEDR | 200 | 230,745 | `138f9d34b140` | CSV (`DATE,IUDBEDR`) | 1975-01-02 | 2026-09-08 | 13,065 |
| baserate_xls | 200 | 5,041,152 | `fc910d349d66` | xls, sheet "HISTORICAL SINCE 1694" | 1694-10-01 | 2025-12-18 | 853 changes |

Quirks:
- With `Datefrom` set to the series' own true start (`01/Jan/1997` for
  SONIA, `01/Jan/1975` for Bank Rate — one day before each series' first
  observation, per the brief), the endpoint returned a plain two-column CSV
  both times (`Content-Type: application/csv`, HTTP 200) — not the HTML
  `<table id="stats-table">` page the brief warns about. `iadb_series()`
  still handles both shapes (sniffs for `<table` in the decoded body,
  falls back to `pd.read_html(..., attrs={"id": "stats-table"})` then a
  bare `pd.read_html`), since a `Datefrom` before a series' start, a future
  BoE endpoint change, or a re-fetch closer to `now` could still trigger
  the HTML path.
- `baserate.xls` sheet "HISTORICAL SINCE 1694": column A carries the year
  only on that year's first rate change (blank on subsequent changes within
  the same year, and on the blank separator row BoE inserts between
  years); column B (day) is blank for every entry before 1844 — before
  that date BoE's own sheet does not record which day of the month the
  rate changed, only the month. `bank_rate_history()` forward-fills the
  year, treats the (expected) blank separator rows as formatting rather
  than a data-quality drop, and represents a day-unknown change as the 1st
  of its month, documented in the docstring. Every one of the 853 changes
  parsed cleanly (0 rows dropped as unparseable after separator rows are
  excluded from the count).

## Corrections to `config/debt_sources.yaml`

None required. All three verification blocks (`BOE_APF`,
`BOE_YIELD_CURVES`, `BOE_IADB`, `checked: 2026-09-09`) matched what was
observed live: `BOE_APF`'s stated date ranges (purchases 2009-03-,
sales/FS 2022-) match exactly; `BOE_YIELD_CURVES`'s "nominal (1979-),
real (1985-)... OIS (2009-)" matches the first non-blank observation in
each curve; `BOE_IADB`'s "IUDSOIA SONIA (1997-), IUDBEDR Bank Rate (1975-);
baserate.xls (1694-)" and its `CSVF=TT` HTML-table note match (see above —
`CSVF=TN` as specified in the task returned CSV directly both times, which
is consistent with, not contradictory to, the recorded note about the
HTML-table shape under different query parameters).

## Files written

- `src/ggfiscal/debt/families/boe.py`
- `src/ggfiscal/debt/readers/boe.py`
- `tests/debt/test_boe.py`
- `reports/debt_sources/boe.md` (this file)
