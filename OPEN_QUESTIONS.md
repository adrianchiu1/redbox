# OPEN_QUESTIONS.md — items for the committee (AC)

References §15 of `COFOG_KICKOFF.md` where applicable. §15 questions are NOT
resolved here; the build uses the stated defaults and records the dependency.

---

## OQ-1 — Network egress policy blocks the Stage 0 harvest (NEW, blocking Gate 0)
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
listed in `HANDOFF.md`. Nothing yet forces an early committee call on any of
them; Q11 (WEO vintage count) will be pinned to what `api.imf.org` actually
exposes once network is available.

## OQ-3 — Raw snapshot archival location (minor)
D-S0-004 keeps raw bytes out of git and provenance in the manifest. If the
committee wants a durable shared archive (LFS, object store), name it and
`ingest/store.py` will grow a sync target. Not blocking.
