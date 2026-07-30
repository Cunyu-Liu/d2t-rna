#!/usr/bin/env python3
"""Build the Task 4 pre-commit manifest from one completed candidate run."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import platform
import sys
from xml.etree import ElementTree

from scripts.verify_task4_acceptance_manifest import (
    ARTIFACT_ROOT,
    COMMIT_TITLE,
    CONTRACT_SHA256,
    EXPECTED_GATE_EVIDENCE_RECORDS,
    _runtime_dependency_snapshot,
    _source_index,
    _summary_between,
    _validate_candidate_run_id,
    _verify_junit,
    _verify_test_log,
    canonical_json_bytes,
    canonical_sha256,
    verify_manifest,
)

import pydantic


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_counts(run_log: Path) -> tuple[int, int, int]:
    lines = run_log.read_text(encoding="utf-8").splitlines()
    return (
        _summary_between(
            lines,
            "TASK4_EXACT_TESTS_BEGIN",
            "TASK4_EXACT_TESTS_END",
        ),
        _summary_between(
            lines,
            "TASK4_COMBINED_TESTS_BEGIN",
            "TASK4_COMBINED_TESTS_END",
        ),
        _summary_between(
            lines,
            "TASK4_FULL_TESTS_BEGIN",
            "TASK4_FULL_TESTS_END",
        ),
    )


def _junit_count(path: Path) -> int:
    root = ElementTree.parse(path).getroot()
    suites = tuple(root.iter("testsuite"))
    if len(suites) != 1 or "tests" not in suites[0].attrib:
        raise ValueError(f"Task 4 JUnit aggregate is malformed: {path}")
    return int(suites[0].attrib["tests"])


def _external_file(path: Path) -> dict[str, str]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError(
            f"Task 4 evidence must be an absolute non-symlink file: {path}"
        )
    return {"path": str(path.resolve()), "sha256": _sha256(path)}


def build_manifest(
    *,
    project_root: Path,
    run_id: str,
    output_path: Path,
    artifact_root: Path = ARTIFACT_ROOT,
) -> dict[str, object]:
    _validate_candidate_run_id(run_id)
    expected_output = project_root / "manifests" / "task4_acceptance.json"
    if output_path.resolve() != expected_output.resolve():
        raise ValueError("Task 4 acceptance manifest output path changed")
    if output_path.exists() or output_path.is_symlink():
        raise FileExistsError(f"Task 4 acceptance manifest exists: {output_path}")

    run_dir = artifact_root / "runs" / run_id
    if run_dir.is_symlink() or not run_dir.is_dir():
        raise ValueError("Task 4 candidate run directory is unavailable")
    run_log = run_dir / "run.log"
    fixture_manifest = run_dir / "fixture" / "fixture_manifest.json"
    junit_paths = {
        "exact": run_dir / "junit" / "exact.xml",
        "combined": run_dir / "junit" / "combined.xml",
        "full": run_dir / "junit" / "full.xml",
    }
    for path in (run_log, fixture_manifest, *junit_paths.values()):
        _external_file(path)

    dependency_snapshot = _runtime_dependency_snapshot(project_root)
    dependencies = dependency_snapshot["dependencies"]
    if type(dependencies) is not dict:
        raise TypeError("Task 4 dependency snapshot is malformed")
    runtime = {
        "python_version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "python_cache_tag": sys.implementation.cache_tag,
        "pydantic_version": pydantic.__version__,
        "pydantic_core_version": (
            dependencies["pydantic_core"]["version"]
        ),
        "pytest_version": dependencies["pytest"]["version"],
        "python_executable_sha256": (
            dependency_snapshot["python_executable_sha256"]
        ),
        "dependency_snapshot_sha256": canonical_sha256(
            dependency_snapshot
        ),
        "gpu_required": False,
        "arithmetic": "fractions.Fraction",
    }
    if (
        runtime["implementation"] != "CPython"
        or not str(runtime["python_version"]).startswith("3.11.")
    ):
        raise ValueError("Task 4 manifest must be built with CPython 3.11")

    source_index = _source_index(project_root)
    source_index_digest = canonical_sha256(source_index)
    counts = _candidate_counts(run_log)
    fixture_record = _external_file(fixture_manifest)
    _verify_test_log(
        run_log,
        run_id=run_id,
        runtime=runtime,
        fixture_manifest_sha256=fixture_record["sha256"],
        source_index_sha256=source_index_digest,
        expected_counts=counts,
        artifact_root=artifact_root,
    )
    junit_records: dict[str, dict[str, str]] = {}
    for name, expected_count in zip(
        ("exact", "combined", "full"),
        counts,
        strict=True,
    ):
        path = junit_paths[name]
        if _junit_count(path) != expected_count:
            raise ValueError(f"Task 4 {name} JUnit count differs from run log")
        _verify_junit(
            path,
            expected_count=expected_count,
            label=f"Task 4 {name} JUnit",
        )
        junit_records[name] = _external_file(path)

    manifest: dict[str, object] = {
        "schema": "d2t_rna.task4_acceptance_manifest.v2",
        "task": 4,
        "status": "READY_FOR_COMMIT",
        "contract_sha256": CONTRACT_SHA256,
        "registered_commit_title": COMMIT_TITLE,
        "runtime": runtime,
        "gate_evidence": EXPECTED_GATE_EVIDENCE_RECORDS,
        "test_evidence": {
            "run_id": run_id,
            "exact_tests_passed": counts[0],
            "contract_probability_exact_tests_passed": counts[1],
            "full_tests_passed": counts[2],
            "run_log": _external_file(run_log),
            "junit_evidence": junit_records,
        },
        "fixture_evidence": {
            "manifest": fixture_record,
            "mathematical_statement_verified": True,
            "risk_certificate_issued": False,
            "formal_scientific_certificate_authorized": False,
            "prospective_claim_authorized": False,
            "new_library_claim_authorized": False,
            "serialized_bearer_authorization": False,
            "external_source_anchor_required": True,
        },
        "source_index": source_index,
        "source_index_sha256": source_index_digest,
        "claim_boundary": {
            "probability_scope": "SYNTHETIC_KNOWN_CHANNEL",
            "claim_domain": "EXACT_SYNTHETIC_KNOWN_CHANNEL_ONLY",
            "risk_certificate_issued": False,
            "formal_scientific_certificate_authorized": False,
            "prospective_claim_authorized": False,
            "new_library_claim_authorized": False,
            "observed_dataset_qa_completed": False,
            "scientific_conclusion_authorized": False,
        },
        "github": {
            "repository": "Cunyu-Liu/d2t-rna",
            "visibility": "PUBLIC",
            "branch": "main",
            "push_required_after_commit": True,
        },
        "post_commit_closure_required": True,
    }

    draft_path = run_dir / "task4_acceptance_manifest.draft.json"
    payload = canonical_json_bytes(manifest) + b"\n"
    with draft_path.open("xb") as stream:
        stream.write(payload)
    verify_manifest(
        project_root,
        draft_path,
        artifact_root=artifact_root,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("xb") as stream:
        stream.write(payload)
    print(f"TASK4_ACCEPTANCE_MANIFEST_SHA256={hashlib.sha256(payload).hexdigest()}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("manifests/task4_acceptance.json"),
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
