"""Pull registry for the debt extension (DEBT_KICKOFF.md §11, §13).

Each source family lives in `ggfiscal.debt.families.<name>` and exposes
`pulls() -> list[Pull]`; optionally `get(pull) -> bytes` for publishers that
need a bespoke client. Families are enumerated here so `ggfiscal debt fetch`
and `detect-vintages` see one list. Blocked hosts (DMO, AFT, Finanzagentur,
ECB, Bundesbank, Banque de France — OQ-8) have families whose `pulls()`
return the intended pull definitions; the fetch layer records the egress
denial rather than skipping them, so `debt_source_verification.md` names
what is still missing.
"""

from __future__ import annotations

import importlib
from types import ModuleType

from ggfiscal.ingest.endpoints import Pull  # noqa: F401  (re-exported)

FAMILIES = (
    "boe",                   # APF operations, yield curves, IADB, Bank Rate history
    "ons_hmt",               # PSF Appendix A/S, PSF time series, RPI, DMR, NLF accounts
    "bmf",                   # Datenportal xlsx/csv, Kreditaufnahmebericht, Monatsbericht
    "eurostat_insee_oecd",   # gov_10dd_*, gov_10a_main S1311, prc_hicp, irt_*, INSEE ajax, OECD T7PSD/FINMARK
    "debt_offices",          # DMO, AFT, Finanzagentur — blocked (OQ-8); definitions only
)


def family(name: str) -> ModuleType:
    return importlib.import_module(f"ggfiscal.debt.families.{name}")


def all_debt_pulls(families: tuple[str, ...] | None = None) -> list[tuple[str, Pull]]:
    """(family_name, Pull) for every registered pull, in family order."""
    out: list[tuple[str, Pull]] = []
    for name in families or FAMILIES:
        for p in family(name).pulls():
            out.append((name, p))
    return out
