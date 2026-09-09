"""FRA class-level aggregate layer (`ggfiscal.debt.aggregates_fra`, DD8):
schema, the INSEE/AFT identities, the INSEE-vs-Eurostat perimeter gaps and
the Δstock definition of `net_issuance`. Skipped when the snapshot store is
empty, following tests/debt/test_eurostat_insee_oecd.py."""

from __future__ import annotations

import pandas as pd
import pytest

from ggfiscal.standardise.readers import latest_snapshots

pytestmark = pytest.mark.skipif(not latest_snapshots(),
                                reason="no snapshots harvested in this environment")

RUN = "test-fra"


@pytest.fixture(scope="module")
def fra() -> pd.DataFrame:
    from ggfiscal.debt.aggregates_fra import class_aggregates

    return class_aggregates(RUN)


def _stock(df: pd.DataFrame, sub_type: str) -> pd.Series:
    s = df[(df["sub_type"] == sub_type) & (df["measure"] == "stock_year_end")]
    return s.set_index("year")["value_lcu_mn"].sort_index()


# ---------------------------------------------------------------- shape

def test_schema_validates_and_keys_are_unique(fra):
    from ggfiscal.debt.aggregates import COLUMNS, SCHEMA

    assert list(fra.columns) == COLUMNS
    assert not fra.empty
    assert set(fra["iso3"]) == {"FRA"}
    SCHEMA.validate(fra)
    key = ["iso3", "year", "instrument_class", "sub_type", "measure"]
    assert not fra.duplicated(key).any()
    assert fra["snapshot_sha256"].notna().all()
    assert set(fra["source_id"]) == {"INSEE_AFT_AGG", "EUROSTAT_GOV10DD"}


def test_combined_class_aggregates_still_validates_and_carries_fra():
    from ggfiscal.debt.aggregates import class_aggregates

    all_rows = class_aggregates(RUN)
    assert "FRA" in set(all_rows["iso3"])
    assert "DEU" in set(all_rows["iso3"])


def test_aft_idbank_titles_are_the_verified_vintage():
    """The mapping idbank -> instrument class is only as good as the BDM
    title; `_aft_december()` raises if any title moved."""
    from ggfiscal.debt.aggregates_fra import AFT_FX, AFT_STOCK, _aft_december
    from ggfiscal.debt.readers.eurostat_insee_oecd import aft_aggregates

    titles = dict(zip(aft_aggregates()["idbank"], aft_aggregates()["label"]))
    for idbank, (_, _, _, title) in {**AFT_STOCK, **AFT_FX}.items():
        assert titles[idbank] == title
    assert not _aft_december().empty


# ---------------------------------------------------------------- INSEE/AFT

def test_insee_total_2024_is_in_the_expected_range(fra):
    total = _stock(fra, "dette_negociable_total")
    assert total.index.min() == 2009
    assert 2_300_000 < total.loc[2024] < 2_900_000
    assert total.loc[2024] == pytest.approx(2_601_637, abs=1)


def test_fixed_plus_inflation_linked_equals_total_every_year(fra):
    """Measured: the AFT taux fixe / indexée split adds to the total
    *exactly* (gap 0.0 at every December 2009-2025), so the 0.5%
    tolerance is met with room to spare."""
    total = _stock(fra, "dette_negociable_total")
    fixed = _stock(fra, "taux_fixe")
    linked = _stock(fra, "oati_oatei")
    gap = (fixed + linked - total).dropna()
    assert len(gap) == len(total)
    assert (gap.abs() / total <= 0.005).all()
    assert (gap == 0.0).all(), gap[gap != 0.0].to_dict()


def test_short_plus_long_equals_total_every_year(fra):
    total = _stock(fra, "dette_negociable_total")
    gap = _stock(fra, "btf") + _stock(fra, "oat_btan_all") - total
    assert (gap == 0.0).all(), gap[gap != 0.0].to_dict()


def test_derived_fixed_bullet_is_taux_fixe_minus_btf(fra):
    derived = _stock(fra, "oat_btan_fixed")
    expected = _stock(fra, "taux_fixe") - _stock(fra, "btf")
    pd.testing.assert_series_equal(derived, expected, check_names=False)
    assert derived.loc[2024] == pytest.approx(2_111_417, abs=1)
    notes = fra[fra["sub_type"] == "oat_btan_fixed"]["notes"].unique()
    assert len(notes) == 1 and "derived" in notes[0]
    assert (fra[fra["sub_type"] == "oat_btan_fixed"]["quality_grade"] == "B").all()
    # the AFT taux-fixe row must itself say that it includes BTF
    taux_fixe_notes = fra[fra["sub_type"] == "taux_fixe"]["notes"].unique()
    assert len(taux_fixe_notes) == 1 and "includes BTF" in taux_fixe_notes[0]


def test_foreign_currency_series_are_zero_and_therefore_not_emitted(fra):
    """001719708-710 (encours en devises) are identically 0.0 at every
    December in the harvested vintage: no `out_of_register` FX rows."""
    from ggfiscal.debt.aggregates_fra import AFT_FX
    from ggfiscal.debt.readers.eurostat_insee_oecd import aft_aggregates

    a = aft_aggregates()
    dec = a[(a["period"].dt.month == 12) & (a["idbank"].isin(AFT_FX))]
    assert not dec.empty
    assert (dec["value_eur_mn"] == 0.0).all()
    assert fra[fra["sub_type"].isin(s for _, s, _, _ in AFT_FX.values())].empty


# ---------------------------------------------------------------- Eurostat

def test_s13111_is_not_published_for_france(fra):
    """The brief's intended perimeter (S13111 budgetary central government)
    is absent from gov_10q_ggdebt for FR; S1311 stands in and the rows say
    so."""
    from ggfiscal.debt.readers.eurostat_insee_oecd import eurostat

    sectors = set(eurostat("gov_10q_ggdebt_FR")["sector"])
    assert sectors == {"S13", "S1311", "S1312", "S1313", "S1314"}
    assert "S13111" not in sectors
    esa = fra[fra["source_id"] == "EUROSTAT_GOV10DD"]
    unsuffixed = esa[~esa["sub_type"].str.endswith("_s13")]
    assert unsuffixed["notes"].str.contains("S13111").all()


def test_eurostat_f31_f32_rows_cover_2000_onward_and_flag_the_register(fra):
    f31 = _stock(fra, "f31_short_term_securities")
    f32 = _stock(fra, "f32_long_term_securities")
    assert f31.index.min() == 2000 and f32.index.min() == 2000
    esa = fra[fra["source_id"] == "EUROSTAT_GOV10DD"]
    in_reg = set(esa[esa["in_register"]]["sub_type"])
    assert in_reg == {"f31_short_term_securities", "f32_long_term_securities"}
    out_reg = set(esa[~esa["in_register"]]["sub_type"])
    assert out_reg == {"f4_loans", "f2_currency_deposits",
                       "f31_short_term_securities_s13", "f32_long_term_securities_s13"}
    # F31 is bills, F32 is `mixed` (fixed + linked + floating bonds together)
    assert set(esa[esa["sub_type"] == "f31_short_term_securities"]["instrument_class"]) == {"bill"}
    assert set(esa[esa["sub_type"] == "f32_long_term_securities"]["instrument_class"]) == {"mixed"}


def test_btf_matches_eurostat_f31_at_2024_year_end(fra):
    """AFT BTF (001711532) vs Eurostat S1311 F31 at 2024-Q4: ratio 1.002,
    i.e. the État's bills are effectively the whole of central-government
    short-term securities."""
    btf = _stock(fra, "btf").loc[2024]
    f31 = _stock(fra, "f31_short_term_securities").loc[2024]
    ratio = f31 / btf
    assert 0.90 < ratio < 1.10, ratio
    assert ratio == pytest.approx(1.002, abs=0.005)


def test_s1311_exceeds_insee_and_s13_exceeds_s1311_at_every_common_year_end(fra):
    """Perimeter ordering INSEE/AFT (État négociable) < S1311 (CG incl.
    ODAC) < S13 (general government), measured on the securities lines."""
    insee = _stock(fra, "dette_negociable_total")
    s1311 = _stock(fra, "f31_short_term_securities") + _stock(fra, "f32_long_term_securities")
    s13 = (_stock(fra, "f31_short_term_securities_s13")
           + _stock(fra, "f32_long_term_securities_s13"))
    common = insee.index.intersection(s1311.index)
    assert len(common) >= 17
    assert (s1311[common] > insee[common]).all()
    assert (s13 > s1311).all()
    pct = ((s1311[common] / insee[common]) - 1) * 100
    assert pct.loc[2024] == pytest.approx(1.697, abs=0.01)
    assert (pct.loc[2012:] < 5.1).all()


# ---------------------------------------------------------------- flows

def test_net_issuance_reproduces_delta_stock_exactly(fra):
    """Every net_issuance row is the year-on-year change of the same
    (instrument_class, sub_type) stock row, recomputed here from the
    stock rows alone."""
    flows = fra[fra["measure"] == "net_issuance"]
    assert set(flows["sub_type"]) == {"btf", "oat_btan_all",
                                      "f31_short_term_securities", "f32_long_term_securities"}
    assert (flows["basis"] == "nominal_change").all()
    assert flows["notes"].str.contains("Δ year-end stock").all()
    assert flows["notes"].str.contains(
        "buy-backs, indexation of principal and FX effects not separated").all()
    for sub_type, g in flows.groupby("sub_type"):
        got = g.set_index("year")["value_lcu_mn"].sort_index()
        expected = _stock(fra, sub_type).diff().dropna()
        pd.testing.assert_series_equal(got, expected, check_names=False)
    assert _stock(fra, "btf").index.min() == 2009
    assert flows[flows["sub_type"] == "btf"]["year"].min() == 2010
    assert flows[flows["sub_type"] == "f31_short_term_securities"]["year"].min() == 2001


def test_no_interest_uplift_or_own_holdings_rows(fra):
    """No reachable French source gives interest, indexation uplift or
    Eurosystem holdings at class level (§14 FRA, §15 Q-D1)."""
    assert set(fra["measure"]) == {"stock_year_end", "net_issuance"}
    assert fra[fra["measure"] == "interest"].empty
    assert fra[fra["measure"] == "uplift_accrued"].empty
    assert fra[fra["measure"] == "own_holdings"].empty


def test_gov_10dd_ggd_s1311_has_no_central_bank_holder_rows():
    """The condition for the `own_holdings` rows: gov_10dd_ggd carries no
    S121 holder for issuing sector S1311 (it does for S13 — reported)."""
    from ggfiscal.debt.readers.eurostat_insee_oecd import debt_by_instrument

    assert "S121" not in set(debt_by_instrument("FRA", "S1311")["sector2"])
    assert "S121" in set(debt_by_instrument("FRA", "S13")["sector2"])
