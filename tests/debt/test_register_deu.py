"""DEU per-security register (DEBT_KICKOFF.md §5, §14 DEU): the Finanzagentur
readers, the four canonical frames, and the reconciliation to the aggregate
layer (V29, V30, V31, V34).

Everything that touches a snapshot is skipped where the D8 store is empty (a
fresh checkout without `ggfiscal debt fetch`).
"""

import pandas as pd
import pytest

from ggfiscal.debt import register_deu as R
from ggfiscal.debt.model import TABLES
from ggfiscal.debt.readers import finanzagentur as F
from ggfiscal.standardise.readers import latest_snapshots

SNAPS = latest_snapshots()
RUN_ID = "TEST_REGISTER_DEU"

#: The office's own Umlaufvolumen at 31.12.2024 (BMF Datenportal, EUR mn).
UMLAUFVOLUMEN_2024_MN = 1_882_000.0

needs_annual = pytest.mark.skipif(
    (F.SOURCE_ID, F.ANNUAL_PART) not in SNAPS, reason="no Finanzagentur annual snapshot")
needs_auctions = pytest.mark.skipif(
    (F.SOURCE_ID, F.AUCTION_PARTS[0]) not in SNAPS, reason="no Finanzagentur auction snapshot")
needs_ratios = pytest.mark.skipif(
    not all((F.SOURCE_ID, p) in SNAPS for p in F.RATIO_PARTS),
    reason="no Finanzagentur index-ratio snapshots")
needs_schuldenbericht = pytest.mark.skipif(
    (F.SOURCE_ID, F.SCHULDENBERICHT_PART) not in SNAPS,
    reason="no Finanzagentur Schuldenbericht snapshot")
needs_all = pytest.mark.skipif(
    not all((F.SOURCE_ID, p) in SNAPS
            for p in (F.ANNUAL_PART, F.MONTHLY_PART, F.AUCTION_PARTS[0], *F.RATIO_PARTS)),
    reason="incomplete Finanzagentur snapshot set")


@pytest.fixture(scope="module")
def tables() -> dict[str, pd.DataFrame]:
    return R.build(RUN_ID)


# --------------------------------------------------------------------- parsing

def test_parse_coupon_reads_the_german_decimal_comma():
    assert R.parse_coupon("6,500") == (6.5, None, None)
    assert R.parse_coupon("0,000") == (0.0, None, None)
    assert R.parse_coupon(None) == (None, None, None)


def test_parse_coupon_reads_the_floating_terms_string():
    coupon, ref, spread = R.parse_coupon("3ME25")
    assert coupon is None and ref == R.FRN_REFERENCE and spread == 25.0


def test_dividend_dates_follow_the_maturity_anniversary():
    from ggfiscal.debt.interest import parse_dividend_dates

    text = R.dividend_dates(pd.Timestamp("2036-02-15"))
    assert text == "15 Feb"
    assert parse_dividend_dates(text, None, 1) == [(15, 2)]


# --------------------------------------------------------------------- readers

@needs_annual
def test_wertpapierliste_covers_every_year_end_since_1995():
    df = F.wertpapierliste(F.ANNUAL_PART)
    years = sorted(df["as_of"].dt.year.unique())
    assert years == list(range(1995, 2026))
    assert set(df["as_of"].dt.strftime("%m-%d")) == {"12-31"}


@needs_annual
def test_wertpapierliste_reproduces_the_sheets_own_summe_row():
    df = F.wertpapierliste(F.ANNUAL_PART)
    total = F.wertpapierliste_total(F.ANNUAL_PART)
    got = df.groupby("as_of")["nominal_eur"].sum()
    pd.testing.assert_series_equal(got, total.rename("nominal_eur").rename_axis("as_of"),
                                   check_exact=False, rtol=1e-9)


@needs_auctions
def test_auktionen_volume_is_allotment_plus_retention():
    au = F.auktionen()
    both = au[au["zuteilung_mn"].notna() & au["marktpflegequote_mn"].notna()
              & au["emissionsvolumen_mn"].notna()]
    off = (both["emissionsvolumen_mn"] - both["zuteilung_mn"]
           - both["marktpflegequote_mn"]).abs() > 0.05
    # the identity holds except on a handful of 1999-2003 rows (documented)
    assert off.sum() <= 40, both[off].head().to_string()
    assert off[both["termin"] >= "2004-01-01"].sum() == 0


@needs_ratios
def test_index_ratio_files_are_continuous_across_their_rebasings():
    seams = F.index_ratio_seams()
    assert not seams.empty
    assert set(seams["date"].dt.strftime("%Y-%m-%d")) == {"2016-03-01", "2026-03-01"}
    worst = seams["ratio_rel_diff"].abs().max()
    assert worst < 1e-4, f"index ratios jump {worst:.2%} at a base-year seam"
    # the daily reference index, unlike the ratio, does rebase
    assert (seams["index_rebase_factor"] > 1.1).all()


@needs_schuldenbericht
def test_eigenbestand_is_published_by_group_not_by_isin():
    eb = R.eigenbestand_year_end()
    assert eb.index.min() == 1995 and eb.loc[2024] == pytest.approx(201_720.09, abs=1.0)
    labels = set(F.umlaufvolumen()["label"])
    assert not any(R.ISIN_RE.match(x) for x in labels)


# -------------------------------------------------------------------- schemas

@needs_all
def test_every_table_validates_against_its_schema(tables):
    for name, df in tables.items():
        TABLES[name].validate(df)
        assert (df["iso3"] == "DEU").all()
        assert (df["source_id"] == R.SOURCE_ID).all()
        assert (df["run_id"] == RUN_ID).all()
        assert df["snapshot_sha256"].notna().all()


@needs_all
def test_office_rows_are_grade_a(tables):
    for name in ("debt_securities", "debt_positions", "debt_index_ratios"):
        assert (tables[name]["quality_grade"] == "A").all()
    fl = tables["debt_flows"]
    assert (fl.loc[fl["flow_type"] != "redemption", "quality_grade"] == "A").all()
    # redemptions are derived from the position (DD13) and are graded down
    assert (fl.loc[fl["flow_type"] == "redemption", "quality_grade"] == "B").all()


# ----------------------------------------------------------------- securities

@needs_all
def test_register_holds_the_whole_federal_securities_universe(tables):
    secs = tables["debt_securities"]
    assert len(secs) >= 150
    assert secs["security_id"].is_unique
    assert secs["security_id"].str.match(R.ISIN_RE).all()
    for sub in ("bund", "bobl", "schatz", "bubill", "bund_ei", "bund_green"):
        assert (secs["sub_type"] == sub).any(), sub
    assert secs["instrument_class"].isin(
        ["fixed_bullet", "floating", "inflation_linked", "bill", "other"]).all()


@needs_all
def test_linkers_and_green_bonds_carry_their_terms(tables):
    secs = tables["debt_securities"]
    lk = secs[secs["instrument_class"] == "inflation_linked"]
    assert len(lk) >= 9
    assert (lk["index_reference"] == "EA_HICP_XT").all()
    assert (lk["index_lag_months"] == 3).all()
    assert lk["base_index"].notna().all()
    assert lk["dividend_dates"].str.endswith("Apr").all()
    assert secs.loc[secs["is_green"], "sub_type"].eq("bund_green").all()


@needs_all
def test_strips_and_schuldscheindarlehen_are_out_of_the_register(tables):
    secs = set(tables["debt_securities"]["security_id"])
    monthly = F.wertpapierliste_securities(F.MONTHLY_PART)
    strips = monthly[monthly["wertpapierart"].str.contains("strips", case=False)]
    assert len(strips) > 100 and not (set(strips["isin"]) & secs)
    annual = F.wertpapierliste_securities(F.ANNUAL_PART)
    ssd = annual[annual["wertpapierart"].str.startswith("Schuldscheindarlehen")]
    assert len(ssd) > 0 and not (set(ssd["isin"]) & secs)


# ------------------------------------------------------------------ positions

@needs_all
def test_every_position_references_a_security(tables):
    """V29 referential integrity."""
    secs = set(tables["debt_securities"]["security_id"])
    for name in ("debt_positions", "debt_flows", "debt_index_ratios"):
        orphans = set(tables[name]["security_id"]) - secs
        assert not orphans, f"{name}: {sorted(orphans)[:5]}"


@needs_all
def test_positions_exist_for_every_31_december_1995_to_2025(tables):
    pos = tables["debt_positions"]
    annual = pos[pos["position_type"] == "office_annual"]
    got = set(annual["as_of"].dt.strftime("%Y-%m-%d"))
    assert {f"{y}-12-31" for y in range(1995, 2026)} <= got
    assert (annual.groupby("as_of").size() >= 60).all()
    snap = pos[pos["position_type"] == "office_snapshot"]
    assert len(snap) > 0 and snap["as_of"].nunique() == 1
    assert snap["as_of"].iloc[0] > pd.Timestamp("2025-12-31")


@needs_all
def test_sum_of_2024_positions_matches_the_official_umlaufvolumen(tables):
    pos = tables["debt_positions"]
    total = pos.loc[pos["as_of"] == "2024-12-31", "nominal_lcu_mn"].sum()
    ratio = total / UMLAUFVOLUMEN_2024_MN
    assert abs(ratio - 1.0) < 0.02, (
        f"Σ nominal 2024-12-31 = {total:,.1f} mn vs Umlaufvolumen "
        f"{UMLAUFVOLUMEN_2024_MN:,.0f} mn, ratio {ratio:.4f}")


@needs_all
def test_linker_positions_carry_the_uplifted_nominal(tables):
    secs, pos = tables["debt_securities"], tables["debt_positions"]
    lk = set(secs.loc[secs["instrument_class"] == "inflation_linked", "security_id"])
    up = pos[pos["security_id"].isin(lk) & (pos["as_of"] >= "2007-12-31")]
    assert up["nominal_uplifted_lcu_mn"].notna().mean() > 0.9
    ratio = up["nominal_uplifted_lcu_mn"] / up["nominal_lcu_mn"]
    assert ratio.dropna().between(0.98, 1.6).all()
    # non-linkers never carry one
    other = pos[~pos["security_id"].isin(lk)]
    assert other["nominal_uplifted_lcu_mn"].isna().all()


# ---------------------------------------------------------------------- flows

@needs_all
def test_flows_cover_every_auction_from_2000(tables):
    fl = tables["debt_flows"]
    ops = fl[fl["flow_type"].isin(["auction", "syndication"])]
    assert len(ops) >= 1_000
    years = set(ops["settlement_date"].dt.year)
    assert set(range(2000, 2026)) <= years
    assert (ops["flow_type"] == "syndication").sum() > 0
    # one 2025 own-book placement is reversed later that year, so the office
    # publishes it as a negative Emissionsvolumen; it is kept as published
    negative = ops[ops["nominal_lcu_mn"] < 0]
    assert len(negative) == 1 and (negative["method"].str.startswith("EB")).all()
    assert ops["nominal_lcu_mn"].ne(0).all()
    priced = ops[ops["price_pct"].notna()]
    assert (priced["cash_lcu_mn"] / priced["nominal_lcu_mn"]).between(0.5, 1.5).mean() > 0.95


@needs_all
def test_retention_flows_mirror_the_marktpflegequote(tables):
    fl = tables["debt_flows"]
    ret = fl[fl["flow_type"] == "retention"]
    assert len(ret) > 1_000
    au = F.auktionen()
    assert ret["nominal_lcu_mn"].sum() == pytest.approx(
        au["marktpflegequote_mn"].fillna(0).sum(), rel=1e-6)


@needs_all
def test_redemptions_close_matured_securities(tables):
    secs, pos, fl = tables["debt_securities"], tables["debt_positions"], tables["debt_flows"]
    red = fl[fl["flow_type"] == "redemption"]
    assert len(red) > 500
    matured = secs[secs["maturity_date"] < pos["as_of"].max()]
    covered = set(red["security_id"])
    assert len(covered & set(matured["security_id"])) / len(matured) > 0.95
    # never a redemption after the last position date
    assert red["settlement_date"].max() <= pos["as_of"].max()


@needs_all
@pytest.mark.parametrize("security_id", ["DE0001102374", "DE0001135275", "DE0001141810"])
def test_v30_recurrence_for_sample_bunds(tables, security_id):
    """V30: position(t) − position(t−1) = Σ flows in the year, within 1 %.

    Flows are dated by the operation day (the office publishes no Valuta), so a
    late-December auction settling in January would show up here; none of the
    sample securities has one.
    """
    pos, fl = tables["debt_positions"], tables["debt_flows"]
    annual = pos[(pos["position_type"] == "office_annual")
                 & (pos["security_id"] == security_id)]
    assert not annual.empty
    level = annual.set_index(annual["as_of"].dt.year)["nominal_lcu_mn"]
    f = fl[(fl["security_id"] == security_id) & (fl["flow_type"] != "retention")]
    sign = f["flow_type"].map(lambda x: -1.0 if x == "redemption" else 1.0)
    net = (f.assign(v=f["nominal_lcu_mn"] * sign)
           .groupby(f["settlement_date"].dt.year)["v"].sum())

    failures = []
    for year in range(1996, 2026):
        change = float(level.get(year, 0.0)) - float(level.get(year - 1, 0.0))
        flow = float(net.get(year, 0.0))
        scale = max(abs(change), abs(flow), 1.0)
        if abs(change - flow) / scale > 0.01:
            failures.append((year, change, flow, change - flow))
    assert not failures, f"{security_id}: Δposition != Σflows in {failures}"


# ------------------------------------------------------------- index ratios

@needs_all
def test_index_ratios_span_2006_to_2026(tables):
    ir = tables["debt_index_ratios"]
    assert (ir["ratio_source"] == "office").all()
    assert ir["date"].min() <= pd.Timestamp("2006-04-01")
    assert ir["date"].max() >= pd.Timestamp("2026-06-30")
    # no single linker lives the whole span (the 2006 vintage matured 2016), so
    # coverage is asserted on the table and on one long-lived security
    spans = ir.groupby("security_id")["date"].agg(["min", "max"])
    assert (spans["min"] <= "2006-04-01").any()
    long_lived = spans[(spans["min"] <= "2015-12-31") & (spans["max"] >= "2026-06-30")]
    assert len(long_lived) >= 2, spans.to_string()


@needs_all
def test_a_linker_is_continuous_across_the_2015_to_2025_base_change(tables):
    sid = "DE0001030575"                       # 0.10 % Bund/ei 15.04.2046
    seam = F.index_ratio_seams()
    row = seam[(seam["isin"] == sid) & (seam["file_new"] == "index_ratios_2025")]
    assert len(row) == 1, seam.to_string()
    r = row.iloc[0]
    assert abs(r["ratio_rel_diff"]) < 1e-4, r.to_dict()
    # the reference index does rebase across the same day
    assert r["index_rebase_factor"] == pytest.approx(1.281, abs=0.01)
    # and the day-over-day step across the seam is an ordinary daily step
    ir = tables["debt_index_ratios"]
    ir = ir[ir["security_id"] == sid].set_index("date")["index_ratio"]
    step = ir.loc["2026-02-01":"2026-04-01"].pct_change().abs()
    assert step.loc[pd.Timestamp("2026-03-01")] <= step.max()


# ------------------------------------------------------------ reconciliation

@needs_all
@needs_schuldenbericht
def test_stock_reconciles_to_the_aggregate_layer(tables):
    """V31: Σ 31 Dec nominal vs the ministry's Umlaufvolumen, and Σ market hands
    vs the Kreditbestand. The pre-2004 shortfall is the assumed special funds
    the Finanzagentur does not list per ISIN; 2013-2019 is the Länder tranche of
    the Bund-Länder-Anleihe; 2022 is the WSF Zusatzemissionen (§26b StFG)."""
    rec = R.reconciliation(RUN_ID, tables).__getitem__("stock").set_index("year")
    modern = rec.loc[2004:]
    off = modern[(modern["ratio_nominal_over_umlauf"] - 1).abs() > 0.005]
    assert set(off.index) <= {2022}, off.round(4).to_string()
    assert rec.loc[2024, "ratio_nominal_over_umlauf"] == pytest.approx(1.0, abs=1e-6)
    kb = modern[(modern["ratio_market_hands_over_kreditbestand"] - 1).abs() > 0.011]
    assert kb.empty, kb.round(4).to_string()


@needs_all
@needs_schuldenbericht
def test_issuance_reconciles_to_the_aggregate_layer_with_a_declared_wedge(tables):
    """The register counts nominal at the operation, the Datenportal counts the
    cash year's Bruttokreditaufnahme (proceeds, so own-book sales of previously
    retained paper are in and the year's unsold retention is out). Close, not
    identical — the wedge is reported, never allocated (DD13)."""
    rec = R.reconciliation(RUN_ID, tables)["issuance"].set_index("year")
    r = rec.loc[1999:2025, "ratio_issue_volume_over_official"].dropna()
    assert len(r) >= 25
    assert r.between(0.90, 1.35).all(), r.round(4).to_string()
    # the total issue volume, not the allotted part, is the closer measure
    assert (r - 1).abs().median() < (
        rec.loc[1999:2025, "ratio_allotted_over_official"] - 1).abs().median()


@needs_all
def test_security_counts_per_year_are_reported(tables):
    rec = R.reconciliation(RUN_ID, tables)["stock"].set_index("year")
    assert rec["n_securities"].min() >= 50
    assert rec.loc[1995, "n_securities"] > 100
    by_class = R.reconciliation(RUN_ID, tables)["by_class"]
    assert set(by_class["instrument_class"]) >= {"fixed_bullet", "bill", "other"}
