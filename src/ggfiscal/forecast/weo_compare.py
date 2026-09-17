"""The benchmark balance read against the IMF WEO's own deficit projection.

§4 of the chartbook compares our published totals with the WEO's over the
overlap years and stops at the last outturn, because our ledger does.
`forecast.balance` now carries a benchmark balance to 2031, and the WEO
publishes GGXCNL over exactly that horizon, so the two can finally be put on
one axis. This module does that, and decomposes the difference.

The comparison is clean because the two start from the same place. At the
base year the balance gap is +0.02 pp of GDP for the United Kingdom and
zero to three decimals for France and Germany, so nothing here is a
definitional wedge in disguise.

**Levels by side are a different matter.** The UK's TR and TE are each about
2.6 pp of GDP larger than the WEO's — a stable perimeter difference (sd 0.25
pp over ten years, classified `perimeter` in §8.2) that cancels in the
balance. So the side comparison is made on **changes since the base year**,
where a stable wedge cancels, and the wedge itself is published on every row
rather than left for the reader to discover.

The decomposition closes exactly:

    balance change gap = revenue change gap
                       + expenditure change gap
                       - weo_internal_wedge

where the wedge is the WEO's own Δ((GGR − GGX − GGXCNL)/NGDP). It is zero to
four decimals on the current vintage and is still carried, because reporting
it is cheaper than discovering later that it was absorbed.

Signs follow `forecast.balance`: revenue enters positive and expenditure
negative, so the two sides sum to the change in the balance on both ours and
the WEO's side.

One thing this deliberately does not do is judge. The benchmark knows only
each line's own history; the WEO's projection embeds announced policy. Where
they differ, the difference IS the policy, and the file reports how far apart
they are and whether the WEO sits inside the benchmark's own interval —
never which one is right.
"""

from __future__ import annotations

import pandas as pd

from ggfiscal import config

Z95, Z80 = 1.959964, 1.281552
SUBJECT = {"revenue": "GGR", "expenditure": "GGX"}
SIGN = {"revenue": 1.0, "expenditure": -1.0}
PERIMETER_WINDOW = 10

COLUMNS = [
    "iso3", "country", "weo_vintage", "base_year", "year", "horizon", "kind",
    "side", "ours_pct_gdp", "weo_pct_gdp", "level_gap_pp", "ours_change_pp",
    "weo_change_pp", "change_gap_pp", "se", "lo80", "hi80", "lo95", "hi95",
    "weo_inside_80", "weo_inside_95", "weo_z", "perimeter_gap_pp",
    "perimeter_gap_sd_pp", "perimeter_classification", "notes", "run_id",
]


def _deliverables():
    deliv = config.repo_root() / "deliverables"
    read = lambda n: pd.read_csv(deliv / n, float_precision="round_trip")
    return read("benchmark_balance.csv"), read("weo_levels_bridge.csv")


def _weo_ratios(vintage: str, iso3: str) -> dict[str, pd.Series]:
    """GGR, GGX and GGXCNL as shares of the WEO's own NGDP."""
    from ggfiscal.standardise.readers import weo_series

    ngdp = weo_series(vintage, iso3, "NGDP").dropna()
    out = {}
    for subject in ("GGR", "GGX", "GGXCNL"):
        s = weo_series(vintage, iso3, subject).dropna()
        years = s.index.intersection(ngdp.index)
        out[subject] = 100.0 * s[years] / ngdp[years]
    return out


def _perimeter(bridge: pd.DataFrame, iso3: str, vintage: str, base: int):
    """The base-year gap by side, and how stable it has been. A stable wedge
    cancels in a change; an unstable one is the thing to worry about."""
    h = (bridge.query("block == 'history' and iso3 == @iso3 and "
                      "weo_vintage == @vintage")
         .dropna(subset=["tr_ours_mn", "gdp_ours_mn"]).sort_values("year"))
    pairs = {"balance": ("nlb_ours_mn", "nlb_weo_mn"),
             "revenue": ("tr_ours_mn", "tr_weo_mn"),
             "expenditure": ("te_ours_mn", "te_weo_mn")}
    out = {}
    for side, (a, b) in pairs.items():
        gap = 100.0 * (h[a] - h[b]) / h.gdp_ours_mn
        at_base = h[h.year == base]
        out[side] = (
            float(100.0 * (at_base[a].iloc[0] - at_base[b].iloc[0])
                  / at_base.gdp_ours_mn.iloc[0]) if len(at_base) else float("nan"),
            float(gap.tail(PERIMETER_WINDOW).std(ddof=1)))
    kinds = sorted(h.gap_classification.dropna().unique())
    return out, (", ".join(kinds) if kinds else "")


def compute(run_id: str = "", vintage: str = "") -> tuple[pd.DataFrame, list[str]]:
    balance, bridge = _deliverables()
    vintage = vintage or sorted(bridge.weo_vintage.dropna().unique())[-1]
    rows, notes = [], []

    for iso3 in sorted(balance.iso3.unique()):
        ours_bal = balance.query("iso3 == @iso3 and kind == 'balance'").sort_values("year")
        country = ours_bal.country.iloc[0]
        base = int(ours_bal.base_year.iloc[0])
        weo = _weo_ratios(vintage, iso3)
        if any(base not in s.index for s in weo.values()):   # pragma: no cover
            notes.append(f"{iso3}: WEO {vintage} has no {base}; skipped")
            continue
        perimeter, classification = _perimeter(bridge, iso3, vintage, base)
        base_gap = perimeter["balance"][0]
        notes.append(
            f"{iso3}: base {base} — ours {float(ours_bal.anchor_pct_gdp.iloc[0]):+.2f}, "
            f"WEO {float(weo['GGXCNL'][base]):+.2f}, perimeter gap "
            f"{base_gap:+.3f} pp (by side: revenue "
            f"{perimeter['revenue'][0]:+.2f}, expenditure "
            f"{perimeter['expenditure'][0]:+.2f}; {classification})")

        for row in ours_bal.itertuples():
            year = int(row.year)
            if year not in weo["GGXCNL"].index:
                continue
            shared = dict(iso3=iso3, country=country, weo_vintage=vintage,
                          base_year=base, year=year, horizon=year - base,
                          perimeter_classification=classification,
                          run_id=run_id)
            weo_bal = float(weo["GGXCNL"][year])
            sd = float(row.se)
            rows.append({
                **shared, "kind": "balance", "side": "balance",
                "ours_pct_gdp": row.pct_gdp, "weo_pct_gdp": weo_bal,
                "level_gap_pp": row.pct_gdp - weo_bal,
                "ours_change_pp": row.contribution_pp,
                "weo_change_pp": weo_bal - float(weo["GGXCNL"][base]),
                "change_gap_pp": (row.contribution_pp
                                  - (weo_bal - float(weo["GGXCNL"][base]))),
                "se": sd, "lo80": row.lo80, "hi80": row.hi80,
                "lo95": row.lo95, "hi95": row.hi95,
                "weo_inside_80": bool(row.lo80 <= weo_bal <= row.hi80),
                "weo_inside_95": bool(row.lo95 <= weo_bal <= row.hi95),
                "weo_z": (weo_bal - row.pct_gdp) / sd if sd else float("nan"),
                "perimeter_gap_pp": perimeter["balance"][0],
                "perimeter_gap_sd_pp": perimeter["balance"][1],
                "notes": "benchmark against the WEO's own GGXCNL/NGDP; "
                         "weo_z is how many of the benchmark's own standard "
                         "errors the WEO sits away from it",
            })

            for side in ("revenue", "expenditure"):
                sign, subject = SIGN[side], SUBJECT[side]
                ours = balance.query("iso3 == @iso3 and year == @year and "
                                     "kind == @side + '_total'").iloc[0]
                weo_level = float(weo[subject][year])
                weo_change = sign * (weo_level - float(weo[subject][base]))
                rows.append({
                    **shared, "kind": side, "side": side,
                    "ours_pct_gdp": ours.pct_gdp, "weo_pct_gdp": weo_level,
                    "level_gap_pp": ours.pct_gdp - weo_level,
                    "ours_change_pp": ours.contribution_pp,
                    "weo_change_pp": weo_change,
                    "change_gap_pp": ours.contribution_pp - weo_change,
                    "perimeter_gap_pp": perimeter[side][0],
                    "perimeter_gap_sd_pp": perimeter[side][1],
                    "notes": f"changes are signed so revenue and expenditure "
                             f"sum to the balance; the LEVEL gap carries the "
                             f"perimeter difference and the change does not",
                })

            # the WEO's own GGR - GGX does not have to equal its GGXCNL; it is
            # reported so the three change gaps close on the balance exactly
            wedge = ((float(weo["GGR"][year]) - float(weo["GGX"][year])
                      - float(weo["GGXCNL"][year]))
                     - (float(weo["GGR"][base]) - float(weo["GGX"][base])
                        - float(weo["GGXCNL"][base])))
            rows.append({
                **shared, "kind": "weo_internal_wedge", "side": "memo",
                "weo_change_pp": wedge, "change_gap_pp": -wedge,
                "notes": "the WEO's own change in (GGR - GGX - GGXCNL)/NGDP "
                         "since the base year. Enters the balance gap with a "
                         "minus sign; reported, never absorbed",
            })

    frame = pd.DataFrame(rows).reindex(columns=COLUMNS)
    frame = frame.sort_values(["iso3", "year", "kind"], kind="stable",
                              na_position="first").reset_index(drop=True)
    return frame, notes


def write(run_id: str = "", vintage: str = ""):
    frame, notes = compute(run_id, vintage)
    dest = config.repo_root() / "deliverables" / "benchmark_vs_weo.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(dest, index=False)
    return dest, notes
