"""ITA / ESP / BEL aggregate class-level layer (DD8, `debt_class_aggregates`
per `ggfiscal.debt.aggregates`; EU3_KICKOFF.md Stage ED1–ED2, D-S17-007).

Every country takes the FRA method's Eurostat leg: Q4 observations of
`gov_10q_ggdebt` for the central-government subsector S1311 by ESA
instrument (F31 short-term securities -> `bill`, F32 long-term securities
-> `mixed`, F4 loans and F2 deposits `out_of_register`) with the S13
securities rows as the wider-perimeter cross-check, and Δ Q4 stock as the
net figure of the two securities lines. On top, each country's own office
or central bank where it publishes a year-end figure:

* **ITA** — the MEF "Composizione dei Titoli di Stato in circolazione"
  editions, by instrument class (`ITA_MEF_COMPOSIZIONE`): December
  editions only, so year-end rows accumulate as the store gains them (the
  listing carries the current year's months; older editions are PDF).
* **ESP** — the Banco de España Boletín Estadístico, chapter 11 table 11b
  (`ESP_BDE_BE`, DE4): the Estado's PDE debt in December (all
  instruments; `mixed`, out of register — the securities split is the
  Eurostat leg).
* **BEL** — the Belgian Debt Agency's OLO lines (`BEL_BDA`) are a
  point-in-time register (Stage ED3); no year-end class aggregate is
  published as a file, so BEL rests on the Eurostat leg here.

No `interest` rows: no reachable source splits these countries' interest
by instrument class (the chains' step B is Eurostat S1311 D.41).
"""

from __future__ import annotations

import pandas as pd

from ggfiscal.debt.aggregates import COLUMNS, row, sha

EUROSTAT_SOURCE = "EUROSTAT_GOV10DD"

EUROSTAT_ITEMS: dict[str, tuple[str, str, bool]] = {
    "F31": ("bill", "f31_short_term_securities", True),
    "F32": ("mixed", "f32_long_term_securities", True),
    "F4": ("out_of_register", "f4_loans", False),
    "F2": ("out_of_register", "f2_currency_deposits", False),
}
EUROSTAT_S13_ITEMS: dict[str, tuple[str, str, bool]] = {
    "F31": ("bill", "f31_short_term_securities_s13", False),
    "F32": ("mixed", "f32_long_term_securities_s13", False),
}
PERIMETER_NOTE = {
    "ITA": "sector S1311 central government (State plus central agencies)",
    "ESP": "sector S1311 central government (Estado plus Organismos de la Administración central)",
    "BEL": "sector S1311 central government (federal State; the communities and regions are S1312)",
}
_ESA_NOTE = ("ESA 2010 instrument class, Maastricht gross debt at face value, "
             "Eurostat gov_10q_ggdebt, Q4 observation")
_S13_NOTE = ("sector S13 general government — wider-perimeter cross-check, "
             "not the register perimeter")
_DELTA_NOTE = ("Δ year-end stock; buy-backs, indexation of principal and FX "
               "effects not separated")


# ---------------------------------------------------------------- Eurostat

def _q4_stocks(iso3: str, sector: str) -> pd.DataFrame:
    from ggfiscal.debt.readers.eurostat_insee_oecd import quarterly_debt

    try:
        q = quarterly_debt(iso3, sector)
    except FileNotFoundError:
        return pd.DataFrame()
    if q.empty:
        return pd.DataFrame()
    q4 = q[q["time_period"].str.endswith("-Q4")].copy()
    q4["year"] = q4["time_period"].str[:4].astype(int)
    return q4.pivot_table(index="year", columns="na_item", values="value")


def eurostat_rows(iso3: str, run_id: str) -> list[dict]:
    from ggfiscal import config

    sha256 = sha(EUROSTAT_SOURCE, f"gov_10q_ggdebt_{config.eurostat_geo(iso3)}")
    rows: list[dict] = []
    for sector, items, perimeter in (("S1311", EUROSTAT_ITEMS, PERIMETER_NOTE[iso3]),
                                     ("S13", EUROSTAT_S13_ITEMS, _S13_NOTE)):
        piv = _q4_stocks(iso3, sector)
        if piv.empty:
            continue
        for na_item, (klass, sub, in_reg) in items.items():
            if na_item not in piv.columns:
                continue
            s = piv[na_item].dropna()
            note = f"{na_item}, {_ESA_NOTE}; {perimeter}"
            for year, value in s.items():
                rows.append(row(run_id, iso3, year, klass, sub, "stock_year_end", value,
                                EUROSTAT_SOURCE, basis="nominal", in_register=in_reg,
                                sha256=sha256, grade="B", notes=note))
            if sector == "S1311" and na_item in ("F31", "F32"):
                for year, value in s.diff().dropna().items():
                    rows.append(row(run_id, iso3, year, klass, sub, "net_issuance", value,
                                    EUROSTAT_SOURCE, basis="nominal_change",
                                    in_register=in_reg, sha256=sha256, grade="B",
                                    notes=f"{_DELTA_NOTE}; {na_item} Q4 stock, {perimeter}"))
    return rows


# ---------------------------------------------------------------- ITA (MEF)

# MEF "Tipologia titolo" label -> (instrument_class, sub_type, in_register)
MEF_CLASSES: dict[str, tuple[str, str, bool]] = {
    "BOT": ("bill", "bot", True),
    "CCTeu": ("floating", "cct_eu", True),
    "BTP": ("fixed_bullet", "btp", True),
    "BTP Green": ("fixed_bullet", "btp_green", True),
    "BTPi (rivalutato)": ("inflation_linked", "btp_ei", True),
    "BTP Italia (rivalutato)": ("inflation_linked", "btp_italia", True),
    "BTP Italia Sì": ("inflation_linked", "btp_italia_si", True),
    "BTP Futura": ("other", "btp_futura", True),
    "BTP Valore": ("other", "btp_valore", True),
    "Altri programmi di emissione (1)": ("other", "altri_programmi", True),
    "Totale": ("mixed", "titoli_di_stato_totale", True),
}
# sub-rows ("di cui ...") are components of a row above and never summed
MEF_SKIP_PREFIXES = ("di cui", "Emissioni in euro", "Titoli Ispa", "Emissioni in valuta")


def mef_composition(path) -> pd.DataFrame:
    """One MEF composition CSV -> (label, value_eur_mn); the Italian number
    format (1.899.665,45) is parsed exactly; unknown labels raise."""
    import csv

    text = open(path, "rb").read().decode("latin-1")
    out = []
    started = False
    for rec in csv.reader(text.splitlines(), delimiter=";"):
        if not rec or not rec[0].strip():
            if started:
                break
            continue
        label = rec[0].strip()
        if label.startswith("Tipologia titolo"):
            started = True
            continue
        if not started or label.startswith(MEF_SKIP_PREFIXES):
            continue
        if label not in MEF_CLASSES:
            raise KeyError(f"unmapped MEF instrument class {label!r} in {path} (extend MEF_CLASSES)")
        value = float(rec[1].replace(".", "").replace(",", "."))
        out.append({"label": label, "value_eur_mn": value})
    return pd.DataFrame(out)


def ita_mef_rows(run_id: str) -> list[dict]:
    from ggfiscal import config
    from ggfiscal.standardise.readers import latest_snapshots

    rows: list[dict] = []
    for (sid, part), e in sorted(latest_snapshots().items()):
        if sid != "ITA_MEF_COMPOSIZIONE" or not part.endswith("_12"):
            continue
        year = int(part.split("_")[1])
        frame = mef_composition(config.repo_root() / e["path"])
        for r in frame.itertuples(index=False):
            klass, sub, in_reg = MEF_CLASSES[r.label]
            rows.append(row(run_id, "ITA", year, klass, sub, "stock_year_end", r.value_eur_mn,
                            "ITA_MEF_COMPOSIZIONE", basis="nominal_revalued", in_register=in_reg,
                            sha256=e["sha256"], grade="A",
                            notes=f'MEF "Composizione dei Titoli di Stato in circolazione" at 31 '
                                  f'December, row "{r.label}"; inflation-linked lines revalued '
                                  "(capitale rivalutato), foreign-currency issues after swaps"))
    return rows


# ---------------------------------------------------------------- ESP (BdE)

BDE_ESTADO_SERIES = "DMNPDE2010_P00000_PS_AES"      # Estado. Deuda PDE. Total (thousand EUR)


def esp_bde_rows(run_id: str) -> list[dict]:
    from ggfiscal.debt.readers.bde import be_series

    try:
        s = be_series("be11b", BDE_ESTADO_SERIES)
    except FileNotFoundError:
        return []
    dec = s[s.index.month == 12]
    sha256 = sha("ESP_BDE_BE", "be_zip")
    rows: list[dict] = []
    for ts, value in (dec / 1000.0).items():
        rows.append(row(run_id, "ESP", ts.year, "mixed", "estado_pde_total", "stock_year_end",
                        value, "ESP_BDE_BE", basis="nominal", in_register=False,
                        sha256=sha256, grade="A",
                        notes=f"Banco de España Boletín Estadístico 11b, series "
                              f"{BDE_ESTADO_SERIES} (Estado, deuda PDE, total, all "
                              "instruments), December; the Estado alone (S13111 "
                              "perimeter), below S1311 by the central agencies"))
    return rows


# ---------------------------------------------------------------- entry points

def ita_class_aggregates(run_id: str) -> pd.DataFrame:
    return pd.DataFrame(ita_mef_rows(run_id) + eurostat_rows("ITA", run_id), columns=COLUMNS)


def esp_class_aggregates(run_id: str) -> pd.DataFrame:
    return pd.DataFrame(esp_bde_rows(run_id) + eurostat_rows("ESP", run_id), columns=COLUMNS)


def bel_class_aggregates(run_id: str) -> pd.DataFrame:
    return pd.DataFrame(eurostat_rows("BEL", run_id), columns=COLUMNS)
