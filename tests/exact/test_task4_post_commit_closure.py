from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import build_task4_post_commit_closure as closure_module
from scripts.build_task4_post_commit_closure import (
    LARGE_FILE_AUDIT_PASS,
    SECRET_AUDIT_PASS,
    TASK4_CHANGED_PATHS,
    _git_environment,
    _parse_public_refs,
    _run_final_acceptance,
    _run_git,
    _validate_run_id,
    _verify_final_log,
    _verify_task4_commit_delta,
)
from scripts.verify_task4_acceptance_manifest import (
    CONTRACT_SHA256,
    TASK3_ACCEPTANCE_COMMIT,
)


RUN_ID = "task4-final-20260730T010203+0800"
RUNTIME = {
    "implementation": "CPython",
    "python_version": "3.11.15",
}
DEPENDENCY_SNAPSHOT_SHA256 = "d" * 64
SOURCE_INDEX_SHA256 = "c" * 64
COUNTS = (53, 153, 273)
HEAD = "a" * 40


def _commit_paths_bytes(paths: set[str] | frozenset[str]) -> bytes:
    return b"".join(
        path.encode("utf-8") + b"\0"
        for path in sorted(paths)
    )


def _valid_log(artifact_root: Path) -> Path:
    run_dir = artifact_root / "runs" / RUN_ID
    (run_dir / "pycache").mkdir(parents=True)
    log = run_dir / "run.log"
    log.write_text(
        "\n".join(
            (
                (
                    "TASK4_FINAL_RUNNER_SCHEMA="
                    "d2t_rna.task4_final_runner.v1"
                ),
                f"TASK4_FINAL_RUN_ID={RUN_ID}",
                "TASK4_RUNTIME=CPython 3.11.15",
                f"TASK4_CONTRACT_SHA256={CONTRACT_SHA256}",
                (
                    "TASK4_DEPENDENCY_SNAPSHOT_SHA256="
                    f"{DEPENDENCY_SNAPSHOT_SHA256}"
                ),
                (
                    "TASK4_PYTHON_ISOLATION_PASS="
                    f"{run_dir}/pycache"
                ),
                (
                    "TASK4_PRE_TEST_SOURCE_INDEX_SHA256="
                    f"{SOURCE_INDEX_SHA256}"
                ),
                "TASK4_EXACT_TESTS_BEGIN",
                f"{COUNTS[0]} passed in 1.00s",
                "TASK4_EXACT_TESTS_END",
                "TASK4_COMBINED_TESTS_BEGIN",
                f"{COUNTS[1]} passed, 1 warning in 2.00s",
                "TASK4_COMBINED_TESTS_END",
                "TASK4_FULL_TESTS_BEGIN",
                f"{COUNTS[2]} passed in 3.00s",
                "TASK4_FULL_TESTS_END",
                (
                    "TASK4_POST_TEST_SOURCE_INDEX_SHA256="
                    f"{SOURCE_INDEX_SHA256}"
                ),
                "TASK4_COMPILE_PASS",
                "TASK4_GIT_DIFF_CHECK_PASS",
                "TASK4_EXISTING_MANIFEST_JSON_PASS",
                "TASK4_MANIFEST_VERIFIED",
                "TASK4_LIVE_MANIFEST_REPLAY_PASS",
                SECRET_AUDIT_PASS,
                LARGE_FILE_AUDIT_PASS,
                "TASK4_ACCEPTANCE_PASS",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    return log


def test_final_log_verifier_accepts_complete_bound_transcript(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    log = _valid_log(artifact_root)
    assert _verify_final_log(
        log,
        run_id=RUN_ID,
        runtime=RUNTIME,
        dependency_snapshot_sha256=DEPENDENCY_SNAPSHOT_SHA256,
        source_index_sha256=SOURCE_INDEX_SHA256,
        expected_counts=COUNTS,
        artifact_root=artifact_root,
    ) == COUNTS


@pytest.mark.parametrize(
    "run_id",
    (
        "task4-final-20260230T010203+0800",
        "task4-final-20260730T250203+0800",
        "task4-final-acceptance-20260730T010203+0800",
        "../task4-final-20260730T010203+0800",
    ),
)
def test_final_run_id_rejects_noncanonical_values(run_id: str) -> None:
    with pytest.raises(ValueError, match="not canonical"):
        _validate_run_id(run_id)


def test_final_log_verifier_rejects_fabricated_three_line_log(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    run_dir = artifact_root / "runs" / RUN_ID
    (run_dir / "pycache").mkdir(parents=True)
    log = run_dir / "run.log"
    log.write_text(
        "41 passed in 1.00s\n"
        "151 passed in 2.00s\n"
        "271 passed in 3.00s\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="runner header"):
        _verify_final_log(
            log,
            run_id=RUN_ID,
            runtime=RUNTIME,
            dependency_snapshot_sha256=DEPENDENCY_SNAPSHOT_SHA256,
            source_index_sha256=SOURCE_INDEX_SHA256,
            expected_counts=COUNTS,
            artifact_root=artifact_root,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (
            lambda text: text.replace(
                "TASK4_EXACT_TESTS_END",
                "TASK4_EXACT_TESTS_BEGIN",
                1,
            ),
            "exactly one",
        ),
        (
            lambda text: text.replace(
                "TASK4_COMBINED_TESTS_BEGIN",
                "TASK4_COMBINED_TESTS_END",
                1,
            ),
            "exactly one",
        ),
        (
            lambda text: text.replace(
                "TASK4_SECRET_AUDIT_PASS\n",
                "TASK4_SECRET_AUDIT_PASS\nTASK4_EXACT_FAILED\n",
            ),
            "failure marker",
        ),
        (
            lambda text: text.replace(
                "TASK4_COMPILE_PASS\n",
                "999 passed in 0.01s\nTASK4_COMPILE_PASS\n",
            ),
            "exactly three",
        ),
        (
            lambda text: text.replace(
                "TASK4_ACCEPTANCE_PASS\n",
                "TASK4_ACCEPTANCE_PASS\ntrailing output\n",
            ),
            "not terminal",
        ),
        (
            lambda text: text.replace(
                f"TASK4_FINAL_RUN_ID={RUN_ID}\n",
                "",
            ),
            "exactly one",
        ),
        (
            lambda text: text.replace(
                (
                    "TASK4_DEPENDENCY_SNAPSHOT_SHA256="
                    f"{DEPENDENCY_SNAPSHOT_SHA256}\n"
                ),
                "",
            ),
            "exactly one",
        ),
        (
            lambda text: text.replace(
                (
                    "TASK4_POST_TEST_SOURCE_INDEX_SHA256="
                    f"{SOURCE_INDEX_SHA256}\n"
                ),
                f"TASK4_POST_TEST_SOURCE_INDEX_SHA256={'e' * 64}\n",
            ),
            "does not match",
        ),
        (
            lambda text: text.replace(
                "TASK4_GIT_DIFF_CHECK_PASS\n",
                "",
            ),
            "exactly one",
        ),
        (
            lambda text: text.replace(
                "TASK4_EXISTING_MANIFEST_JSON_PASS\n",
                "TASK4_EXISTING_MANIFEST_JSON_PASS\n"
                "TASK4_EXISTING_MANIFEST_JSON_PASS\n",
            ),
            "exactly one",
        ),
        (
            lambda text: text.replace(
                f"{SECRET_AUDIT_PASS}\n{LARGE_FILE_AUDIT_PASS}\n",
                f"{LARGE_FILE_AUDIT_PASS}\n{SECRET_AUDIT_PASS}\n",
            ),
            "out of order",
        ),
    ),
)
def test_final_log_verifier_rejects_mutated_transcript(
    tmp_path: Path,
    mutation,
    message: str,
) -> None:
    artifact_root = tmp_path / "artifacts"
    log = _valid_log(artifact_root)
    log.write_text(
        mutation(log.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=message):
        _verify_final_log(
            log,
            run_id=RUN_ID,
            runtime=RUNTIME,
            dependency_snapshot_sha256=DEPENDENCY_SNAPSHOT_SHA256,
            source_index_sha256=SOURCE_INDEX_SHA256,
            expected_counts=COUNTS,
            artifact_root=artifact_root,
        )


def test_final_log_verifier_binds_run_id_and_log_path(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    log = _valid_log(artifact_root)
    with pytest.raises(ValueError, match="bound to its run ID"):
        _verify_final_log(
            log,
            run_id="task4-final-20260730T010204+0800",
            runtime=RUNTIME,
            dependency_snapshot_sha256=DEPENDENCY_SNAPSHOT_SHA256,
            source_index_sha256=SOURCE_INDEX_SHA256,
            expected_counts=COUNTS,
            artifact_root=artifact_root,
        )


def test_final_runner_failure_log_is_preserved_exclusively(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    scripts = project_root / "scripts"
    scripts.mkdir(parents=True)
    runner = scripts / "run_task4_acceptance.sh"
    runner.write_text(
        "#!/usr/bin/env bash\n"
        "printf 'BOUND_RUN_ID=%s\\n' \"${TASK4_FINAL_RUN_ID}\"\n"
        "printf 'deliberate failure\\n' >&2\n"
        "exit 7\n",
        encoding="utf-8",
    )
    runner.chmod(0o750)
    artifact_root = tmp_path / "artifacts"

    with pytest.raises(RuntimeError, match="exit code 7"):
        _run_final_acceptance(
            project_root=project_root,
            run_id=RUN_ID,
            artifact_root=artifact_root,
        )
    log = artifact_root / "runs" / RUN_ID / "run.log"
    assert log.read_text(encoding="utf-8") == (
        f"BOUND_RUN_ID={RUN_ID}\ndeliberate failure\n"
    )

    with pytest.raises(FileExistsError):
        _run_final_acceptance(
            project_root=project_root,
            run_id=RUN_ID,
            artifact_root=artifact_root,
        )
    assert log.read_text(encoding="utf-8") == (
        f"BOUND_RUN_ID={RUN_ID}\ndeliberate failure\n"
    )


def test_final_log_verifier_rejects_count_gate_and_candidate_mismatch(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    log = _valid_log(artifact_root)
    valid_text = log.read_text(encoding="utf-8")
    log.write_text(
        valid_text.replace(
            f"{COUNTS[0]} passed in 1.00s",
            "52 passed in 1.00s",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="final counts do not satisfy"):
        _verify_final_log(
            log,
            run_id=RUN_ID,
            runtime=RUNTIME,
            dependency_snapshot_sha256=DEPENDENCY_SNAPSHOT_SHA256,
            source_index_sha256=SOURCE_INDEX_SHA256,
            expected_counts=COUNTS,
            artifact_root=artifact_root,
        )

    log.write_text(valid_text, encoding="utf-8")
    with pytest.raises(ValueError, match="differ from candidate"):
        _verify_final_log(
            log,
            run_id=RUN_ID,
            runtime=RUNTIME,
            dependency_snapshot_sha256=DEPENDENCY_SNAPSHOT_SHA256,
            source_index_sha256=SOURCE_INDEX_SHA256,
            expected_counts=(53, 154, 273),
            artifact_root=artifact_root,
        )


def test_final_runner_receives_only_allowlisted_environment_and_fixed_bash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    scripts = project_root / "scripts"
    scripts.mkdir(parents=True)
    runner = scripts / "run_task4_acceptance.sh"
    runner.write_text(
        "#!/definitely/not/the/interpreter\n"
        "set -eu\n"
        "printf 'BASH=%s\\n' \"${BASH_VERSION:+/bin/bash}\"\n"
        "printf 'HOME=%s\\n' \"${HOME}\"\n"
        "printf 'PATH=%s\\n' \"${PATH}\"\n"
        "printf 'USER=%s\\n' \"${USER}\"\n"
        "printf 'LOGNAME=%s\\n' \"${LOGNAME}\"\n"
        "printf 'RUN_ID=%s\\n' \"${TASK4_FINAL_RUN_ID}\"\n"
        "printf 'GIT=%s\\n' \"$(command -v git)\"\n"
        "for name in BASH_ENV ENV GH_TOKEN GIT_CONFIG_GLOBAL "
        "PYTHONPATH PYTEST_ADDOPTS INJECTED_BY_BASH_ENV; do\n"
        "  if /usr/bin/printenv \"${name}\" >/dev/null 2>&1; then\n"
        "    printf 'LEAKED=%s\\n' \"${name}\"\n"
        "    exit 9\n"
        "  fi\n"
        "done\n"
        "if declare -F injected_function >/dev/null; then\n"
        "  printf 'LEAKED_FUNCTION\\n'\n"
        "  exit 10\n"
        "fi\n",
        encoding="utf-8",
    )
    runner.chmod(0o750)
    bash_env = tmp_path / "bash-env"
    bash_env.write_text(
        "export INJECTED_BY_BASH_ENV=1\n",
        encoding="utf-8",
    )
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    for name in ("bash", "git"):
        fake = fake_bin / name
        fake.write_text(
            "#!/bin/sh\nprintf 'FAKE COMMAND\\n'\nexit 99\n",
            encoding="utf-8",
        )
        fake.chmod(0o750)
    monkeypatch.setenv("BASH_ENV", str(bash_env))
    monkeypatch.setenv("ENV", str(bash_env))
    monkeypatch.setenv("PATH", str(fake_bin))
    monkeypatch.setenv("GH_TOKEN", "caller-gh-token")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "fake-gitconfig"))
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "fake-python"))
    monkeypatch.setenv("PYTEST_ADDOPTS", "--collect-only")
    monkeypatch.setenv(
        "BASH_FUNC_injected_function%%",
        "() { printf 'INJECTED FUNCTION\\n'; }",
    )

    artifact_root = tmp_path / "artifacts"
    log = _run_final_acceptance(
        project_root=project_root,
        run_id=RUN_ID,
        artifact_root=artifact_root,
    )
    assert log.read_text(encoding="utf-8") == (
        "BASH=/bin/bash\n"
        "HOME=/home/cunyuliu\n"
        "PATH=/usr/bin:/bin\n"
        "USER=cunyuliu\n"
        "LOGNAME=cunyuliu\n"
        f"RUN_ID={RUN_ID}\n"
        "GIT=/usr/bin/git\n"
    )


def test_anonymous_https_refs_require_public_default_main_and_exact_head() -> None:
    head = "a" * 40
    output = (
        "ref: refs/heads/main\tHEAD\n"
        f"{head}\tHEAD\n"
        f"{head}\trefs/heads/main\n"
    )
    assert _parse_public_refs(output, expected_head=head) == {
        "defaultBranchRef": {"name": "main"},
        "nameWithOwner": "Cunyu-Liu/d2t-rna",
        "visibility": "PUBLIC",
    }

    for changed in (
        output.replace("refs/heads/main\tHEAD", "refs/heads/dev\tHEAD", 1),
        output.replace(head, "b" * 40, 1),
        output + f"{head}\trefs/heads/extra\n",
    ):
        with pytest.raises(ValueError, match="evidence changed"):
            _parse_public_refs(changed, expected_head=head)


def test_git_process_uses_fixed_binary_and_caller_independent_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured.update(kwargs)
        return SimpleNamespace(stdout="clean output\n")

    monkeypatch.setenv("PATH", str(tmp_path / "fake-bin"))
    monkeypatch.setenv("GH_TOKEN", "caller-token")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "hostile"))
    monkeypatch.setenv("BASH_ENV", str(tmp_path / "hostile-bash"))
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "hostile-python"))
    monkeypatch.setattr(closure_module.subprocess, "run", fake_run)

    assert _run_git(tmp_path, "status", "--porcelain") == "clean output"
    assert captured["argv"] == (
        "/usr/bin/git",
        "status",
        "--porcelain",
    )
    assert captured["cwd"] == tmp_path
    assert captured["env"] == _git_environment()
    assert set(captured["env"]) == {
        "HOME",
        "USER",
        "LOGNAME",
        "PATH",
        "LANG",
        "LC_ALL",
        "GIT_CONFIG_NOSYSTEM",
        "GIT_CONFIG_GLOBAL",
        "GIT_TERMINAL_PROMPT",
        "GIT_NO_REPLACE_OBJECTS",
    }


def test_task4_commit_delta_accepts_only_task3_child_and_frozen_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert (
        closure_module.TASK3_ACCEPTANCE_COMMIT
        == TASK3_ACCEPTANCE_COMMIT
        == "5f3a0301fb0051fcee173a08c98677bc1ea20ec5"
    )

    def fake_git(project_root: Path, *argv: str, **kwargs) -> str:
        assert project_root == tmp_path
        assert argv == (
            "rev-list",
            "--parents",
            "-n",
            "1",
            HEAD,
        )
        return f"{HEAD} {TASK3_ACCEPTANCE_COMMIT}"

    def fake_git_bytes(project_root: Path, *argv: str) -> bytes:
        assert project_root == tmp_path
        assert argv == (
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            "--no-renames",
            "-z",
            TASK3_ACCEPTANCE_COMMIT,
            HEAD,
        )
        return _commit_paths_bytes(TASK4_CHANGED_PATHS)

    monkeypatch.setattr(closure_module, "_run_git", fake_git)
    monkeypatch.setattr(
        closure_module,
        "_run_git_bytes",
        fake_git_bytes,
    )
    result = _verify_task4_commit_delta(
        tmp_path,
        expected_head=HEAD,
    )
    assert result["parent"] == TASK3_ACCEPTANCE_COMMIT
    assert result["changed_paths"] == sorted(TASK4_CHANGED_PATHS)
    assert len(result["changed_paths_sha256"]) == 64
    assert len(TASK4_CHANGED_PATHS) == 28


def test_task4_commit_delta_rejects_wrong_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        closure_module,
        "_run_git",
        lambda *args, **kwargs: f"{HEAD} {'b' * 40}",
    )
    with pytest.raises(ValueError, match="single parent"):
        _verify_task4_commit_delta(
            tmp_path,
            expected_head=HEAD,
        )


@pytest.mark.parametrize(
    "paths",
    (
        TASK4_CHANGED_PATHS | {"unexpected-task4-file.txt"},
        TASK4_CHANGED_PATHS - {"README.md"},
    ),
)
def test_task4_commit_delta_rejects_extra_or_missing_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    paths: frozenset[str],
) -> None:
    monkeypatch.setattr(
        closure_module,
        "_run_git",
        lambda *args, **kwargs: (
            f"{HEAD} {TASK3_ACCEPTANCE_COMMIT}"
        ),
    )
    monkeypatch.setattr(
        closure_module,
        "_run_git_bytes",
        lambda *args, **kwargs: _commit_paths_bytes(paths),
    )
    with pytest.raises(ValueError, match="frozen allowlist"):
        _verify_task4_commit_delta(
            tmp_path,
            expected_head=HEAD,
        )


@pytest.mark.parametrize(
    ("raw_paths", "message"),
    (
        (b"", "terminal NUL"),
        (b"README.md", "terminal NUL"),
        (b"README.md\0README.md\0", "duplicates"),
        (b"\xff\0", "not UTF-8"),
    ),
)
def test_task4_commit_delta_path_parser_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raw_paths: bytes,
    message: str,
) -> None:
    monkeypatch.setattr(
        closure_module,
        "_run_git",
        lambda *args, **kwargs: (
            f"{HEAD} {TASK3_ACCEPTANCE_COMMIT}"
        ),
    )
    monkeypatch.setattr(
        closure_module,
        "_run_git_bytes",
        lambda *args, **kwargs: raw_paths,
    )
    with pytest.raises(ValueError, match=message):
        _verify_task4_commit_delta(
            tmp_path,
            expected_head=HEAD,
        )


@pytest.mark.parametrize(
    "runner_name",
    ("run_task4_candidate.sh", "run_task4_acceptance.sh"),
)
def test_task4_shell_runners_pin_interpreter_path_and_clear_injection(
    runner_name: str,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    text = (project_root / "scripts" / runner_name).read_text(
        encoding="utf-8"
    )
    assert text.splitlines()[0] == "#!/bin/bash"
    assert "PATH=/usr/bin:/bin\nexport PATH\n" in text
    assert (
        "BASH_ENV|ENV|BASH_FUNC_*|GIT_*|GH_*|PYTHON*|_PYTHON*|PYTEST*)"
        in text
    )
    for family in (
        "BASH_ENV",
        "ENV",
        "BASH_FUNC_*",
        "GIT_*",
        "GH_*",
        "PYTHON*",
        "_PYTHON*",
        "PYTEST*",
    ):
        assert family in text
    assert "builtin unset -f" in text
    assert (
        "TASK4_DEPENDENCY_SNAPSHOT_SHA256=%s"
        in text
    )
    assert (
        "export TASK4_REGISTERED_DEPENDENCY_SNAPSHOT_SHA256="
        '"${dependency_snapshot_sha}"'
        in text
    )
    assert (
        "export TASK4_REGISTERED_SOURCE_INDEX_SHA256="
        '"${pre_test_source_index_sha}"'
        in text
    )
    assert text.count("TASK4_PRE_TEST_SOURCE_INDEX_SHA256=%s") == 1
    assert text.count("TASK4_POST_TEST_SOURCE_INDEX_SHA256=%s") == 1
    assert (
        '[[ "${post_test_source_index_sha}" '
        '!= "${pre_test_source_index_sha}" ]]'
        in text
    )


def test_final_shell_runner_uses_nul_safe_file_audits() -> None:
    project_root = Path(__file__).resolve().parents[2]
    text = (
        project_root / "scripts" / "run_task4_acceptance.sh"
    ).read_text(encoding="utf-8")
    assert text.count("read -r -d '' path") == 2
    assert text.count(
        "/usr/bin/git ls-files -z --cached --others "
        "--exclude-standard"
    ) == 0
    assert text.count("/usr/bin/git ls-files -z --cached --others") == 1
    assert text.count('done < "${committable_path_index}"') == 2
    assert "TASK4_FINAL_RUN_ID=%s" in text


def test_build_closure_orders_local_run_and_publication_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    manifest_path = project_root / "manifests" / "task4_acceptance.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("{}\n", encoding="utf-8")
    run_log = tmp_path / "run.log"
    run_log.write_text("registered final log\n", encoding="utf-8")
    output = tmp_path / "closure.json"
    events: list[str] = []
    state = {
        "head": HEAD,
        "title": closure_module.COMMIT_TITLE,
        "branch": "main",
        "status": "",
        "origin_url": closure_module.ORIGIN_URL,
    }
    manifest = {
        "runtime": {
            **RUNTIME,
            "dependency_snapshot_sha256": DEPENDENCY_SNAPSHOT_SHA256,
        },
        "fixture_evidence": {
            "manifest": {
                "path": "/mnt/cunyuliu/d2t-rna/artifacts/fixture.json",
                "sha256": "b" * 64,
            }
        },
        "source_index_sha256": "c" * 64,
        "test_evidence": {
            "run_id": "task4-acceptance-unit",
            "exact_tests_passed": COUNTS[0],
            "contract_probability_exact_tests_passed": COUNTS[1],
            "full_tests_passed": COUNTS[2],
        },
        "claim_boundary": {"scientific_claim_authorized": False},
    }

    def resolve_output(*args, **kwargs):
        events.append("resolve_output")
        return output

    def preflight(*args, **kwargs):
        events.append("preflight")
        return state

    def final_run(*args, **kwargs):
        events.append("final_run")
        return run_log

    def commit_delta(*args, **kwargs):
        events.append("commit_delta")
        assert kwargs["expected_head"] == state["head"]
        return {
            "parent": TASK3_ACCEPTANCE_COMMIT,
            "changed_paths": sorted(TASK4_CHANGED_PATHS),
            "changed_paths_sha256": "e" * 64,
        }

    def verify_manifest(*args, **kwargs):
        events.append("manifest")
        return manifest

    def dependency_snapshot(*args, **kwargs):
        events.append("dependency")
        return DEPENDENCY_SNAPSHOT_SHA256

    def verify_log(*args, **kwargs):
        events.append("final_log")
        assert (
            kwargs["dependency_snapshot_sha256"]
            == DEPENDENCY_SNAPSHOT_SHA256
        )
        assert kwargs["source_index_sha256"] == "c" * 64
        assert kwargs["expected_counts"] == COUNTS
        return COUNTS

    def publication(*args, **kwargs):
        events.append("publication")
        assert kwargs["expected_head"] == state["head"]
        return state, {"visibility": "PUBLIC"}

    monkeypatch.setattr(
        closure_module,
        "_resolve_output_path",
        resolve_output,
    )
    monkeypatch.setattr(
        closure_module,
        "_verify_local_preflight",
        preflight,
    )
    monkeypatch.setattr(
        closure_module,
        "_run_final_acceptance",
        final_run,
    )
    monkeypatch.setattr(
        closure_module,
        "_verify_task4_commit_delta",
        commit_delta,
    )
    monkeypatch.setattr(
        closure_module,
        "verify_manifest",
        verify_manifest,
    )
    monkeypatch.setattr(
        closure_module,
        "runtime_dependency_snapshot_sha256",
        dependency_snapshot,
    )
    monkeypatch.setattr(
        closure_module,
        "_verify_final_log",
        verify_log,
    )
    monkeypatch.setattr(
        closure_module,
        "_verify_publication",
        publication,
    )

    closure = closure_module.build_closure(
        project_root=project_root,
        run_id=RUN_ID,
        output_path=output,
    )
    assert events == [
        "resolve_output",
        "preflight",
        "commit_delta",
        "final_run",
        "manifest",
        "dependency",
        "final_log",
        "publication",
    ]
    assert closure["status"] == "CLOSED_ACCEPTED_PUSHED_PUBLIC"
    assert closure["schema"] == "d2t_rna.task4_post_commit_closure.v3"
    assert closure["commit"]["parent"] == TASK3_ACCEPTANCE_COMMIT
    assert closure["commit"]["changed_paths"] == sorted(
        TASK4_CHANGED_PATHS
    )
    assert closure["commit"]["changed_paths_sha256"] == "e" * 64
    assert output.is_file()
