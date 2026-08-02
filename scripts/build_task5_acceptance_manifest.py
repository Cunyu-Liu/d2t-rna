#!/usr/bin/env python3
"""Build the Task 5 pre-commit acceptance manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree

from d2t_rna.contracts.base import canonical_json_bytes, canonical_sha256
from scripts.verify_task5_acceptance_manifest import (
    ARTIFACT_ROOT,
    CLAIM_BOUNDARY,
    COMMIT_TITLE,
    CONTRACT_SHA256,
    EXPECTED_HISTORICAL_EVIDENCE,
    MANIFEST_SCHEMA,
    REPOSITORY,
    TASK4_ACCEPTANCE_COMMIT,
    TASK4_ACCEPTANCE_MANIFEST_SHA256,
    TASK4_CLOSURE_PATH,
    TASK4_CLOSURE_SHA256,
    _canonical_json_equal,
    _load_canonical_json,
    _sha256,
    _summary_between,
    _validate_run_id,
    _verify_external_file,
    _verify_historical_evidence,
    _verify_junit,
    _verify_test_log,
    build_runtime_dependency_snapshot,
    build_source_snapshot,
    derive_task4_nested_parent_binding,
    task5_delta_snapshot,
    verify_fixture,
    verify_manifest,
)


def _external_file(path: Path, *, root: Path, label: str) -> dict[str, str]:
    record = {
        "path": str(path.resolve()),
        "sha256": _sha256(path),
    }
    _verify_external_file(record, root=root, label=label)
    return record


def _candidate_counts(run_log: Path) -> tuple[int, int, int]:
    lines = run_log.read_text(encoding="utf-8").splitlines()
    return (
        _summary_between(
            lines,
            "TASK5_EVALUATION_TESTS_BEGIN",
            "TASK5_EVALUATION_TESTS_END",
        ),
        _summary_between(
            lines,
            "TASK5_COMBINED_TESTS_BEGIN",
            "TASK5_COMBINED_TESTS_END",
        ),
        _summary_between(
            lines,
            "TASK5_FULL_TESTS_BEGIN",
            "TASK5_FULL_TESTS_END",
        ),
    )


def _junit_count(path: Path) -> int:
    root = ElementTree.parse(path).getroot()
    suites = (
        (root,)
        if root.tag == "testsuite"
        else tuple(root.findall("testsuite"))
    )
    return sum(int(suite.attrib.get("tests", "0")) for suite in suites)


def build_manifest(
    *,
    project_root: Path,
    run_id: str,
    output_path: Path,
    artifact_root: Path = ARTIFACT_ROOT,
) -> dict[str, object]:
    _validate_run_id(run_id)
    expected_output = project_root / "manifests" / "task5_acceptance.json"
    if output_path.resolve() != expected_output.resolve():
        raise ValueError("Task 5 acceptance manifest output path changed")
    if output_path.exists() or output_path.is_symlink():
        raise FileExistsError(
            f"Task 5 acceptance manifest already exists: {output_path}"
        )
    _verify_historical_evidence(
        project_root,
        EXPECTED_HISTORICAL_EVIDENCE,
    )

    run_dir = artifact_root / "runs" / run_id
    if run_dir.is_symlink() or not run_dir.is_dir():
        raise ValueError("Task 5 candidate run directory is unavailable")
    run_log = run_dir / "run.log"
    fixture_path = run_dir / "fixture" / "fixture_manifest.json"
    source_snapshot_path = run_dir / "snapshots" / "source_index.json"
    post_source_snapshot_path = (
        run_dir / "snapshots" / "source_index_post_test.json"
    )
    runtime_snapshot_path = (
        run_dir / "snapshots" / "runtime_dependency_snapshot.json"
    )
    task4_parent_binding_path = (
        run_dir / "snapshots" / "task4_nested_parent_binding.json"
    )
    junit_paths = {
        name: run_dir / "junit" / f"{name}.xml"
        for name in ("evaluation", "combined", "full")
    }
    for label, path in (
        ("candidate run log", run_log),
        ("fixture manifest", fixture_path),
        ("source snapshot", source_snapshot_path),
        ("post-test source snapshot", post_source_snapshot_path),
        ("dependency snapshot", runtime_snapshot_path),
        ("nested Task 4 parent binding", task4_parent_binding_path),
        *((f"{name} JUnit", path) for name, path in junit_paths.items()),
    ):
        _verify_external_file(
            _external_file(path, root=artifact_root, label=label),
            root=artifact_root,
            label=label,
        )

    source_snapshot = _load_canonical_json(
        source_snapshot_path,
        label="Task 5 source snapshot",
    )
    post_source_snapshot = _load_canonical_json(
        post_source_snapshot_path,
        label="Task 5 post-test source snapshot",
    )
    live_source = build_source_snapshot(project_root)
    if (
        not _canonical_json_equal(source_snapshot, live_source)
        or not _canonical_json_equal(
            post_source_snapshot, source_snapshot
        )
    ):
        raise ValueError("Task 5 candidate source snapshot changed")
    runtime_snapshot = _load_canonical_json(
        runtime_snapshot_path,
        label="Task 5 dependency snapshot",
    )
    live_runtime = build_runtime_dependency_snapshot(project_root)
    if not _canonical_json_equal(runtime_snapshot, live_runtime):
        raise ValueError("Task 5 candidate dependency snapshot changed")
    task4_parent_binding = derive_task4_nested_parent_binding(
        project_root,
        runtime_snapshot=runtime_snapshot,
        source_snapshot=source_snapshot,
    )
    if _load_canonical_json(
        task4_parent_binding_path,
        label="Task 5 nested Task 4 parent binding",
    ) != task4_parent_binding:
        raise ValueError("Task 5 nested Task 4 parent binding changed")
    runtime = {
        "implementation": runtime_snapshot["implementation"],
        "python_version": runtime_snapshot["python_version"],
        "python_cache_tag": runtime_snapshot["python_cache_tag"],
        "gpu_required": False,
        "arithmetic": "fractions.Fraction",
        "dependency_snapshot": _external_file(
            runtime_snapshot_path,
            root=artifact_root,
            label="Task 5 dependency snapshot",
        ),
        "dependency_snapshot_sha256": canonical_sha256(
            runtime_snapshot
        ),
        "task4_parent_dependency_snapshot_sha256": (
            task4_parent_binding["dependency_snapshot_sha256"]
        ),
        "task4_parent_binding": _external_file(
            task4_parent_binding_path,
            root=artifact_root,
            label="Task 5 nested Task 4 parent binding",
        ),
    }
    counts = _candidate_counts(run_log)
    fixture_record = _external_file(
        fixture_path,
        root=artifact_root,
        label="Task 5 fixture manifest",
    )
    verify_fixture(
        project_root,
        fixture_path,
        artifact_root=artifact_root,
    )
    _verify_test_log(
        run_log,
        run_id=run_id,
        runtime=runtime,
        dependency_snapshot_sha256=runtime[
            "dependency_snapshot_sha256"
        ],
        source_index_sha256=source_snapshot["source_index_sha256"],
        task4_parent_dependency_snapshot_sha256=(
            task4_parent_binding["dependency_snapshot_sha256"]
        ),
        task4_parent_source_index_sha256=(
            task4_parent_binding["source_index_sha256"]
        ),
        fixture_manifest_sha256=fixture_record["sha256"],
        expected_counts=counts,
        artifact_root=artifact_root,
    )
    junit_records: dict[str, dict[str, str]] = {}
    for name, count in zip(
        ("evaluation", "combined", "full"),
        counts,
        strict=True,
    ):
        if _junit_count(junit_paths[name]) != count:
            raise ValueError(
                f"Task 5 {name} JUnit count differs from run log"
            )
        _verify_junit(
            junit_paths[name],
            expected_count=count,
            label=f"Task 5 {name} JUnit",
        )
        junit_records[name] = _external_file(
            junit_paths[name],
            root=artifact_root,
            label=f"Task 5 {name} JUnit",
        )

    delta = task5_delta_snapshot(
        project_root,
        require_post_commit=False,
    )
    manifest: dict[str, object] = {
        "schema": MANIFEST_SCHEMA,
        "task": 5,
        "status": "READY_FOR_COMMIT",
        "contract_sha256": CONTRACT_SHA256,
        "registered_commit_title": COMMIT_TITLE,
        "prior_task": {
            "task": 4,
            "accepted_commit": TASK4_ACCEPTANCE_COMMIT,
            "acceptance_manifest_sha256": (
                TASK4_ACCEPTANCE_MANIFEST_SHA256
            ),
            "post_commit_closure": {
                "path": str(TASK4_CLOSURE_PATH),
                "sha256": TASK4_CLOSURE_SHA256,
            },
        },
        "historical_evidence": EXPECTED_HISTORICAL_EVIDENCE,
        "runtime": runtime,
        "source_snapshot": {
            "artifact": _external_file(
                source_snapshot_path,
                root=artifact_root,
                label="Task 5 source snapshot",
            ),
            "post_test_artifact": _external_file(
                post_source_snapshot_path,
                root=artifact_root,
                label="Task 5 post-test source snapshot",
            ),
            "source_index": source_snapshot["source_index"],
            "source_index_sha256": source_snapshot[
                "source_index_sha256"
            ],
            "task4_parent_source_index_sha256": (
                task4_parent_binding["source_index_sha256"]
            ),
        },
        "task5_delta": {
            "base_commit": TASK4_ACCEPTANCE_COMMIT,
            "changed_paths": list(delta["changed_paths"]),
            "changed_paths_sha256": delta["changed_paths_sha256"],
        },
        "test_evidence": {
            "run_id": run_id,
            "evaluation_tests_passed": counts[0],
            "combined_tests_passed": counts[1],
            "full_tests_passed": counts[2],
            "run_log": _external_file(
                run_log,
                root=artifact_root,
                label="Task 5 candidate run log",
            ),
            "junit": junit_records,
        },
        "fixture_evidence": {
            "manifest": fixture_record,
            "all_registered_replays_passed": True,
            "risk_certificate_issued": False,
            "scientific_claim_authorized": False,
            "serialized_bearer_authorization": False,
        },
        "claim_boundary": CLAIM_BOUNDARY,
        "github": {
            "repository": REPOSITORY,
            "visibility": "PUBLIC",
            "branch": "main",
            "push_required_after_commit": True,
        },
        "post_commit_closure_required": True,
    }
    payload = canonical_json_bytes(manifest) + b"\n"
    draft = run_dir / "task5_acceptance_manifest.draft.json"
    with draft.open("xb") as stream:
        stream.write(payload)
    verify_manifest(
        project_root,
        draft,
        artifact_root=artifact_root,
        require_post_commit=False,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("xb") as stream:
        stream.write(payload)
    print(
        "TASK5_ACCEPTANCE_MANIFEST_SHA256="
        f"{hashlib.sha256(payload).hexdigest()}"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("manifests/task5_acceptance.json"),
    )
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    output = args.output
    if not output.is_absolute():
        output = project_root / output
    build_manifest(
        project_root=project_root,
        run_id=args.run_id,
        output_path=output,
    )


if __name__ == "__main__":
    main()
