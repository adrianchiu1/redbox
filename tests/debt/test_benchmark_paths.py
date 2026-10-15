"""Gate for the official baselines drawn beside the scenario paths (D-S19-005)."""
import numpy as np

from ggfiscal.report.briefing_fra_scenarios import benchmark_paths


def test_benchmark_file_has_both_sources_and_the_derived_deficit():
    bp = benchmark_paths()
    dsm, weo = "EC_DSM_2025", "IMF_WEO_2026_10"
    assert set(bp[dsm].columns) >= {"debt_pct_gdp", "deficit_pct_gdp", "interest_pct_gdp", "primary_balance_pct_gdp"}
    assert set(bp[weo].columns) >= {"debt_pct_gdp", "deficit_pct_gdp"}
    d = bp[dsm].dropna()
    assert d.index.min() == 2024 and d.index.max() == 2036
    assert np.allclose(d.deficit_pct_gdp, d.interest_pct_gdp - d.primary_balance_pct_gdp)
    w = bp[weo].dropna()
    assert w.index.max() == 2031 and 110 < w.debt_pct_gdp[2025] < 120
    # both baselines rise or stay flat on debt and neither reaches 3% on the deficit before 2031
    assert d.debt_pct_gdp.diff().dropna().min() > 0
    assert (bp[dsm].deficit_pct_gdp.loc[2025:2031] > 3).all() and (w.deficit_pct_gdp.loc[2025:2031] > 3).all()
