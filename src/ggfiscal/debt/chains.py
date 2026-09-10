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
            # financing chain runs in net-borrowing sign (+ = borrowing) = −B.9
            v = float(s[year]) if chain == "interest" else -float(s[year])
            items.append(ChainItem(STEP_C[chain], f"{label}_{'d41' if chain == 'interest' else 'net_borrowing'}",
                                   v, "official", "EUROSTAT_GOV10A_MAIN_S1311",
                                   "accrued" if chain == "interest" else "accrued, net borrowing = -B.9"))
    return items


def _deu_nka_items(year: int) -> list[ChainItem]:
    """Kreditaufnahmebericht annex 4.10 'Herleitung der Nettokreditaufnahme':
    the official items between gross issuance − redemptions and the NKA
    (sonstige Einnahmen zur Schuldentilgung, Eigenbestand change, the
    non-cash / non-NKA-relevant special-fund and Selbstbewirtschaftung
    lines). Only the top-level items (3.x, not 3.x.y) so nothing double
    counts; 3.1 and 3.3 (gross, redemptions) are the register's own
    quantities and are excluded. Available for the editions that parse."""
    try:
        from ggfiscal.debt.readers import bmf as B
        t = B.kreditaufnahmebericht_annex(year, "4.10")
    except Exception:
        return []
    if t.empty:
        return []
    h = t[t["group"].str.contains("Herleitung", na=False)]
    items = []
    for _, r in h.iterrows():
        item = str(r["item"]).strip()
        if item.count(".") != 1 or item in ("3.1", "3.3"):
            continue
        label = str(r["label"]).strip()
        if label.lower().startswith("nettokreditaufnahme"):
            continue
        items.append(ChainItem("A_cg_cash_requirement", f"nka_{item.replace('.', '_')}_{_short(label)}",
                               float(r["ist_eur"]) / 1e6, "official", "BMF_KREDITAUFNAHMEBERICHT", "cash"))
    return items


def _bridge_items(iso3: str, chain: str, year: int) -> list[ChainItem]:
    """Official step-B (and GBR step-C) items from ggfiscal.debt.bridges."""
    try:
        from ggfiscal.debt.bridges import bridge_items
    except ImportError:
        return []
    return bridge_items(iso3, chain, year)


def _short(label: str) -> str:
    from ggfiscal.debt.aggregates import _slug
    return _slug(label)[:40]


def _register_rows(iso3: str, measure: str, in_reg: pd.DataFrame) -> pd.DataFrame:
    """config/debt.yaml register_selection: the first alternative whose
    sub_types all exist this year; `all` keeps every in-register row."""
    alts = (config.debt().get("register_selection") or {}).get(iso3, {}).get(measure, [])
    for alt in alts:
        if alt == "all":
            return in_reg
        present = set(in_reg["sub_type"])
        if set(alt) <= present:
            return in_reg[in_reg["sub_type"].isin(alt)]
    return in_reg.iloc[0:0]


def build_chain(chain: str, aggregates: pd.DataFrame, totals: pd.DataFrame,
                run_id: str, register_sums: pd.DataFrame | None = None) -> pd.DataFrame:
    """`register_sums` (from register.register_sums) carries the computed
    per-security sums by class; where a (country, year) has them they take
    the register step (item_type computed, grade A) and the DD8 aggregate
    rows step aside into the V31/V39 cross-checks."""
    measure = MEASURE[chain]
    agg = aggregates[aggregates["measure"] == measure]
    tot = totals[totals["chain"] == chain]
    rs = (register_sums[register_sums["chain"] == chain] if register_sums is not None
          else pd.DataFrame(columns=["iso3", "year", "instrument_class", "value_lcu_mn", "basis"]))
    frames = []
    for iso3 in config.COUNTRIES:
        t_iso = tot[tot["iso3"] == iso3]
        a_iso = agg[agg["iso3"] == iso3]
        r_iso = rs[rs["iso3"] == iso3]
        years = sorted(set(t_iso["year"]) | set(a_iso["year"]) | set(r_iso["year"]))
        for year in years:
            items: list[ChainItem] = []
            a_y = a_iso[a_iso["year"] == year]
            r_y = r_iso[r_iso["year"] == year]
            if len(r_y):
                for _, r in r_y.iterrows():
                    items.append(ChainItem("register", f"sum_{r['instrument_class']}", float(r["value_lcu_mn"]),
                                           "computed", "ggfiscal.debt.register", str(r["basis"])))
                if register_sums is not None:
                    br = register_sums[(register_sums["chain"] == f"{chain}_bridge_A")
                                       & (register_sums["iso3"] == iso3) & (register_sums["year"] == year)]
                    for _, r in br.iterrows():
                        items.append(ChainItem(STEP_A[chain], str(r["instrument_class"]), float(r["value_lcu_mn"]),
                                               "computed", "ggfiscal.debt.register", str(r["basis"])))
            else:
                for klass, g in _register_rows(iso3, measure, a_y[a_y["in_register"]]).groupby("instrument_class"):
                    items.append(ChainItem("register", f"sum_{klass}", float(g["value_lcu_mn"].sum()),
                                           "official", str(g["source_id"].iloc[0]), str(g["basis"].iloc[0])))
            for sub, g in a_y[~a_y["in_register"]].groupby("sub_type"):
                v = float(g["value_lcu_mn"].sum())
                if sub.startswith("sondervermoegen_"):
                    # special-fund borrowing is INSIDE the register sum (the
                    # instrument tree is Bund-wide) and OUTSIDE the core-budget
                    # NKA: subtract it on the way to step A
                    items.append(ChainItem(STEP_A[chain], f"less_{sub}", -v, "official",
                                           str(g["source_id"].iloc[0]), str(g["basis"].iloc[0])))
                else:
                    items.append(ChainItem(STEP_A[chain], f"out_of_register_{sub}", v, "official",
                                           str(g["source_id"].iloc[0]), str(g["basis"].iloc[0])))
            if chain == "financing" and iso3 == "DEU":
                items += _deu_nka_items(int(year))
                if len(r_y):
                    # computed register counts auctions at total volume (incl.
                    # the tranche retained for market management); the cash
                    # actually raised differs by the change in the Bund's own
                    # book — an official aggregate from the office
                    own = aggregates[(aggregates["iso3"] == "DEU") & (aggregates["measure"] == "own_holdings")]
                    own = own.set_index("year")["value_lcu_mn"]
                    if year in own.index and (year - 1) in own.index:
                        items.append(ChainItem(STEP_A[chain], "own_holdings_change",
                                               -(float(own[year]) - float(own[year - 1])), "official",
                                               "BMF_DATENPORTAL", "nominal"))
                elif not any(it.item.startswith("nka_") for it in items):
                    own = aggregates[(aggregates["iso3"] == "DEU") & (aggregates["measure"] == "own_holdings")]
                    own = own.set_index("year")["value_lcu_mn"]
                    if year in own.index and (year - 1) in own.index:
                        items.append(ChainItem(STEP_A[chain], "own_holdings_change_declared",
                                               -(float(own[year]) - float(own[year - 1])), "declared",
                                               "BMF_DATENPORTAL", "nominal"))
            for _, r in t_iso[t_iso["year"] == year].iterrows():
                v, basis = r["value_lcu_mn"], r["basis"]
                if chain == "financing" and r["step"] in ("B_s1311_b9", "C_s13_nlb") and pd.notna(v):
                    # totals are stored as B.9 / NLB (net lending); the chain
                    # runs in net-borrowing sign so it flows from net issuance
                    v, basis = -float(v), f"{basis}, net borrowing = -B.9"
                items.append(ChainItem(r["step"], "official_total", v, "official",
                                       r["item_source_id"], basis))
            items += _subsector_items(iso3, chain, year)
            items += _bridge_items(iso3, chain, int(year))
            if chain == "financing" and iso3 == "DEU":
                # the core-budget NKA at step A excludes the special funds
                # that ARE inside S.1311 debt: add their net borrowing back
                # on the way to step B (same rows, opposite sign)
                sv = sum(-it.value for it in items
                         if it.step == STEP_A[chain] and it.item.startswith("less_sondervermoegen_")
                         and it.value is not None)
                items.append(ChainItem("B_s1311_b9", "special_funds_net_borrowing_added_back", sv,
                                       "official", "BMF_DATENPORTAL", "cash"))
            frames.append(assemble(iso3, int(year), STEPS[chain], items))
    out = pd.concat(frames, ignore_index=True)
    out["run_id"] = run_id
    out["source_id"] = "ggfiscal.debt.chains"
    out["snapshot_sha256"] = None
    out["quality_grade"] = out["item_type"].map({"official": "A", "computed": "B", "declared": "C", "residual": "B"})
    out["notes"] = None
    reg = out["step"] == "register"
    computed = reg & (out["item_source_id"] == "ggfiscal.debt.register")
    out.loc[reg & ~computed, "quality_grade"] = "B"
    out.loc[reg & ~computed & (out["item"] != "official_total"), "notes"] = \
        "aggregate class-level layer (DD8) pending the per-security register (OQ-8)"
    out.loc[computed, "quality_grade"] = "A"
    out.loc[computed, "notes"] = "computed from the per-security register (debt_interest_by_security / debt_flows)"
    return out
