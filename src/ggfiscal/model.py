"""§5 data model: the canonical long format and its pandera schema.

One row per (iso3, classification, line_code, year, series_variant). Stage 1
populates anchor history only (observation_type anchor_actual / derived_actual,
grade A, is_forecast False); later stages add stitched and forecast rows using
the same schema.
"""

from __future__ import annotations

import pandera.pandas as pa
from pandera.pandas import Column

COLUMNS = [
    "series_id", "iso3", "classification", "line_code", "line_level",
    "line_label", "year", "native_period", "source_period_basis",
    "value_lcu_mn", "currency",
    "gdp_lcu_mn", "gdp_source_id", "pct_gdp",
    "total_lcu_mn", "total_source_id", "pct_total",
    "series_variant", "observation_type",
    "anchor_source", "anchor_year", "anchor_value",
    "growth_source_id", "growth_rate",
    "residual_method", "interpolation_method", "period_conversion_method",
    "coverage_share", "coverage_share_year",
    "quality_grade", "crosswalk_version",
    "source_id", "source_release_date", "source_vintage", "source_status",
    "scenario_label", "concept_flag",
    "imf_value", "imf_diff_pct", "oecd_rs_value", "oecd_rs_diff_pct",
    "is_interpolated", "is_period_converted", "is_forecast",
    "run_id", "notes",
]

OBSERVATION_TYPES = [
    "anchor_actual", "level2_proxy_actual", "derived_actual", "imf_actual",
    "stitched_actual", "direct_forecast", "composite_forecast",
    "proxy_forecast", "official_benchmark_interpolation",
]

SCHEMA = pa.DataFrameSchema(
    {
        "series_id": Column(str),
        "iso3": Column(str, pa.Check.isin(["GBR", "FRA", "DEU"])),
        "classification": Column(str, pa.Check.isin(["COFOG", "ESA_REV", "BALANCE"])),
        "line_code": Column(str),
        "line_level": Column(str, pa.Check.isin(["1", "2", "derived", "total"])),
        "line_label": Column(str),
        "year": Column(int, pa.Check.in_range(1900, 2100)),
        "native_period": Column(str),
        "source_period_basis": Column(str, pa.Check.isin(["CY", "FY"])),
        "value_lcu_mn": Column(float, nullable=False),  # V14: missing stays missing (absent row)
        "currency": Column(str, pa.Check.isin(["GBP", "EUR"])),
        "gdp_lcu_mn": Column(float, nullable=True),
        "gdp_source_id": Column(str, nullable=True),
        "pct_gdp": Column(float, nullable=True),
        "total_lcu_mn": Column(float, nullable=True),
        "total_source_id": Column(str, nullable=True),
        "pct_total": Column(float, nullable=True),
        "series_variant": Column(str, pa.Check.isin(["strict", "maximum_extension"])),
        "observation_type": Column(str, pa.Check.isin(OBSERVATION_TYPES)),
        "anchor_source": Column(str, nullable=True),
        "anchor_year": Column(float, nullable=True),
        "anchor_value": Column(float, nullable=True),
        "growth_source_id": Column(str, nullable=True),
        "growth_rate": Column(float, nullable=True),
        "residual_method": Column(str, nullable=True),
        "interpolation_method": Column(str, nullable=True),
        "period_conversion_method": Column(str, nullable=True),
        "coverage_share": Column(float, nullable=True),
        "coverage_share_year": Column(float, nullable=True),
        "quality_grade": Column(str, pa.Check.isin(["A", "B", "C", "D"])),
        "crosswalk_version": Column(str, nullable=True),
        "source_id": Column(str),
        "source_release_date": Column(str, nullable=True),
        "source_vintage": Column(str, nullable=True),
        "source_status": Column(str, nullable=True),
        "scenario_label": Column(str, nullable=True),
        "concept_flag": Column(str, nullable=True),
        "imf_value": Column(float, nullable=True),
        "imf_diff_pct": Column(float, nullable=True),
        "oecd_rs_value": Column(float, nullable=True),
        "oecd_rs_diff_pct": Column(float, nullable=True),
        "is_interpolated": Column(bool),
        "is_period_converted": Column(bool),
        "is_forecast": Column(bool),
        "run_id": Column(str),
        "notes": Column(str, nullable=True),
    },
    strict=True,
    coerce=True,
    unique=["iso3", "classification", "line_code", "year", "series_variant"],
)
