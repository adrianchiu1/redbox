"""D-S17-024: ensemble admission by calibration ratio — a member whose
horizon standard error exceeds five times the series' own h-year change
volatility stays published but leaves the combination (never below two)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ggfiscal.forecast import statistical as S

Y = pd.Series(np.r_[np.linspace(1.0, 2.0, 20)] + 0.1 * np.sin(np.arange(20)),
              index=range(2005, 2025))
H = 3


def _sd_changes():
    v = Y.to_numpy()
    return float(np.std(v[H:] - v[:-H], ddof=1))


def test_calibration_ratio():
    assert S.calibration_ratio(Y, 2 * _sd_changes(), H) == pytest.approx(2.0)
    assert np.isnan(S.calibration_ratio(Y.iloc[:4], 1.0, H))           # < 3 changes
    assert np.isnan(S.calibration_ratio(pd.Series([1.0] * 10), 1.0, 2))  # never varies


def _fake(se_mult):
    def fit(y, h):
        se = np.linspace(0.1, se_mult * _sd_changes(), h)
        return np.full(h, 2.0), se, f"fake {se_mult}"
    return fit


@pytest.mark.parametrize("mults,excluded", [
    ({"a": 1.0, "b": 0.8, "c": 1.2, "d": 0.9}, []),                 # all calibrated
    ({"a": 1.0, "b": 0.8, "c": 1.2, "d": 75.0}, ["d"]),             # one outlier
    ({"a": 9.0, "b": 0.8, "c": 1.2, "d": 75.0}, ["d", "a"]),        # two, worst first
    ({"a": 9.0, "b": 6.0, "c": 1.2, "d": 75.0}, ["d", "a"]),        # floor: two remain
    ({"a": 9.0, "b": 6.0}, []),                                     # floor: nothing to drop
])
def test_combination_admission(monkeypatch, mults, excluded):
    monkeypatch.setattr(S, "METHODS", {m: _fake(k) for m, k in mults.items()})
    fits, notes = S.forecast_series(Y, H)
    label = fits["combination"][2]
    kept = [m for m in mults if m not in excluded]
    assert label.startswith(f"mean of {len(kept)} ")
    for m in excluded:
        assert f"excluded {m}" in label or f", {m} (" in label
    assert set(fits) == set(mults) | {"combination"}          # members still published
    ses = np.vstack([fits[m][1] for m in kept])
    assert fits["combination"][1][-1] == pytest.approx(np.sqrt((ses ** 2).mean(axis=0))[-1])
    assert bool(excluded) == any("excluded from the combination" in n for n in notes)
