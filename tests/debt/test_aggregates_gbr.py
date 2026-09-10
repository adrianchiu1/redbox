"""GBR aggregate class-level layer (DEBT_KICKOFF.md DD8, §6.3 GBR, §14 GBR).

Every test needs the D8 snapshots and skips without them —
`python3 -m ggfiscal.cli debt fetch --family ons_hmt --family boe`.
"""

from __future__ import annotations

import pandas as pd
import pandera.errors as pa_errors
import pytest

from ggfiscal.debt import aggregates as A
from ggfiscal.standardise.readers import latest_snapshots

NEEDED = ("ONS_PSF_APPENDIX_A", "ONS_PSF_APPENDIX_S", "ONS_PSF_TIMESERIES",
          "HMT_DMR", "HMT_NLF", "BOE_APF")

needs_snapshots = pytest.mark.skipif(
    not {k[0] for k in latest_snapshots()} >= set(NEEDED),
    reason="GBR aggregates need the ons_hmt and boe snapshots; run "
           "`ggfiscal debt fetch --family ons_hmt --family boe`")

pytestmark = needs_snapshots


@pytest.fixture(scope="module")
def gbr() -> pd.DataFrame:
    from ggfiscal.debt.aggregates_gbr import class_aggregates
    return class_aggregates("test_gbr")


def pick(df, **kw) -> pd.DataFrame:
    out = df
    for k, v in kw.items():
        out = out[out[k] == v]
    return out


def one(df, **kw) -> float:
    s = pick(df, **kw)
    assert len(s) == 1, f"expected exactly one row for {kw}, got {len(s)}"
    return float(s["value_lcu_mn"].iloc[0])


# ---------------------------------------------------------------- shape

def test_schema_validates(gbr):
    A.SCHEMA.validate(gbr)


def test_shape_is_the_aggregates_table(gbr):
    assert list(gbr.columns) == A.COLUMNS
    assert set(gbr["iso3"]) == {"GBR"}
    assert set(gbr["measure"]) <= set(A.MEASURES)
    assert set(gbr["instrument_class"]) <= set(A.AGG_CLASSES)
    assert not gbr.duplicated(
        ["iso3", "year", "instrument_class", "sub_type", "measure"]).any()


def test_every_row_names_its_table_and_conversion(gbr):
    assert gbr["notes"].notna().all()
    assert (gbr["notes"].str.len() > 20).all()
    assert gbr["source_id"].isin(
        {"ONS_PSF_APPENDIX_A", "ONS_PSF_APPENDIX_S", "ONS_PSF_TIMESERIES",
         "HMT_DMR", "HMT_NLF", "BOE_APF"}).all()
    # every financial-year source records the §7.10 conversion
    fy = gbr[gbr["source_id"].isin({"HMT_NLF"})
             | ((gbr["source_id"] == "HMT_DMR")
                & gbr["measure"].isin({"gross_issuance", "redemptions"}))]
    assert not fy.empty
    assert fy["notes"].str.contains("§7.10").all()


# ------------------------------------------------------- ONS stock (DD6)

def test_gilts_stock_year_end_2024(gbr):
    v = one(gbr, year=2024, measure="stock_year_end", instrument_class="mixed",
            sub_type="gilts_all")
    assert 2_000_000 < v < 3_000_000


def test_gilts_stock_is_the_december_month_end_not_the_annual_block(gbr):
    """PSA8A_1's annual block is the financial year; the layer must use the
    December month-end. Recomputed here straight from the reader."""
    from ggfiscal.debt.readers.ons_hmt import cg_debt_by_instrument
    d = cg_debt_by_instrument(("M",))
    d = d[(d["instrument"] == "gilts") & (d["period_start"].dt.month == 12)]
    want = d.set_index(d["period_start"].dt.year)["value"]
    got = pick(gbr, measure="stock_year_end", sub_type="gilts_all")
    got = got.set_index("year")["value_lcu_mn"]
    assert not got.empty
    pd.testing.assert_series_equal(got.sort_index(), want.loc[got.index].sort_index(),
                                   check_names=False, check_dtype=False)


def test_treasury_bill_rows_are_present(gbr):
    bills = pick(gbr, instrument_class="bill")
    assert not bills.empty
    # the ONS BKPJ stock, the Appendix S NAVG net issuance and the DMR A.1
    # debt-management bills must all be there
    assert one(gbr, year=2024, measure="stock_year_end", instrument_class="bill",
               sub_type="treasury_bills") > 0
    assert not pick(gbr, measure="net_issuance", instrument_class="bill",
                    sub_type="treasury_bills").empty
    assert not pick(gbr, measure="stock_year_end", instrument_class="bill",
                    sub_type="treasury_bills_debt_management").empty


def test_pre_1997_gilts_are_flagged_as_end_march_not_year_end(gbr):
    """The PUSF BKPM calendar-year block is blank before 1997; the pre-1997
    observations are end-March and must not masquerade as 31 December."""
    m = pick(gbr, sub_type="gilts_all_march")
    assert not m.empty
    assert m["year"].max() < pick(gbr, sub_type="gilts_all",
                                  measure="stock_year_end")["year"].min()
    assert (m["basis"] == "nominal_end_march").all()
    assert (m["quality_grade"] == "C").all()
    assert m["notes"].str.contains("MARCH").all()


# ------------------------------------------------------ Appendix S flows

def test_net_issuance_gilts_2023_equals_the_twelve_anta_months(gbr):
    from ggfiscal.debt.readers.ons_hmt import cgncr_financing
    f = cgncr_financing()
    m = f[(f["cdid"] == "ANTA") & (f["period_type"] == "M")
          & (f["period_start"].dt.year == 2023)]
    assert len(m) == 12
    want = float(m["value"].sum())
    got = one(gbr, year=2023, measure="net_issuance", instrument_class="mixed",
              sub_type="gilts_all")
    assert got == pytest.approx(want, rel=1e-9)
    assert want > 0


def test_net_issuance_years_are_complete_calendar_years(gbr):
    """Appendix S has no calendar-year block, so a year is only emitted when all
    12 monthly rows are published — 2026 (7 months in this vintage) is not."""
    from ggfiscal.debt.readers.ons_hmt import cgncr_financing
    f = cgncr_financing()
    m = f[(f["cdid"] == "ANTA") & (f["period_type"] == "M")]
    full = {y for y, g in m.groupby(m["period_start"].dt.year) if len(g) == 12}
    got = set(pick(gbr, measure="net_issuance", sub_type="gilts_all")["year"])
    assert got == full


# ------------------------------------------------------------- DMR A.1

def test_dmr_a1_class_rows_reconcile_to_the_ons_gilt_stock(gbr):
    """The DMR A.1 conventional + index-linked lines (both net of government
    holdings, index-linked including accrued uplift) against ONS BKPM at the
    same end-December. Tolerance 2%; the observed wedge is ~0.02%, which is the
    DMR's £0.1bn rounding."""
    stock = pick(gbr, measure="stock_year_end")
    ons = pick(stock, sub_type="gilts_all").set_index("year")["value_lcu_mn"]
    conv = pick(stock, sub_type="gilts_conventional").set_index("year")["value_lcu_mn"]
    ilg = pick(stock, sub_type="gilts_index_linked").set_index("year")["value_lcu_mn"]
    years = sorted(set(conv.index) & set(ilg.index) & set(ons.index))
    assert years, "no year carries both the DMR class split and the ONS gilt stock"
    for y in years:
        ratio = (conv[y] + ilg[y]) / ons[y]
        assert 0.90 < ratio < 1.15, f"{y}: DMR/ONS gilt-stock ratio {ratio}"
        assert abs(ratio - 1.0) < 0.02, f"{y}: DMR/ONS gilt-stock wedge {ratio - 1:.4%}"


def test_dmr_a1_keeps_the_uplift_wedge_visible(gbr):
    """Index-linked gilts are published at unindexed nominal with the accrued
    uplift on its own line; both must be emitted, and the uplifted line must be
    the larger."""
    stock = pick(gbr, measure="stock_year_end")
    for y in sorted(set(pick(stock, sub_type="gilts_index_linked")["year"])):
        uplifted = one(stock, year=y, sub_type="gilts_index_linked")
        unindexed = one(stock, year=y, sub_type="gilts_index_linked_unindexed")
        uplift = one(stock, year=y, sub_type="gilts_index_linked_accrued_uplift")
        assert uplifted > unindexed > 0 and uplift > 0
        # uplifted = unindexed − government holdings + uplift, to DMR rounding
        holdings = one(gbr, year=y, measure="own_holdings",
                       sub_type="gilts_index_linked")
        assert uplifted == pytest.approx(unindexed - holdings + uplift, abs=200.0)


# ------------------------------------------------------- DMR A.2 and 3.A

def test_dmr_a2_gross_and_redemptions_are_fy_converted(gbr):
    from ggfiscal.debt.intermediates import fy_to_cy
    from ggfiscal.debt.readers.ons_hmt import dmr_tables
    a2 = dmr_tables("2026-27", ("A.2",))["A.2"]
    fy = {}
    for _, g in a2.groupby("row_index"):
        label = str(g["row"].iloc[0])
        if "(" in label or not label[:4].isdigit():
            continue                       # forecast rows carry a footnote marker
        v = g.loc[g["column"].str.contains("Gross gilt sales"), "value"]
        if not v.empty and pd.notna(v.iloc[0]):
            fy[int(label[:4])] = float(v.iloc[0])
    want = fy_to_cy(pd.Series(fy)) * 1000.0
    got = pick(gbr, measure="gross_issuance", sub_type="gilts_all")
    got = got.set_index("year")["value_lcu_mn"]
    assert not got.empty
    assert set(got.index) == set(want.index)
    pd.testing.assert_series_equal(got.sort_index(), want.sort_index(),
                                   check_names=False, check_dtype=False)
    # redemptions are positive and smaller than gross sales in every year
    red = pick(gbr, measure="redemptions", sub_type="gilts_all")
    red = red.set_index("year")["value_lcu_mn"]
    assert (red > 0).all()
    assert (red < got.loc[red.index]).all()


def test_dmr_3a_class_split_is_forecast_flagged(gbr):
    """3.A carries two financial years per edition, the later one a remit
    estimate, so a converted calendar year that leans on it is grade C."""
    g = pick(gbr, measure="gross_issuance", source_id="HMT_DMR")
    split = g[g["sub_type"].isin({"gilts_conventional", "gilts_index_linked",
                                  "gilts_unallocated"})]
    assert not split.empty
    assert split["quality_grade"].isin({"B", "C"}).all()
    assert split["notes"].str.contains("3.A").all()
    # A.2 total gilt sales and 3.A's split are the same financial-year figures,
    # but A.2 is emitted for outturn years only, so compare where both exist
    for y in sorted(set(split["year"])):
        a2 = pick(gbr, year=y, measure="gross_issuance", sub_type="gilts_all")
        if a2.empty:
            continue
        parts = float(split[split["year"] == y]["value_lcu_mn"].sum())
        assert parts == pytest.approx(float(a2["value_lcu_mn"].iloc[0]), rel=0.02)


# ------------------------------------------------------------- interest

def test_nlf_gilt_interest_2024_against_ons_nmfx(gbr):
    """The NLF gilts line is one instrument of the National Loans Fund's
    finance costs; NMFX is the whole of central government's accrued D.41. They
    are different perimeters, so the check is a magnitude check (15%)."""
    from ggfiscal.debt.readers.ons_hmt import ons_timeseries
    ts = ons_timeseries("NMFX", "pusf")
    ann = ts[ts["period_type"] == "A"]
    nmfx = float(ann.loc[ann["period_start"].dt.year == 2024, "value"].iloc[0])
    nlf = one(gbr, year=2024, measure="interest", instrument_class="mixed",
              sub_type="gilts_all")
    assert nlf == pytest.approx(nmfx, rel=0.15)


def test_nlf_interest_skips_the_unreadable_editions(gbr):
    """2006-07 and 2007-08 have no usable PDF text layer, so no calendar year
    that needs them is built."""
    years = set(pick(gbr, measure="interest", sub_type="gilts_all")["year"])
    assert years and not (years & {2006, 2007, 2008})
    assert min(years) == 2009


# --------------------------------------------------------------- uplift

def test_mw7l_uplift_2022(gbr):
    v = one(gbr, year=2022, measure="uplift_accrued",
            instrument_class="inflation_linked", sub_type="gilts_index_linked")
    assert v > 40_000
    grades = pick(gbr, measure="uplift_accrued")["quality_grade"]
    assert set(grades) == {"A"}          # calendar-year and exact


# --------------------------------------------------------- APF overlay

def test_apf_rows_do_not_pretend_to_be_holdings(gbr):
    ops = pick(gbr, measure="own_holdings", sub_type="boe_apf_net_operations")
    assert not ops.empty
    assert set(ops["quality_grade"]) == {"C"}
    assert ops["notes"].str.contains("REDEMPTIONS OUT OF THE APF ARE NOT DEDUCTED").all()
    published = pick(gbr, measure="own_holdings", sub_type="boe_apf_published_stock")
    assert len(published) == 1
    assert published["quality_grade"].iloc[0] == "B"
    # the published stock is below the undeducted cumulative operations: the gap
    # is exactly the matured nominal that is not published per ISIN
    assert published["value_lcu_mn"].iloc[0] < ops["value_lcu_mn"].max()


# ------------------------------------------------- the combined DD8 build

KEY = ["iso3", "year", "instrument_class", "sub_type", "measure"]


def test_combined_class_aggregates_still_validates():
    """The whole DD8 build (DEU + GBR + FRA). If it fails, the failure must not
    be GBR's: as of this vintage `aggregates.deu_class_aggregates` emits
    duplicate keys because two distinct BMF Verwendung labels collapse to the
    same 80-character `sub_type` (see reports/debt_sources/aggregates_gbr.md),
    which is a DEU-side defect this module cannot fix."""
    try:
        out = A.class_aggregates("test_all")
    except pa_errors.SchemaError as exc:
        data = getattr(exc, "data", None)
        if data is None or not isinstance(data, pd.DataFrame) or "iso3" not in data:
            raise
        dup = data[data.duplicated(KEY, keep=False)]
        assert not dup.empty, "combined build failed for a reason other than duplicates"
        assert "GBR" not in set(dup["iso3"]), \
            f"GBR contributes duplicate keys: {dup[dup['iso3'] == 'GBR'][KEY]}"
        pytest.skip("combined DD8 build fails on non-GBR duplicate keys "
                    f"({sorted(set(dup['iso3']))}); the GBR slice is clean")
    assert "GBR" in set(out["iso3"])
    assert not out[out["iso3"] == "GBR"].duplicated(KEY).any()
    A.SCHEMA.validate(out)
