"""URL builders for every registered machine-readable source.

D-S0-003 chose the access paths; D-S0-006 (2026-08-31, second session) resolved
every id against the live catalogs and switched the Eurostat/OECD/IMF pulls
from full-table to filtered extractions (the filter is part of the recorded
URL, so a snapshot remains a complete, reproducible extraction definition).

Confirmed live 2026-08-31:
  - Eurostat dissemination API, SDMX 3.0 SDMX-CSV; key order
    freq.unit.sector[.cofog99].na_item.geo (nama_10_gdp: freq.unit.na_item.geo).
    The key parser accepts single values only -> one pull per country.
  - IMF api.imf.org SDMX 3.0. WEO editions exposed as THREE vintages today:
    WEO/9.0.0 (April 2026), WEO_2025_OCT_VINTAGE/1.0.0 (October 2025),
    WEO/6.0.0 (April 2025). `+` multi-values accepted in keys.
  - IMF GFS COFOG dataflow: IMF.STA:GFS_COFOG(11.0.0); main-aggregates
    companion IMF.STA:GFS_SOO(12.0.0).
  - OECD Table 11: OECD.SDD.NAD,DSD_NASEC10@DF_TABLE11,1.1 (13-dim DSD).
  - OECD Revenue Statistics: OECD.CTP.TPS,DSD_REV_COMP_GLOBAL@DF_RSGLOBAL,2.1
    (7-dim DSD: REF_AREA.MEASURE.SECTOR.STANDARD_REVENUE.CTRY_SPECIFIC_REVENUE.
    UNIT_MEASURE.FREQ).
  - AMECO bulk zips: ec.europa.eu/economy_finance/db_indicators/ameco/documents/
    ameco{1..18}.zip; Stage 0 takes 6 (domestic product) and 16-18 (government).
  - ONS: dataset pages serve the latest file at
    /file?uri={dataset_uri}/current/{filename}.
"""

from __future__ import annotations

import dataclasses

EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/3.0"
IMF_BASE = "https://api.imf.org/external/sdmx/3.0"
OECD_BASE = "https://sdmx.oecd.org/public/rest"
AMECO_DOC_BASE = "https://ec.europa.eu/economy_finance/db_indicators/ameco/documents"
ONS_BASE = "https://www.ons.gov.uk"
ONS_DATASETS = "/economy/governmentpublicsectorandtaxes/publicspending/datasets"

# Eurostat country codes for our ISO3s
EUROSTAT_GEO = {"FRA": "FR", "DEU": "DE"}
# WEO subject codes used by the reconciliation module (§6.3, §8.1)
WEO_SUBJECTS = ("GGR", "GGX", "GGXCNL", "GGXONLB", "NGDP")


def registered_countries(source_id: str) -> list[str]:
    """The countries a register entry declares (`countries` in
    config/sources.yaml), restricted to the configured country list — the
    per-country pulls of a source enumerate this, so adding a country to a
    source is a register change, never a code change (Stage U0, D-S16-004;
    the former ISO3 literal is gone)."""
    from ggfiscal import config

    declared = (config.sources().get(source_id) or {}).get("countries") or []
    return [c for c in config.COUNTRIES if c in declared]

# WEO vintages: vintage label -> (dataflow id, dataflow version), latest first.
# Since Stage 6 (D-S6-001) the mapping lives in config/sources.yaml
# (IMF_WEO.api.vintages) so that registering a new WEO edition is a config
# change plus rebuild, never a code change (§11.7); the API drops old
# editions, so new ones must be snapshotted promptly (D-S0-007).
def weo_vintages() -> dict[str, tuple[str, str]]:
    from ggfiscal import config

    reg = config.sources()["IMF_WEO"]["api"]["vintages"]
    return {label: (str(v["dataflow"]), str(v["version"]))
            for label, v in reg.items()}

GFS_COFOG_FLOW = ("IMF.STA", "GFS_COFOG", "11.0.0")
GFS_SOO_FLOW = ("IMF.STA", "GFS_SOO", "12.0.0")
OECD_T11_FLOW = "OECD.SDD.NAD,DSD_NASEC10@DF_TABLE11,1.1"
# DF_RSOECD (OECD members) not DF_RSGLOBAL: only the members flow carries the
# 1965– history D15 requires (global flow starts 1990; verified live 2026-08-31).
OECD_RS_FLOW = "OECD.CTP.TPS,DSD_REV_COMP_OECD@DF_RSOECD,2.0"
AMECO_CHAPTERS = (6, 16, 17, 18)

# ONS dataset slug -> current filename (resolved live via {slug}/current/data JSON)
ONS_FILES = {
    "ONS_ESA_T11": ("esatable11annualexpenditureofgeneralgovernment",
                    "esatable11generalgovernment.xlsx"),
    "ONS_GG_RECEIPTS": ("esatable2mainaggregatesofgeneralgovernment",
                        "esatable0200.xls"),
    "ONS_TAX_DETAIL": ("esaquestionnairedetailedtaxandsocialcontributions",
                       "esantl0999.xls"),
    "ONS_TAX_LIST": ("esatable9listoftaxes", "esatable0900.xls"),
}


@dataclasses.dataclass(frozen=True)
class Pull:
    source_id: str     # register id (config/sources.yaml)
    part: str          # sub-identifier within the source (country, vintage, chapter)
    url: str
    accept: str = ""   # optional Accept header (IMF needs the sdmx csv media type)
    headers: tuple = ()  # extra (name, value) headers (EC document store needs
    #                      browser-like headers or it serves a "Sorry" JS page)


def eurostat_data_url(dataset: str, key: str) -> str:
    return (f"{EUROSTAT_BASE}/data/dataflow/ESTAT/{dataset}/1.0/{key}"
            f"?format=csvdata&compress=false")


def imf_dataflow_catalog_url(agency: str = "IMF.RES") -> str:
    """Enumerate an agency's dataflows (all ids, all versions): WEO editions
    appear both as WEO versions and as *_VINTAGE flows (Q11)."""
    return f"{IMF_BASE}/structure/dataflow/{agency}/%2A/%2A"


def imf_weo_data_url(flow: str, version: str, iso3: str, subject: str) -> str:
    """One (country, subject) per pull: the API only serves series-level
    attributes (LATEST_ACTUAL_ANNUAL_DATA, PUBLICATION_DATE — needed for the
    §8.1 base year) on single-series queries; multi-value keys drop them."""
    return (f"{IMF_BASE}/data/dataflow/IMF.RES/{flow}/{version}/"
            f"{iso3}.{subject}.A?attributes=all")


def imf_gfs_data_url(flow: tuple[str, str, str], iso3: str) -> str:
    agency, flow_id, version = flow
    return (f"{IMF_BASE}/data/dataflow/{agency}/{flow_id}/{version}/"
            f"{iso3}.S13.%2A.%2A.%2A.A?attributes=none")


def oecd_rs_data_url(iso3: str) -> str:
    return f"{OECD_BASE}/data/{OECD_RS_FLOW}/{iso3}......A?format=csvfile"


def oecd_t11_data_url(iso3: str) -> str:
    # 13-dim key: FREQ.REF_AREA.SECTOR then 10 wildcards
    return f"{OECD_BASE}/data/{OECD_T11_FLOW}/A.{iso3}.S13..........?format=csvfile"


def ameco_chapter_url(chapter: int) -> str:
    return f"{AMECO_DOC_BASE}/ameco{chapter}.zip"


def ons_file_url(slug: str, filename: str) -> str:
    return f"{ONS_BASE}/file?uri={ONS_DATASETS}/{slug}/current/{filename}"


def ons_dataset_meta_url(slug: str) -> str:
    """Landing-page JSON: carries the dataset title and latest releaseDate."""
    return f"{ONS_BASE}{ONS_DATASETS}/{slug}/data"


def ons_gdp_url() -> str:
    """YBHA — nominal GDP at market prices, £m, calendar years from 1948 (QNA).
    The GBR anchor-vintage GDP denominator (§6.3); ESA Table 2 has no GDP row."""
    return f"{ONS_BASE}/economy/grossdomesticproductgdp/timeseries/ybha/qna/data"


SDMX_CSV = "application/vnd.sdmx.data+csv"


# ---------- Stage 3 forecast sources (resolved live 2026-08-31, session 3) ----------
# The EC document store (economy-finance.ec.europa.eu/document/download) serves
# an anti-bot "Sorry" interstitial to bare clients; browser-like headers are
# required and are part of the recorded pull definition. Blocked Stage 3 hosts
# (obr.uk Cloudflare challenge; gov.uk, circabc.europa.eu, bmas.de egress
# policy) are documented in OPEN_QUESTIONS OQ-6 — no Pull entries exist for
# them until access is granted.

EC_DOC_BASE = "https://economy-finance.ec.europa.eu/document/download"
BMF_BASE = "https://www.bundesfinanzministerium.de"

BROWSER_HEADERS = (
    ("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
    ("Accept-Language", "en-GB,en;q=0.9"),
)

AR_2024_FICHES_URL = (f"{EC_DOC_BASE}/e248db46-f876-4e72-8821-efae678e81ea_en"
                      "?filename=2024_Ageing_Report-Statistical_annex_all_countryfiches.xlsx")
AR_2024_HORIZONTAL_URL = (f"{EC_DOC_BASE}/403cc04f-9487-406b-a48a-22538e0d461c_en"
                          "?filename=2024_Ageing_Report-Statistical_annex_all_horizontal_tables.xlsx")
DSM_2025_FICHES_URL = (f"{EC_DOC_BASE}/19852ffb-d8c5-4d47-a402-aa6179dc8051_en"
                       "?filename=DSM%202025%20country%20fiches%20tables%20and%20graphs.xlsx")
STEUERSCHAETZUNG_2026_05_URL = (
    f"{BMF_BASE}/Content/DE/Standardartikel/Themen/Steuern/"
    "Steuerschaetzungen_und_Steuereinnahmen/Steuerschaetzung/"
    "2026-05-07-ergebnisse-170-steuerschaetzung-dl-xlsx.xlsx?__blob=publicationFile")


# PESA 2026 (July 2026, HMT): departmental DEL history + SR plans — resolved
# via the gov.uk content API after the egress allowlisting of 2026-09-03
# (OQ-6 partial unblock, D-S7-002). Table 1.9 Defence = MoD RDEL+CDEL, £mn.
PESA_2026_CH1_URL = ("https://assets.publishing.service.gov.uk/media/"
                     "6a57728b822fbe6b8245c9a1/PESA_2026_CP_Chapter_1_tables.xlsx")


def all_stage3_pulls() -> list[Pull]:
    """Stage 3 forecast-source pulls (machine-readable, reachable hosts only)."""
    return [
        Pull("EC_AGEING_2024", "country_fiches", AR_2024_FICHES_URL,
             headers=BROWSER_HEADERS),
        Pull("EC_AGEING_2024", "horizontal_tables", AR_2024_HORIZONTAL_URL,
             headers=BROWSER_HEADERS),
        Pull("EC_DSM", "country_fiches_2025", DSM_2025_FICHES_URL,
             headers=BROWSER_HEADERS),
        Pull("DEU_STEUERSCHAETZUNG", "2026_05", STEUERSCHAETZUNG_2026_05_URL,
             headers=BROWSER_HEADERS),
        Pull("HMT_PESA", "chapter-1", PESA_2026_CH1_URL,
             headers=BROWSER_HEADERS),
    ]


def all_stage0_pulls() -> list[Pull]:
    """Every Stage 0 pull: anchors, GDP, WEO vintages, GFS, OECD RS/T11, AMECO, ONS."""
    pulls: list[Pull] = []
    for dataset, sid, key_fmt in (
        ("gov_10a_exp", "EUROSTAT_GOV10A_EXP", "A.MIO_NAC.S13.*.*.{geo}"),
        ("gov_10a_main", "EUROSTAT_GOV10A_MAIN", "A.MIO_NAC.S13.*.{geo}"),
        ("gov_10a_taxag", "EUROSTAT_GOV10A_TAXAG", "A.MIO_NAC.S13.*.{geo}"),
        ("nama_10_gdp", "EUROSTAT_NAMA10_GDP", "A.CP_MNAC.B1GQ.{geo}"),
    ):
        for iso3, geo in EUROSTAT_GEO.items():
            pulls.append(Pull(sid, iso3, eurostat_data_url(dataset, key_fmt.format(geo=geo))))

    pulls.append(Pull("IMF_WEO", "catalog", imf_dataflow_catalog_url(),
                      "application/vnd.sdmx.structure+json"))
    for vintage, (flow, version) in weo_vintages().items():
        for iso3 in registered_countries("IMF_WEO"):
            for subject in WEO_SUBJECTS:
                pulls.append(Pull(f"IMF_WEO_{vintage.replace('-', '_')}",
                                  f"{iso3}_{subject}",
                                  imf_weo_data_url(flow, version, iso3, subject),
                                  SDMX_CSV))
    for iso3 in registered_countries("IMF_GFS"):
        pulls.append(Pull("IMF_GFS", f"cofog_{iso3}", imf_gfs_data_url(GFS_COFOG_FLOW, iso3), SDMX_CSV))
        pulls.append(Pull("IMF_GFS", f"soo_{iso3}", imf_gfs_data_url(GFS_SOO_FLOW, iso3), SDMX_CSV))
    for iso3 in registered_countries("OECD_RS"):
        pulls.append(Pull("OECD_RS", iso3, oecd_rs_data_url(iso3)))
    for iso3 in registered_countries("OECD_T11"):
        pulls.append(Pull("OECD_T11", iso3, oecd_t11_data_url(iso3)))
    for ch in AMECO_CHAPTERS:
        pulls.append(Pull("EC_AMECO", f"chapter{ch}", ameco_chapter_url(ch)))
    for sid, (slug, filename) in ONS_FILES.items():
        pulls.append(Pull(sid, "current", ons_file_url(slug, filename)))
    pulls.append(Pull("ONS_GDP", "ybha", ons_gdp_url()))
    return pulls


# ---------- Stage U0 sources (REPLICATION_KICKOFF.md §11.2, §13.1; verified live
# ---------- 2026-09-21, D-S16-004) ----------
# OECD SNA tables of the `oecd_sna` anchor family (D18): the three Table 12
# flows, Table 10 and the Table 1 GDP flow (resolved live in U0 from the
# OECD.SDD.NAD catalog: `DSD_NAMAIN10@DF_TABLE1_EXPENDITURE,2.0`, 12-dim key,
# B1GQ current prices XDC, UNIT_MULT 6), the Economic Outlook flow, the BEA
# NIPA flat files (the API needs a key), the Fed's Z.1 CSV bundle, the OMB
# Historical Tables (browser headers, or whitehouse.gov serves a challenge
# page), CBO's own GitHub mirror of its baselines (www.cbo.gov is DataDome-
# blocked, D24) and the CMS Medicare trustees' expanded tables. Fiscal Data
# (debt extension, UD0) needs literal square brackets in `page[size]`: the
# URL builder below keeps them unencoded; nothing is pulled from it in U0.
OECD_T12_FLOWS = {flow: f"OECD.SDD.NAD,DSD_NASEC10@DF_TABLE12_{flow},1.1"
                  for flow in ("EXP", "REV", "BAL")}
OECD_T10_FLOW = "OECD.SDD.NAD,DSD_NASEC10@DF_TABLE10,1.1"       # key A.{iso3}.S13..........
OECD_T1_FLOW = "OECD.SDD.NAD,DSD_NAMAIN10@DF_TABLE1_EXPENDITURE,2.0"   # key A.{iso3}...B1GQ.......
OECD_EO_FLOW = "OECD.ECO.MAD,DSD_EO@DF_EO,1.5"                  # key {iso3}.<M1>+<M2>….A
OECD_EO_MEASURES = ("YPGT", "YPG", "GGINTP", "GGINTR", "TYH", "TYB", "TIND", "SSRG",
                    "SSPG", "IGAA", "TKPG", "CGAA", "NLGQ", "GGFLQ", "GDP")
BEA_TXT_BASE = "https://apps.bea.gov/national/Release/TXT"
BEA_NIPA_FILES = {"annual": "NipaDataA.txt", "quarterly": "NipaDataQ.txt",
                  "register": "SeriesRegister.txt"}
FISCALDATA_BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
NYFED_SOMA_BASE = "https://markets.newyorkfed.org/api/soma"
FRB_Z1_ZIP = "https://www.federalreserve.gov/releases/z1/current/z1_csv_files.zip"
OMB_UPLOADS = "https://www.whitehouse.gov/wp-content/uploads/2026/04/"
# Historical Tables workbooks of the FY2027 Budget (resolved from the OMB
# historical-tables page 2026-09-21): 1.1 receipts/outlays/surplus, 1.3 in
# constant dollars and % GDP, 3.1 outlays by superfunction/function, 3.2 by
# function and subfunction (incl. 901 gross interest), 14.1 government
# receipts/expenditures (NIPA-basis totals by level), 15.1 total government
# receipts/outlays as % GDP.
OMB_HIST_TABLES = ("hist01z1", "hist01z3", "hist03z1", "hist03z2", "hist14z1", "hist15z1")
OMB_FY_SUFFIX = "_fy2027.xlsx"
CBO_RAW = "https://raw.githubusercontent.com/US-CBO/eval-projections/main/input_data/"
CBO_FILES = ("baselines.csv", "actuals.csv")
CMS_TR_ZIP = "https://www.cms.gov/files/zip/2026-expanded-supplementary-tables-figures.zip"


def oecd_t12_data_url(iso3: str, flow: str) -> str:
    return f"{OECD_BASE}/data/{OECD_T12_FLOWS[flow]}/A.{iso3}.S13..........?format=csvfile"


def oecd_t10_data_url(iso3: str) -> str:
    return f"{OECD_BASE}/data/{OECD_T10_FLOW}/A.{iso3}.S13..........?format=csvfile"


def oecd_t1_gdp_url(iso3: str) -> str:
    # 12-dim DSD_NAMAIN10: FREQ.REF_AREA.SECTOR.COUNTERPART_SECTOR.TRANSACTION
    # then 7 wildcards; the reader keeps B1GQ / XDC / current prices (V)
    return f"{OECD_BASE}/data/{OECD_T1_FLOW}/A.{iso3}...B1GQ.......?format=csvfile"


def oecd_eo_data_url(iso3: str, measures: tuple[str, ...] = OECD_EO_MEASURES) -> str:
    return f"{OECD_BASE}/data/{OECD_EO_FLOW}/{iso3}.{'+'.join(measures)}.A?format=csvfile"


def bea_txt_url(filename: str) -> str:
    return f"{BEA_TXT_BASE}/{filename}"


def omb_hist_url(table: str) -> str:
    return f"{OMB_UPLOADS}{table}{OMB_FY_SUFFIX}"


def cbo_raw_url(filename: str) -> str:
    return f"{CBO_RAW}{filename}"


def fiscaldata_url(endpoint: str, page_size: int = 10000, page_number: int = 1,
                   **params: str) -> str:
    """Fiscal Data API URL with the literal `page[size]` / `page[number]`
    brackets the service requires (curl `-g`; URL-encoding them returns an
    error). Not pulled in U0 — registered here for the debt extension (UD0)."""
    query = "&".join([f"page[size]={page_size}", f"page[number]={page_number}"]
                     + [f"{k}={v}" for k, v in params.items()])
    return f"{FISCALDATA_BASE}/{endpoint.strip('/')}?{query}"


def all_u0_pulls() -> list[Pull]:
    """Every Stage U0 pull (kickoff §12 Stage U0), country lists from the
    register: OECD T12/T10/T1 and EO per registered country, the BEA flat
    files and register, the Z.1 bundle, the OMB workbooks, the CBO mirror
    files and the CMS zip."""
    pulls: list[Pull] = []
    for flow in ("EXP", "REV", "BAL"):
        for iso3 in registered_countries(f"OECD_T12_{flow}"):
            pulls.append(Pull(f"OECD_T12_{flow}", iso3, oecd_t12_data_url(iso3, flow)))
    for iso3 in registered_countries("OECD_T10"):
        pulls.append(Pull("OECD_T10", iso3, oecd_t10_data_url(iso3)))
    for iso3 in registered_countries("OECD_T1"):
        pulls.append(Pull("OECD_T1", iso3, oecd_t1_gdp_url(iso3)))
    for iso3 in registered_countries("OECD_EO"):
        pulls.append(Pull("OECD_EO", iso3, oecd_eo_data_url(iso3)))
    if registered_countries("BEA_NIPA"):
        for part, filename in BEA_NIPA_FILES.items():
            pulls.append(Pull("BEA_NIPA", part, bea_txt_url(filename)))
    if registered_countries("FRB_Z1"):
        pulls.append(Pull("FRB_Z1", "current", FRB_Z1_ZIP))
    if registered_countries("OMB_BUDGET"):
        for table in OMB_HIST_TABLES:
            pulls.append(Pull("OMB_BUDGET", table, omb_hist_url(table), headers=BROWSER_HEADERS))
    if registered_countries("CBO_BASELINE"):
        for filename in CBO_FILES:
            pulls.append(Pull("CBO_BASELINE", filename.split(".")[0], cbo_raw_url(filename)))
    if registered_countries("CMS_TRUSTEES"):
        pulls.append(Pull("CMS_TRUSTEES", "expanded_tables_2026", CMS_TR_ZIP))
    return pulls


