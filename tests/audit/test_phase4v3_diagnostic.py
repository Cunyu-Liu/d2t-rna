"""P0-6 evaluator diagnostic: standalone-oracle parity + schema-guard tests.

These tests verify the *independent* diagnostic oracle and the P0-6 generator
guards without touching the production evaluator:

(a) classic / CA exact fractions are reproduced by the standalone recomputation
    (classic 1/4 vs 1/3; CA_p1 n=4 -> 81/512 vs 81/337);
(b) the diagnostic generator refuses to run when the output path is phase4v2
    (must not overwrite);
(c) all diagnostic records carry paper_eligible=false and
    purpose=EVALUATOR_DIAGNOSTIC_ONLY;
(d) a cell whose minimax LP cannot be solved is marked
    WITHHELD_RANDOMIZED_MINIMAX_UNAVAILABLE rather than silently aliased to
    the Bayes average error.
"""

from __future__ import annotations

import pathlib

import pytest
from fractions import Fraction as F

import importlib.util
from pathlib import Path as _P

from d2t_rna.audit import diagnostic_oracle as O

_spec = importlib.util.spec_from_file_location(
    "t6_phase4v3_diagnostic",
    _P(__file__).resolve().parents[2] / "scripts" / "t6_phase4v3_diagnostic.py",
)
_gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gen)
_Rec = _gen._Rec
_guard_not_phase4v2 = _gen._guard_not_phase4v2
build_parity = _gen.build_parity
build_12cell = _gen.build_12cell
SCHEMA_ID = _gen.SCHEMA_ID
PURPOSE = _gen.PURPOSE
PAPER_ELIGIBLE = _gen.PAPER_ELIGIBLE


# ---------------------------------------------------------------------------
# (a) classic / CA exact parity via the standalone oracle
# ---------------------------------------------------------------------------


def test_classic_exact_parity():
    r = O.single_action_parity((F(1), F(0)), (F(1, 2), F(1, 2)), 1)
    assert r["bayes_average_error"] == F(1, 4)
    assert r["randomized_minimax_error"] == F(1, 3)


def test_ca_p1_exact_parity():
    r = O.single_action_parity((F(1, 4), F(3, 4)), (F(0), F(1)), 4)
    assert r["bayes_average_error"] == F(81, 512)
    assert r["randomized_minimax_error"] == F(81, 337)


def test_bayes_and_minimax_are_distinct():
    r = O.single_action_parity((F(1), F(0)), (F(1, 2), F(1, 2)), 1)
    assert r["bayes_average_error"] != r["randomized_minimax_error"]


# ---------------------------------------------------------------------------
# (b) refuse to overwrite phase4v2
# ---------------------------------------------------------------------------


def test_guard_rejects_phase4v2_destination():
    bad = pathlib.Path("/mnt/cunyuliu/d2t-rna/artifacts/phase4v2")
    with pytest.raises(RuntimeError):
        _guard_not_phase4v2(bad)
    with pytest.raises(RuntimeError):
        _guard_not_phase4v2(pathlib.Path("/tmp/phase4v2/overwrite"))


def test_guard_allows_phase4v3_destination():
    ok = pathlib.Path("/mnt/cunyuliu/d2t-rna/artifacts/phase4v3-diagnostic/run")
    _guard_not_phase4v2(ok)  # must not raise


# ---------------------------------------------------------------------------
# (c) every record carries paper_eligible=false and purpose=EVALUATOR_DIAGNOSTIC_ONLY
# ---------------------------------------------------------------------------


def _fresh_rec():
    return _Rec("commit0", "tree0")


def test_parity_records_carry_eligibility_and_purpose():
    d = build_parity(_fresh_rec(), "c", "t")
    assert d["schema"] == SCHEMA_ID
    assert d["paper_eligible"] is False
    assert d["purpose"] == PURPOSE
    assert len(d["records"]) == 2
    for r in d["records"]:
        assert r["paper_eligible"] is False
        assert r["purpose"] == PURPOSE
        assert r["purpose"] == "EVALUATOR_DIAGNOSTIC_ONLY"


def test_12cell_records_carry_eligibility_and_purpose():
    d = build_12cell(_fresh_rec(), "c", "t")
    assert len(d["records"]) == 12
    for r in d["records"]:
        assert r["paper_eligible"] is False
        assert r["purpose"] == PURPOSE
        assert r["method_role"] == "oracle"
        assert r["task_id"] == "P0-6-EVALUATOR-DIAGNOSTIC"


def test_parity_records_match_ground_truth():
    d = build_parity(_fresh_rec(), "c", "t")
    by = {r["block_id"]: r for r in d["records"]}
    assert by["classic_n1"]["bayes_average_error"] == "1/4"
    assert by["classic_n1"]["randomized_minimax_error"] == "1/3"
    assert by["CA_p1_n4"]["bayes_average_error"] == "81/512"
    assert by["CA_p1_n4"]["randomized_minimax_error"] == "81/337"


# ---------------------------------------------------------------------------
# (d) unsolvable cell -> WITHHELD, never aliased to Bayes
# ---------------------------------------------------------------------------


def test_withheld_not_aliased_to_bayes(monkeypatch):
    # Force the minimax LP to be "unsupported" (tiny outcome cap).
    monkeypatch.setattr(O, "MAX_MINIMAX_OUTCOMES", 1)
    r = O.single_action_parity((F(1), F(0)), (F(1, 2), F(1, 2)), 1)
    # n=1 classic has 2 outcomes > 1 -> minimax unavailable
    assert r["randomized_minimax_error"] is None
    # Bayes is still computed and is NOT substituted for the minimax endpoint
    assert r["bayes_average_error"] == F(1, 4)
    assert r["randomized_minimax_error"] != r["bayes_average_error"]


def test_withheld_record_status_not_aliased(monkeypatch):
    monkeypatch.setattr(O, "MAX_MINIMAX_OUTCOMES", 1)
    laws0 = [O.action_law(O.id_channel(2), (F(1, 4), F(3, 4)))]
    laws1 = [O.action_law(O.id_channel(2), (F(0), F(1)))]
    ev = O.evaluate_cell(laws0, laws1, (F(1),), F(4))
    assert ev["randomized_minimax_error"] is None
    assert ev["bayes_average_error"] is not None
