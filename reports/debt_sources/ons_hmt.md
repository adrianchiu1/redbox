# ONS / HM Treasury source family — verification report

Fetched 2026-09-09 via `python3 -m ggfiscal.cli debt fetch --family ons_hmt`.
**41 of 41 parts across all six registered sources returned HTTP 200 on the
first attempt** with a plain GET plus `BROWSER_HEADERS`; no `get()` override is
needed in `families/ons_hmt.py`.

| source | parts | status |
|---|---|---|
| `ONS_PSF_APPENDIX_A` | 1 | 200 |
| `ONS_PSF_APPENDIX_S` | 1 | 200 |
| `ONS_PSF_TIMESERIES` | 10 | 200 (all ten CDIDs resolve under `/pusf/data`; the CSV-generator fallback was never needed) |
| `ONS_RPI` | 3 | 200 |
| `HMT_DMR` | 6 (4 PDF + 2 accessible HTML) | 200 |
| `HMT_NLF` | 20 | 200 |

Pull resolution that needs an API call happens inside `pulls()` and is cached in
module scope: the gov.uk content API for every DMR and NLF attachment
(`GovUkResolutionError` is raised, not swallowed, if a lookup fails), and a
`HEAD` on each ONS workbook URL that falls back to `{dataset}/current/data →
downloads[0].file` if the published filename has moved. Both ONS filenames in
`config/debt_sources.yaml` are still current, so the fallback did not fire.

---

## ONS_PSF_APPENDIX_A

| part | HTTP | bytes | sha256[:12] | format |
|---|---|---|---|---|
| `appendix_a` | 200 | 1,679,632 | `da9919a727d1` | xlsx (65 sheets), vintage 2026-08-20 |

URL: `https://www.ons.gov.uk/file?uri=/economy/governmentpublicsectorandtaxes/publicsectorfinance/datasets/publicsectorfinancesappendixatables110/current/publicsectorfinancessummarytablesappendixafinal.xlsx`

Sheets read by `readers/ons_hmt.py` (all via the generic `psa_table(sheet)`):

| sheet | reader | columns (CDIDs) | rows | FY span | monthly span |
|---|---|---|---|---|---|
| PSA8A_1 | `cg_debt_by_instrument()` | 8 | 4,208 | 1997-98 → 2025-26 | 1997-04 → 2026-07 |
| PSA6B_2 | `cg_interest()` | 10 | 5,260 | 1997-98 → 2025-26 | 1997-04 → 2026-07 |
| PSA6B_1 | `cg_interest()` (L6BD only) | 11 | 5,786 | 1997-98 → 2025-26 | 1997-04 → 2026-07 |
| REC2 | `cgncr_reconciliation()` | 7 | 3,682 | 1997-98 → 2025-26 | 1997-04 → 2026-07 |
| REC3 | `cgncr_reconciliation()` | 14 | 7,364 | 1997-98 → 2025-26 | 1997-04 → 2026-07 |

Layout quirks:

- **The header offset is not constant.** PSA8A_1 and PSA6B_2 put the column
  headings on Excel row 5 and the CDIDs on row 6; REC2, REC3 and PSA6B_1 insert
  a `Transaction code` row between them, so the CDIDs are on row 7. `psa_table`
  finds both rows by their column-A stub ("Time period", "Dataset identifier
  code") rather than by position; `psa_table_columns(sheet)` exposes the
  transaction (ESA) code where the sheet publishes one.
- **Period labels are not the "1998/99" form the brief assumed.** This vintage
  publishes four stacked blocks with the labels `1998` (calendar year, end-
  December stock), `Apr 1997 to Mar 1998` (financial year), `Apr to Jun 1997`
  (quarter) and `2026 Jul` (month). `_parse_period` handles those plus
  `1998/99`, `1998-99`, `2026 Q1`, `Q1 2026`, `Jul 2026` and `1987 JAN`, and
  returns `("", NaT)` for anything else so a stray stub row is dropped rather
  than mis-dated.
- Calendar years start at **1998**, financial years at **1997-98** — the register
  entry's "FY from 1998" is one year late (see corrections).
- CDIDs are published with leading spaces and, where the column is the negative
  of the named series, a leading minus (` -NMFJ`, `-EYMW`). `psa_table` strips
  whitespace and keeps the sign, which is the publisher's own sign convention.
- PSA8A_1 instrument map used by `cg_debt_by_instrument()`: BKPM gilts, BKPJ
  Treasury bills, ACUA NS&I, ACRV tax instruments, KW6Q other sterling and
  foreign currency, KW6R NRAM/B&B, MDL3 Network Rail, BKPW total. Values are
  £ million, end of period, for every period type. Cross-check: the month-end
  BKPM column is **identical** to the `BKPM` PUSF time series over all **352**
  overlapping months, 1997-04 to 2026-07 (tested).

## ONS_PSF_APPENDIX_S

| part | HTTP | bytes | sha256[:12] | format |
|---|---|---|---|---|
| `appendix_s` | 200 | 279,552 | `21d7fd85ca0d` | legacy .xls (BIFF, read with `xlrd`), 6 sheets |

URL: `https://www.ons.gov.uk/file?uri=/economy/governmentpublicsectorandtaxes/publicsectorfinance/datasets/financialstatisticsforpublicsector/current/publicsectornetcashrequirementappendixsfinal.xls`

`cgncr_financing()` reads sheet `Table 1.2A`: 15 instrument columns, **7,530
rows**, FY 1997-98 → 2025-26, quarterly 1997 Q1 →, monthly 1997-01 → 2026-07.

- Row offsets confirmed as the brief stated (1-based): row 4 headings, row 5
  transaction codes, row 6 CDIDs, data from row 7 — one row earlier than
  Appendix A, and the stub reads `Transaction`, not `Time period`.
- **There is no calendar-year block** on this sheet (period types are FY, Q, M
  only), unlike Appendix A.
- ESA codes as published: gilts `F.332` (ANTA), Treasury bills `F.331` (NAVG),
  coin `F.21` (-EYMW), NS&I and tax instruments `F.29`, loans `F.4`, and a
  compound `F.332, F.411, F.424` on the Northern Ireland and foreign-currency
  columns. The heading text carries the publisher's typo "Liabilty".
- Signs are pre-applied by ONS (a column headed `-AACE` is published negated so
  the row sums to M98R); the reader does not re-sign anything.

## ONS_PSF_TIMESERIES (PUSF)

All ten CDIDs resolve at
`https://www.ons.gov.uk/economy/governmentpublicsectorandtaxes/publicsectorfinance/timeseries/{cdid}/pusf/data`
(lowercase CDID in the path). **None 404'd**, so the
`/generator?format=csv` fallback (`psf_timeseries_csv_url`) is defined but
unused.

| part | HTTP | bytes | sha256[:12] | obs | first | last |
|---|---|---|---|---|---|---|
| BKPM | 200 | 174,514 | `22f0d2e72610` | 544 | 1975 | 2026-07 |
| BKPJ | 200 | 119,996 | `194cf0ee8dc9` | 600 | 1986 | 2026-07 |
| NMFX | 200 | 142,929 | `66cd0ad7e616` | 754 | 1946 | 2026-07 |
| MW7L | 200 | 146,740 | `e120ba820ba8` | 774 | 1981 | 2026-07 |
| M98R | 200 | 138,909 | `5d88ef001dd5` | 718 | 1984-04 (annual from 1985) | 2026-07 |
| ANTA | 200 | 96,145 | `7fe99476d027` | 498 | 1997 | 2026-07 |
| AACE | 200 | 95,857 | `0ac9fe4ea59c` | 498 | 1997 | 2026-07 |
| L6BD | 200 | 124,685 | `b94575f83e84` | 498 | 1997 | 2026-07 |
| ANSK | 200 | 161,694 | `f51ed9f49c21` | 754 | 1946 | 2026-07 |
| ANLO | 200 | 149,816 | `fcc84865976b` | 754 | 1946 | 2026-07 |

- Format is one JSON document with `years` / `quarters` / `months` arrays;
  `ons_timeseries(cdid, dataset)` stacks all three into
  `period_type (A|Q|M), period_start, value`. Annual observations are **calendar
  years** on both PUSF and MM23, not financial years.
- Month labels are uppercase (`2026 JUL`); quarter labels are `1946 Q1`.
- Values arrive as strings; blank strings are dropped, zeros kept (§7.12).

## ONS_RPI (MM23)

| part | HTTP | bytes | sha256[:12] | monthly first | last |
|---|---|---|---|---|---|
| CHAW | 200 | 128,563 | `e00d5d88558d` | 1987-01 (=100.0) | 2026-07 (419.1) |
| CDKO | 200 | 208,075 | `4405b4316ba0` | 1947-06 | 2026-07 (1,653.3) |
| CZBH | 200 | 232,334 | `b74312ef656c` | 1948-06 | 2026-07 |

`rpi_index()` — the `UK_RPI` reference series of §4.2 — returns **950 monthly
observations, 1947-06 → 2026-07**, on the Jan 1987 = 100 base:

- CHAW is used unchanged from 1987-01 (verified equal element-for-element in the
  test suite).
- Before 1987-01, CDKO is rescaled by `factor = 100 / CDKO(1987-01) =
  100 / 394.5 = 0.2534854…`.
- **Splice verification:** CHAW/CDKO is constant at **0.2535** to 4 dp over all
  **475** overlapping months (maximum departure from the factor 2.9e-05, i.e.
  ~0.01%); `rpi_index()` raises rather than returning a distorted index if a
  future vintage breaks that. The residual variation is CDKO's published
  1-dp rounding, not a base break.
- §14 GBR relies on this: pre-1987 index-linked gilts quote base RPIs on the
  Jan-1987 base while the only monthly RPI before 1987 lives in CDKO.
- CDKO also carries **annual** observations back to **1800** (title: "Long run
  series: 1800 to 2024"); `rpi_index()` uses the monthly array only.

## HMT_DMR

Resolved through `https://www.gov.uk/api/content/government/publications/debt-management-report-{edition}` →
`details.attachments[]`.

| part | HTTP | bytes | sha256[:12] | format |
|---|---|---|---|---|
| 2026-27 | 200 | 583,046 | `7ed70b794bb7` | PDF |
| 2026-27_html | 200 | 318,171 | `4a1191694bd9` | HTML |
| 2025-26 | 200 | 551,437 | `026d20d8f5f5` | PDF |
| 2025-26_html | 200 | 302,516 | `1153e5f9d8cb` | HTML |
| 2024-25 | 200 | 601,348 | `ae094fb0dde9` | PDF |
| 2023-24 | 200 | 633,153 | `93ed515b05af` | PDF |

- **Only 2025-26 and 2026-27 have an accessible HTML rendering.** For 2024-25
  and 2023-24 the content API lists a PDF attachment only, and the guessable
  HTML slug 404s — those two editions are PDF-only and `dmr_tables()` raises
  `FileNotFoundError` for them. The HTML slug is not guessable either: 2025-26's
  is `…/debt-management-report-2025-26-accessible`, 2026-27's is
  `…/debt-management-report-2026-27`, so both are read from the API.
- Attachment URLs are opaque `assets.publishing.service.gov.uk/media/<id>/…`
  paths — the API lookup is mandatory, and the media ids will change if HMT
  re-uploads a file.

`dmr_tables(edition)` parses tables **3.A**, **A.1** and **A.2** from the HTML
into a long frame (`table, row_index, row, column, value_text, value`):

| edition | 3.A | A.1 | A.2 |
|---|---|---|---|
| 2026-27 | 22 rows × 2 year columns, 36 numeric cells | 22 × 2, 37 | 19 financial years × 3, 57 |
| 2025-26 | 20 × 2, 34 | 22 × 2, 38 | 18 × 3, 54 |

- gov.uk publishes no `<caption>`: the table number sits in the paragraph
  before the element, so the parser (stdlib `html.parser`; `bs4`/`lxml` are not
  installed in this image and `pandas.read_html` therefore cannot be used)
  keeps a 600-character rolling buffer of the preceding document text and takes
  the **last** `Table X.Y` mention in it.
- Each real table is immediately followed by a one-column footnote table
  carrying the same preceding text; the reader takes the first table under a
  title with at least two columns.
- A.2 rows run **2008-09 → 2026-27** (2026-27 edition) with forecast years
  flagged by footnote markers in the row label (`2025-26(3)`); footnote markers
  are stripped before the numeric parse, and `-`/blank cells are missing, not
  zero. 3.A rows include headings with no figures (`less:`,
  `DMO's NFR will be financed through:`) — kept as rows with NaN values.
- A.1 in the 2026-27 edition contains one genuinely mangled published row,
  `Public sector net debt Z 2,815.2 | 2,923.7 | ` (the label has swallowed the
  first figure). It is preserved verbatim in `value_text` with `value` NaN
  rather than repaired.

## HMT_NLF

Enumerated from `https://www.gov.uk/api/content/government/collections/hmt-central-funds`;
of the 91 documents in the collection, the 20 titled "National Loans Fund
account …" are pulled, one PDF each, part = financial year.

| part | bytes | sha256[:12] | pypdf text | Note 2 extracted |
|---|---|---|---|---|
| 2005-06 | 156,163 | `f41707c780de` | 51,540 ch | yes (8 lines) |
| 2006-07 | 180,033 | `039f605ba181` | mojibake | **no** |
| 2007-08 | 221,632 | `b5b446148ec3` | mojibake | **no** |
| 2008-09 | 169,140 | `ed6d0239075e` | 73,488 ch | yes (8) |
| 2009-10 | 1,685,233 | `0da0e2521fd9` | 90,083 ch | yes (9) |
| 2010-11 | 1,632,931 | `e9069a5cc206` | 87,323 ch | yes (8) |
| 2011-12 | 187,175 | `9c2ce46f6fd3` | 89,602 ch | yes (6) |
| 2012-13 | 250,832 | `7de88917fca6` | 94,667 ch | yes (8) |
| 2013-14 | 853,555 | `132769a8e54a` | 92,444 ch | yes (7) |
| 2014-15 | 858,088 | `a1a5b5f9353c` | 92,820 ch | yes (6) |
| 2015-16 | 725,247 | `f2733c280aca` | 100,116 ch | yes (6) |
| 2016-17 | 399,991 | `f05676514f7d` | 102,858 ch | yes (6) |
| 2017-18 | 589,537 | `01e4da1b52aa` | 110,615 ch | yes (6) |
| 2018-19 | 1,177,349 | `20dc40eb1d0b` | 112,610 ch | yes (6) |
| 2019-20 | 654,362 | `e64afcdc55f1` | 115,760 ch | yes (6) |
| 2020-21 | 1,407,936 | `99fba95cda92` | 125,614 ch | yes (6) |
| 2021-22 | 4,015,672 | `f8102b795630` | 123,014 ch | yes (6) |
| 2022-23 | 656,788 | `800c67eb115b` | 112,441 ch | yes (5) |
| 2023-24 | 749,013 | `75341a59afd6` | 112,247 ch | yes (5) |
| 2024-25 | 1,074,303 | `e02a2b2cd7d6` | 112,826 ch | yes (5) |

`nlf_interest_summary(edition)` extracts note 2 "Finance costs of borrowing"
(the §6.3 step-A GBR cash/effective-interest intermediate) plus the Statement of
Cash Flows "Interest paid" line. Nothing is hand-keyed; nothing is imputed.

- **18 of 20 editions parse.** 2006-07 and 2007-08 are typeset in a font with no
  usable `ToUnicode` map — pypdf returns mojibake ("nɛźɤźǾʍźŠ Ȱʩɛɤʩ¨Ǿʍ …") for the
  entire document — so both return an **empty frame**, as the brief directs.
  (2007-08's figures survive as the prior-year column of the readable 2008-09
  edition; 2006-07's prior-year column lives only in the equally unreadable
  2007-08 edition, so 2006-07 has no machine-readable route at all. Recovering
  either from a neighbouring edition's comparative column is a reconstruction
  decision for D1, not a reader decision, and is not done here.)
- **Extraction check:** in **16 of the 18** readable editions the components
  (gilts + Treasury bills + NS&I + other) sum **exactly** to the note's own
  published total. The two exceptions are the publisher's, not the parser's:
  - 2008-09 and 2009-10 print "Other finance costs" as a heading over
    "Payable in sterling" / "Payable in foreign currencies" with **no sub-total
    line**, so £1,378 m and £365 m respectively sit in rows with `item=""`
    rather than `item="other"`. Both rows are present and captured.
  - 2012-13 as published does not add up: 48,085 + 3,082 + 2,228 + 74 + 184 =
    53,653 against its own printed total of 53,713. The 2013-14 edition restates
    NS&I for 2012-13 as **2,288** (not 2,228), which reconciles exactly — an ONS-
    side typo in the 2012-13 account, corrected the following year. The reader
    reports what each edition prints.
- Parsing defences that were needed: the print typefaces break words with stray
  spaces and ligatures ("Total **fi nance** costs", "3 Income from lending
  **oper ations**"), so headings and item labels are matched on a
  letters-and-digits key, not on words; note 2's title also labels a line of the
  Statement of Comprehensive Net Expenditure ("Financing costs of borrowing 2
  86,949 84,167"), so the heading is the occurrence with **no figures after the
  title**; 2024-25 renamed the note "Financing costs of borrowing"; 2020-21
  splits label and figure across lines; labels carry footnote digits and
  brackets ("FLS Treasury Bills1 74 –", "Treasury Bills (FLS) - 7"), so each
  line is read from the right — trailing figure tokens are the year columns,
  the rest is the label. A published dash is the publisher's nil (0.0), brackets
  are its minus sign.
- Structure varies by era and is preserved rather than normalised: 2005-06 to
  2010-11 split gilts into "Marketable"/"Non-marketable" closed by a "Total"
  line (classified as gilts by the block it sits in); a Treasury bills line
  exists only from 2008-09; 2012-13 carries a one-off "Loss on cancellation of
  Royal Mail gilts" of £3,082 m.
- Three editions (2015-16, 2016-17, 2017-18) publish a web and a print PDF of
  the same account; `nlf_editions()` takes the web rendering.

---

## Environment note

`pypdf` 6.18.0 is installed but **fails to import** in this image: the Debian
`python3-cryptography` it reaches for needs `_cffi_backend`, which is absent, and
the resulting `pyo3_runtime.PanicException` is not an `ImportError`, so pypdf's
own fallback chain does not catch it. `pip install cffi` fixes it. Worth adding
`cffi` alongside `pypdf` wherever the debt extension's dependencies are declared.

---

## Corrections and observations for the register / shared code

1. **`ONS_PSF_APPENDIX_A.object` — "FY from 1998" is one year late.** The
   financial-year block starts at **1997-98** (`Apr 1997 to Mar 1998`); it is the
   *calendar-year* block that starts at 1998. Suggested wording: "CY from 1998,
   FY from 1997-98, quarterly from 1997 Q2, monthly from 1997-04".
2. **`ONS_PSF_APPENDIX_A.object` sheet list.** The workbook has 65 sheets, and
   the PSA6B interest pair is split: **PSA6B_2** is expenditure (NMFX) and
   **PSA6B_1** is receipts (L6BD, the APF interest and dividends the §14 GBR
   note depends on). The current text names only "PSA6B_2 CG interest".
   Sheet name `'PSA6C_2 '` carries a **trailing space** in the workbook.
3. **`ONS_PSF_TIMESERIES.object` first years.** Observed monthly/annual starts
   are BKPM 1975, BKPJ **1986**, NMFX 1946, MW7L 1981, M98R **1984-04**,
   ANTA/AACE/L6BD 1997, ANSK 1946, ANLO 1946 (M98R's annual block starts 1985, its monthly and quarterly blocks 1984-04). The entry omits `AACE` and `ANLO`
   from its narrative list although both are in the CDID set; §13's table row
   also omits them.
4. **`ONS_RPI.object` — CDKO coverage.** CDKO is monthly from **1947-06** but
   annual from **1800**, and its ONS title still reads "1800 to 2024" although
   the series now runs to 2026-07. Suggested: "CDKO long run (Jan 1974 = 100),
   monthly 1947-06–, annual 1800–".
5. **`HMT_DMR.api.landing` points at one edition only.** Each edition is a
   separate gov.uk publication
   (`/government/publications/debt-management-report-{edition}`), and the
   accessible HTML slug differs per edition, so a `landing_template` plus the
   note that **HTML exists only for 2025-26 and 2026-27** would be more
   accurate. `verification.note` should record that A.1/A.2/3.A are machine-
   extractable for those two editions and PDF-only for 2023-24 and 2024-25.
6. **`HMT_NLF` — scope of the collection.** The collection also holds nine
   *combined* "Consolidated Fund and National Loans Fund accounts" publications
   (1996-97 to 2004-05, **2002-03 missing** from gov.uk), which this family does
   **not** pull — the object text mentions them, so either the entry should say
   they are out of scope for now or a second part set should be added.
   Recommend also updating `verification.note` (Q-D7): machine extraction of the
   NLF PDFs is now demonstrated for 18 of 20 editions with an exact internal
   reconciliation in 16.
7. **`ingest.endpoints.ONS_DATASETS` is hard-coded to `/economy/…/publicspending/datasets`.**
   The PSF datasets live under `/economy/…/publicsectorfinance/datasets`, so
   `ons_file_url` and `ons_dataset_meta_url` cannot be reused for this family and
   `families/ons_hmt.py` carries its own builders. Suggest making the dataset
   path prefix an argument. Also note the resolver JSON is at
   `{dataset}/current/data` (`downloads[0].file`), **not** `{dataset}/data`,
   which `ons_dataset_meta_url` currently returns — the latter carries only the
   title and release date, no filename.
8. **`ingest.fetch._ext_for` has no PDF or HTML branch**, so all 26 HMT
   snapshots are stored with extension `.bin`. Harmless (readers address
   snapshots by manifest path and the content type is recorded), but adding
   `pdf` and `html` branches would make `data/raw/HMT_*/` self-describing.
9. **ONS release cadence.** Both workbooks and every time series carry
   `releaseDate 2026-08-20T23:00Z` with `nextRelease "22 September 2026"`; the
   register's `last_update_observed: "2026-08-21"` for Appendix A is the same
   release in local time. A re-pull after 22 September 2026 will be a vintage
   event for all 15 ONS parts at once.
