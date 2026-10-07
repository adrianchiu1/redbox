"""Stage ED0-ED2 (EU3_KICKOFF.md): the ITA/ESP/BEL debt routing, the new
source family and the two national readers (MEF composition CSV, Banco de
España Boletín table), on synthetic files — no snapshot needed."""

from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

from ggfiscal import config
from ggfiscal.debt import countries as C

EU3 = ("ITA", "ESP", "BEL")


def test_eu3_debt_routing():
    cfg = C.configured()
    for iso3 in EU3:
        assert iso3 in cfg
        assert C.builder(iso3, "aggregates", "class_aggregates") is not None
        assert C.builder(iso3, "official_totals", "official_totals") is not None
        assert C.builder(iso3, "register", "build") is None     # DD8 path until ED3
        assert cfg[iso3]["v31_official"]["kind"] == "eurostat_gd_f3"
    assert "USA" not in cfg     # UD0 has not run


def test_debt_eurostat_geo_follows_config():
    from ggfiscal.debt.families.eurostat_insee_oecd import eurostat_geo

    assert eurostat_geo() == {"FRA": "FR", "DEU": "DE", "ITA": "IT", "ESP": "ES", "BEL": "BE"}


def test_eu3_family_pull_ids():
    from ggfiscal.debt.families import eu3_offices as F

    assert F.mef_part("composizione",
                      "https://x/Composizione-dei-Titoli-di-Stato-in-Circolazione-al-31-dicembre-2025.csv"
                      ) == "composizione_2025_12"
    assert F.mef_part("scadenze", "https://x/a-al-28-febbraio-2026.csv") == "scadenze_2026_02"
    assert F.mef_part("x", "https://x/no-date.csv") is None


MEF_CSV = (
    "COMPOSIZIONE DEI TITOLI DI STATO;;;\r\n(in circolazione al 31 dicembre 2025);;;\r\n;;;\r\n"
    "Tipologia titolo;mln. Euro;%;\r\nBOT;144.464,83;5,33%;\r\nBTP;1.899.665,45;70,05%;\r\n"
    "di cui BTP Più;14.905,67;0,55%;\r\nTotale;2.044.130,28;100,00%;\r\n;;;\r\n"
    "Vita Media del Debito (anni);;;\r\n"
)


def test_mef_composition_parser(tmp_path):
    from ggfiscal.debt.aggregates_eu3 import mef_composition

    p = tmp_path / "c.csv"
    p.write_bytes(MEF_CSV.encode("latin-1"))
    df = mef_composition(p)
    assert list(df["label"]) == ["BOT", "BTP", "Totale"]          # "di cui" rows skipped
    assert df["value_eur_mn"].tolist() == [144464.83, 1899665.45, 2044130.28]
    p.write_bytes(MEF_CSV.replace("BOT;", "BOT nuovi;").encode("latin-1"))
    with pytest.raises(KeyError, match="unmapped MEF"):
        mef_composition(p)


def _be_zip(tmp_path):
    csv = ('"CÓDIGO DE LA SERIE",A1,A2\n"NÚMERO SECUENCIAL",1,2\n"ALIAS DE LA SERIE","x","y"\n'
           '"DESCRIPCIÓN DE LA SERIE","Estado","AAPP"\n'
           '"DESCRIPCIÓN DE LAS UNIDADES","Miles de euros","Miles de euros"\n'
           '"FRECUENCIA","MENSUAL","MENSUAL"\n'
           '"NOV 2025",100,"_"\n"DIC 2025",2000,300\n"FUENTE","",""\n"NOTAS","",""\n')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("be11b.csv", csv.encode("latin-1"))
    path = tmp_path / "be.zip"
    path.write_bytes(buf.getvalue())
    return path


def test_bde_reader(tmp_path, monkeypatch):
    from ggfiscal.debt.readers import bde

    path = _be_zip(tmp_path)
    monkeypatch.setattr(bde, "snap_path", lambda sid, part: path)
    bde.be_table.cache_clear()
    try:
        s = bde.be_series("be11b", "A1")
        assert list(s.index) == [pd.Timestamp("2025-11-30"), pd.Timestamp("2025-12-31")]
        assert s.tolist() == [100.0, 2000.0] and s.attrs["unit"] == "Miles de euros"
        assert bde.be_series("be11b", "A2").tolist() == [300.0]   # "_" is missing
        with pytest.raises(KeyError):
            bde.be_series("be11b", "ZZ")
    finally:
        bde.be_table.cache_clear()


def test_eu3_step_a_rows_name_their_reason():
    from ggfiscal.debt import intermediates as I

    for iso3 in EU3:
        rows = I._unavailable_rows(iso3, "interest", "A_cg_cash", [2024])
        assert rows[0]["value_lcu_mn"] is None and rows[0]["quality_grade"] == "D"
        assert "EU3_KICKOFF" in rows[0]["notes"] and rows[0]["item_source_id"] in config.sources()
