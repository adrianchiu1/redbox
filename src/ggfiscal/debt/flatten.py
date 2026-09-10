"""The debt extension's part of the flat-file bundle (DEBT_KICKOFF.md DD12,
§12 D5): every canonical `debt_*` table copied verbatim into
`deliverables/`, its columns described for `data_dictionary.csv`, and a
one-line description per file for the bundle README. Nothing is recomputed.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ggfiscal import config

FILES = {
    "debt_reference_series.csv":
        "reference series behind the register: RPI (Jan 1987=100, 1947-), "
        "French CPI ex-tobacco (base 2025, 1990-), euro-area/FR/DE HICP "
        "ex-tobacco, SONIA, Bank Rate, euro money-market and national 3m and "
        "long rates, and the BoE nominal/real/inflation/OIS month-end curves "
        "by maturity — one row per series-date",
    "debt_official_totals.csv":
        "the official intermediate totals of the two reconciliation chains "
        "per country-year: finance-ministry central-government interest / net "
        "cash requirement (step A), S.1311 D.41 / B.9 (step B), the package's "
        "GF01_7 / NLB (step C); null where the source is blocked (OQ-8)",
    "debt_class_aggregates.csv":
        "the ministries' and statistical offices' own instrument-class totals "
        "per country-year (stock at 31 Dec, gross issuance, redemptions, net "
        "issuance, interest, own holdings) — the DD8 aggregate layer standing "
        "in for the per-security register",
    "debt_interest_reconciliation.csv":
        "interest chain: Σ register by class → CG interest (ministry) → S.1311 "
        "D.41 → GF01_7, with every bridge item and the residual per step, per "
        "country-year (V32: official_total = carried + Σ items + residual)",
    "debt_financing_reconciliation.csv":
        "financing chain: Σ net issuance by class → CG net cash requirement / "
        "Nettokreditaufnahme → S.1311 B.9 → NLB, same shape",
    "debt_securities.csv":
        "the per-security register: one row per security (ISIN) with class, "
        "coupon, dates, index or floating reference, from the debt office",
    "debt_positions.csv":
        "nominal outstanding per security at each year-end (and month-end "
        "where the office publishes it), with own holdings and market-hands",
    "debt_flows.csv":
        "every issuance, retention, redemption, buy-back or conversion per "
        "security by settlement date, with price and yield where published",
    "debt_index_ratios.csv":
        "the office's daily index ratios for inflation-linked securities",
    "debt_interest_by_security.csv":
        "interest per security-year on both bases (accrued, cash): coupon, "
        "indexation uplift, bill discount, floating coupon, premium/discount "
        "amortisation, with the derivation",
    "debt_maturity_profile.csv":
        "nominal outstanding by instrument class and residual-maturity "
        "bucket at each 31 December",
    "debt_issuance_by_bucket.csv":
        "gross issuance by instrument class and residual maturity at "
        "settlement, per year",
}

_COMMON = {
    "run_id": "Build run that produced the row (data/manifest/run_{run_id}.json).",
    "iso3": "Country: GBR, FRA, DEU.",
    "year": "Calendar year (DD6).",
    "source_id": "Register id of the source (config/debt_sources.yaml), or the module that derived the row.",
    "snapshot_sha256": "sha256 of the raw snapshot the value was read from (D8); empty for derived rows.",
    "quality_grade": "A–D per DEBT_KICKOFF.md §9; official rows A, aggregate-layer and derived rows B, declared items C, blocked D.",
    "notes": "Free-text provenance: table, row, conversion, caveat.",
}

DICTIONARY: dict[str, dict[str, str]] = {
    "debt_reference_series.csv": {
        **_COMMON,
        "series_id": "Reference series id (DEBT_KICKOFF.md §4.2), e.g. UK_RPI, FR_CPI_XT, EA_HICP_XT, UK_SONIA, EA_MM_3M, UK_GLC_NOMINAL_10Y.",
        "date": "Observation date (month start for monthly indices; the fixing date for daily rates; month-end for curves).",
        "value": "Observation in `unit`.",
        "unit": "index | pct_pa.",
        "base_period": "Index base (e.g. 1987-01=100, 2025=100); empty for rates.",
        "vintage_note": "How the series was built (splice, chaining factor, geography).",
    },
    "debt_official_totals.csv": {
        **_COMMON,
        "chain": "interest | financing.",
        "step": "A_cg_cash / B_s1311_d41 / C_s13_gf01_7 (interest); A_cg_cash_requirement / B_s1311_b9 / C_s13_nlb (financing).",
        "value_lcu_mn": "The official total, millions of national currency; null where the source is unreachable (OQ-8) or the year is not covered.",
        "item_source_id": "Source of the total (register id, or package_GF01_7 / package_NLB for step C).",
        "basis": "Accounting basis of the total as published: cash, accrued, accrued_nlf_finance_costs, cash_budgetaire.",
        "period_basis": "CY, FY or M: the source's native period before conversion.",
        "period_conversion_method": "How a non-calendar-year source was converted (§7.10 formula, or 'sum of 12 calendar months'); empty when none.",
    },
    "debt_class_aggregates.csv": {
        **_COMMON,
        "instrument_class": "DD2 class (fixed_bullet, floating, inflation_linked, bill, other), or mixed where the source does not split, or out_of_register for the source's rows outside DD1 (loans, retail, special funds).",
        "sub_type": "The source's own instrument or fund label, slugged.",
        "measure": "stock_year_end | stock_gross_umlauf | own_holdings | gross_issuance | redemptions | net_issuance | interest | uplift_accrued.",
        "value_lcu_mn": "Value, millions of national currency; interest and redemptions positive.",
        "basis": "nominal, cash, accrued, nominal_change, … as the source publishes it.",
        "in_register": "True when the row is inside the DD1 perimeter and enters the register step of the chains.",
    },
    "debt_interest_reconciliation.csv": {
        **_COMMON,
        "step": "register → A_cg_cash → B_s1311_d41 → C_s13_gf01_7.",
        "item": "sum_{class} at the register step; carried_from_previous_step; the named bridge items; official_total; residual.",
        "value_lcu_mn": "Millions of national currency; null where the total is unknown (blocked source or no register).",
        "item_type": "computed | official | declared | residual.",
        "item_source_id": "Where the item comes from.",
        "basis": "Accounting basis of the item (cash, accrued, nominal).",
    },
}
_REG_COMMON = {**_COMMON, "security_id": "ISIN, or {iso3}_{office code} for pre-ISIN securities."}
DICTIONARY["debt_securities.csv"] = {
    **_REG_COMMON,
    "isin": "ISIN where one exists.", "name": "Name as published by the office.",
    "instrument_class": "DD2: fixed_bullet | floating | inflation_linked | bill | other.",
    "sub_type": "National instrument name (config/debt.yaml sub_types).",
    "currency": "Currency of issue (ISO code).", "coupon_pct": "Annual coupon, %; null for bills and floaters.",
    "coupon_frequency": "Number of coupon payments per year.", "day_count": "Day-count / accrual convention.",
    "first_issue_date": "First issue (settlement) date.", "maturity_date": "Final redemption date; null for undated.",
    "first_call_date": "First call date for callable/double-dated securities.",
    "dividend_dates": "Coupon dates, e.g. '22 Apr/Oct'.",
    "index_reference": "Reference index id for linkers (§4.2).", "index_lag_months": "Indexation lag in months.",
    "base_index": "Base index value of the linker.", "floating_reference": "Reference rate id for floaters.",
    "spread_bp": "Spread over the reference rate, basis points.", "is_green": "True for green bonds and green twins.",
    "issuer_unit": "state, or special_fund:{name}.",
}
DICTIONARY["debt_positions.csv"] = {
    **_REG_COMMON, "as_of": "Date of the position (as-of).", "nominal_lcu_mn": "Nominal in issue (unindexed), millions LCU.",
    "nominal_uplifted_lcu_mn": "Nominal × index ratio for linkers.", "nominal_issue_ccy_mn": "Nominal in the issue currency.",
    "official_holdings_lcu_mn": "Issuer's own book (Eigenbestand, DMO/CRND holdings).",
    "market_hands_lcu_mn": "Nominal less official holdings.",
    "position_type": "office_snapshot | office_annual | rolled_from_flows.",
    "fx_rate": "Conversion rate used for foreign-currency issues.", "fx_source_id": "Register id of the FX rate source.",
}
DICTIONARY["debt_flows.csv"] = {
    **_REG_COMMON, "settlement_date": "Settlement date of the operation.",
    "flow_type": "§4.3: auction, syndication, tap, tender, conversion_in/out, switch_in/out, buyback, redemption, retention, own_book_sale/purchase, implied.",
    "seq": "Sequence number for same-day rows.", "operation_date": "Operation (auction) date.",
    "nominal_lcu_mn": "Nominal amount, millions LCU.", "cash_lcu_mn": "Cash proceeds where published.",
    "price_pct": "Issue price per 100 nominal.", "yield_pct": "Yield at issue, per cent.", "method": "Issuance method as published.",
    "counter_security_id": "Counterpart security of a conversion or switch.",
}
DICTIONARY["debt_index_ratios.csv"] = {
    **_REG_COMMON, "date": "Date of the index ratio.", "reference_index": "Reference index value on that date.",
    "index_ratio": "Index ratio (uplift factor).", "ratio_source": "office | recomputed.",
}
DICTIONARY["debt_interest_by_security.csv"] = {
    **_REG_COMMON, "basis": "accrued | cash (DD3).", "coupon_lcu_mn": "Coupon interest, millions LCU.",
    "uplift_lcu_mn": "Indexation uplift, millions LCU.", "discount_lcu_mn": "Bill discount accretion, millions LCU.",
    "floating_lcu_mn": "Floating-rate coupon, millions LCU.", "premium_discount_amort_lcu_mn": "Premium/discount amortisation (accrued basis).",
    "total_lcu_mn": "Sum (coupon + uplift + discount + floating − amortisation); null when not computable.",
    "computability": "computed | not_computable (DD10).", "reference_values_used": "Index ratios / fixings used.",
    "derivation": "The arithmetic in words.",
}
DICTIONARY["debt_maturity_profile.csv"] = {
    **_COMMON, "as_of": "Position date, 31 December.", "instrument_class": "Instrument class per DD2.", "bucket": "Residual-maturity bucket (§4.4).",
    "nominal_lcu_mn": "Nominal outstanding, millions LCU.", "nominal_uplifted_lcu_mn": "Uplifted nominal (linkers).",
    "market_hands_lcu_mn": "Nominal less official holdings.", "n_securities": "Number of securities in the cell.",
    "weighted_residual_years": "Nominal-weighted residual maturity, years.",
}
DICTIONARY["debt_issuance_by_bucket.csv"] = {
    **_COMMON, "instrument_class": "Instrument class per DD2.", "bucket": "Residual maturity at settlement (§4.4).",
    "gross_nominal_lcu_mn": "Gross issuance, nominal.", "gross_cash_lcu_mn": "Gross issuance, cash proceeds.",
    "n_operations": "Number of operations in the cell.", "weighted_residual_years_at_issue": "Nominal-weighted residual maturity at issue.",
}
DICTIONARY["debt_financing_reconciliation.csv"] = {
    **DICTIONARY["debt_interest_reconciliation.csv"],
    "step": "register → A_cg_cash_requirement → B_s1311_b9 → C_s13_nlb.",
    "item": "sum_{class} net issuance at the register step; carried_from_previous_step; the named bridge items (out-of-register instruments, less_special_fund…, nka_3_x… from the Kreditaufnahmebericht, subsector B.9); official_total; residual.",
}


def _canonical_dir() -> Path:
    return config.repo_root() / "data" / "canonical"


def bundle() -> tuple[dict[str, pd.DataFrame], list[tuple[str, str, str]], dict[str, str]]:
    """(files, dictionary rows, descriptions) for every debt table present."""
    files: dict[str, pd.DataFrame] = {}
    rows: list[tuple[str, str, str]] = []
    desc: dict[str, str] = {}
    for name, description in FILES.items():
        src = _canonical_dir() / name
        if not src.exists():
            continue
        df = pd.read_csv(src, float_precision="round_trip")
        files[name] = df
        desc[name] = description
        known = DICTIONARY.get(name, {})
        for col in df.columns:
            rows.append((name, col, known.get(col, "See DEBT_KICKOFF.md §5.")))
    return files, rows, desc
