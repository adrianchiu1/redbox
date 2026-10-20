# Retirement age and the Le Pen scenario: grounding research

Research note for the France fiscal brief, 20 October 2026. Scope: how sensitive
the categories of general-government expenditure and revenue are to the legal
retirement age, and how that could be brought into the Le Pen branches of the
scenario tree (section 5 of the brief; `ggfiscal.debt.simulate.SCENARIOS`).
Nothing here is yet in the engine or the note; it is the evidence base and a
menu of approaches for the committee. All external facts are **[ext]** in the
brief's convention and listed in §7.

## 1. Where the brief stands

The Le Pen branches are two declared primary-balance paths: +€25bn a year
2028–2031 with a majority (0% real growth, spread 190 → 125 bp), +€15bn a
year hung (0.5%, 175 → 125 bp), both "the RN counter-budget enacted with
slippage" against the €140bn of net savings by 2032 it promises (D-S18-001).
Pensions are not a separate lever: the fiscal path is one number a year, and
the note's only pension references are the Philippe-majority label ("pension
age and spending review delivered in part") and the CGE's €2.5tn of civil-service
pension commitments in section 7.

The flat files carry the lines the question is about (France, strict, 2024):

| Redbox line | 2024, % GDP | EUR bn | What the age moves |
|---|---|---|---|
| `GF10_2` Old age (pensions) | 13.35 | 392 | the direct cost |
| `GF10_X` Social protection ex old age and unemployment | 8.60 | 253 | invalidity, sickness benefit, minima (the spillover) |
| `GF10_5` Unemployment | 1.65 | 49 | older unemployed staying longer |
| `R06` Net social contributions (`R06_E` 10.0, `R06_H` 4.7) | 16.48 | 484 | fewer contributors at 60–63 |
| `R03` Taxes on household income | 9.37 | 275 | wages replaced by (lower, less taxed) pensions |
| `R01` VAT | 7.08 | 208 | through consumption/GDP |

The `GF10_2` forward path in the strict file (13.3–13.4% of GDP to 2036) is
chained on EC Ageing Report 2024 growth, i.e. a 64-year path with the 2023 reform
fully in force; the Redbox statistical benchmark holds `GF10_2` at 13.3–13.4% to
2031. Nothing in the bundle carries population by age, pension flows by cohort
or the age of entry into work.

## 2. What the RN actually proposes (as of 20 October 2026)

- **6 October, the counter-budget.** €140bn of net savings by 2032 against 2026,
  deficit below 3% in 2030, debt 121% → 112%. Pensions appear twice in the RN's
  own tables (as read by Terra Nova): the reform **costs €1.9bn in 2027 rising to
  €9.5bn in 2031**, and a single line "Retraite : mesures de réparation du
  système actuel" **yields €3, 6, 9, 12, 15bn in 2027–2031**, so the package is
  shown as "financed". Terra Nova's recomputation of the whole counter-budget
  finds €7.5bn of net savings by 2031, not €140bn.
- **11–18 October, the age.** Before the Medef and in Brussels (14 Oct), then on
  Europe 1/CNEWS (17 Oct) and by Chenu on RTL (18 Oct): legal age **62** (the
  2023 reform to 64 reversed), **60 for those who started work before 20, with
  40 annuités**; 42 annuités for the others; the automatic full-rate age stays 67
  (Tanguy); a funded (capitalisation) pillar beside pay-as-you-go. The RN's cost:
  **about €9bn a year "en rythme de croisière"**. Le Pen has promised a fully
  costed plan on **17 November 2026**.
- **The baseline is already not 64.** The LFSS 2026 (law 2025-1403, 30 Dec 2025)
  suspended the 2023 reform for pensions liquidated from 1 Sep 2026: the age is
  frozen at **62 years 9 months** for the 1964 cohort and Q1-1965; 64 is reached
  for the 1969 cohort instead of 1968; 172 quarters for 1966 instead of 1965.
  Cost: ~€1.8bn a year to 2032 (DREES Trajectoire, in COR June 2026), ≈0.1% of
  GDP; the government's rectifying letter said €0.1bn 2026 / €1.4bn 2027. So in
  2028 "back to 62" unwinds about one year for the cohorts then reaching the age,
  and forgoes the remaining 1¼ years of the 64 path for later cohorts.

## 3. Independent costings of the RN's age policy

| Source (date) | Measure costed | Cost, EUR bn a year | Scope |
|---|---|---|---|
| RN (Oct 2026) | 62, 60 for early starters | 9 (cruising); 1.9 (2027) → 9.5 (2031) | not documented |
| Cour des comptes (Feb 2025) | **one year** of legal age: 63 instead of 64 | +5.8 in 2035; 65 would save 8.4 | pension system only |
| OFCE (2024) | repeal of the 2023 reform (back to 62) | 9.5 (2027), 15.6 (2030) "minimal" | net gain of reform 7.9 → 13.8 plus minimum-pension measures 1.6–1.8 |
| CNAV, via Assembly amendments (Nov 2024) | repeal | 3.4–5 (2025) → 16 (2032) | pension system |
| M. Zemmour (2024) | repeal | 20–22 in 2030 | general government |
| Institut Montaigne (2022) | 60 at full rate with 40 annuités | 26.5 | pension schemes only |
| Institut Montaigne (2024) | repeal + 60 with 40 annuités for pre-20 starters | **34.7 by 2027**; 31.5 low case (pre-20 starters only) | pension schemes; press now quotes "about 35" |
| Chaire TDTE (via press) | same, employment channel | −0.3 to −1.5% of GDP | macro, not a budget figure |
| Government (2023) | the 2023 reform's gross yield | 17.7 in 2030 before accompanying measures (19.7 per Sénat) | pension system |
| Rexecode / Fipaddict (Apr 2023) | the 2023 reform | +0.4% GDP pension balance, **+0.6% GDP general-government balance** in 2030; +300k jobs, +1.1% GDP | macro model |

Reading across: **reversing 64 → 62 for everyone is €13–22bn a year by 2030–32
(0.4–0.6% of GDP)**, the lower end pension-system-only, the upper end general
government with the revenue side; **adding 60 for early starters roughly
doubles it** to €27–35bn (Montaigne). The RN's €9bn is below every
independent figure, including the Cour's one-year-of-age number. Against the
Le Pen-majority path (+€25bn a year, €105bn by 2032), the pension measure alone
is the same order as the whole scenario's consolidation.

## 4. Elasticities: what one year of legal age does, line by line

**DG Trésor for the COR (Jan 2022), two years of minimum age phased one quarter
a cohort, long run (15–20 years), % of GDP** (as tabulated by FIPECO):

| Channel | Effect on GG balance | Redbox line |
|---|---|---|
| Lower pensions | +0.4 | `GF10_2` |
| Higher pension contributions | +0.1 | `R06` |
| Other social benefits (sickness, invalidity, unemployment, minima) | −0.2 | `GF10_X`, `GF10_5`, `GF07` |
| Other taxes and contributions (wages > pensions; GDP) | +0.6 | `R03`, `R01`, `R06` non-pension |
| **Total** | **+0.9** (≈ €22bn 2022) | half pension system, half the rest |

Time path (Mésange, INSEE/DG Trésor): 5 years +0.1, 10 years +0.4, 15 years
+0.7, 20 years +0.9% of GDP; +260k jobs at 10 years but unemployment still
+0.7 pt. OFCE e-mod.fr: only +0.15% of GDP at 10 years, +110k jobs, unemployment
+0.9 pt. So the two standard French macro models disagree by a factor of ~2.5
on the medium-term fiscal yield, and the gap is entirely the revenue side.

**DREES for the COR (Jan 2022):** two years of age raise non-pension, non-UI
benefits by €3.6bn (0.14% GDP, 2019 base): invalidity +€1.8bn (+162k
beneficiaries), sickness daily allowances and AT-MP, minima +€0.83bn (AAH 510m,
RSA 150m, ASS). Against a pension saving of ~0.60% GDP that is a **~25%
"éviction"**; unemployment insurance and prime d'activité come on top.

**Cour des comptes (Feb 2025):** 63 vs 64 = +€5.8bn in 2035 on the pension
system; 65 = −€8.4bn: the response is not symmetric (fewer people are
constrained by a lower floor than by a higher one). Effect "powerful in the
short run, stabilising in the medium run".

**COR (June 2026):** spending 14.1% of GDP 2025, ~14.0% through the 2030s,
15.3% in 2070; balance −0.2% GDP in 2030 (€6.8bn), −0.9% in 2045, −2.4% in
2070; âge conjoncturel 63.1 (2025) → 64.6 (2040s). The reform's suspension
(≈1 year for ≈1¼ cohorts) costs €1.8bn a year: a useful unit, ≈€1.5bn per
cohort-year of age on the pension system before any revenue effect.

**Bottom-up units (DREES, Les retraités et les retraites 2025; INSEE/DARES):**
781k first liquidations a year; average gross direct pension €1,666/month
(€20k/yr) for residents, new retirees €1,557; employment rate 60–64 44.4% in
2025 (+2.0 pt after +3.4 pt in 2024, mostly the 2023 reform; EU 55.0%). At 62 in
2021: 51% retired, 33% employed, 14% inactive, 3% unemployed (FIPECO on INSEE),
so roughly half a cohort is bound by the floor. Naive check: 800k × ½ × €20k ≈
€8bn per year of age on gross pensions, consistent with the Cour's €5.8bn once
contribution and durée effects are netted.

**Scaling to the engine's GDP** (2027 €3,151bn, then 0% real × 2% deflator in
the Le Pen majority): 0.1% of GDP = €3.3bn in 2030, €3.7bn in 2035.

## 5. Candidate approaches

**A. Declared elasticity table (top-down).** Take the DG Trésor/COR decomposition
and the Cour's one-year figure, scale per year of legal age and per cohort
affected, and declare a per-year EUR bn path for each Redbox line (`GF10_2`,
`GF10_X`+`GF10_5`, `R06`, other revenue) 2028–2035, low/central/high (OFCE vs
Mésange revenue side; with/without the 60 option). Sum into `pb_change_bn`
overrides for new scenarios `lepen_*_pension`. Cheap, transparent, same style as
the existing assumptions table; the brief gets a chart "what the pension lever
is made of" beside Figure 9. Weakness: elasticities estimated for raising the
age, applied to lowering it, and the asymmetry the Cour flags.

**B. Cohort arithmetic (bottom-up).** Cohorts 1965–1973 × share bound by the
floor × average pension × years gained, phased by cohort against the suspended
64 path; a second block for the pre-20 starters (needs the DREES/CNAV share of
early starters, which Montaigne's low case puts at most of the cost); revenue
side as employed share × average wage × tax wedge. Gives the year-by-year
phase-in the engine wants and a defensible split between "62 for all" and "60
for early starters". Needs data not in the bundle (INSEE population by single
year of age, DREES age-of-entry shares) under `data/manual`, and a small module.

**C. Range of published costings (triangulation).** No model: lay the RN €9bn,
OFCE €15.6bn, Zemmour €20–22bn and Montaigne €35bn side by side with their
scopes, then run the engine with three pension variants layered on the Le Pen
paths. Fastest; honest about the spread; mirrors the existing "RN promise vs
engine" table. Weakness: no line decomposition, which was the question.

**D. Growth channel.** The engine's real growth is declared; the 2023 reform is
credited with +1.1% GDP by 2030 (Rexecode), far less by OFCE. A −0.1 to −0.2 pp
a year growth haircut for a decade in the pension variants would move the
ratios and `R06`/`R01` through nominal GDP. Can sit on top of A, B or C; the Le
Pen-majority 0% growth already carries some of it implicitly.

**E. Line-level shock in the Redbox forecast framework.** Apply the shock to the
`GF10_2` forward path itself (EC Ageing 2024 growth source) and let the balance
ledger carry it, so the deliverables and the brief agree line by line. Most
consistent, heaviest; probably a later step.

Recommended: A + C now (A gives the line-by-line sensitivity, C the band and the
RN-vs-independent framing), engine variants `lepen_majority_pension_{rn,central,high}`,
with B after 17 November when the RN's costed plan fixes the parameters.

## 6. Decisions for the committee

1. Scope: pension system only, or general government with the second-round
   revenue (the factor-of-two question)?
2. Central case: 62 for all, with 60 for early starters as a variant, or the
   full RN package as central?
3. Baseline: the suspended path in law (62y9m frozen to 2028, 64 from the 1969
   cohort), not 64 today.
4. Does the pension cost come out of the €25bn/€15bn consolidation (the RN
   says it is financed by "réparation" savings) or on top of it?
5. Touch growth (D) or leave it in the declared 0%/0.5%?

## 7. Sources [ext]

- franceinfo, 14 Oct 2026; Renseignement Économique, 15 and 17 Oct 2026; Capital/Yahoo, 18 Oct 2026 (Chenu on RTL); Atlantico, 11 Oct 2026 (B. Martinot); Patrimoine Magazine, 7 Oct 2026; Référence Entreprise, 4 Oct 2026; Capital, 24 Sep 2026 (candidates' positions).
- Terra Nova / La Grande Conversation, "RN : les mauvais comptes d'un budget dopé à l'IA", 13 Oct 2026 (RN counter-budget lines; Montaigne footnote).
- Institut Montaigne, chiffrages 2022 (€26.5bn) and législatives 2024 (€34.7bn, low €31.5bn).
- COR, Rapport annuel June 2026 (synthèse and full report; suspension cost, Tableau 1.4 on the suspended age path, sensitivity chapter).
- COR Jan 2022 plenary: DREES note "Dépenses relèvement âge" (éviction 25%); DG Trésor note as tabulated in FIPECO, "Le recul de l'âge de la retraite", 19 Oct 2022.
- Cour des comptes, "Situation financière et perspectives du système de retraites", 20 Feb 2025.
- OFCE, législatives 2024 analysis "Conséquences budgétaires de la réforme des retraites de 2023".
- Rexecode / Fipaddict, "Réforme des retraites : une résorption partielle du déficit après 2030", Apr 2023.
- DREES, Les retraités et les retraites, édition 2025; DARES/INSEE, emploi des seniors 2025.
- Sénat, PLF 2026 rapport Régimes sociaux et de retraite; CMS Law on the PLFSS 2026 rectifying letter; IFRAP, 21 Apr 2026.
- Assembly amendments to PPL 613 (Nov 2024) quoting CNAV; rapport AN 613 quoting M. Zemmour.
