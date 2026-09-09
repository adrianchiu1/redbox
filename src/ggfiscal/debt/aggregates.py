"""DD8 aggregate class-level layer: the ministry's / statistical office's own
instrument-type totals per country-year, standing in for the register
step of both chains until the per-security register exists (OQ-8), and
remaining afterwards as the official cross-check (V31, V39).

Table `debt_class_aggregates`, one row per
(iso3, year, instrument_class, sub_type, measure):

  measure ∈ stock_year_end        nominal outstanding at 31 Dec (net of the
                                  issuer's own book where the source nets it)
            stock_gross_umlauf    outstanding incl. the issuer's own holdings
            own_holdings          issuer's own book at 31 Dec (positive)
            gross_issuance        cash-year gross issuance
            redemptions           cash-year redemptions (positive)
            net_issuance          gross_issuance − redemptions (or the source's
                                  own net figure; notes say which)
            interest              interest paid in the year (positive), on
                                  the source's basis (notes)
            uplift_accrued        indexation uplift accrued in the year
  instrument_class: DD2 classes, plus `mixed` where the source does not
                    split (e.g. ONS gilts total), plus `out_of_register`
                    for the source's rows outside DD1 (loans, retail,
                    money-market borrowing) — kept because they are the
                    step-A bridge items.

Country modules: `aggregates_deu` (here), `aggregates_gbr`, `aggregates_fra`
each expose `class_aggregates(run_id) -> DataFrame` in this shape.
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Column

from ggfiscal.debt.model import GRADES, INSTRUMENT_CLASSES, ISO3
from ggfiscal.standardise.readers import latest_snapshots

MEASURES = ["stock_year_end", "stock_gross_umlauf", "own_holdings", "gross_issuance",
            "redemptions", "net_issuance", "interest", "uplift_accrued"]
AGG_CLASSES = INSTRUMENT_CLASSES + ["mixed", "out_of_register"]
COLUMNS = ["run_id", "iso3", "year", "instrument_class", "sub_type", "measure", "value_lcu_mn",
           "basis", "in_register", "source_id", "snapshot_sha256", "quality_grade", "notes"]

SCHEMA = pa.DataFrameSchema(
    {
        "run_id": Column(str),
        "iso3": Column(str, pa.Check.isin(ISO3)),
        "year": Column(int, pa.Check.in_range(1900, 2100)),
        "instrument_class": Column(str, pa.Check.isin(AGG_CLASSES)),
        "sub_type": Column(str),
        "measure": Column(str, pa.Check.isin(MEASURES)),
        "value_lcu_mn": Column(float, nullable=True),
        "basis": Column(str, nullable=True),
        "in_register": Column(bool),
        "source_id": Column(str),
        "snapshot_sha256": Column(str, nullable=True),
        "quality_grade": Column(str, pa.Check.isin(GRADES)),
        "notes": Column(str, nullable=True),
    },
    strict=True, coerce=True,
    unique=["iso3", "year", "instrument_class", "sub_type", "measure"],
)


def sha(source_id: str, part: str) -> str | None:
    e = latest_snapshots().get((source_id, part))
    return e["sha256"] if e else None


def row(run_id, iso3, year, klass, sub_type, measure, value, source_id, *, basis=None,
        in_register=True, sha256=None, grade="B", notes=None) -> dict:
    return {"run_id": run_id, "iso3": iso3, "year": int(year), "instrument_class": klass,
            "sub_type": sub_type, "measure": measure,
            "value_lcu_mn": None if value is None or pd.isna(value) else float(value),
            "basis": basis, "in_register": bool(in_register), "source_id": source_id,
            "snapshot_sha256": sha256, "quality_grade": grade, "notes": notes}


# ---------------------------------------------------------------- DEU (BMF)

# Instrumentenarten leaves of the BMF Datenportal trees (the labels are the
# last path component). Values: (instrument_class, sub_type, in_register).
DEU_LEAVES = {
    "10-jährige Bundesanleihen": ("fixed_bullet", "bund_10y", True),
    "15-/20-jährige Bundesanleihen": ("fixed_bullet", "bund_15_20y", True),
    "30-jährige Bundesanleihen": ("fixed_bullet", "bund_30y", True),
    "7-jährige Bundesanleihen": ("fixed_bullet", "bund_7y", True),
    "Bundesobligationen": ("fixed_bullet", "bobl", True),
    "Bundesschatzanweisungen": ("fixed_bullet", "schatz", True),
    "Unverzinsliche Schatzanweisungen des Bundes": ("bill", "bubill", True),
    "Inflationsindexierte Bundeswertpapiere": ("inflation_linked", "bund_bobl_ei", True),
    "Grüne Bundeswertpapiere": ("fixed_bullet", "bund_green", True),
    "Sonstige Bundeswertpapiere": ("other", "sonstige_bundeswertpapiere", True),
    "Anlage des WSF in Forderungen an den Bund nach § 26b Abs. 5 StFG": ("other", "wsf_zusatzemission", True),
    "Kredite aus Zusatzemissionen des Bundes für den WSF nach § 26b StFG": ("other", "wsf_zusatzemission_kredite", True),
    "Geldmarktgeschäfte zur Haushaltsfinanzierung": ("out_of_register", "geldmarkt", False),
    "Schuldscheindarlehen": ("out_of_register", "schuldschein", False),
    "Sonstige Kredite und Buchschulden": ("out_of_register", "sonstige_kredite", False),
}
DEU_PARENTS = {"Bundeswertpapiere", "Konventionelle Bundeswertpapiere", "Bundesanleihen",
               "Zusatzemissionen des Bundes"}


def _deu_leaf_frame(df: pd.DataFrame, december_only: bool) -> pd.DataFrame:
    d = df[df["section"] == "Instrumentenarten"].copy()
    d["label"] = d["series_path"].str.split(" / ").str[-1]
    if december_only:
        d = d[d["period"].dt.month == 12]
    d["year"] = d["period"].dt.year
    unknown = sorted(set(d["label"]) - set(DEU_LEAVES) - DEU_PARENTS)
    if unknown:
        raise KeyError(f"unmapped BMF instrument rows (extend DEU_LEAVES): {unknown}")
    d = d[d["label"].isin(DEU_LEAVES)]
    return d


def deu_class_aggregates(run_id: str) -> pd.DataFrame:
    from ggfiscal.debt.readers import bmf as B
    sha256 = sha("BMF_DATENPORTAL", "kredit_brutto_tilgung_zinsen_xlsx")
    rows: list[dict] = []
    specs = (
        ("stock_year_end", B.bund_stock_by_instrument, 1.0, "nominal, Kreditbestand (net of Eigenbestand)"),
        ("gross_issuance", B.bund_gross_issuance_by_instrument, 1.0, "cash year, year-to-date December"),
        ("redemptions", B.bund_redemptions_by_instrument, -1.0, "cash year, year-to-date December; sign flipped"),
        ("interest", B.bund_interest_by_instrument, -1.0,
         "Verzinsung: coupons, agio/disagio, Stückzinsen, uplift, net of interest income; sign flipped"),
    )
    for measure, fn, sign, note in specs:
        d = _deu_leaf_frame(fn(), december_only=True)
        for (year, label), g in d.groupby(["year", "label"]):
            klass, sub, in_reg = DEU_LEAVES[label]
            rows.append(row(run_id, "DEU", year, klass, sub, measure, sign * g["value_eur_mn"].sum(),
                            "BMF_DATENPORTAL", basis="cash" if measure != "stock_year_end" else "nominal",
                            in_register=in_reg, sha256=sha256, grade="B", notes=note))
    # net issuance per leaf = gross − redemptions
    df = pd.DataFrame(rows)
    piv = df.pivot_table(index=["year", "instrument_class", "sub_type"], columns="measure",
                         values="value_lcu_mn", aggfunc="first")
    for (year, klass, sub), r in piv.iterrows():
        if pd.notna(r.get("gross_issuance")) and pd.notna(r.get("redemptions")):
            rows.append(row(run_id, "DEU", year, klass, sub, "net_issuance",
                            r["gross_issuance"] - r["redemptions"], "BMF_DATENPORTAL", basis="cash",
                            in_register=DEU_LEAVES_BY_SUB[sub][2], sha256=sha256, grade="B",
                            notes="gross_issuance − redemptions (Datenportal); from 2025 not equal to Δstock (agio/disagio spreading)"))
    # The instrument tree sums to the WIDER Gesamt row ("Kredite … und
    # Mitfinanzierung Abwicklungsanstalten und KfW"); the Kreditaufnahme-
    # bericht totals (step A) are the NARROWER "Finanzierung Bundeshaushalt
    # und Sondervermögen". The difference — credit raised on behalf of the
    # FMS resolution agencies and KfW — is an out-of-register official item
    # so the step-A residual is not polluted by it.
    for measure, sheet, sign in (("interest", "rpgZinsen Gesamt", -1.0),
                                 ("gross_issuance", "rpgBruttokreditaufnahme Gesamt", 1.0),
                                 ("redemptions", "rpgTilgungen", -1.0)):
        g = B.datenportal(sheet)
        g = g[(g["level"] == 0) & (g["period"].dt.month == 12)]
        wide = g[g["series_path"].str.contains("Mitfinanzierung")].set_index(g[g["series_path"].str.contains("Mitfinanzierung")]["period"].dt.year)["value_eur_mn"]
        narrow = g[g["series_path"].str.contains("Finanzierung Bundeshaushalt und Sonderverm")].set_index(g[g["series_path"].str.contains("Finanzierung Bundeshaushalt und Sonderverm")]["period"].dt.year)["value_eur_mn"]
        for year in sorted(set(wide.index) & set(narrow.index)):
            rows.append(row(run_id, "DEU", year, "out_of_register", "mitfinanzierung_abwicklungsanstalten_kfw",
                            measure, sign * (float(narrow[year]) - float(wide[year])), "BMF_DATENPORTAL",
                            basis="cash", in_register=False, sha256=sha256, grade="B",
                            notes="narrower Gesamt (Finanzierung Bundeshaushalt und Sondervermögen) minus the wider "
                                  "Gesamt the instrument tree sums to (incl. Mitfinanzierung Abwicklungsanstalten und KfW)"))
    df = pd.DataFrame(rows)
    piv = df[df["sub_type"] == "mitfinanzierung_abwicklungsanstalten_kfw"].pivot_table(
        index="year", columns="measure", values="value_lcu_mn", aggfunc="first")
    for year, r in piv.iterrows():
        if pd.notna(r.get("gross_issuance")) and pd.notna(r.get("redemptions")):
            rows.append(row(run_id, "DEU", year, "out_of_register", "mitfinanzierung_abwicklungsanstalten_kfw",
                            "net_issuance", r["gross_issuance"] - r["redemptions"], "BMF_DATENPORTAL",
                            basis="cash", in_register=False, sha256=sha256, grade="B",
                            notes="narrower minus wider Gesamt, gross issuance − redemptions"))
    # memo: Umlaufvolumen (gross of own book) and Eigenbestände
    s = B.datenportal("rpgSchuldenstand")
    s = s[(s["section"] == "Nachrichtlich") & (s["period"].dt.month == 12)]
    for _, r in s.iterrows():
        path = r["series_path"].split(" / ")
        label, year = path[-1], r["period"].year
        if path[1] == "Umlaufvolumen" and len(path) == 2:
            rows.append(row(run_id, "DEU", year, "mixed", "umlaufvolumen_total", "stock_gross_umlauf",
                            r["value_eur_mn"], "BMF_DATENPORTAL", basis="nominal", sha256=sha256, grade="B",
                            notes="Umlaufvolumen: securities outstanding incl. the Bund's own holdings"))
        elif label == "Eigenbestände (Netto)":
            rows.append(row(run_id, "DEU", year, "mixed", "eigenbestand_netto", "own_holdings",
                            -r["value_eur_mn"], "BMF_DATENPORTAL", basis="nominal", sha256=sha256, grade="B",
                            notes="Finanzagentur own holdings (net), sign flipped to positive"))
    return pd.DataFrame(rows, columns=COLUMNS)


DEU_LEAVES_BY_SUB = {v[1]: v for v in DEU_LEAVES.values()}


# ------------------------------------------------------------------ all

def class_aggregates(run_id: str) -> pd.DataFrame:
    frames = [deu_class_aggregates(run_id)]
    for mod in ("aggregates_gbr", "aggregates_fra"):
        try:
            m = __import__(f"ggfiscal.debt.{mod}", fromlist=["class_aggregates"])
        except ImportError:
            continue
        frames.append(m.class_aggregates(run_id))
    out = pd.concat(frames, ignore_index=True)
    return SCHEMA.validate(out.sort_values(["iso3", "year", "instrument_class", "sub_type", "measure"])
                           .reset_index(drop=True))
