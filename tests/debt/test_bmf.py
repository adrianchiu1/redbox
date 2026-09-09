"""Family 'bmf' (DEBT_KICKOFF.md §6.3 DEU, §13): pull definitions, the
Datenportal workbook and its sibling CSVs, and the Kreditaufnahmebericht PDFs.

Everything that touches a snapshot is skipped where the D8 store is empty (a
fresh checkout without `ggfiscal debt fetch`)."""

import pandas as pd
import pytest

from ggfiscal.debt.families import bmf as family
from ggfiscal.debt.readers import bmf as readers
from ggfiscal.standardise.readers import latest_snapshots

SNAPS = latest_snapshots()


def _have(source_id: str, part: str) -> bool:
    return (source_id, part) in SNAPS


needs_xlsx = pytest.mark.skipif(
    not _have("BMF_DATENPORTAL", readers.DATENPORTAL_XLSX),
    reason="no BMF_DATENPORTAL workbook snapshot")
needs_csv = pytest.mark.skipif(
    not all(_have("BMF_DATENPORTAL", p) for p in readers.CSV_SHEET),
    reason="no BMF_DATENPORTAL CSV snapshots")
needs_kab_2025 = pytest.mark.skipif(
    not _have("BMF_KREDITAUFNAHMEBERICHT", "2025"),
    reason="no Kreditaufnahmebericht 2025 snapshot")


# ---------------------------------------------------------------------- pulls

def test_pulls_cover_every_registered_part():
    parts = {(p.source_id, p.part) for p in family.pulls()}
    assert ("BMF_DATENPORTAL", "kredit_brutto_tilgung_zinsen_xlsx") in parts
    for part in ("bruttokreditaufnahme_csv", "tilgungen_csv", "kreditbestand_csv"):
        assert ("BMF_DATENPORTAL", part) in parts
    for year in range(2018, 2026):
        assert ("BMF_KREDITAUFNAHMEBERICHT", str(year)) in parts
    assert ("BMF_MONATSBERICHT", "2025-11_kreditaufnahme") in parts
    assert ("BMF_HAUSHALTSRECHNUNG", "index") in parts
    assert ("BMF_HAUSHALTSRECHNUNG", "2025_band2") in parts


def test_pull_urls_are_bmf_and_unique():
    pulls = family.pulls()
    assert len({(p.source_id, p.part) for p in pulls}) == len(pulls)
    assert len({p.url for p in pulls}) == len(pulls)
    assert all(p.url.startswith(family.BMF_BASE) for p in pulls)


# --------------------------------------------------------- Datenportal workbook

@needs_xlsx
def test_schuldenstand_periods_are_monthly_and_span_1995_to_2026():
    df = readers.datenportal("rpgSchuldenstand")
    periods = pd.DatetimeIndex(sorted(df["period"].unique()))
    assert periods.min() == pd.Timestamp("1995-12-31")
    assert periods.max() >= pd.Timestamp("2026-06-30")
    # every month-end between the two, with no gaps and nothing else
    expected = pd.date_range(periods.min(), periods.max(), freq="ME")
    assert list(periods) == list(expected)


@needs_xlsx
def test_schuldenstand_carries_the_bundesanleihen_tree():
    df = readers.datenportal("rpgSchuldenstand")
    anleihen = df[df["series_label"].str.contains("Bundesanleihen")]
    assert not anleihen.empty
    paths = set(anleihen["series_path"])
    assert ("Instrumentenarten / Bundeswertpapiere / Konventionelle "
            "Bundeswertpapiere / Bundesanleihen") in paths
    # the hierarchy is reconstructed from the indentation, so the 10-year line
    # must sit *below* the Bundesanleihen line, not beside it
    assert any(p.endswith("/ Bundesanleihen / 10-jährige Bundesanleihen")
               for p in paths)


@needs_xlsx
def test_total_stock_december_2024_is_in_range():
    df = readers.datenportal("rpgSchuldenstand")
    dec = df[df["period"] == pd.Timestamp("2024-12-31")]
    total = dec[(dec["section"] == "Gesamt") & (dec["level"] == 0)]
    assert not total.empty
    for value in total["value_eur_mn"]:
        assert 1_500_000 < value < 2_100_000
    instruments = dec[dec["series_path"] ==
                      "Instrumentenarten / Bundeswertpapiere"]["value_eur_mn"]
    assert 1_500_000 < float(instruments.iloc[0]) < 2_100_000


@needs_xlsx
def test_zinsen_sheet_has_values_and_is_signed_negative():
    """The Zinsen sheet is the balance of interest paid and received, so an
    interest *cost* is negative; it is cumulative within the calendar year."""
    df = readers.datenportal("rpgZinsen Gesamt")
    assert not df.empty
    dec = df[(df["period"] == pd.Timestamp("2024-12-31")) & (df["level"] == 0)]
    assert not dec.empty
    assert (dec["value_eur_mn"] < 0).all()
    year = df[(df["series_path"] == "Gesamt / Finanzierung Bundeshaushalt "
                                    "und Sondervermögen")]
    jan = float(year[year["period"] == pd.Timestamp("2024-01-31")]["value_eur_mn"].iloc[0])
    dec24 = float(year[year["period"] == pd.Timestamp("2024-12-31")]["value_eur_mn"].iloc[0])
    assert dec24 < jan < 0  # cumulative: December is the full year


@needs_xlsx
def test_instrument_wrappers_return_eur_millions():
    stock = readers.bund_stock_by_instrument()
    assert set(stock["section"]) == {"Instrumentenarten", "Nachrichtlich"}
    assert stock["series_path"].str.startswith("Nachrichtlich / Umlaufvolumen").any()
    assert stock["series_path"].str.startswith("Nachrichtlich / Eigenbestände").any()
    for frame in (readers.bund_gross_issuance_by_instrument(),
                  readers.bund_redemptions_by_instrument(),
                  readers.bund_interest_by_instrument()):
        assert set(frame["section"]) == {"Instrumentenarten"}
        assert "value_eur_mn" in frame.columns and not frame.empty


# -------------------------------------------------------------- Datenportal CSV

@needs_csv
@pytest.mark.parametrize("part", sorted(readers.CSV_SHEET))
def test_csv_matches_the_workbook_on_overlapping_series(part):
    csv = readers.datenportal_csv(part)
    xlsx = readers.datenportal(readers.CSV_SHEET[part])
    assert not csv.empty
    assert csv["period"].max() == xlsx["period"].max()

    checked = 0
    for label in ("Bundeshaushalt", "Bundesobligationen", "Euro"):
        for period in (pd.Timestamp("2005-12-31"), pd.Timestamp("2024-12-31")):
            a = csv[(csv["series_label"] == label) & (csv["period"] == period)]
            b = xlsx[(xlsx["series_label"] == label) & (xlsx["period"] == period)]
            if a.empty or b.empty:
                continue
            left, right = float(a["value_eur"].iloc[0]), float(b["value_eur"].iloc[0])
            assert abs(left - right) <= abs(right) * 0.001
            checked += 1
    assert checked >= 3


# ------------------------------------------------------- Kreditaufnahmebericht

@needs_kab_2025
def test_kreditaufnahmebericht_text_2025():
    text = readers.kreditaufnahmebericht_text(2025)
    assert "Nettokreditaufnahme" in text
    assert len(text) > 100_000


@needs_kab_2025
def test_annex_45_2025_parses_verzinsung_and_kap3205():
    df = readers.kreditaufnahmebericht_annex(2025, "4.5")
    assert set(df["table"]) == {"verzinsung", "kap3205"}
    assert df["year"].min() == 1996 and df["year"].max() == 2025

    total = df[(df["table"] == "verzinsung") & (df["series_label"] == "Insgesamt")]
    assert (total["value_eur_mn"] < 0).all()

    kap = df[df["table"] == "kap3205"]
    assert {"davon Zinsausgaben", "davon Zinseinnahmen"} <= set(kap["series_label"])

    # the annex and the Datenportal are the same publisher's same concept on a
    # slightly different perimeter: the 2024 total must agree to well under 1 %
    if (("BMF_DATENPORTAL", readers.DATENPORTAL_XLSX) in SNAPS):
        stock = readers.datenportal("rpgZinsen Gesamt")
        portal = float(stock[(stock["period"] == pd.Timestamp("2024-12-31"))
                             & (stock["series_path"] == "Gesamt / Finanzierung "
                                "Bundeshaushalt und Sondervermögen")]
                       ["value_eur_mn"].iloc[0])
        annex = float(total[total["year"] == 2024]["value_eur_mn"].iloc[0])
        assert abs(annex - portal) < abs(portal) * 0.01


@needs_kab_2025
def test_annex_410_2025_parses_the_financing_plan():
    df = readers.kreditaufnahmebericht_annex(2025, "4.10")
    assert not df.empty
    labels = set(df["label"])
    assert "Einnahmen aus Krediten (Bruttokreditaufnahme)*" in labels
    assert "Eigenbestandsaufbau" in labels
    assert "Nettokreditaufnahme" in labels

    nka = df[df["label"] == "Nettokreditaufnahme"].iloc[-1]
    assert nka["ist_eur"] > 0
    assert abs(nka["ist_eur"] - nka["soll_eur"] - nka["abweichung_eur"]) < 1.0

    brutto = df[df["item"] == "3.1"].iloc[0]
    tilgung = df[df["item"] == "3.3"].iloc[0]
    assert brutto["ist_eur"] > 0 > tilgung["ist_eur"]
