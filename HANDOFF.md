# HANDOFF.md

Rewritten 2026-10-07, end of session 17 (Stage E — Italy, Spain and
Belgium, `EU3_KICKOFF.md`, on `claude/serene-thompson-soiwhn` branched
from `main` at 4374a31).

## Session 17 (2026-10-07): ITA, ESP and BEL carry the full fiscal package and the DD8 debt layer; no number moved for GBR, FRA, DEU or USA on the same vintages

The committee asked for the FRA/DEU approach on ITA/ESP/BEL, with the debt
layer, before USA U1, built from main, Level II before 2001 from IMF GFS
as for DEU, and Spain's debt from the Banco de España (DE1–DE6). Decisions
**D-S17-001 .. D-S17-010**; open questions **OQ-17 .. OQ-19**.

- Fiscal (stages E0–E6 in one pass, `stage_reached: 6`): Eurostat anchors,
  41 lines + ledger 1995–2025, backward legs (OECD RS revenue from 1965;
  AMECO ESA_EXP from 1995 — AMECO's own start for the three), AMECO / AR /
  DSM forward legs by registration, declarations in config, WEO bridge and
  §8.3, flat files `strict_{ITA,ESP,BEL}.csv`, statistical forecasts,
  benchmarks, chartbook sections and nine forecast books.
- Data facts met: ESP publishes no D.92/D.99 split (R10 via D.9 − D.91) and
  no D.51 payer split in gov_10a_main (taxag, identical); BEL's TR − TE ≠
  B.9 by up to EUR 0.8 mn; BEL's GDP agrees across sources in 2025.
- DE3 measured: nothing reachable has ITA/BEL Level II before 2001 (OQ-18).
- Debt: `eu3_offices` family (MEF, BDA, Banco de España),
  `aggregates_eu3`, `official_totals_{ita,esp,bel}`; chains 1995–2025.
  Per-security registers are Stage ED3 (below).
- Fixes found on the way: `ggfiscal debt build` had raised since U0
  (official_totals iterated the USA); the downstream packaging and the
  notebook tool had picked up the USA (now gated to stage 6).

## Blocked on whom

- **Committee (OQ-17):** approve the DSM interest joins (GF01_7, E05) and
  the AR GF10 join for ITA/ESP/BEL as for FRA/DEU — one
  `v16_approved_joins` row each + rebuild. Until then those lines end at
  2027 for the three.
- **Network:** `www.tesoro.es` fails TLS verification (incomplete chain;
  DE4 uses the Banco de España); `www.airef.es`, `www.upbinfo.it`,
  `www.planbureau.be`, `stat.nbb.be` are egress-denied (national
  forecasts — not needed for the FRA-level package);
  `infostat.bancaditalia.it` requires a login.
- Informational: OQ-18 (Level II start 2001), OQ-19 (ESP V24).
- Pre-existing: 3 GBR debt tests fail on the 2026-10-07 DMO vintage with
  main's code too (pytest 473 passed, 3 failed).

## Next: Stage ED3 — per-security registers (BEL, then ITA)

1. **BEL**: `register_bel.py` from `BEL_BDA/olo_outstanding_html` — three
   tables: 38 OLO lines (maturity, coupon, ISIN, net outstanding,
   buy-backs in portfolio, stripped capital), 13 Treasury Certificates,
   56 EMTN/Schuldschein/other lines (currency, coupon or Euribor spread,
   EUR equivalent). Positions `office_snapshot` at the page date; the
   maturity profile from them. Year-end positions need an auction history
   (not yet found on the BDA site — look under `datafederalstateissues`).
   Watch the chains: a snapshot year must not add a register step to a
   year the official totals do not cover.
2. **ITA**: auction results are HTML per auction
   (`/it/debito_pubblico/emissioni_titoli_di_stato_interni/risultati_aste/`)
   plus the archive xls (`Risultati-aste-BTP-*.xls`); no per-ISIN
   outstanding file — the AFT method (anchor + walked-back operations)
   needs an anchor; candidate: the MEF monthly bulletin.
3. **ESP**: stays aggregate (DE4) until the Tesoro is reachable.

## Exact commands

```
pip install -e ".[dev,forecast,notebook]" && pip install playwright   # debt browser path
ggfiscal fetch --all                          # 187 pulls
ggfiscal debt fetch                           # > 30 min (AFT challenges): run in background, 2 h limit
ggfiscal build && ggfiscal reconcile && ggfiscal validate && ggfiscal report && ggfiscal flatten
ggfiscal statistical-forecasts && ggfiscal forecast-levels && ggfiscal benchmark-balance && ggfiscal benchmark-vs-weo
python3 tools/update_notebooks_s11.py
jupyter nbconvert --execute --inplace notebooks/chartbook*.ipynb notebooks/derivation.ipynb notebooks/forecasts_*.ipynb
ggfiscal debt build && ggfiscal debt validate && ggfiscal flatten
python3 -m pytest -q
```

Byte identity for a later stage: build a baseline from the branch you
start on, on the SAME vintages (a fresh fetch moves GBR/USA values), in a
worktree with its own `data/canonical` (symlink raw/manifest only), then
`tools/byte_identity.py <baseline> --countries GBR,FRA,DEU,ITA,ESP,BEL,USA ...`.

## Facts not to rediscover (session 17)

- `ggfiscal debt fetch` prints nothing until it ends; snapshots land as it
  goes (check `data/manifest/snapshots.jsonl`). Install `playwright`
  (the browser is preinstalled at /opt/pw-browsers).
- Statistical forecast intervals (Prophet, ETS, combination) are unseeded:
  two runs differ in `se`/lo/hi; compare point columns only.
- MEF CSVs: Latin-1, `;`-separated, Italian number format; the listing
  pages carry the current year's monthly editions only.
- Banco de España `be.zip`: chapter 11 tables `be11*.csv`, six header rows,
  thousand EUR, `_` = missing; `be11b` is monthly PDE debt by sub-sector
  (`..._AES` = Estado).
- BDA spreadsheets (indicators, maturity schedule) are point-in-time.
- AR/DSM sheets exist for IT/ES/BE; AR gross pensions overshoot COFOG 10.2
  for all three (116–132%, grade D).

---

# Previous handoffs


### (previous) Rewritten 2026-09-21, end of session 14 (Stage U0 — verify and harvest the
United States, on `claude/gg-fiscal-stage-u0-usa-9lg74j` branched from
`main` at 4b2e603).

## Session 14 (2026-09-21): Stage U0 complete — the United States is harvested, verified, configured and anchored; no number moved for GBR, FRA or DEU

The six U0 steps of the session brief (kickoff §12 Stage U0, §11.1–§11.4,
§13.1) are built and recorded as **D-S16-001 .. D-S16-012** in
`DECISIONS.md`; the measurements are in `reports/source_verification_USA.md`
(generated by `tools/source_verification_usa.py`, never hand-edited). One
commit per step on this branch.

- `config/countries.yaml` carries the `USA` block of kickoff §11.1 plus
  `level2_source: BEA_NIPA_T316` (D26) and `stage_reached: 0`
  (D-S16-008). `config.COUNTRIES` is four; every accessor derives from it.
- `standardise/readers_oecd.py` (T12 EXP/REV/BAL, T10, T11 items, T1 GDP,
  EO — UNIT_MULT-scaled), `standardise/readers_bea.py` (NIPA flat files,
  register-driven `(table, line)` lookup; a secondary reader, not a family),
  `standardise/proxies.py` (the config-keyed D26 registry).
- `standardise/families.py`: `OecdSnaFamily` = `FAMILIES["oecd_sna"]`,
  the protocol and every site method from the new `lines.yaml` cells
  (`oecd_t11` / `oecd_t12` / `oecd_t10` / `bea_nipa`); per-flow source ids
  (`esa_exp_source`, `revenue_source`, `balance_source`) on the base class,
  defaulting to `main_source` for ONS/Eurostat. `level2()` returns None:
  the build takes the D26 proxies (`level2_proxy_actual`, B) for GF10_2 /
  GF10_5 / GF04_5 and the D10 fallback (= D.41) for GF01_7.
- `ingest/endpoints.py`: per-country pulls enumerate the register's
  `countries` (no ISO3 literal); `all_u0_pulls()` (19 pulls) for the §11.2
  endpoints; the Table 1 GDP flow resolved live
  (`DSD_NAMAIN10@DF_TABLE1_EXPENDITURE,2.0`); Fiscal Data URL builder with
  literal brackets (not pulled). `ggfiscal fetch --all` = 118 pulls.
- `config/sources.yaml`: every §13.1 USA entry (`CBO_SITE`, `SSA_TRUSTEES`
  `status: blocked`, D-S7-001 route named), USA on OECD_T11 / OECD_RS /
  IMF_GFS / IMF_WEO / EC_AMECO, `period_basis: FY` on CBO and OMB.
- The cell mapping (the judgement item) is in
  `crosswalks/OECD_T12_to_ESA_EXP.csv` and
  `crosswalks/OECD_T12_T10_to_ESA_REV.csv` with the measured evidence per
  cell (D-S16-005): R09 = P1O (= P1M + P131, the sales aggregate); R03/R04 =
  T10 D51M/D51O (incl. holding gains, the D51A_C1/D51B_C2 concept); R05 =
  T12 D5 − R03 − R04 + D91; R06 split from T12; R02_A = T10 D214A; E07 =
  D29 + D5 + D4 − D41 + D7 + D8 (= D7 for the USA).
- Stage gating (D-S16-008): the build runs a country's backward legs from
  `stage_reached` 2 and its forecast legs from 3; the forecast-side
  reconciliation runs for stage-3 countries; the stage-3/4/5/6 tests iterate
  `config.countries_at_stage(n)`. The USA canonical layer is anchors only:
  44 lines × 1970–2024 (2,420 strict rows), ledger 1970–2024 with NI.
- V4 reads `may_be_negative` from `lines.yaml`; E07 admits the USA's 1991
  D.7 payable (−25,625 USD mn, allied Gulf War contributions) — D-S16-009.
- `tools/byte_identity.py --countries GBR,FRA,DEU` is the gate for the
  existing countries (D-S16-010); `reports/source_register.csv` publishes
  the `period_basis` column; `report/small_multiples.py` has one column per
  configured country.

## Gate U0 (D-S16-012)

| criterion | result |
|---|---|
| all 41 USA lines have programmatic coverage from ≥ 1 source or a `lines_absent` entry | **holds**: `ggfiscal coverage` 164/164 (USA: 80 (line, source) rows incl. the three `structural_zero` declarations); `S0_COVERAGE` OK |
| §8.2 bridge has a USA base-year row on the latest WEO vintage | **holds**: base 2024 on 2026-04 (and on both earlier vintages), 24 overlap years from 2001; `S0_BRIDGE` OK; V24 WARN on every vintage (sigma 1.5 % of TE > 0.5 — OQ-16) |
| `reports/source_verification_USA.md` | written (generated) |
| GBR/FRA/DEU byte-identical (run_id excepted) | **holds** on every canonical CSV and deliverable restricted to their rows; `exceptions.csv` differs only by the two V18 WARN rows of the blocked registers and the V24 OK row that the USA's scoped WARNs replace, both named on the gate command line |
| `ggfiscal validate` | ERROR=0, WARN=2761, OK=101 (baseline OK=89 WARN=2298; the added WARNs are USA-scoped V1/V25 concept wedges, V24 and V5 diagnostics, and V18 for the two blocked hosts) |
| `python3 -m pytest -q` | 299 passed, 80 skipped, 33 failed, 21 errors — the baseline's 285 plus the 12 new `tests/stage_0/test_u0_usa.py` tests and the two USA cases of the parametrised strict-file tests (the three-country literals now derive from config or `countries_at_stage`); the identical 54 `tests/debt/` failures/errors for absent debt snapshots (OQ-14) |

## Current stage

Parent stages 0–6 complete on the 123-line universe; R0 complete; **U0
complete. Next stage: U1 — canonical history (USA), kickoff §12.** The
canonical layer already carries the USA anchors, the structural zeros and
the D26 proxies (built as a by-product of the family; U1 reviews them and
adds V44); U1's remaining items are the `OECD_T11_to_COFOG.csv` and
`BEA_NIPA_to_COFOG.csv` crosswalks, V44, the small multiples check and the
§8.3 history decomposition review (it runs already: 2001–2024).

## Blocked on whom

Nothing blocks U1. OQ-13 (cbo.gov, ssa.gov blocked; re-tested 403) matters
for the U4 long legs. OQ-15 (GF04_5: no gross-investment-by-subfunction
cell in the NIPA flat files — the proxy is current expenditure) and OQ-16
(the WEO perimeter rule does not hold as a stable gap for the USA) are
informational with defaults. OQ-14 unchanged (run `ggfiscal debt fetch`
before a full `pytest` to see `tests/debt/` green).

## Exact next command (Stage U1)

```
git checkout -b claude/replication-u1-canonical-usa     # from this branch, or from main after merge
pip install -e ".[dev,forecast,notebook]"
ggfiscal fetch --all                                    # 118 pulls (the D8 snapshots are absent in a fresh container)
mkdir -p /tmp/gg_baseline && cp -r data/canonical /tmp/gg_baseline/canonical && cp -r deliverables /tmp/gg_baseline/deliverables
ggfiscal build && ggfiscal reconcile && ggfiscal validate && ggfiscal report && ggfiscal flatten
python3 tools/source_verification_usa.py
python3 tools/byte_identity.py /tmp/gg_baseline --countries GBR,FRA,DEU --new-file strict_USA.csv \
    --new-crosswalk OECD_T12_to_ESA_EXP --new-crosswalk OECD_T12_T10_to_ESA_REV \
    --new-scope register/CBO_SITE --new-scope register/SSA_TRUSTEES --check-now-scoped V24
python3 -m pytest -q
```

Then, per kickoff §12 Stage U1 (Gate U1: 41 lines + ledger 1970–2024 from
anchors; V1–V4, V7–V9, V12, V14, V19–V23, V41, V44 green; small multiples
render; §8.3 history decomposition 2001–2024 runs and passes V26):

1. `validate/r0.py` (or a new `validate/u1.py`): **V44** — every USA Level
   II row is `level2_proxy_actual`, grade B, with a concept note; remainder
   + Σ level2 = parent (V19); the IMF GFS `GF0170_T` comparison reported for
   1980–89. Register it at stage 1 in `runner.V_SUITE_STAGE`.
2. Crosswalks `OECD_T11_to_COFOG.csv` (identity mapping, GF05 structural
   zero, the `_T` vs OTE wedge) and `BEA_NIPA_to_COFOG.csv` (the four D26
   cells with the measured shares of §5 of the USA report); `write_crosswalks`
   picks them up; add them to the byte-identity command as `--new-crosswalk`.
3. Set `stage_reached: 1` for USA in `countries.yaml` (no behavioural
   change until 2); record the U1 gate as D-S16-013.
4. Re-run the chain and the gate command above; every GBR/FRA/DEU value
   must be unchanged.

## Facts not to rediscover (session 14)

- **The chain must not be re-run while `src/` is being edited** (session
  13's rule still holds); every U0 chain here ran after the edits were
  complete. `tools/byte_identity.py` needs the baseline copy made *before*
  the change and, since U0, `--countries GBR,FRA,DEU` with the allowed
  exceptions named (see the command above); it reports `OK` for the three.
- **`stage_reached` gates the legs.** A country at stage < 2 gets no
  backward legs, < 3 no forecasts or D7 declarations (the structural-zero
  declarations always), and no forecast-side §8.3 rows. The generic AMECO
  and OECD RS blocks of `forward.py` / `backward.py` DO apply to the USA
  the moment the stage is raised (AMECO USA rows exist 1960–2027 and V5
  already measures the RS/AMECO overlap for the USA in `exceptions.csv`);
  U2/U3 raise the stage after reviewing them.
- **OECD Table 12 codes for the USA**: OTR = D2 + D5 + D61 + D4 + D7 + D9 +
  D39 + P1O exactly; P1O ("market output, own final use and payments for
  other non-market output") = P1M + P131 = the ESA sales aggregate; D29,
  D5, D8, D39, D92, D4N, P5M are identically zero on the expenditure side;
  D6M = D62 + D632 with D632 = 0; T11 has no GF05 rows and nine functions
  summing to `_T`; T11 `_T` ≠ T12 OTE (−665 to +1,335 mn); T10 D51M + D51O
  = D51 and D51 + D59 = D5, but T10 D5 ≠ T12 D5 by up to 5.8 bn and T10
  D61 ≠ T12 D61 by up to 0.7 bn in some years.
- **NIPA flat files**: `SeriesRegister.txt` cells are `TableId:LineNo`;
  Table 3.16 total-government block = lines 1–41 (5 interest, 14
  transportation, 38 retirement, 40 unemployment), federal from 43; Table
  3.17 gross investment by function is Level I only (lines 105–133) and
  capital transfers by function at 134–145; values are USD millions
  (DefaultScale −6). `NipaDataQ.txt` is 35 MB (snapshotted, unread).
- **EO**: XDC measures are in units (UNIT_MULT 0); GGINTP is the NIPA/IMA
  interest incl. imputed pension interest (+0.94 % on T12 D41 in 2024);
  SSPG = D62, SSRG = D61, TIND = D2 exactly; TYB includes rest-of-world
  taxes (D51O + 38.9 bn).
- **WEO USA**: fiscal series from 2001, latest actual 2025; GGR ≈ 4.2 % of
  TE below OTR and GGX ≈ 4–8.6 % below OTE — a GFSM-basis wedge, not a
  stable perimeter gap (12 of 24 years `unexplained`; OQ-16).
- **Blocked**: `www.cbo.gov` (DataDome) and `www.ssa.gov` (Akamai) return
  403 to every client here; `github.com` too, but
  `raw.githubusercontent.com` (CBO mirror) is open. OMB workbooks need
  `BROWSER_HEADERS`; their file names carry `_fy2027` under
  `/wp-content/uploads/2026/04/`.
- pandas 3.0 in this image: `TIME_PERIOD.astype(int)` on an SDMX-CSV frame
  raises on missing values — coerce with `pd.to_numeric(..., errors=
  "coerce")` first (the readers do).
- `tests/deliverables/test_r0_notebook_tooling.py` seeds a synthetic JPN
  (not USA) as the fourth country now that the real USA has catalogue
  rows; `tools/update_notebooks_s11.py` filters the catalogue to the
  countries it handles. The committed notebooks are untouched; the USA
  books are U6 work.
- Validate's WARN count is container-dependent through `S0_SNAPSHOTS`
  (2298 baseline here vs 2218 in session 13).

---

# Previous handoffs

## Session 13 (2026-09-20): Stage R0 complete — the package is generalised by configuration and readers; no country added, no number changed

The eight R0 steps of REPLICATION_KICKOFF.md §12 (D27, D20, D19 plumbing,
the config flags, the generic GFS legs, the tooling, the debt engine) are
built, each verified by a full chain re-run against a frozen copy of
`src/` and a diff of `data/canonical/` and `deliverables/` against the
session baseline, and recorded as **D-S15-001 .. D-S15-009** in
`DECISIONS.md`.

- `config/countries.yaml` is the single source of country routing;
  `config.COUNTRIES` and every accessor read it; `config/debt.yaml
  countries` does the same for the debt engine.
- `standardise/families.py`: `AnchorFamily` (kickoff §11.3), `OnsFamily`,
  `EurostatFamily`, `config.family(iso3)`; the twelve routing sites call
  it; an unimplemented family raises `FamilyNotConfigured` — never a
  fall-through. `forecast/envelopes.py` chooses the envelope by
  `envelope_forecast`.
- D20: `structural_zero` rows, V41, tolerant identities. D19: per-tree
  period basis, `FY{start_year}` labels, register `period_basis`, weights
  per country, `fy_cy_bridge.csv`, V42.
- Generic IMF GFS COFOG/SOO backward legs, enabled by config (DEU only).
- `tools/update_notebooks_s11.py` seeds a fourth country's books by copy;
  `tools/build_chartsite.py` reads countries from config;
  `tools/byte_identity.py` is the gate script.
- Debt engine: `intermediates.official_totals` has no `else`; register,
  aggregates, chains, reference and V31 route through `debt/countries.py`.

Gate R0 (D-S15-009): byte identity of `data/canonical/` and
`deliverables/` (run_id excepted) held after every step; validate ERROR=0,
WARN=2218, OK=89; pytest 285 passed, 80 skipped, 33 failed, 21 errors (the
54 debt tests failing for absent snapshots, OQ-14).

### Facts not to rediscover (session 13)

- Each R0 step's chain ran against a frozen copy (`PYTHONPATH=<copy>`), so
  the next step could be written while the previous one verified.
- `config.COUNTRIES` is a lazy module attribute (PEP 562) — prefer
  `config.COUNTRIES` at call time in anything a test may monkeypatch
  (`config.countries`).
- A test that adds a country does it by monkeypatching `config.countries`;
  see `tests/stage_0/test_r0_generalisation.py` and
  `tests/deliverables/test_r0_notebook_tooling.py` for the pattern.
- Row order in the canonical CSVs is the insertion order of
  `extensions_for` / `forecasts_for` keys — a registry refactor must keep
  the key order or the CSV reorders.
- `source_period_basis` on a row is the *tree's* published basis, not the
  source's (D-S15-004); the register's `period_basis` is what V42 polices.
- The GF10_2 forecast-candidate block in `coverage.line_sources` and the
  per-country source blocks of `forward.py` / `backward.py` still name
  countries: they are source declarations, not anchor routing.
- `notebooks/*.ipynb` were not touched; `tools/update_notebooks_s11.py`
  rebuilds the companion books WITHOUT outputs on every run.

### Facts not to rediscover (session 12)

- OECD flows verified 2026-09-20: `DSD_NASEC10@DF_TABLE12_{EXP,REV,BAL},1.1`
  and `@DF_TABLE10,1.1`, 13-dim key `A.{iso3}.S13..........`, same
  pattern as T11. USA 1970–2024 CY; JPN T12 2005–2024 CY, T10 1994–2024
  FY, T11 2005–2024 FY (labelled by starting year, equal to IMF GFS and
  ESRI FY cell-for-cell).
- Fiscal Data needs literal brackets in `page[size]` (curl `-g`); OMB
  needs browser headers; BEA's API needs a key (use the TXT flat files);
  cbo.gov and ssa.gov are bot-blocked, CBO's GitHub mirror is open.
- AMECO chapters 6/16/18 carry USA and JPN on ESA names with values equal
  to OECD T12; JPN 2025 is NA in the Spring 2026 file.
- Japan's two D.41 concepts: FISIM-adjusted 7,368 bn (ESRI/OECD/AMECO)
  vs unadjusted 8,657 bn (IMF GFS) in FY2023.
- Research downloads from the scoping session live outside the repo and
  are not D8 snapshots; U0/J0 re-pull everything.

---

# Session 11 and earlier — the parent package state

Everything in the session-11 HANDOFF (git history at 4b2e603: the AFT
briefing D-S12-001, the Level II config mechanism, the ESA_EXP tree, the
R02_A / R06_E / R06_H splits, the benchmark chain D-S11-001..004, the
chartbook facts, the §15 defaults) still holds and is not repeated here.
Its exact command for the parent chain remains:

```
pip install -e ".[dev,forecast,notebook]"
ggfiscal fetch --all && ggfiscal build && ggfiscal reconcile && ggfiscal validate
ggfiscal report && ggfiscal statistical-forecasts
ggfiscal forecast-levels && ggfiscal benchmark-balance && ggfiscal benchmark-vs-weo
python3 tools/update_notebooks_s11.py
jupyter nbconvert --execute --inplace notebooks/chartbook*.ipynb notebooks/derivation.ipynb notebooks/forecasts_*.ipynb
python3 -m pytest -q --ignore=tests/debt
```

The `statistical-forecasts` / `forecast-levels` / `benchmark-*` chain and
the notebooks cover the three packaged countries only until the USA's U6.

## §15 dependencies currently riding on defaults

Unchanged: Q1, Q3, Q4, Q8, Q10, Q13 on defaults; Q11 pinned (D-S6-001);
Q7 and Q12 exercised; Q-K1–Q-K6 on their defaults.
