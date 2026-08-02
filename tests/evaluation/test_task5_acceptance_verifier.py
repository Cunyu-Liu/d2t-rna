from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree

import pytest

from d2t_rna.contracts.base import canonical_json_bytes, canonical_sha256
from scripts import verify_task5_acceptance_manifest as verifier
from scripts.build_task5_acceptance_fixture import build_fixture
from scripts.verify_task5_acceptance_manifest import (
    CLAIM_BOUNDARY,
    CONTRACT_SHA256,
    EXPECTED_HISTORICAL_EVIDENCE,
    EXPECTED_MANIFEST_FIELDS,
    MANIFEST_SCHEMA,
    TASK4_ACCEPTANCE_COMMIT,
    TASK4_ACCEPTANCE_MANIFEST_SHA256,
    TASK4_CLOSURE_SHA256,
    _source_index,
    _validate_manifest_build_failure_record,
    _validate_repair_record_status,
    _validate_run_id,
    _validate_task5_delta_paths,
    derive_task4_nested_parent_binding,
    _verify_external_file,
    _verify_junit,
    _verify_test_log,
    source_index_sha256,
    verify_fixture,
)


RUN_ID = "task5-acceptance-20260730T190203+0800"
COUNTS = (61, 371, 489)
DEPENDENCY_SHA = "d" * 64
SOURCE_SHA = "e" * 64
TASK4_PARENT_DEPENDENCY_SHA = "a" * 64
TASK4_PARENT_SOURCE_SHA = "b" * 64


def _write_junit(path: Path, *, tests: int, skipped: int = 0) -> None:
    root = ElementTree.Element("testsuites")
    suite = ElementTree.SubElement(
        root,
        "testsuite",
        {
            "name": "pytest",
            "tests": str(tests),
            "errors": "0",
            "failures": "0",
            "skipped": str(skipped),
        },
    )
    for index in range(tests):
        ElementTree.SubElement(
            suite,
            "testcase",
            {"classname": "registered", "name": f"test_{index}"},
        )
    if skipped:
        ElementTree.SubElement(suite[0], "skipped")
    ElementTree.ElementTree(root).write(
        path,
        encoding="utf-8",
        xml_declaration=True,
    )


def _valid_candidate_log(
    artifact_root: Path,
    *,
    fixture_sha: str,
) -> Path:
    run_dir = artifact_root / "runs" / RUN_ID
    (run_dir / "pycache").mkdir(parents=True)
    log = run_dir / "run.log"
    lines = [
        "TASK5_CANDIDATE_RUNNER_SCHEMA=d2t_rna.task5_candidate_runner.v1",
        f"TASK5_RUN_ID={RUN_ID}",
        "TASK5_RUNTIME=CPython 3.11.15",
        f"TASK5_CONTRACT_SHA256={CONTRACT_SHA256}",
        f"TASK5_TASK4_ACCEPTANCE_COMMIT={TASK4_ACCEPTANCE_COMMIT}",
        (
            "TASK5_TASK4_ACCEPTANCE_MANIFEST_SHA256="
            f"{TASK4_ACCEPTANCE_MANIFEST_SHA256}"
        ),
        f"TASK5_TASK4_CLOSURE_SHA256={TASK4_CLOSURE_SHA256}",
        f"TASK5_DEPENDENCY_SNAPSHOT_SHA256={DEPENDENCY_SHA}",
        (
            "TASK5_TASK4_PARENT_DEPENDENCY_SNAPSHOT_SHA256="
            f"{TASK4_PARENT_DEPENDENCY_SHA}"
        ),
        (
            "TASK5_TASK4_PARENT_SOURCE_INDEX_SHA256="
            f"{TASK4_PARENT_SOURCE_SHA}"
        ),
        (
            "TASK5_PYTHON_ISOLATION_PASS="
            f"{run_dir / 'pycache'}"
        ),
        f"TASK5_PRE_TEST_SOURCE_INDEX_SHA256={SOURCE_SHA}",
        "TASK5_COMPILE_PASS",
        "TASK5_EVALUATION_TESTS_BEGIN",
        f"{COUNTS[0]} passed in 1.00s",
        "TASK5_EVALUATION_TESTS_END",
        "TASK5_COMBINED_TESTS_BEGIN",
        f"{COUNTS[1]} passed in 2.00s",
        "TASK5_COMBINED_TESTS_END",
        "TASK5_FULL_TESTS_BEGIN",
        f"{COUNTS[2]} passed in 3.00s",
        "TASK5_FULL_TESTS_END",
        f"TASK5_FIXTURE_MANIFEST_SHA256={fixture_sha}",
        f"TASK5_POST_TEST_SOURCE_INDEX_SHA256={SOURCE_SHA}",
        "TASK5_GIT_DIFF_CHECK_PASS",
        "TASK5_EXISTING_MANIFEST_JSON_PASS",
        "TASK5_SECRET_AUDIT_PASS",
        "TASK5_LARGE_FILE_AUDIT_PASS",
        "TASK5_CANDIDATE_PASS",
    ]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log


def test_source_index_is_dynamic_complete_and_non_self_referential(
    tmp_path: Path,
) -> None:
    for directory in (
        "src/pkg",
        "tests/unit",
        "scripts",
        "contracts",
        "docs/audit",
        "manifests",
    ):
        (tmp_path / directory).mkdir(parents=True, exist_ok=True)
    files = {
        "src/pkg/a.py": b"A = 1\n",
        "src/pkg/a.pyi": b"A: int\n",
        "src/pkg/py.typed": b"\n",
        "tests/unit/test_a.py": b"def test_a(): pass\n",
        "scripts/run.sh": b"#!/bin/bash\n",
        "scripts/tool.py": b"VALUE = 1\n",
        "scripts/config.yaml": b"registered: true\n",
        "contracts/D2T-RNA-v6.1-frozen-plan.md": b"contract\n",
        "docs/audit/task-5-evaluation.md": b"audit\n",
        "manifests/project_contract.json": b"{}\n",
        "manifests/task5_acceptance.json": b'{"self": true}\n',
        "pyproject.toml": b"[project]\n",
        "README.md": b"readme\n",
    }
    for relative, payload in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    (tmp_path / "scripts" / "__pycache__").mkdir()
    (tmp_path / "scripts" / "__pycache__" / "tool.pyc").write_bytes(b"x")

    index = _source_index(tmp_path)
    assert tuple(index) == tuple(sorted(index))
    assert "src/pkg/a.py" in index
    assert "scripts/run.sh" in index
    assert "scripts/config.yaml" in index
    assert "docs/audit/task-5-evaluation.md" in index
    assert "manifests/task5_acceptance.json" not in index
    assert not any("__pycache__" in path for path in index)
    first = source_index_sha256(tmp_path)

    (tmp_path / "tests" / "unit" / "future_task6.py").write_text(
        "VALUE = 6\n",
        encoding="utf-8",
    )
    second = source_index_sha256(tmp_path)
    assert first != second
    assert "tests/unit/future_task6.py" in _source_index(tmp_path)


def test_source_index_rejects_execution_symlink(tmp_path: Path) -> None:
    for directory in ("src", "tests", "scripts", "contracts", "manifests"):
        (tmp_path / directory).mkdir()
    (tmp_path / "contracts" / "D2T-RNA-v6.1-frozen-plan.md").write_text(
        "contract\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    target = tmp_path / "outside.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "scripts" / "linked.py").symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        _source_index(tmp_path)


@pytest.mark.parametrize(
    ("relative", "payload", "message"),
    (
        ("scripts/legacy.pyc", b"bytecode", "bytecode"),
        ("src/native.so", b"native", "native"),
    ),
)
def test_source_index_rejects_sourceless_or_native_execution_input(
    tmp_path: Path,
    relative: str,
    payload: bytes,
    message: str,
) -> None:
    for directory in ("src", "tests", "scripts", "contracts", "manifests"):
        (tmp_path / directory).mkdir()
    (tmp_path / "contracts" / "D2T-RNA-v6.1-frozen-plan.md").write_text(
        "contract\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    path = tmp_path / relative
    path.write_bytes(payload)
    with pytest.raises(ValueError, match=message):
        _source_index(tmp_path)


def test_source_index_ignores_only_generated_pycache_bytecode(
    tmp_path: Path,
) -> None:
    for directory in (
        "src",
        "tests",
        "scripts/__pycache__",
        "contracts",
        "manifests",
    ):
        (tmp_path / directory).mkdir(parents=True)
    (tmp_path / "contracts" / "D2T-RNA-v6.1-frozen-plan.md").write_text(
        "contract\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("readme\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    generated = tmp_path / "scripts" / "__pycache__" / "tool.pyc"
    generated.write_bytes(b"generated")
    assert not any("__pycache__" in path for path in _source_index(tmp_path))
    unexpected = generated.with_name("config.yaml")
    unexpected.write_text("forged: true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non-generated"):
        _source_index(tmp_path)


def _task4_parent_binding_snapshots() -> tuple[dict, dict, tuple[str, ...]]:
    from scripts.verify_task4_acceptance_manifest import (
        EXPECTED_SOURCE_PATHS,
    )

    task4_paths = tuple(sorted(EXPECTED_SOURCE_PATHS))
    task4_runtime = {
        "schema": "registered-task4-runtime-for-unit-test",
        "members": ("python", "stdlib", "dependencies"),
    }
    runtime = {
        "schema": verifier.RUNTIME_SNAPSHOT_SCHEMA,
        "implementation": "CPython",
        "python_version": "3.11.15",
        "python_cache_tag": "cpython-311",
        "reused_task4_helper_sha256": {
            str(verifier.TASK4_ISOLATED_LAUNCHER_PATH): (
                verifier.TASK4_ISOLATED_LAUNCHER_SHA256
            ),
            str(verifier.TASK4_RUNTIME_HELPER_PATH): (
                verifier.TASK4_RUNTIME_HELPER_SHA256
            ),
        },
        "task4_runtime_dependency_snapshot": task4_runtime,
        "task4_runtime_dependency_snapshot_sha256": canonical_sha256(
            task4_runtime
        ),
    }
    source_index = {
        path: hashlib.sha256(path.encode("utf-8")).hexdigest()
        for path in task4_paths
    }
    source_index["tests/future_task6.py"] = "f" * 64
    source = {
        "schema": verifier.SOURCE_INDEX_SCHEMA,
        "source_index": source_index,
        "source_index_sha256": canonical_sha256(source_index),
        "execution_roots_regular_file_policy": "registered",
        "generated_cache_policy": "registered",
        "self_referential_paths_excluded": (
            "manifests/task5_acceptance.json",
        ),
        "future_descendant_mutation_policy": "FAIL_CLOSED",
    }
    return runtime, source, task4_paths


def test_task4_nested_parent_binding_uses_exact_live_subclosures() -> None:
    project_root = Path(__file__).resolve().parents[2]
    runtime, source, task4_paths = _task4_parent_binding_snapshots()
    binding = derive_task4_nested_parent_binding(
        project_root,
        runtime_snapshot=runtime,
        source_snapshot=source,
    )
    task4_projection = {
        path: source["source_index"][path] for path in task4_paths
    }
    assert binding == {
        "schema": verifier.TASK4_NESTED_PARENT_BINDING_SCHEMA,
        "dependency_snapshot_sha256": (
            runtime["task4_runtime_dependency_snapshot_sha256"]
        ),
        "source_index_sha256": canonical_sha256(task4_projection),
    }
    assert binding["source_index_sha256"] != source["source_index_sha256"]
    assert binding["dependency_snapshot_sha256"] != canonical_sha256(runtime)


@pytest.mark.parametrize(
    "mutation",
    (
        "inner_dependency_hash",
        "missing_task4_source",
        "invalid_source_digest",
        "outer_source_hash",
    ),
)
def test_task4_nested_parent_binding_rejects_wrong_digest_domain(
    mutation: str,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    runtime, source, task4_paths = _task4_parent_binding_snapshots()
    if mutation == "inner_dependency_hash":
        runtime[
            "task4_runtime_dependency_snapshot_sha256"
        ] = "0" * 64
    elif mutation == "missing_task4_source":
        source["source_index"].pop(task4_paths[0])
        source["source_index_sha256"] = canonical_sha256(
            source["source_index"]
        )
    elif mutation == "invalid_source_digest":
        source["source_index"][task4_paths[0]] = "not-a-sha"
        source["source_index_sha256"] = canonical_sha256(
            source["source_index"]
        )
    else:
        source["source_index_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="Task 4|source snapshot"):
        derive_task4_nested_parent_binding(
            project_root,
            runtime_snapshot=deepcopy(runtime),
            source_snapshot=deepcopy(source),
        )


def test_snapshot_equivalence_uses_canonical_json_not_container_identity() -> None:
    loaded = {
        "paths": ["a", "b"],
        "nested": {"aliases": ["x"]},
    }
    live = {
        "paths": ("a", "b"),
        "nested": {"aliases": ("x",)},
    }
    assert loaded != live
    assert verifier._canonical_json_equal(loaded, live)
    assert not verifier._canonical_json_equal(
        loaded,
        {"paths": ("a", "changed"), "nested": {"aliases": ("x",)}},
    )


def test_task4_parent_binding_cli_paths_are_one_canonical_snapshot_dir(
    tmp_path: Path,
) -> None:
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    runtime_path = snapshot_dir / "runtime_dependency_snapshot.json"
    source_path = snapshot_dir / "source_index.json"
    runtime_path.write_text("{}\n", encoding="utf-8")
    source_path.write_text("{}\n", encoding="utf-8")
    output_path = snapshot_dir / "task4_nested_parent_binding.json"
    assert verifier._resolve_task4_binding_cli_paths(
        output_path=output_path,
        runtime_snapshot_path=runtime_path,
        source_snapshot_path=source_path,
    ) == (output_path, runtime_path, source_path)

    other_dir = tmp_path / "other"
    other_dir.mkdir()
    other_source = other_dir / "source_index.json"
    other_source.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="share one canonical directory"):
        verifier._resolve_task4_binding_cli_paths(
            output_path=output_path,
            runtime_snapshot_path=runtime_path,
            source_snapshot_path=other_source,
        )

    output_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="fresh registered artifact"):
        verifier._resolve_task4_binding_cli_paths(
            output_path=output_path,
            runtime_snapshot_path=runtime_path,
            source_snapshot_path=source_path,
        )


def test_candidate_log_requires_ordered_complete_transcript(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    log = _valid_candidate_log(artifact_root, fixture_sha="f" * 64)
    assert _verify_test_log(
        log,
        run_id=RUN_ID,
        runtime={
            "implementation": "CPython",
            "python_version": "3.11.15",
        },
        dependency_snapshot_sha256=DEPENDENCY_SHA,
        source_index_sha256=SOURCE_SHA,
        task4_parent_dependency_snapshot_sha256=(
            TASK4_PARENT_DEPENDENCY_SHA
        ),
        task4_parent_source_index_sha256=TASK4_PARENT_SOURCE_SHA,
        fixture_manifest_sha256="f" * 64,
        expected_counts=COUNTS,
        artifact_root=artifact_root,
    ) == COUNTS

    log.write_text(
        log.read_text(encoding="utf-8").replace(
            "TASK5_SECRET_AUDIT_PASS\n",
            "TASK5_SECRET_AUDIT_PASS\n999 passed in 0.01s\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="exactly three"):
        _verify_test_log(
            log,
            run_id=RUN_ID,
            runtime={
                "implementation": "CPython",
                "python_version": "3.11.15",
            },
            dependency_snapshot_sha256=DEPENDENCY_SHA,
            source_index_sha256=SOURCE_SHA,
            task4_parent_dependency_snapshot_sha256=(
                TASK4_PARENT_DEPENDENCY_SHA
            ),
            task4_parent_source_index_sha256=TASK4_PARENT_SOURCE_SHA,
            fixture_manifest_sha256="f" * 64,
            expected_counts=COUNTS,
            artifact_root=artifact_root,
        )


def test_candidate_log_rejects_hidden_failure_beside_pass_summary(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    log = _valid_candidate_log(artifact_root, fixture_sha="f" * 64)
    text = log.read_text(encoding="utf-8").replace(
        f"{COUNTS[0]} passed in 1.00s",
        f"1 failed, {COUNTS[0]} passed in 1.00s\n"
        f"{COUNTS[0]} passed in 1.00s",
    )
    log.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="failure marker"):
        _verify_test_log(
            log,
            run_id=RUN_ID,
            runtime={
                "implementation": "CPython",
                "python_version": "3.11.15",
            },
            dependency_snapshot_sha256=DEPENDENCY_SHA,
            source_index_sha256=SOURCE_SHA,
            task4_parent_dependency_snapshot_sha256=(
                TASK4_PARENT_DEPENDENCY_SHA
            ),
            task4_parent_source_index_sha256=TASK4_PARENT_SOURCE_SHA,
            fixture_manifest_sha256="f" * 64,
            expected_counts=COUNTS,
            artifact_root=artifact_root,
        )


def test_junit_rejects_skip_failure_and_count_forgery(tmp_path: Path) -> None:
    valid = tmp_path / "valid.xml"
    _write_junit(valid, tests=7)
    _verify_junit(valid, expected_count=7, label="valid")

    skipped = tmp_path / "skipped.xml"
    _write_junit(skipped, tests=7, skipped=1)
    with pytest.raises(ValueError, match="skipped"):
        _verify_junit(skipped, expected_count=7, label="skipped")
    with pytest.raises(ValueError, match="count"):
        _verify_junit(valid, expected_count=8, label="forged")


def test_external_file_rejects_path_and_hash_substitution(
    tmp_path: Path,
) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    registered = root / "registered.json"
    substituted = root / "substituted.json"
    registered.write_text("{}\n", encoding="utf-8")
    substituted.write_text('{"forged":true}\n', encoding="utf-8")
    registered_sha = hashlib.sha256(registered.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="registered path"):
        _verify_external_file(
            {
                "path": str(substituted),
                "sha256": hashlib.sha256(
                    substituted.read_bytes()
                ).hexdigest(),
            },
            root=root,
            label="evidence",
            expected_path=registered,
        )
    with pytest.raises(ValueError, match="bytes"):
        _verify_external_file(
            {
                "path": str(registered),
                "sha256": "f" * 64,
            },
            root=root,
            label="evidence",
        )
    assert registered_sha != "f" * 64


def test_fixture_replays_every_embedded_artifact_and_claim_boundary(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    output = artifact_root / "runs" / RUN_ID / "fixture"
    manifest = build_fixture(
        project_root=Path(__file__).resolve().parents[2],
        output_dir=output,
        artifact_root=artifact_root,
    )
    verified = verify_fixture(
        Path(__file__).resolve().parents[2],
        output / "fixture_manifest.json",
        artifact_root=artifact_root,
    )
    assert verified == manifest
    assert verified["claim_boundary"] == CLAIM_BOUNDARY
    assert verified["replay"]["all_registered_replays_passed"] is True
    assert verified["replay"]["risk_certificate_issued"] is False


def test_fixture_rejects_nested_artifact_tamper_even_if_manifest_rehashed(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    output = artifact_root / "runs" / RUN_ID / "fixture"
    build_fixture(
        project_root=Path(__file__).resolve().parents[2],
        output_dir=output,
        artifact_root=artifact_root,
    )
    scenario_path = output / "scenario_aggregate.json"
    raw = json.loads(scenario_path.read_text(encoding="utf-8"))
    raw["continuous_uncertainty_set_claim"] = True
    scenario_path.write_bytes(canonical_json_bytes(raw) + b"\n")

    fixture_path = output / "fixture_manifest.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    fixture["artifacts"]["scenario_aggregate"]["sha256"] = hashlib.sha256(
        scenario_path.read_bytes()
    ).hexdigest()
    fixture_path.write_bytes(canonical_json_bytes(fixture) + b"\n")

    with pytest.raises(ValueError, match="scenario|replay|literal"):
        verify_fixture(
            Path(__file__).resolve().parents[2],
            fixture_path,
            artifact_root=artifact_root,
        )


def test_frozen_authority_and_claim_boundary_are_exact() -> None:
    assert CONTRACT_SHA256 == (
        "87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d"
    )
    assert TASK4_ACCEPTANCE_COMMIT == (
        "4793026c1e709b7ca78042b8a10294fe569d7b8c"
    )
    assert TASK4_ACCEPTANCE_MANIFEST_SHA256 == (
        "61348d3d00fb96c543e38ffa3b4ab0e15749214ebe54c875024d8efa0a600e96"
    )
    assert TASK4_CLOSURE_SHA256 == (
        "c023cb1efcfa8cc6d4fe36227d70075bab1a34b7f6cd2939693375016920c068"
    )
    assert CLAIM_BOUNDARY == {
        "claim_domain": "TASK5_SYNTHETIC_SOFTWARE_EVALUATION_ONLY",
        "probability_scope": "SYNTHETIC_KNOWN_CHANNEL",
        "finite_registered_scenarios_only": True,
        "risk_certificate_issued": False,
        "formal_scientific_certificate_authorized": False,
        "prospective_claim_authorized": False,
        "new_library_claim_authorized": False,
        "native_t4_claim_authorized": False,
        "population_claim_authorized": False,
        "observed_dataset_qa_completed": False,
        "scientific_conclusion_authorized": False,
        "serialized_bearer_authorization": False,
    }
    assert EXPECTED_HISTORICAL_EVIDENCE[
        "task5_rejected_green_log"
    ]["status"] == "NOT_ACCEPTANCE"
    assert EXPECTED_HISTORICAL_EVIDENCE["task5_red_log"] == {
        "path": (
            "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
            "task5-red-20260730T165809p0800/pytest-red.log"
        ),
        "sha256": (
            "1e43f7ab5edbc879f54535ec8f560a4a"
            "1f82a52b80ff58d911ed580b8919ff84"
        ),
    }
    assert EXPECTED_HISTORICAL_EVIDENCE[
        "task5_adversarial_pause"
    ]["status"] == "PAUSED_FOR_FAIL_CLOSED_REPAIR"
    assert EXPECTED_HISTORICAL_EVIDENCE[
        "task5_corrected_repair_green_log_not_acceptance"
    ]["status"] == "NOT_ACCEPTANCE"
    assert EXPECTED_HISTORICAL_EVIDENCE[
        "task5_corrected_repair_record_not_acceptance"
    ]["status"] == "NOT_ACCEPTANCE"
    assert EXPECTED_HISTORICAL_EVIDENCE[
        "task5_corrected_repair_record_not_acceptance"
    ]["record_status"] == "CORRECTED_TARGETED_GREEN_NOT_ACCEPTANCE"
    assert EXPECTED_HISTORICAL_EVIDENCE[
        "task5_cross_audit_pause"
    ]["status"] == "PAUSED_FOR_FORMAL_PROVENANCE_REPAIR"
    assert EXPECTED_HISTORICAL_EVIDENCE[
        "task5_risk_wrapper_pause"
    ] == {
        "path": (
            "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
            "task5-risk-wrapper-pause-20260730T192413p0800/"
            "risk-wrapper-pause.json"
        ),
        "sha256": (
            "5de706de64c39aab350d1679242d62809"
            "dad94c48f9f0c656f604d44021a679c"
        ),
        "status": "PAUSED_FOR_RISK_WRAPPER_EXECUTION_CLOSURE_REPAIR",
    }
    assert EXPECTED_HISTORICAL_EVIDENCE[
        "task5_runtime_provenance_pause"
    ] == {
        "path": (
            "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
            "task5-runtime-provenance-pause-20260730T194019p0800/"
            "runtime-provenance-pause.json"
        ),
        "sha256": (
            "9a4cd3aff53140e5cdef1a7a4cda4504"
            "d45fc6ed49db3a96288d15badb7ece8c"
        ),
        "status": "PAUSED_FOR_PLANNER_RORC_CFA_PROVENANCE_REPAIR",
    }
    assert EXPECTED_HISTORICAL_EVIDENCE[
        "task5_parent_binding_candidate_failure"
    ] == {
        "path": (
            "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
            "task5-acceptance-20260730T201740+0800/failure-record.json"
        ),
        "sha256": (
            "84dd9e3767511faeb6b15991d3cce78b"
            "efaba71a4016b5c27d528e6d9105ffce"
        ),
        "status": "FAILED_WITH_EVIDENCE_PRESERVED_NOT_ACCEPTANCE",
    }
    assert EXPECTED_HISTORICAL_EVIDENCE[
        "task5_targeted_repair_preflight_failure"
    ] == {
        "path": (
            "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
            "task5-parent-binding-repair-20260731T052401+0800/"
            "failure-record.json"
        ),
        "sha256": (
            "39df71b945f826dcddcfe011c14f68c09"
            "f43866c6b1e925dc70d314324217f8d"
        ),
        "status": "FAILED_WITH_EVIDENCE_PRESERVED_NOT_ACCEPTANCE",
    }
    assert EXPECTED_HISTORICAL_EVIDENCE[
        "task5_parent_binding_corrected_targeted_green_not_acceptance"
    ] == {
        "path": (
            "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
            "task5-parent-binding-repair-20260731T053556+0800/"
            "repair-record.json"
        ),
        "sha256": (
            "801b248a0677a213c921c899be928aa79"
            "70c6161619d3c66a5d4066cb0aec643"
        ),
        "status": "CORRECTED_TARGETED_GREEN_NOT_ACCEPTANCE",
    }
    assert EXPECTED_HISTORICAL_EVIDENCE[
        "task5_manifest_build_canonical_equivalence_failure"
    ] == {
        "path": (
            "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
            "task5-manifest-build-20260731T234517+0800/"
            "failure-record.json"
        ),
        "sha256": (
            "549d722e83d1e9e00ac804097abf12e96"
            "e1997505b54dbcc3f474c5b43c3ae63"
        ),
        "status": "FAILED_WITH_EVIDENCE_PRESERVED_NOT_ACCEPTANCE",
    }


def test_manifest_build_failure_is_exact_and_candidate_is_consumed() -> None:
    record = json.loads(
        verifier.TASK5_MANIFEST_BUILD_FAILURE_RECORD_PATH.read_text(
            encoding="utf-8"
        )
    )
    _validate_manifest_build_failure_record(record)
    with pytest.raises(ValueError, match="registered failed evidence"):
        _validate_run_id("task5-acceptance-20260731T055458+0800")
    assert (
        _validate_run_id("task5-acceptance-20260801T000001+0800")
        == "task5-acceptance-20260801T000001+0800"
    )

    def set_top_level(raw: dict[str, object]) -> None:
        raw["acceptance_authorized"] = True

    def set_canonical_digest(raw: dict[str, object]) -> None:
        canonical = raw["canonical_equality"]
        assert isinstance(canonical, dict)
        canonical["runtime_snapshot_sha256"] = "0" * 64

    def set_evidence_digest(raw: dict[str, object]) -> None:
        evidence = raw["evidence"]
        assert isinstance(evidence, dict)
        build_log = evidence["build_log"]
        assert isinstance(build_log, dict)
        build_log["sha256"] = "0" * 64

    def set_type_mismatch(raw: dict[str, object]) -> None:
        mismatches = raw["type_mismatches"]
        assert isinstance(mismatches, dict)
        mismatches["source"] = []

    def add_unregistered_field(raw: dict[str, object]) -> None:
        raw["scientific_claim"] = True

    for mutate in (
        set_top_level,
        set_canonical_digest,
        set_evidence_digest,
        set_type_mismatch,
        add_unregistered_field,
    ):
        tampered = deepcopy(record)
        mutate(tampered)
        with pytest.raises(
            ValueError,
            match="manifest-build failure semantics changed",
        ):
            _validate_manifest_build_failure_record(tampered)


@pytest.mark.parametrize(
    "status",
    (
        "NOT_ACCEPTANCE",
        "GREEN_NOT_ACCEPTANCE",
        "CORRECTED_TARGETED_GREEN",
        "ACCEPTANCE",
    ),
)
def test_repair_record_status_is_exact_not_a_substring(
    status: str,
) -> None:
    with pytest.raises(ValueError, match="promoted"):
        _validate_repair_record_status({"status": status})
    _validate_repair_record_status(
        {"status": "CORRECTED_TARGETED_GREEN_NOT_ACCEPTANCE"}
    )


def test_manifest_claim_tamper_fails_before_evidence_is_considered(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifests" / "task5_acceptance.json"
    manifest_path.parent.mkdir()
    raw = {name: None for name in EXPECTED_MANIFEST_FIELDS}
    raw.update(
        {
            "schema": MANIFEST_SCHEMA,
            "task": 5,
            "status": "READY_FOR_COMMIT",
            "contract_sha256": CONTRACT_SHA256,
            "registered_commit_title": (
                "feat(evaluation): unify proof manifests and "
                "baseline feasibility"
            ),
            "claim_boundary": {
                **CLAIM_BOUNDARY,
                "scientific_conclusion_authorized": True,
            },
        }
    )
    manifest_path.write_bytes(canonical_json_bytes(raw) + b"\n")
    with pytest.raises(ValueError, match="authority or claim"):
        verifier.verify_manifest(tmp_path, manifest_path)


def test_shell_runners_pin_isolation_and_required_audits() -> None:
    project_root = Path(__file__).resolve().parents[2]
    for name in ("run_task5_candidate.sh", "run_task5_acceptance.sh"):
        text = (project_root / "scripts" / name).read_text(encoding="utf-8")
        assert text.splitlines()[0] == "#!/bin/bash"
        assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1" in text
        assert '"${python_bin}" -I -S -B -X' in text
        assert "task4_isolated_python.py" in text
        assert (
            "01e8ac006837a46faf7208630df8cc362"
            "a1e1713c5ecf38229c72c60ec3bbf51"
        ) in text
        assert (
            "1bb76747e04ebb527c79105b2349bdd64"
            "8210a30a86498de065330b4e5541b5f"
        ) in text
        assert "for execution_root in src tests scripts" in text
        assert "TASK5_PRE_TEST_SOURCE_INDEX_SHA256" in text
        assert "TASK5_POST_TEST_SOURCE_INDEX_SHA256" in text
        assert "source_index_post_test.json" in text
        assert "--write-task4-nested-parent-binding" in text
        dependency_export = (
            "export TASK4_REGISTERED_DEPENDENCY_SNAPSHOT_SHA256="
        )
        source_export = "export TASK4_REGISTERED_SOURCE_INDEX_SHA256="
        first_test = text.index("TASK5_EVALUATION_TESTS_BEGIN")
        assert text.index(dependency_export) < first_test
        assert text.index(source_export) < first_test
        assert "task4_parent_dependency_sha" in text
        assert "task4_parent_source_sha" in text
        assert "TASK5_TASK4_PARENT_DEPENDENCY_SNAPSHOT_SHA256" in text
        assert "TASK5_TASK4_PARENT_SOURCE_INDEX_SHA256" in text
        assert "tests/evaluation tests/exact tests/probability tests/contracts" in text
        assert "TASK5_SECRET_AUDIT_PASS" in text
        assert "TASK5_LARGE_FILE_AUDIT_PASS" in text


def test_manifest_and_closure_use_canonical_snapshot_equivalence() -> None:
    project_root = Path(__file__).resolve().parents[2]
    for name in (
        "build_task5_acceptance_manifest.py",
        "build_task5_post_commit_closure.py",
        "verify_task5_acceptance_manifest.py",
    ):
        text = (project_root / "scripts" / name).read_text(encoding="utf-8")
        assert "_canonical_json_equal(" in text
        assert "source_snapshot != live_source" not in text
        assert "runtime_snapshot != live_runtime" not in text


def test_task5_verifier_does_not_call_task4_strict_source_index() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")
    assert "source_index_sha256 as" not in source
    assert "_source_index as" not in source
    assert "verify_task4_acceptance_manifest import _source_index" not in source


def test_fixture_uses_formal_task4_replay_and_bulk_seed_declarations() -> None:
    project_root = Path(__file__).resolve().parents[2]
    source = (
        project_root / "scripts" / "build_task5_acceptance_fixture.py"
    ).read_text(encoding="utf-8")
    assert "evaluate_registered_exact_synthetic_coverage_report" in source
    assert "build_exact_synthetic_scenario_artifact" in source
    assert "build_baseline_seed_declaration" in source
    assert "build_baseline_evaluation_batch_from_declarations" in source
    assert "build_exact_enumeration_artifact" not in source
    assert "build_baseline_seed_result" not in source


def test_task5_delta_requires_risk_binding_as_a_first_class_change() -> None:
    required = (
        "src/d2t_rna/evaluation/scenario.py",
        "src/d2t_rna/evaluation/milp_check.py",
        "src/d2t_rna/evaluation/planner.py",
        "src/d2t_rna/evaluation/risk_binding.py",
        "src/d2t_rna/evaluation/baselines.py",
        "docs/audit/task-5-evaluation.md",
        "manifests/task5_acceptance.json",
    )
    _validate_task5_delta_paths(required)
    with pytest.raises(ValueError, match="risk_binding.py"):
        _validate_task5_delta_paths(
            tuple(
                path
                for path in required
                if path != "src/d2t_rna/evaluation/risk_binding.py"
            )
        )
