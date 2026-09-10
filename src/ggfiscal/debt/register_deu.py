"""DEU per-security register (DEBT_KICKOFF.md §3–§5, §14 DEU) from the
Bundesrepublik Deutschland – Finanzagentur files.

``build(run_id)`` returns the four canonical frames for iso3 ``DEU``:

===================== ===================================================
``debt_securities``   one row per code ever listed in the annual file, the
                      monthly file or the auction history (strips and the
                      Schuldscheindarlehen excluded, see below)
``debt_positions``    31 December 1995…2025 from ``einzelaufstellung_seit_1995``
                      (``office_annual``) plus the latest month-end of
                      ``umlaufende_monatsultimo`` (``office_snapshot``)
``debt_flows``        every auction / syndication since 1999 with its
                      ``retention`` twin (Marktpflegequote), plus a derived
                      ``redemption`` per matured security (grade B)
``debt_index_ratios`` every daily Index-Verhältniszahl of the three base-year
                      files, ``ratio_source='office'``
===================== ===================================================

All amounts are EUR millions. The office reports the whole 1995–1998 history in
euro already, converted at the irrevocable 1.95583 DEM/EUR — no row in these
files is denominated in DEM, so ``currency`` is ``EUR`` throughout except the
two ``Fremdwährungsanleihen``, which the office carries at their euro value at
issue (``currency='USD'``, the office's own conversion recorded in ``notes``).

Perimeter notes (DD1):

* **Strips are dropped.** ``Kapitalstrips`` / ``Zinsstrips`` blocks appear in
  the monthly file with empty nominal columns; the issuer's obligation is the
  underlying bond's.
* **Schuldscheindarlehen are dropped.** Their column-B code is ``SSD fällig
  {year}``, not an ISIN — they are loans, a step-A bridge item, not securities.
* **Retail paper is kept** as ``instrument_class='other'`` with a naming
  ``sub_type`` (Bundesschatzbriefe, Finanzierungsschätze, Tagesanleihe). DD1
  puts them outside the marketable register; keeping them here — and only here —
  is what makes Σ positions reproduce the office's own ``Summe`` row and the
  ministry's Umlaufvolumen exactly, and ``sub_type`` lets a consumer drop them.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from ggfiscal.debt.model import FLOWS, INDEX_RATIOS, POSITIONS, SECURITIES
from ggfiscal.debt.readers import finanzagentur as F

ISO3 = "DEU"
SOURCE_ID = F.SOURCE_ID
INDEX_REFERENCE = "EA_HICP_XT"
INDEX_LAG_MONTHS = 3.0
#: The FRN's terms string names a tenor, a reference and a spread; the office
#: publishes no fixing history for it, so interest stays DD10 not_computable.
FRN_REFERENCE = "EA_MM_3M"

# --------------------------------------------------------------- name parsing

#: '15.04.2046' -> Timestamp (the office's only date format in these files).
DATE_RE = F.DATE_RE
#: German decimal comma, e.g. KUPON '0,100' -> 0.1, '6,500' -> 6.5.
COUPON_RE = re.compile(r"^-?\d{1,3}(?:,\d+)?$")
#: KUPON of a floater, e.g. '3ME25' = 3-month EURIBOR + 25 bp.
FRN_TERMS_RE = re.compile(r"^(?P<tenor>\d+)(?P<unit>[MJ])(?P<ref>[A-Z]+)(?P<spread>\d+)$")
#: WERTPAPIERART tenor prefix, e.g. '30-jährige Bundesanleihen' -> 30.
TENOR_RE = re.compile(r"^(\d+)(?:-|/)?.*?j(?:ä|ae)hrige", re.IGNORECASE)
#: Auktionsergebnisse Laufzeitsegment, e.g. '10 J', '6 M'.
SEGMENT_RE = re.compile(r"^(\d+)\s*([JM])$")
#: Column-B codes of the Wertpapierliste that are not ISINs.
ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def parse_coupon(raw: str | None) -> tuple[float | None, str | None, float | None]:
    """KUPON cell -> (coupon_pct, floating_reference, spread_bp).

    ``'6,500'`` -> ``(6.5, None, None)``; ``'3ME25'`` -> ``(None, 'EA_MM_3M',
    25.0)``; blank -> ``(None, None, None)``.
    """
    if raw in (None, ""):
        return None, None, None
    text = str(raw).strip()
    if COUPON_RE.match(text):
        return float(text.replace(",", ".")), None, None
    m = FRN_TERMS_RE.match(text)
    if m:
        return None, FRN_REFERENCE, float(m.group("spread"))
    return None, None, None


def dividend_dates(maturity: pd.Timestamp | None) -> str | None:
    """German federal bonds pay annually on the maturity anniversary, so the
    dividend date is the maturity day/month: 15.02.2036 -> ``'15 Feb'``
    (the format :func:`ggfiscal.debt.interest.parse_dividend_dates` reads)."""
    if maturity is None or pd.isna(maturity):
        return None
    return f"{maturity.day:02d} {MONTH_ABBR[maturity.month - 1]}"


# --------------------------------------------------------- instrument mapping

#: WERTPAPIERART -> (instrument_class, sub_type, is_green, currency, issuer_unit).
#: Every label of both Wertpapierliste parts is listed; an unmapped label raises
#: rather than being silently dropped.
WERTPAPIERART = {
    "30-jährige inflationsindexierte Anleihen des Bundes":
        ("inflation_linked", "bund_ei", False, "EUR", "state"),
    "10-jährige inflationsindexierte Anleihen des Bundes":
        ("inflation_linked", "bund_ei", False, "EUR", "state"),
    "Inflationsindexierte Obligationen des Bundes":
        ("inflation_linked", "bobl_ei", False, "EUR", "state"),
    "30-jährige Grüne Bundesanleihen": ("fixed_bullet", "bund_green", True, "EUR", "state"),
    "20-jährige Grüne Bundesanleihen": ("fixed_bullet", "bund_green", True, "EUR", "state"),
    "15-jährige Grüne Bundesanleihen": ("fixed_bullet", "bund_green", True, "EUR", "state"),
    "10-jährige Grüne Bundesanleihen": ("fixed_bullet", "bund_green", True, "EUR", "state"),
    "7-jährige Grüne Bundesanleihen": ("fixed_bullet", "bund_green", True, "EUR", "state"),
    "Grüne Bundesobligationen": ("fixed_bullet", "bund_green", True, "EUR", "state"),
    "Grüne Bundesschatzanweisungen": ("fixed_bullet", "bund_green", True, "EUR", "state"),
    "30-jährige Bundesanleihen": ("fixed_bullet", "bund", False, "EUR", "state"),
    "20-jährige Bundesanleihen": ("fixed_bullet", "bund", False, "EUR", "state"),
    "15-jährige Bundesanleihen": ("fixed_bullet", "bund", False, "EUR", "state"),
    "10-jährige Bundesanleihen": ("fixed_bullet", "bund", False, "EUR", "state"),
    "7-jährige Bundesanleihen": ("fixed_bullet", "bund", False, "EUR", "state"),
    "Bundesobligationen": ("fixed_bullet", "bobl", False, "EUR", "state"),
    "Bundesschatzanweisungen": ("fixed_bullet", "schatz", False, "EUR", "state"),
    "Unverzinsliche Schatzanweisungen (06M)": ("bill", "bubill", False, "EUR", "state"),
    "Unverzinsliche Schatzanweisungen (12M)": ("bill", "bubill", False, "EUR", "state"),
    # two-year discount paper funding the Bund's share in the Liquiditäts-
    # Konsortialbank: a bill by name, but > 1 year at issue, so DD2 `other`.
    "Unverzinsliche Schatzanweisung (Likobank, 2J.)":
        ("other", "uschatz_likobank_2j", False, "EUR", "state"),
    "Variabel verzinsliche Anleihe": ("floating", "bund_frn", False, "EUR", "state"),
    "Fremdwährungsanleihe": ("fixed_bullet", "bund_usd", False, "USD", "state"),
    "Bund-Länder-Anleihe (Gesamtemission)":
        ("fixed_bullet", "bund_laender_gesamtemission", False, "EUR", "joint:bund_and_laender"),
    "Bundesschatzbriefe Typ A": ("other", "bundesschatzbrief_a", False, "EUR", "state"),
    "Bundesschatzbriefe Typ B": ("other", "bundesschatzbrief_b", False, "EUR", "state"),
    "Finanzierungsschätze (1J)": ("other", "finanzierungsschatz_1j", False, "EUR", "state"),
    "Finanzierungsschätze (2J)": ("other", "finanzierungsschatz_2j", False, "EUR", "state"),
    "Tagesanleihe des Bundes": ("other", "tagesanleihe", False, "EUR", "state"),
}
#: Blocks dropped from the register (DD1): strips are not separate securities;
#: Schuldscheindarlehen are loans and carry no ISIN.
DROP_WERTPAPIERART = {
    "30-jährige Kapitalstrips", "20-jährige Kapitalstrips", "15-jährige Kapitalstrips",
    "10-jährige Kapitalstrips", "7-jährige Kapitalstrips", "Kapitalstrips", "Zinsstrips",
    "Schuldscheindarlehen des Bundes",
}
#: sub_types outside the DD1 marketable perimeter, kept so Σ positions matches
#: the office's Summe row; consumers filter on this set.
NON_MARKETABLE_SUB_TYPES = {
    "bundesschatzbrief_a", "bundesschatzbrief_b",
    "finanzierungsschatz_1j", "finanzierungsschatz_2j", "tagesanleihe",
}

#: Auktionsergebnisse ``Anleihe`` label -> (instrument_class, sub_type, is_green,
#: currency). Used only for ISINs that never reach a Wertpapierliste as-of date
#: (mostly Bubills issued and redeemed inside one calendar year).
ANLEIHE = {
    "Bund": ("fixed_bullet", "bund", False, "EUR"),
    "Bobl": ("fixed_bullet", "bobl", False, "EUR"),
    "Schatz": ("fixed_bullet", "schatz", False, "EUR"),
    "Bubill": ("bill", "bubill", False, "EUR"),
    "ILB": ("inflation_linked", "bund_ei", False, "EUR"),
    "Green": ("fixed_bullet", "bund_green", True, "EUR"),
    "USD-Bond": ("fixed_bullet", "bund_usd", False, "USD"),
}

DEM_NOTE = (f"office reports 1995-1998 nominals in euro, converted at the irrevocable "
            f"{F.DEM_PER_EUR} DEM/EUR")
USD_NOTE = ("Fremdwährungsanleihe: nominal carried at the office's own euro value "
            "(USD nominal / the fixing at issue); no fx rate is published in the file")


def _provenance(run_id: str, part: str, grade: str = "A", notes: str | None = None) -> dict:
    return {"run_id": run_id, "source_id": SOURCE_ID, "snapshot_sha256": F.sha(part),
            "quality_grade": grade, "notes": notes}


# ------------------------------------------------------------------ securities

def _wertpapierliste_terms() -> pd.DataFrame:
    """The union of both Wertpapierliste parts, one row per code, monthly file
    first (its terms are the current ones)."""
    frames = []
    for part in (F.MONTHLY_PART, F.ANNUAL_PART):
        if F.have(part):
            frames.append(F.wertpapierliste_securities(part).assign(part=part))
    if not frames:
        raise FileNotFoundError("no Finanzagentur Wertpapierliste snapshot")
    df = pd.concat(frames, ignore_index=True)
    df = df[~df["wertpapierart"].isin(DROP_WERTPAPIERART)]
    df = df[df["isin"].str.match(ISIN_RE)]
    unknown = sorted(set(df["wertpapierart"]) - set(WERTPAPIERART))
    if unknown:
        raise KeyError(f"unmapped Finanzagentur WERTPAPIERART (extend WERTPAPIERART): {unknown}")
    return df.drop_duplicates("isin", keep="first").reset_index(drop=True)


def _auction_terms() -> pd.DataFrame:
    """One row per ISIN in the auction history: first operation date, maturity,
    coupon and the office's own instrument label."""
    au = F.auktionen()
    au = au[au["isin"].str.match(ISIN_RE)]
    g = au.sort_values("termin").groupby("isin")
    return pd.DataFrame({
        "first_auction": g["termin"].first(),
        "maturity_auction": g["laufzeit"].first(),
        "coupon_auction": g["kupon_frac"].apply(lambda s: s.dropna().iloc[0] * 100.0
                                                if s.notna().any() else np.nan),
        "anleihe": g["anleihe"].first(),
        "segment": g["laufzeitsegment"].first(),
    }).reset_index()


def securities(run_id: str) -> pd.DataFrame:
    terms = _wertpapierliste_terms()
    au = _auction_terms()
    listed = set(terms["isin"])

    rows: list[dict] = []
    for r in terms.itertuples(index=False):
        klass, sub, green, ccy, unit = WERTPAPIERART[r.wertpapierart]
        coupon, fref, spread = parse_coupon(r.kupon_raw)
        rows.append({
            "security_id": r.isin, "isin": r.isin, "wertpapierart": r.wertpapierart,
            "instrument_class": klass, "sub_type": sub, "currency": ccy,
            "coupon_pct": coupon, "floating_reference": fref, "spread_bp": spread,
            "first_issue_date": r.first_issue_date, "maturity_date": r.maturity_date,
            "is_green": green, "issuer_unit": unit, "part": r.part, "from_auction_only": False,
        })
    for r in au[~au["isin"].isin(listed)].itertuples(index=False):
        klass, sub, green, ccy = ANLEIHE[r.anleihe]
        if r.anleihe == "ILB" and (r.segment or "").startswith(("5", "7")):
            sub = "bobl_ei"
        rows.append({
            "security_id": r.isin, "isin": r.isin,
            "wertpapierart": f"{r.anleihe} ({r.segment})",
            "instrument_class": klass, "sub_type": sub, "currency": ccy,
            "coupon_pct": None if pd.isna(r.coupon_auction) else float(r.coupon_auction),
            "floating_reference": None, "spread_bp": None,
            "first_issue_date": r.first_auction, "maturity_date": r.maturity_auction,
            "is_green": green, "issuer_unit": "state",
            "part": F.AUCTION_PARTS[0], "from_auction_only": True,
        })

    df = pd.DataFrame(rows)
    # coupon fallback: the auction history's Kupon column for pre-listed terms
    fallback = au.set_index("isin")["coupon_auction"]
    filled = df["security_id"].map(fallback)
    from_auction = df["coupon_pct"].isna() & filled.notna() & (df["instrument_class"] != "floating")
    df.loc[from_auction, "coupon_pct"] = filled[from_auction]

    ratio_terms = (F.index_ratios()[1] if any(F.have(p) for p in F.RATIO_PARTS)
                   else pd.DataFrame())
    # The Basisindex is restated on every HICP rebasing. Take the FIRST file
    # that lists the ISIN, so `base_index` is on the same base as the earliest
    # `reference_index` stored for it in debt_index_ratios; the other bases go
    # into the security's notes.
    base = (ratio_terms.drop_duplicates("isin", keep="first").set_index("isin")["base_index"]
            if len(ratio_terms) else pd.Series(dtype=float))
    all_bases: dict[str, str] = {}
    if len(ratio_terms):
        for isin, g in ratio_terms.groupby("isin"):
            all_bases[isin] = ", ".join(f"{r.part}: {r.base_index:g}" for r in
                                        g.itertuples(index=False) if pd.notna(r.base_index))
    df["base_note"] = df["security_id"].map(all_bases)
    linker = df["instrument_class"] == "inflation_linked"

    out = pd.DataFrame({
        "iso3": ISO3,
        "security_id": df["security_id"],
        "isin": df["isin"],
        "name": [_name(r) for r in df.itertuples(index=False)],
        "instrument_class": df["instrument_class"],
        "sub_type": df["sub_type"],
        "currency": df["currency"],
        "coupon_pct": df["coupon_pct"],
        # German federal bonds pay one annual coupon; the FRN pays quarterly.
        # The schema coerces to int64, so bills and the coupon-less retail paper
        # carry the nominal 1 they never use (the engine short-circuits on class).
        "coupon_frequency": np.where(df["instrument_class"] == "floating", 4, 1),
        "day_count": np.where(df["instrument_class"] == "bill", "ACT/360", "ACT/ACT"),
        "first_issue_date": df["first_issue_date"],
        "maturity_date": df["maturity_date"],
        "first_call_date": pd.NaT,
        "dividend_dates": [dividend_dates(m) if c is not None and pd.notna(c) else None
                           for m, c in zip(df["maturity_date"], df["coupon_pct"])],
        "index_reference": np.where(linker, INDEX_REFERENCE, None),
        "index_lag_months": np.where(linker, INDEX_LAG_MONTHS, np.nan),
        "base_index": np.where(linker, df["security_id"].map(base), np.nan),
        "floating_reference": df["floating_reference"],
        "spread_bp": df["spread_bp"],
        "is_green": df["is_green"],
        "issuer_unit": df["issuer_unit"],
        "run_id": run_id,
        "source_id": SOURCE_ID,
        "snapshot_sha256": df["part"].map(lambda p: F.sha(p)),
        "quality_grade": "A",
        "notes": [_security_note(r) for r in df.itertuples(index=False)],
    })
    out = out.drop_duplicates("security_id").sort_values("security_id").reset_index(drop=True)
    return SECURITIES.validate(out)


def _name(r) -> str:
    """The office publishes no per-security name, only the block label plus the
    KUPON / FÄLLIGKEIT columns; the name is composed from them."""
    bits = [r.wertpapierart]
    if r.coupon_pct is not None and pd.notna(r.coupon_pct):
        bits.append(f"{float(r.coupon_pct):.3f}%".replace(".000%", "%"))
    if pd.notna(r.maturity_date):
        bits.append(pd.Timestamp(r.maturity_date).strftime("%d.%m.%Y"))
    return " ".join(bits)


def _security_note(r) -> str | None:
    notes = []
    if getattr(r, "base_note", None):
        notes.append(f"Basisindex per base-year file ({r.base_note}); the base_index column "
                     "carries the earliest, matching the reference index stored with its ratios")
    if r.from_auction_only:
        notes.append("terms from the auction history only: never outstanding at a listed as-of date")
    if r.currency == "USD":
        notes.append(USD_NOTE)
    if pd.notna(r.first_issue_date) and pd.Timestamp(r.first_issue_date).year < 1999:
        notes.append(DEM_NOTE)
    if r.sub_type in NON_MARKETABLE_SUB_TYPES:
        notes.append("non-marketable retail paper: outside the DD1 register perimeter, "
                     "kept so Σ positions reproduces the office's Summe row")
    if r.instrument_class == "floating":
        notes.append("no official fixing history published for this security (DD10)")
    return "; ".join(notes) or None


# ------------------------------------------------------------------- positions

def positions(run_id: str, secs: pd.DataFrame) -> pd.DataFrame:
    known = set(secs["security_id"])
    frames = []
    if F.have(F.ANNUAL_PART):
        a = F.wertpapierliste(F.ANNUAL_PART)
        frames.append(a.assign(position_type="office_annual", part=F.ANNUAL_PART))
    if F.have(F.MONTHLY_PART):
        m = F.wertpapierliste(F.MONTHLY_PART)
        m = m[m["as_of"] == m["as_of"].max()]
        frames.append(m.assign(position_type="office_snapshot", part=F.MONTHLY_PART))
    df = pd.concat(frames, ignore_index=True)
    df = df[df["isin"].isin(known)]
    # the monthly file repeats year-ends the annual file already carries
    df = df.drop_duplicates(["isin", "as_of"], keep="first")

    ratio = _ratio_lookup()
    linker = secs.set_index("security_id")["instrument_class"] == "inflation_linked"
    is_linker = df["isin"].map(linker).fillna(False)
    ir = pd.Series([ratio.get((i, d)) for i, d in zip(df["isin"], df["as_of"])], index=df.index)

    out = pd.DataFrame({
        "iso3": ISO3,
        "security_id": df["isin"],
        "as_of": df["as_of"],
        "nominal_lcu_mn": df["nominal_eur"] / 1e6,
        "nominal_uplifted_lcu_mn": np.where(is_linker & ir.notna(),
                                            df["nominal_eur"] / 1e6 * ir.fillna(1.0), np.nan),
        "nominal_issue_ccy_mn": np.nan,
        "official_holdings_lcu_mn": np.nan,
        "market_hands_lcu_mn": np.nan,
        "position_type": df["position_type"],
        "fx_rate": np.nan,
        "fx_source_id": None,
        "run_id": run_id,
        "source_id": SOURCE_ID,
        "snapshot_sha256": df["part"].map(lambda p: F.sha(p)),
        "quality_grade": "A",
        "notes": np.where(
            is_linker & ir.notna(),
            "Umlauf incl. the Bund's own book (Eigenbestand); uplifted at the office index ratio; "
            "no per-ISIN Eigenbestand is published",
            "Umlauf incl. the Bund's own book (Eigenbestand); no per-ISIN Eigenbestand is published"),
    })
    return POSITIONS.validate(out.sort_values(["security_id", "as_of"]).reset_index(drop=True))


def _ratio_lookup() -> dict:
    if not any(F.have(p) for p in F.RATIO_PARTS):
        return {}
    ratios, _ = F.index_ratios()
    return dict(zip(zip(ratios["isin"], ratios["date"]), ratios["index_ratio"]))


# ----------------------------------------------------------------------- flows

def flows(run_id: str, secs: pd.DataFrame, pos: pd.DataFrame) -> pd.DataFrame:
    known = set(secs["security_id"])
    au = F.auktionen()
    au = au[au["isin"].isin(known)].copy()

    rows: list[dict] = []
    for r in au.itertuples(index=False):
        volume = r.emissionsvolumen_mn
        allotted = r.zuteilung_mn
        retained = r.marktpflegequote_mn
        if volume is None or pd.isna(volume):
            volume = (0.0 if allotted is None or pd.isna(allotted) else allotted) + \
                     (0.0 if retained is None or pd.isna(retained) else retained)
        price = r.durchschnittskurs
        cash = (allotted * price / 100.0
                if allotted is not None and pd.notna(allotted) and pd.notna(price) else None)
        method = f"{r.verfahren} ({F.VERFAHREN.get(r.verfahren, r.verfahren)}); " \
                 f"Typ {r.typ}" if r.verfahren else None
        wedge = None
        if all(v is not None and pd.notna(v) for v in (allotted, retained)) and \
                abs(volume - allotted - retained) > 0.05:
            wedge = (f"Emissionsvolumen {volume:,.2f} != Zuteilung {allotted:,.2f} + "
                     f"Marktpflegequote {retained:,.2f} as published")
        rows.append({
            "security_id": r.isin,
            "settlement_date": r.termin, "operation_date": r.termin,
            "flow_type": "syndication" if r.verfahren == "Syn" else "auction",
            "nominal_lcu_mn": float(volume), "cash_lcu_mn": cash,
            "price_pct": price, "yield_pct": r.durchschnittsrendite, "method": method,
            "grade": "A",
            "notes": "; ".join(x for x in [
                "nominal = Emissionsvolumen (Zuteilung + Marktpflegequote); the office publishes "
                "the bidding day (Termin), not the Valuta, so settlement_date = operation_date",
                ("negative Emissionsvolumen as published: an own-book placement reversed"
                 if float(volume) < 0 else None),
                wedge] if x),
        })
        if retained is not None and pd.notna(retained) and retained != 0:
            rows.append({
                "security_id": r.isin,
                "settlement_date": r.termin, "operation_date": r.termin,
                "flow_type": "retention", "nominal_lcu_mn": float(retained),
                "cash_lcu_mn": None, "price_pct": None, "yield_pct": None, "method": method,
                "grade": "A",
                "notes": "Marktpflegequote: the tranche retained in the Bund's own book at the "
                         "operation; a memo leg of the auction above, not an extra increment",
            })

    rows.extend(_redemptions(secs, pos, au))

    df = pd.DataFrame(rows)
    df["seq"] = df.groupby(["security_id", "settlement_date", "flow_type"]).cumcount()
    out = pd.DataFrame({
        "iso3": ISO3,
        "security_id": df["security_id"],
        "settlement_date": df["settlement_date"],
        "flow_type": df["flow_type"],
        "seq": df["seq"],
        "operation_date": df["operation_date"],
        "nominal_lcu_mn": df["nominal_lcu_mn"],
        "cash_lcu_mn": df["cash_lcu_mn"],
        "price_pct": df["price_pct"],
        "yield_pct": df["yield_pct"],
        "method": df["method"],
        "counter_security_id": None,
        "run_id": run_id,
        "source_id": SOURCE_ID,
        "snapshot_sha256": F.sha(F.AUCTION_PARTS[0]),
        "quality_grade": df["grade"],
        "notes": df["notes"],
    })
    return FLOWS.validate(
        out.sort_values(["settlement_date", "security_id", "flow_type", "seq"]).reset_index(drop=True))


def _redemptions(secs: pd.DataFrame, pos: pd.DataFrame, au: pd.DataFrame) -> list[dict]:
    """One `redemption` per matured security (DD13: a position difference, so
    grade B and the derivation is in `notes`). The office publishes no
    redemption file; the amount is the last positive listed nominal before
    maturity, or — for paper that never reached a listed as-of date — the sum of
    its issue volumes."""
    coverage_end = pos["as_of"].max()
    last = (pos[pos["nominal_lcu_mn"] > 0].sort_values("as_of")
            .groupby("security_id").agg(as_of=("as_of", "last"),
                                        nominal=("nominal_lcu_mn", "last")))
    issued = au.groupby("isin")["emissionsvolumen_mn"].sum()
    out: list[dict] = []
    for r in secs.itertuples(index=False):
        mat = r.maturity_date
        if pd.isna(mat) or mat > coverage_end:
            continue
        if r.security_id in last.index:
            row = last.loc[r.security_id]
            if row["as_of"] >= mat:
                continue                                  # still listed after maturity
            amount, why = float(row["nominal"]), (
                f"derived from the position: last listed nominal {row['as_of']:%Y-%m-%d}")
        elif r.security_id in issued.index and pd.notna(issued[r.security_id]):
            amount, why = float(issued[r.security_id]), (
                "derived from Σ issue volumes: never outstanding at a listed as-of date")
        else:
            continue
        if amount == 0:
            continue
        out.append({
            "security_id": r.security_id, "settlement_date": mat, "operation_date": mat,
            "flow_type": "redemption", "nominal_lcu_mn": amount, "cash_lcu_mn": None,
            "price_pct": None, "yield_pct": None, "method": None, "grade": "B",
            "notes": "the Finanzagentur publishes no redemption file; " + why,
        })
    return out


# ----------------------------------------------------------------- index ratios

def index_ratios(run_id: str, secs: pd.DataFrame) -> pd.DataFrame:
    ratios, _ = F.index_ratios()
    known = set(secs["security_id"])
    r = ratios[ratios["isin"].isin(known)]
    out = pd.DataFrame({
        "iso3": ISO3,
        "security_id": r["isin"],
        "date": r["date"],
        "reference_index": r["reference_index"],
        "index_ratio": r["index_ratio"],
        "ratio_source": "office",
        "run_id": run_id,
        "source_id": SOURCE_ID,
        "snapshot_sha256": r["base_year_file"].map(lambda p: F.sha(p)),
        "quality_grade": "A",
        "notes": r["base_year_file"].map(
            lambda p: f"{p}: daily reference index on that file's HICP base year; the ratios are "
                      "continuous across the files, the reference index rebases"),
    })
    return INDEX_RATIOS.validate(out.sort_values(["security_id", "date"]).reset_index(drop=True))


# ----------------------------------------------------------------------- build

def build(run_id: str) -> dict[str, pd.DataFrame]:
    secs = securities(run_id)
    pos = positions(run_id, secs)
    fl = flows(run_id, secs, pos)
    ratios = index_ratios(run_id, secs)
    return {"debt_securities": secs, "debt_positions": pos,
            "debt_flows": fl, "debt_index_ratios": ratios}


# -------------------------------------------------------------- reconciliation

#: `debt_class_aggregates` measures the register is reconciled against (§8, V31).
AGGREGATES_CSV = "data/canonical/debt_class_aggregates.csv"


def class_aggregates(run_id: str | None = None) -> pd.DataFrame:
    """The DEU rows of the aggregate layer — the canonical file when it exists,
    otherwise recomputed from the BMF snapshots."""
    from ggfiscal import config

    path = config.repo_root() / AGGREGATES_CSV
    if path.exists():
        df = pd.read_csv(path)
        return df[df["iso3"] == ISO3].copy()
    from ggfiscal.debt.aggregates import deu_class_aggregates
    return deu_class_aggregates(run_id or "RECON")


def eigenbestand_year_end() -> pd.Series:
    """The office's own-book holdings at each 31 December, EUR mn, positive.

    From ``schuldenbericht`` sheet ``rpgUmlaufvolumen``, whose ``Eigenbestand``
    block is signed negative and is published **by instrument group only** —
    there is no per-ISIN Eigenbestand in any Finanzagentur file, which is why
    ``debt_positions.official_holdings_lcu_mn`` is null throughout."""
    u = F.umlaufvolumen()
    top = u[(u["block"] == "Eigenbestand") & (u["level"] == 0)]
    dec = top[top["period"].dt.month == 12]
    return pd.Series(dec["value_eur_mn"].abs().values,
                     index=dec["period"].dt.year.values).sort_index()


def reconciliation(run_id: str, tables: dict[str, pd.DataFrame] | None = None) -> dict[str, pd.DataFrame]:
    """Register vs the aggregate layer, per year (§8, V31, V39).

    ``stock``   Σ 31 Dec nominal by year against the ministry's Umlaufvolumen
                (``stock_gross_umlauf``, gross of the own book) and, net of the
                office's aggregate Eigenbestand, against Σ ``stock_year_end``
                over the in-register BMF leaves (the Kreditbestand).
    ``by_class``Σ 31 Dec nominal per DD2 class and year.
    ``issuance`` Σ auction + syndication nominal per year against Σ
                ``gross_issuance`` over the in-register leaves, with the
                retained tranche shown separately.
    """
    t = tables or build(run_id)
    pos, fl = t["debt_positions"], t["debt_flows"]
    agg = class_aggregates(run_id)

    ye = pos[pos["position_type"] == "office_annual"].copy()
    ye["year"] = ye["as_of"].dt.year
    by_class = (ye.merge(t["debt_securities"][["security_id", "instrument_class", "sub_type"]],
                         on="security_id")
                .groupby(["year", "instrument_class"], as_index=False)
                .agg(nominal_lcu_mn=("nominal_lcu_mn", "sum"), n_securities=("security_id", "nunique")))

    umlauf = agg[agg["measure"] == "stock_gross_umlauf"].set_index("year")["value_lcu_mn"]
    kredit = (agg[(agg["measure"] == "stock_year_end") & agg["in_register"]]
              .groupby("year")["value_lcu_mn"].sum())
    gross = (agg[(agg["measure"] == "gross_issuance") & agg["in_register"]]
             .groupby("year")["value_lcu_mn"].sum())
    eb = eigenbestand_year_end()

    reg = ye.groupby("year")["nominal_lcu_mn"].sum()
    n_sec = ye[ye["nominal_lcu_mn"] > 0].groupby("year")["security_id"].nunique()
    stock = pd.DataFrame({
        "register_nominal_lcu_mn": reg,
        "official_umlaufvolumen_lcu_mn": umlauf,
        "ratio_nominal_over_umlauf": reg / umlauf,
        "office_eigenbestand_lcu_mn": eb,
        "register_market_hands_lcu_mn": reg - eb,
        "official_kreditbestand_lcu_mn": kredit,
        "ratio_market_hands_over_kreditbestand": (reg - eb) / kredit,
        "n_securities": n_sec,
    }).sort_index()
    stock.index.name = "year"

    iss = fl[fl["flow_type"].isin(["auction", "syndication"])].copy()
    ret = fl[fl["flow_type"] == "retention"].copy()
    iss["year"] = iss["settlement_date"].dt.year
    ret["year"] = ret["settlement_date"].dt.year
    gi = iss.groupby("year")["nominal_lcu_mn"].sum()
    gr = ret.groupby("year")["nominal_lcu_mn"].sum().reindex(gi.index).fillna(0.0)
    issuance = pd.DataFrame({
        "register_issue_volume_lcu_mn": gi,
        "register_retained_lcu_mn": gr,
        "register_allotted_lcu_mn": gi - gr,
        "official_gross_issuance_lcu_mn": gross,
        "ratio_issue_volume_over_official": gi / gross,
        "ratio_allotted_over_official": (gi - gr) / gross,
        "n_operations": iss.groupby("year").size(),
    }).sort_index()
    issuance.index.name = "year"

    return {"stock": stock.reset_index(), "by_class": by_class,
            "issuance": issuance.reset_index()}
