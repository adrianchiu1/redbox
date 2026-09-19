"""Family 'boe' — pulls() coverage and reader sanity checks against the
harvested snapshot store (DEBT_KICKOFF.md §13). Skipped when the store is
empty, following the tests/deliverables and tests/stage_N pattern."""

from __future__ import annotations

import pytest

from ggfiscal.standardise.readers import latest_snapshots

pytestmark = pytest.mark.skipif(not latest_snapshots(),
                                reason="no snapshots harvested in this environment")


def test_pulls_list_all_parts_with_correct_source_ids():
    from ggfiscal.debt.families import boe

    pulls = boe.pulls()
    by_source = {}
    for p in pulls:
        by_source.setdefault(p.source_id, set()).add(p.part)

    assert by_source["BOE_APF"] == {
        "gilt_purchases", "gilt_sales", "maturity_profile",
        "fs_long_dated_purchases", "fs_index_linked_purchases", "fs_gilt_sales",
    }
    assert by_source["BOE_YIELD_CURVES"] == {
        "nominal_daily", "real_daily", "inflation_daily", "ois_daily",
        "nominal_monthend", "real_monthend", "inflation_monthend", "ois_monthend",
        "latest",
    }
    assert by_source["BOE_IADB"] == {"IUDSOIA", "IUDBEDR", "baserate_xls"}
    # every part has a distinct, well-formed https URL
    urls = [p.url for p in pulls]
    assert len(urls) == len(pulls)
    assert all(u.startswith("https://www.bankofengland.co.uk/") for u in urls)


def test_apf_operations_purchases_and_sales():
    from ggfiscal.debt.readers import boe

    df = boe.apf_operations()
    expected_cols = ["operation_date", "settlement_date", "isin", "bond_label",
                     "direction", "nominal_gbp_mn", "proceeds_gbp_mn",
                     "wa_yield_pct", "wa_price", "programme", "part"]
    assert list(df.columns) == expected_cols
    assert set(df["direction"].unique()) <= {1, -1}
    assert set(df["programme"].unique()) <= {
        "apf", "fs_long_dated", "fs_index_linked", "fs_sales"}

    import pandas as pd

    purchases = df[df["direction"] == 1]
    assert len(purchases) > 7000
    assert purchases["operation_date"].min() == pd.Timestamp("2009-03-11")
    assert purchases["isin"].str.match(r"^GB00").all()

    sales = df[df["direction"] == -1]
    assert len(sales) > 0
    assert sales["operation_date"].min() == pd.Timestamp("2022-11-01")


def test_apf_maturity_profile():
    from ggfiscal.debt.readers import boe

    df = boe.apf_maturity_profile()
    assert list(df.columns) == ["gilt_name", "maturity_date",
                                "total_nominal_gbp_bn", "remaining_stock_gbp_bn"]
    assert len(df) > 0
    assert df["maturity_date"].notna().all()
    assert (df["total_nominal_gbp_bn"] > 0).all()


def test_yield_curve_nominal_monthend_spans_history():
    import pandas as pd

    from ggfiscal.debt.readers import boe

    df = boe.yield_curve("nominal", "monthend")
    assert list(df.columns) == ["date", "maturity_years", "value_pct", "kind"]
    assert (df["kind"] == "nominal").all()
    assert df["date"].min() <= pd.Timestamp("1979-12-31")
    assert df["maturity_years"].max() >= 25


def test_yield_curve_rejects_unknown_kind():
    from ggfiscal.debt.readers import boe

    with pytest.raises(ValueError):
        boe.yield_curve("nope")


def test_iadb_sonia_starts_1997_01_02():
    import pandas as pd

    from ggfiscal.debt.readers import boe

    s = boe.iadb_series("IUDSOIA")
    assert s.index.min() == pd.Timestamp("1997-01-02")
    assert s.dtype.kind == "f"
    assert s.index.is_monotonic_increasing


def test_iadb_bank_rate_starts_1975_01_02():
    import pandas as pd

    from ggfiscal.debt.readers import boe

    s = boe.iadb_series("IUDBEDR")
    assert s.index.min() == pd.Timestamp("1975-01-02")


def test_bank_rate_history_covers_1694():
    import pandas as pd

    from ggfiscal.debt.readers import boe

    df = boe.bank_rate_history()
    assert list(df.columns) == ["date_changed", "rate_pct"]
    assert df["date_changed"].min() == pd.Timestamp("1694-10-01")
    assert df["date_changed"].is_monotonic_increasing
    assert df["rate_pct"].notna().all()
