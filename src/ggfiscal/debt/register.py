"""Stage D2–D4 assembly (DEBT_KICKOFF.md §12): collect each country's
per-security register, compute interest by security (§7), the maturity
profile and issuance-by-bucket tables (DD7), and hand the computed register
sums to the chains.

Country builders live in `register_{iso3}.py` and expose
`build(run_id) -> {"debt_securities", "debt_positions", "debt_flows",
"debt_index_ratios"}`; a country without a builder (or whose office is
still unreachable) simply contributes no rows, and the chains fall back to
the DD8 aggregate layer for it.
"""

from __future__ import annotations

import pandas as pd

from ggfiscal import config
from ggfiscal.debt import interest as I
from ggfiscal.debt import maturity as M
from ggfiscal.debt import model

REGISTER_TABLES = ("debt_securities", "debt_positions", "debt_flows", "debt_index_ratios")
COUNTRY_MODULES = {"DEU": "register_deu", "GBR": "register_gbr", "FRA": "register_fra"}


def collect(run_id: str) -> dict[str, pd.DataFrame]:
    parts: dict[str, list[pd.DataFrame]] = {t: [] for t in REGISTER_TABLES}
    for iso3, mod in COUNTRY_MODULES.items():
        try:
            m = __import__(f"ggfiscal.debt.{mod}", fromlist=["build"])
        except ImportError:
            continue
        out = m.build(run_id)
        for t in REGISTER_TABLES:
            df = out.get(t)
            if df is not None and len(df):
                parts[t].append(df)
    result = {}
    for t in REGISTER_TABLES:
        if parts[t]:
            result[t] = model.TABLES[t].validate(pd.concat(parts[t], ignore_index=True))
        else:
            result[t] = pd.DataFrame(columns=list(model.TABLES[t].columns))
    return result


# ---------------------------------------------------------------- interest

def _reference_for(security: pd.Series, reference: pd.DataFrame | None) -> pd.Series | None:
    ref_id = security.get("floating_reference")
    if reference is None or not isinstance(ref_id, str):
        return None
    s = reference[reference["series_id"] == ref_id]
    if s.empty:
        return None
    return s.set_index("date")["value"].sort_index()


def build_interest_by_security(reg: dict[str, pd.DataFrame], reference: pd.DataFrame | None,
                               run_id: str, years: range | None = None) -> pd.DataFrame:
    secs, pos, flows, ratios = (reg["debt_securities"], reg["debt_positions"],
                                reg["debt_flows"], reg["debt_index_ratios"])
    rows: list[dict] = []
    for iso3, s_iso in secs.groupby("iso3"):
        p_iso = pos[pos["iso3"] == iso3]
        f_iso = flows[flows["iso3"] == iso3]
        r_iso = ratios[ratios["iso3"] == iso3]
        yrs = years or range(int(min(p_iso["as_of"].min(), f_iso["settlement_date"].min()).year),
                             int(max(p_iso["as_of"].max(), f_iso["settlement_date"].max()).year) + 1)
        for _, sec in s_iso.iterrows():
            first = sec["first_issue_date"] if pd.notna(sec["first_issue_date"]) else None
            last = sec["maturity_date"] if pd.notna(sec["maturity_date"]) else None
            for year in yrs:
                if first is not None and year < first.year:
                    continue
                if last is not None and year > last.year:
                    continue
                for r in I.interest_for_security(sec, p_iso, f_iso, year, ratios=r_iso,
                                                 reference=_reference_for(sec, reference)):
                    r.pop("implied_flows", None)
                    r.update({"run_id": run_id, "source_id": "ggfiscal.debt.interest",
                              "snapshot_sha256": None, "quality_grade": sec["quality_grade"],
                              "notes": None})
                    rows.append(r)
    df = pd.DataFrame(rows, columns=list(model.INTEREST_BY_SECURITY.columns))
    return model.INTEREST_BY_SECURITY.validate(df) if len(df) else df


# ---------------------------------------------------------------- maturity

def build_maturity_tables(reg: dict[str, pd.DataFrame], run_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    secs, pos, flows = reg["debt_securities"], reg["debt_positions"], reg["debt_flows"]
    profiles, issuance = [], []
    for iso3 in config.COUNTRIES:
        p = pos[pos["iso3"] == iso3]
        if p.empty:
            continue
        year_ends = sorted(d for d in p["as_of"].unique() if pd.Timestamp(d).month == 12 and pd.Timestamp(d).day == 31)
        for d in year_ends:
            prof = M.maturity_profile(secs, p, pd.Timestamp(d), iso3)
            if len(prof):
                profiles.append(prof)
        f = flows[flows["iso3"] == iso3]
        if not f.empty:
            for year in range(int(f["settlement_date"].min().year), int(f["settlement_date"].max().year) + 1):
                iss = M.issuance_by_bucket(secs, f, year, iso3)
                if len(iss):
                    issuance.append(iss)

    def _finish(frames, schema):
        if not frames:
            return pd.DataFrame(columns=list(schema.columns))
        df = pd.concat(frames, ignore_index=True)
        df["run_id"] = run_id
        df["source_id"] = "ggfiscal.debt.maturity"
        df["snapshot_sha256"] = None
        df["quality_grade"] = "A"
        df["notes"] = None
        return schema.validate(df)

    return _finish(profiles, model.MATURITY_PROFILE), _finish(issuance, model.ISSUANCE_BY_BUCKET)


# ------------------------------------------------ register sums for the chains

def register_sums(reg: dict[str, pd.DataFrame], interest: pd.DataFrame,
                  basis: str = "cash") -> pd.DataFrame:
    """Computed register-step items per (iso3, year, chain, instrument_class):
    interest on `basis` (cash matches the ministries' step-A totals; the
    accrued figure is published alongside in debt_interest_by_security),
    and net issuance = Σ issuance − redemptions − buybacks ± conversions
    from the flows. Only countries with a register appear."""
    rows = []
    secs = reg["debt_securities"].set_index(["iso3", "security_id"])["instrument_class"]
    if len(interest):
        it = interest[(interest["basis"] == basis) & (interest["computability"] == "computed")].copy()
        it["instrument_class"] = [secs.get((a, b)) for a, b in zip(it["iso3"], it["security_id"])]
        for (iso3, year, klass), g in it.groupby(["iso3", "year", "instrument_class"]):
            rows.append({"iso3": iso3, "year": int(year), "chain": "interest",
                         "instrument_class": klass, "value_lcu_mn": float(g["total_lcu_mn"].sum()),
                         "n_securities": int(g["security_id"].nunique()), "basis": basis})
    fl = reg["debt_flows"]
    if len(fl):
        fl = fl.copy()
        fl["instrument_class"] = [secs.get((a, b)) for a, b in zip(fl["iso3"], fl["security_id"])]
        sign = {"auction": 1, "syndication": 1, "tap": 1, "tender": 1, "conversion_in": 1, "switch_in": 1,
                "redemption": -1, "buyback": -1, "conversion_out": -1, "switch_out": -1,
                "retention": 0, "own_book_sale": 0, "own_book_purchase": 0, "implied": 1}
        fl["_v"] = fl["nominal_lcu_mn"] * fl["flow_type"].map(sign).fillna(0)
        fl["year"] = fl["settlement_date"].dt.year
        for (iso3, year, klass), g in fl.groupby(["iso3", "year", "instrument_class"]):
            rows.append({"iso3": iso3, "year": int(year), "chain": "financing",
                         "instrument_class": klass, "value_lcu_mn": float(g["_v"].sum()),
                         "n_securities": int(g["security_id"].nunique()), "basis": "nominal"})
    # step-A bridge for the interest chain: premia/discounts realised at
    # issue (the ministries' cash interest books agio/disagio at value
    # date; the register's cash coupons do not) — Σ (price − 100)/100 ×
    # nominal placed, per year, sign such that a premium REDUCES interest
    if len(fl):
        priced = fl[fl["price_pct"].notna() & fl["flow_type"].isin(["auction", "syndication", "tap", "tender"])].copy()
        if len(priced):
            ret = fl[fl["flow_type"] == "retention"].groupby(["iso3", "security_id", "settlement_date"])["nominal_lcu_mn"].sum()
            placed = priced["nominal_lcu_mn"] - [ret.get((a, b, d), 0.0) for a, b, d in
                                                  zip(priced["iso3"], priced["security_id"], priced["settlement_date"])]
            priced["_prem"] = -(priced["price_pct"] - 100.0) / 100.0 * placed
            # accrued interest (Stückzinsen) received from buyers on a
            # reopening: placed × coupon × days since the last coupon date /
            # days in the coupon period — netted against interest paid by
            # the ministries, and not in the register's cash coupons
            sec_rows = reg["debt_securities"].set_index(["iso3", "security_id"])
            accrued = []
            for (iso3, sid, d, n) in zip(priced["iso3"], priced["security_id"], priced["settlement_date"], placed):
                sec = sec_rows.loc[(iso3, sid)]
                cpn = sec.get("coupon_pct")
                if pd.isna(cpn) or sec.get("instrument_class") in ("bill", "floating") or n <= 0:
                    accrued.append(0.0)
                    continue
                try:
                    prev, nxt = I.coupon_period_bounds(sec, pd.Timestamp(d))
                    f = int(sec["coupon_frequency"]) if pd.notna(sec.get("coupon_frequency")) else 1
                    accrued.append(-float(n) * float(cpn) / 100.0 / f * (pd.Timestamp(d) - prev).days / (nxt - prev).days)
                except Exception:
                    accrued.append(0.0)
            priced["_acc"] = accrued
            for (iso3, year), g in priced.groupby(["iso3", "year"]):
                rows.append({"iso3": iso3, "year": int(year), "chain": "interest_bridge_A",
                             "instrument_class": "issue_premium_at_value_date",
                             "value_lcu_mn": float(g["_prem"].sum()), "n_securities": int(g["security_id"].nunique()),
                             "basis": "cash"})
                rows.append({"iso3": iso3, "year": int(year), "chain": "interest_bridge_A",
                             "instrument_class": "accrued_interest_received_at_issue",
                             "value_lcu_mn": float(g["_acc"].sum()), "n_securities": int(g["security_id"].nunique()),
                             "basis": "cash"})
    return pd.DataFrame(rows, columns=["iso3", "year", "chain", "instrument_class",
                                       "value_lcu_mn", "n_securities", "basis"])
