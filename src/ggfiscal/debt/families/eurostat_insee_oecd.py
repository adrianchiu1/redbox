"""Family 'eurostat_insee_oecd' — pull definitions (DEBT_KICKOFF.md §13, §6.3).

Three registered sources feed this family, machine-readable and reachable:

* ``EUROSTAT_GOV10A_MAIN_S1311`` — ``gov_10a_main``, D41PAY and B9 by
  subsector (step-B interest and financing intermediates, §6.3).
* ``EUROSTAT_GOV10DD`` — ``gov_10dd_ggd`` (debt by instrument x holder x
  maturity), ``gov_10dd_rmd`` (remaining-maturity profile, incl. GD_VAR
  average residual maturity in years), ``gov_10dd_edpt1/2/3`` (EDP notification
  tables, edpt2/3 carrying the stock-flow adjustment components), ``gov_10dd_dcur``
  (debt by currency), ``gov_10q_ggdebt`` (quarterly debt, incl. S13111).
* ``EUROSTAT_PRC_HICP`` — HICP excluding tobacco, current (``prc_hicp_minr``,
  base I25/2025) and archive (``prc_hicp_midx``, base I15/2015) vintages.
* ``EUROSTAT_IRT`` — euro-area money-market rates (``irt_st_m``) and
  long-term government-bond yields (``irt_lt_mcby_m``).
* ``INSEE_IPC`` / ``INSEE_AFT_AGG`` — the INSEE ``serie/ajax`` endpoint:
  CPI ex-tobacco (two base vintages) and the AFT-sourced négociable-debt
  aggregates.
* ``OECD_T7PSD`` / ``OECD_FINMARK`` — OECD SDMX-CSV: quarterly public-sector
  debt by instrument/maturity, and short/long reference rates.

**Key-order corrections found live (2026-09-09), documented in
`reports/debt_sources/eurostat_insee_oecd.md`:**

* ``gov_10dd_ggd``'s key order is ``freq.na_item.sector2.sector.maturity.unit.geo``
  — ``sector2`` (the holder classification, codelist includes ``S1_S2``
  "holders total") comes *before* ``sector`` (the issuing subsector), the
  reverse of the kickoff note's guess. Confirmed against the dataflow's
  SDMX 2.1 content-constraint (dimension order in the cube region) and by a
  live probe.
* The SDMX 3.0 key parser accepts ``*`` (all values) independently per
  dimension, so most ``gov_10dd_*`` pulls wildcard every dimension except
  ``geo`` (and, for ``gov_10dd_ggd``, ``sector``) — one pull per country
  returns the whole table (tens to a few hundred KB) rather than needing one
  pull per instrument/holder/maturity combination.
"""

from __future__ import annotations

from ggfiscal.ingest.endpoints import EUROSTAT_BASE, SDMX_CSV, Pull, eurostat_data_url

OECD_BASE = "https://sdmx.oecd.org/public/rest"

EUROSTAT_GEO = {"FRA": "FR", "DEU": "DE"}
ISO3 = ("GBR", "FRA", "DEU")

_GOV10A_MAIN = "EUROSTAT_GOV10A_MAIN_S1311"
_GOV10DD = "EUROSTAT_GOV10DD"
_PRC_HICP = "EUROSTAT_PRC_HICP"
_IRT = "EUROSTAT_IRT"
_INSEE_IPC = "INSEE_IPC"
_INSEE_AFT_AGG = "INSEE_AFT_AGG"
_T7PSD = "OECD_T7PSD"
_FINMARK = "OECD_FINMARK"

# ---------- INSEE idbanks (serie/ajax; www.insee.fr reachable) ----------

INSEE_IPC_IDBANKS = (
    "001763852",  # IPC ensemble des menages, France, ensemble hors tabac, base 2015 (stopped 2025-12)
    "011814056",  # same series, base 2025 (from 1996-01)
    "001764305",  # IPC ensemble des menages, France metropolitaine, hors tabac, base 2015 (stopped)
)

INSEE_AFT_AGG_IDBANKS = (
    "001711531", "001711532", "001711533",  # encours negociable total / CT / MLT, EUR
    "001719708", "001719709", "001719710",  # same, part en devises
    "001738853", "001738854",               # encours a taux fixe / indexee
    "001738855", "001738856", "001738857", "001738858", "001738859",
    "001738860", "001738861", "001738862",  # YTD flow variations (issuance/redemption breakdown)
)

INSEE_AJAX_BASE = "https://www.insee.fr/fr/statistiques/serie/ajax"
INSEE_HEADERS = (
    ("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    ("Accept", "application/json"),
)


def insee_ajax_url(idbank: str) -> str:
    return f"{INSEE_AJAX_BASE}/{idbank}"


# ---------- OECD SDMX-CSV ----------

T7PSD_FLOW = "OECD.SDD.NAD,DSD_NASEC20@DF_T7PSD_Q,1.1"
FINMARK_FLOW = "OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0"
FINMARK_MEASURES = ("IR3TIB", "IRLT")


def oecd_t7psd_url(iso3: str) -> str:
    """18-dim key: FREQ..REF_AREA............... (freq, [adjustment], geo,
    then 15 wildcarded dims) — verified live against the DSD_NASEC20 DSD."""
    return f"{OECD_BASE}/data/{T7PSD_FLOW}/Q..{iso3}...............?format=csvfilewithlabels"


def oecd_finmark_url(iso3: str, measure: str) -> str:
    """9-dim key: REF_AREA.FREQ.MEASURE.UNIT_MEASURE.......(4 wildcards)."""
    return f"{OECD_BASE}/data/{FINMARK_FLOW}/{iso3}.M.{measure}.PA.......?format=csvfilewithlabels"


def pulls() -> list[Pull]:
    out: list[Pull] = []

    # ---------- gov_10a_main: D41PAY, B9 by subsector (sector wildcarded) ----------
    for na_item in ("D41PAY", "B9"):
        for iso3, geo in EUROSTAT_GEO.items():
            key = f"A.MIO_NAC.*.{na_item}.{geo}"
            out.append(Pull(_GOV10A_MAIN, f"gov_10a_main_{na_item}_{geo}",
                             eurostat_data_url("gov_10a_main", key)))

    # ---------- gov_10dd_ggd: freq.na_item.sector2.sector.maturity.unit.geo ----------
    # sector (issuer subsector) fixed per pull; na_item, sector2 (holder,
    # incl. S1_S2 "holders total"), maturity wildcarded.
    for sector in ("S1311", "S13"):
        for iso3, geo in EUROSTAT_GEO.items():
            key = f"A.*.*.{sector}.*.MIO_NAC.{geo}"
            out.append(Pull(_GOV10DD, f"gov_10dd_ggd_{sector}_{geo}",
                             eurostat_data_url("gov_10dd_ggd", key)))

    # ---------- gov_10dd_rmd: freq.sector.maturity.na_item.unit.geo ----------
    # fully wildcarded except geo: returns S13 and S1311, all maturities,
    # GD and GD_VAR, all units (incl. YR average residual maturity) in one pull.
    for iso3, geo in EUROSTAT_GEO.items():
        key = f"A.*.*.*.*.{geo}"
        out.append(Pull(_GOV10DD, f"gov_10dd_rmd_{geo}",
                         eurostat_data_url("gov_10dd_rmd", key)))

    # ---------- gov_10dd_edpt1: freq.unit.sector.na_item.geo ----------
    for iso3, geo in EUROSTAT_GEO.items():
        key = f"A.*.*.*.{geo}"
        out.append(Pull(_GOV10DD, f"gov_10dd_edpt1_{geo}",
                         eurostat_data_url("gov_10dd_edpt1", key)))

    # ---------- gov_10dd_edpt2: freq.unit.sector.na_item.geo (SFA transactions) ----------
    for iso3, geo in EUROSTAT_GEO.items():
        key = f"A.*.*.*.{geo}"
        out.append(Pull(_GOV10DD, f"gov_10dd_edpt2_{geo}",
                         eurostat_data_url("gov_10dd_edpt2", key)))

    # ---------- gov_10dd_edpt3: freq.unit.sector.na_item.geo (SFA valuation/other) ----------
    for iso3, geo in EUROSTAT_GEO.items():
        key = f"A.*.*.*.{geo}"
        out.append(Pull(_GOV10DD, f"gov_10dd_edpt3_{geo}",
                         eurostat_data_url("gov_10dd_edpt3", key)))

    # ---------- gov_10dd_dcur: freq.sector.currency.na_item.unit.geo ----------
    for iso3, geo in EUROSTAT_GEO.items():
        key = f"A.*.*.*.*.{geo}"
        out.append(Pull(_GOV10DD, f"gov_10dd_dcur_{geo}",
                         eurostat_data_url("gov_10dd_dcur", key)))

    # ---------- gov_10q_ggdebt: freq.na_item.sector.unit.geo ----------
    for iso3, geo in EUROSTAT_GEO.items():
        key = f"Q.*.*.MIO_NAC.{geo}"
        out.append(Pull(_GOV10DD, f"gov_10q_ggdebt_{geo}",
                         eurostat_data_url("gov_10q_ggdebt", key)))

    # ---------- prc_hicp_minr (current, I25/2025) and prc_hicp_midx (archive, I15/2015) ----------
    for geo in ("EA", "FR", "DE"):
        out.append(Pull(_PRC_HICP, f"prc_hicp_minr_{geo}",
                         eurostat_data_url("prc_hicp_minr", f"M.I25.TOT_X_TBC.{geo}")))
        out.append(Pull(_PRC_HICP, f"prc_hicp_midx_{geo}",
                         eurostat_data_url("prc_hicp_midx", f"M.I15.TOT_X_TBC.{geo}")))

    # ---------- irt_st_m (EA money-market), irt_lt_mcby_m (long yields) ----------
    for code in ("IRT_M3", "IRT_M6"):
        out.append(Pull(_IRT, f"irt_st_m_{code}",
                         eurostat_data_url("irt_st_m", f"M.{code}.EA")))
    for geo in ("FR", "DE", "EA"):
        out.append(Pull(_IRT, f"irt_lt_mcby_m_{geo}",
                         eurostat_data_url("irt_lt_mcby_m", f"M.MCBY.{geo}")))

    # ---------- INSEE serie/ajax (CPI ex-tobacco, AFT negotiable-debt aggregates) ----------
    for idbank in INSEE_IPC_IDBANKS:
        out.append(Pull(_INSEE_IPC, idbank, insee_ajax_url(idbank), headers=INSEE_HEADERS))
    for idbank in INSEE_AFT_AGG_IDBANKS:
        out.append(Pull(_INSEE_AFT_AGG, idbank, insee_ajax_url(idbank), headers=INSEE_HEADERS))

    # ---------- OECD T7PSD (quarterly public-sector debt) ----------
    for iso3 in ISO3:
        out.append(Pull(_T7PSD, f"T7PSD_{iso3}", oecd_t7psd_url(iso3)))

    # ---------- OECD FINMARK (short/long reference rates) ----------
    for iso3 in ISO3:
        for measure in FINMARK_MEASURES:
            out.append(Pull(_FINMARK, f"FINMARK_{measure}_{iso3}",
                             oecd_finmark_url(iso3, measure)))

    return out
