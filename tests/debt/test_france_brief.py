"""Gate for the France fiscal brief notebook (D-S18-003): it shows every
chart and section of the briefing note except the questions for the AFT,
and it is committed executed, error-free, ending with the HTML rebuild."""
import json
import re

from ggfiscal.report import france_brief as fb

NB = fb.sim.ROOT / "notebooks" / "France_fiscal_brief_20261013.ipynb"


def test_every_chart_of_the_note_is_in_the_brief():
    tpl = (fb.BRIEF_DIR / "briefing_template.html").read_text()
    assert fb.figures() == re.findall(r"\{\{fig:([a-z_0-9]+)\}\}", tpl)


def test_the_brief_leaves_out_the_questions_and_nothing_else():
    assert "s7" not in fb.SECTIONS
    html = " ".join(v for s in fb.SECTIONS for k, v in fb.chunks(s) if k == "html")
    assert "To ask the AFT" not in html and "{{" not in html
    for heading in ("Scenario assumptions", "Assumptions common to every scenario",
                    "The statistical benchmark, year by year", "Caveats"):
        assert heading in html, heading
    assert any(k == "svg" for k, _ in fb.chunks("s2"))          # the loop diagram


def test_notebook_is_executed_error_free_and_rebuilds_the_html():
    nb = json.loads(NB.read_text())
    code = [c for c in nb["cells"] if c["cell_type"] == "code"]
    assert all(c.get("execution_count") for c in code)
    assert not [o for c in code for o in c.get("outputs", []) if o["output_type"] == "error"]
    images = sum("image/png" in o.get("data", {}) for c in code for o in c.get("outputs", []))
    assert images == len(fb.figures())
    assert "builder().main()" in "".join(code[-1]["source"])
