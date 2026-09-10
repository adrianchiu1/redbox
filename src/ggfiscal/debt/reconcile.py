"""DEBT_KICKOFF.md §8, DD4/DD5: assemble a reconciliation chain.

A chain for one (iso3, year) is a sequence of steps. The first step
(`register`) carries computed items (sums over the register by instrument
class). Each later step carries official or declared bridge items and an
official total; the step's `carried` value is the previous step's official
total (or, for the first bridge step, the register sum), and

    residual = official_total − carried − Σ bridge items

is published as its own item (`item_type = residual`), never allocated
(D16). Where a step has no official total for the year the residual is
NaN and the chain continues from the previous carried value, so downstream
steps still reconcile against their own totals.

`assemble` is pure: it takes ChainItems and returns §5.7/5.8 rows without
provenance columns; the caller adds run_id / source_id / grade.
"""

from __future__ import annotations

import dataclasses
import math

import pandas as pd

OFFICIAL_TOTAL = "official_total"
RESIDUAL = "residual"
CARRIED = "carried_from_previous_step"


@dataclasses.dataclass(frozen=True)
class ChainItem:
    step: str
    item: str
    value: float | None
    item_type: str            # computed | official | declared
    source_id: str | None = None
    basis: str | None = None


def assemble(iso3: str, year: int, steps: list[str], items: list[ChainItem]) -> pd.DataFrame:
    if not steps or steps[0] != "register":
        raise ValueError("a chain starts with the 'register' step")
    by_step: dict[str, list[ChainItem]] = {s: [] for s in steps}
    for it in items:
        if it.step not in by_step:
            raise ValueError(f"item {it.item} names unknown step {it.step}; steps are {steps}")
        by_step[it.step].append(it)

    rows: list[dict] = []
    carried: float | None = None
    for i, step in enumerate(steps):
        its = by_step[step]
        if step == "register":
            vals = [it.value for it in its if it.item != OFFICIAL_TOTAL]
            # no register data at all (e.g. FRA while AFT is blocked): the
            # register total is unknown, not zero — carried stays None and
            # the first residual is null (never a fabricated gap)
            total = _sum(vals) if any(v is not None and not _isnan(v) for v in vals) else None
            for it in its:
                rows.append(_row(iso3, year, step, it))
            rows.append(_row(iso3, year, step, ChainItem(step, OFFICIAL_TOTAL, total, "computed",
                                                        None, _basis(its))))
            carried = total
            continue
        official = next((it for it in its if it.item == OFFICIAL_TOTAL), None)
        bridge = [it for it in its if it.item != OFFICIAL_TOTAL]
        rows.append(_row(iso3, year, step, ChainItem(step, CARRIED, carried, "computed", None, None)))
        for it in bridge:
            rows.append(_row(iso3, year, step, it))
        if official is None or official.value is None or _isnan(official.value):
            rows.append(_row(iso3, year, step, ChainItem(step, OFFICIAL_TOTAL, None, "official",
                                                        official.source_id if official else None,
                                                        official.basis if official else None)))
            rows.append(_row(iso3, year, step, ChainItem(step, RESIDUAL, None, "residual")))
            # nothing official to carry: keep carrying the last known level
            # plus declared bridges — unless nothing is known yet at all
            carried = None if carried is None else _sum([carried] + [it.value for it in bridge])
        else:
            rows.append(_row(iso3, year, step, official))
            if carried is None:
                resid = None          # nothing to reconcile against yet
            else:
                resid = official.value - _sum([carried] + [it.value for it in bridge])
            rows.append(_row(iso3, year, step, ChainItem(step, RESIDUAL, resid, "residual",
                                                        None, official.basis)))
            carried = official.value
    return pd.DataFrame(rows, columns=["iso3", "year", "step", "item", "value_lcu_mn",
                                       "item_type", "item_source_id", "basis"])


def check_additivity(chain: pd.DataFrame, tol: float = 1e-6) -> list[str]:
    """V32: per step, official_total − carried − Σ bridge − residual == 0."""
    problems = []
    for (iso3, year, step), g in chain.groupby(["iso3", "year", "step"], sort=False):
        if step == "register":
            vals = g[g["item"] != OFFICIAL_TOTAL]["value_lcu_mn"]
            tot = g[g["item"] == OFFICIAL_TOTAL]["value_lcu_mn"]
            if len(tot) != 1 or abs(_sum(list(vals)) - float(tot.iloc[0])) > tol:
                problems.append(f"{iso3} {year} {step}: register sum != official_total")
            continue
        d = g.set_index("item")["value_lcu_mn"]
        if OFFICIAL_TOTAL not in d or RESIDUAL not in d or CARRIED not in d:
            problems.append(f"{iso3} {year} {step}: incomplete step")
            continue
        if _isnan(d[OFFICIAL_TOTAL]) or _isnan(d[CARRIED]):
            if not _isnan(d[RESIDUAL]):
                problems.append(f"{iso3} {year} {step}: residual without official total or carried value")
            continue
        bridge = d.drop([OFFICIAL_TOTAL, RESIDUAL, CARRIED])
        lhs = float(d[OFFICIAL_TOTAL]) - _sum([d[CARRIED]] + list(bridge)) - float(d[RESIDUAL])
        if abs(lhs) > tol:
            problems.append(f"{iso3} {year} {step}: additivity off by {lhs}")
    return problems


def _row(iso3, year, step, it: ChainItem) -> dict:
    return {"iso3": iso3, "year": year, "step": step, "item": it.item,
            "value_lcu_mn": it.value, "item_type": it.item_type,
            "item_source_id": it.source_id, "basis": it.basis}


def _sum(vals) -> float:
    return float(sum(v for v in vals if v is not None and not _isnan(v)))


def _isnan(v) -> bool:
    try:
        return v is None or math.isnan(float(v))
    except (TypeError, ValueError):
        return True


def _basis(items: list[ChainItem]) -> str | None:
    bases = {it.basis for it in items if it.basis}
    return bases.pop() if len(bases) == 1 else None
