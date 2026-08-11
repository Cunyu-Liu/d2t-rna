"""P0-9 precommit / confirmation tests.

Covers:
  (a) precommit receipt requires the frozen registry fields (missing
      cost_cap_hash / non-IDENTIFIED endpoint / missing strongest_comparator /
      missing method_role_table -> PrecommitError);
  (b) the confirmation runner refuses a run missing precommit hash,
      method-role registry, primary decision, endpoint, or comparator-set hash;
  (c) an oracle row writes regret only in solvable cells and is never ranked
      (ranking claim on an oracle raises OracleRankingError);
  (d) failure / withheld cells remain in the denominator (never dropped).
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from d2t_rna.audit import precommit as PC
from d2t_rna.evaluation.method_role import (
    OracleRankingError,
    MethodRole,
    assert_no_oracle_ranking,
)
from d2t_rna.audit import diagnostic_oracle as O


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _role_table():
    return [
        {"method_id": "chernoff", "method_role": "comparator"},
        {"method_id": "eig", "method_role": "comparator"},
        {"method_id": "D2T_FIXED_BUDGET_SOLVER", "method_role": "deployable"},
        {"method_id": "INDEPENDENT_ORACLE_EXACT", "method_role": "oracle"},
    ]


def _frozen_registry():
    return {
        "primary_decision": {"cost_cap_hash": "a" * 64},
        "endpoint": {
            "status": "IDENTIFIED", "endpoint": "1/10", "endpoint_float": 0.1,
        },
        "strongest_comparator": {"strongest_comparator": "chernoff"},
        "method_role_table": _role_table(),
    }


def _receipt():
    return PC.build_precommit_receipt(
        frozen_registry=_frozen_registry(),
        instance_json={"n_cells": 1, "cells": [{"cell_id": "c0"}]},
        seeds={"s": 1},
        generator_commit="c" * 40,
        generator_tree="t" * 40,
    )


def _simple_cell(solvable=True):
    p0 = (Fraction(1, 2), Fraction(1, 2))
    p1 = (Fraction(1, 4), Fraction(3, 4))
    actions = [O.id_channel(2), O.id_channel(2)]
    return {
        "cell_id": "c0",
        "p0": list(p0),
        "p1": list(p1),
        "actions": actions,
        "costs": [Fraction(1), Fraction(1)],
        "budget": Fraction(8),
        "deployable_alloc": [4, 4],
        "comparator_alloc": [4, 0],
    }


# ---------------------------------------------------------------------------
# (a) precommit receipt requires frozen registry fields
# ---------------------------------------------------------------------------


def test_receipt_requires_cost_cap_hash():
    frozen = _frozen_registry()
    del frozen["primary_decision"]["cost_cap_hash"]
    with pytest.raises(PC.PrecommitError):
        PC.build_precommit_receipt(
            frozen_registry=frozen, instance_json={}, seeds={},
            generator_commit="c", generator_tree="t",
        )


def test_receipt_requires_identified_endpoint():
    frozen = _frozen_registry()
    frozen["endpoint"] = {"status": "NOT_IDENTIFIABLE"}
    with pytest.raises(PC.PrecommitError):
        PC.build_precommit_receipt(
            frozen_registry=frozen, instance_json={}, seeds={},
            generator_commit="c", generator_tree="t",
        )


def test_receipt_requires_strongest_comparator():
    frozen = _frozen_registry()
    frozen["strongest_comparator"] = {}
    with pytest.raises(PC.PrecommitError):
        PC.build_precommit_receipt(
            frozen_registry=frozen, instance_json={}, seeds={},
            generator_commit="c", generator_tree="t",
        )


def test_receipt_requires_method_role_table():
    frozen = _frozen_registry()
    del frozen["method_role_table"]
    with pytest.raises(PC.PrecommitError):
        PC.build_precommit_receipt(
            frozen_registry=frozen, instance_json={}, seeds={},
            generator_commit="c", generator_tree="t",
        )


def test_receipt_records_commitment_hash_and_status():
    receipt = _receipt()
    assert receipt["status"] == PC.PRECOMMIT_STATUS
    assert len(receipt["commitment_hash"]) == 64
    assert receipt["commitment_hash"] == PC.precommit_hash(
        PC.canonical_precommit_payload(receipt)
    )
    assert receipt["strongest_comparator"] == "chernoff"
    assert receipt["endpoint"] == "1/10"


def test_receipt_deterministic_hash():
    a = _receipt()["commitment_hash"]
    b = _receipt()["commitment_hash"]
    assert a == b


# ---------------------------------------------------------------------------
# (b) confirmation runner refuses missing required inputs
# ---------------------------------------------------------------------------


def _base_inputs():
    receipt = _receipt()
    return {
        "precommit_receipt": receipt,
        "method_role_registry": _role_table(),
        "primary_decision": {"max_registered_cost": 8},
        "endpoint": receipt["endpoint"],
        "comparator_set_hash": receipt["comparator_set_hash"],
    }


def test_confirmation_refuses_missing_precommit():
    inp = _base_inputs()
    inp["precommit_receipt"] = {}
    with pytest.raises(PC.PrecommitError):
        PC.require_confirmation_inputs(**inp)


def test_confirmation_refuses_missing_method_role():
    inp = _base_inputs()
    inp["method_role_registry"] = {}
    with pytest.raises(PC.PrecommitError):
        PC.require_confirmation_inputs(**inp)


def test_confirmation_refuses_missing_primary_decision():
    inp = _base_inputs()
    inp["primary_decision"] = {}
    with pytest.raises(PC.PrecommitError):
        PC.require_confirmation_inputs(**inp)


def test_confirmation_refuses_missing_endpoint():
    inp = _base_inputs()
    inp["endpoint"] = ""
    with pytest.raises(PC.PrecommitError):
        PC.require_confirmation_inputs(**inp)


def test_confirmation_refuses_missing_comparator_hash():
    inp = _base_inputs()
    inp["comparator_set_hash"] = ""
    with pytest.raises(PC.PrecommitError):
        PC.require_confirmation_inputs(**inp)


def test_confirmation_refuses_endpoint_mismatch_with_precommit():
    inp = _base_inputs()
    inp["endpoint"] = "1/5"
    with pytest.raises(PC.PrecommitError):
        PC.require_confirmation_inputs(**inp)


def test_confirmation_accepts_valid_inputs():
    # a valid input set must NOT raise
    PC.require_confirmation_inputs(**_base_inputs())


# ---------------------------------------------------------------------------
# (c) oracle not ranked; regret only in solvable cells
# ---------------------------------------------------------------------------


def test_oracle_never_ranked_guard():
    with pytest.raises(OracleRankingError):
        assert_no_oracle_ranking(MethodRole.ORACLE, "win")
    with pytest.raises(OracleRankingError):
        assert_no_oracle_ranking(MethodRole.ORACLE, "superiority")
    # regret is allowed on an oracle row
    assert_no_oracle_ranking(MethodRole.ORACLE, "regret")


def test_oracle_regret_only_in_solvable_cell():
    receipt = _receipt()
    cell = PC.evaluate_confirmation_cell(
        cell_id="c0", p0=_simple_cell()["p0"], p1=_simple_cell()["p1"],
        actions=_simple_cell()["actions"], costs=_simple_cell()["costs"],
        budget=_simple_cell()["budget"],
        deployable_alloc=_simple_cell()["deployable_alloc"],
        comparator_alloc=_simple_cell()["comparator_alloc"],
        endpoint=Fraction(1, 10), run_id="r0",
    )
    # oracle row present only because the cell is solvable, and only as regret
    assert cell["solvable"] is True
    oracle_rows = cell["oracle_regret_solvable_only"]
    assert oracle_rows  # regret written
    assert all(r["method_role"] == "oracle" for r in oracle_rows)
    assert all(r["solvable"] is True for r in oracle_rows)
    # every record is a non-result artifact with the pre-committed purpose
    assert cell["deployable"]["paper_eligible"] is False
    assert cell["deployable"]["purpose"] == PC.PURPOSE


def test_oracle_not_in_ranking_consumer_of_report():
    # run_confirmation never emits a ranking claim over oracle rows; verify the
    # report carries no win/superiority field and the oracle appears only in the
    # solvable-only regret field.
    receipt = _receipt()
    report = PC.run_confirmation(
        precommit_receipt=receipt,
        method_role_registry=_role_table(),
        primary_decision={"max_registered_cost": 8},
        endpoint=receipt["endpoint"],
        comparator_set_hash=receipt["comparator_set_hash"],
        cells=[_simple_cell()],
        run_id="r0",
    )
    assert report["n_total_cells"] == 1
    assert report["n_solvable_cells"] == 1
    # no ranking artifact
    assert "win" not in report
    assert "superiority" not in report
    assert "regret" not in report  # regret only lives on solvable oracle rows


# ---------------------------------------------------------------------------
# (d) failure / withheld cells remain in the denominator
# ---------------------------------------------------------------------------


def _bad_cell():
    cell = _simple_cell()
    # malformed p0 length (3) mismatching the 2-state channel -> IndexError in
    # the independent oracle -> the cell is recorded FAILURE (kept in the
    # denominator, never dropped).
    cell["p0"] = [Fraction(1, 3), Fraction(1, 3), Fraction(1, 3)]
    return cell


def test_failure_cell_kept_in_denominator():
    receipt = _receipt()
    cells = [_simple_cell(), _bad_cell()]
    report = PC.run_confirmation(
        precommit_receipt=receipt,
        method_role_registry=_role_table(),
        primary_decision={"max_registered_cost": 8},
        endpoint=receipt["endpoint"],
        comparator_set_hash=receipt["comparator_set_hash"],
        cells=cells,
        run_id="r0",
    )
    # denominator keeps ALL cells (including the failed one)
    assert report["n_total_cells"] == 2
    assert report["n_denominator_cells"] == 2
    assert report["n_solvable_cells"] == 1
    assert report["n_withheld_or_failed_in_denominator"] == 1
    # the failed cell is still present in records and not dropped
    statuses = [r.get("status") for r in report["records"]]
    assert "FAILURE" in statuses
    assert len(report["records"]) == 2


def test_all_cells_in_denominator_when_all_fail():
    receipt = _receipt()
    report = PC.run_confirmation(
        precommit_receipt=receipt,
        method_role_registry=_role_table(),
        primary_decision={"max_registered_cost": 8},
        endpoint=receipt["endpoint"],
        comparator_set_hash=receipt["comparator_set_hash"],
        cells=[_bad_cell()],
        run_id="r0",
    )
    assert report["n_total_cells"] == 1
    assert report["n_denominator_cells"] == 1
    assert report["n_solvable_cells"] == 0
    assert report["n_withheld_or_failed_in_denominator"] == 1
