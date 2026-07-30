from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.verify_task4_acceptance_manifest import (
    CONTRACT_SHA256,
    EXPECTED_GATE_EVIDENCE_RECORDS,
    EXPECTED_TASK3_CLOSURE_FIELDS,
    EXPECTED_TASK4_ENTRY_GATE,
    EXPECTED_TASK4_RED_LOG_BYTES,
    EXPECTED_TASK4_RED_RECORD,
    TASK3_ACCEPTANCE_COMMIT,
    TASK3_CLOSURE_PATH,
    TASK3_CLOSURE_SHA256,
    TASK4_ENTRY_GATE_PATH,
    TASK4_ENTRY_GATE_SHA256,
    TASK4_RED_LOG_PATH,
    TASK4_RED_LOG_SHA256,
    TASK4_RED_RECORD_PATH,
    TASK4_RED_RECORD_SHA256,
    _validate_candidate_run_id,
    _verify_historical_gate_records,
    _verify_runtime_isolation_flags,
    _verify_task3_closure_semantics,
    _verify_task4_entry_gate_semantics,
    _verify_task4_red_log,
    _verify_task4_red_record_semantics,
    _verify_test_log,
)

SOURCE_INDEX_SHA256 = "c" * 64


def _valid_task3_closure() -> dict[str, object]:
    closure = {
        field: None
        for field in EXPECTED_TASK3_CLOSURE_FIELDS
    }
    closure.update(
        {
            "schema_id": "d2t_rna.acceptance_closure",
            "schema_version": "1.0",
            "task_id": "TASK_3",
            "contract_sha256": CONTRACT_SHA256,
            "git_commit": TASK3_ACCEPTANCE_COMMIT,
            "registered_commit_title": (
                "feat(data-lock): seal truth payloads until "
                "post-certificate audit"
            ),
            "run_id": (
                "task3-acceptance-recovery-20260730T011748p0800"
            ),
            "working_tree": "CLEAN_SYNCHRONIZED_WITH_ORIGIN_MAIN",
            "github": {
                "commit_url": (
                    "https://github.com/Cunyu-Liu/d2t-rna/commit/"
                    f"{TASK3_ACCEPTANCE_COMMIT}"
                ),
                "default_branch": "main",
                "github_main": TASK3_ACCEPTANCE_COMMIT,
                "origin_main": TASK3_ACCEPTANCE_COMMIT,
                "repository": "Cunyu-Liu/d2t-rna",
                "visibility": "PUBLIC",
            },
            "claim_state": {
                "authenticated_chronology_and_access_audit": "UNAVAILABLE",
                "bound_certificate_decision_plan_scoring_byte_replay": (
                    "UNAVAILABLE"
                ),
                "lock_d_credential_status": (
                    "STRUCTURAL_A_D_PAYLOAD_BOUND_VERIFIED"
                ),
                "scientific_certificates_issued": 0,
                "scoring_allowed": False,
            },
        }
    )
    return closure


def _valid_candidate_log(
    *,
    artifact_root: Path,
    run_id: str,
    fixture_sha256: str,
) -> str:
    return "\n".join(
        (
            "TASK4_RUNNER_SCHEMA=d2t_rna.task4_candidate_runner.v1",
            f"TASK4_RUN_ID={run_id}",
            "TASK4_RUNTIME=CPython 3.11.15",
            f"TASK4_CONTRACT_SHA256={CONTRACT_SHA256}",
            f"TASK4_DEPENDENCY_SNAPSHOT_SHA256={'b' * 64}",
            (
                "TASK4_PYTHON_ISOLATION_PASS="
                f"{artifact_root}/runs/{run_id}/pycache"
            ),
            (
                "TASK4_PRE_TEST_SOURCE_INDEX_SHA256="
                f"{SOURCE_INDEX_SHA256}"
            ),
            "TASK4_EXACT_TESTS_BEGIN",
            "55 passed in 1.00s",
            "TASK4_EXACT_TESTS_END",
            "TASK4_COMBINED_TESTS_BEGIN",
            "185 passed in 2.00s",
            "TASK4_COMBINED_TESTS_END",
            "TASK4_FULL_TESTS_BEGIN",
            "300 passed in 3.00s",
            "TASK4_FULL_TESTS_END",
            (
                "TASK4_POST_TEST_SOURCE_INDEX_SHA256="
                f"{SOURCE_INDEX_SHA256}"
            ),
            "TASK4_COMPILE_PASS",
            f"TASK4_FIXTURE_MANIFEST_SHA256={fixture_sha256}",
            "TASK4_GIT_DIFF_CHECK_PASS",
            "TASK4_EXISTING_MANIFEST_JSON_PASS",
            "TASK4_CANDIDATE_PASS",
            "",
        )
    )


def test_historical_anchor_literals_are_frozen() -> None:
    assert str(TASK3_CLOSURE_PATH) == (
        "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
        "task3-acceptance-recovery-20260730T011748p0800/closure.json"
    )
    assert TASK3_CLOSURE_SHA256 == (
        "60353d49876cc87217d983dd97a7bbd872b2ea3bd96396d74bd49402626c21de"
    )
    assert str(TASK4_ENTRY_GATE_PATH) == (
        "/mnt/cunyuliu/d2t-rna/artifacts/gates/"
        "task4-entry-gate-open-20260730T012421p0800.json"
    )
    assert TASK4_ENTRY_GATE_SHA256 == (
        "afb3582a5dcb4fd6c06505068299731687c4a2ab5d401d1d008d61103283a28d"
    )
    assert str(TASK4_RED_RECORD_PATH) == (
        "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
        "task4-red-20260730T013744p0800/red-test.json"
    )
    assert TASK4_RED_RECORD_SHA256 == (
        "f6403baa1a22a9009b23cd961ccade8e98c7843667e378c03769277d4ce5c30c"
    )
    assert str(TASK4_RED_LOG_PATH) == (
        "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
        "task4-red-20260730T013744p0800/pytest-red.log"
    )
    assert TASK4_RED_LOG_SHA256 == (
        "24b29268333094fb9c2236e2a9338ed95d499072b6eedc241afb73292e8b8bee"
    )
    assert hashlib.sha256(EXPECTED_TASK4_RED_LOG_BYTES).hexdigest() == (
        TASK4_RED_LOG_SHA256
    )


@pytest.mark.parametrize(
    "changed_flag",
    (
        "isolated",
        "no_site",
        "ignore_environment",
        "no_user_site",
        "safe_path",
    ),
)
def test_verifier_requires_every_python_isolation_flag(
    changed_flag: str,
) -> None:
    values = {
        "isolated": 1,
        "no_site": 1,
        "ignore_environment": 1,
        "no_user_site": 1,
        "safe_path": True,
    }
    _verify_runtime_isolation_flags(SimpleNamespace(**values))

    values[changed_flag] = False if changed_flag == "safe_path" else 0
    with pytest.raises(ValueError, match=changed_flag):
        _verify_runtime_isolation_flags(SimpleNamespace(**values))


def test_gate_manifest_records_require_literal_paths_and_hashes() -> None:
    _verify_historical_gate_records(
        deepcopy(EXPECTED_GATE_EVIDENCE_RECORDS)
    )

    changed_path = deepcopy(EXPECTED_GATE_EVIDENCE_RECORDS)
    changed_path["entry_gate"]["path"] += ".copy"
    with pytest.raises(ValueError, match="value changed"):
        _verify_historical_gate_records(changed_path)

    changed_hash = deepcopy(EXPECTED_GATE_EVIDENCE_RECORDS)
    changed_hash["red_test_record"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="value changed"):
        _verify_historical_gate_records(changed_hash)

    extra_field = deepcopy(EXPECTED_GATE_EVIDENCE_RECORDS)
    extra_field["red_test_log"]["description"] = "plausible but unregistered"
    with pytest.raises(ValueError, match="fields are not exact"):
        _verify_historical_gate_records(extra_field)


def test_entry_and_red_objects_require_recursive_exact_fields() -> None:
    _verify_task4_entry_gate_semantics(
        deepcopy(EXPECTED_TASK4_ENTRY_GATE)
    )
    _verify_task4_red_record_semantics(
        deepcopy(EXPECTED_TASK4_RED_RECORD)
    )

    entry_extra = deepcopy(EXPECTED_TASK4_ENTRY_GATE)
    entry_extra["task_contract"]["unregistered_limit"] = 1
    with pytest.raises(ValueError, match="fields are not exact"):
        _verify_task4_entry_gate_semantics(entry_extra)

    entry_type_swap = deepcopy(EXPECTED_TASK4_ENTRY_GATE)
    entry_type_swap["scientific_claim_boundary"]["gpu_required"] = 0
    with pytest.raises(TypeError, match="expected bool"):
        _verify_task4_entry_gate_semantics(entry_type_swap)

    red_extra = deepcopy(EXPECTED_TASK4_RED_RECORD)
    red_extra["expected_failure"]["plausible_note"] = "still red"
    with pytest.raises(ValueError, match="fields are not exact"):
        _verify_task4_red_record_semantics(red_extra)

    red_anchor_swap = deepcopy(EXPECTED_TASK4_RED_RECORD)
    red_anchor_swap["entry_gate"]["sha256"] = "f" * 64
    with pytest.raises(ValueError, match="value changed"):
        _verify_task4_red_record_semantics(red_anchor_swap)


def test_task3_closure_semantics_fail_closed() -> None:
    closure = _valid_task3_closure()
    _verify_task3_closure_semantics(closure)

    extra = deepcopy(closure)
    extra["status"] = "ACCEPTED"
    with pytest.raises(ValueError, match="fields are not exact"):
        _verify_task3_closure_semantics(extra)

    dirty = deepcopy(closure)
    dirty["working_tree"] = "DIRTY"
    with pytest.raises(ValueError, match="value changed"):
        _verify_task3_closure_semantics(dirty)

    unpublished = deepcopy(closure)
    unpublished["github"]["visibility"] = "PRIVATE"
    with pytest.raises(ValueError, match="value changed"):
        _verify_task3_closure_semantics(unpublished)

    scoring_enabled = deepcopy(closure)
    scoring_enabled["claim_state"]["scoring_allowed"] = True
    with pytest.raises(ValueError, match="value changed"):
        _verify_task3_closure_semantics(scoring_enabled)

    bool_certificate_count = deepcopy(closure)
    bool_certificate_count["claim_state"][
        "scientific_certificates_issued"
    ] = False
    with pytest.raises(TypeError, match="expected int"):
        _verify_task3_closure_semantics(bool_certificate_count)


def test_red_log_requires_the_exact_preserved_bytes(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "pytest-red.log"
    log_path.write_bytes(EXPECTED_TASK4_RED_LOG_BYTES)
    _verify_task4_red_log(log_path)

    log_path.write_bytes(EXPECTED_TASK4_RED_LOG_BYTES + b"\n")
    with pytest.raises(ValueError, match="bytes changed"):
        _verify_task4_red_log(log_path)


def test_candidate_log_uses_the_supplied_artifact_root(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "custom-artifacts"
    run_id = "task4-acceptance-20260730T010203+0800"
    run_dir = artifact_root / "runs" / run_id
    (run_dir / "pycache").mkdir(parents=True)
    log_path = run_dir / "run.log"
    fixture_sha256 = "a" * 64
    log_path.write_text(
        _valid_candidate_log(
            artifact_root=artifact_root,
            run_id=run_id,
            fixture_sha256=fixture_sha256,
        ),
        encoding="utf-8",
    )

    _verify_test_log(
        log_path,
        run_id=run_id,
        runtime={
            "implementation": "CPython",
            "python_version": "3.11.15",
            "dependency_snapshot_sha256": "b" * 64,
        },
        fixture_manifest_sha256=fixture_sha256,
        source_index_sha256=SOURCE_INDEX_SHA256,
        expected_counts=(55, 185, 300),
        artifact_root=artifact_root,
    )

    unrelated_root = tmp_path / "wrong-artifacts"
    unrelated_root.mkdir()
    with pytest.raises(
        ValueError,
        match="must remain under|canonically bound",
    ):
        _verify_test_log(
            log_path,
            run_id=run_id,
            runtime={
                "implementation": "CPython",
                "python_version": "3.11.15",
                "dependency_snapshot_sha256": "b" * 64,
            },
            fixture_manifest_sha256=fixture_sha256,
            source_index_sha256=SOURCE_INDEX_SHA256,
            expected_counts=(55, 185, 300),
            artifact_root=unrelated_root,
        )


def test_candidate_log_rejects_relocated_artifact_path(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    run_id = "task4-acceptance-20260730T010203+0800"
    canonical_run_dir = artifact_root / "runs" / run_id
    (canonical_run_dir / "pycache").mkdir(parents=True)
    relocated_run_dir = artifact_root / "relocated" / run_id
    relocated_run_dir.mkdir(parents=True)
    fixture_sha256 = "a" * 64
    relocated_log = relocated_run_dir / "run.log"
    relocated_log.write_text(
        _valid_candidate_log(
            artifact_root=artifact_root,
            run_id=run_id,
            fixture_sha256=fixture_sha256,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="canonically bound"):
        _verify_test_log(
            relocated_log,
            run_id=run_id,
            runtime={
                "implementation": "CPython",
                "python_version": "3.11.15",
                "dependency_snapshot_sha256": "b" * 64,
            },
            fixture_manifest_sha256=fixture_sha256,
            source_index_sha256=SOURCE_INDEX_SHA256,
            expected_counts=(55, 185, 300),
            artifact_root=artifact_root,
        )


def test_candidate_log_rejects_source_index_drift(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    run_id = "task4-acceptance-20260730T010203+0800"
    run_dir = artifact_root / "runs" / run_id
    (run_dir / "pycache").mkdir(parents=True)
    fixture_sha256 = "a" * 64
    log_path = run_dir / "run.log"
    log_path.write_text(
        _valid_candidate_log(
            artifact_root=artifact_root,
            run_id=run_id,
            fixture_sha256=fixture_sha256,
        ).replace(
            (
                "TASK4_POST_TEST_SOURCE_INDEX_SHA256="
                f"{SOURCE_INDEX_SHA256}"
            ),
            f"TASK4_POST_TEST_SOURCE_INDEX_SHA256={'d' * 64}",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="does not match"):
        _verify_test_log(
            log_path,
            run_id=run_id,
            runtime={
                "implementation": "CPython",
                "python_version": "3.11.15",
                "dependency_snapshot_sha256": "b" * 64,
            },
            fixture_manifest_sha256=fixture_sha256,
            source_index_sha256=SOURCE_INDEX_SHA256,
            expected_counts=(55, 185, 300),
            artifact_root=artifact_root,
        )


@pytest.mark.parametrize(
    "run_id",
    (
        "task4-acceptance-20260229T010203+0800",
        "task4-acceptance-20261301T010203+0800",
        "task4-acceptance-20260730T250203+0800",
        "task4-acceptance-20260730T010203p0800",
    ),
)
def test_candidate_run_id_requires_real_calendar_time(
    run_id: str,
) -> None:
    with pytest.raises(ValueError, match="run ID"):
        _validate_candidate_run_id(run_id)

    assert _validate_candidate_run_id(
        "task4-acceptance-20260730T010203+0800"
    ) == "task4-acceptance-20260730T010203+0800"
