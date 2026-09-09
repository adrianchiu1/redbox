"""DEBT_KICKOFF.md §5 data model: the canonical debt tables and their pandera
schemas. Every table carries run_id, source_id, snapshot_sha256,
quality_grade, notes (DD12).
"""

from __future__ import annotations

import pandera.pandas as pa
from pandera.pandas import Column

ISO3 = ["GBR", "FRA", "DEU"]
CURRENCIES = ["GBP", "EUR", "USD", "CHF", "JPY", "DEM", "FRF"]
INSTRUMENT_CLASSES = ["fixed_bullet", "floating", "inflation_linked", "bill", "other"]
FLOW_TYPES = ["auction", "syndication", "tap", "tender", "conversion_in",
              "conversion_out", "switch_in", "switch_out", "buyback",
              "redemption", "retention", "own_book_sale", "own_book_purchase",
              "implied"]
POSITION_TYPES = ["office_snapshot", "office_annual", "rolled_from_flows"]
INTEREST_BASES = ["accrued", "cash"]
COMPUTABILITY = ["computed", "not_computable"]
RATIO_SOURCES = ["office", "recomputed"]
GRADES = ["A", "B", "C", "D"]
INTEREST_STEPS = ["register", "A_cg_cash", "B_s1311_d41", "C_s13_gf01_7"]
FINANCING_STEPS = ["register", "A_cg_cash_requirement", "B_s1311_b9", "C_s13_nlb"]
ITEM_TYPES = ["computed", "official", "declared", "residual"]
HOLDERS = ["BOE_APF", "DMO_CRND", "FINANZAGENTUR_OWN", "EUROSYSTEM_S121"]
HOLDING_TYPES = ["per_isin_from_operations", "per_isin_published", "aggregate"]
BUCKETS = ["0-1", "1-2", "2-3", "3-5", "5-7", "7-10", "10-15", "15-20", "20-30", "30+"]


def _provenance() -> dict:
    return {
        "run_id": Column(str),
        "source_id": Column(str),
        "snapshot_sha256": Column(str, nullable=True),
        "quality_grade": Column(str, pa.Check.isin(GRADES)),
        "notes": Column(str, nullable=True),
    }


SECURITIES = pa.DataFrameSchema(
    {
        "iso3": Column(str, pa.Check.isin(ISO3)),
        "security_id": Column(str),
        "isin": Column(str, nullable=True),
        "name": Column(str),
        "instrument_class": Column(str, pa.Check.isin(INSTRUMENT_CLASSES)),
        "sub_type": Column(str),
        "currency": Column(str, pa.Check.isin(CURRENCIES)),
        "coupon_pct": Column(float, nullable=True),
        "coupon_frequency": Column(int, nullable=True),
        "day_count": Column(str, nullable=True),
        "first_issue_date": Column("datetime64[ns]", nullable=True),
        "maturity_date": Column("datetime64[ns]", nullable=True),
        "first_call_date": Column("datetime64[ns]", nullable=True),
        "dividend_dates": Column(str, nullable=True),
        "index_reference": Column(str, nullable=True),
        "index_lag_months": Column(float, nullable=True),
        "base_index": Column(float, nullable=True),
        "floating_reference": Column(str, nullable=True),
        "spread_bp": Column(float, nullable=True),
        "is_green": Column(bool),
        "issuer_unit": Column(str),
        **_provenance(),
    },
    strict=True, coerce=True, unique=["iso3", "security_id"],
)

POSITIONS = pa.DataFrameSchema(
    {
        "iso3": Column(str, pa.Check.isin(ISO3)),
        "security_id": Column(str),
        "as_of": Column("datetime64[ns]"),
        "nominal_lcu_mn": Column(float),
        "nominal_uplifted_lcu_mn": Column(float, nullable=True),
        "nominal_issue_ccy_mn": Column(float, nullable=True),
        "official_holdings_lcu_mn": Column(float, nullable=True),
        "market_hands_lcu_mn": Column(float, nullable=True),
        "position_type": Column(str, pa.Check.isin(POSITION_TYPES)),
        "fx_rate": Column(float, nullable=True),
        "fx_source_id": Column(str, nullable=True),
        **_provenance(),
    },
    strict=True, coerce=True, unique=["iso3", "security_id", "as_of"],
)

FLOWS = pa.DataFrameSchema(
    {
        "iso3": Column(str, pa.Check.isin(ISO3)),
        "security_id": Column(str),
        "settlement_date": Column("datetime64[ns]"),
        "flow_type": Column(str, pa.Check.isin(FLOW_TYPES)),
        "seq": Column(int),
        "operation_date": Column("datetime64[ns]", nullable=True),
        "nominal_lcu_mn": Column(float),
        "cash_lcu_mn": Column(float, nullable=True),
        "price_pct": Column(float, nullable=True),
        "yield_pct": Column(float, nullable=True),
        "method": Column(str, nullable=True),
        "counter_security_id": Column(str, nullable=True),
        **_provenance(),
    },
    strict=True, coerce=True,
    unique=["iso3", "security_id", "settlement_date", "flow_type", "seq"],
)

REFERENCE_SERIES = pa.DataFrameSchema(
    {
        "series_id": Column(str),
        "date": Column("datetime64[ns]"),
        "value": Column(float),
        "unit": Column(str),
        "base_period": Column(str, nullable=True),
        "vintage_note": Column(str, nullable=True),
        **_provenance(),
    },
    strict=True, coerce=True, unique=["series_id", "date"],
)

INDEX_RATIOS = pa.DataFrameSchema(
    {
        "iso3": Column(str, pa.Check.isin(ISO3)),
        "security_id": Column(str),
        "date": Column("datetime64[ns]"),
        "reference_index": Column(float, nullable=True),
        "index_ratio": Column(float),
        "ratio_source": Column(str, pa.Check.isin(RATIO_SOURCES)),
        **_provenance(),
    },
    strict=True, coerce=True, unique=["iso3", "security_id", "date", "ratio_source"],
)

INTEREST_BY_SECURITY = pa.DataFrameSchema(
    {
        "iso3": Column(str, pa.Check.isin(ISO3)),
        "security_id": Column(str),
        "year": Column(int, pa.Check.in_range(1900, 2100)),
        "basis": Column(str, pa.Check.isin(INTEREST_BASES)),
        "coupon_lcu_mn": Column(float, nullable=True),
        "uplift_lcu_mn": Column(float, nullable=True),
        "discount_lcu_mn": Column(float, nullable=True),
        "floating_lcu_mn": Column(float, nullable=True),
        "premium_discount_amort_lcu_mn": Column(float, nullable=True),
        "total_lcu_mn": Column(float, nullable=True),
        "computability": Column(str, pa.Check.isin(COMPUTABILITY)),
        "reference_values_used": Column(str, nullable=True),
        "derivation": Column(str),
        **_provenance(),
    },
    strict=True, coerce=True, unique=["iso3", "security_id", "year", "basis"],
)


def _chain_schema(steps: list[str]) -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {
            "iso3": Column(str, pa.Check.isin(ISO3)),
            "year": Column(int, pa.Check.in_range(1900, 2100)),
            "step": Column(str, pa.Check.isin(steps)),
            "item": Column(str),
            "value_lcu_mn": Column(float, nullable=True),
            "item_type": Column(str, pa.Check.isin(ITEM_TYPES)),
            "item_source_id": Column(str, nullable=True),
            "basis": Column(str, nullable=True),
            **_provenance(),
        },
        strict=True, coerce=True, unique=["iso3", "year", "step", "item"],
    )


INTEREST_RECONCILIATION = _chain_schema(INTEREST_STEPS)
FINANCING_RECONCILIATION = _chain_schema(FINANCING_STEPS)

MATURITY_PROFILE = pa.DataFrameSchema(
    {
        "iso3": Column(str, pa.Check.isin(ISO3)),
        "as_of": Column("datetime64[ns]"),
        "instrument_class": Column(str, pa.Check.isin(INSTRUMENT_CLASSES)),
        "bucket": Column(str, pa.Check.isin(BUCKETS)),
        "nominal_lcu_mn": Column(float),
        "nominal_uplifted_lcu_mn": Column(float, nullable=True),
        "market_hands_lcu_mn": Column(float, nullable=True),
        "n_securities": Column(int),
        "weighted_residual_years": Column(float, nullable=True),
        **_provenance(),
    },
    strict=True, coerce=True, unique=["iso3", "as_of", "instrument_class", "bucket"],
)

ISSUANCE_BY_BUCKET = pa.DataFrameSchema(
    {
        "iso3": Column(str, pa.Check.isin(ISO3)),
        "year": Column(int, pa.Check.in_range(1900, 2100)),
        "instrument_class": Column(str, pa.Check.isin(INSTRUMENT_CLASSES)),
        "bucket": Column(str, pa.Check.isin(BUCKETS)),
        "gross_nominal_lcu_mn": Column(float),
        "gross_cash_lcu_mn": Column(float, nullable=True),
        "n_operations": Column(int),
        "weighted_residual_years_at_issue": Column(float, nullable=True),
        **_provenance(),
    },
    strict=True, coerce=True, unique=["iso3", "year", "instrument_class", "bucket"],
)

OFFICIAL_HOLDINGS = pa.DataFrameSchema(
    {
        "iso3": Column(str, pa.Check.isin(ISO3)),
        "holder": Column(str, pa.Check.isin(HOLDERS)),
        "security_id": Column(str),          # or "AGG"
        "as_of": Column("datetime64[ns]"),
        "nominal_lcu_mn": Column(float),
        "holding_type": Column(str, pa.Check.isin(HOLDING_TYPES)),
        **_provenance(),
    },
    strict=True, coerce=True, unique=["iso3", "holder", "security_id", "as_of"],
)

TABLES = {
    "debt_securities": SECURITIES,
    "debt_positions": POSITIONS,
    "debt_flows": FLOWS,
    "debt_reference_series": REFERENCE_SERIES,
    "debt_index_ratios": INDEX_RATIOS,
    "debt_interest_by_security": INTEREST_BY_SECURITY,
    "debt_interest_reconciliation": INTEREST_RECONCILIATION,
    "debt_financing_reconciliation": FINANCING_RECONCILIATION,
    "debt_maturity_profile": MATURITY_PROFILE,
    "debt_issuance_by_bucket": ISSUANCE_BY_BUCKET,
    "debt_official_holdings": OFFICIAL_HOLDINGS,
}
