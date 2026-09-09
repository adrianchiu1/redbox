"""Build the two reconciliation tables (§5.7, §5.8) from what exists today:
the aggregate class-level layer (DD8) at the register step, the official
intermediates at steps A/B/C, and the bridge items an official source
provides. Everything else is residual, published per step (D16).

Register step, while OQ-8 is open: Σ in-register aggregate rows by
instrument class (item `sum_{class}`, item_type official, grade B/C). When
the per-security register exists these items are replaced by the computed
sums of `debt_interest_by_security` / `debt_flows`, and the aggregate rows
become V31/V39 cross-checks.

Bridge items provided:
  interest  A: out-of-register instrument interest from the same ministry
               source (Schuldscheindarlehen etc.; NS&I and other NLF costs)
            C: D.41 payable of S.1312 + S.1313 + S.1314 (Eurostat, FRA/DEU)
  financing A: out-of-register net financing from the same source
               (NS&I, deposits, loans; Geldmarkt, Schuldschein); DEU own-
               holdings change (Eigenbestandsaufbau) as a declared item
            C: B.9 of S.1312 + S.1313 + S.1314 (Eurostat, FRA/DEU)
"""

from __future__ import annotations

import pandas as pd

from ggfiscal import config
from ggfiscal.debt import model
from ggfiscal.debt.reconcile import ChainItem, assemble

MEASURE = {"interest": "interest", "financing": "net_issuance"}
STEPS = {"interest": model.INTEREST_STEPS, "financing": model.FINANCING_STEPS}
STEP_A = {"interest": "A_cg_cash", "financing": "A_cg_cash_requirement"}
STEP_C = {"interest": "C_s13_gf01_7", "financing": "C_s13_nlb"}


def _subsector_items(iso3: str, chain: str, year: int) -> list[ChainItem]:
    if iso3 not in ("FRA", "DEU"):
        return []
    from ggfiscal.debt.readers import eurostat_insee_oecd as E
    fn = E.d41pay if chain == "interest" else E.b9
    items = []
    for sector, label in (("S1312", "state_government"), ("S1313", "local_government"),
                          ("S1314", "social_security_funds")):
        try:
            s = fn(iso3, sector)
        except Exception:
            continue
        if year in s.index and pd.notna(s[year]):
            items.append(ChainItem(STEP_C[chain], f"{label}_{'d41' if chain == 'interest' else 'b9'}",
                                   float(s[year]), "official", "EUROSTAT_GOV10A_MAIN_S1311", "accrued"))
    return items


def build_chain(chain: str, aggregates: pd.DataFrame, totals: pd.DataFrame,
                run_id: str) -> pd.DataFrame:
    measure = MEASURE[chain]
    agg = aggregates[aggregates["measure"] == measure]
    tot = totals[totals["chain"] == chain]
    frames = []
    for iso3 in config.COUNTRIES:
        t_iso = tot[tot["iso3"] == iso3]
        a_iso = agg[agg["iso3"] == iso3]
        years = sorted(set(t_iso["year"]) | set(a_iso["year"]))
        for year in years:
            items: list[ChainItem] = []
            a_y = a_iso[a_iso["year"] == year]
            for klass, g in a_y[a_y["in_register"]].groupby("instrument_class"):
                items.append(ChainItem("register", f"sum_{klass}", float(g["value_lcu_mn"].sum()),
                                       "official", str(g["source_id"].iloc[0]), str(g["basis"].iloc[0])))
            for sub, g in a_y[~a_y["in_register"]].groupby("sub_type"):
                items.append(ChainItem(STEP_A[chain], f"out_of_register_{sub}", float(g["value_lcu_mn"].sum()),
                                       "official", str(g["source_id"].iloc[0]), str(g["basis"].iloc[0])))
            if chain == "financing" and iso3 == "DEU":
                own = aggregates[(aggregates["iso3"] == "DEU") & (aggregates["measure"] == "own_holdings")]
                own = own.set_index("year")["value_lcu_mn"]
                if year in own.index and (year - 1) in own.index:
                    items.append(ChainItem(STEP_A[chain], "own_holdings_change_declared",
                                           -(float(own[year]) - float(own[year - 1])), "declared",
                                           "BMF_DATENPORTAL", "nominal"))
            for _, r in t_iso[t_iso["year"] == year].iterrows():
                items.append(ChainItem(r["step"], "official_total", r["value_lcu_mn"], "official",
                                       r["item_source_id"], r["basis"]))
            items += _subsector_items(iso3, chain, year)
            frames.append(assemble(iso3, int(year), STEPS[chain], items))
    out = pd.concat(frames, ignore_index=True)
    out["run_id"] = run_id
    out["source_id"] = "ggfiscal.debt.chains"
    out["snapshot_sha256"] = None
    out["quality_grade"] = out["item_type"].map({"official": "A", "computed": "B", "declared": "C", "residual": "B"})
    out["notes"] = None
    out.loc[out["step"] == "register", "quality_grade"] = "B"
    out.loc[out["step"] == "register", "notes"] = "aggregate class-level layer (DD8) pending the per-security register (OQ-8)"
    return out
