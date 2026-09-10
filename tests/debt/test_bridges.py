"""Step-B (and GBR step-C) official bridge items — DEBT_KICKOFF.md §8,
DD4/DD5. Every test reads the D8 snapshots through the family readers and
skips without them (`python3 -m ggfiscal.cli debt fetch`)."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from ggfiscal.debt import bridges
from ggfiscal.standardise.readers import latest_snapshots

pytestmark = pytest.mark.skipif(not latest_snapshots(),
                                reason="no snapshots harvested in this environment")

GBR_YEARS = list(range(2010, 2025))
TOL_GBP_MN = 100.0


def _have(source_id: str, part: str) -> bool:
    return (source_id, part) in latest_snapshots()


needs_ons = pytest.mark.skipif(
    not (_have("ONS_PSF_APPENDIX_A", "appendix_a") and _have("ONS_PSF_APPENDIX_S", "appendix_s")),
    reason="no ONS PSF Appendix A / Appendix S snapshot")

needs_eurostat = pytest.mark.skipif(
    not _have("EUROSTAT_GOV10DD", "gov_10dd_edpt3_DE"),
    reason="no Eurostat gov_10dd_edpt3 snapshot")


def _step_sum(items, step: str) -> float:
    return float(sum(i.value for i in items if i.step == step))


def _package(fn, iso3: str):
    """package_gf01_7 / package_nlb, or None when the canonical build is absent."""
    try:
        return fn(iso3)
    except Exception:
        return None


# ------------------------------------------------------------ GBR step B

@needs_ons
def test_gbr_financing_step_b_identity_closes():
    """M98R (carried) + Σ items == central government net borrowing (-NMFJ),
    within £100 mn, for every calendar year 2010-2024."""
    from ggfiscal.debt.readers import ons_hmt as O

    fin = O.cgncr_financing()
    m = fin[(fin["cdid"] == "M98R") & (fin["period_type"] == "M")]
    carried = m.groupby(m["period_start"].dt.year)["value"].sum()
    months = m.groupby(m["period_start"].dt.year)["value"].size()

    ci = O.cg_interest()
    nb = ci[(ci["cdid"] == "-NMFJ") & (ci["period_type"] == "CY")]
    nb = nb.set_index(nb["period_start"].dt.year)["value"]

    checked = 0
    for year in GBR_YEARS:
        if months.get(year, 0) != 12 or year not in nb.index:
            continue
        items = bridges.bridge_items("GBR", "financing", year)
        got = float(carried[year]) + _step_sum(items, "B_s1311_b9")
        assert abs(got - float(nb[year])) < TOL_GBP_MN, (
            f"{year}: carried + Σ bridge = {got:,.0f} vs net borrowing {nb[year]:,.0f}")
        checked += 1
    assert checked >= 14


@needs_ons
def test_gbr_financing_step_b_item_set_is_the_documented_nine():
    items = [i.item for i in bridges.bridge_items("GBR", "financing", 2024)
             if i.step == "B_s1311_b9"]
    assert items == [
        "nram_and_bb_net_cash_requirement",
        "network_rail_net_cash_requirement",
        "less_payments_to_local_government",
        "less_payments_to_public_corporations",
        "less_net_lending_to_private_sector_and_rest_of_world",
        "less_net_acquisition_of_company_securities",
        "less_adjustment_for_interest_on_gilts",
        "less_accounts_receivable_payable",
        "less_other_financial_transactions",
    ]


@needs_ons
def test_gbr_interest_step_b_has_no_official_bridge():
    """NLF accrued finance costs -> ONS NMFX: nothing is published, so the
    whole wedge must stay in the residual."""
    items = bridges.bridge_items("GBR", "interest", 2024)
    assert [i for i in items if i.step == "B_s1311_d41"] == []


# ------------------------------------------------------------ GBR step C

@needs_ons
@pytest.mark.parametrize("chain,step,fn_name", [
    ("interest", "C_s13_gf01_7", "package_gf01_7"),
    ("financing", "C_s13_nlb", "package_nlb"),
])
def test_gbr_step_c_items_shrink_the_residual(chain, step, fn_name):
    from ggfiscal.debt import intermediates as I
    from ggfiscal.debt.readers import ons_hmt as O

    official = _package(getattr(I, fn_name), "GBR")
    if official is None:
        pytest.skip("canonical package legs not built in this environment")

    if chain == "interest":
        ts = O.ons_timeseries("NMFX", "pusf")
        ann = ts[ts["period_type"] == "A"]
        carried = ann.set_index(ann["period_start"].dt.year)["value"]
        total = official
    else:
        ci = O.cg_interest()
        nb = ci[(ci["cdid"] == "-NMFJ") & (ci["period_type"] == "CY")]
        carried = nb.set_index(nb["period_start"].dt.year)["value"]
        total = -official          # chain runs in net-borrowing sign

    checked = 0
    for year in range(2020, 2025):
        if year not in carried.index or year not in total.index:
            continue
        items = bridges.bridge_items("GBR", chain, year)
        assert [i.item for i in items if i.step == step], f"{year}: no step-C item"
        before = abs(float(total[year]) - float(carried[year]))
        after = abs(float(total[year]) - float(carried[year]) - _step_sum(items, step))
        assert after < before, f"{year}: |residual| {before:,.0f} -> {after:,.0f}"
        checked += 1
    assert checked == 5


# --------------------------------------------------------- FRA / DEU step B

@needs_eurostat
@pytest.mark.parametrize("iso3", ["FRA", "DEU"])
def test_eurostat_financing_items_exist_for_the_latest_three_years(iso3):
    wide, _, _ = bridges._edpt3(iso3)
    if wide.empty:
        pytest.skip(f"no gov_10dd_edpt3 rows for {iso3}")
    years = sorted(int(y) for y in wide.index)[-3:]
    assert len(years) == 3
    for year in years:
        items = [i for i in bridges.bridge_items(iso3, "financing", year)
                 if i.step == "B_s1311_b9"]
        assert len(items) >= 10, f"{iso3} {year}: only {len(items)} items"
        assert {i.item for i in items} >= {
            "net_issuance_other_liabilities_loans",
            "less_net_acquisition_currency_and_deposits",
            "less_sfa_adjustment_issuance_above_below_par",
            "less_sfa_adjustment_interest_accrued_less_paid",
            "less_statistical_discrepancy",
        }
        total = sum(i.value for i in items)
        assert math.isfinite(total)


@needs_eurostat
def test_deu_2023_sfa_identity_and_item_signs():
    """The published identity ΔDebt = −B.9 + SFA, recomputed from the raw
    gov_10dd_edpt3 pull for DE/S1311 2023, and the signs the items carry:

        GD_CH  = B9_T3 + F_ASS + ORADJ + YA3
        ΔF3    + Σ(emitted items) = B9_T3          (net-borrowing sign)
    """
    from ggfiscal.debt.readers import eurostat_insee_oecd as E

    df = E.eurostat("gov_10dd_edpt3_DE")
    df = df[(df["sector"] == "S1311") & (df["unit"] == "MIO_NAC")
            & (df["time_period"] == "2023")]
    v = df.set_index("na_item")["value"]

    assert v["GD_CH"] == pytest.approx(v["B9_T3"] + v["F_ASS"] + v["ORADJ"] + v["YA3"], abs=0.5)
    assert v["F_ASS"] == pytest.approx(sum(v[c] for c in bridges.EDPT3_ASSETS), abs=0.5)
    assert v["ORADJ"] == pytest.approx(sum(v[c] for c in bridges.EDPT3_ADJUSTMENTS), abs=0.5)

    stock = bridges._debt_stock("DEU", "S1311")
    d_f3 = float(stock.at[2023, "F3"] - stock.at[2022, "F3"])
    items = [i for i in bridges.bridge_items("DEU", "financing", 2023)
             if i.step == "B_s1311_b9"]
    assert d_f3 + sum(i.value for i in items) == pytest.approx(float(v["B9_T3"]), abs=1.0)

    # every emitted asset/adjustment item is the published cell, sign reversed
    by_item = {i.item: i.value for i in items}
    assert by_item["less_net_acquisition_currency_and_deposits"] == pytest.approx(-v["F2_ASS"])
    assert by_item["less_sfa_adjustment_issuance_above_below_par"] == pytest.approx(-v["ORINV"])
    assert by_item["less_statistical_discrepancy"] == pytest.approx(-v["YA3"])


@needs_eurostat
def test_deu_interest_step_b_is_the_accrual_adjustment_sign_reversed():
    from ggfiscal.debt.readers import eurostat_insee_oecd as E

    df = E.eurostat("gov_10dd_edpt3_DE")
    df = df[(df["sector"] == "S1311") & (df["unit"] == "MIO_NAC")
            & (df["na_item"] == "ORD41A_ADJ") & (df["time_period"] == "2023")]
    published = float(df["value"].iloc[0])

    items = bridges.bridge_items("DEU", "interest", 2023)
    assert [i.item for i in items] == ["d41_accrued_less_paid_adjustment"]
    assert items[0].value == pytest.approx(-published)


def test_fra_interest_has_no_items():
    """Step A is blocked for FRA (OQ-8): no carried value, no bridge."""
    assert bridges.bridge_items("FRA", "interest", 2023) == []


# --------------------------------------------------------------- shape

@pytest.mark.parametrize("iso3,chain", [(i, c) for i in ("GBR", "FRA", "DEU")
                                        for c in ("interest", "financing")])
def test_every_item_is_official_and_traceable(iso3, chain):
    for year in (2015, 2020, 2023):
        for it in bridges.bridge_items(iso3, chain, year):
            assert it.item_type == "official"
            assert it.source_id
            assert it.basis and "sign" in it.basis
            assert it.step in ("B_s1311_d41", "B_s1311_b9",
                               "C_s13_gf01_7", "C_s13_nlb")
            assert it.value is not None and math.isfinite(it.value)


def test_unknown_chain_raises():
    with pytest.raises(ValueError):
        bridges.bridge_items("GBR", "maturity", 2020)
