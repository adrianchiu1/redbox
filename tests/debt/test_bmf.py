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


def _kab_years() -> list[int]:
    return sorted(int(part) for (sid, part) in SNAPS
                  if sid == "BMF_KREDITAUFNAHMEBERICHT" and part.isdigit())


needs_kab_any = pytest.mark.skipif(
    not _kab_years(), reason="no Kreditaufnahmebericht snapshots")


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


def _top_level_sum_and_nka(df):
    """Annex-4.10 helper: (sum of the top-level 3.x 'Herleitung' items,
    Nettokreditaufnahme Ist) in EUR — the invariant checked below."""
    herleitung = df[df["group"].str.contains("Herleitung", na=False)]
    top = herleitung[(herleitung["item"].str.count(r"\.") == 1)
                     & (~herleitung["label"].str.lower().str.startswith("nettokredit"))]
    nka = herleitung[herleitung["label"].str.lower().str.startswith("nettokredit")]
    return float(top["ist_eur"].sum()), float(nka["ist_eur"].iloc[0])


@needs_kab_any
@pytest.mark.parametrize("year", _kab_years())
def test_annex_410_top_level_items_close_to_nka_for_every_parsing_edition(year):
    """DEBT_KICKOFF.md §14 DD-style closure: in every edition whose annex
    4.10 parses at all, the top-level items 3.1 ... 3.n of 'Herleitung der
    Nettokreditaufnahme' (including 3.1 gross, 3.3 redemptions negative, the
    Sondervermögen and Rücklage lines) must sum to the Nettokreditaufnahme
    Ist line to the euro -- this is what the 2023 correction-booking fix
    (wrapped labels, a 2-cell row for the blank-Soll 'Rückabwicklung' lines,
    and the label-after-figures reattachment) restores."""
    df = readers.kreditaufnahmebericht_annex(year, "4.10")
    if df.empty:
        pytest.skip(f"annex 4.10 does not parse for the {year} edition "
                    f"(see reports/debt_sources/bmf.md)")
    top_sum, nka = _top_level_sum_and_nka(df)
    assert abs(top_sum - nka) < 1.0, (
        f"{year}: top-level 3.x sum {top_sum/1e6:,.3f} EUR mn "
        f"!= Nettokreditaufnahme Ist {nka/1e6:,.3f} EUR mn")


@needs_kab_any
def test_annex_410_2023_closes_after_the_correction_booking_fix():
    """The 2023 edition introduced a "Rückabwicklung von Zuführungen an
    Sondervermögen" correction-booking row under several Sondervermögen items
    (following the Bundesverfassungsgericht ruling of 15 November 2023) that
    prints only Ist and Abweichung, leaving Soll blank rather than "0,00".
    Before the fix this 2-cell row was buffered rather than closed, which
    glued its text (and the *next* item's own label and figures) onto
    whatever line closed next -- e.g. the Ist of the real item 3.9 got
    attributed to a bogus "3.8.3" record, so item 3.9 never appeared and the
    top-level sum came out 40,600 EUR mn too high (67,777 vs the true 27,177)."""
    if not _have("BMF_KREDITAUFNAHMEBERICHT", "2023"):
        pytest.skip("no Kreditaufnahmebericht 2023 snapshot")
    df = readers.kreditaufnahmebericht_annex(2023, "4.10")
    assert not df.empty
    # every top-level item 3.1 ... 3.16 must be present exactly once, in
    # particular the three that used to be swallowed by the row before them
    top_items = set(df.loc[df["item"].str.count(r"\.") == 1, "item"])
    for item in ("3.9", "3.11", "3.13"):
        assert item in top_items, f"item {item} missing (swallowed by a neighbour)"
    top_sum, nka = _top_level_sum_and_nka(df)
    assert abs(nka / 1e6 - 27_176.573) < 0.001
    assert abs(top_sum - nka) < 1.0


@needs_kab_any
def test_bund_net_borrowing_annual_covers_2020_through_2025_and_earlier_years():
    s = readers.bund_net_borrowing_annual()
    have_2020_2025 = {y for y in range(2020, 2026) if _have("BMF_KREDITAUFNAHMEBERICHT", str(y))}
    assert have_2020_2025 <= set(s.index), (
        f"missing years: {have_2020_2025 - set(s.index)}")
    for year in have_2020_2025:
        assert s[year] > 0

    # every earlier edition in the store adds its own (narrower, coarser)
    # narrative-table Nettokreditaufnahme where no annex exists (2013-2019
    # have no chapter-4 annex before the 2019 typo fix / it not existing at
    # all before 2019; the note says which years and from which source)
    earlier_editions = [y for y in _kab_years() if y < 2020]
    if earlier_editions:
        assert s.index.min() <= min(earlier_editions)
        assert "note" in s.attrs and s.attrs["note"]


@needs_kab_any
def test_bund_interest_annual_agrees_across_editions_for_overlapping_years():
    """DEBT_KICKOFF.md §6.3/§14: annex 4.5 'Insgesamt' (Verzinsung) for a
    given year must be the same figure regardless of which later edition's
    annex it is read from -- it is settled history, not a revised estimate."""
    years = [y for y in (2023, 2024, 2025) if _have("BMF_KREDITAUFNAHMEBERICHT", str(y))]
    if len(years) < 2:
        pytest.skip("need at least two of the 2023/2024/2025 editions")
    series = {}
    for y in years:
        a = readers.kreditaufnahmebericht_annex(y, "4.5")
        tot = a[(a["table"] == "verzinsung") & (a["series_label"] == "Insgesamt")]
        series[y] = tot.set_index("year")["value_eur_mn"]
    base_year = years[0]
    for other in years[1:]:
        common = series[base_year].index.intersection(series[other].index)
        assert len(common) > 10
        diff = (series[base_year].reindex(common) - series[other].reindex(common)).abs()
        assert diff.max() == 0, (
            f"editions {base_year} and {other} disagree on years "
            f"{list(diff[diff > 0].index)}")
