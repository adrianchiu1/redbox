"""DEBT_KICKOFF.md §4.2 / §5.4: the reference-series table from the reachable
statistical sources (DD9: statistical indices are the cross-check and the
gap-filler; the debt offices' own index ratios are contractual and live in
`debt_index_ratios` once their hosts are reachable).

Series ids and their provenance are declared in config/debt.yaml
`reference_series`; this module knows how to materialise each one from
the family readers.
"""

from __future__ import annotations

import warnings

import pandas as pd

from ggfiscal.standardise.readers import latest_snapshots

CURVE_KINDS = {"UK_GLC_NOMINAL": "nominal", "UK_GLC_REAL": "real",
               "UK_GLC_INFLATION": "inflation", "UK_OIS": "ois"}


def _sha(source_id: str, part: str) -> str | None:
    e = latest_snapshots().get((source_id, part))
    return e["sha256"] if e else None


def _rows(series_id: str, s: pd.Series, unit: str, source_id: str, sha: str | None,
          base_period: str | None, note: str | None, grade: str = "A") -> pd.DataFrame:
    s = s.dropna()
    return pd.DataFrame({
        "series_id": series_id, "date": pd.to_datetime(s.index), "value": s.values.astype(float),
        "unit": unit, "base_period": base_period, "vintage_note": note,
        "source_id": source_id, "snapshot_sha256": sha, "quality_grade": grade, "notes": None,
    })


def build_reference_series(run_id: str, include_curves: bool = True) -> pd.DataFrame:
    from ggfiscal.debt.readers import boe as B
    from ggfiscal.debt.readers import ecb_bbk as X
    from ggfiscal.debt.readers import eurostat_insee_oecd as E
    from ggfiscal.debt.readers import ons_hmt as O

    frames: list[pd.DataFrame] = []

    # --- inflation references -------------------------------------------
    rpi = O.rpi_index()
    frames.append(_rows("UK_RPI", rpi, "index", "ONS_RPI", _sha("ONS_RPI", "CHAW"), "1987-01=100",
                        "CHAW from 1987-01; CDKO (1974-01=100) rescaled by 100/CDKO(1987-01) before"))
    fr = E.fr_cpi_ex_tobacco_chained()
    frames.append(_rows("FR_CPI_XT", fr, "index", "INSEE_IPC", _sha("INSEE_IPC", "011814056"), "2025=100",
                        f"idbank 011814056 (base 2025) chained back with 001763852 (base 2015) "
                        f"x {fr.attrs.get('chain_factor'):.6f} over {fr.attrs.get('overlap_months')} months; "
                        "France entière, ensemble hors tabac"))
    for geo in ("EA", "FR", "DE"):
        h = E.hicp_ex_tobacco_chained(geo)
        sid = "EA_HICP_XT" if geo == "EA" else f"{geo}_HICP_XT"
        frames.append(_rows(sid, h, "index", "EUROSTAT_PRC_HICP", _sha("EUROSTAT_PRC_HICP", f"prc_hicp_minr_{geo}"),
                            "2025=100", f"prc_hicp_minr I25 TOT_X_TBC {geo}; I15 archive chained "
                            f"x {h.attrs.get('chain_factor'):.6f} where I25 absent"
                            + ("; EA = changing composition" if geo == "EA" else "")))

    # --- short rates ------------------------------------------------------
    frames.append(_rows("UK_SONIA", B.iadb_series("IUDSOIA"), "pct_pa", "BOE_IADB", _sha("BOE_IADB", "IUDSOIA"), None, "daily"))
    frames.append(_rows("UK_BANK_RATE", B.iadb_series("IUDBEDR"), "pct_pa", "BOE_IADB", _sha("BOE_IADB", "IUDBEDR"), None, "daily"))
    for tenor, sid in (("3M", "EA_MM_3M"), ("6M", "EA_MM_6M")):
        frames.append(_rows(sid, E.ea_money_market(tenor), "pct_pa", "EUROSTAT_IRT",
                            _sha("EUROSTAT_IRT", f"irt_st_m_IRT_M{tenor[0]}"), None,
                            "monthly average; EA aggregate retropolated before 1999"))
    for iso3, sid in (("FRA", "FR_IR3"), ("DEU", "DE_IR3"), ("GBR", "GB_IR3")):
        frames.append(_rows(sid, E.oecd_rate(iso3, "IR3TIB"), "pct_pa", "OECD_FINMARK",
                            _sha("OECD_FINMARK", f"FINMARK_IR3TIB_{iso3}"), None, "monthly average, national 3-month rate"))
        frames.append(_rows(sid.replace("IR3", "LT10"), E.oecd_rate(iso3, "IRLT"), "pct_pa", "OECD_FINMARK",
                            _sha("OECD_FINMARK", f"FINMARK_IRLT_{iso3}"), None, "monthly average, long-term government yield"))
    for geo, sid in (("FR", "FR_MCBY"), ("DE", "DE_MCBY"), ("EA", "EA_MCBY")):
        frames.append(_rows(sid, E.long_term_yield(geo), "pct_pa", "EUROSTAT_IRT",
                            _sha("EUROSTAT_IRT", f"irt_lt_mcby_m_{geo}"), None, "EMU convergence-criterion 10y yield"))

    # --- ecb_bbk reference rates (§13) -------------------------------------
    # Each entry may be missing if `ggfiscal debt fetch --family ecb_bbk`
    # has not run in this environment; skip with a warning rather than
    # failing the whole build (family readers raise FileNotFoundError via
    # `snap_path` when the snapshot is absent).
    for sid, reader, source_id, part, note in (
        ("EA_ESTR", X.ecb_series, "ECB_EMMI_RATES", "estr",
         "euro short-term rate, daily, volume-weighted trimmed mean, from 2019-10-01"),
        ("EA_EURIBOR_3M", X.ecb_series, "ECB_EMMI_RATES", "euribor_3m",
         "Euribor 3-month, historical close, monthly average, from 1994-01 (no daily key found — see report)"),
        ("EA_EURIBOR_6M", X.ecb_series, "ECB_EMMI_RATES", "euribor_6m",
         "Euribor 6-month, historical close, monthly average, from 1994-01 (no daily key found — see report)"),
        ("EA_EONIA", X.ecb_series, "ECB_EMMI_RATES", "eonia",
         "Eonia rate, historical close, monthly average, 1994-01 to 2021-12 "
         "(discontinued 2022-01; monthly only — the daily key 404s, see report)"),
        ("DE_BUND_YIELD_10Y", X.bbk_series, "BBK_KAPITALMARKT", "bund_yield_10y",
         "Svensson-method term structure, listed federal securities, 10.0y residual maturity, daily"),
    ):
        try:
            frames.append(_rows(sid, reader(part), "pct_pa", source_id, _sha(source_id, part), None, note))
        except FileNotFoundError as e:
            warnings.warn(f"reference series {sid} skipped: {e}")

    # --- BoE curves (Q-D10: stored now) -----------------------------------
    if include_curves:
        for prefix, kind in CURVE_KINDS.items():
            curve = B.yield_curve(kind, "monthend")
            for mat, g in curve.groupby("maturity_years"):
                s = g.set_index("date")["value_pct"].sort_index()
                sid = f"{prefix}_{mat:g}Y"
                frames.append(_rows(sid, s, "pct_pa", "BOE_YIELD_CURVES",
                                    _sha("BOE_YIELD_CURVES", f"{kind}_monthend"), None,
                                    f"BoE government liability {kind} spot curve, month-end, {mat:g}y"))

    out = pd.concat(frames, ignore_index=True)
    out.insert(0, "run_id", run_id)
    out = out.drop_duplicates(["series_id", "date"], keep="last").sort_values(["series_id", "date"]).reset_index(drop=True)
    return out
