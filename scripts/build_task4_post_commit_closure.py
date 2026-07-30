#!/usr/bin/env python3
"""Build Task 4 closure from a self-captured final acceptance run."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import os
from pathlib import Path
import re
import subprocess
from zoneinfo import ZoneInfo

from scripts.verify_task4_acceptance_manifest import (
    ARTIFACT_ROOT,
    COMMIT_TITLE,
    CONTRACT_SHA256,
    _path_within,
    _verify_source_index_log_markers,
    canonical_json_bytes,
    runtime_dependency_snapshot_sha256,
    verify_manifest,
)


REPOSITORY = "Cunyu-Liu/d2t-rna"
ORIGIN_URL = "git@github.com:Cunyu-Liu/d2t-rna.git"
PUBLIC_HTTPS_URL = "https://github.com/Cunyu-Liu/d2t-rna.git"
GIT_BINARY = "/usr/bin/git"
BASH_BINARY = "/bin/bash"
TASK3_ACCEPTANCE_COMMIT = (
    "5f3a0301fb0051fcee173a08c98677bc1ea20ec5"
)
FINAL_RUN_ID = re.compile(
    r"^task4-final-(?P<stamp>[0-9]{8}T[0-9]{6})\+0800$"
)
PYTEST_SUMMARY = re.compile(
    r"^(\d+) passed(?:, \d+ warnings?)? in [0-9.]+s"
    r"(?: \([0-9:]+\))?$"
)
FINAL_RUNNER_HEADER = (
    "TASK4_FINAL_RUNNER_SCHEMA=d2t_rna.task4_final_runner.v1"
)
SECRET_AUDIT_PASS = "TASK4_SECRET_AUDIT_PASS"
LARGE_FILE_AUDIT_PASS = "TASK4_LARGE_FILE_AUDIT_PASS"
TASK4_CHANGED_PATHS = frozenset(
    {
        "README.md",
        "docs/audit/task-4-exact-engine.md",
        "manifests/task4_acceptance.json",
        "scripts/build_task4_acceptance_fixture.py",
        "scripts/build_task4_acceptance_manifest.py",
        "scripts/build_task4_post_commit_closure.py",
        "scripts/run_task4_acceptance.sh",
        "scripts/run_task4_candidate.sh",
        "scripts/task4_isolated_python.py",
        "scripts/verify_task4_acceptance_manifest.py",
        "src/d2t_rna/exact/__init__.py",
        "src/d2t_rna/exact/confidence.py",
        "src/d2t_rna/exact/coverage.py",
        "src/d2t_rna/exact/enumerate.py",
        "src/d2t_rna/exact/support.py",
        "tests/contracts/test_canonical.py",
        "tests/exact/__init__.py",
        "tests/exact/conftest.py",
        "tests/exact/naive_oracle.py",
        "tests/exact/test_acceptance_verifier.py",
        "tests/exact/test_confidence.py",
        "tests/exact/test_coverage.py",
        "tests/exact/test_enumerate.py",
        "tests/exact/test_support.py",
        "tests/exact/test_task4_historical_gate.py",
        "tests/exact/test_task4_isolated_python.py",
        "tests/exact/test_task4_manifest_builder.py",
        "tests/exact/test_task4_post_commit_closure.py",
    }
)


def _git_environment() -> dict[str, str]:
    """Return the complete, caller-independent Git environment."""

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


def _run_git_bytes(
    project_root: Path,
    *argv: str,
) -> bytes:
    completed = subprocess.run(
        (GIT_BINARY, *argv),
        cwd=project_root,
        env=_git_environment(),
        check=True,
        capture_output=True,
    )
    return completed.stdout


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_run_id(run_id: str) -> None:
    if type(run_id) is not str:
        raise ValueError("Task 4 final run ID is not canonical")
    match = FINAL_RUN_ID.fullmatch(run_id)
    if match is None:
        raise ValueError("Task 4 final run ID is not canonical")
    try:
        datetime.strptime(match.group("stamp"), "%Y%m%dT%H%M%S")
    except ValueError as exc:
        raise ValueError("Task 4 final run ID is not canonical") from exc


def _unique_line_position(lines: list[str], marker: str) -> int:
    positions = [
        index for index, line in enumerate(lines) if line == marker
    ]
    if len(positions) != 1:
        raise ValueError(
            "Task 4 final log requires exactly one "
            f"{marker!r}"
        )
    return positions[0]


def _summary_between(
    lines: list[str],
    begin: str,
    end: str,
) -> int:
    begin_index = _unique_line_position(lines, begin)
    end_index = _unique_line_position(lines, end)
    if begin_index >= end_index:
        raise ValueError(f"Task 4 final log stage is reversed: {begin}")
    matches = tuple(
        match
        for line in lines[begin_index + 1 : end_index]
        if (match := PYTEST_SUMMARY.fullmatch(line))
    )
    if len(matches) != 1:
        raise ValueError(
            "Task 4 final log stage must contain exactly one "
            f"pytest passed summary: {begin}"
        )
    return int(matches[0].group(1))


def _verify_final_log(
    path: Path,
    *,
    run_id: str,
    runtime: dict[str, object],
    dependency_snapshot_sha256: str,
    source_index_sha256: str,
    expected_counts: tuple[int, int, int],
    artifact_root: Path = ARTIFACT_ROOT,
) -> tuple[int, int, int]:
    """Verify the complete ordered transcript of the final runner."""

    _validate_run_id(run_id)
    checked_log = _path_within(
        path,
        artifact_root,
        label="Task 4 final acceptance log",
    )
    expected_run_dir = artifact_root / "runs" / run_id
    expected_log = expected_run_dir / "run.log"
    if (
        checked_log != expected_log.resolve()
        or expected_run_dir.is_symlink()
        or not expected_run_dir.is_dir()
    ):
        raise ValueError(
            "Task 4 final acceptance log is not bound to its run ID"
        )
    expected_pycache = expected_run_dir / "pycache"
    if expected_pycache.is_symlink() or not expected_pycache.is_dir():
        raise ValueError(
            "Task 4 final Python isolation directory is unavailable"
        )

    implementation = runtime.get("implementation")
    python_version = runtime.get("python_version")
    if (
        type(implementation) is not str
        or type(python_version) is not str
        or implementation != "CPython"
        or re.fullmatch(r"3\.11\.[0-9]+", python_version) is None
    ):
        raise ValueError(
            "Task 4 manifest runtime is not registered CPython 3.11"
        )
    if (
        type(dependency_snapshot_sha256) is not str
        or re.fullmatch(
            r"[0-9a-f]{64}",
            dependency_snapshot_sha256,
        )
        is None
    ):
        raise ValueError(
            "Task 4 dependency snapshot SHA-256 is not canonical"
        )
    if (
        type(expected_counts) is not tuple
        or len(expected_counts) != 3
        or any(type(count) is not int for count in expected_counts)
        or expected_counts[0] < 53
        or expected_counts[0] > expected_counts[1]
        or expected_counts[1] > expected_counts[2]
    ):
        raise ValueError(
            "Task 4 candidate counts do not satisfy the acceptance gate"
        )

    lines = checked_log.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != FINAL_RUNNER_HEADER:
        raise ValueError(
            "Task 4 final log has no registered runner header"
        )
    if any(
        "FAILED" in line
        or line.startswith("FAIL:")
        or line.startswith("TASK4_MANIFEST_REJECTED")
        for line in lines
    ):
        raise ValueError("Task 4 final log contains a failure marker")

    pre_source_marker, post_source_marker = (
        _verify_source_index_log_markers(
            lines,
            source_index_sha256=source_index_sha256,
        )
    )
    runtime_marker = (
        f"TASK4_RUNTIME={implementation} {python_version}"
    )
    isolation_marker = (
        f"TASK4_PYTHON_ISOLATION_PASS={expected_pycache}"
    )
    dependency_marker = (
        "TASK4_DEPENDENCY_SNAPSHOT_SHA256="
        f"{dependency_snapshot_sha256}"
    )
    required_markers = (
        FINAL_RUNNER_HEADER,
        f"TASK4_FINAL_RUN_ID={run_id}",
        runtime_marker,
        f"TASK4_CONTRACT_SHA256={CONTRACT_SHA256}",
        dependency_marker,
        isolation_marker,
        pre_source_marker,
        "TASK4_EXACT_TESTS_BEGIN",
        "TASK4_EXACT_TESTS_END",
        "TASK4_COMBINED_TESTS_BEGIN",
        "TASK4_COMBINED_TESTS_END",
        "TASK4_FULL_TESTS_BEGIN",
        "TASK4_FULL_TESTS_END",
        post_source_marker,
        "TASK4_COMPILE_PASS",
        "TASK4_GIT_DIFF_CHECK_PASS",
        "TASK4_EXISTING_MANIFEST_JSON_PASS",
        "TASK4_MANIFEST_VERIFIED",
        "TASK4_LIVE_MANIFEST_REPLAY_PASS",
        SECRET_AUDIT_PASS,
        LARGE_FILE_AUDIT_PASS,
        "TASK4_ACCEPTANCE_PASS",
    )
    positions = tuple(
        _unique_line_position(lines, marker)
        for marker in required_markers
    )
    if positions != tuple(sorted(positions)):
        raise ValueError("Task 4 final run stages are out of order")
    if positions[:7] != tuple(range(7)):
        raise ValueError(
            "Task 4 final runner preamble is not contiguous"
        )
    if lines[-1] != "TASK4_ACCEPTANCE_PASS":
        raise ValueError(
            "Task 4 final acceptance marker is not terminal"
        )

    summaries = (
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
    all_summaries = tuple(
        match
        for line in lines
        if (match := PYTEST_SUMMARY.fullmatch(line))
    )
    if len(all_summaries) != 3:
        raise ValueError(
            "Task 4 final log must contain exactly three pytest "
            "passed summaries"
        )
    if (
        summaries[0] < 53
        or summaries[0] > summaries[1]
        or summaries[1] > summaries[2]
    ):
        raise ValueError(
            "Task 4 final counts do not satisfy the acceptance gate"
        )
    if summaries != expected_counts:
        raise ValueError(
            "Task 4 final counts differ from candidate manifest counts"
        )
    return summaries


def _run_final_acceptance(
    *,
    project_root: Path,
    run_id: str,
    artifact_root: Path = ARTIFACT_ROOT,
) -> Path:
    """Exclusively create and synchronously capture one final run."""

    _validate_run_id(run_id)
    runner = project_root / "scripts" / "run_task4_acceptance.sh"
    if (
        runner.is_symlink()
        or not runner.is_file()
        or not os.access(runner, os.X_OK)
    ):
        raise ValueError(
            "Task 4 final acceptance runner is unavailable"
        )

    if artifact_root.is_symlink():
        raise ValueError("Task 4 artifact root must not be a symlink")
    artifact_root.mkdir(parents=True, exist_ok=True)
    if not artifact_root.is_dir():
        raise ValueError("Task 4 artifact root is not a directory")
    runs_root = artifact_root / "runs"
    if runs_root.is_symlink():
        raise ValueError("Task 4 runs root must not be a symlink")
    runs_root.mkdir(exist_ok=True)
    if not runs_root.is_dir():
        raise ValueError("Task 4 runs root is not a directory")

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
        "TASK4_FINAL_RUN_ID": run_id,
    }

    with run_log.open("xb") as stream:
        try:
            completed = subprocess.run(
                [BASH_BINARY, str(runner)],
                cwd=project_root,
                env=environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
            )
        except OSError as exc:
            stream.write(
                (
                    "TASK4_CLOSURE_LAUNCH_FAILED="
                    f"{type(exc).__name__}: {exc}\n"
                ).encode("utf-8", errors="replace")
            )
            raise RuntimeError(
                "Task 4 final runner could not be launched; "
                f"evidence preserved at {run_log}"
            ) from exc
        finally:
            stream.flush()
            os.fsync(stream.fileno())
    if completed.returncode != 0:
        raise RuntimeError(
            "Task 4 final runner failed with exit code "
            f"{completed.returncode}; evidence preserved at {run_log}"
        )
    return run_log


def _local_commit_state(project_root: Path) -> dict[str, str]:
    return {
        "head": _run_git(project_root, "rev-parse", "HEAD"),
        "title": _run_git(
            project_root,
            "log",
            "-1",
            "--pretty=%s",
        ),
        "branch": _run_git(
            project_root,
            "branch",
            "--show-current",
        ),
        "status": _run_git(
            project_root,
            "status",
            "--porcelain",
        ),
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
    ):
        raise ValueError(
            "Task 4 final run requires the clean registered main commit"
        )
    return state


def _verify_task4_commit_delta(
    project_root: Path,
    *,
    expected_head: str,
) -> dict[str, object]:
    """Bind Task 4 to one exact child commit and changed-path set."""

    if re.fullmatch(r"[0-9a-f]{40}", expected_head) is None:
        raise ValueError("Task 4 expected Git commit is not canonical")
    parent_record = _run_git(
        project_root,
        "rev-list",
        "--parents",
        "-n",
        "1",
        expected_head,
    )
    fields = parent_record.split()
    if fields != [expected_head, TASK3_ACCEPTANCE_COMMIT]:
        raise ValueError(
            "Task 4 commit must have the accepted Task 3 commit as its "
            "single parent"
        )

    raw_paths = _run_git_bytes(
        project_root,
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        "--no-renames",
        "-z",
        TASK3_ACCEPTANCE_COMMIT,
        expected_head,
    )
    if not raw_paths or not raw_paths.endswith(b"\0"):
        raise ValueError(
            "Task 4 commit changed-path output is not terminal NUL data"
        )
    raw_records = raw_paths[:-1].split(b"\0")
    if any(not record for record in raw_records):
        raise ValueError(
            "Task 4 commit changed-path output contains an empty record"
        )
    try:
        changed_paths = tuple(
            record.decode("utf-8", errors="strict")
            for record in raw_records
        )
    except UnicodeDecodeError as exc:
        raise ValueError(
            "Task 4 commit changed-path output is not UTF-8"
        ) from exc
    if len(changed_paths) != len(set(changed_paths)):
        raise ValueError(
            "Task 4 commit changed-path output contains duplicates"
        )
    observed = frozenset(changed_paths)
    if observed != TASK4_CHANGED_PATHS:
        missing = sorted(TASK4_CHANGED_PATHS - observed)
        extra = sorted(observed - TASK4_CHANGED_PATHS)
        raise ValueError(
            "Task 4 commit changed path set differs from the frozen "
            f"allowlist: missing={missing}, extra={extra}"
        )
    ordered_paths = sorted(observed)
    return {
        "parent": TASK3_ACCEPTANCE_COMMIT,
        "changed_paths": ordered_paths,
        "changed_paths_sha256": hashlib.sha256(
            canonical_json_bytes(ordered_paths)
        ).hexdigest(),
    }


def _parse_public_refs(
    output: str,
    *,
    expected_head: str,
) -> dict[str, object]:
    """Verify anonymous HTTPS HEAD and main output from ``ls-remote``."""

    if re.fullmatch(r"[0-9a-f]{40}", expected_head) is None:
        raise ValueError("Task 4 expected Git commit is not canonical")
    records: list[tuple[str, str]] = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(
                "Task 4 anonymous GitHub response is malformed"
            )
        records.append((parts[0], parts[1]))
    expected_records = [
        ("ref: refs/heads/main", "HEAD"),
        (expected_head, "HEAD"),
        (expected_head, "refs/heads/main"),
    ]
    if records != expected_records:
        raise ValueError(
            "Task 4 anonymous GitHub HEAD/default-main evidence changed"
        )
    return {
        "defaultBranchRef": {"name": "main"},
        "nameWithOwner": REPOSITORY,
        "visibility": "PUBLIC",
    }


def _verify_publication(
    project_root: Path,
    *,
    expected_head: str,
) -> tuple[dict[str, str], dict[str, object]]:
    state = _verify_local_preflight(project_root)
    if state["head"] != expected_head:
        raise ValueError("Task 4 HEAD changed during final acceptance")
    remote_output = _run_git(
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
    github = _parse_public_refs(
        remote_output,
        expected_head=expected_head,
    )
    return state, github


def _resolve_output_path(
    output_path: Path,
    *,
    run_id: str,
    artifact_root: Path = ARTIFACT_ROOT,
) -> Path:
    if not output_path.is_absolute() or output_path.is_symlink():
        raise ValueError(
            "Task 4 closure output must be an absolute non-symlink path"
        )
    resolved = output_path.resolve()
    try:
        resolved.relative_to(artifact_root.resolve())
    except ValueError as exc:
        raise ValueError(
            "Task 4 closure must remain under the artifact root"
        ) from exc
    if resolved == (
        artifact_root / "runs" / run_id / "run.log"
    ).resolve():
        raise ValueError(
            "Task 4 closure output must not replace the final run log"
        )
    if resolved.exists():
        raise FileExistsError(
            f"Task 4 closure output already exists: {resolved}"
        )
    return resolved


def build_closure(
    *,
    project_root: Path,
    run_id: str,
    output_path: Path,
) -> dict[str, object]:
    _validate_run_id(run_id)
    resolved_output = _resolve_output_path(
        output_path,
        run_id=run_id,
    )
    preflight = _verify_local_preflight(project_root)
    commit_delta = _verify_task4_commit_delta(
        project_root,
        expected_head=preflight["head"],
    )
    run_log = _run_final_acceptance(
        project_root=project_root,
        run_id=run_id,
    )
    manifest_path = project_root / "manifests" / "task4_acceptance.json"
    manifest = verify_manifest(project_root, manifest_path)
    dependency_snapshot_sha = runtime_dependency_snapshot_sha256(
        project_root
    )
    if (
        manifest["runtime"].get("dependency_snapshot_sha256")
        != dependency_snapshot_sha
    ):
        raise ValueError(
            "Task 4 manifest dependency snapshot changed before closure"
        )
    candidate_counts = (
        manifest["test_evidence"]["exact_tests_passed"],
        manifest["test_evidence"][
            "contract_probability_exact_tests_passed"
        ],
        manifest["test_evidence"]["full_tests_passed"],
    )
    test_counts = _verify_final_log(
        run_log,
        run_id=run_id,
        runtime=manifest["runtime"],
        dependency_snapshot_sha256=dependency_snapshot_sha,
        source_index_sha256=manifest["source_index_sha256"],
        expected_counts=candidate_counts,
    )
    state, _github = _verify_publication(
        project_root,
        expected_head=preflight["head"],
    )

    fixture_record = manifest["fixture_evidence"]["manifest"]
    closure = {
        "schema": "d2t_rna.task4_post_commit_closure.v3",
        "task": 4,
        "status": "CLOSED_ACCEPTED_PUSHED_PUBLIC",
        "verified_at": datetime.now(
            ZoneInfo("Asia/Shanghai")
        ).isoformat(timespec="seconds"),
        "contract_sha256": CONTRACT_SHA256,
        "commit": {
            "sha": state["head"],
            "title": state["title"],
            "branch": state["branch"],
            "origin_main": state["head"],
            "parent": commit_delta["parent"],
            "changed_paths": commit_delta["changed_paths"],
            "changed_paths_sha256": commit_delta[
                "changed_paths_sha256"
            ],
        },
        "github": {
            "repository": REPOSITORY,
            "visibility": "PUBLIC",
            "default_branch": "main",
            "origin_url": state["origin_url"],
        },
        "acceptance_manifest": {
            "path": str(manifest_path),
            "sha256": _sha256(manifest_path),
            "source_index_sha256": manifest["source_index_sha256"],
        },
        "fixture_manifest": fixture_record,
        "candidate_run_id": manifest["test_evidence"]["run_id"],
        "final_acceptance": {
            "run_id": run_id,
            "runner": str(
                project_root / "scripts" / "run_task4_acceptance.sh"
            ),
            "test_counts": {
                "exact": test_counts[0],
                "combined": test_counts[1],
                "full": test_counts[2],
            },
            "dependency_snapshot_sha256": dependency_snapshot_sha,
            "run_log": {
                "path": str(run_log),
                "sha256": _sha256(run_log),
            },
        },
        "claim_boundary": manifest["claim_boundary"],
    }
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(closure) + b"\n"
    with resolved_output.open("xb") as stream:
        stream.write(payload)
    print(f"TASK4_CLOSURE_SHA256={hashlib.sha256(payload).hexdigest()}")
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
