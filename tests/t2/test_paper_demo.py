"""Unit tests for the interactive paper demo build (C3).

Validates that the flattening of a measured certificate into the demo-data
schema is lossless and faithful, and that the self-contained demo HTML embeds
valid JSON carrying both the add and glycine measured cases.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.build_paper_demo_data import flatten

REPO = Path(__file__).resolve().parents[2]
DEMO_HTML = REPO / "docs" / "paper" / "demo" / "index.html"


def _synthetic_cert() -> dict:
    """A minimal certificate dict in the exact on-disk artifact schema."""
    return {
        "name": "unit_case",
        "length": 3,
        "sequence": ["A", "C", "G"],
        "n_measured_separating_positions": 2,
        "t2b_full_panel": {
            "status": "IFF",
            "gamma": "1/2",
            "panel": ["probe1", "probe2"],
            "enumeration_matches_lp": True,
            "lp_strong_duality": True,
            "separation_witness": ["-1", "1"],
        },
        "t2d_design": {
            "achievable_integer_cost": "3",
            "achievable_integer_n_nonzero": {"probe1": 3},
            "no_go_status_budget_1": "NO_GO",
        },
        "t2c_per_probe": [
            {
                "probe": 1,
                "nucleotide": "A",
                "reactivity_apo": 0.2,
                "reactivity_bound": 0.8,
                "q_paired_apo": "1/2",
                "q_paired_bound": "3/4",
                "info_lo": "0.1",
                "info_hi": "0.2",
                "n_sufficient_for_correct_0.99": 10,
            },
            {
                "probe": 3,
                "nucleotide": "G",
                "reactivity_apo": 0.1,
                "reactivity_bound": 0.4,
                "q_paired_apo": "1/3",
                "q_paired_bound": "2/3",
                "info_lo": "0.05",
                "info_hi": "0.06",
                "n_sufficient_for_correct_0.99": 42,
            },
        ],
    }


def test_flatten_preserves_separation_and_design():
    d = flatten(_synthetic_cert())
    assert d["n_sep"] == 2
    assert d["length"] == 3
    # T2b panel and certificate are copied through.
    assert d["t2b"]["status"] == "IFF"
    assert d["t2b"]["gamma"] == "1/2"
    assert d["t2b"]["panel"] == ["probe1", "probe2"]
    assert d["t2b"]["lp_strong_duality"] is True
    # T2d design cost / no-go are carried into the demo schema.
    assert d["t2d"]["cost"] == "3"
    assert d["t2d"]["design_cost"] == 3
    assert d["t2d"]["no_go_status"] == "NO_GO"
    assert d["t2d"]["n_nonzero"] == {"probe1": 3}


def test_flatten_maps_rows_with_float_q():
    d = flatten(_synthetic_cert())
    # One row per separating probe, positions preserved.
    assert [r["pos"] for r in d["rows"]] == [1, 3]
    # Fraction strings are converted to floats.
    assert abs(d["rows"][0]["qa"] - 0.5) < 1e-9
    assert abs(d["rows"][0]["qb"] - 0.75) < 1e-9
    assert abs(d["rows"][0]["info_lo"] - 0.1) < 1e-9
    assert d["rows"][0]["n"] == 10
    # Reactivity and nucleotide carried through.
    assert d["rows"][0]["nt"] == "A"
    assert d["rows"][0]["ra"] == 0.2
    assert d["rows"][0]["rb"] == 0.8


def test_demo_html_embeds_both_cases_as_valid_json():
    assert DEMO_HTML.exists(), f"{DEMO_HTML} missing"
    html = DEMO_HTML.read_text(encoding="utf-8")
    m = re.search(
        r'<script id="demo-data" type="application/json">(.*?)</script>',
        html,
        re.S,
    )
    assert m, "demo-data JSON block not found"
    data = json.loads(m.group(1))
    cases = data["cases"]
    assert set(cases) == {"add", "glycine"}
    # add case carries the measured SHAPE certificate fields.
    add = cases["add"]
    assert add["n_sep"] == 64
    assert add["t2d"]["design_cost"] == 3
    assert add["accession"] == "ADD71_STD_0001"
    # glycine case carries the measured DMS certificate fields.
    gly = cases["glycine"]
    assert gly["n_sep"] == 206
    assert gly["t2d"]["design_cost"] == 15
    assert len(gly["rows"]) == gly["n_sep"]
    assert len(gly["sequence"]) == gly["length"] == 265


def test_demo_html_contains_budget_slider_and_case_tabs():
    html = DEMO_HTML.read_text(encoding="utf-8")
    assert 'id="budget-slider"' in html
    assert 'id="budget-status"' in html
    assert 'id="c-cost"' in html
    assert "budget" in html.lower()