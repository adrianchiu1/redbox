# Source family: ecb_bbk

Stage D0 harvest report for `ECB_EMMI_RATES` and `BBK_KAPITALMARKT`
(DEBT_KICKOFF.md §13). Both hosts, previously egress-blocked (OQ-8), are now
reachable. All 7 pulls in `ggfiscal.debt.families.ecb_bbk.pulls()` succeeded
on the first `ggfiscal debt fetch --family ecb_bbk` run (2026-09-09).
`tests/debt/test_ecb_bbk.py`: 7/7 green.

## 1. Per-part harvest record

All URLs `GET`, HTTP 200, `format=csvdata` (ECB) / `format=csv` (Bundesbank).

| source_id | part | bytes | sha256[:12] | n (obs) | first | last |
|---|---|---:|---|---:|---|---|
| ECB_EMMI_RATES | estr | 551,752 | b28d5b5308ab | 1,777 | 2019-10-01 | 2026-09-08 |
| ECB_EMMI_RATES | eonia | 114,727 | 1bf3914b3e53 | 336 | 1994-01 | 2021-12 |
| ECB_EMMI_RATES | euribor_3m | 145,457 | 551c6c3d4106 | 392 | 1994-01 | 2026-08 |
| ECB_EMMI_RATES | euribor_6m | 145,477 | 449fa98127ca | 392 | 1994-01 | 2026-08 |
| ECB_EMMI_RATES | dfr | 3,003,884 | bcb22deaf3a6 | 10,114 | 1999-01-01 | 2026-09-09 |
| ECB_EMMI_RATES | hicp_xt_ea | 118,143 | a9104d9c9578 | 360 | 1996-01 | 2025-12 |
| BBK_KAPITALMARKT | bund_yield_10y | 230,663 | f565c0381ad4 | 7,384 | 1997-08-07 | 2026-09-09 |

`n` is post-parse observation count (NaN/`.` rows dropped for `dfr`'s daily
history — the deposit-facility-rate series has a value on every calendar
day it publishes a "date of changes" observation, not a business-day
calendar, hence 10,114 rows over ~27 years).

## 2. ECB Data Portal (`data-api.ecb.europa.eu`) — key discovery

The dataflow/key/format pattern is `{ECB_BASE}/service/data/{flow}/{key}?
format=csvdata`. Two of the kickoff's key guesses were confirmed as-given;
three needed a live correction, found without needing the ECB SDW website's
own JS search:

* **€STR** — `EST/B.EU000A2X2A25.WT`, daily, confirmed as given.
  `lastNObservations=2` / `firstNObservations=2` probes: first obs
  2019-10-01, matching €STR's actual launch date.
* **Deposit facility rate** — `FM/D.U2.EUR.4F.KR.DFR.LEV`, confirmed as
  given, daily from 1999-01 (the euro's launch).
* **EONIA is monthly-only, not daily.** The kickoff's guess
  `FM/D.U2.EUR.4F.MM.EONIA.HSTA` 404s ("No Series was returned"). The
  correct key is `FM/M.U2.EUR.4F.MM.EONIA.HSTA` — recovered by fetching the
  `CL_PROVIDER_FM_ID` codelist (`GET
  /service/codelist/ECB/CL_PROVIDER_FM_ID`) and grepping its code *labels*
  for "EONIA": several unrelated "deposit spread" codes (e.g.
  `EONIA_L21A224`) cite `FM.M.U2.EUR.4F.MM.EONIA.HSTA` verbatim in their own
  description text, which is what surfaced the `M.` frequency. Confirmed
  live: retropolated history from 1994-01, ending 2021-12 (EONIA was
  discontinued 2022-01-03, so December 2021 is the last full month) —
  matches the kickoff's "1999-2021" expectation on the end date, extends
  further back than expected on the start.
* **Euribor 3M/6M are monthly-only, not daily**, for the same reason: the
  `D.` form of `FM/D.U2.EUR.RT.MM.EURIBOR{3,6}MD_.HSTA` 404s; only
  `M.U2.EUR.RT.MM.EURIBOR{3,6}MD_.HSTA` resolves. History runs from 1994-01
  for both tenors (`firstNObservations` probe), well before the kickoff's
  "1994/1999-" uncertainty — no daily EMMI fixing is republished by the ECB
  Data Portal under any key found (a wildcarded key search,
  `FM/D.U2.EUR.RT.MM..HSTA`, returns zero series — see the caveat below on
  wildcard probing).
* **HICP ex-tobacco item code is `X02200`, not a `TOB000`-shaped code.**
  `ICP/M.U2.N.XEF000.4.INX` (the kickoff's other candidate) is *ex energy
  and food*, not ex-tobacco — a different exclusion basis entirely. The
  correct code was found by fetching the full `CL_ICP_ITEM` codelist
  (`GET /service/codelist/ECB/CL_ICP_ITEM`, ~2,700 codes) and grepping code
  labels for "tobacco": `X02200` = "HICP - All-items excluding tobacco".
  Confirmed live, and its `DOM_SER_IDS` attribute
  (`ICPT.M.VAL.HICP.INDEX.EA.TOT_X_TBC.M`) matches Eurostat's own
  `TOT_X_TBC` coicop code exactly — i.e. `ICP/M.U2.N.X02200.4.INX` is the
  *same underlying series* the `eurostat_insee_oecd` family already
  snapshots as `prc_hicp_minr_EA`/`prc_hicp_midx_EA` (Eurostat is the
  `SOURCE_AGENCY` for this ICP series; the ECB just republishes it). It is
  pulled here as a same-value cross-check but is **not** re-wired into
  `reference.build_reference_series` — `EA_HICP_XT` already exists from
  `eurostat_insee_oecd`, and wiring both would double the row for the same
  `(series_id, date)` pair under two different `source_id`s.

**Wildcard-probing caveat**: the ECB Data Portal accepts a `WILDCARDED_QUERY`
form (an empty key segment, e.g. `FM/D.U2.EUR.4F.MM..HSTA`, matches any
value in that dimension) for exploratory probing, but a request wildcarding
*multiple* dimensions at once (e.g. leaving both `REF_AREA` and
`INSTRUMENT_FM` empty) tripped the site's bot-defence WAF and returned an
HTTP 400 "Your access has been blocked due to security concerns" HTML page
instead of an SDMX response. Single-dimension wildcards were fine; the
codelist-grep approach above avoided the WAF entirely and is the recommended
discovery method for this API going forward.

## 3. Bundesbank SDW REST API (`api.statistiken.bundesbank.de`) — key discovery

The Bundesbank kickoff guess (`BBK01/WZ3409`) 404s — `BBK01` is a legacy
flowRef from the old SDW that the current REST API does not serve under
that path. The documented pattern `/rest/data/{flowRef}/{key}?format=csv`
does work; the correct flowRef/key pair for the 10-year Bund yield is:

```
BBSIS/D.I.ZST.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A
```

— the kickoff prompt's own worked example, confirmed live
(`https://api.statistiken.bundesbank.de/rest/data/BBSIS/D.I.ZST.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A?format=csv`,
200, 10,641 lines including the metadata preamble). It is the
Svensson-method term-structure estimate for listed federal securities
(`S1311` = central government), 10.0-year residual maturity (`R10XX`),
daily. First real observation 1997-08-07 (earlier dates in the series are
present but blank — "No value available" — back to at least 1997-08-01).

**Response format is not SDMX-CSV.** Unlike the ECB, the Bundesbank export
is a bespoke CSV: a metadata preamble (one `key,value` row each for
`Comment (in english)`, `Decimals`, `Time format code`, `category`, `unit`,
`unit multiplier`, `last update`) precedes the data rows, and missing
observations are the literal string `"."` rather than an empty field. The
reader (`bbk_series`) selects data rows by matching the first column against
a `YYYY-MM-DD` pattern rather than depending on a fixed preamble length
(undocumented and not guaranteed stable across datasets).

**Not found within the discovery budget** (documented so a future session
does not re-guess the same keys):

* **The Svensson beta/tau parameters themselves** (β0, β1, β2, β3, τ1, τ2 —
  the curve-fitting coefficients, as opposed to a yield *read off* the
  fitted curve at a given maturity). Guessed keys substituting `BETA0` /
  `PARAM` for `R10XX` in the same key template both 404. No public
  metadata-search endpoint was found under `/rest/metadata/` (every guessed
  path — `/rest/metadata/dataflow/BBSIS`, `/rest/metadata/table/BBSIS`,
  `/rest/metadata/structure/dataflow/...` — 404s with "Unknown path"); the
  Bundesbank's own statistics website has a JS-driven search/browse UI that
  is out of scope for a machine SDMX-style pull.
* **"Umlauf von Bundeswertpapieren"** (the stock-of-federal-securities
  series referenced in `config/debt_sources.yaml`'s `BBK_KAPITALMARKT`
  object description). No flowRef/key was found for it within budget; the
  same metadata-search gap applies.

Both remain `role: reconciliation_intermediate` items for `BBK_KAPITALMARKT`
to pick up in a future session once a working metadata-discovery route (or
a hand-browsed key list) is available; they are not required for the
`EA_ESTR` / `EA_EURIBOR_3M` / `EA_EURIBOR_6M` / `EA_EONIA` /
`DE_BUND_YIELD_10Y` reference series this session adds.

## 4. Reference-series wiring

`reference.build_reference_series` adds five `pct_pa` series, each wrapped
in `try/except FileNotFoundError` so a missing snapshot in another
environment skips that one series (with a `warnings.warn`) rather than
failing the whole build:

| series_id | reader | source_id / part |
|---|---|---|
| `EA_ESTR` | `ecb_bbk.ecb_series` | `ECB_EMMI_RATES` / `estr` |
| `EA_EURIBOR_3M` | `ecb_bbk.ecb_series` | `ECB_EMMI_RATES` / `euribor_3m` |
| `EA_EURIBOR_6M` | `ecb_bbk.ecb_series` | `ECB_EMMI_RATES` / `euribor_6m` |
| `EA_EONIA` | `ecb_bbk.ecb_series` | `ECB_EMMI_RATES` / `eonia` |
| `DE_BUND_YIELD_10Y` | `ecb_bbk.bbk_series` | `BBK_KAPITALMARKT` / `bund_yield_10y` |

Confirmed present in `data/canonical/debt_reference_series.csv` after
`ggfiscal debt build --no-curves` (2026-09-09): 1,777 / 392 / 392 / 336 /
7,384 rows respectively, all with a non-null `snapshot_sha256`.
