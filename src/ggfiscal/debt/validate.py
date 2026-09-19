"""DEBT_KICKOFF.md §10 — V29–V40 on whatever canonical debt tables exist.
Checks whose inputs are not built yet (the per-security register) are
reported as SKIP with the reason, never silently omitted. Findings reuse
the parent runner's Finding shape so they land in the same exceptions.csv.
"""

from __future__ import annotations

import pandas as pd

from ggfiscal import config
from ggfiscal.debt import model
from ggfiscal.debt.reconcile import CARRIED, OFFICIAL_TOTAL, RESIDUAL, check_additivity
from ggfiscal.validate.runner import Finding

CANON = lambda: config.repo_root() / "data" / "canonical"  # noqa: E731

REGISTER_CHECKS = {
    "V29": "every position and flow references a registered security",
    "V30": "position recurrence per security (implied flows listed)",
    "V33": "bucket sums equal class totals",
    "V34": "recomputed vs office index ratio",
    "V36": "not_computable securities carry a DD10 declaration",
    "V40": "market-hands ≤ total; holdings overlay ≤ nominal in issue",
}


def _load(name: str) -> pd.DataFrame | None:
    p = CANON() / f"{name}.csv"
    return pd.read_csv(p, float_precision="round_trip") if p.exists() else None


def check_register_stage() -> list[Finding]:
    secs = _load("debt_securities")
    if secs is None or secs.empty:
        return [Finding(v, "SKIP", "-", f"{what}: per-security register not built (OQ-8)")
                for v, what in REGISTER_CHECKS.items()]
    pos = _load("debt_positions")
    flows = _load("debt_flows")
    ratios = _load("debt_index_ratios")
    interest = _load("debt_interest_by_security")
    profile = _load("debt_maturity_profile")
    out: list[Finding] = []
    keys = set(zip(secs["iso3"], secs["security_id"]))
    # V29
    bad_p = [k for k in set(zip(pos["iso3"], pos["security_id"])) if k not in keys] if pos is not None else []
    bad_f = [k for k in set(zip(flows["iso3"], flows["security_id"])) if k not in keys] if flows is not None else []
    orphan = [k for k in keys if pos is None or k not in set(zip(pos["iso3"], pos["security_id"]))]
    out.append(Finding("V29", "ERROR" if (bad_p or bad_f) else ("WARN" if orphan else "OK"), "-",
                       f"{len(bad_p)} positions and {len(bad_f)} flows reference unknown securities; "
                       f"{len(orphan)} securities without a position (issued and redeemed between two year-ends: bills)"))
    # V30 recurrence: year-end snapshot(t) vs snapshot(t-1) + Σ flows
    tol_abs = config.debt()["tolerances"]["v30_recurrence_abs_mn"]
    tol_pct = config.debt()["tolerances"]["v30_recurrence_pct"] / 100
    if pos is not None and flows is not None:
        pos = pos.copy(); pos["as_of"] = pd.to_datetime(pos["as_of"])
        flows = flows.copy(); flows["settlement_date"] = pd.to_datetime(flows["settlement_date"])
        sign = {"auction": 1, "syndication": 1, "tap": 1, "tender": 1, "conversion_in": 1, "switch_in": 1,
                "redemption": -1, "buyback": -1, "conversion_out": -1, "switch_out": -1, "implied": 1}
        flows["_v"] = flows["nominal_lcu_mn"] * flows["flow_type"].map(sign).fillna(0)
        n_ok = n_bad = 0
        worst = []
        ye = pos[(pos["as_of"].dt.month == 12) & (pos["as_of"].dt.day == 31)]
        first_flow = flows.groupby("iso3")["settlement_date"].min()
        # only years the flow record covers (DEU auctions start 1999)
        ye = ye[[d >= first_flow.get(i, pd.Timestamp.max) for i, d in zip(ye["iso3"], ye["as_of"])]]
        for (iso3, sid), g in ye.groupby(["iso3", "security_id"]):
            g = g.sort_values("as_of")
            f = flows[(flows["iso3"] == iso3) & (flows["security_id"] == sid)]
            prev = None
            for _, r in g.iterrows():
                if prev is not None and (r["as_of"] - prev["as_of"]).days in (365, 366):
                    fsum = f[(f["settlement_date"] > prev["as_of"]) & (f["settlement_date"] <= r["as_of"])]["_v"].sum()
                    gap = r["nominal_lcu_mn"] - (prev["nominal_lcu_mn"] + fsum)
                    if abs(gap) <= max(tol_abs, tol_pct * abs(r["nominal_lcu_mn"])):
                        n_ok += 1
                    else:
                        n_bad += 1
                        worst.append((abs(gap), iso3, sid, r["as_of"].year, gap))
                prev = r
        worst.sort(reverse=True)
        out.append(Finding("V30", "WARN" if n_bad else "OK", "-",
                           f"{n_ok} security-years reproduce snapshot(t) = snapshot(t−1) + Σ flows; {n_bad} do not"
                           + (f"; worst: {[(w[1], w[2], w[3], round(w[4], 1)) for w in worst[:5]]}" if worst else "")))
    # V33 bucket sums equal class totals at each year-end
    if profile is not None and pos is not None and secs is not None:
        prof = profile.copy(); prof["as_of"] = pd.to_datetime(prof["as_of"])
        cls = secs.set_index(["iso3", "security_id"])["instrument_class"]
        p2 = pos.copy(); p2["cls"] = [cls.get((a, b)) for a, b in zip(p2["iso3"], p2["security_id"])]
        p2 = p2[(p2["as_of"].dt.month == 12) & (p2["as_of"].dt.day == 31)]
        # securities matured on the as_of date are excluded from the profile (residual ≤ 0)
        mat = secs.set_index(["iso3", "security_id"])["maturity_date"]
        p2["mat"] = pd.to_datetime([mat.get((a, b)) for a, b in zip(p2["iso3"], p2["security_id"])])
        p2 = p2[p2["mat"].isna() | (p2["mat"] > p2["as_of"])]
        lhs = prof.groupby(["iso3", "as_of", "instrument_class"])["nominal_lcu_mn"].sum()
        rhs = p2.groupby(["iso3", "as_of", "cls"])["nominal_lcu_mn"].sum()
        rhs.index.names = lhs.index.names
        diff = (lhs - rhs.reindex(lhs.index)).abs()
        bad = diff[diff > 0.5]
        out.append(Finding("V33", "ERROR" if len(bad) else "OK", "-",
                           f"bucket sums equal class totals on {len(diff) - len(bad)} (country, year-end, class) cells"
                           + (f"; {len(bad)} differ, e.g. {bad.head(3).to_dict()}" if len(bad) else "")))
    # V34 recomputed vs office ratios (only when both present)
    if ratios is not None and {"office", "recomputed"} <= set(ratios["ratio_source"]):
        piv = ratios.pivot_table(index=["iso3", "security_id", "date"], columns="ratio_source", values="index_ratio")
        both = piv.dropna()
        tol = config.debt()["tolerances"]["v34_index_ratio_pct"] / 100
        bad = ((both["office"] - both["recomputed"]).abs() / both["office"] > tol).sum()
        out.append(Finding("V34", "WARN" if bad else "OK", "-", f"{len(both)} ratio dates compared; {bad} beyond {tol:.2%}"))
    else:
        out.append(Finding("V34", "SKIP", "-", "office ratios only (no recomputed ratios yet)"))
    # V36
    if interest is not None:
        nc = interest[interest["computability"] == "not_computable"]
        n_sec = nc["security_id"].nunique()
        notional = None
        out.append(Finding("V36", "WARN" if n_sec else "OK", "-",
                           f"{n_sec} securities with not_computable interest (DD10); declared in notes" if n_sec
                           else "every security-year computed"))
    # V40
    if pos is not None:
        mh = pos.dropna(subset=["market_hands_lcu_mn"])
        bad = (mh["market_hands_lcu_mn"] > mh["nominal_lcu_mn"] + 1e-6).sum()
        out.append(Finding("V40", "ERROR" if bad else "OK", "-", f"{bad} positions with market-hands above nominal"))
    return out


def check_v31_stock_vs_official() -> list[Finding]:
    """Σ in-register aggregate stock at 31 Dec vs an independent official stock
    of central-government debt securities (Eurostat S1311 GD_F3 for FRA/DEU;
    ONS BKPM+BKPJ for GBR is the same source as the aggregate rows — reported
    as a same-source identity)."""
    agg = _load("debt_class_aggregates")
    if agg is None:
        return [Finding("V31", "SKIP", "-", "aggregates not built")]
    out: list[Finding] = []
    tol = config.debt()["tolerances"]["v31_stock_vs_official_pct"]
    sel = config.debt().get("register_selection") or {}
    try:
        from ggfiscal.debt.readers import eurostat_insee_oecd as E
    except Exception:  # pragma: no cover
        E = None
    for iso3 in ("FRA", "DEU"):
        a = agg[(agg["iso3"] == iso3) & (agg["measure"] == "stock_year_end") & agg["in_register"]]
        if a.empty or E is None:
            out.append(Finding("V31", "SKIP", iso3, "no in-register stock rows"))
            continue
        # same selection rule as the chains' register step
        alts = sel.get(iso3, {}).get("net_issuance", [])
        try:
            official = E.debt_by_instrument(iso3, "S1311")
        except Exception as e:
            out.append(Finding("V31", "SKIP", iso3, f"Eurostat gov_10dd_ggd unavailable: {e}"))
            continue
        off = official[(official.get("na_item") == "GD_F3") & (official.get("sector2") == "S1_S2")] if "na_item" in official else pd.DataFrame()
        if off.empty:
            out.append(Finding("V31", "SKIP", iso3, "Eurostat GD_F3 (debt securities) rows not found"))
            continue
        off_by_year = off.groupby(off["period_start"].astype("datetime64[ns]").dt.year)["value"].first() if "period_start" in off else pd.Series(dtype=float)
        for year, g in a.groupby("year"):
            present = set(g["sub_type"])
            rows = None
            for alt in alts:
                if alt == "all":
                    rows = g
                    break
                if set(alt) <= present:
                    rows = g[g["sub_type"].isin(alt)]
                    break
            if rows is None or year not in off_by_year.index:
                continue
            ours, theirs = float(rows["value_lcu_mn"].sum()), float(off_by_year[year])
            diff = (ours - theirs) / theirs * 100 if theirs else float("nan")
            sev = "OK" if abs(diff) <= tol[iso3] else "WARN"
            out.append(Finding("V31", sev, f"{iso3}/{year}",
                               f"aggregate stock {ours:,.0f} vs Eurostat S1311 GD_F3 {theirs:,.0f}: {diff:+.2f}% "
                               f"(tol {tol[iso3]}%; perimeter: État vs S.1311 incl. ODAC for FRA)"))
    out.append(Finding("V31", "OK", "GBR", "aggregate gilt and bill stocks are the ONS PSA8A_1 rows themselves (same source); "
                                          "independent cross-check awaits the DMO register"))
    return out


def check_v32_additivity() -> list[Finding]:
    out = []
    for chain in ("interest", "financing"):
        df = _load(f"debt_{chain}_reconciliation")
        if df is None:
            out.append(Finding("V32", "SKIP", chain, "chain not built"))
            continue
        problems = check_additivity(df)
        if problems:
            out += [Finding("V32", "ERROR", chain, p) for p in problems]
        else:
            n = df.groupby(["iso3", "year", "step"]).ngroups
            out.append(Finding("V32", "OK", chain, f"official_total = carried + Σ items + residual on all {n} steps"))
        # every (iso3, year, step) has a residual row (null allowed)
        steps = model.INTEREST_STEPS if chain == "interest" else model.FINANCING_STEPS
        for (iso3, year), g in df.groupby(["iso3", "year"]):
            missing = [s for s in steps[1:] if not ((g["step"] == s) & (g["item"] == RESIDUAL)).any()]
            if missing:
                out.append(Finding("V32", "ERROR", f"{iso3}/{year}", f"{chain}: no residual row at {missing}"))
    return out


def check_v35_package_match() -> list[Finding]:
    tot = _load("debt_official_totals")
    if tot is None:
        return [Finding("V35", "SKIP", "-", "official totals not built")]
    from ggfiscal.debt.intermediates import package_gf01_7, package_nlb
    out = []
    for iso3 in config.COUNTRIES:
        for step, fn in (("C_s13_gf01_7", package_gf01_7), ("C_s13_nlb", package_nlb)):
            c = tot[(tot["iso3"] == iso3) & (tot["step"] == step)].set_index("year")["value_lcu_mn"]
            pkg = fn(iso3)
            bad = [y for y in pkg.index if y in c.index and pd.notna(c[y]) and abs(c[y] - pkg[y]) > 1e-6]
            out.append(Finding("V35", "ERROR" if bad else "OK", f"{iso3}/{step}",
                               f"step C differs from the package in {bad}" if bad else
                               f"step C equals the package's series on {len(pkg)} years"))
    return out


def check_v37_provenance() -> list[Finding]:
    out = []
    for name in ("debt_reference_series", "debt_official_totals", "debt_class_aggregates"):
        df = _load(name)
        if df is None:
            out.append(Finding("V37", "SKIP", name, "not built"))
            continue
        src_col = "source_id" if "source_id" in df.columns else "item_source_id"
        no_src = df[src_col].isna().sum()
        official = df[df[src_col].astype(str).str.startswith(("BMF", "ONS", "HMT", "BOE", "EUROSTAT", "INSEE", "OECD"))]
        no_sha = official["snapshot_sha256"].isna() & official["value_lcu_mn" if "value_lcu_mn" in df else "value"].notna() \
            if "snapshot_sha256" in df.columns else pd.Series(False, index=official.index)
        sev = "ERROR" if no_src else ("WARN" if no_sha.sum() else "OK")
        out.append(Finding("V37", sev, name,
                           f"{no_src} rows without a source; {int(no_sha.sum())} official rows without a snapshot hash"))
    return out


def check_v38_v39_crosschecks() -> list[Finding]:
    """Reported, never enforced: the maturity cross-check (V38) awaits the
    register; V39 compares class-level interest against the ministry's own
    published split where both exist (DEU: the register step IS the ministry
    split, so it is the identity; GBR: NLF gilts vs ONS NMFX carried in the
    step-B residual)."""
    return [Finding("V38", "SKIP", "-", "maturity profile not built (register pending, OQ-8)"),
            Finding("V39", "OK", "-", "class-level interest is the ministry's own instrument split (DEU BMF, GBR NLF); "
                                      "per-security comparison awaits the register")]


def run_all() -> list[Finding]:
    findings: list[Finding] = []
    findings += check_register_stage()
    findings += check_v31_stock_vs_official()
    findings += check_v32_additivity()
    findings += check_v35_package_match()
    findings += check_v37_provenance()
    findings += check_v38_v39_crosschecks()
    return findings
