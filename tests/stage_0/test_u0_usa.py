"""Stage U0 (REPLICATION_KICKOFF.md §12 Stage U0, §11.1-§11.4, §13.1;
D-S16-001..): the United States is configured, its anchor family exists,
its structural zeros are declared, its endpoints and register entries are
in place, and — where the harvest is present — its anchors close their
identities, every line has measured coverage and the §8.2 bridge has a
base-year row. Nothing here touches GBR/FRA/DEU (tools/byte_identity.py
with --countries is the gate for those)."""

import inspect
import re

import pandas as pd
import pytest

from ggfiscal import config
from ggfiscal.ingest import endpoints as E
from ggfiscal.standardise import families as F
from ggfiscal.standardise import readers as R
from ggfiscal.standardise import readers_bea as RB
from ggfiscal.standardise import readers_oecd as RO

needs_harvest = pytest.mark.skipif(
    ("OECD_T12_REV", "USA") not in R.latest_snapshots(),
    reason="USA snapshots not harvested in this environment (run ggfiscal fetch --all)")


# ------------------------------------------------------------- config (§11.1)

def test_usa_config_block_matches_kickoff_11_1():
    usa = config.country("USA")
    assert config.COUNTRIES[-1] == "USA" and usa["currency"] == "USD"
    assert usa["anchor_family"] == "oecd_sna"
    assert usa["anchors"] == {"expenditure": "OECD_T11", "expenditure_esa": "OECD_T12_EXP",
                              "revenue": "OECD_T12_REV", "balance": "OECD_T12_BAL",
                              "tax_detail": "OECD_T10"}
    assert usa["gdp_source"] == "OECD_T1" and usa["secondary_national"] == "BEA_NIPA"
    assert usa["interest_anchor"] == "d41" and config.level2_source("USA") == "BEA_NIPA_T316"
    assert config.lines_absent("USA") == {
        "R01": "no value-added tax; D.211 = 0 in OECD T12",
        "E04": "Medicare and Medicaid are D.62 in the SNA presentation; D.632 = 0",
        "GF05": "BEA has no environmental-protection function; components in 04 and 06"}
    assert config.absent_lines("USA") == {("ESA_REV", "R01"): config.lines_absent("USA")["R01"],
                                          ("ESA_EXP", "E04"): config.lines_absent("USA")["E04"],
                                          ("COFOG", "GF05"): config.lines_absent("USA")["GF05"]}
    assert config.fy_to_cy_weights("USA") == (0.75, 0.25)
    assert config.period_basis("USA")["anchor"] == "CY"
    for cls in config.TREES:
        assert config.tree_period_basis("USA", cls) == "CY"
        assert config.fy_label("USA", 2024, cls) == "2024"
    assert usa["envelope_forecast"] == ["EC_AMECO", "OECD_EO"]
    assert config.weo_perimeter_gap_expected("USA") is True
    assert config.perimeter_break("USA") is None
    assert config.backward_legs("USA") == {}
    assert config.stage_reached("USA") >= 0          # U0 passed; U1 raised it to 1 (D-S17-006)
    assert config.countries_at_stage(3) == ("GBR", "FRA", "DEU")
    assert config.countries_at_stage(0) == config.COUNTRIES
    assert config.country_names()["USA"] == "United States"
    assert config.prose_names()["USA"] == "the United States"
    assert config.country_aliases()["USA"] == ("United States", "US", "USA")
    assert "USD" in config.currencies()
    assert config.universe_size() == 164


def test_usa_is_admitted_by_the_schema_and_the_flat_file_list():
    from ggfiscal import manifest as M
    from ggfiscal.model import _in_countries, _in_currencies

    assert _in_countries(pd.Series(["USA"])).all() and _in_currencies(pd.Series(["USD"])).all()
    assert "deliverables/strict_USA.csv" in M.FLAT_FILES


# ------------------------------------------------- the oecd_sna family (§11.3)

PROTOCOL_METHODS = ("cofog", "cofog_total", "main", "tax", "d41_payable", "gdp",
                    "totals", "level2")
SITE_METHODS = ("d41_receivable", "revenue_lines", "revenue_total", "revenue_coverage",
                "revenue_level2", "esa_exp_parts", "recon_revenue", "bridge_aggregates")


def test_oecd_sna_family_is_registered_and_routes_the_usa():
    assert F.FAMILIES["oecd_sna"] is F.OecdSnaFamily
    fam = config.family("USA")
    assert isinstance(fam, F.OecdSnaFamily) and isinstance(fam, F.AnchorFamily)
    assert fam is config.family("USA")                      # one instance
    for m in PROTOCOL_METHODS + SITE_METHODS:
        assert callable(getattr(fam, m)), m
    assert fam.name == "oecd_sna"
    assert fam.expenditure_source == "OECD_T11"
    assert (fam.esa_exp_source, fam.revenue_source, fam.balance_source) == (
        "OECD_T12_EXP", "OECD_T12_REV", "OECD_T12_BAL")
    assert fam.tax_source == "OECD_T10" and fam.interest_history_source == "OECD_T12_EXP"
    assert fam.revenue_cell_key == "oecd_t12" and fam.esa_exp_key == "oecd_t12"
    # D26: no Level II table — the proxy path, never a fall-through
    for l2 in ("GF01_7", "GF10_2", "GF10_5", "GF04_5"):
        assert fam.level2("USA", l2) is None
    # the per-flow ids default to main_source for the two existing families
    for iso3 in ("GBR", "FRA"):
        f = config.family(iso3)
        assert f.esa_exp_source == f.revenue_source == f.balance_source == f.main_source


def test_line_cells_for_the_oecd_family_and_the_bea_proxies_are_in_lines_yaml():
    exp = config.tree_lines("COFOG")
    for n in range(1, 11):
        assert exp[f"GF{n:02d}"]["oecd_t11"] == f"GF{n:02d}"
    assert exp["TE"]["oecd_t11"] == "_T"
    for l2, line_no in (("GF01_7", 5), ("GF04_5", 14), ("GF10_2", 38), ("GF10_5", 40)):
        assert exp[l2]["bea_nipa"] == {**exp[l2]["bea_nipa"], "table": "T31600", "lines": [line_no]}
        assert exp[l2]["bea_nipa"]["note"]
    esa = config.tree_lines("ESA_EXP")
    assert esa["E07"]["oecd_t12"] == {"plus": ["D29", "D5", "D4", "D7", "D8"], "minus": ["D41"]}
    assert esa["E08"]["oecd_t12"] == {"plus": ["P5", "NP"]} and esa["TE_ESA"]["oecd_t12"] == {"plus": ["OTE"]}
    rev = config.tree_lines("ESA_REV")
    assert rev["R03"]["oecd_t10"] == {"code": "D51M"} and rev["R04"]["oecd_t10"] == {"code": "D51O"}
    assert rev["R02_A"]["oecd_t10"] == {"codes": ["D214A"]}
    assert rev["R06_E"]["oecd_t12"] == {"codes": ["D611"]} and rev["R06_H"]["oecd_t12"] == {"codes": ["D613"]}
    assert rev["R09"]["oecd_t12"] == {"code": "P1O"} and rev["TR"]["oecd_t12"] == {"code": "OTR"}
    assert esa["E07"].get("may_be_negative") is True      # USA 1991 D.7 payable (D-S16-009)
    meta = {sp["parent"]: sp["meta"] for sp in config.level2_splits("COFOG")}
    assert meta["GF10"]["GF10_2"]["bea_nipa"]["lines"] == [38]
    assert meta["GF10"]["GF10_2"]["oecd_t11"] == "GF1002"


def test_no_routing_site_or_family_decides_by_a_usa_literal():
    from ggfiscal import build, coverage
    from ggfiscal.standardise import proxies

    for mod in (build, coverage, F, proxies, RO, RB):
        src = inspect.getsource(mod)
        assert 'iso3 == "USA"' not in src and 'iso3 in ("USA"' not in src, mod.__name__
    # the proxy path is keyed by config, not by country
    assert "BEA_NIPA_T316" in proxies.LEVEL2_PROXY_READERS
    assert proxies.level2_proxy("GBR", "GF10_2", {"bea_nipa": {"table": "T31600", "lines": [38]}}) is None


# --------------------------------------------------- endpoints and register

def test_u0_endpoints_and_pulls():
    assert E.OECD_T1_FLOW == "OECD.SDD.NAD,DSD_NAMAIN10@DF_TABLE1_EXPENDITURE,2.0"
    assert E.oecd_t1_gdp_url("USA").endswith("/A.USA...B1GQ.......?format=csvfile")
    assert E.oecd_t12_data_url("USA", "REV").endswith("DF_TABLE12_REV,1.1/A.USA.S13..........?format=csvfile")
    assert E.oecd_t10_data_url("USA").endswith("DF_TABLE10,1.1/A.USA.S13..........?format=csvfile")
    assert E.oecd_eo_data_url("USA").startswith(f"{E.OECD_BASE}/data/OECD.ECO.MAD,DSD_EO@DF_EO,1.5/USA.YPGT+")
    assert "page[size]=10000&page[number]=2" in E.fiscaldata_url("v1/accounting/od/auctions_query", 10000, 2)
    assert "%5B" not in E.fiscaldata_url("v1/accounting/od/auctions_query")
    assert E.registered_countries("IMF_WEO") == ["GBR", "FRA", "DEU", "USA"]
    assert E.registered_countries("OECD_T12_EXP") == ["USA"]
    assert E.registered_countries("EUROSTAT_GOV10A_EXP") == ["FRA", "DEU"]
    pulls = E.all_u0_pulls()
    keys = {(p.source_id, p.part) for p in pulls}
    assert keys >= {("OECD_T12_EXP", "USA"), ("OECD_T12_REV", "USA"), ("OECD_T12_BAL", "USA"),
                    ("OECD_T10", "USA"), ("OECD_T1", "USA"), ("OECD_EO", "USA"),
                    ("BEA_NIPA", "annual"), ("BEA_NIPA", "quarterly"), ("BEA_NIPA", "register"),
                    ("FRB_Z1", "current"), ("CBO_BASELINE", "baselines"), ("CBO_BASELINE", "actuals"),
                    ("CMS_TRUSTEES", "expanded_tables_2026")}
    assert {p.part for p in pulls if p.source_id == "OMB_BUDGET"} == set(E.OMB_HIST_TABLES)
    assert all(p.headers == E.BROWSER_HEADERS for p in pulls if p.source_id == "OMB_BUDGET")
    assert all("raw.githubusercontent.com" in p.url for p in pulls if p.source_id == "CBO_BASELINE")
    assert not any("cbo.gov" in p.url or "ssa.gov" in p.url for p in pulls)   # blocked hosts, D24
    stage0 = E.all_stage0_pulls()
    assert {p.part for p in stage0 if p.source_id == "OECD_T11"} == {"GBR", "FRA", "DEU", "USA"}
    assert {p.part for p in stage0 if p.source_id == "OECD_RS"} == {"GBR", "FRA", "DEU", "USA"}
    assert ("IMF_WEO_2026_04", "USA_GGXCNL") in {(p.source_id, p.part) for p in stage0}
    assert len(stage0) + len(E.all_stage3_pulls()) + len(pulls) == 118


def test_u0_register_entries():
    src = config.sources()
    for sid in ("OECD_T12_EXP", "OECD_T12_REV", "OECD_T12_BAL", "OECD_T10", "OECD_T1", "BEA_NIPA",
                "FRB_Z1", "OECD_EO", "OECD_EO_LTB", "CBO_BASELINE", "CBO_SITE", "OMB_BUDGET",
                "CMS_TRUSTEES", "SSA_TRUSTEES", "CENSUS_GOVFIN", "BLS_CPI"):
        assert sid in src, sid
        assert src[sid]["countries"] == ["USA"], sid
        assert src[sid]["verification"]["status"], sid
    for sid in ("CBO_SITE", "SSA_TRUSTEES"):
        assert src[sid]["verification"]["status"] == "blocked"
        assert "D-S7-001" in src[sid]["verification"]["note"]
    for sid in ("CBO_BASELINE", "CBO_SITE", "OMB_BUDGET"):
        assert config.source_period_basis(sid) == "FY", sid
    for sid in ("OECD_T12_EXP", "OECD_T10", "BEA_NIPA", "CMS_TRUSTEES", "OECD_EO", "SSA_TRUSTEES"):
        assert config.source_period_basis(sid) == "CY", sid
    for sid in ("OECD_T11", "OECD_RS", "IMF_GFS", "IMF_WEO", "EC_AMECO"):
        assert "USA" in src[sid]["countries"], sid
    from ggfiscal.validate.runner import check_s0_register
    assert all(f.severity == "OK" for f in check_s0_register())


# ------------------------------------------------- readers and the anchors

@needs_harvest
def test_usa_anchor_cells_close_their_identities():
    fam = config.family("USA")
    t12 = lambda item, flow: RO.oecd_t12("USA", item, flow)  # noqa: E731
    ote, otr, b9 = fam.totals("USA")["TE"], fam.totals("USA")["TR"], fam.totals("USA")["B9"]
    assert ote.index.min() == 1970 and ote.index.max() == 2024 and len(ote) == 55
    assert ote[2024] == pytest.approx(11592173.245, abs=0.01)
    assert otr[2024] == pytest.approx(9236733.593, abs=0.01)
    assert (b9 - (otr - ote)).abs().max() < 0.01
    # ESA_EXP identity from the family's own parts
    total = None
    for code, meta in config.tree_lines("ESA_EXP").items():
        if config.is_total(meta):
            continue
        plus, minus = fam.esa_exp_parts("USA", meta)
        s = sum(plus[1:], plus[0]) - sum(minus, pd.Series(0.0, index=plus[0].index))
        total = s if total is None else total + s
    assert (total - ote).abs().max() < 0.01
    # revenue identity from the family's mapping
    rev = fam.revenue_lines("USA")
    total = sum((s for s, _, _ in rev.values()), pd.Series(0.0, index=otr.index))
    assert (total - otr).abs().max() < 0.01
    assert rev["R09"][0][2024] == pytest.approx(t12("P1M", "REV")[2024] + t12("P131", "REV")[2024], abs=0.01)
    # the three structural zeros are identically zero in the anchor (D20)
    assert t12("D211", "REV").abs().max() == 0.0 and len(t12("D211", "REV")) == 55
    assert t12("D632", "EXP").abs().max() == 0.0 and len(t12("D632", "EXP")) == 55
    assert fam.cofog("USA", "GF05").empty                       # no GF05 rows in Table 11
    gf = sum(fam.cofog("USA", f"GF{n:02d}") for n in range(1, 11) if n != 5)
    assert (gf - fam.cofog_total("USA")).abs().max() < 0.01     # so GF05 is zero by additivity
    # D26: T11 D4 x GF01 = T12 D41 to table rounding (USD 3 mn at most); the interest line is D.41
    assert (RO.oecd_t11_item("USA", "GF01", "D4") - fam.d41_payable("USA")).abs().max() <= 3.0
    assert fam.bridge_aggregates("USA")["GF01_7"].equals(fam.d41_payable("USA"))
    gdp, sid = fam.gdp("USA")
    assert sid == "OECD_T1" and gdp[2024] == 29298013.0 and gdp.index.max() == 2025
    assert RO.oecd_eo("USA", "GDP")[2024] == pytest.approx(gdp[2024], rel=1e-6)
    assert RO.oecd_eo("USA", "NLGQ")[2024] < 0      # % of GDP, unscaled


@needs_harvest
def test_bea_register_driven_lookup_and_the_d26_proxies():
    assert RB.nipa_label("T31600", 5) == "G16005 Interest payments"
    assert RB.nipa_label("T31600", 38) == "G16036 Retirement"
    assert RB.nipa_label("T31600", 40) == "G16038 Unemployment"
    assert RB.nipa_label("T31600", 14) == "G16018 Transportation"
    assert RB.series_by_code("A001RC")[1929] == 105322.0           # GNP 1929, USD mn
    fam = config.family("USA")
    d41 = fam.d41_payable("USA")
    for l2, parent, lo, hi in (("GF01_7", "GF01", 0.55, 0.85), ("GF10_2", "GF10", 0.45, 0.7),
                               ("GF10_5", "GF10", 0.005, 0.12), ("GF04_5", "GF04", 0.15, 0.4)):
        meta = config.tree_lines("COFOG")[l2]
        s, note = RB.level2_proxy(l2, meta["bea_nipa"])
        assert s.index.min() == 1959 and s.index.max() == 2024
        assert "D26" in note and "T31600" in note
        share = s[2024] / fam.cofog("USA", parent)[2024]
        assert lo < share < hi, (l2, share)
    interest, _ = RB.level2_proxy("GF01_7", config.tree_lines("COFOG")["GF01_7"]["bea_nipa"])
    ratio = interest[d41.index.intersection(interest.index)] / d41
    assert 0.99 < ratio.min() and ratio.max() < 1.04       # NIPA/IMA interest vs T12 D41


@needs_harvest
def test_usa_anchor_layer_has_zero_rows_and_proxies_and_every_line_is_covered():
    from ggfiscal.build import anchor_series
    from ggfiscal.coverage import gate0_line_coverage, line_sources

    series = anchor_series("USA")
    for cls, code in (("ESA_REV", "R01"), ("ESA_EXP", "E04"), ("COFOG", "GF05")):
        s = series[(cls, code)]
        assert s["observation_type"] == "structural_zero"
        assert (s["series"] == 0).all() and list(s["series"].index) == list(range(1970, 2025))
        assert s["notes"].startswith("structural zero (D20)")
    for l2 in ("GF10_2", "GF10_5", "GF04_5"):
        s = series[("COFOG", l2)]
        assert set(v["observation_type"] for v in s["per_year"].values()) == {"level2_proxy_actual"}
        assert set(v["quality_grade"] for v in s["per_year"].values()) == {"B"}
        assert s["source_id"] == "BEA_NIPA" and s["concept_flag"] == "level2_bea_function"
        assert list(s["series"].index) == list(range(1970, 2025))
    gf017 = series[("COFOG", "GF01_7")]
    assert gf017["source_id"] == "OECD_T11" and len(gf017["per_year"]) == 55   # D10 fallback = D.41
    rem = series[("COFOG", "GF10_X")]["series"]
    assert (rem - (series[("COFOG", "GF10")]["series"] - series[("COFOG", "GF10_2")]["series"]
                   - series[("COFOG", "GF10_5")]["series"])).abs().max() < 1e-6
    srcs = line_sources("USA")
    assert len(srcs) == 41
    for key, entries in srcs.items():
        assert any(not s.empty for _, s, _ in entries), key
    assert [e[0] for e in srcs[("COFOG", "GF10_2")]] == ["OECD_T11", "IMF_GFS", "BEA_NIPA"]
    assert srcs[("COFOG", "GF05")][0][0] == "structural_zero"
    covered, uncovered = gate0_line_coverage()
    assert not [u for u in uncovered if u[0] == "USA"]


@needs_harvest
def test_usa_bridge_has_a_base_year_on_the_latest_vintage():
    from ggfiscal.reconcile import bridge

    latest = next(iter(E.weo_vintages()))
    anchor = bridge.anchor_aggregates("USA")
    assert bridge.base_year(latest, "USA", anchor) == 2024
    assert R.weo_series(latest, "USA", "GGXCNL").index.min() == 2001
    path = config.repo_root() / "data" / "canonical" / "weo_base_bridge.csv"
    if path.exists():
        br = pd.read_csv(path)
        row = br[(br.iso3 == "USA") & (br.weo_vintage == latest) & br.is_base_year]
        assert len(row) == 1 and int(row.year.iloc[0]) == 2024
        assert set(br[br.iso3 == "USA"].classification) <= {"perimeter", "unexplained"}


@needs_harvest
def test_validate_suite_names_the_usa_structural_zeros_and_no_error():
    from ggfiscal.validate.runner import check_s0_coverage, check_s0_line_universe

    lines = check_s0_line_universe()[0]
    assert lines.severity == "OK" and "3 declared structural zero(s)" in lines.message
    cov = check_s0_coverage()
    assert all(f.severity == "OK" for f in cov), [f.message for f in cov]
    path = config.repo_root() / "data" / "canonical" / "exceptions.csv"
    if path.exists():
        ex = pd.read_csv(path, dtype=str, keep_default_na=False)
        assert not (ex.severity == "ERROR").any()
        v41 = ex[ex.check_id == "V41"]
        assert list(v41.severity) == ["OK"] and "3 declared structural zero(s)" in v41.message.iloc[0]
        assert re.search(r"register/CBO_SITE", " ".join(ex.scope))   # the blocked host is visible (V18)
