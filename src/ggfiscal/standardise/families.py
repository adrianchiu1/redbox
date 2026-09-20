"""Anchor families (REPLICATION_KICKOFF.md §11.3, D27; Stage R0, D-S15-002).

An anchor family is the set of readers that serve one institution's tables
behind one interface. Every place that used to decide by ``iso3 == "GBR"``
which reader serves a cell now asks ``config.family(iso3)`` and calls the
family; the family is named per country in ``config/countries.yaml``
(``anchor_family: ons | eurostat``). A country whose family is not
configured, or names a family this module does not implement, raises
:class:`FamilyNotConfigured` — it never falls through to another country's
path.

The two implementations here wrap today's readers (``standardise.readers``)
unchanged: every series a family returns is exactly the series the routing
sites read before R0, so the canonical layer is byte-identical. A third
family (``oecd_sna`` for USA/JPN, kickoff §11.3) is one more class in the
registry plus its readers.

Beyond the seven protocol methods, the sites need the institution-specific
cell arithmetic that used to sit inline (the D1 revenue mapping, the ESA_EXP
item lists, the Level II revenue cells, the recon and coverage candidate
lists); those are family methods too, so a family is the complete answer to
"which cells build this country's trees".
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

from ggfiscal import config
from ggfiscal.standardise import readers as R


class FamilyNotConfigured(LookupError):
    """The country has no usable anchor family in countries.yaml."""


@runtime_checkable
class AnchorFamily(Protocol):
    """Kickoff §11.3: the interface every routing site programs against."""

    name: str

    def cofog(self, iso3: str, code: str) -> pd.Series:
        """GFxx / GFxxyy total expenditure (OTE / na_item TE), LCU mn."""

    def cofog_total(self, iso3: str) -> pd.Series:
        """The COFOG table's own total row (V2 baseline)."""

    def main(self, iso3: str, item: str, direction: str = "") -> pd.Series:
        """Main-aggregates item (gov_10a_main na_item; ONS ESA Table 2 code +
        'payable' | 'receivable' | '')."""

    def tax(self, iso3: str, code: str) -> pd.Series:
        """Tax-detail cell (gov_10a_taxag; ONS NTL table 9)."""

    def d41_payable(self, iso3: str) -> pd.Series:
        """GG gross D.41 payable from the same institution (D10 fallback)."""

    def gdp(self, iso3: str) -> tuple[pd.Series, str]:
        """(nominal GDP LCU mn, source_id)."""

    def totals(self, iso3: str) -> dict[str, pd.Series]:
        """{'TR', 'TE', 'B9'} from the balance anchor (V23 within-source)."""

    def level2(self, iso3: str, line_code: str) -> pd.Series | None:
        """COFOG Level II cell of a `level: "2"` line; None where the family
        publishes no Level II table (fallback / proxy path applies)."""


class _Base:
    name = ""
    expenditure_source = ""       # COFOG table source_id
    main_source = ""              # main aggregates / revenue / balance source_id
    tax_source = ""               # tax-detail table source_id
    interest_history_source = ""  # coverage label of the D10 D.41-payable candidate
    revenue_cell_key = ""         # lines.yaml key of a revenue Level II cell spec
    esa_exp_key = ""              # lines.yaml key of an ESA_EXP item list

    # --- derived from the protocol methods, identical for every family ---

    def level2(self, iso3: str, line_code: str) -> pd.Series | None:
        meta = config.level2_lines("COFOG").get(line_code)
        if meta is None or not meta.get("eurostat_cofog"):
            return None
        return self.cofog(iso3, meta["eurostat_cofog"])

    def bridge_aggregates(self, iso3: str) -> dict[str, pd.Series]:
        """§8.2: TR, TE, NLB, GDP, GF01_7, R07 from the anchors, LCU mn."""
        t = self.totals(iso3)
        return {"TR": t["TR"], "TE": t["TE"], "NLB": t["B9"],
                "GDP": self.gdp(iso3)[0], "GF01_7": self.cofog(iso3, "GF0107"),
                "R07": self.d41_receivable(iso3)}


class OnsFamily(_Base):
    """ONS ESA Table 11 (COFOG), ESA Table 2 S13 (main aggregates, payable and
    receivable rows), the ESA questionnaire table 9 (NTL tax detail) and YBHA
    GDP — the United Kingdom's anchors (D1)."""

    name = "ons"
    expenditure_source = "ONS_ESA_T11"
    main_source = "ONS_GG_RECEIPTS"
    tax_source = "ONS_TAX_DETAIL"
    interest_history_source = "ONS_PSF_INTEREST"
    revenue_cell_key = "ons"
    esa_exp_key = "ons_t2"

    def cofog(self, iso3: str, code: str) -> pd.Series:
        return R.ons_cofog(code)

    def cofog_total(self, iso3: str) -> pd.Series:
        return R.ons_cofog("_T")

    def main(self, iso3: str, item: str, direction: str = "") -> pd.Series:
        return R.ons_t2_series(item, direction)

    def tax(self, iso3: str, code: str) -> pd.Series:
        return R.ons_tax_series(code)

    def d41_payable(self, iso3: str) -> pd.Series:
        return R.ons_t2_series("D41", "payable")

    def d41_receivable(self, iso3: str) -> pd.Series:
        return R.ons_t2_series("D41", "receivable")

    def gdp(self, iso3: str) -> tuple[pd.Series, str]:
        return R.ons_gdp(), "ONS_GDP"

    def totals(self, iso3: str) -> dict[str, pd.Series]:
        return {"TR": R.ons_t2_series("OTR", ""), "TE": R.ons_t2_series("OTE", ""),
                "B9": R.ons_t2_series("B9", "")}

    # --- the D1 revenue mapping (§4.2, §14) ---

    def revenue_lines(self, iso3: str) -> dict[str, tuple[pd.Series, str, str]]:
        t2 = lambda c, d="receivable": R.ons_t2_series(c, d)  # noqa: E731
        return {
            "R01": (t2("D211"), "anchor_actual", ""),
            "R02": ((t2("D2") - t2("D211")).dropna(), "derived_actual",
                    "derived D.2 - D.211"),
            "R03": (t2("D51M"), "anchor_actual",
                    "D51M households incl. holding gains; crosswalk: NICs are D.61 not here"),
            "R04": (t2("D51O"), "anchor_actual", "D51O corporations incl. holding gains"),
            "R05": ((t2("D5") - t2("D51M") - t2("D51O") + t2("D91")).dropna(),
                    "derived_actual", "derived D.5 - R03 - R04 + D.91 (D.59 inside D.5)"),
            "R06": (t2("D61"), "anchor_actual", "NICs are D.61 (§14)"),
            "R07": (t2("D41"), "anchor_actual", ""),
            "R08": ((t2("D4") - t2("D41")).dropna(), "derived_actual",
                    "derived D.4 - D.41 resources"),
            "R09": ((t2("P11", "") + t2("P12", "") + t2("P131", "")).dropna(),
                    "derived_actual", "derived P.11 + P.12 + P.131"),
            "R10": ((t2("D39R") + t2("D7") + t2("D9") - t2("D91")).dropna(),
                    "derived_actual", "derived D.39 + D.7 + (D.9 - D.91) resources"),
        }

    def revenue_total(self, iso3: str) -> pd.Series:
        return R.ons_t2_series("OTR", "")

    def revenue_coverage(self, iso3: str) -> dict[str, list[tuple[str, pd.Series, str]]]:
        from ggfiscal.coverage import _intersect

        t2 = lambda c, d="receivable": R.ons_t2_series(c, d)  # noqa: E731
        ntl = R.ons_tax_series
        return {
            "R01": [("ONS_GG_RECEIPTS", t2("D211"), "anchor; D.211 receivable"),
                    ("ONS_TAX_DETAIL", ntl("D211"), "NTL detail")],
            "R02": [("ONS_GG_RECEIPTS", _intersect(t2("D2"), t2("D211")),
                     "derived D.2 - D.211")],
            "R03": [("ONS_GG_RECEIPTS", t2("D51M"),
                     "D51M = household income taxes incl. holding gains"),
                    ("ONS_TAX_DETAIL", ntl("D51M"), "NTL detail")],
            "R04": [("ONS_GG_RECEIPTS", t2("D51O"),
                     "D51O = corporate income taxes incl. holding gains"),
                    ("ONS_TAX_DETAIL", ntl("D51O"), "NTL detail")],
            "R05": [("ONS_GG_RECEIPTS",
                     _intersect(t2("D5"), t2("D51M"), t2("D51O"), t2("D59"), t2("D91")),
                     "derived D.5 - D.51M - D.51O + D.59 + D.91")],
            "R06": [("ONS_GG_RECEIPTS", t2("D61"), "anchor; D.61 receivable")],
            "R07": [("ONS_GG_RECEIPTS", t2("D41"), "anchor; D.41 receivable, accrued")],
            "R08": [("ONS_GG_RECEIPTS", _intersect(t2("D4"), t2("D41")),
                     "derived D.4 - D.41 receivable")],
            "R09": [("ONS_GG_RECEIPTS",
                     _intersect(t2("P11", ""), t2("P12", ""), t2("P131", "")),
                     "derived P.11 + P.12 + P.131")],
            "R10": [("ONS_GG_RECEIPTS",
                     _intersect(t2("D39R"), t2("D7"), t2("D9"), t2("D91")),
                     "derived D.39 + D.7 + (D.9 - D.91) receivable")],
        }

    def revenue_level2(self, iso3: str, meta: dict) -> tuple[pd.Series, str, str]:
        """(series, source_id, concept note) of a revenue Level II line from
        its lines.yaml `ons` cell: ESA Table 2 receivable rows, or NTL table
        9 codes (a different table from the parent's T2 aggregate, so any
        transmission-timing drift lands in the derived remainder)."""
        from ggfiscal.build import _sum_codes

        spec = meta[self.revenue_cell_key]
        codes = spec["codes"]
        if spec["table"] == "t2":
            d = spec.get("direction", "receivable")
            return (_sum_codes([R.ons_t2_series(c, d) for c in codes]),
                    "ONS_GG_RECEIPTS", f"ESA Table 2 {' + '.join(codes)} receivable")
        return (_sum_codes([R.ons_tax_series(c) for c in codes]), "ONS_TAX_DETAIL",
                f"NTL table 9 {' + '.join(codes)} (per-tax detail table; the parent "
                "comes from ESA Table 2, so any drift lands in the remainder)")

    def esa_exp_parts(self, iso3: str, meta: dict) -> tuple[list[pd.Series], list[pd.Series]]:
        """(plus, minus) ESA Table 2 payable rows of one ESA_EXP line."""
        spec = meta[self.esa_exp_key]
        return ([R.ons_t2_series(c, d) for c, d in spec.get("plus", [])],
                [R.ons_t2_series(c, d) for c, d in spec.get("minus", [])])

    def recon_revenue(self, iso3: str) -> tuple[dict[str, pd.Series], str]:
        """Anchor cells compared with OECD RS headings (recon_v0)."""
        return ({"R01": R.ons_t2_series("D211", "receivable"),
                 "R03": R.ons_t2_series("D51M", "receivable"),
                 "R04": R.ons_t2_series("D51O", "receivable"),
                 "R06": R.ons_t2_series("D61", "receivable")}, "ONS_GG_RECEIPTS")


class EurostatFamily(_Base):
    """Eurostat gov_10a_exp (COFOG), gov_10a_main (main aggregates, REC/PAY
    items), gov_10a_taxag (tax detail) and nama_10_gdp — the anchors of the
    euro-area countries (D1). All revenue lines come from gov_10a_main's own
    REC codes (D-S1-002): taxag values drift from the main table in the
    freshest years, which would break V22 against the main table's TR."""

    name = "eurostat"
    expenditure_source = "EUROSTAT_GOV10A_EXP"
    main_source = "EUROSTAT_GOV10A_MAIN"
    tax_source = "EUROSTAT_GOV10A_TAXAG"
    interest_history_source = "EUROSTAT_GOV10A_MAIN"
    revenue_cell_key = "eurostat"
    esa_exp_key = "eurostat_main"

    def cofog(self, iso3: str, code: str) -> pd.Series:
        return R.eurostat_cofog(iso3, code)

    def cofog_total(self, iso3: str) -> pd.Series:
        return R.eurostat_cofog(iso3, "TOTAL")

    def main(self, iso3: str, item: str, direction: str = "") -> pd.Series:
        # gov_10a_main items carry the direction in the code (D41REC / D41PAY)
        return R.eurostat_main(iso3, item)

    def tax(self, iso3: str, code: str) -> pd.Series:
        return R.eurostat_taxag(iso3, code)

    def d41_payable(self, iso3: str) -> pd.Series:
        return R.eurostat_main(iso3, "D41PAY")

    def d41_receivable(self, iso3: str) -> pd.Series:
        return R.eurostat_main(iso3, "D41REC")

    def gdp(self, iso3: str) -> tuple[pd.Series, str]:
        return R.eurostat_gdp(iso3), "EUROSTAT_NAMA10_GDP"

    def totals(self, iso3: str) -> dict[str, pd.Series]:
        return {"TR": R.eurostat_main(iso3, "TR"), "TE": R.eurostat_main(iso3, "TE"),
                "B9": R.eurostat_main(iso3, "B9")}

    def revenue_lines(self, iso3: str) -> dict[str, tuple[pd.Series, str, str]]:
        em = lambda c: R.eurostat_main(iso3, c)  # noqa: E731
        return {
            "R01": (em("D211REC"), "anchor_actual", ""),
            "R02": ((em("D2REC") - em("D211REC")).dropna(), "derived_actual",
                    "derived D.2 - D.211"),
            "R03": (em("D51A_C1REC"), "anchor_actual", "CSG is D.5 -> here, not R06 (§14)"
                    if iso3 == "FRA" else ""),
            "R04": (em("D51B_C2REC"), "anchor_actual", ""),
            "R05": ((em("D5REC") - em("D51A_C1REC") - em("D51B_C2REC")
                     + em("D91REC")).dropna(),
                    "derived_actual", "derived D.5 - R03 - R04 + D.91 (D.59 inside D.5)"),
            "R06": (em("D61REC"), "anchor_actual", ""),
            "R07": (em("D41REC"), "anchor_actual", ""),
            "R08": ((em("D4REC") - em("D41REC")).dropna(), "derived_actual",
                    "derived D.4 - D.41 resources"),
            "R09": (em("P11_P12_P131"), "anchor_actual", ""),
            "R10": ((em("D39REC") + em("D7REC") + em("D92REC") + em("D99REC")).dropna(),
                    "derived_actual", "derived D.39 + D.7 + D.92 + D.99 resources"),
        }

    def revenue_total(self, iso3: str) -> pd.Series:
        return R.eurostat_main(iso3, "TR")

    def revenue_coverage(self, iso3: str) -> dict[str, list[tuple[str, pd.Series, str]]]:
        from ggfiscal.coverage import _intersect

        em = lambda c: R.eurostat_main(iso3, c)  # noqa: E731
        et = lambda c: R.eurostat_taxag(iso3, c)  # noqa: E731
        return {
            "R01": [("EUROSTAT_GOV10A_MAIN", em("D211REC"), "anchor; D.211 (D-S1-002)"),
                    ("EUROSTAT_GOV10A_TAXAG", et("D211"), "detail/verification")],
            "R02": [("EUROSTAT_GOV10A_MAIN", _intersect(em("D2REC"), em("D211REC")),
                     "derived D.2 - D.211")],
            "R03": [("EUROSTAT_GOV10A_MAIN", em("D51A_C1REC"),
                     "anchor; household income taxes incl. holding gains"),
                    ("EUROSTAT_GOV10A_TAXAG", et("D51A_C1"), "detail/verification")],
            "R04": [("EUROSTAT_GOV10A_MAIN", em("D51B_C2REC"),
                     "anchor; corporate income taxes incl. holding gains"),
                    ("EUROSTAT_GOV10A_TAXAG", et("D51B_C2"), "detail/verification")],
            "R05": [("EUROSTAT_GOV10A_MAIN",
                     _intersect(em("D5REC"), em("D51A_C1REC"), em("D51B_C2REC"),
                                em("D91REC")),
                     "derived D.5 - R03 - R04 + D.91 (D.59 inside D.5)")],
            "R06": [("EUROSTAT_GOV10A_MAIN", em("D61REC"), "anchor; D.61 resources")],
            "R07": [("EUROSTAT_GOV10A_MAIN", em("D41REC"), "anchor; D.41 resources")],
            "R08": [("EUROSTAT_GOV10A_MAIN", _intersect(em("D4REC"), em("D41REC")),
                     "derived D.4 - D.41 resources")],
            "R09": [("EUROSTAT_GOV10A_MAIN", em("P11_P12_P131"), "anchor")],
            "R10": [("EUROSTAT_GOV10A_MAIN",
                     _intersect(em("D39REC"), em("D7REC"), em("D92REC"), em("D99REC")),
                     "derived D.39 + D.7 + D.92 + D.99 resources")],
        }

    def revenue_level2(self, iso3: str, meta: dict) -> tuple[pd.Series, str, str]:
        """(series, source_id, concept note) of a revenue Level II line from
        its lines.yaml `eurostat` cell: gov_10a_main or gov_10a_taxag items
        (taxag is a different table from the parent's main aggregate, so any
        drift lands in the derived remainder, D-S1-002)."""
        from ggfiscal.build import _sum_codes

        spec = meta[self.revenue_cell_key]
        codes = spec["codes"]
        if spec["dataset"] == "gov_10a_main":
            return (_sum_codes([R.eurostat_main(iso3, c) for c in codes]), "EUROSTAT_GOV10A_MAIN",
                    f"gov_10a_main {' + '.join(codes)}")
        return (_sum_codes([R.eurostat_taxag(iso3, c) for c in codes]), "EUROSTAT_GOV10A_TAXAG",
                f"gov_10a_taxag {' + '.join(codes)} (detail table; the parent comes from "
                "gov_10a_main, so any drift lands in the remainder, D-S1-002)")

    def esa_exp_parts(self, iso3: str, meta: dict) -> tuple[list[pd.Series], list[pd.Series]]:
        """(plus, minus) gov_10a_main payable items of one ESA_EXP line."""
        spec = meta[self.esa_exp_key]
        return ([R.eurostat_main(iso3, c) for c in spec.get("plus", [])],
                [R.eurostat_main(iso3, c) for c in spec.get("minus", [])])

    def recon_revenue(self, iso3: str) -> tuple[dict[str, pd.Series], str]:
        return ({"R01": R.eurostat_taxag(iso3, "D211"),
                 "R03": R.eurostat_taxag(iso3, "D51A_C1"),
                 "R04": R.eurostat_taxag(iso3, "D51B_C2"),
                 "R06": R.eurostat_main(iso3, "D61REC")}, "EUROSTAT_GOV10A_TAXAG/MAIN")


# The registry: anchor_family name (countries.yaml) -> implementation. A
# fourth country with a new institution adds a class here; nothing else in
# the package learns a new country name.
FAMILIES: dict[str, type] = {"ons": OnsFamily, "eurostat": EurostatFamily}

_instances: dict[str, _Base] = {}


def for_country(iso3: str) -> AnchorFamily:
    """The anchor family configured for `iso3`. Raises FamilyNotConfigured
    (never falls through) when countries.yaml names no family for the
    country or names one this module does not implement."""
    cfg = config.country(iso3)
    name = cfg.get("anchor_family")
    if not name:
        raise FamilyNotConfigured(
            f"{iso3}: no `anchor_family` in config/countries.yaml "
            f"(implemented families: {', '.join(FAMILIES)})")
    cls = FAMILIES.get(name)
    if cls is None:
        raise FamilyNotConfigured(
            f"{iso3}: anchor family {name!r} is not implemented in "
            f"ggfiscal.standardise.families (implemented: {', '.join(FAMILIES)}); "
            "add its class to FAMILIES — no other country's readers are used")
    if name not in _instances:
        _instances[name] = cls()
    return _instances[name]
