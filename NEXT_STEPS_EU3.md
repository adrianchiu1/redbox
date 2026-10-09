# Next steps — Italy, Spain, Belgium (Stage E follow-up)

Working list, updated 2026-10-09 (session 17, second pass). Background:
`EU3_KICKOFF.md`, `DECISIONS.md` D-S17-001..019, `HANDOFF.md`.

## Done this pass

- [x] Ageing Report GF10 join approved for ITA/ESP/BEL — GF10 maximum to 2070 (D-S17-013)
- [x] Italy/Belgium Level II start in 2001 accepted (D-S17-015)
- [x] Spain's WEO gap treated as a known perimeter gap (D-S17-014)
- [x] Network: nothing is blocked. tesoro.es and airef.es omit an FNMT
  intermediate certificate — now supplied from `config/certs/` with full
  verification; the other three were wrong/retired addresses (plan.be,
  upbilancio.it, dataexplorer.nbb.be) (D-S17-012)
- [x] Belgium per-bond register from the Debt Agency page (D-S17-016)
- [x] Spain: Tesoro outstanding by instrument and tenor in the aggregates (D-S17-017)
- [x] Seeded forecast intervals; README prose from config; notebook fan
  cells follow the forecasts (D-S17-018)
- [x] UK debt tests: opening stubs no longer count auctions after the
  snapshot date (D-S17-019)
- [x] Belgium R03/R04: Federal Planning Bureau outlook, strict to 2031,
  grade B (D-S17-020)

## Not possible with current sources (decide whether to pursue)

- [ ] **Italy per-bond register.** Recent auction results are one PDF per
  auction; no per-ISIN outstanding file. Options: accept aggregate-only
  (current), or allow PDF ingestion with a second keying (the OQ-5 rule),
  or find a per-ISIN source (e.g. Borsa Italiana / MTS listings).
- [ ] **Spain per-bond register.** The Tesoro's files identify issues by
  tenor and coupon, never ISIN. Same options as Italy.
- [ ] **Belgium year-end positions.** The register is a snapshot; year-end
  history needs an auction history file, not found on the BDA site.

## Build work still open

1. [ ] **More from the Belgian Planning Bureau.** Its T17 also projects
   interest, compensation, intermediate consumption, subsidies, social
   benefits and investment to 2031 — candidates to chain after AMECO
   (2027) on GF01_7 and E01–E08 (V16 decides; may need your approval as
   for the DSM). Its Study Committee on Ageing file (DATA_FOR_VERG_FR.xlsx)
   projects pensions long-term — a candidate for GF10_2, where the Ageing
   Report failed (grade D).
2. [ ] **AIReF, UPB, NBB**: no machine-readable fiscal projections found on
   2026-10-09; recheck when their next reports land.
3. [ ] **Step A of the debt chains** (cash interest, cash borrowing
   requirement) for ITA/ESP/BEL: the Tesoro bulletin's "Financiación del
   Estado" (file 09/13) may serve Spain; Italy/Belgium publish PDF only.
4. [ ] **Italy year-end class history**: the MEF December composition file
   is picked up automatically from early 2027.
5. [ ] **Then the USA** — Stage U1 per `REPLICATION_KICKOFF.md`.

## Housekeeping

- [ ] **Open a pull request** for `claude/serene-thompson-soiwhn` when ready.

## How to rebuild everything

See "Exact commands" in `HANDOFF.md`. `ggfiscal debt fetch` takes over 30
minutes (the French Treasury's bot challenges) and needs `pip install
playwright`.
