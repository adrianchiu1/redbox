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
