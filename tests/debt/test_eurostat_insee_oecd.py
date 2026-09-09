"""Family 'eurostat_insee_oecd' — pulls() coverage and reader sanity checks
against the harvested snapshot store (DEBT_KICKOFF.md §13, §6.3). Skipped
when the store is empty, following the tests/deliverables and
tests/stage_N pattern (see tests/debt/test_boe.py)."""

from __future__ import annotations

import pandas as pd
import pytest

from ggfiscal.standardise.readers import latest_snapshots

pytestmark = pytest.mark.skipif(not latest_snapshots(),
                                reason="no snapshots harvested in this environment")


def test_pulls_list_all_parts_with_correct_source_ids():
    from ggfiscal.debt.families import eurostat_insee_oecd as fam

    pulls = fam.pulls()
    assert len(pulls) < 60

    by_source: dict[str, set[str]] = {}
    for p in pulls:
        by_source.setdefault(p.source_id, set()).add(p.part)

    assert by_source["EUROSTAT_GOV10A_MAIN_S1311"] == {
        "gov_10a_main_D41PAY_FR", "gov_10a_main_D41PAY_DE",
        "gov_10a_main_B9_FR", "gov_10a_main_B9_DE",
    }
    assert {"gov_10dd_ggd_S1311_FR", "gov_10dd_ggd_S13_DE",
            "gov_10dd_rmd_FR", "gov_10dd_rmd_DE",
            "gov_10dd_edpt1_FR", "gov_10dd_edpt2_DE", "gov_10dd_edpt3_FR",
            "gov_10dd_dcur_DE", "gov_10q_ggdebt_FR"} <= by_source["EUROSTAT_GOV10DD"]
    assert {"prc_hicp_minr_EA", "prc_hicp_midx_EA",
            "prc_hicp_minr_FR", "prc_hicp_midx_DE"} <= by_source["EUROSTAT_PRC_HICP"]
    assert {"irt_st_m_IRT_M3", "irt_st_m_IRT_M6",
            "irt_lt_mcby_m_FR", "irt_lt_mcby_m_DE", "irt_lt_mcby_m_EA"} <= by_source["EUROSTAT_IRT"]
    assert by_source["INSEE_IPC"] == {"001763852", "011814056", "001764305"}
    assert len(by_source["INSEE_AFT_AGG"]) == 16
    assert by_source["OECD_T7PSD"] == {"T7PSD_GBR", "T7PSD_FRA", "T7PSD_DEU"}
    assert by_source["OECD_FINMARK"] == {
        "FINMARK_IR3TIB_GBR", "FINMARK_IRLT_GBR",
        "FINMARK_IR3TIB_FRA", "FINMARK_IRLT_FRA",
        "FINMARK_IR3TIB_DEU", "FINMARK_IRLT_DEU",
    }

    urls = [p.url for p in pulls]
    assert len(urls) == len(set(zip((p.source_id for p in pulls), (p.part for p in pulls))))
    assert all(u.startswith("https://") for u in urls)


def test_d41pay_fra_s1311():
    from ggfiscal.debt.readers.eurostat_insee_oecd import d41pay

    s = d41pay("FRA", "S1311")
    assert 1995 in s.index
    assert 2024 in s.index
    assert s.loc[2024] == pytest.approx(46851, rel=0.01)


def test_d41pay_deu_s13_2024_above_30bn():
    from ggfiscal.debt.readers.eurostat_insee_oecd import d41pay

    s = d41pay("DEU", "S13")
    assert s.loc[2024] > 30_000


def test_hicp_ex_tobacco_ea_span():
    from ggfiscal.debt.readers.eurostat_insee_oecd import hicp_ex_tobacco

    s = hicp_ex_tobacco("EA", base="I25")
    assert s.index.min() == pd.Timestamp("1999-12-01")
    assert s.index.max() >= pd.Timestamp("2026-06-01")
    assert s.index.is_monotonic_increasing


def test_fr_cpi_ex_tobacco_chained_starts_1990_and_no_large_jumps():
    from ggfiscal.debt.readers.eurostat_insee_oecd import fr_cpi_ex_tobacco_chained

    s = fr_cpi_ex_tobacco_chained()
    assert s.index.min() == pd.Timestamp("1990-01-01")
    assert s.index.is_monotonic_increasing
    mom = s.pct_change().dropna().abs()
    assert mom.max() < 0.05
    # the chain factor is close to 1/1.198 (base 2015 -> base 2025 rebasing)
    assert s.attrs["chain_factor"] == pytest.approx(0.8346, abs=0.001)


def test_debt_by_maturity_deu_s13_has_1995_and_maturity_codes():
    from ggfiscal.debt.readers.eurostat_insee_oecd import debt_by_maturity

    # NOTE: DEU's gov_10dd_rmd publishes only 4 of the 7 standard maturity
    # bands (TOTAL, Y_LE1, Y1-5, Y_GT1 — no Y5-10/Y10-30/Y_GT30; other EU
    # members such as BE do report all 7). Also: sector S1311 in gov_10dd_rmd
    # only starts 2004 for DEU; S13 starts 1995 (see the report). Documented
    # as a data-availability correction to the kickoff's "7 maturity codes"
    # expectation.
    df = debt_by_maturity("DEU", sector="S13")
    assert (df["time_period"] == "1995").any()
    assert set(df["maturity"].unique()) == {"TOTAL", "Y_LE1", "Y1-5", "Y_GT1"}


def test_debt_by_instrument_holders_total_available():
    from ggfiscal.debt.readers.eurostat_insee_oecd import debt_by_instrument

    df = debt_by_instrument("FRA", "S1311")
    assert "S1_S2" in df["sector2"].unique()
    assert (df["na_item"] == "GD").any()


def test_quarterly_debt_fra_s13():
    from ggfiscal.debt.readers.eurostat_insee_oecd import quarterly_debt

    df = quarterly_debt("FRA", "S13")
    assert (df["na_item"] == "GD").any()
    assert df["time_period"].str.match(r"\d{4}-Q[1-4]").all()


def test_sfa_components_deu_has_labelled_items():
    from ggfiscal.debt.readers.eurostat_insee_oecd import sfa_components

    df = sfa_components("DEU")
    assert set(df["table"].unique()) <= {"edpt2", "edpt3"}
    assert (df["na_item_label"] != "").all()


def test_insee_series_ipc_base2015():
    from ggfiscal.debt.readers.eurostat_insee_oecd import insee_series

    s = insee_series("001763852")
    assert s.index.min() == pd.Timestamp("1990-01-01")
    assert s.index.max() == pd.Timestamp("2025-12-01")
    assert s.dtype.kind == "f"


def test_aft_aggregates_long_frame():
    from ggfiscal.debt.readers.eurostat_insee_oecd import aft_aggregates

    df = aft_aggregates()
    assert list(df.columns) == ["idbank", "label", "period", "value_eur_mn"]
    assert df["idbank"].nunique() == 16
    assert (df["label"] != "").all()


def test_oecd_psd_gbr_s1311_from_1995():
    from ggfiscal.debt.readers.eurostat_insee_oecd import oecd_psd

    df = oecd_psd("GBR")
    s1311 = df[df["sector"] == "S1311"]
    assert len(s1311) > 0
    assert s1311["time_period"].min() == "1995-Q1"


def test_oecd_rate_deu_ir3tib_starts_1960():
    from ggfiscal.debt.readers.eurostat_insee_oecd import oecd_rate

    s = oecd_rate("DEU", "IR3TIB")
    assert s.index.min() == pd.Timestamp("1960-01-01")
    assert s.dtype.kind == "f"
