"""The official forecast envelope per country (D4, §15 Q12): TR, TE and the
same source's nominal GDP path, LCU mn, chosen by the first entry of
``countries.yaml.envelope_forecast`` (R0, D-S15-002) rather than by a
country literal. Each envelope source is one reader here; a country whose
primary envelope source has no reader raises, never falls through.

  OBR_EFO_LATEST  OBR PSF databank: public sector current receipts / total
                  managed expenditure / nominal GDP, FY converted per §7.10
                  with the country's weights — public-sector perimeter
                  (PSCR ≈ 0.97 × GG TR, TME ≈ 0.95 × GG TE, stable; D-S7-002)
  EC_AMECO        AMECO URTG / UUTG (chapter 16) and UVGD (chapter 6),
                  general government, ESA 2010
"""

from __future__ import annotations

import pandas as pd

from ggfiscal import config
from ggfiscal.standardise import readers as R


def _obr(iso3: str) -> dict[str, pd.Series]:
    from ggfiscal.forecast.forward import fy_to_cy

    w = config.fy_to_cy_weights(iso3)
    ag = lambda label: R.obr_databank("Aggregates (£bn)", label)  # noqa: E731
    return {"TR": fy_to_cy(ag("Public sector current receipts"), w) * 1000.0,
            "TE": fy_to_cy(ag("Total managed expenditure"), w) * 1000.0,
            "GDP": fy_to_cy(ag("Nominal GDP (£ billion)"), w) * 1000.0}


def _ameco(iso3: str) -> dict[str, pd.Series]:
    return {"TR": R.ameco_series(iso3, "URTG", 16) * 1000.0,
            "TE": R.ameco_series(iso3, "UUTG", 16) * 1000.0,
            "GDP": R.ameco_series(iso3, "UVGD", 6) * 1000.0}


ENVELOPE_READERS = {"OBR_EFO_LATEST": _obr, "EC_AMECO": _ameco}


def envelope_source(iso3: str) -> str:
    """The primary envelope source_id of the country (envelope_forecast[0])."""
    sources = config.country(iso3).get("envelope_forecast") or []
    if not sources:
        raise LookupError(f"{iso3}: no `envelope_forecast` in config/countries.yaml")
    return sources[0]


def official_envelope(iso3: str) -> dict[str, pd.Series]:
    """{'TR', 'TE', 'GDP'} levels per year, LCU mn, from the country's
    primary envelope source."""
    sid = envelope_source(iso3)
    reader = ENVELOPE_READERS.get(sid)
    if reader is None:
        raise LookupError(f"{iso3}: envelope source {sid!r} has no reader in "
                          f"ggfiscal.forecast.envelopes (readers: {', '.join(ENVELOPE_READERS)})")
    return reader(iso3)
