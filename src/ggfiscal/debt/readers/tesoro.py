"""Spanish Treasury (Secretaría General del Tesoro y Financiación
Internacional) monthly statistics reader (`ESP_TESORO`, D-S17-017).

`deuda_circulacion_xlsx` ("Deuda del Estado en circulación", file 01 of the
monthly bulletin) is one sheet: nominal outstanding at the end of each
period, EUR mn, index-linked debt uplifted by its indexation coefficient.
Rows: one per year-end 2007..(last full year before the current monthly
block), then a year label followed by its months (Enero..Diciembre).
Columns: Letras by tenor (≤3m, 6m, 9m, 12m, 18m), Bonos y Obligaciones by
tenor (≤3y, 5-7y, 10y, 15y, 20-50y), index-linked B y O, euro-bonds and
medium-term notes, other, assumed debt, foreign-currency debt, Banco de
España loans, total.
"""

from __future__ import annotations

import pandas as pd

from ggfiscal.debt.readers import snap_path

SOURCE = "ESP_TESORO"
PART = "deuda_circulacion_xlsx"
# column -> (sub_type, instrument_class, in_register); the order of the sheet
COLUMNS = [
    ("letras_3m", "bill", True), ("letras_6m", "bill", True), ("letras_9m", "bill", True),
    ("letras_12m", "bill", True), ("letras_18m", "bill", True),
    ("bonos_hasta_3a", "fixed_bullet", True), ("bonos_obligaciones_5_7a", "fixed_bullet", True),
    ("obligaciones_10a", "fixed_bullet", True), ("obligaciones_15a", "fixed_bullet", True),
    ("obligaciones_20_50a", "fixed_bullet", True),
    ("bonos_obligaciones_indexados", "inflation_linked", True),
    ("eurobonos_notas_mp", "other", True),
    ("resto", "out_of_register", False), ("deuda_asumida", "out_of_register", False),
    ("deuda_en_divisas", "other", True), ("prestamos_banco_de_espana", "out_of_register", False),
    ("total", "mixed", False),
]
MONTHS = {"Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6, "Julio": 7,
          "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12}


def outstanding(path=None) -> pd.DataFrame:
    """Period-end outstanding: index = period end (31 Dec for the annual
    rows, month end in the monthly block), columns = COLUMNS sub_types."""
    df = pd.read_excel(path or snap_path(SOURCE, PART), header=None)
    first = df.index[df.iloc[:, 0].astype(str).str.strip() == "FECHA"]
    if not len(first):
        raise ValueError("Tesoro 'Deuda del Estado en circulación': no FECHA header row")
    rows, index = [], []
    year = None
    for _, r in df.iloc[first[0] + 1:].iterrows():
        label = r.iloc[0]
        values = r.iloc[1:1 + len(COLUMNS)]
        has_values = pd.to_numeric(values, errors="coerce").notna().any()
        if isinstance(label, (int, float)) and not pd.isna(label):
            year = int(label)
            if has_values:                       # an annual (year-end) row
                index.append(pd.Timestamp(year, 12, 31))
                rows.append(values.tolist())
        elif isinstance(label, str) and label.strip() in MONTHS and year is not None:
            if has_values:
                index.append(pd.Timestamp(year, MONTHS[label.strip()], 1) + pd.offsets.MonthEnd(0))
                rows.append(values.tolist())
        elif isinstance(label, str) and label.strip().startswith("("):
            break                                # footnotes
    out = pd.DataFrame(rows, index=pd.DatetimeIndex(index),
                       columns=[c for c, _, _ in COLUMNS]).apply(pd.to_numeric, errors="coerce")
    parts = out.drop(columns="total").sum(axis=1, min_count=1)
    bad = (parts - out["total"]).abs() > 2.0           # rounding of 16 published components
    if bad.any():
        raise ValueError(f"Tesoro outstanding: components do not sum to the total at "
                         f"{[d.date() for d in out.index[bad]][:5]}")
    return out
