# OPEN_QUESTIONS.md — items for the committee (AC)

References §15 of `COFOG_KICKOFF.md` where applicable. §15 questions are NOT
resolved here; the build uses the stated defaults and records the dependency.

---

## OQ-1 — Network egress policy blocks the Stage 0 harvest — **RESOLVED 2026-08-31**
Resolved in the second session: the statistical hosts were allowlisted for
this repo's remote sessions. `ggfiscal fetch --all` completed with 0 failures
(75 pulls, D8 snapshots + manifest committed provenance). The Stage 3+ hosts
listed below (OBR, INSEE, Destatis, BMF, COR, webgate) have NOT yet been
exercised — re-raise if they turn out to be blocked when Stage 3 starts.

Original ask (kept for the record):
Raised 2026-08-31. The remote execution environment denies outbound HTTPS to
every statistical source host (403 policy denial at the egress proxy; also
denied for server-side fetching). Hosts needed:

- `ec.europa.eu` (Eurostat dissemination API)
- `api.imf.org`, `data.imf.org`, `www.imf.org` (IMF SDMX 3.0: WEO, GFS)
- `sdmx.oecd.org` (OECD RS, Table 11, National Accounts)
- `economy-finance.ec.europa.eu` (AMECO bulk)
- `www.ons.gov.uk` (ONS Table 11, GG receipts, PSF interest)
- later stages will also need: `webgate.ec.europa.eu` (Ageing Report/DSM
  annexes), `obr.uk` (OBR EFO/FRS), `www.insee.fr`, `www-genesis.destatis.de`,
  `www.bundesfinanzministerium.de`, `www.cor-retraites.fr`.

**Ask:** either (a) allowlist these hosts for this repo's sessions, or
(b) run `ggfiscal fetch --all` from a network-enabled machine and commit
`data/manifest/` (raw snapshots can be synced separately per D-S0-004).
Everything downstream of the harvest is built and waiting.

## OQ-2 — §15 defaults in force (standing note)
The build proceeds on all §15 defaults (Q1–Q13 as tabled). Dependencies are
listed in `HANDOFF.md`. Q11 is now pinned (D-S0-007): the API exposes only
**3** WEO vintages (2026-04, 2025-10, 2025-04) — below the 5–10 target; per
Q11's own fallback rule all three are retained and the earliest (2025-04) is
noted. No committee action needed unless the committee wants pre-2025-04
vintages sourced from the WEO archive downloads instead (a new decision, not
the default).

Stage 6 update (2026-09-03): the vintage register now lives in
`config/sources.yaml` (`IMF_WEO.api.vintages`, D-S6-001) and
`ggfiscal detect-vintages` diffs the live API against it (D-S6-002) —
registering a future edition is one config entry plus rebuild. The WEO
October 2026 edition, expected mid-October, should be registered and
snapshotted promptly when it appears (the API drops old editions).

## OQ-5 — Pre-1995 expenditure archives need manual ingestion or committee guidance (NEW; limits Stage 2 depth for GBR/FRA expenditure)
Raised 2026-08-31. The §12 Stage 2 archive leg (INSEE pre-ESA95 base series;
GBR PESA "only if reconcilable"; archived ONS T11 vintages all start 1995) has
no machine-readable path in the harvest: these are PDF/scan-era publications
whose ingestion falls under §11.4, which requires an independent second keying
that a single-agent session cannot supply. Expenditure lines therefore stop at
1995 (GBR, FRA) / 1991 (DEU, deliberate reunification stop) with reasons per
line in D-S2-004. **Ask:** either (a) accept the current depth, (b) authorise
a manual-ingest workflow with a second keyer, or (c) point to machine-readable
archive endpoints (e.g. INSEE long series API paths) to register and pull.
Candidate quick win needing neither: ONS long-run PSF series could push GBR
GF01_7/R07 interest history before 1987/1990 — approve a follow-up pull if
wanted.

## OQ-4 — AMECO cannot serve as a UK envelope (NEW, informational; affects Stage 3)
Raised 2026-08-31. AMECO Spring 2026 carries no UK TR/TE level history
(URTG/UUTG exist for 2026–27 only; UBLG/UYIG from 1987). §6.3/Q12 already make
OBR the primary UK envelope with AMECO as cross-check; the cross-check will be
limited to balance and interest, not levels. No default overridden; recorded
so Stage 3 does not rediscover it.

## OQ-3 — Raw snapshot archival location (minor)
D-S0-004 keeps raw bytes out of git and provenance in the manifest. If the
committee wants a durable shared archive (LFS, object store), name it and
`ingest/store.py` will grow a sync target. Not blocking.

## OQ-6 — forecast hosts: PARTIALLY RESOLVED 2026-09-05 (session 5); remaining asks below

Resolved in session 5, 2026-09-05 (D-S7-001/002/003): the committee allowlisted
gov.uk / assets.publishing.service.gov.uk / bmas.de (+ insee.fr,
www-genesis.destatis.de, cor-retraites.fr) and hand-retrieved the OBR
files (obr.uk itself remains Cloudflare-blocked to every client here).
Result: GBR strict forecasts now run on OBR EFO March 2026 + PESA 2026
(R01-R04 to 2030, GF02 to 2028; R05 maximum to 2030; Q12's OBR envelope
exercised). **Remaining asks:**
- (a) an FRS edition WITH functional long-term projections — the 2024
  edition ("Fiscal sustainability" long-term projections data), or the
  2026 edition if one was published in July 2026 — would give GBR
  GF07/GF09/GF10 long-term legs; hand-retrieve as before (D-S7-001).
- (b) a PSF-databank-style welfare-spending FY history (or any OBR file
  carrying welfare outturns before 2024-25) would make the EFO welfare
  series measurable for GF10 (D-S7-003).
- (c) the BMAS Rentenversicherungsbericht is reachable now but PDF-only:
  its ingestion is an OQ-5 second-keying question, not a network one.
- (d) obr.uk challenge-capable access would let `ggfiscal fetch` and
  `detect-vintages` cover OBR without hand-retrieval — worth keeping on
  the list for each new EFO round (the next EFO lands ~November 2026 and
  will need the same manual route otherwise).

Original record (kept):
Stage 3 forecast hosts partially blocked; every GBR-specific source unreachable (predicted by OQ-1's closing note)
Raised 2026-08-31 (session 3). Probed live:

- **Reachable + harvested**: economy-finance.ec.europa.eu (AR 2024 annexes,
  DSM 2025 fiches), bundesfinanzministerium.de (Steuerschätzung xlsx).
- **obr.uk — blocked by the publisher, not the proxy**: Cloudflare JS
  challenge on every path; no client in this environment can pass it (curl
  and server-side fetch get 403; headless Chromium cannot tunnel TLS through
  the egress proxy at all). This blocks OBR_EFO_LATEST, OBR_FRS_2026 — i.e.
  ALL GBR lines beyond what AMECO carries (GF02, GF07, GF09, GF10, R01–R04,
  R07, envelope).
- **Egress-policy denials**: www.gov.uk + assets.publishing.service.gov.uk
  (UK_DEFENCE_PLAN / SR25 tables), circabc.europa.eu (AR detail annexes —
  not needed, the economy-finance copies sufficed), www.bmas.de
  (Rentenversicherungsbericht).
- **PDF-only, unaffected by network**: FRA_LPFP_PSTAB, FRA_LPM_2030,
  FRA_LFSS, COR_2026, DEU_BMF_FINPLAN (§11.4 second keying still
  unavailable — OQ-5).

**Ask:** (a) allowlist gov.uk/assets.publishing and bmas.de;
(b) for obr.uk, either run `ggfiscal fetch` for the OBR pulls from a
network-normal machine and sync the snapshots + manifest, or provide a
challenge-capable fetch path; (c) OQ-5's second-keyer question now also
gates FRA tax lines and all three GF02 lines. Until then GBR strict
forecasts are AMECO-only and §15 Q12's OBR-primary envelope runs on the
AMECO cross-check (levels exist 2026–27 only, OQ-4).

## OQ-7 — D12/V16 withheld joins — **RESOLVED 2026-09-05 (option a, D-S8-001)**

The committee approved the withheld joins; both are applied via the new
`tolerances.v16_approved_joins` config list: FRA/DEU GF01_7 ← DSM (grade
B, strict to 2036) and GBR R06 ← OBR NICs (grade C, maximum to 2030 —
grades still route variants). V16 keeps WARNing on the seams by design.
Standing note for the next vintages: when DSM 2026 (~Feb 2027) and the
next EFO (~Nov 2026) arrive, the seams should shrink — detect-vintages
plus a rebuild refreshes them; no re-adjudication needed unless the
committee wants the approvals revisited (remove the config rows).
The GBR CG-debt-interest candidate for GF01_7 stays out on concept
(grade D, D-S7-003) — no join approval can cure that.

Original item (kept for the record):
D12/V16: AMECO-vs-DSM interest join withheld — committee to adjudicate (blocks the 2028–2036 GF01_7 leg)
Raised 2026-08-31. The DSM 2025 long-term interest path (to 2036, grade-B
coverage) diverges from AMECO Spring 2026 growth by up to −6.5pp (FRA) /
+4.0pp (DEU) per year in the 2025–27 overlap — the DSM predates the Spring
2026 vintage. D12 says above-threshold divergence is flagged, not
auto-joined, so FRA/DEU GF01_7 strict ends at 2027 with the DSM leg recorded
as `not_applied_v16_divergence` (D-S3-005). **Ask:** approve one of
(a) join anyway at 2028 (accepting the vintage seam; one config change),
(b) wait for DSM 2026 (expected ~Feb 2027) and re-run, or (c) keep the 2027
stop. The V5-style diagnostics and both sources' snapshots are in place; no
code change needed for any option.

## OQ-8 — Debt-office hosts: DMO harvested; AFT saved by hand in three rounds — the three registers are built (updated 2026-09-10 night; see D-S10-007)

**Update 2026-09-10 (night).** All three rounds of AFT files are in the
store and France's register is complete on them. What remains behind the
hosts, none of it blocking: (a) the DMO page's own export link for a past
close-of-business date (the year-end positions the DMO publishes, to cross-
check the rolled positions); (b) the AFT "fiche titre" pages per ISIN
(first coupon dates), and the AFT's monthly bulletins if a per-line
buyback record exists in them; (c) budget.gouv.fr programme 117 tables for
the État's own interest (step A). The desktop script keeps its AFT part
for the day the challenge relents.

## OQ-8 (evening) — Debt-office hosts: DMO harvested; AFT pages saved by hand, second round listed (updated 2026-09-10 evening; see D-S10-006)

**Update 2026-09-10 (evening).** Nine AFT pages saved by the committee are
ingested and read; the French snapshot register is built. The AFT
challenges every automated navigation and its static files, so the
remaining items are a second hand-save round (DOWNLOAD_LIST.md, "AFT, second
round"): the OATi encours page, the auction-history page and its files, the
six indexation/index files, the key-figure pages. With the auction history
the French positions are rolled back from the snapshot as the UK's are.

## OQ-8 (afternoon) — Debt-office hosts: DMO reachable and harvested; AFT still needs the desktop run (updated 2026-09-10 pm; see D-S10-005)

**Update 2026-09-10 (afternoon).** The DMO's export endpoint clears the
challenge for the package's browser session (`ggfiscal debt fetch --family
debt_offices`): 14 reports snapshotted, the UK register is built. Two
residual asks: (a) **AFT** — run `python tools/harvest_offices_local.py
--only aft` on a desktop, commit `data/incoming/`, then `ggfiscal debt
ingest-incoming`; (b) **DMO year-end positions** — on the Gilts in Issue page
pick a past close-of-business date, right-click the Excel/XML icon and send
the link (the `COBDate` parameter is ignored by the xml export and answered
with a stub by the xls export; the page's own link must carry the date
elsewhere). Not blocking: positions are rolled from the operations record and
verified against the office's anchors (D-S10-005).

## OQ-9 — UK gilts held inside central government: the ONS/DMR gilt stock is consolidated, the DMO's register is gross (raised 2026-09-10, D-S10-005)
The register's conventional gilts exceed HMT DMR table A.1 and ONS PSA8A_1
BKPM by 150–171 £bn (8%) at end-2023/2024/2025, and the ONS gilt stock by
7–17% from 2008, while the index-linked unindexed nominal matches the DMR to
the million. The ONS series (F.332 at nominal, consolidated within S.1311)
and the DMR table net out gilts held by central-government bodies — the Debt
Management Account, the CRND funds (National Insurance Fund etc.) and others;
the register carries the DMO's gross creation, as DD1 requires. The same
wedge appears in the financing chain (ONS F.332 net financing vs Σ register
issuance: −57 £bn in 2022, −63/−40 in 2008/2009). **Ask:** is an official
series of gilts held by CG bodies (by year, ideally by ISIN) known to the
committee — the DMA's annual accounts, the CRND accounts, or the ONS PSF
methodology's consolidation table? With it the wedge becomes a DD11 holdings
overlay and an official step-A item; without it the residual stays published
as it is now.

Earlier update (kept):
## OQ-8 (morning) — Debt-office hosts: allowlisted 2026-09-10; DMO and AFT behind interactive captchas (see D-S10-004)

**Update 2026-09-10.** The committee allowlisted every domain. Finanzagentur,
Bundesbank, ECB, Banque de France and budget.gouv.fr are reachable on plain
HTTP and harvested (Germany's register is complete). `www.dmo.gov.uk` and
`www.aft.gouv.fr` answer with JavaScript challenges (Radware ShieldSquare,
Cloudflare); the committee authorised a browser session, which cleared both
on first contact, but after the debugging visits both sites now serve
interactive captchas to this address. **Ask (either):** (a) hand-download
the files in `DOWNLOAD_LIST.md` into `data/incoming/` and run
`ggfiscal debt ingest-incoming` — 60 files, of which the UK year-end
position snapshots (28) and the AFT Excel exports (13) matter most; or
(b) allow a cooled-off retry of `browser.py` in a day or two, ideally from a
different egress address, one careful pass with no debugging.

Original item (kept):
## OQ-8 (original) — Debt-office and central-bank hosts denied by the egress policy (2026-09-09)
Raised 2026-09-09 (D-S10-001). Every bond-level source for the debt
extension is unreachable from this environment; the agent cannot change
the allowlist — it is an environment network setting the committee
controls (the route used for OQ-1 and OQ-6). Tested denied: `www.dmo.gov.uk`
(and `pwlb.gov.uk`, `crnd.gov.uk`, `data.gov.uk`), `www.aft.gouv.fr` (and
every `*.data.gouv.fr`, `webstat.banque-france.fr`, `www.budget.gouv.fr`,
`www.performance-publique.budget.gouv.fr`, `bdm.insee.fr`, `api.insee.fr`),
`www.deutsche-finanzagentur.de` (and `www.bundesbank.de`,
`api.statistiken.bundesbank.de`, `genesis.destatis.de`, `www.bundeshaushalt.de`),
`data-api.ecb.europa.eu`, `www.ecb.europa.eu`, `www.emmi-benchmarks.eu`,
`web.archive.org`. **Ask:** allowlist, in priority order:
1. `www.dmo.gov.uk`, `www.aft.gouv.fr`, `www.deutsche-finanzagentur.de`
   (the registers);
2. `www.bundesbank.de`, `api.statistiken.bundesbank.de`,
   `webstat.banque-france.fr`, `data-api.ecb.europa.eu` (yields, TEC10,
   €STR/Euribor, pre-1995 German issuance statistics);
3. `www.budget.gouv.fr`, `www.performance-publique.budget.gouv.fr`
   (programme 117 interest tables), `bdm.insee.fr`.
Fallback per D-S7-001: hand-download the file lists in `DEBT_SCOPING.md`
§6 and ingest with `ggfiscal ingest-file`. Until either happens the
extension builds the reference series, the official intermediates and the
DEU aggregate layer (all reachable), and the per-security register waits.

## OQ-10 — Further breakdowns after the session-11 review — **RESOLVED 2026-09-19 (all three asks approved; D-S13-005)**

The committee approved (a) all four breakdowns, (b) the OBR pensioner series as a C-band backward leg for GBR `GF10_2`, and (c) the E05 ← DSM join. All built and verified end to end (D-S13-005/006). One finding from building: excise duties had to be defined as D.214A + D.2122C because Germany books its energy tax on imported fuels under D.2122C. Not taken up: `GF09_4` tertiary education (optional in the review) — one config entry if wanted.

Original item (kept for the record):

### OQ-10 (original) — Further breakdowns after the session-11 review: what the data says, and three asks (raised 2026-09-19, D-S13-001..004)

The committee asked for a review of every COFOG Level I line and every
revenue line for breakdowns that "make sense", with general public services
and VAT named. Measured from the harvested anchors (Level II groups and
economic items from ONS Table 11 and Eurostat `gov_10a_exp`; tax sub-items
from ONS NTL table 9 and `gov_10a_taxag`), shares of the 2024 total,
GBR / FRA / DEU. Built this session: `GF10_2` old age (pensions) and the
`ESA_EXP` economic tree with `E03` social benefits (D-S13-002/003).

**Expenditure — where a further Level II line would carry weight**

| line | largest groups, % of TE (GBR / FRA / DEU) | verdict |
|---|---|---|
| GF10 social protection (34.5 / 41.5 / 41.3) | old age 10.2: 18.5 / 23.4 / 20.0 — **built**; sickness & disability 10.1: 5.5 / 5.0 / 6.7; social exclusion 10.7: 5.3 / 2.2 / 1.3; family 10.4: 2.9 / 4.0 / 3.9; unemployment 10.5: 0.1 / 2.9 / 3.4; survivors 10.3: 0.1 / 2.4 / 3.8 | **Recommend `GF10_5` unemployment** (the cyclical line, the one automatic stabiliser the §8.3 decomposition could then show; caveat: the UK codes Universal Credit under 10.7, so the UK line is near zero — the note would have to say so). 10.1 is the next largest but no institution forecasts it. |
| GF01 general public services (13.1 / 10.8 / 13.0) | interest 01.7: 6.3 / 3.5 / 2.3 — already split; executive/legislative/fiscal/external affairs 01.1: 4.8 / 2.6 / 4.2; general services 01.3: 1.1 / 3.2 / 3.1; basic research 01.4: 0.0 / 1.2 / 2.0; foreign aid 01.2: 0.8 / 0.3 / 1.0 | **No further functional split recommended.** Once interest is out, `GF01_X` is 7-9% of TE spread over groups that the three statistical offices code differently (the UK books no basic research under 01.4 at all), so a group line would not be comparable across countries. What the committee probably wants from "general government expenditure" — the transfer component (EU contributions, transfers to other units) — is now visible as `E07` other current expenditure in the economic tree, and the compensation/procurement content of GF01 as `E01`/`E02`. |
| GF04 economic affairs (8.6 / 9.9 / 11.0) | transport 04.5: 4.3 / 3.6 / 5.4; R&D 04.8: 1.6 / 1.3 / 0.6; fuel & energy 04.3: 1.0 / 0.9 / 1.4; general economic & labour affairs 04.1: 0.9 / 2.7 / 1.7; agriculture 04.2: 0.6 / 0.4 / 0.4. Economically the most heterogeneous division: subsidies 25 / 31 / 16% of it, capital transfers 0 / 16 / 16%, investment 29 / 20 / 21% | **Recommend `GF04_5` transport** if a second split is wanted: the largest group after old age, hospitals and secondary education, capital-heavy, and the one with a policy handle. 04.3 fuel and energy is where the 2022-23 energy support sits and would be worth a memo series, not a line. |
| GF07 health (19.0 / 15.6 / 15.4) | hospital 07.3: 14.5 / 6.5 / 5.8; outpatient 07.2: 2.2 / 5.5 / 4.6; medical products 07.1: 0.9 / 2.6 / 3.6 | No split: the group shares show institutional coding (the NHS is booked as hospital services), not comparable structure. `E04` (purchased health care in kind) now isolates the part bought from market producers. |
| GF09 education (10.6 / 8.9 / 9.1) | secondary 09.2: 4.9 / 3.8 / 3.1; pre-primary & primary 09.1: 2.3 / 2.5 / 3.0; tertiary 09.4: 1.0 / 0.7 / 1.6 | Optional `GF09_4` tertiary (a distinct policy line; the UK figure is low because student loans are not expenditure). Modest. |
| GF02, GF03, GF05, GF06, GF08 | each ≤ 5% of TE and dominated by one group (military defence 4.3 / 2.9 / 2.1; police 2.8 / 1.7 / 1.5) | No split. |

**Revenue — VAT is already a line; the two splits that carry weight**

| line | sub-items, % of TR (GBR / FRA / DEU) | verdict |
|---|---|---|
| R01 VAT (17.2 / 13.7 / 14.8) | a single ESA item, D.211 | Already separated (§4.2); nothing to add. The OBR, the Steuerschätzung and AMECO all forecast it and the pipeline applies them. |
| R02 other production and import taxes (11.9 / 16.4 / 7.2) | **excise duties D.214A: 5.4 / 3.9 / 1.8**; financial and capital transaction taxes D.214C: 1.6 / 1.1 / –; insurance premium tax D.214G: 0.8 / 1.3 / 0.9; other taxes on production D.29: 3.8 / 8.6 / 2.1 (business rates 2.5; French taxes on land/buildings 4.1 and business licences 3.9) | **Recommend `R02_A` excise duties** (fuel, tobacco, alcohol): the sub-line most discussed, forecast duty by duty by the OBR and the Steuerschätzung, OECD RS heading 5121 for the backward leg, D.214A published by all three anchors from 1995. |
| R06 net social contributions (19.8 / 32.1 / 37.4) | employers' actual D.611: 13.8 / 19.5 / 14.9; households' actual D.613: 5.9 / 9.2 / 20.1; imputed D.612: 0.1 / 3.4 / 2.4 | **Recommend the employers'/households' split** (revisiting §15 Q13, which chose one line with the imputed component flagged): the OBR forecasts employer and employee NICs separately, AMECO carries UTAG (actual) and UTIG (imputed), and the split is the one the 2025-26 UK employer-NICs rise made salient. Imputed contributions would sit with employers' (the ESA convention) with the flag kept. |
| R03 household income taxes (26.6 / 18.3 / 19.6) | France's CSG (~8-9% of TR) sits inside D.51 households | A CSG line would be France-only; not recommended as a common line. |
| R05, R08, R10 | council tax / property taxes 4.4 / 0.4 / –; capital taxes 0.7 / 1.4 / 0.5; the rest under 2% | No split. |

**Asks**
- (a) Confirm or amend the two expenditure recommendations (`GF10_5`
  unemployment, `GF04_5` transport) and the two revenue ones (`R02_A`
  excise duties, the R06 employers'/households' split). Each is now a
  config entry plus its sources and a notebook cell (D-S13-001); the
  revenue split additionally needs the OECD RS / OBR / Steuerschätzung
  crosswalk rows.
- (b) GBR pensions history: the OBR historical public finances database
  carries pensioner spending 1978-79 to 2022-23 (public sector, FY). Used
  as a C-band backward leg it would take `GF10_2` back to 1978 in
  `maximum_extension`. Approve or decline; not built this session.
- (c) `E05` interest (economic tree) ← DSM 2025: the same source, concept
  and overlap divergence the committee approved for `GF01_7` (OQ-7,
  D-S8-001), withheld because the approval list names `GF01_7` only. If
  the committee wants the two interest lines to run to the same 2036
  horizon, add `{iso3: FRA, line_code: E05, incoming_source: EC_DSM}` and
  the DEU row to `tolerances.v16_approved_joins` and rebuild — one config
  change, no code.
## OQ-11 — Cyclically adjusted variants: not available at our granularity (NEW, informational + one decision)

Raised 2026-09-10 (session 6), in answer to the committee's question: is the
data this repo stitches available in cyclically adjusted form from official
sources, for GBR/FRA/DEU? Full evidence and measured spans in
`reports/cyclical_adjustment_availability.md` (+ `.csv`).

**Findings, all verified live 2026-09-10:**
- **COFOG expenditure: nothing exists**, from Eurostat (0 of 8,156
  dataflows), OECD, AMECO, IMF WEO, ONS/OBR, Destatis or INSEE. This is
  methodological, not editorial: under the EU method (DG ECFIN DP 098) the
  ONLY cyclical expenditure item is unemployment-related spending, which sits
  inside `GF10` and is never published separately. A cyclically adjusted
  `GF02` or `GF07` is an *undefined* concept, not an unpublished series —
  constructing one would be original research, which D13/D16 forbid.
- **Revenue: 4 of our 10 lines have an official adjusted analogue**, from the
  OECD Economic Outlook only — `TINDA` → `R01`+`R02` (jointly; no VAT split),
  `TYHA` → `R03`, `TYBA` → `R04`, `SSRGA` → `R06`. Spans 1971/1985/1991–2027.
  `R05`, `R07`–`R10` have none anywhere.
- **Aggregates are well covered** (AMECO `UBLGAP`/`URTGAP`/`UUTGAP`, IMF WEO
  `GGSB_NPGDP`, OECD `NLGQA`, OBR CANB/GGNB). One trap: **AMECO's GBR
  `URTGAP`/`UUTGAP` carry 2026–2027 only** — the same post-Brexit hole OQ-4
  records for unadjusted `URTG`/`UUTG`, so OQ-4's conclusion carries over
  unchanged.
- Caution for the record: Eurostat/NSI **seasonally and calendar adjusted**
  quarterly government data is a within-year timing adjustment and is NOT
  cyclical adjustment. The two must not be conflated.

**Ask (one decision):** whether to add cyclical context to the §8
reconciliation module — nothing enters the 66 lines either way.
(a) Add IMF WEO `GGSB_NPGDP` + `NGAP_NPGDP` to §8 reconciliation only. The
pipeline already pulls this dataflow and vintage; it is a `sources.yaml`
subject-list change, no new source, no code change. **Recommended.**
(b) Also register OECD EO as a reconciliation source for the four revenue
lines above, carrying the measured concept wedges (VAT not split; `SSRGA`
excludes imputed contributions; OECD adjusts on its own output gap, so
adjusted levels from different providers are never additive).
(c) Do nothing.

Not recommended under any option: constructing cyclically adjusted COFOG
lines from published elasticities (D13/D16).

**Incidental unblock for OQ-6:** the March 2026 EFO PDF is mirrored on
`assets.publishing.service.gov.uk` (allowlisted under D-S7-002) and fetched
cleanly here, while `obr.uk` returned 403 as usual. The gov.uk asset mirror
can stand in for obr.uk **for EFO documents**, softening OQ-6(d) for each new
EFO round. It does not cover the PSF databank or supplementary tables, which
remain obr.uk-only.

## OQ-12 — Replicating the package for the United States and Japan (NEW, scoping; ten decisions)
Raised 2026-09-20. The committee asked what it would take to replicate the
package (three trees, ledger, WEO reconciliation, debt extension) for `USA`
and `JPN`. The answer is `REPLICATION_SCOPING.md`: source-by-source
findings tested live from the sandbox, the code audit, an effort estimate
(≈ 30 engineering-days for the first country including a one-off
generalisation of the package, ≈ 20 for the second) and ten questions
Q-R1–Q-R10 with build defaults. Headlines: the US has no COFOG Level II and
no general-government forecaster but fully machine-readable anchors from
1970 and a complete Treasury register from 1979; Japan has Level II from
FY2005 and a 100-year pension valuation but every functional table is
fiscal-year only and its projections are PDF-only Japanese. **Ask:** answer
Q-R1 (anchor), Q-R2 (Japan's COFOG basis) and Q-R10 (scope of the first
cut) first; the rest can follow the defaults. Nothing has been registered
or pulled into the D8 store.
