"""The other side of the French balance sheet (D-S19-001): cash, financial
assets, net debt, stock-flow adjustments and what could be sold.

The scenario engine (`simulate.py`) rolls the Maastricht stock — a gross,
face-value liability — and reads sustainability off it. This module puts
the asset side beside it, for the France brief's section 7, and answers two
questions as generously to France as the official numbers allow:

1. If the government's income from its assets is counted against the
   interest bill, and its liquid assets against the debt, how much better
   does the arithmetic look (net debt, net interest, the primary balance
   before asset income)?
2. What could be sold or run down to retire debt in an extreme stress, on
   the national-accounts balance sheet (cash, paper, loans, equity) and off
   it (the Caisse des dépôts, the Banque de France's gold, the État's real
   estate), and what does each rung do to the debt path and the interest
   bill once the income forgone is counted?

Data: the general-government financial balance sheet from Eurostat
(gov_10a_ggfa: S13 consolidated and the sub-sectors, assets and liabilities
by ESA instrument, market value, 1998–2025), the property-income flows
(gov_10a_main: D.41 paid and received, D.42 dividends, D.45 rents), the
non-financial balance sheet (nama_10_nfa_bs) and the Maastricht debt levels
(gov_10dd_edpt1), all retrieved on 12 October 2026 into
`data/manual/FRA_balance_sheet_eurostat.csv` with the dataset's `updated`
stamp. Net debt is rebuilt from them on INSEE's definition — gross debt
less currency and deposits, debt securities and loans held — and checked
against INSEE's published figure (`INSEE_2025`). The stock-flow adjustment
history is Δ(Maastricht debt) + net lending, from the Eurostat levels and
the strict ledger; its 2021–2025 S.1311 components are read from
`deliverables/debt_financing_reconciliation.csv` (Eurostat EDP table 3).

Everything the engine does not produce and Eurostat does not publish is a
declared external fact, marked `ext` in the brief and listed in
`EXTERNAL`: INSEE's net-debt release, the État's own accounts (Compte
général de l'État 2025), the APE portfolio valuation, the Caisse des dépôts'
own funds and the Banque de France's gold. The sell-down rungs
(`LADDER`) and the amounts each run counts are declared numbers, argued
in the brief, not estimates.

Forward arithmetic (`net_view`): liquid assets are held constant in euros
(a cash buffer is not grown), equity holdings grow with nominal GDP (held
at market value, no excess return assumed), each class earns the yield its
2025 income implied (`AssetBlock`), and a sale removes the stock and, from
the half-year of the sale, its income. The income forgone is taken off the
primary balance (dividends and interest receivable are revenue), the
proceeds off the debt through the engine's stock-flow adjustment
(`Scenario.sfa_bn`). Nothing else moves: the spread paths are the
scenario's own, so a sale neither reassures nor alarms the market.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from ggfiscal.debt import simulate as sim

MANUAL = sim.ROOT / "data" / "manual" / "FRA_balance_sheet_eurostat.csv"
ISO = "FRA"
LIQUID = ("F2", "F3", "F4")               # INSEE's net-debt deductions: deposits, debt securities, loans

# --------------------------------------------------------------------------
# External facts (ext), EUR bn unless named otherwise
# --------------------------------------------------------------------------

INSEE_2025 = {                            # INSEE Informations rapides, Maastricht debt at end-2025
    "gross_bn": 3460.5, "gross_pct": 115.6, "net_bn": 3245.5, "net_pct": 108.4,
    "net_pct_2024": 104.5, "cash_change_bn": -19.9,
    "by_subsector": {                     # gross, net
        "État": (2822.7, 2727.3), "ODAC": (69.0, 37.4), "APUL": (275.7, 261.4), "ASSO": (293.1, 219.5)},
}
CGE_2025 = {                              # Compte général de l'État 2025, rapport de présentation (État only, accrual)
    "assets_bn": 1326.1, "tangible_bn": 604.6, "intangible_bn": 45.9, "financial_bn": 436.7,
    "participations_bn": 394.5, "controlled_equity_value_bn": 237.3, "non_controlled_net_bn": 157.2,
    "cash_active_bn": 22.9, "cash_active_2024_bn": 38.0, "cash_passive_bn": 150.2,
    "liabilities_bn": 3442.0, "financial_debt_bn": 2787.0, "net_position_bn": -2115.9,
    "pension_commitments_bn": 1428.0, "pension_civil_military_bn": 1366.0, "pension_discount_pct": 2.21,
    "pension_civil_military_2024_bn": 1573.0, "pension_discount_2024_pct": 1.38,
    "guaranteed_debt_bn": 237.1, "guarantees_general_interest_bn": 794.4, "regulated_savings_guarantee_bn": 699.1,
    "financial_commitments_bn": 597.0, "esm_callable_bn": 126.0,
}
APE_2025H1 = {"total_bn": 209.1, "listed_bn": 67.9, "listed_count": 10, "unlisted_count": 72}   # APE, 30 June 2025
CDC_2025 = {"own_funds_bn": 76.0, "contribution_to_state_bn": 3.337}                            # CDC results, 26 Mar 2026
BDF_GOLD_2025 = {"tonnes": 2436.8, "book_value_bn": 257.0}                                        # Banque de France annual report 2025

EXTERNAL = [
    "INSEE, Informations rapides, Maastricht debt at end-2025 (3,460.5 Md€, 115.6%; net debt 3,245.5 Md€, 108.4%; trésorerie −19.9 Md€).",
    "DGFiP, Compte général de l'État 2025, rapport de présentation (bilan at 31 Dec 2025, trésorerie active, participations, engagements hors bilan).",
    "Agence des participations de l'État, rapport d'activité 2025 (portfolio €209.1bn at 30 June 2025, listed €67.9bn), as relayed by economie.gouv.fr and MoneyVox.",
    "Caisse des dépôts, résultats 2025 (26 March 2026): €76bn aggregated own funds, €3.3bn paid to the État.",
    "Banque de France, rapport annuel 2025: 2,436.8 tonnes of gold, €257bn at end-2025 book value.",
]


# --------------------------------------------------------------------------
# History from the bundle and the Eurostat pull
# --------------------------------------------------------------------------

def eurostat() -> pd.DataFrame:
    d = pd.read_csv(MANUAL, low_memory=False, keep_default_na=False)
    d["year"] = d.year.astype(int)
    d["value_bn"] = d.value_mn.astype(float) / 1000.0
    return d


def updated() -> dict[str, str]:
    """The Eurostat `updated` stamp of each dataset in the manual file."""
    d = eurostat()
    return d.groupby("dataset").updated.first().to_dict()


def financial_balance_sheet(sector: str = "S13", finpos: str = "ASS") -> pd.DataFrame:
    """Year × ESA instrument, EUR bn, consolidated, market value (gov_10a_ggfa)."""
    d = eurostat().query("dataset == 'gov_10a_ggfa' and sector == @sector and finpos == @finpos")
    return d.pivot_table(index="year", columns="na_item", values="value_bn", aggfunc="first")


def gross_debt_levels(sector: str = "S13") -> pd.Series:
    """Maastricht debt, EUR bn, face value (gov_10dd_edpt1)."""
    d = eurostat().query("dataset == 'gov_10dd_edpt1' and sector == @sector and unit == 'MIO_EUR'")
    return d.set_index("year").value_bn.sort_index()


def property_income() -> pd.DataFrame:
    """D.41 paid and received, D.42 dividends received, D.45 rents, EUR bn (gov_10a_main, S13)."""
    d = eurostat().query("dataset == 'gov_10a_main'")
    return d.pivot_table(index="year", columns="na_item", values="value_bn", aggfunc="first")


def nonfinancial_assets() -> pd.DataFrame:
    """Produced (N1N) and non-produced (N2N, mostly land) non-financial assets, EUR bn (nama_10_nfa_bs, S13)."""
    d = eurostat().query("dataset == 'nama_10_nfa_bs'")
    return d.pivot_table(index="year", columns="na_item", values="value_bn", aggfunc="first")


def _gdp() -> pd.Series:
    s = pd.read_csv(sim.DELIV / "strict_FRA.csv").set_index("year")
    return (s["GDP - Gross domestic product at current market prices"] / 1000).dropna()


def _nlb() -> pd.Series:
    led = pd.read_csv(sim.DELIV / "balance_ledger.csv").query("iso3 == @ISO and variant == 'strict'").set_index("year")
    return led.nlb_lcu_mn / 1000


def history() -> pd.DataFrame:
    """One row per year, 1998–2025: the gross stock, the asset side by class,
    the two net measures, the property-income flows and the stock-flow
    adjustment, in EUR bn and % of GDP."""
    a = financial_balance_sheet("S13", "ASS")
    li = financial_balance_sheet("S13", "LIAB")
    cg = financial_balance_sheet("S1311", "ASS")
    gd = gross_debt_levels()
    pi = property_income()
    nfa = nonfinancial_assets()
    gdp, nlb = _gdp(), _nlb()
    years = [y for y in a.index if y in gd.index]
    h = pd.DataFrame(index=pd.Index(years, name="year"))
    h["gdp_bn"] = gdp.reindex(years)
    h["gross_bn"] = gd.reindex(years)
    for k in ("F2", "F3", "F4", "F5", "F51", "F52", "F8", "F"):
        h[f"{k.lower()}_bn"] = a[k].reindex(years)
    h["liquid_bn"] = sum(a[k] for k in LIQUID).reindex(years)
    h["net_bn"] = h.gross_bn - h.liquid_bn                         # INSEE's definition
    h["net_fin_bn"] = h.net_bn - h.f5_bn                           # also net of equity at market
    h["fin_liab_bn"] = li["F"].reindex(years)
    h["nfw_bn"] = li["BF90"].reindex(years)                        # net financial worth (Eurostat)
    h["nonfin_bn"] = (nfa["N1N"] + nfa["N2N"]).reindex(years)
    h["cash_cg_bn"] = cg["F2"].reindex(years)                      # S.1311: the Trésor's account, mostly
    h["interest_paid_bn"] = pi["D41PAY"].reindex(years)
    h["interest_recv_bn"] = pi["D41REC"].reindex(years)
    h["dividends_bn"] = pi["D42REC"].reindex(years)
    h["rents_bn"] = pi["D45REC"].reindex(years)
    h["asset_income_bn"] = h.interest_recv_bn + h.dividends_bn
    h["net_interest_bn"] = h.interest_paid_bn - h.asset_income_bn
    h["nlb_bn"] = nlb.reindex(years)
    h["sfa_bn"] = h.gross_bn.diff() + h.nlb_bn                      # Δdebt = −NLB + SFA
    for c in [c for c in h.columns if c.endswith("_bn") and c != "gdp_bn"]:
        h[c.replace("_bn", "_pct")] = 100 * h[c] / h.gdp_bn
    h["liquid_yield_pct"] = 100 * h.interest_recv_bn / ((h.liquid_bn + h.liquid_bn.shift()) / 2)
    h["equity_yield_pct"] = 100 * h.dividends_bn / ((h.f5_bn + h.f5_bn.shift()) / 2)
    return h


def sfa_components_s1311() -> pd.DataFrame:
    """The S.1311 stock-flow adjustment by component, 2021–2025, EUR bn, from
    the financing chain (Eurostat EDP table 3): positive = adds to debt
    beyond the deficit. The chain stores them as "less_…" items (sign −1 on
    the way from debt change to net borrowing), so the sign is flipped back."""
    f = pd.read_csv(sim.DELIV / "debt_financing_reconciliation.csv", low_memory=False)
    f = f[(f.iso3 == ISO) & (f.step == "B_s1311_b9") & f.item.str.startswith(("less_", "net_issuance_other"))]
    p = f.pivot_table(index="year", columns="item", values="value_lcu_mn", aggfunc="first") / 1000
    p = p.dropna(how="all")
    groups = {
        "cash_and_deposits": ["less_net_acquisition_currency_and_deposits"],
        "securities_and_loans": ["less_net_acquisition_debt_securities", "less_net_acquisition_loans"],
        "equity": ["less_net_acquisition_equity_and_investment_fund_shares"],
        "other_receivables": ["less_net_acquisition_other_accounts_receivable", "less_net_acquisition_other_financial_assets",
                              "less_net_acquisition_financial_derivatives"],
        "issuance_premia_and_accruals": ["less_sfa_adjustment_issuance_above_below_par", "less_sfa_adjustment_redemption_above_below_nominal",
                                         "less_sfa_adjustment_interest_accrued_less_paid"],
        "other": ["less_sfa_adjustment_foreign_currency_debt_revaluation", "less_sfa_adjustment_other_accounts_payable",
                  "less_sfa_adjustment_derivative_liabilities", "less_sfa_adjustment_other_liabilities",
                  "less_sfa_adjustment_other_volume_changes", "less_sfa_adjustment_sector_reclassification",
                  "less_statistical_discrepancy", "net_issuance_other_liabilities_currency_and_deposits",
                  "net_issuance_other_liabilities_loans"],
    }
    out = pd.DataFrame(index=p.index)
    for k, items in groups.items():
        cols = [c for c in items if c in p.columns]
        sign = pd.Series({c: (1.0 if c.startswith("net_issuance_other") else -1.0) for c in cols})
        out[k] = (p[cols] * sign).sum(axis=1)
    out["total"] = out.sum(axis=1)
    return out


def insee_check() -> dict:
    """Our Eurostat-built net debt against INSEE's published end-2025 figure."""
    h = history()
    r = h.loc[2025]
    return {"redbox_net_2025_bn": round(float(r.net_bn), 1), "insee_net_2025_bn": INSEE_2025["net_bn"],
            "gap_bn": round(float(r.net_bn) - INSEE_2025["net_bn"], 1),
            "redbox_gross_2025_bn": round(float(r.gross_bn), 1), "insee_gross_2025_bn": INSEE_2025["gross_bn"]}


# --------------------------------------------------------------------------
# The sell-down ladder (declared)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Rung:
    key: str
    label: str
    stock_bn: float               # end-2025, EUR bn
    where: str                    # "S13 balance sheet", "État accounts", "off balance sheet"
    basis: str
    liquidity: str                # how fast it turns into cash, in a stress
    asset_class: str              # "liquid" or "equity" (which yield is forgone), "none" for gold
    counted: dict                 # run name -> EUR bn sold in that run
    note: str
    ext: bool = False


def _ladder(h: pd.DataFrame) -> list[Rung]:
    r = h.loc[2025]
    cash_floor = 30.0
    listed = APE_2025H1["listed_bn"]
    unlisted = float(r.f51_bn) - listed
    return [
        Rung("cash", "Currency and deposits", float(r.f2_bn), "S13 balance sheet",
             f"Eurostat F.2, consolidated; the État's own account at the Banque de France is €{CGE_2025['cash_active_bn']:.0f}bn (CGE) — the rest is social-security and local cash",
             "days", "liquid",
             {"liquidity": float(r.f2_bn) - cash_floor, "realistic": float(r.f2_bn) - cash_floor,
              "maximal": float(r.f2_bn) - cash_floor, "extreme": float(r.f2_bn) - cash_floor},
             f"Run down to a €{cash_floor:.0f}bn operating floor. INSEE: cash fell €{-INSEE_2025['cash_change_bn']:.1f}bn in 2025 already."),
        Rung("paper", "Debt securities held", float(r.f3_bn), "S13 balance sheet",
             "Eurostat F.3, market value; mostly the social-security reserve funds' bond portfolios", "weeks", "liquid",
             {"liquidity": float(r.f3_bn), "realistic": float(r.f3_bn), "maximal": float(r.f3_bn), "extreme": float(r.f3_bn)},
             "Saleable at market; the reserves belong to the pension schemes, not the État."),
        Rung("loans", "Loans granted", float(r.f4_bn), "S13 balance sheet",
             "Eurostat F.4; loans to foreign states, students, public bodies, the EU recovery vehicles", "years", "liquid",
             {"liquidity": 0.0, "realistic": 50.0, "maximal": float(r.f4_bn), "extreme": float(r.f4_bn)},
             "Securitisable at a discount; counted half in the realistic run, whole in the maximal one."),
        Rung("listed", "Listed equity (APE portfolio)", listed, "État accounts",
             "APE, market value at 30 June 2025: Airbus, Safran, Thales, Engie, Orange, Renault, Eramet, FDJ, Air France-KLM, ADP",
             "months", "equity",
             {"liquidity": 0.0, "realistic": listed, "maximal": listed, "extreme": listed},
             "Every listed line sold, strategic or not: the 2027 programmes all touch some of these.", ext=True),
        Rung("funds", "Investment fund shares", float(r.f52_bn), "S13 balance sheet",
             "Eurostat F.52, market value; the FRR, AGIRC-ARRCO, CNAV and ODAC placements", "months", "equity",
             {"liquidity": 0.0, "realistic": 80.0, "maximal": float(r.f52_bn), "extreme": float(r.f52_bn)},
             "Half in the realistic run (the reserves of the complementary schemes are the social partners'); all in the maximal."),
        Rung("unlisted", "Unlisted and other equity", unlisted, "S13 balance sheet",
             "Eurostat F.51 less the listed lines; EDF, SNCF, La Poste, RATP, Bpifrance, the CDC and the Banque de France at own funds",
             "years", "equity",
             {"liquidity": 0.0, "realistic": 100.0, "maximal": unlisted, "extreme": unlisted},
             "Minority stakes (EDF, La Poste, RATP, SNCF subsidiaries) €100bn in the realistic run; the whole book value in the maximal — a value no buyer would pay."),
        Rung("cdc", "Caisse des dépôts own funds", CDC_2025["own_funds_bn"], "off balance sheet",
             "CDC aggregated own funds, end-2025; CDC is a financial corporation (S.12) under Parliament's protection, its contribution to the État €3.3bn in 2025",
             "a law", "equity",
             {"liquidity": 0.0, "realistic": 0.0, "maximal": 0.0, "extreme": 40.0},
             "An exceptional transfer of half its own funds in the extreme run; the État's claim is partly inside F.51 already, so this may double count.", ext=True),
        Rung("gold", "Banque de France gold", BDF_GOLD_2025["book_value_bn"], "off balance sheet",
             f"{BDF_GOLD_2025['tonnes']:,.0f} tonnes at end-2025 book value; realised gains flow to the Banque's result, then to the État as dividend",
             "a Eurosystem decision", "none",
             {"liquidity": 0.0, "realistic": 0.0, "maximal": 0.0, "extreme": 128.0},
             "Half the stock in the extreme run only: an NCB's gold operations need the ECB's assent (Statute art. 31) and the proceeds are the Banque's, not the Trésor's.", ext=True),
        Rung("nonfin", "Non-financial assets", float(r.nonfin_bn), "S13 balance sheet",
             "Eurostat nama_10_nfa_bs: produced assets (roads, schools, hospitals, military) and land at replacement cost",
             "decades", "none",
             {"liquidity": 0.0, "realistic": 0.0, "maximal": 0.0, "extreme": 0.0},
             "Not counted in any run: the État sells well under €1bn of real estate a year and the rest is the public service itself."),
    ]


def ladder() -> pd.DataFrame:
    h = history()
    rows = []
    for g in _ladder(h):
        rows.append({"key": g.key, "label": g.label, "stock_bn": g.stock_bn, "where": g.where, "basis": g.basis,
                     "liquidity": g.liquidity, "asset_class": g.asset_class, "ext": g.ext, "note": g.note,
                     **{f"sold_{k}_bn": v for k, v in g.counted.items()}})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# The asset block and the net view
# --------------------------------------------------------------------------

@dataclass
class AssetBlock:
    """Opening stocks (end-2025, Eurostat S13 consolidated) and the yields
    their 2025 income implied. Liquid assets held flat in euros; equity grows
    with nominal GDP."""
    liquid_bn: float
    equity_bn: float
    liquid_yield: float            # D.41 received / average liquid stock, 2025
    equity_yield: float            # D.42 received / average equity stock, 2025
    cdc_yield: float = CDC_2025["contribution_to_state_bn"] / CDC_2025["own_funds_bn"]
    equity_grows_with_gdp: bool = True


def asset_block() -> AssetBlock:
    h = history()
    r = h.loc[2025]
    return AssetBlock(liquid_bn=float(r.liquid_bn), equity_bn=float(r.f5_bn),
                      liquid_yield=float(r.liquid_yield_pct) / 100, equity_yield=float(r.equity_yield_pct) / 100)


RUNS = {                               # run name -> (label, sale years)
    "status_quo": ("Status quo (no sale)", ()),
    "liquidity": ("Liquidity drawdown", (2027, 2028)),
    "realistic": ("Realistic sell-down", (2027, 2028, 2029)),
    "maximal": ("Everything financial", (2027, 2028, 2029, 2030, 2031)),
    "extreme": ("Extreme: plus CDC and gold", (2027, 2028, 2029, 2030, 2031)),
}


def sales(run: str) -> pd.DataFrame:
    """EUR bn sold by year and asset class in `run`, spread evenly over its sale years."""
    label, years = RUNS[run]
    rows = []
    if years:
        for g in _ladder(history()):
            amt = g.counted.get(run, 0.0)
            if amt > 0:
                for y in years:
                    rows.append({"year": y, "rung": g.key, "asset_class": g.asset_class, "sold_bn": amt / len(years)})
    cols = ["year", "rung", "asset_class", "sold_bn"]
    return pd.DataFrame(rows, columns=cols)


def selldown_scenario(run: str, base_sc: sim.Scenario | None = None, block: AssetBlock | None = None) -> sim.Scenario:
    """The status-quo scenario with the run's sales as a negative stock-flow
    adjustment and the income forgone (half in the year of sale, the rest
    the year after) taken off the primary balance."""
    sc = base_sc or sim.scenario(sim.REFERENCE)
    block = block or asset_block()
    s = sales(run)
    if s.empty:
        return replace(sc, name=f"{sc.name}__{run}", label=RUNS[run][0])
    by_year = s.groupby("year").sold_bn.sum()
    yield_of = {"liquid": block.liquid_yield, "equity": block.equity_yield, "none": 0.0}
    s = s.assign(y=s.asset_class.map(yield_of))
    s.loc[s.rung == "cdc", "y"] = block.cdc_yield
    lost = (s.sold_bn * s.y).groupby(s.year).sum()           # full-year income lost per vintage
    changes = dict(sc.pb_changes())
    for y, v in lost.items():
        changes[int(y)] = changes.get(int(y), 0.0) - 0.5 * v
        changes[int(y) + 1] = changes.get(int(y) + 1, 0.0) - 0.5 * v
    return replace(sc, name=f"{sc.name}__{run}", label=RUNS[run][0],
                   sfa_bn={int(y): -float(v) for y, v in by_year.items()}, pb_change_bn=changes)


def net_view(res: pd.DataFrame, run: str = "status_quo", block: AssetBlock | None = None) -> pd.DataFrame:
    """Add the asset side to one engine run: the liquid and equity stocks
    after the run's sales, the income they pay, net debt on INSEE's
    definition, net financial debt (also net of equity), net interest and the
    primary balance before asset income. One row per year, like `res`."""
    block = block or asset_block()
    s = sales(run)
    sold = s.pivot_table(index="year", columns="asset_class", values="sold_bn", aggfunc="sum") if not s.empty else pd.DataFrame()
    r = res.sort_values("year").set_index("year").copy()
    liquid, equity, income = {}, {}, {}
    liq, eq = block.liquid_bn, block.equity_bn
    gdp_prev = sim.BASELINE.gdp[2025]
    for y in r.index:
        inc = block.liquid_yield * liq + block.equity_yield * eq          # on the opening stocks
        if block.equity_grows_with_gdp:
            eq *= r.gdp_bn[y] / gdp_prev
        sl = float(sold.get("liquid", pd.Series(dtype=float)).get(y, 0.0)) if not sold.empty else 0.0
        se = float(sold.get("equity", pd.Series(dtype=float)).get(y, 0.0)) if not sold.empty else 0.0
        inc -= 0.5 * (block.liquid_yield * sl + block.equity_yield * se)   # half a year lost on this year's sales
        liq, eq = liq - sl, eq - se
        liquid[y], equity[y], income[y] = liq, eq, inc
        gdp_prev = r.gdp_bn[y]
    r["liquid_assets_bn"] = pd.Series(liquid)
    r["equity_assets_bn"] = pd.Series(equity)
    r["asset_income_bn"] = pd.Series(income)
    r["net_debt_bn"] = r.debt_bn - r.liquid_assets_bn
    r["net_debt_pct_gdp"] = 100 * r.net_debt_bn / r.gdp_bn
    r["net_fin_debt_bn"] = r.net_debt_bn - r.equity_assets_bn
    r["net_fin_debt_pct_gdp"] = 100 * r.net_fin_debt_bn / r.gdp_bn
    r["net_interest_bn"] = r.gg_interest_bn - r.asset_income_bn
    r["net_interest_pct_gdp"] = 100 * r.net_interest_bn / r.gdp_bn
    r["pb_before_asset_income_pct"] = r.primary_balance_pct - 100 * r.asset_income_bn / r.gdp_bn
    r["run"] = run
    r["run_label"] = RUNS[run][0]
    return r.reset_index()


def run_all(base_sc: sim.Scenario | None = None) -> pd.DataFrame:
    """Every run on the status quo, with the net view. The register and the
    issuance mix are loaded once."""
    reg, mix = sim.load_register(), sim.issuance_mix()
    block = asset_block()
    out = []
    for run in RUNS:
        sc = selldown_scenario(run, base_sc, block)
        res = sim.run_scenario(sc, register=reg, mix=mix, feedback=False)
        out.append(net_view(res, run, block))
    return pd.concat(out, ignore_index=True)


def stabilising_pb(debt_pct: float, eff_rate_pct: float, nominal_growth_pct: float) -> float:
    """The primary balance (% of GDP) that holds a debt ratio flat:
    (i − g)/(1 + g) × d, all in per cent."""
    i, g = eff_rate_pct / 100, nominal_growth_pct / 100
    return 100 * (i - g) / (1 + g) * debt_pct / 100


def summary() -> dict:
    """The numbers the brief quotes, from the history, the ladder and the runs."""
    h = history()
    r25, r24 = h.loc[2025], h.loc[2024]
    chk = insee_check()
    runs = run_all()
    sq = runs[runs.run == "status_quo"].set_index("year")
    out = {
        "gross_2025_pct": float(r25.gross_pct), "net_2025_pct": float(r25.net_pct), "net_fin_2025_pct": float(r25.net_fin_pct),
        "gross_2025_bn": float(r25.gross_bn), "net_2025_bn": float(r25.net_bn),
        "liquid_2025_bn": float(r25.liquid_bn), "f2_2025_bn": float(r25.f2_bn), "f3_2025_bn": float(r25.f3_bn), "f4_2025_bn": float(r25.f4_bn),
        "equity_2025_bn": float(r25.f5_bn), "listed_2025_bn": APE_2025H1["listed_bn"], "f52_2025_bn": float(r25.f52_bn),
        "f8_2025_bn": float(r25.f8_bn), "fin_assets_2025_bn": float(r25.f_bn), "fin_assets_2025_pct": float(r25.f_pct),
        "nfw_2025_bn": float(r25.nfw_bn), "nfw_2025_pct": float(r25.nfw_pct), "nonfin_2025_bn": float(r25.nonfin_bn),
        "cash_cg_2025_bn": float(r25.cash_cg_bn), "cash_cg_2024_bn": float(r24.cash_cg_bn),
        "cash_s13_2020_bn": float(h.loc[2020].f2_bn), "cash_s13_2019_bn": float(h.loc[2019].f2_bn),
        "equity_2022_bn": float(h.loc[2022].f5_bn),
        "interest_paid_2025_bn": float(r25.interest_paid_bn), "interest_recv_2025_bn": float(r25.interest_recv_bn),
        "dividends_2025_bn": float(r25.dividends_bn), "rents_2025_bn": float(r25.rents_bn),
        "asset_income_2025_bn": float(r25.asset_income_bn), "asset_income_2025_pct": float(r25.asset_income_pct),
        "net_interest_2025_bn": float(r25.net_interest_bn), "net_interest_2025_pct": float(r25.net_interest_pct),
        "interest_paid_2025_pct": float(r25.interest_paid_pct),
        "liquid_yield_pct": float(r25.liquid_yield_pct), "equity_yield_pct": float(r25.equity_yield_pct),
        "eff_rate_gross_2025_pct": 100 * float(r25.interest_paid_bn / r24.gross_bn),
        "eff_rate_net_2025_pct": 100 * float(r25.net_interest_bn / r24.net_bn),
        "sfa_mean_1996_2025_pct": float(h.loc[1999:2025].sfa_pct.mean()),
        "sfa_2020_bn": float(h.loc[2020].sfa_bn), "sfa_2021_bn": float(h.loc[2021].sfa_bn),
        "sfa_2024_bn": float(h.loc[2024].sfa_bn), "sfa_2025_bn": float(h.loc[2025].sfa_bn),
        "sfa_cum_2021_2025_bn": float(h.loc[2021:2025].sfa_bn.sum()),
        "redbox_net_2025_bn": chk["redbox_net_2025_bn"], "insee_gap_bn": chk["gap_bn"],
        "equity_cagr_2022_2025_pct": 100 * (float(r25.f5_bn / h.loc[2022].f5_bn) ** (1 / 3) - 1),
    }
    # the stabilising primary balance in 2030, gross and net, status quo
    g30 = 100 * (sq.gdp_bn[2030] / sq.gdp_bn[2029] - 1)
    out["sq_2030_nominal_growth_pct"] = g30
    out["sq_2030_eff_rate_gross_pct"] = 100 * sq.gg_interest_bn[2030] / sq.debt_bn[2029]
    out["sq_2030_eff_rate_net_pct"] = 100 * sq.net_interest_bn[2030] / sq.net_debt_bn[2029]
    out["sq_2030_pb_star_gross"] = stabilising_pb(sq.debt_pct_gdp[2029], out["sq_2030_eff_rate_gross_pct"], g30)
    out["sq_2030_pb_star_net"] = stabilising_pb(sq.net_debt_pct_gdp[2029], out["sq_2030_eff_rate_net_pct"], g30)
    out["sq_2030_pb"] = float(sq.primary_balance_pct[2030])
    for y in (2027, 2030, 2035):
        out[f"sq_{y}_debt"] = float(sq.debt_pct_gdp[y]); out[f"sq_{y}_net_debt"] = float(sq.net_debt_pct_gdp[y])
        out[f"sq_{y}_net_fin_debt"] = float(sq.net_fin_debt_pct_gdp[y])
        out[f"sq_{y}_interest_bn"] = float(sq.gg_interest_bn[y]); out[f"sq_{y}_net_interest_bn"] = float(sq.net_interest_bn[y])
        out[f"sq_{y}_asset_income_bn"] = float(sq.asset_income_bn[y])
        out[f"sq_{y}_interest_pct"] = float(sq.gg_interest_pct_gdp[y]); out[f"sq_{y}_net_interest_pct"] = float(sq.net_interest_pct_gdp[y])
    for run in RUNS:
        if run == "status_quo":
            continue
        rr = runs[runs.run == run].set_index("year")
        sold = sales(run).sold_bn.sum()
        out[f"{run}_sold_bn"] = float(sold)
        out[f"{run}_sold_pct"] = 100 * float(sold) / sim.BASELINE.gdp[2025]
        for y in (2030, 2035):
            out[f"{run}_{y}_debt"] = float(rr.debt_pct_gdp[y])
            out[f"{run}_{y}_debt_gap"] = float(sq.debt_pct_gdp[y] - rr.debt_pct_gdp[y])
            out[f"{run}_{y}_interest_bn"] = float(rr.gg_interest_bn[y])
            out[f"{run}_{y}_interest_saved_bn"] = float(sq.gg_interest_bn[y] - rr.gg_interest_bn[y])
            out[f"{run}_{y}_income_lost_bn"] = float(sq.asset_income_bn[y] - rr.asset_income_bn[y])
            out[f"{run}_{y}_net_interest_bn"] = float(rr.net_interest_bn[y])
            out[f"{run}_{y}_net_interest_gain_bn"] = float(sq.net_interest_bn[y] - rr.net_interest_bn[y])
            out[f"{run}_{y}_deficit"] = float(rr.deficit_pct_gdp[y])
            out[f"{run}_{y}_deficit_gain"] = float(sq.deficit_pct_gdp[y] - rr.deficit_pct_gdp[y])
            out[f"{run}_{y}_net_debt"] = float(rr.net_debt_pct_gdp[y])
    return out


if __name__ == "__main__":       # pragma: no cover
    pd.set_option("display.width", 220)
    h = history()
    print(h.loc[2015:, ["gross_pct", "net_pct", "net_fin_pct", "liquid_bn", "f5_bn", "cash_cg_bn", "asset_income_bn",
                        "net_interest_bn", "sfa_bn", "sfa_pct"]].round(1))
    print(insee_check())
    print(sfa_components_s1311().round(1))
    print(ladder()[["label", "stock_bn", "sold_realistic_bn", "sold_maximal_bn", "sold_extreme_bn"]])
    r = run_all()
    print(r[r.year.isin([2027, 2030, 2035])][["run", "year", "debt_pct_gdp", "net_debt_pct_gdp", "gg_interest_bn",
                                             "asset_income_bn", "net_interest_bn", "deficit_pct_gdp"]].round(1).to_string())
