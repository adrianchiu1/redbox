# HANDOFF.md

Rewritten 2026-09-08, end of session 6 (the flat-file bundle and the
derivation notebook, on `claude/gbr-fra-deu-govt-expenditure-0lc1w1`
branched from the merged `main` at 7cf4a83).

## Current stage

**Debt extension (DEBT_KICKOFF.md v1.0): Stages D0 and D1 complete
(D-S10-002); D2 blocked on the debt-office hosts (OQ-8).** The parent
package is untouched except: `config.sources()` now merges
`config/debt_sources.yaml`; the snapshot store names pdf/html extensions;
pypdf and cffi are dependencies. Parent baseline still 120 passed (the
three validation tests are order-sensitive when a build runs concurrently —
rerun alone).

## What session 7 did (D-S10-001/002)

- `DEBT_SCOPING.md` (source findings, design, Q-D1–Q-D11) → committee
  accepted defaults → `DEBT_KICKOFF.md` v1.0 (DD1–DD13, V29–V40, D0–D5).
- `ggfiscal.debt`: family pull registry + `debt fetch`; four reachable
  families harvested (138 pulls, all OK) with readers and 57 family tests;
  `debt_offices` family defined but denied by egress.
- Engines (pure, unit-tested): §7 interest (both bases, uplift, bills,
  floaters, premium/discount), DD7 maturity buckets and issuance-by-
  residual-maturity, §8 chain assembler with V32 additivity.
- `debt build` → `data/canonical/debt_reference_series.csv` (350 series)
  and `debt_official_totals.csv` (steps A/B/C per country-year).
- Tests: `tests/debt` 70 passed.

## Blocked on whom

- **OQ-8 (committee)**: allowlist `www.dmo.gov.uk`, `www.aft.gouv.fr`,
  `www.deutsche-finanzagentur.de` (+ Bundesbank, ECB, Banque de France,
  budget.gouv.fr, bdm.insee.fr). Fallback: hand-download the `DEBT_SCOPING.md`
  §6 lists and `ggfiscal ingest-file` with the part names documented in
  `src/ggfiscal/debt/families/debt_offices.py`.
- Q-D7 (committee, later): PDF extraction rule for pre-register years.

## Exact next command

```
ggfiscal debt fetch            # re-harvest (all families; debt_offices will FAIL until OQ-8)
ggfiscal debt build            # reference series + official totals
python3 -m pytest tests/debt -q
```

Next build step (no committee input needed): the aggregate class-level
layer (DD8) from BMF instrument-type totals, ONS gilt/bill stocks and
flows, INSEE/Eurostat FRA aggregates, feeding the register step of both
chains so `debt_interest_reconciliation` and `debt_financing_reconciliation`
publish for every year; then flatten + notebook (D5) on that basis, and
swap in per-security rows as the offices open.

## Data facts future sessions must not rediscover (debt)

- BMF Datenportal flow sheets are cumulative year-to-date (December = full
  year); Tilgungen/Zinsen are negative; values in whole euro. Indent-0
  totals: "Kredite … inklusive Mitfinanzierung" is the wider total the
  instrument tree sums to. From 2025 stock(t) ≠ stock(t−1)+gross−redemptions
  (agio/disagio spreading, +9.9 EUR bn wedge in 2025).
- Kreditaufnahmebericht annex numbering moves by edition: match on title.
  Annex 4.5 (2025 edition) carries Verzinsung 1996–2025 and agrees with the
  Datenportal to 0.5 EUR mn; annex 4.10 parses 2020–2025 only.
- BMF host: Radware bot manager — fresh session, de-DE headers, Referer,
  same-host redirects only, up to 8 retries; large PDFs need Range resume;
  HTML carries per-request `__uzdbm_*` tokens (never hash-stable).
- ONS PSA sheets: locate header/CDID rows by column-A stub, never by
  offset; period labels are `1998`, `Apr 1997 to Mar 1998`, `Apr to Jun
  1997`, `2026 Jul`. PSA CY blocks start 1998; PUSF NMFX annual goes to
  1946; M98R monthly from 1984-04 sums to calendar years directly.
- NLF accounts: 18 of 20 editions parse (2006-07, 2007-08 have no
  ToUnicode map); 2012-13's printed total does not add up (restated in
  2013-14). Finance costs are accrual; "Interest paid" is the cash line.
- RPI: CHAW (Jan 1987=100) from 1987; CDKO (Jan 1974=100) from 1947-06;
  splice factor 100/394.5, constant to 4 dp over the 475-month overlap.
- INSEE: `serie/ajax/{idbank}` returns the full history as an HTML table;
  the csv route 500s; bdm.insee.fr is blocked. FR CPI ex-tobacco base
  2015→2025 chain factor 0.834606 over 360 months.
- Eurostat: gov_10dd_ggd key order freq.na_item.sector2.sector.maturity.
  unit.geo; FR structure-of-debt tables start 2020; DE rmd has 4 of 7
  bands and S1311 from 2004; HICP coicop code is TOT_X_TBC (dimension
  `coicop18` in prc_hicp_minr, `coicop` in the midx archive); UK absent.
- BoE: media CDN 403s a bare requests UA — send browser headers; IADB
  `_iadb-fromshowcolumns.asp` returns CSV when Datefrom ≥ series start,
  else HTML/302; curve workbooks: spot sheet, maturities row 4, dates from
  row 6.
