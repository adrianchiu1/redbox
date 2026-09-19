"""Family 'ons_hmt': pull coverage and reader behaviour (DEBT_KICKOFF.md §6.3
GBR, §13). Reader tests need the D8 snapshots and skip without them —
`python3 -m ggfiscal.cli debt fetch --family ons_hmt`."""

from __future__ import annotations

import pandas as pd
import pytest

from ggfiscal.debt.families import ons_hmt as family
from ggfiscal.debt.readers import ons_hmt as reader
from ggfiscal.standardise.readers import latest_snapshots

SOURCE_IDS = ("ONS_PSF_APPENDIX_A", "ONS_PSF_APPENDIX_S", "ONS_PSF_TIMESERIES",
              "ONS_RPI", "HMT_DMR", "HMT_NLF")


def _snapshot_parts() -> set[tuple[str, str]]:
    return {k for k in latest_snapshots() if k[0] in SOURCE_IDS}


needs_snapshots = pytest.mark.skipif(
    not _snapshot_parts(),
    reason="no ons_hmt snapshots; run `ggfiscal debt fetch --family ons_hmt`")


# ---------- period labels (no snapshot needed) ----------

@pytest.mark.parametrize("label,expected", [
    ("1998", ("CY", "1998-01-01")),
    ("1998/99", ("FY", "1998-04-01")),
    ("2023-24", ("FY", "2023-04-01")),
    ("Apr 1997 to Mar 1998", ("FY", "1997-04-01")),
    ("Apr to Jun 1997", ("Q", "1997-04-01")),
    ("Jan to Mar 1998", ("Q", "1998-01-01")),
    ("2026 Q1", ("Q", "2026-01-01")),
    ("2026 Jul", ("M", "2026-07-01")),
    ("1987 JAN", ("M", "1987-01-01")),
])
def test_period_labels_parse(label, expected):
    ptype, start = reader._parse_period(label)
    assert (ptype, str(start.date())) == expected


def test_unparseable_period_is_dropped_not_misdated():
    assert reader._parse_period("Time period") == ("", pd.NaT)


# ---------- pulls ----------

@needs_snapshots
def test_pulls_cover_the_register():
    """Every §13 GBR ONS/HMT entry is pulled, with the parts D1 needs."""
    try:
        pulls = family.pulls()
    except family.GovUkResolutionError as e:      # gov.uk unreachable right now
        pytest.skip(str(e))
    by_source: dict[str, set[str]] = {}
    for p in pulls:
        assert p.url.startswith("https://"), p
        assert dict(p.headers).get("User-Agent"), p   # BROWSER_HEADERS on every pull
        by_source.setdefault(p.source_id, set()).add(p.part)

    assert set(by_source) == set(SOURCE_IDS)
    assert by_source["ONS_PSF_APPENDIX_A"] == {"appendix_a"}
    assert by_source["ONS_PSF_APPENDIX_S"] == {"appendix_s"}
    assert by_source["ONS_PSF_TIMESERIES"] == set(family.PSF_CDIDS)
    assert by_source["ONS_RPI"] == {"CHAW", "CDKO", "CZBH"}
    assert set(family.DMR_EDITIONS) <= by_source["HMT_DMR"]
    # the accessible-HTML rendering exists for the two most recent editions
    assert {"2026-27_html", "2025-26_html"} <= by_source["HMT_DMR"]
    # National Loans Fund Accounts: 2005-06 onward, one PDF per financial year
    nlf = sorted(by_source["HMT_NLF"])
    assert nlf[0] == "2005-06" and len(nlf) >= 20
    assert all(len(fy) == 7 and fy[4] == "-" for fy in nlf)


@needs_snapshots
def test_every_pulled_part_has_a_snapshot():
    parts = _snapshot_parts()
    assert len(parts) >= 41
    assert ("ONS_PSF_APPENDIX_A", "appendix_a") in parts
    assert ("ONS_PSF_APPENDIX_S", "appendix_s") in parts
    for cdid in family.PSF_CDIDS:
        assert ("ONS_PSF_TIMESERIES", cdid) in parts
    for cdid in family.RPI_CDIDS:
        assert ("ONS_RPI", cdid) in parts
    for edition in family.DMR_EDITIONS:
        assert ("HMT_DMR", edition) in parts
    assert ("HMT_NLF", "2024-25") in parts


# ---------- Appendix A ----------

@needs_snapshots
def test_psa8a1_gilts_stock_from_1997_98_and_in_the_trillions():
    df = reader.cg_debt_by_instrument()
    assert set(df["instrument"]) == set(reader.CG_DEBT_INSTRUMENTS.values())

    fy = df[(df["cdid"] == "BKPM") & (df["period_type"] == "FY")]
    fy = fy.sort_values("period_start")
    # the financial-year block opens at 1997-98; the calendar block at 1998
    assert fy["period_start"].min() == pd.Timestamp("1997-04-01")
    assert fy["period_label"].iloc[0].startswith("Apr 1997")
    assert len(fy) >= 28

    cy = df[(df["cdid"] == "BKPM") & (df["period_type"] == "CY")]
    assert cy["period_start"].min() == pd.Timestamp("1998-01-01")
    # £mn: the gilt stock passes £1 trillion well before 2023 (§14 GBR)
    v2023 = cy.loc[cy["period_start"] == pd.Timestamp("2023-01-01"), "value"]
    assert float(v2023.iloc[0]) > 1_000_000

    months = df[df["period_type"] == "M"]
    assert months["period_start"].max() >= pd.Timestamp("2026-01-01")


@needs_snapshots
def test_psa_table_layout_is_found_by_stub_not_by_offset():
    """REC2 carries a transaction-code row between the header and the CDIDs;
    PSA8A_1 does not. Both must read."""
    cols = reader.psa_table_columns("REC2").set_index("cdid")["transaction_code"]
    assert cols.loc["-NMFJ"] == "-B.9g"
    assert reader.psa_table_columns("PSA8A_1")["transaction_code"].eq("").all()


@needs_snapshots
def test_cgncr_reconciliation_carries_uplift_and_premia():
    rec = reader.cgncr_reconciliation()
    assert set(rec["sheet"]) == {"REC2", "REC3"}
    cdids = set(rec["cdid"])
    assert {"M98R", "MW7L", "LSIW"} <= cdids     # §14 GBR: uplift and 2020-21 premia
    assert {"-NMFJ", "RUUX"} <= cdids            # REC2: net borrowing -> CGNCR


@needs_snapshots
def test_cg_interest_has_nmfx_and_apf_income():
    ci = reader.cg_interest()
    assert set(ci["sheet"]) == {"PSA6B_2", "PSA6B_1"}
    assert "NMFX" in set(ci.loc[ci["sheet"] == "PSA6B_2", "cdid"])
    apf = ci[ci["sheet"] == "PSA6B_1"]
    assert set(apf["cdid"]) == {"L6BD"}
    assert not apf.empty


# ---------- Appendix S ----------

@needs_snapshots
def test_appendix_s_gilts_column_is_f332_from_1997_98():
    fin = reader.cgncr_financing()
    assert list(fin.columns) == ["period_label", "period_type", "period_start",
                                 "cdid", "esa_code", "label", "value"]
    gilts = fin[fin["cdid"] == "ANTA"]
    assert set(gilts["esa_code"]) == {"F.332"}
    assert "British government securities" in gilts["label"].iloc[0]

    fy = gilts[gilts["period_type"] == "FY"].sort_values("period_start")
    assert fy["period_start"].min() == pd.Timestamp("1997-04-01")
    assert fy["period_label"].iloc[0].startswith("Apr 1997")
    # bills are F.331, coin F.21 — the ESA row is read, not guessed
    assert set(fin.loc[fin["cdid"] == "NAVG", "esa_code"]) == {"F.331"}


# ---------- ONS time series ----------

@needs_snapshots
def test_nmfx_annual_back_to_1946():
    ts = reader.ons_timeseries("NMFX", "pusf")
    assert list(ts.columns) == ["period_type", "period_start", "value"]
    annual = ts[ts["period_type"] == "A"]
    assert annual["period_start"].min() == pd.Timestamp("1946-01-01")
    assert annual["period_start"].max() >= pd.Timestamp("2024-01-01")
    assert set(ts["period_type"]) == {"A", "Q", "M"}


@needs_snapshots
def test_bkpm_timeseries_agrees_with_psa8a1_month_ends():
    ts = reader.ons_timeseries("BKPM", "pusf")
    ts = ts[ts["period_type"] == "M"].set_index("period_start")["value"]
    psa = reader.cg_debt_by_instrument(period_types=("M",))
    psa = psa[psa["cdid"] == "BKPM"].set_index("period_start")["value"]
    common = ts.index.intersection(psa.index)
    assert len(common) > 300
    assert (ts.loc[common] == psa.loc[common]).all()


@needs_snapshots
def test_rpi_index_starts_1947_06_and_is_chaw_from_1987():
    rpi = reader.rpi_index()
    assert isinstance(rpi.index, pd.DatetimeIndex)
    assert rpi.index[0] == pd.Timestamp("1947-06-01")
    assert rpi.loc[pd.Timestamp("1987-01-01")] == 100.0

    chaw = reader.ons_timeseries("CHAW", "mm23")
    chaw = chaw[chaw["period_type"] == "M"].set_index("period_start")["value"]
    spliced = rpi.loc[pd.Timestamp("1987-01-01"):]
    assert len(spliced) == len(chaw)
    assert (spliced.to_numpy() == chaw.sort_index().to_numpy()).all()
    # the pre-1987 tail is CDKO on the Jan-1987 base, so it is strictly smaller
    assert rpi.loc[:pd.Timestamp("1986-12-01")].max() < 100.0


# ---------- HMT ----------

@needs_snapshots
def test_at_least_one_dmr_edition_yields_table_a2_from_2008_09():
    parsed = {}
    for edition in family.DMR_EDITIONS:
        try:
            parsed[edition] = reader.dmr_tables(edition)
        except FileNotFoundError:
            continue            # PDF-only edition: no accessible HTML published
    assert parsed, "no DMR edition has an accessible-HTML snapshot"

    for edition, tables in parsed.items():
        assert set(tables) == {"3.A", "A.1", "A.2"}, edition
        a2 = tables["A.2"]
        rows = set(a2["row"])
        assert "2008-09" in rows, edition
        assert any(r.startswith("2024-25") for r in rows), edition
        cgncr = a2[(a2["row"] == "2008-09") & a2["column"].str.startswith("CGNCR")]
        assert float(cgncr["value"].iloc[0]) > 100.0          # £bn
        assert tables["3.A"]["row"].str.contains("Gross financing requirement").any()
        assert tables["A.1"]["row"].str.contains("Conventional gilts").any()


@needs_snapshots
def test_nlf_2024_25_text_and_interest_note():
    text = reader.nlf_account_text("2024-25")
    assert len(text) > 50_000
    assert "National Loans Fund" in text

    note = reader.nlf_interest_summary("2024-25")
    assert not note.empty
    items = note.set_index("item")["value"]
    assert items["gilts"] == 71595.0
    assert items["national_savings"] == 9316.0
    # the note's own components add to its own total: extraction, not arithmetic
    parts = note[note["item"].isin(
        ("gilts", "treasury_bills", "national_savings", "other"))]["value"].sum()
    assert parts == items["total"]
    assert items["interest_paid_cash"] < 0        # cash flow statement, outflow


@needs_snapshots
def test_nlf_editions_that_do_not_parse_return_an_empty_frame():
    """2006-07 and 2007-08 are published with a font that carries no usable
    ToUnicode map; extraction yields mojibake and the reader says so by
    returning nothing rather than a wrong number."""
    for edition in ("2006-07", "2007-08"):
        empty = reader.nlf_interest_summary(edition)
        assert empty.empty
        assert list(empty.columns) == ["edition", "source", "label", "item", "value"]
