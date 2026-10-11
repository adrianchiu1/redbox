"""Stage ED3 (D-S17-016): the Belgian register from the Debt Agency's
outstanding page, on a synthetic page — no snapshot needed."""

from __future__ import annotations

import pandas as pd
import pytest

from ggfiscal.debt import register_bel as B

PAGE = """<html><body>
<p>OLOs &gt; Lines and outstanding at 01.10.2026 (trade date)</p>
<table><tr><th>Maturity Date</th><th>Coupon</th><th>ISIN Code</th><th>Nr</th>
<th>Net outstanding (EUR)**</th><th>Buy-backs&nbsp;in portfolio (EUR)</th>
<th>Capital Withdrawn by stripping (EUR)</th><th>%</th></tr>
<tr><td>22/06/2027</td><td>0.8</td><td>BE0000341504</td><td>81</td><td>16435000000</td><td>570000000</td><td></td><td></td></tr>
<tr><td>22/06/2071</td><td>0.65</td><td>BE0000353624</td><td>93</td><td>7370000000</td><td></td><td>91990000</td><td>1.25%</td></tr>
<tr><td></td><td></td><td></td><td></td><td>23805000000</td><td>570000000</td><td>91990000</td><td></td></tr>
</table>
<p>TCs &gt; Outstanding at 30.09.2026</p>
<table><tr><th>Maturity Date</th><th>ISIN Code</th><th>Net amount paid</th><th>Interest (EUR)</th><th>Nominal Amount (EUR)</th></tr>
<tr><td>15/10/2026</td><td>BE0312817894</td><td>7394996000</td><td>88003989</td><td>7483000000</td></tr>
<tr><td></td><td>TOTAL</td><td>7394996000</td><td>88003989</td><td>7483000000</td></tr>
</table>
<p>EMTN &gt; Outstanding at 10.06.2026</p>
<table><tr><th>Nr</th><th>Value Date</th><th>Maturity Date</th><th>ISIN Code</th><th>Currency</th><th>Amount</th><th>Coupon</th><th>EUR Equivalent</th></tr>
<tr><td>12</td><td>28/09/2010</td><td>28/09/2030</td><td>BE6203178288</td><td>EUR</td><td>175000000</td><td>Euribor6M +0.485</td><td>175000000</td></tr>
<tr><td>75</td><td>04/09/2025</td><td>16/08/2035</td><td>BE6367588231</td><td>USD</td><td>300000000</td><td>4.500</td><td>257113500</td></tr>
<tr><td>75B</td><td>09/09/2025</td><td>17/08/2035</td><td>BE6367588231</td><td>USD</td><td>350000000</td><td>4.500</td><td>300300300</td></tr>
<tr><td>40</td><td>01/03/2016</td><td>01/03/2036</td><td>BE6286998404</td><td>EUR</td><td>100000000</td><td>inflation coef. * 0.05</td><td>100000000</td></tr>
</table>
<p>Schuldscheine &gt; Outstanding at 31.05.2025</p>
<table><tr><th>Value Date</th><th>Maturity Date</th><th>Amount (EUR)</th><th>Coupon</th><th>Issue Price</th></tr>
<tr><td>20/01/2015</td><td>20/01/2045</td><td>14000000</td><td>1.733</td><td>100.54</td></tr>
</table></body></html>"""


@pytest.fixture
def page(tmp_path, monkeypatch):
    p = tmp_path / "bda.html"
    p.write_text(PAGE, encoding="utf-8")
    monkeypatch.setattr(B, "snap_path", lambda sid, part: p)
    monkeypatch.setattr(B, "_sha", lambda: "x")
    return p


def test_register_from_the_page(page):
    out = B.build("r")
    s = out["debt_securities"].set_index("security_id")
    p = out["debt_positions"].set_index("security_id")
    # OLO, TC and EMTN lines; the Schuldscheine (no ISIN, loans) stay out
    assert len(s) == 2 + 1 + 3
    assert s.loc["BE0000341504", "instrument_class"] == "fixed_bullet"
    assert s.loc["BE0312817894", "instrument_class"] == "bill"
    assert s.loc["BE6203178288", ["instrument_class", "floating_reference", "spread_bp"]].tolist() \
        == ["floating", "EA_EURIBOR_6M", 48.5]
    assert s.loc["BE6286998404", "instrument_class"] == "inflation_linked"
    # each table at its own date; net outstanding with the buy-backs alongside
    assert p.loc["BE0000341504", "as_of"] == pd.Timestamp("2026-10-01")
    assert p.loc["BE0000341504", "nominal_lcu_mn"] == pytest.approx(16435.0)
    assert p.loc["BE0000341504", "official_holdings_lcu_mn"] == pytest.approx(570.0)
    assert p.loc["BE0312817894", "as_of"] == pd.Timestamp("2026-09-30")
    # EMTN taps aggregate per ISIN: EUR equivalent and issue-currency amount
    usd = p.loc["BE6367588231"]
    assert usd["nominal_lcu_mn"] == pytest.approx(557.4138)
    assert usd["nominal_issue_ccy_mn"] == pytest.approx(650.0)
    assert s.loc["BE6367588231", "currency"] == "USD"
    assert s.loc["BE6367588231", "first_issue_date"] == pd.Timestamp("2025-09-04")
    # one ISIN, one maturity: the first tap's, with the page's spread noted
    assert s.loc["BE6367588231", "maturity_date"] == pd.Timestamp("2035-08-16")
    assert "maturity dates across taps" in s.loc["BE6367588231", "notes"]
    assert set(p.position_type) == {"office_snapshot"}
    assert out["debt_flows"].empty


def test_olo_lines_must_sum_to_the_page_total(page):
    page.write_text(PAGE.replace("<td>23805000000</td>", "<td>23905000000</td>"), encoding="utf-8")
    with pytest.raises(ValueError, match="page total"):
        B.build("r")
