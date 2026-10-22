"""Placeholders for the France brief's retirement-age section (D-S20-001),
prefix `pa_`, read from the CSVs `briefing_fra_pensions.render_all` writes
under figures/. Imported by tools/build_briefing_fra.py."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ggfiscal.debt import pension_age as pa

YEARS = (2028, 2030, 2032, 2035)
SHORT = {"p62": "p62", "p60": "p60", "p64": "p64"}


def _f(x, nd=1):
    return f"{x:,.{nd}f}"


def values(fig_dir: Path) -> dict[str, str]:
    mat = pd.read_csv(fig_dir / "pension_age_matrix.csv")
    ex = pd.read_csv(fig_dir / "pension_age_exposure.csv")
    units = pd.read_csv(fig_dir / "pension_age_units.csv", index_col=0)
    pub = pd.read_csv(fig_dir / "pension_age_published.csv")
    reg = pd.read_csv(fig_dir / "pension_age_assumptions.csv", keep_default_na=False)
    V: dict[str, str] = {}

    # totals by policy × variant × method × year
    tot = mat.groupby(["policy", "variant", "method", "year"]).balance_bn.sum()
    for pol in ("p62", "p60", "p64"):
        for y in (2028, 2029, 2030, 2031, 2032, 2033, 2035, 2040):
            c = tot.loc[(pol, "central")]
            V[f"pa_{pol}_{y}_bu"] = _f(-c.loc[("m2_bottom_up", y)])
            V[f"pa_{pol}_{y}_min"] = _f(-c.xs(y, level="year").max())      # smallest cost across methods
            V[f"pa_{pol}_{y}_max"] = _f(-c.xs(y, level="year").min())
            V[f"pa_{pol}_{y}_low"] = _f(-tot.loc[(pol, "low", "m2_bottom_up", y)])
            V[f"pa_{pol}_{y}_high"] = _f(-tot.loc[(pol, "high", "m2_bottom_up", y)])
            V[f"pa_{pol}_{y}_tresor"] = _f(-c.loc[("m1_tresor", y)])
            V[f"pa_{pol}_{y}_cour"] = _f(-c.loc[("m1_cour", y)])
            V[f"pa_{pol}_{y}_cor"] = _f(-c.loc[("m1_cor", y)])
            V[f"pa_{pol}_{y}_pub"] = _f(-c.loc[("m3_published", y)])
            V[f"pa_{pol}_{y}_gdp"] = _f(-c.loc[("m4_growth", y)])
            V[f"pa_{pol}_{y}_bu_pct"] = _f(-100 * c.loc[("m2_bottom_up", y)] / pa.gdp(y), 2)
    for pol in ("p64",):
        for y in (2028, 2030, 2032):
            V[f"pa_{pol}_{y}_bu"] = _f(tot.loc[(pol, "central", "m2_bottom_up", y)])   # a saving, positive

    # lines, central bottom-up, with the range across methods (p62 and p60)
    for pol in ("p62", "p60"):
        rows = []
        for line in pa.LINES:
            cells = []
            for y in YEARS:
                m = mat[(mat.policy == pol) & (mat.variant == "central") & (mat.year == y) & (mat.line_code == line)].set_index("method").eur_bn
                bu = m["m2_bottom_up"]
                lo, hi = m.min(), m.max()
                cells.append(f"<td>{bu:+.1f} <span class='rng'>({lo:+.1f} to {hi:+.1f})</span></td>")
                V[f"pa_{pol}_{line}_{y}"] = f"{bu:+.1f}"
            rows.append(f"<tr><td class='l'>{line} · {pa.LINE_LABEL[line]}</td><td class='l'>{'expenditure' if line in pa.EXPENDITURE else 'revenue'}</td>{''.join(cells)}</tr>")
        cells = []
        for y in YEARS:
            c = tot.loc[(pol, "central")].xs(y, level="year")
            cells.append(f"<td><b>{c['m2_bottom_up']:+.1f}</b> <span class='rng'>({c.min():+.1f} to {c.max():+.1f})</span></td>")
        rows.append(f"<tr class='hl'><td class='l'>Primary balance, all lines</td><td class='l'>net</td>{''.join(cells)}</tr>")
        cells = []
        for y in YEARS:
            lo = tot.loc[(pol, "low", "m2_bottom_up", y)]; hi = tot.loc[(pol, "high", "m2_bottom_up", y)]
            cells.append(f"<td>{lo:+.1f} to {hi:+.1f}</td>")
        rows.append(f"<tr><td class='l'>Primary balance, bottom-up, low to high assumptions</td><td class='l'>net</td>{''.join(cells)}</tr>")
        V[f"pa_matrix_rows_{pol}"] = "\n".join(rows)

    # units per cohort-year (2030)
    rows = []
    for m, r in units.iterrows():
        rows.append(f"<tr><td class='l'>{m}</td>" + "".join(f"<td>{r[l]:+.1f}</td>" for l in pa.LINES) + f"<td><b>{r.total_cost:.1f}</b></td></tr>")
    V["pa_units_rows"] = "\n".join(rows)
    V["pa_unit_bu"] = _f(units.loc[pa.METHODS["m2_bottom_up"], "total_cost"])
    V["pa_unit_min"] = _f(units.total_cost.min()); V["pa_unit_max"] = _f(units.total_cost.max())
    V["pa_unit_cour"] = _f(units.loc[pa.METHODS["m1_cour"], "total_cost"])
    V["pa_unit_cor"] = _f(units.loc[pa.METHODS["m1_cor"], "total_cost"])
    V["pa_unit_tresor"] = _f(units.loc[pa.METHODS["m1_tresor"], "total_cost"])
    V["pa_unit_pub"] = _f(units.loc[pa.METHODS["m3_published"], "total_cost"])
    V["pa_unit_gdp"] = _f(units.loc[pa.METHODS["m4_growth"], "total_cost"])
    bu = units.loc[pa.METHODS["m2_bottom_up"]]
    V["pa_unit_bu_gf10_2"] = _f(bu["GF10_2"]); V["pa_unit_bu_r06"] = _f(-bu["R06"]); V["pa_unit_bu_gf10_x"] = _f(-bu["GF10_X"])
    V["pa_unit_bu_gf10_5"] = _f(-bu["GF10_5"]); V["pa_unit_bu_r03"] = _f(-bu["R03"])
    V["pa_unit_bu_pension_system"] = _f(bu["GF10_2"] + 0.65 * bu["R06"])

    # published costings
    rows = []
    for r in pub.itertuples():
        rows.append(f"<tr><td class='l'>{r.source}</td><td>€{r.eur_bn:g}bn in {r.year}</td><td class='l'>{r.measure}</td><td>{r.scope}</td>"
                    f"<td>{r.cohort_years:.2f}</td><td><b>{r.eur_bn_per_cohort_year:.1f}</b></td></tr>")
    V["pa_published_rows"] = "\n".join(rows)
    P = pub.set_index("source").eur_bn_per_cohort_year
    V["pa_pub_rn_unit"] = _f(P["RN (Oct 2026)"]); V["pa_pub_montaigne_unit"] = _f(P["Montaigne (2024)"])
    V["pa_pub_ofce_unit"] = _f(P["OFCE (2024)"]); V["pa_pub_zemmour_unit"] = _f(P["Zemmour (2024)"]); V["pa_pub_cnav_unit"] = _f(P["CNAV (Nov 2024)"])
    su = pa.suspension_unit()
    V["pa_susp_cohort_years"] = _f(su["cohort_years_2027_2031_avg"], 2)

    # exposure and timing
    E = ex[ex.variant == "central"].groupby(["policy", "year"])[["cohort_person_years", "bound_person_years", "people_end_year"]].sum()
    rows = []
    for y in range(2028, 2037):
        e62, e60 = E.loc[("p62", y)], E.loc[("p60", y)]
        steady62 = E.loc[("p62", 2034), "cohort_person_years"]; steady60 = E.loc[("p60", 2034), "cohort_person_years"]
        p64 = E.loc[("p64", y), "people_end_year"] if ("p64", y) in E.index else 0.0
        rows.append(f"<tr><td class='l'>{y}</td><td>{e62.cohort_person_years / 850_000:.2f}</td><td>{100 * e62.cohort_person_years / steady62:.0f}%</td>"
                    f"<td>{e62.people_end_year / 1000:,.0f}</td><td>{-tot.loc[('p62', 'central', 'm2_bottom_up', y)]:.1f}</td>"
                    f"<td>{e60.cohort_person_years / 850_000:.2f}</td><td>{100 * e60.cohort_person_years / steady60:.0f}%</td>"
                    f"<td>{e60.people_end_year / 1000:,.0f}</td><td>{-tot.loc[('p60', 'central', 'm2_bottom_up', y)]:.1f}</td>"
                    f"<td>{p64 / 1000:,.0f}</td><td>{tot.loc[('p64', 'central', 'm2_bottom_up', y)]:.1f}</td></tr>")
    V["pa_timing_rows"] = "\n".join(rows)
    for pol in ("p62", "p60"):
        for y in (2028, 2030, 2033):
            V[f"pa_{pol}_{y}_people"] = f"{E.loc[(pol, y), 'people_end_year'] / 1000:,.0f}"
            V[f"pa_{pol}_{y}_cy"] = f"{E.loc[(pol, y), 'cohort_person_years'] / 850_000:.2f}"
        V[f"pa_{pol}_2028_share"] = f"{100 * E.loc[(pol, 2028), 'cohort_person_years'] / E.loc[(pol, 2034), 'cohort_person_years']:.0f}"
        V[f"pa_{pol}_2030_share"] = f"{100 * E.loc[(pol, 2030), 'cohort_person_years'] / E.loc[(pol, 2034), 'cohort_person_years']:.0f}"
    V["pa_susp_people_2028"] = f"{E.loc[('suspension', 2028), 'people_end_year'] / 1000:,.0f}"
    pop = pa.population()
    V["pa_cohort_2028"] = f"{pop.loc[2028, 60] / 1000:,.0f}"; V["pa_cohort_2033"] = f"{pop.loc[2033, 60] / 1000:,.0f}"; V["pa_cohort_2040"] = f"{pop.loc[2040, 60] / 1000:,.0f}"

    # growth channel
    for v in ("low", "central", "high"):
        g = pa.gdp_channel("p62", v).set_index("year")
        V[f"pa_gdp_2035_{v}"] = f"{-g.loc[2035, 'gdp_pct']:.2f}"
        V[f"pa_gdp_rev_2035_{v}"] = _f(-(g.loc[2035, ["R01_bn", "R02_bn", "R03_bn", "R04_bn", "R06_bn"]].sum()))
    g60 = pa.gdp_channel("p60").set_index("year")
    V["pa_gdp60_2035_central"] = f"{-g60.loc[2035, 'gdp_pct']:.2f}"
    h = pd.Series(pa.growth_haircut("p62")); V["pa_haircut_max_bp"] = f"{-100 * h.min():.0f}"
    h60 = pd.Series(pa.growth_haircut("p60")); V["pa_haircut60_max_bp"] = f"{-100 * h60.min():.0f}"

    # the strict file's GF10_2 path with the shock (method 5)
    c = pd.read_csv(pa.DELIV / "expenditure_cofog.csv", low_memory=False).query("iso3 == 'FRA' and variant == 'strict' and line_code == 'GF10_2'").set_index("year").pct_gdp
    for y in (2030, 2035):
        V[f"pa_gf10_2_{y}_strict"] = f"{c.loc[y]:.1f}"
        for pol in ("p62", "p60"):
            m = mat[(mat.policy == pol) & (mat.variant == "central") & (mat.method == "m2_bottom_up") & (mat.line_code == "GF10_2") & (mat.year == y)].pct_gdp.iloc[0]
            V[f"pa_gf10_2_{y}_{pol}"] = f"{c.loc[y] + m:.1f}"

    # assumptions register
    rows = []
    for r in reg.itertuples():
        rng = f"{r.low} to {r.high}" if (r.low or r.high) else ""
        rows.append(f"<tr class='st-{r.status}'><td class='l'><b>{r.id}</b></td><td class='l'>{r.name}</td><td class='l'>{r.value}{(' ' + r.unit) if r.unit else ''}"
                    f"{('<br><span class=rng>' + rng + '</span>') if rng else ''}</td><td>{r.status}</td><td class='l'>{r.source}{('<br><i>' + r.note + '</i>') if r.note else ''}</td></tr>")
    V["pa_assumption_rows"] = "\n".join(rows)
    V["pa_n_assumptions"] = str(len(reg)); V["pa_n_missing"] = str(int((reg.status == "missing").sum()))
    V["pa_n_inferred"] = str(int((reg.status == "inferred").sum())); V["pa_n_sourced"] = str(int((reg.status == "sourced").sum()))
    # scale against the Le Pen path
    V["pa_lp_consolidation"] = "25"
    c30 = tot.loc[("p62", "central")].xs(2030, level="year")
    V["pa_p62_2030_min_vs_lph"] = f"{100 * -c30.max() / 15:.0f}"
    V["pa_p62_2030_max_vs_lp"] = f"{100 * -c30.min() / 25:.0f}"
    return V
