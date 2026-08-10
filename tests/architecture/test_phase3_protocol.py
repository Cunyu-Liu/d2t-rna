"""Tests for the Conditional Phase 3 architecture protocol (plan §P3).

Runs on synthetic fixture scalability/baseline-suite artifacts and verifies:
bottleneck facts are derived from the real payload (not hand-written),
the three candidate schemes each carry the ten required §P3 fields, the
at-most-three constraint holds, the implementation state is NOT implemented,
and the output is deterministic.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from d2t_rna.architecture.phase3_protocol import (
    MAX_SCHEMES,
    PHASE3_IMPLEMENTATION,
    PHASE3_STATE,
    build_phase3_protocol,
)

REQUIRED_SCHEME_FIELDS = {
    "id",
    "name",
    "bottleneck",
    "why_current_insufficient",
    "new_capability",
    "basis",
    "minimal_implementation",
    "risk",
    "control",
    "ablation",
    "success_threshold",
    "failure_rollback",
}


def _write_fixture_scalability(d: pathlib.Path) -> pathlib.Path:
    p = d / "scalability.json"
    p.write_text(
        json.dumps(
            {
                "schema": "d2t_rna.v7_p1_scalability_report.v1",
                "n_cells": 80,
                "coverage": {
                    "exhaustive_oracle": {
                        "executed_ok_cells": 80,
                        "coverage": 1.0,
                    },
                    "t2_integer_lp": {"executed_ok_cells": 64, "coverage": 0.8},
                },
                "exact_oracle_boundary": {
                    "max_allocation_space": 81,
                    "exact_solvable_boundary": "cap-free within-budget allocation space <= 81",
                    "beyond_exact_scale": "UNKNOWN_NOT_ASSERTED",
                },
                "lp_dims_by_catalog_class": {
                    "CA": {"n_decision_variables": 2, "n_threshold_constraints": 1},
                    "CB": {"n_decision_variables": 2, "n_threshold_constraints": 1},
                },
            }
        ),
        encoding="utf-8",
    )
    return p


def _write_fixture_baseline(d: pathlib.Path) -> pathlib.Path:
    p = d / "baseline_suite.json"
    p.write_text(
        json.dumps({"schema": "d2t_rna.v7_p1_baseline_suite.v1", "headline": {}}),
        encoding="utf-8",
    )
    return p


@pytest.fixture
def artifacts(tmp_path: pathlib.Path):
    return (
        _write_fixture_scalability(tmp_path),
        _write_fixture_baseline(tmp_path),
    )


def test_bottleneck_facts_from_real_payload(artifacts) -> None:
    s, b = artifacts
    m = build_phase3_protocol(s, b, head="h")
    f = m["bottleneck_facts"]
    assert f["integer_lp_coverage"] == 0.8
    assert f["integer_lp_withheld_certificates"] == 16
    assert f["exact_oracle_max_allocation_space"] == 81
    assert f["beyond_exact_scale"] == "UNKNOWN_NOT_ASSERTED"
    assert f["lp_max_decision_variables"] == 2


def test_at_most_three_schemes(artifacts) -> None:
    s, b = artifacts
    m = build_phase3_protocol(s, b, head="h")
    assert len(m["schemes"]) <= MAX_SCHEMES
    assert m["schemes"][0]["id"] == "A_TYPED_EXACT_KERNEL_CERTIFICATE"
    assert m["schemes"][2]["id"] == "C_EXACT_SCALING_BB_CP_CG"


def test_each_scheme_has_all_required_fields(artifacts) -> None:
    s, b = artifacts
    m = build_phase3_protocol(s, b, head="h")
    for scheme in m["schemes"]:
        assert REQUIRED_SCHEME_FIELDS.issubset(scheme.keys()), scheme["id"]
        for k in REQUIRED_SCHEME_FIELDS:
            assert isinstance(scheme[k], str) and scheme[k]


def test_state_and_selection(artifacts) -> None:
    s, b = artifacts
    m = build_phase3_protocol(s, b, head="h")
    assert m["state"] == PHASE3_STATE
    assert m["implementation"] == PHASE3_IMPLEMENTATION
    assert m["selection"]["selected_scheme"] == "NONE_YET_PROTOCOL_PRE_REGISTERED"


def test_deterministic_and_sha_bound(artifacts) -> None:
    s, b = artifacts
    a = build_phase3_protocol(s, b, head="same")
    c = build_phase3_protocol(s, b, head="same")
    assert a == c
    assert len(a["input_artifacts_sha256"]["scalability.json"]) == 64


def test_missing_artifact_raises(tmp_path: pathlib.Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_phase3_protocol(
            tmp_path / "nope.json", tmp_path / "also_nope.json", head="h"
        )
