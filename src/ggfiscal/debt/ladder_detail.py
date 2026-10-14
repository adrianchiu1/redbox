"""The sell-down ladder, line by line (D-S19-002): every asset the French
state could sell or run down, valued on the État's own accounts (Compte
général de l'État 2025, certified by the Cour des comptes), the APE's
portfolio valuation (30 June 2025) and Eurostat's balance sheet, with who
holds it, whether the État has the right to sell it, how fast it turns
into cash, what it pays the État, and the amount three runs would sell.

The amounts in `sold_*` follow the committee's rules of 2026-10-14
(`apply_rules`, D-S19-003) and drive the engine runs of the brief
(`balance_sheet.RUNS`): a liquidity drawdown, a realistic sell-down and a
distress run (everything the État can reach, by law where a law is needed).

Valuation rules, in order of preference:
  * listed equity: the APE's market value at 30 June 2025 (rapport de
    l'État actionnaire 2025, figure 5) for the five lines it publishes;
    the remaining lines share the published residual of the listed total
    (€67.9bn) in proportion to the État's stake × market capitalisation at
    that date (Redbox split, flagged);
  * unlisted equity: the CGE's valeur d'équivalence (the État's share of
    the entity's own funds on its latest accounts) for controlled entities,
    the CGE's net book value for non-controlled ones;
  * loans and cash: the CGE's net values at 31 December 2025;
  * pension reserves: each scheme's latest published reserves (AGIRC-ARRCO
    2025 accounts, ERAFP annual report 2025, FRR annual report 2025; the
    Cour des comptes' 2022 report for Ircantec, RCI and the professional
    schemes, end-2020 market values), split between direct bonds and
    fund shares so the totals match Eurostat's S.1314 F.3 and F.5;
  * CDC and Banque de France: their own 2025 accounts;
  * non-financial assets: Eurostat nama_10_nfa_bs (general government) and
    the CGE's categories (État).

Income to the État: dividends actually paid in 2025 where the amount is
public (EDF), else the État's stake × the dividend per share paid in 2025
for the 2024 financial year × the share count (flagged est.); the CDC's
versement; the Banque de France's nil dividend. Income the pension
schemes earn on their reserves is theirs, not the État's, and is shown as
the scheme's return in the note.

Right to sell: "yes" where the État owns the asset outright and no law
forbids the sale; "law" where a statute would have to change (SNCF's
capital is inalienable by the 2018 law, La Poste's must stay public, the
FRR's assets are earmarked to CADES, the pension schemes' reserves are the
schemes' own); "no" where the État has no claim (the reserves of the
paritarian and professional schemes, the Banque de France's gold under the
ESCB Statute, assets of the public domain, paid-in capital of
international institutions).
"""
from __future__ import annotations

import pandas as pd

GROUPS = ["cash", "paper", "loans", "listed", "funds", "unlisted", "cdc", "bdf", "nonfin"]
GROUP_LABEL = {
    "cash": "A · Cash: currency and deposits",
    "paper": "B · Debt securities held",
    "loans": "C · Loans granted",
    "listed": "D · Listed equity (APE portfolio)",
    "funds": "E · Investment fund shares",
    "unlisted": "F · Unlisted equity",
    "cdc": "G · Caisse des dépôts (off balance sheet)",
    "bdf": "H · Banque de France (off balance sheet)",
    "nonfin": "I · Non-financial assets",
}
RUN_LABEL = {"liquidity": "Liquidity drawdown", "realistic": "Realistic sell-down", "distress": "Distress: everything the État can reach"}

# One row per line: group, line, holder/where, stock (EUR bn), basis, as-of,
# can_sell, liquidity, income to the État (EUR bn a year), sales in the three
# runs (EUR bn), note, source, flags ("ext" = outside the bundle; "est" = a
# Redbox estimate inside a published total).
R = []


def _r(group, line, holder, stock, basis, as_of, can_sell, liquidity, income, sl, sr, se, note, source, flags=""):
    R.append({"group": group, "line": line, "holder": holder, "stock_bn": float(stock), "basis": basis, "as_of": as_of,
              "can_sell": can_sell, "liquidity": liquidity, "income_bn": None if income is None else float(income),
              "sold_liquidity_bn": float(sl), "sold_realistic_bn": float(sr), "sold_distress_bn": float(se),
              "note": note, "source": source, "flags": flags})


# --- A. cash ---------------------------------------------------------------
_r("cash", "Trésor single account at the Banque de France", "État (AFT)", 0.887,
   "CGE note 15: compte courant du Trésor, 31 Dec 2025 (€1.9bn a year earlier)", "2025-12-31", "yes", "same day", 0.01,
   0, 0, 0, "The operating balance; the AFT keeps it near zero and parks the buffer in placements (next line).",
   "CGE 2025 note 15.1", "ext")
_r("cash", "Trésor short-term placements (loans and reverse repos of État cash)", "État (AFT)", 24.1,
   "CGE note 15: placements de trésorerie, 31 Dec 2025 (€38.3bn a year earlier); Eurostat books most of this as F.4 short-term loans", "2025-12-31",
   "yes", "days", 0.55,
   10, 10, 15, "The real cash buffer. Run down to a €10bn floor in the liquidity and realistic runs, €9bn in the distress run; INSEE: general-government cash fell €19.9bn in 2025 already.",
   "CGE 2025 note 15.1; money-market yield ~2.3% (Redbox)", "ext,est")
_r("cash", "Other central-government units' deposits (CADES, Bpifrance EPIC, agencies, universities)", "ODAC", 11.0,
   "Eurostat S.1311 F.2 consolidated (€36.0bn) less the État's own cash above; not itemised by any source reached", "2025-12-31",
   "law", "weeks", 0.2,
   5, 5, 8, "Most public bodies must already deposit at the Trésor; what sits at banks could be centralised by extending the deposit obligation.",
   "Eurostat gov_10a_ggfa; CGE", "est")
_r("cash", "Local-government and social-security cash outside the Trésor", "S.1313, S.1314", 39.0,
   "Eurostat S.13 consolidated F.2 (€75.1bn) less S.1311 (€36.0bn): the sub-sectors' bank deposits net of what they hold at the Trésor", "2025-12-31",
   "no", "weeks", 0.0,
   0, 0, 10, "Not the État's money. The distress run assumes a law extending the Trésor deposit obligation to the social-security funds' and schemes' working cash (€10bn).",
   "Eurostat gov_10a_ggfa", "est")

# --- B. debt securities held ------------------------------------------------
_r("paper", "FRR (Fonds de réserve pour les retraites): bond portfolio", "FRR, S.1314", 8.0,
   "FRR net assets €20.7bn at end-2025 (annual report), of which about 40% in the hedging (bond) portfolio — Redbox split", "2025-12-31",
   "law", "weeks", 0.0,
   8, 8, 8, "The FRR is a public establishment whose assets the 2010 and 2020 social-security laws earmark to CADES (€1.45bn a year to 2033). Parliament has redirected them twice; it can again. The return (9.1% in 2025) accrues to the fund, not the budget.",
   "FRR rapport annuel 2025; Eurostat S.1314 F.3", "ext,est")
_r("paper", "ERAFP (civil-service additional pension): direct bonds", "ERAFP, S.1314", 25.0,
   "ERAFP net assets €53.6bn at end-2025 (annual report), about 45% in directly held bonds — Redbox split", "2025-12-31",
   "no", "weeks", 0.0,
   0, 0, 0, "A funded scheme: the assets back civil servants' accrued points (coverage ratio 146%). Taking them would be a default on the scheme's members, not a sale.",
   "RAFP rapport annuel 2025", "ext,est")
_r("paper", "AGIRC-ARRCO: directly held bonds", "AGIRC-ARRCO, S.1314", 5.0,
   "Reserves €91.2bn at end-2025 (2025 accounts); mostly held through dedicated funds (group E); a small direct bond book — Redbox split", "2025-12-31",
   "no", "weeks", 0.0,
   0, 0, 0, "Paritarian scheme under private law; the reserves are the scheme's. See group E for the bulk.",
   "AGIRC-ARRCO comptes 2025 (press); Cour des comptes 2022", "ext,est")
_r("paper", "Other schemes' direct bonds (Ircantec, RCI, professional schemes)", "S.1314", 3.0,
   "Residual of Eurostat S.1314 F.3 (€43bn) after the three lines above", "2025-12-31",
   "no", "weeks", 0.0,
   0, 0, 0, "Reserves of the complementary and professional schemes; theirs.",
   "Eurostat gov_10a_ggfa", "est")
_r("paper", "Paper held by the État, its agencies and local government", "S.1311, S.1313", 2.0,
   "Eurostat S.1311 F.3 (€1bn) + S.1313 F.3 (€1bn)", "2025-12-31",
   "yes", "days", 0.05,
   2, 2, 2, "Negligible; sold in every run.", "Eurostat gov_10a_ggfa", "")

# --- C. loans ---------------------------------------------------------------
_r("loans", "Bilateral loan to Greece (2010 Greek Loan Facility)", "État", 5.674,
   "CGE note 8.3: outstanding principal after €5.7bn of repayments", "2025-12-31",
   "yes", "years", 0.15,
   0, 0, 5, "Transferable in principle under the 2010 intercreditor agreement; no market. Pays 3-month Euribor + 50 bp. Counted in the distress run as a securitisation.",
   "CGE 2025 note 8.3.1.1", "ext")
_r("loans", "Loans to foreign states and banks via Natixis (programme 851, export-linked)", "État", 3.961,
   "CGE note 8.3: gross; €0.9bn of impairment sits across the foreign-loan lines", "2025-12-31",
   "yes", "years", 0.05,
   0, 0, 2, "Concessional, tied to French exports; securitisable at a deep discount.", "CGE 2025 note 8.3", "ext,est")
_r("loans", "Development-aid loans to foreign states (programme 852)", "État", 1.351,
   "CGE note 8.3", "2025-12-31", "yes", "years", 0.01,
   0, 0, 1, "Concessional; many under debt-relief (C2D) contracts.", "CGE 2025 note 8.3", "ext")
_r("loans", "Repayable advances conditional on success (France 2030, PIA, aerospace programmes)", "État", 4.224,
   "CGE note 8.3", "2025-12-31", "yes", "never", 0.0,
   0, 0, 0, "Repaid only if the financed project succeeds; no buyer.", "CGE 2025 note 8.3", "ext")
_r("loans", "Advances to Île-de-France Mobilités (COVID revenue shortfall)", "État", 1.975,
   "CGE note 8.3", "2025-12-31", "yes", "years", 0.0,
   0, 0, 0, "Repayable by a public body on a schedule; intra-public.", "CGE 2025 note 8.3", "ext")
_r("loans", "Loans to private bodies and other État loans and advances", "État", 4.6,
   "CGE note 8.3: organismes privés €3.5bn, other €0.4bn, local authorities €0.1bn, individuals, accrued interest", "2025-12-31",
   "yes", "years", 0.1,
   0, 1, 3, "Mixed book; securitisable in part.", "CGE 2025 note 8.3", "ext,est")
_r("loans", "Other central-government units' loan books (Action Logement Services' housing loans, State funds managed by Bpifrance and the CDC, agencies)", "ODAC", 50.0,
   "Eurostat S.1311 F.4 (€93bn) less the État's loans above (€18.8bn net) and the Trésor's placements (group A); Action Logement's loan book was €10.9bn in 2022", "2025-12-31",
   "law", "years", 0.5,
   0, 0, 10, "Not itemised by any source reached. Mostly housing and SME loans at below-market rates; securitisable at a discount; counted €10bn in the distress run.",
   "Eurostat gov_10a_ggfa; Action Logement 2022 accounts (press)", "est")
_r("loans", "Local-government and social-security loans", "S.1313, S.1314", 14.0,
   "Eurostat S.1313 F.4 (€12bn) + S.1314 F.4 (€2bn)", "2025-12-31", "no", "years", 0.0,
   0, 0, 0, "Loans to their own satellites; not the État's.", "Eurostat gov_10a_ggfa", "")

# --- D. listed equity (APE, 30 June 2025) -----------------------------------
# stake, value, dividend per share paid in 2025 (FY2024), share count (mn)
LISTED = [
    ("Airbus", "10.83% via SOGEPA", 15.215, 3.00, 790, "APE figure 5", "The Franco-German-Spanish shareholder pact fixes the three states' parity; a French sale would need Berlin and Madrid to follow or waive. Defence."),
    ("Thales", "26.60% via TSA", 13.675, 3.70, 206, "APE figure 5", "Shareholder pact with Dassault Aviation; golden-share-type rights on the defence business. The State's veto, not the stake, is what matters."),
    ("Safran", "11.20%", 13.533, 2.90, 420, "APE figure 5", "No pact; the State keeps board seats by decree. Half sold in the realistic run."),
    ("Engie", "23.64%", 11.471, 1.48, 2435, "APE figure 5", "The 2015 law lets the State go below a third; no blocking rule. Sold whole in the realistic run."),
    ("Orange", "13.39% (Bpifrance holds another 9.6%)", 4.600, 0.75, 2660, "APE figure 5", "No legal floor; sold whole in the realistic run."),
    ("Aéroports de Paris", "50.63%", 5.5, 3.00, 99, "Redbox split of the APE residual", "The 2019 PACTE law authorised the privatisation; the 2019 referendum petition stalled it politically. Sold whole in the realistic run."),
    ("Renault", "15.01%", 1.9, 2.20, 295, "Redbox split of the APE residual", "Alliance pact with Nissan limits a sale's timing, not its possibility."),
    ("FDJ United", "20.46%", 1.2, 2.05, 191, "Redbox split of the APE residual", "The 2019 law sets no floor; the State keeps the regulatory grip through the gambling licence."),
    ("Air France-KLM", "27.98%", 0.6, 0.0, 258, "Redbox split of the APE residual", "Parity with the Dutch state; no dividend; sold in the realistic run at a small value."),
    ("Eramet", "27.13% via FSI Equation", 0.4, 0.0, 29, "Redbox split of the APE residual", "Pact with the Duval family; critical minerals. No 2024 dividend."),
    ("Eutelsat", "29.65% (acquired July 2025)", 0.6, 0.0, 480, "CGE 2025 note 8.1.2.3: net book value €597m on a €1,008m cost", "Bought after the APE's June 2025 valuation; sovereignty asset; no dividend."),
]
_REAL = {"Airbus": 0.0, "Thales": 0.0, "Safran": 6.8, "Engie": 11.471, "Orange": 4.6, "Aéroports de Paris": 5.5,
         "Renault": 1.9, "FDJ United": 1.2, "Air France-KLM": 0.6, "Eramet": 0.4, "Eutelsat": 0.0}
for name, stake, value, dps, shares, basis, note in LISTED:
    pct = float(stake.split("%")[0]) / 100
    income = pct * shares * dps / 1000
    liq = "months (block trade)" if value > 2 else "weeks"
    can = "yes" if name not in ("Airbus", "Thales", "Air France-KLM") else "yes, pact"
    _r("listed", name, f"État {stake}", value,
       f"{basis}, market value at 30 June 2025" if "Redbox" not in basis else f"{basis} (€67.9bn total, €9.4bn unallocated), stake × market capitalisation at 30 June 2025",
       "2025-06-30", can, liq, income, 0, _REAL[name], value,
       f"{note} Dividend: {stake.split(' ')[0]} of {shares:,}m shares × €{dps:.2f} paid in 2025." if dps else note,
       "APE rapport de l'État actionnaire 2025; CGE 2025 note 8.1.2.3; company dividend notices", "ext,est")

# --- E. investment fund shares ----------------------------------------------
_r("funds", "AGIRC-ARRCO reserves held through funds", "AGIRC-ARRCO, S.1314", 86.0,
   "Reserves €91.2bn at end-2025 (2025 accounts) less the direct bonds in group B — Redbox split", "2025-12-31",
   "no", "months", 0.0,
   0, 0, 86.0, "The paritarian complementary scheme's buffer (about nine months of benefits). The State tried to take €1–3bn a year in 2023 and backed down; the reserves are the social partners'. The distress run assumes a law taking them, which the Conseil constitutionnel might not allow. Return accrues to the scheme (about 3% a year in cash income).",
   "AGIRC-ARRCO comptes 2025 (press); Cour des comptes, Les réserves des caisses de retraite, 2022", "ext,est")
_r("funds", "ERAFP: equities and funds", "ERAFP, S.1314", 28.6,
   "ERAFP net assets €53.6bn less the direct bonds in group B — Redbox split", "2025-12-31",
   "no", "months", 0.0,
   0, 0, 0, "Funded rights; see group B.", "RAFP rapport annuel 2025", "ext,est")
_r("funds", "FRR: performance portfolio (equities, funds)", "FRR, S.1314", 12.7,
   "FRR net assets €20.7bn less the bond portfolio in group B — Redbox split", "2025-12-31",
   "law", "months", 0.0,
   0, 12.7, 12.7, "As group B: Parliament's to redirect. Sold whole in the realistic run (it is already being drawn down for CADES).",
   "FRR rapport annuel 2025", "ext,est")
_r("funds", "Ircantec reserves", "Ircantec (managed by the CDC), S.1314", 12.9,
   "Cour des comptes 2022: €12.9bn at end-2020 market value; no 2025 figure reached", "2020-12-31",
   "law", "months", 0.0,
   0, 0, 12.9, "A public scheme for contractual public employees, piloted by decree; a law could take the reserves, which back no individual rights. Counted in the distress run only.",
   "Cour des comptes, 2022", "ext")
_r("funds", "RCI (self-employed) and the professional schemes (Cipav, Carmf, CRPNPAC and others)", "S.1314", 36.0,
   "Cour des comptes 2022: RCI €17.1bn, Cipav €7.2bn, Carmf €6.4bn, CRPNPAC €5.2bn at end-2020 market value, plus smaller schemes; residual to Eurostat S.1314 F.5", "2020-12-31",
   "no", "months", 0.0,
   0, 0, 0, "Reserves of autonomous schemes funded by their members; not counted in any run.", "Cour des comptes, 2022", "ext,est")
_r("funds", "State funds without legal personality managed by Bpifrance and the CDC (France 2030, PIA, guarantee funds)", "État", 10.8,
   "CGE note 8.4: FSPJ at net asset value — Bpifrance €8.2bn (guarantee funds €3.6bn, France 2030/PIA funds €3.6bn), CDC €2.6bn", "2025-12-31",
   "yes", "years", 0.1,
   0, 2, 5, "The État's own. The guarantee funds back live guarantees; the investment funds hold venture stakes saleable over years.",
   "CGE 2025 note 8.4", "ext")
_r("funds", "Local-government fund holdings and other", "S.1313, other", 7.0,
   "Residual of Eurostat S.13 F.52 (€161bn) after the lines above", "2025-12-31", "no", "months", 0.0,
   0, 0, 0, "Residual; not the État's.", "Eurostat gov_10a_ggfa", "est")

# --- F. unlisted equity (CGE valeur d'équivalence, 31 Dec 2025) --------------
_r("unlisted", "EDF", "État 100%", 68.452,
   "CGE note 8.1.1: valeur d'équivalence (État's share of own funds, TSDI excluded since 2024)", "2025-12-31",
   "yes", "years (IPO)", 2.0,
   0, 15, 68.452, "Dividend €2.0bn paid in 2025 for 2024 (the first in ten years), €1.0bn for 2025. Re-listing a minority is possible (the 2023 buy-out cost €9.7bn for 16%); the realistic run sells a quarter at a discount to equity value. Nuclear liabilities make the book value the ceiling, not the price.",
   "CGE 2025; EDF AGM 2026 (press)", "ext")
_r("unlisted", "SNCF", "État 100%", 27.841,
   "CGE note 8.1.1: valeur d'équivalence (with reservation on the accounts)", "2025-12-31",
   "law", "years", 1.0,
   0, 3, 27.841, "The 2018 railway law makes SNCF SA's capital inalienable; subsidiaries (Geodis, Keolis 70%) are saleable, hence €3bn in the realistic run. The dividend (about €1bn a year) is recycled into SNCF Réseau through the fonds de concours, so the État's net income is nil.",
   "CGE 2025; FIPECO on the 2023 dividend", "ext,est")
_r("unlisted", "EPIC Bpifrance (49.3% of Bpifrance SA; the CDC holds 49.3%)", "État 100% of the EPIC", 15.531,
   "CGE note 8.1.1: valeur d'équivalence", "2025-12-31",
   "law", "years", 0.2,
   0, 0, 15.531, "Bpifrance SA's statute and the CDC's parity make a private sale a legislative project; its dividend to the EPIC is small (net profit €0.5bn in 2025).",
   "CGE 2025; Bpifrance results 2025 (press)", "ext,est")
_r("unlisted", "La Poste SA", "État 34% (CDC 66%)", 4.943,
   "CGE note 8.1.2.3: net book value", "2025-12-31",
   "law", "years", 0.1,
   0, 0, 4.943, "The 2010 law requires a wholly public shareholding; a sale to the CDC is intra-public and raises nothing consolidated. Dividend to the État about €0.1–0.15bn (FY2022: €421m in total).",
   "CGE 2025; La Poste URD 2025", "ext,est")
_r("unlisted", "RATP", "État 100% (EPIC)", 5.577,
   "CGE note 8.1.1: valeur d'équivalence", "2025-12-31",
   "law", "years", 0.0,
   0, 1, 5.577, "EPIC; RATP Dev and other subsidiaries are saleable (€1bn in the realistic run). No dividend.",
   "CGE 2025", "ext")
_r("unlisted", "Caisse centrale de réassurance (CCR)", "État 100%", 3.366,
   "CGE note 8.1.1: valeur d'équivalence", "2025-12-31",
   "yes", "years", 0.1,
   0, 0, 3.366, "A reinsurer whose natural-catastrophe book carries the State guarantee; saleable in principle, worth less without the guarantee.",
   "CGE 2025", "ext,est")
_r("unlisted", "Orano", "État 90.33%", 2.715,
   "CGE note 8.1.1: valeur d'équivalence", "2025-12-31",
   "yes", "years", 0.0,
   0, 0, 2.715, "Nuclear fuel cycle; no dividend; strategic.", "CGE 2025", "ext")
_r("unlisted", "GIAT Industries (KNDS stake)", "État 100% of GIAT", 2.289,
   "CGE note 8.1.1: valeur d'équivalence", "2025-12-31",
   "yes", "years", 0.05,
   0, 0, 2.289, "Defence (KNDS); an IPO of KNDS has been discussed by its Franco-German owners.", "CGE 2025", "ext,est")
_r("unlisted", "Naval Group", "État 62.25% (Thales 35%)", 1.235,
   "CGE note 8.1.1: valeur d'équivalence", "2025-12-31",
   "yes", "years", 0.05,
   0, 0, 1.235, "Defence; Thales has pre-emption rights. Small dividend.", "CGE 2025", "ext,est")
_r("unlisted", "Chantiers de l'Atlantique", "État 84.34%", 0.792,
   "CGE note 8.1.1: valeur d'équivalence", "2025-12-31",
   "yes", "years", 0.0,
   0, 0.792, 0.792, "A sale (to Fincantieri) was attempted and abandoned in 2021; sold in the realistic run.", "CGE 2025", "ext")
_r("unlisted", "Société pour le logement intermédiaire (SLI) and other investment vehicles (Imprimerie nationale, LFB, IFPEN)", "État 100%", 4.1,
   "CGE note 8.1.1: SLI €1.1bn, Imprimerie nationale €1.1bn, LFB €0.7bn, IFPEN €0.9bn, others", "2025-12-31",
   "yes", "years", 0.0,
   0, 0.5, 4.1, "The SLI's housing units are saleable; the rest are policy vehicles.", "CGE 2025", "ext,est")
_r("unlisted", "Dexia Holding (run-off)", "État 46.81%", 2.261,
   "CGE note 8.1.2.3: net book value", "2025-12-31", "no", "never", 0.0,
   0, 0, 0, "A bank in run-off under State guarantees; nothing to sell.", "CGE 2025", "ext")
_r("unlisted", "Public establishments that are the State itself (CEA €14.2bn, AFD €9.5bn, ONF €9.5bn, VNF €5.2bn, ports €6.7bn, universities, CNES, BnF, CNRS, EPFs, agencies, TELT)", "État 100%", 100.0,
   "CGE note 8.1.1: valeur d'équivalence of the remaining controlled entities (total controlled €237.3bn less the enterprises above)", "2025-12-31",
   "no", "never", 0.0,
   0, 0, 0, "Research bodies, forests, waterways, universities, agencies: their own funds are buildings and endowments, not a stake anyone buys. The AFD is a policy bank. Not counted in any run.",
   "CGE 2025", "ext,est")
_r("unlisted", "International institutions (IMF quota €18.6bn, ESM €16.3bn, EIB €3.5bn, development banks)", "État", 43.082,
   "CGE note 8.1.2.2: paid-in capital, net", "2025-12-31", "no", "never", 0.0,
   0, 0, 0, "Paid-in capital of treaty institutions; not transferable.", "CGE 2025", "ext")
_r("unlisted", "Local-government and social-security equity (SEMs, social-housing bodies, hospitals, the schemes' direct equities)", "S.1313, S.1314", 160.0,
   "Eurostat S.1313 F.5 (€80bn) + S.1314 F.51 (part of €176bn), at own funds", "2025-12-31", "no", "never", 0.0,
   0, 0, 0, "Not the État's; largely hospitals and housing bodies at own funds.", "Eurostat gov_10a_ggfa", "est")

# --- G. Caisse des dépôts ---------------------------------------------------
_r("cdc", "CDC Section générale: own funds (social accounts, incl. FRBG)", "CDC, S.12 — under Parliament's protection", 25.717,
   "CDC rapport financier 2025: capitaux propres hors FRBG €25,161m + FRBG €556m", "2025-12-31",
   "law", "a decree sets the annual versement; a law for more", 3.337,
   0, 0, 5, "The État's claim is the annual versement (a fraction of the result plus the CRIS, €3.3bn in 2025 across both sections), set by decree after the Commission de surveillance's opinion; the own funds are the Caisse's, supervised by the ACPR. The distress run assumes an exceptional €5bn distribution of surplus over the prudential model. In the État's own accounts the CDC is carried at €31.6bn.",
   "CDC rapport financier 2025; CGE 2025 note 8.1.2.1", "ext")
_r("cdc", "CDC Fonds d'épargne: own funds (incl. FRBG)", "CDC, S.12", 17.742,
   "CDC rapport financier 2025: capitaux propres hors FRBG €11,592m + FRBG €6,150m", "2025-12-31",
   "law", "a decree sets the annual prélèvement", 0.0,
   0, 0, 0, "Backs the State guarantee on €699bn of regulated savings. The December 2025 rule takes 50% of the current result each year, floored at 0.10% of centralised deposits, capped so that the CET1 ratio stays 5% above the ACPR requirement: the surplus is already being taken. Income is counted in the line above.",
   "CDC rapport financier 2025 §2.1.1.2", "ext")
_r("cdc", "CDC group consolidated equity (IFRS), for reference", "CDC group", 75.6,
   "CDC rapport financier 2025: total capitaux propres €75,599m, of which part du Groupe €58,312m (incl. unrealised gains)", "2025-12-31",
   "no", "—", None,
   0, 0, 0, "Includes La Poste, CNP and Bpifrance at consolidation; overlaps the lines above and group F. Shown so the €76bn headline is not added to anything.",
   "CDC rapport financier 2025", "ext")

# --- H. Banque de France ----------------------------------------------------
_r("bdf", "Gold: 2,436.8 tonnes", "Banque de France", 257.0,
   "Banque de France rapport annuel 2025: book value at end-2025 market price", "2025-12-31",
   "no", "a Eurosystem decision", 0.0,
   0, 0, 0, "The Banque's, not the Trésor's. Article 123 TFEU and article 31 of the ESCB Statute (ECB assent for reserve operations above a threshold); unrealised gains sit in the revaluation account and cannot be distributed; realised gains go to the result, then to reserves and a dividend. Dividend nil since the 2022 accounts; €1.5bn of corporate tax in 2025. In the État's accounts the Banque is carried at €26.3bn.",
   "Banque de France résultats 2025; CGE 2025 note 8.1.2.1", "ext")
_r("bdf", "Situation nette (net position) incl. revaluation accounts, for reference", "Banque de France", 283.4,
   "Banque de France résultats 2025 (€202.7bn at end-2024); RRRODE reserve €11.4bn", "2025-12-31",
   "no", "—", None,
   0, 0, 0, "Mostly the gold revaluation; the 2025 result of €8.1bn cleared the 2024 loss carried forward. Not additive to the gold line.",
   "Banque de France résultats 2025", "ext")

# --- I. non-financial assets ------------------------------------------------
NONFIN_GG = [  # Eurostat nama_10_nfa_bs, S13, end-2025, EUR bn
    ("Dwellings (N.111)", 88.0), ("Other buildings (N.1121)", 390.0), ("Other structures: roads, networks, rail (N.1122)", 1040.0),
    ("Machinery, equipment and weapons systems (N.113–N.114)", 88.0), ("Intellectual property products (N.117)", 153.0),
    ("Inventories (N.12)", 62.0), ("Land (N.211)", 1094.0),
]
for lab, v in NONFIN_GG:
    _r("nonfin", f"General government: {lab}", "S.13 (reference, not summed)", v, "Eurostat nama_10_nfa_bs, replacement cost", "2025-12-31",
       "no", "—", None, 0, 0, 0, "The public service itself (roads, schools, hospitals, barracks); local government owns most buildings. Overlaps the État's categories below, so shown for reference only.", "Eurostat nama_10_nfa_bs", "")
NONFIN_ETAT = [  # CGE note 7, net values, EUR bn
    ("buildings (parc immobilier, prisons)", 59.082, "yes", 0, 1, 2, "Surplus real estate: €0.9bn is booked as ready for sale (note 7.11); the État sells a few hundred million a year. €1bn in the realistic run, €2bn in the distress run."),
    ("land", 11.181, "yes", 0, 0, 0, "Mostly the land under the buildings and military land."),
    ("road infrastructure", 153.631, "no", 0, 0, 0, "Public domain; the non-concessioned network."),
    ("concession assets: motorways €200.4bn, hydro €57.8bn, rail tunnels €6.5bn, airports €5.7bn, Stade de France", 276.097, "law", 0, 0, 0,
     "The concessions revert in 2031–2036 (motorways); a re-concession or a sale of future tolls is the one large non-financial receipt available this decade. Not counted here: its value is a flow the engine does not model."),
    ("equipment, mostly military", 51.009, "no", 0, 0, 0, "Weapons systems; nothing to sell."),
    ("assets under construction", 50.446, "no", 0, 0, 0, "Work in progress."),
]
for lab, v, can, sl, sr, se, note in NONFIN_ETAT:
    _r("nonfin", f"État: {lab}", "État", v, "CGE 2025 note 7, net book value", "2025-12-31", can, "years" if can == "yes" else "decades",
       0.0, sl, sr, se, note, "CGE 2025 note 7", "ext")


# Committee rules of 2026-10-14 (D-S19-003) for the three runs, applied to
# every line after the rows above are declared; the declared amounts are
# kept only where the rules say "otherwise, stay with your assumptions".
#   no                       -> 0 / 0 / 0
#   law                      -> 0 / 0 / half the stock
#   yes, cash: Trésor placements 10 / 10 / the whole buffer; ODAC deposits 0 / 0 / 10
#   yes, loans               -> 0 / 0 / half the stock (nothing where nothing is recoverable)
#   yes, pact (listed)       -> 0 / 0 / half the stock
#   yes, listed              -> 0 / half / whole
#   yes, unlisted            -> 0 / 0 / whole
#   everything else "yes"    -> as declared
RULE_OVERRIDES = {
    "Trésor short-term placements (loans and reverse repos of État cash)": (10.0, 10.0, 24.1),
    "Other central-government units' deposits (CADES, Bpifrance EPIC, agencies, universities)": (0.0, 0.0, 10.0),
}


def apply_rules(row: dict) -> dict:
    r = dict(row)
    st = r["stock_bn"]
    if r["line"] in RULE_OVERRIDES:
        sl, sr, se = RULE_OVERRIDES[r["line"]]; rule = "committee: stated"
    elif r["can_sell"] == "no":
        sl, sr, se = 0.0, 0.0, 0.0; rule = "no -> 0/0/0"
    elif r["can_sell"] == "law":
        sl, sr, se = 0.0, 0.0, st / 2; rule = "law -> 0/0/half"
    elif r["group"] == "loans":
        half = 0.0 if r["liquidity"] == "never" else st / 2
        sl, sr, se = 0.0, 0.0, half; rule = "yes, loan -> 0/0/half"
    elif r["group"] == "listed" and r["can_sell"] == "yes, pact":
        sl, sr, se = 0.0, 0.0, st / 2; rule = "yes, pact -> 0/0/half"
    elif r["group"] == "listed":
        sl, sr, se = 0.0, st / 2, st; rule = "yes, listed -> 0/half/whole"
    elif r["group"] == "unlisted":
        sl, sr, se = 0.0, 0.0, st; rule = "yes, unlisted -> 0/0/whole"
    else:
        sl, sr, se = r["sold_liquidity_bn"], r["sold_realistic_bn"], r["sold_distress_bn"]; rule = "as declared"
    r.update(sold_liquidity_bn=float(sl), sold_realistic_bn=float(sr), sold_distress_bn=float(se), rule=rule)
    return r


def ladder_detail() -> pd.DataFrame:
    d = pd.DataFrame([apply_rules(r) for r in R])
    d["group_label"] = d.group.map(GROUP_LABEL)
    d["asset_class"] = d.group.map({"cash": "liquid", "paper": "liquid", "loans": "liquid", "listed": "equity", "funds": "equity",
                                    "unlisted": "equity", "cdc": "equity", "bdf": "none", "nonfin": "nonfin"})
    d["yield_pct"] = 100 * d.income_bn / d.stock_bn
    # reference rows (flagged by a None income and a "—" liquidity) are not summed
    d["reference_only"] = d.liquidity.eq("—")
    return d


def totals(d: pd.DataFrame | None = None) -> pd.DataFrame:
    """Stock, income and the three runs' sales by group and in total, excluding
    reference-only rows and, for the stock, the general-government
    non-financial rows (the État's categories are the ones with a sale)."""
    d = ladder_detail() if d is None else d
    s = d[~d.reference_only].copy()
    cols = ["stock_bn", "income_bn", "sold_liquidity_bn", "sold_realistic_bn", "sold_distress_bn"]
    g = s.groupby("group")[cols].sum().reindex(GROUPS)
    g.loc["total"] = g.sum()
    return g


def runs_from_detail() -> dict[str, float]:
    """The three runs' totals from the line-by-line table (EUR bn)."""
    t = totals()
    return {"liquidity": float(t.loc["total", "sold_liquidity_bn"]), "realistic": float(t.loc["total", "sold_realistic_bn"]),
            "distress": float(t.loc["total", "sold_distress_bn"])}


if __name__ == "__main__":       # pragma: no cover
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
    d = ladder_detail()
    print(d[["group", "line", "stock_bn", "can_sell", "income_bn", "yield_pct", "sold_liquidity_bn", "sold_realistic_bn", "sold_distress_bn"]].round(2).to_string())
    print(totals().round(1))
