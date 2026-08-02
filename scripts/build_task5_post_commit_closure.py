#!/usr/bin/env python3
"""Build Task 5 closure only after clean public GitHub publication."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import os
from pathlib import Path
import re
import subprocess
from zoneinfo import ZoneInfo

from d2t_rna.contracts.base import canonical_json_bytes, canonical_sha256
from scripts.verify_task5_acceptance_manifest import (
    ARTIFACT_ROOT,
    COMMIT_TITLE,
    CONTRACT_SHA256,
    EXPECTED_FIXTURE_ARTIFACTS,
    ORIGIN_URL,
    PUBLIC_HTTPS_URL,
    REPOSITORY,
    TASK4_ACCEPTANCE_COMMIT,
    _canonical_json_equal,
    _load_canonical_json,
    _path_within,
    _sha256,
    _summary_between,
    _validate_final_run_id,
    _verify_external_file,
    _verify_junit,
    _verify_test_log,
    build_runtime_dependency_snapshot,
    build_source_snapshot,
    derive_task4_nested_parent_binding,
    task5_delta_snapshot,
    verify_fixture,
    verify_manifest,
)


BASH_BINARY = "/bin/bash"
GIT_BINARY = "/usr/bin/git"


def _git_environment() -> dict[str, str]:
    return {
        "HOME": "/nonexistent",
        "USER": "cunyuliu",
        "LOGNAME": "cunyuliu",
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
    }


def _run_git(
    project_root: Path,
    *argv: str,
    cwd: Path | None = None,
) -> str:
    completed = subprocess.run(
        (GIT_BINARY, *argv),
        cwd=project_root if cwd is None else cwd,
        env=_git_environment(),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _local_commit_state(project_root: Path) -> dict[str, str]:
    return {
        "head": _run_git(project_root, "rev-parse", "HEAD"),
        "title": _run_git(project_root, "log", "-1", "--pretty=%s"),
        "branch": _run_git(project_root, "branch", "--show-current"),
        "status": _run_git(project_root, "status", "--porcelain"),
        "origin_url": _run_git(
            project_root,
            "remote",
            "get-url",
            "origin",
        ),
    }


def _verify_local_preflight(project_root: Path) -> dict[str, str]:
    state = _local_commit_state(project_root)
    if (
        state["title"] != COMMIT_TITLE
        or state["branch"] != "main"
        or state["status"]
        or state["origin_url"] != ORIGIN_URL
        or re.fullmatch(r"[0-9a-f]{40}", state["head"]) is None
    ):
        raise ValueError(
            "Task 5 final closure requires the clean registered main commit"
        )
    parent = _run_git(
        project_root,
        "rev-list",
        "--parents",
        "-n",
        "1",
        state["head"],
    )
    if parent.split() != [state["head"], TASK4_ACCEPTANCE_COMMIT]:
        raise ValueError(
            "Task 5 final commit is not the single child of accepted Task 4"
        )
    return state


def _parse_public_refs(
    output: str,
    *,
    expected_head: str,
) -> dict[str, object]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_head) is None:
        raise ValueError("Task 5 expected public commit is not canonical")
    records: list[tuple[str, str]] = []
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or not fields[0] or not fields[1]:
            raise ValueError("Task 5 anonymous GitHub response is malformed")
        records.append((fields[0], fields[1]))
    expected = [
        ("ref: refs/heads/main", "HEAD"),
        (expected_head, "HEAD"),
        (expected_head, "refs/heads/main"),
    ]
    if records != expected:
        raise ValueError(
            "Task 5 anonymous GitHub HEAD/default-main evidence changed"
        )
    return {
        "default_branch": "main",
        "origin_main": expected_head,
        "repository": REPOSITORY,
        "visibility": "PUBLIC",
    }


def _verify_publication(
    project_root: Path,
    *,
    expected_head: str,
) -> dict[str, object]:
    state = _verify_local_preflight(project_root)
    if state["head"] != expected_head:
        raise ValueError("Task 5 HEAD changed during final acceptance")
    output = _run_git(
        project_root,
        "-c",
        "credential.helper=",
        "-c",
        "core.askPass=/bin/false",
        "-c",
        "credential.interactive=never",
        "-c",
        "protocol.allow=never",
        "-c",
        "protocol.https.allow=always",
        "ls-remote",
        "--symref",
        PUBLIC_HTTPS_URL,
        "HEAD",
        "refs/heads/main",
        cwd=Path("/"),
    )
    return _parse_public_refs(output, expected_head=expected_head)


def _resolve_output_path(
    output_path: Path,
    *,
    run_id: str,
    artifact_root: Path = ARTIFACT_ROOT,
) -> Path:
    _validate_final_run_id(run_id)
    if not output_path.is_absolute() or output_path.is_symlink():
        raise ValueError(
            "Task 5 closure output must be an absolute non-symlink path"
        )
    expected = artifact_root / "runs" / run_id / "closure.json"
    for component in (output_path, *output_path.parents):
        if component.is_symlink():
            raise ValueError("Task 5 closure path has a symlink component")
    resolved_root = artifact_root.resolve()
    resolved = output_path.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(
            "Task 5 closure output escaped the artifact root"
        ) from exc
    if output_path != expected:
        raise ValueError(
            "Task 5 closure output must be the registered run closure path"
        )
    if resolved == (
        artifact_root / "runs" / run_id / "run.log"
    ).resolve():
        raise ValueError("Task 5 closure must not replace the final run log")
    if output_path.exists():
        raise FileExistsError(
            f"Task 5 closure output already exists: {output_path}"
        )
    return resolved


def _run_final_acceptance(
    *,
    project_root: Path,
    run_id: str,
    artifact_root: Path = ARTIFACT_ROOT,
) -> Path:
    _validate_final_run_id(run_id)
    runner = project_root / "scripts" / "run_task5_acceptance.sh"
    if (
        runner.is_symlink()
        or not runner.is_file()
        or not os.access(runner, os.X_OK)
    ):
        raise ValueError("Task 5 final runner is unavailable")
    runs_root = artifact_root / "runs"
    if runs_root.is_symlink():
        raise ValueError("Task 5 runs root is a symlink")
    runs_root.mkdir(parents=True, exist_ok=True)
    run_dir = runs_root / run_id
    run_dir.mkdir(mode=0o750, exist_ok=False)
    run_log = run_dir / "run.log"
    environment = {
        "HOME": "/home/cunyuliu",
        "USER": "cunyuliu",
        "LOGNAME": "cunyuliu",
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TASK5_FINAL_RUN_ID": run_id,
    }
    with run_log.open("xb") as stream:
        try:
            completed = subprocess.run(
                (BASH_BINARY, str(runner)),
                cwd=project_root,
                env=environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
            )
        except OSError as exc:
            stream.write(
                (
                    "TASK5_CLOSURE_LAUNCH_FAILED="
                    f"{type(exc).__name__}: {exc}\n"
                ).encode("utf-8", errors="replace")
            )
            raise RuntimeError(
                "Task 5 final runner could not launch; evidence preserved at "
                f"{run_log}"
            ) from exc
        finally:
            stream.flush()
            os.fsync(stream.fileno())
    if completed.returncode != 0:
        raise RuntimeError(
            "Task 5 final runner failed with exit code "
            f"{completed.returncode}; evidence preserved at {run_log}"
        )
    return run_log


def _counts_from_log(path: Path) -> tuple[int, int, int]:
    lines = path.read_text(encoding="utf-8").splitlines()
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


def _fixture_scientific_payload(
    fixture: object,
) -> dict[str, object]:
    """Drop run-specific paths while retaining every scientific commitment."""

    if type(fixture) is not dict:
        raise ValueError("Task 5 fixture payload is not an object")
    artifacts = fixture.get("artifacts")
    if (
        type(artifacts) is not dict
        or set(artifacts) != EXPECTED_FIXTURE_ARTIFACTS
    ):
        raise ValueError("Task 5 fixture artifact registry changed")
    artifact_sha256: dict[str, str] = {}
    for name in sorted(EXPECTED_FIXTURE_ARTIFACTS):
        record = artifacts[name]
        if (
            type(record) is not dict
            or set(record) != {"path", "sha256"}
            or type(record["sha256"]) is not str
            or re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is None
        ):
            raise ValueError(
                f"Task 5 fixture artifact record is malformed: {name}"
            )
        artifact_sha256[name] = record["sha256"]
    return {
        "schema": fixture.get("schema"),
        "fixture_id": fixture.get("fixture_id"),
        "contract_sha256": fixture.get("contract_sha256"),
        "artifact_sha256": artifact_sha256,
        "replay": fixture.get("replay"),
        "claim_boundary": fixture.get("claim_boundary"),
    }


def _verify_candidate_final_fixture_payload(
    candidate_fixture: object,
    final_fixture: object,
) -> str:
    """Require identical canonical science despite different run directories."""

    candidate = _fixture_scientific_payload(candidate_fixture)
    final = _fixture_scientific_payload(final_fixture)
    if canonical_json_bytes(candidate) != canonical_json_bytes(final):
        raise ValueError(
            "Task 5 final fixture scientific payload differs from candidate"
        )
    return canonical_sha256(candidate)


def build_closure(
    *,
    project_root: Path,
    run_id: str,
    output_path: Path,
    artifact_root: Path = ARTIFACT_ROOT,
) -> dict[str, object]:
    _validate_final_run_id(run_id)
    resolved_output = _resolve_output_path(
        output_path,
        run_id=run_id,
        artifact_root=artifact_root,
    )
    preflight = _verify_local_preflight(project_root)
    manifest_path = project_root / "manifests" / "task5_acceptance.json"
    manifest = verify_manifest(
        project_root,
        manifest_path,
        artifact_root=artifact_root,
        require_post_commit=True,
    )
    delta = task5_delta_snapshot(
        project_root,
        require_post_commit=True,
    )
    run_log = _run_final_acceptance(
        project_root=project_root,
        run_id=run_id,
        artifact_root=artifact_root,
    )
    run_dir = artifact_root / "runs" / run_id
    runtime_snapshot_path = _path_within(
        run_dir / "snapshots" / "runtime_dependency_snapshot.json",
        artifact_root,
        label="Task 5 final dependency snapshot",
    )
    source_snapshot_path = _path_within(
        run_dir / "snapshots" / "source_index.json",
        artifact_root,
        label="Task 5 final source snapshot",
    )
    post_source_snapshot_path = _path_within(
        run_dir / "snapshots" / "source_index_post_test.json",
        artifact_root,
        label="Task 5 final post-test source snapshot",
    )
    task4_parent_binding_path = _path_within(
        run_dir / "snapshots" / "task4_nested_parent_binding.json",
        artifact_root,
        label="Task 5 final nested Task 4 parent binding",
    )
    runtime_snapshot = _load_canonical_json(
        runtime_snapshot_path,
        label="Task 5 final dependency snapshot",
    )
    source_snapshot = _load_canonical_json(
        source_snapshot_path,
        label="Task 5 final source snapshot",
    )
    post_source_snapshot = _load_canonical_json(
        post_source_snapshot_path,
        label="Task 5 final post-test source snapshot",
    )
    task4_parent_binding_artifact = _load_canonical_json(
        task4_parent_binding_path,
        label="Task 5 final nested Task 4 parent binding",
    )
    live_runtime = build_runtime_dependency_snapshot(project_root)
    live_source = build_source_snapshot(project_root)
    if (
        not _canonical_json_equal(runtime_snapshot, live_runtime)
        or not _canonical_json_equal(source_snapshot, live_source)
        or not _canonical_json_equal(
            post_source_snapshot, source_snapshot
        )
    ):
        raise ValueError("Task 5 final snapshots differ from live closure")
    if (
        canonical_sha256(runtime_snapshot)
        != manifest["runtime"]["dependency_snapshot_sha256"]
        or source_snapshot["source_index_sha256"]
        != manifest["source_snapshot"]["source_index_sha256"]
    ):
        raise ValueError("Task 5 final snapshots differ from candidate")
    task4_parent_binding = derive_task4_nested_parent_binding(
        project_root,
        runtime_snapshot=runtime_snapshot,
        source_snapshot=source_snapshot,
    )
    if (
        task4_parent_binding_artifact != task4_parent_binding
        or task4_parent_binding["dependency_snapshot_sha256"]
        != manifest["runtime"][
            "task4_parent_dependency_snapshot_sha256"
        ]
        or task4_parent_binding["source_index_sha256"]
        != manifest["source_snapshot"][
            "task4_parent_source_index_sha256"
        ]
    ):
        raise ValueError(
            "Task 5 final nested Task 4 parent binding differs from candidate"
        )
    fixture_path = run_dir / "fixture" / "fixture_manifest.json"
    final_fixture = verify_fixture(
        project_root,
        fixture_path,
        artifact_root=artifact_root,
    )
    fixture_sha = _sha256(fixture_path)
    candidate_fixture_path = _verify_external_file(
        manifest["fixture_evidence"]["manifest"],
        root=artifact_root,
        label="Task 5 candidate fixture manifest",
    )
    candidate_fixture = _load_canonical_json(
        candidate_fixture_path,
        label="Task 5 candidate fixture manifest",
    )
    fixture_scientific_payload_sha256 = (
        _verify_candidate_final_fixture_payload(
            candidate_fixture,
            final_fixture,
        )
    )
    counts = _counts_from_log(run_log)
    candidate_counts = (
        manifest["test_evidence"]["evaluation_tests_passed"],
        manifest["test_evidence"]["combined_tests_passed"],
        manifest["test_evidence"]["full_tests_passed"],
    )
    if counts != candidate_counts:
        raise ValueError("Task 5 final test counts differ from candidate")
    _verify_test_log(
        run_log,
        run_id=run_id,
        runtime=manifest["runtime"],
        dependency_snapshot_sha256=canonical_sha256(runtime_snapshot),
        source_index_sha256=source_snapshot["source_index_sha256"],
        task4_parent_dependency_snapshot_sha256=(
            task4_parent_binding["dependency_snapshot_sha256"]
        ),
        task4_parent_source_index_sha256=(
            task4_parent_binding["source_index_sha256"]
        ),
        fixture_manifest_sha256=fixture_sha,
        expected_counts=counts,
        artifact_root=artifact_root,
        final=True,
    )
    for name, count in zip(
        ("evaluation", "combined", "full"),
        counts,
        strict=True,
    ):
        _verify_junit(
            run_dir / "junit" / f"{name}.xml",
            expected_count=count,
            label=f"Task 5 final {name} JUnit",
        )
    publication = _verify_publication(
        project_root,
        expected_head=preflight["head"],
    )
    closure = {
        "schema": "d2t_rna.task5_post_commit_closure.v1",
        "task": 5,
        "status": "CLOSED_ACCEPTED_PUSHED_PUBLIC",
        "verified_at": datetime.now(
            ZoneInfo("Asia/Shanghai")
        ).isoformat(timespec="seconds"),
        "contract_sha256": CONTRACT_SHA256,
        "commit": {
            "sha": preflight["head"],
            "title": preflight["title"],
            "branch": preflight["branch"],
            "parent": TASK4_ACCEPTANCE_COMMIT,
            "changed_paths": list(delta["changed_paths"]),
            "changed_paths_sha256": delta["changed_paths_sha256"],
        },
        "github": {
            **publication,
            "origin_url": preflight["origin_url"],
        },
        "acceptance_manifest": {
            "path": str(manifest_path),
            "sha256": _sha256(manifest_path),
            "source_index_sha256": manifest[
                "source_snapshot"
            ]["source_index_sha256"],
        },
        "candidate_run_id": manifest["test_evidence"]["run_id"],
        "final_acceptance": {
            "run_id": run_id,
            "runner": str(
                project_root / "scripts" / "run_task5_acceptance.sh"
            ),
            "test_counts": {
                "evaluation": counts[0],
                "combined": counts[1],
                "full": counts[2],
            },
            "runtime_dependency_snapshot_sha256": canonical_sha256(
                runtime_snapshot
            ),
            "source_index_sha256": source_snapshot[
                "source_index_sha256"
            ],
            "task4_parent_binding": {
                **task4_parent_binding,
                "artifact_sha256": _sha256(task4_parent_binding_path),
            },
            "pre_post_source_snapshots_identical": True,
            "fixture_manifest": {
                "path": str(fixture_path),
                "sha256": fixture_sha,
                "candidate_sha256": manifest[
                    "fixture_evidence"
                ]["manifest"]["sha256"],
                "scientific_payload_sha256": (
                    fixture_scientific_payload_sha256
                ),
            },
            "run_log": {
                "path": str(run_log),
                "sha256": _sha256(run_log),
            },
        },
        "claim_boundary": manifest["claim_boundary"],
    }
    payload = canonical_json_bytes(closure) + b"\n"
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    with resolved_output.open("xb") as stream:
        stream.write(payload)
    print(f"TASK5_CLOSURE_SHA256={hashlib.sha256(payload).hexdigest()}")
    return closure


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    build_closure(
        project_root=project_root,
        run_id=args.run_id,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
