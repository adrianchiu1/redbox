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

## OQ-7 — D12/V16: withheld long-term joins — committee to adjudicate (blocks the 2028+ legs of GF01_7 FRA/DEU and now R06 GBR)

Session-5 addition (D-S7-003): the same V16 rule also withheld the
AMECO-UTSG→OBR-NICs join for GBR R06 (2028-2030 leg; NICs is a C-band
component of D.61, overlap growth divergence above the 0.02 threshold).
The GBR CG-debt-interest candidate for GF01_7 failed on concept (grade D,
share 0.67-1.28) — that one is not a V16 question and should stay out.
The options below apply to the NICs join as to the DSM join: approve,
wait for the next vintage, or keep the stop — all config-only.

Original item:
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
