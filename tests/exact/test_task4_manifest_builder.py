from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.build_task4_acceptance_manifest import (
    _candidate_counts,
    _junit_count,
    _source_index,
)
from scripts.verify_task4_acceptance_manifest import EXPECTED_SOURCE_PATHS


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_manifest_builder_derives_all_three_marked_test_counts(
    tmp_path: Path,
) -> None:
    log = tmp_path / "run.log"
    log.write_text(
        "\n".join(
            (
                "TASK4_EXACT_TESTS_BEGIN",
                "71 passed in 1.00s",
                "TASK4_EXACT_TESTS_END",
                "TASK4_COMBINED_TESTS_BEGIN",
                "201 passed, 1 warning in 2.00s",
                "TASK4_COMBINED_TESTS_END",
                "TASK4_FULL_TESTS_BEGIN",
                "321 passed in 321.00s (0:05:21)",
                "TASK4_FULL_TESTS_END",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    assert _candidate_counts(log) == (71, 201, 321)


def test_manifest_builder_rejects_ambiguous_test_summary(
    tmp_path: Path,
) -> None:
    log = tmp_path / "run.log"
    log.write_text(
        "TASK4_EXACT_TESTS_BEGIN\n"
        "1 passed in 1.00s\n"
        "2 passed in 2.00s\n"
        "TASK4_EXACT_TESTS_END\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="lacks one pytest summary"):
        _candidate_counts(log)


def test_manifest_builder_reads_one_junit_aggregate(tmp_path: Path) -> None:
    junit = tmp_path / "tests.xml"
    junit.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuites><testsuite name="pytest" errors="0" failures="0" '
        'skipped="0" tests="7" time="0.1"></testsuite></testsuites>',
        encoding="utf-8",
    )
    assert _junit_count(junit) == 7


def test_manifest_builder_source_index_fails_on_missing_source(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="registered source is unavailable"):
        _source_index(tmp_path)


def test_task4_source_index_stays_closed_in_a_descendant_stage() -> None:
    with pytest.raises(
        ValueError,
        match="dynamic Python execution closure",
    ):
        _source_index(PROJECT_ROOT)

    assert len(EXPECTED_SOURCE_PATHS) == 74
    assert "manifests/task4_acceptance.json" not in EXPECTED_SOURCE_PATHS
    assert {
        "manifests/task2_failure_policy_abstain_all.json",
        "manifests/task3_historical_exposure_registry.json",
    }.issubset(EXPECTED_SOURCE_PATHS)
    current_historical_regression_index = {
        relative: hashlib.sha256(
            (PROJECT_ROOT / relative).read_bytes()
        ).hexdigest()
        for relative in sorted(EXPECTED_SOURCE_PATHS)
    }
    assert set(current_historical_regression_index) == EXPECTED_SOURCE_PATHS


def test_builders_freeze_verifier_runtime_before_other_project_imports() -> None:
    manifest_builder = (
        PROJECT_ROOT / "scripts" / "build_task4_acceptance_manifest.py"
    ).read_text(encoding="utf-8")
    closure_builder = (
        PROJECT_ROOT / "scripts" / "build_task4_post_commit_closure.py"
    ).read_text(encoding="utf-8")

    verifier_import = (
        "from scripts.verify_task4_acceptance_manifest import ("
    )
    assert manifest_builder.index(verifier_import) < manifest_builder.index(
        "import pydantic"
    )
    assert "from d2t_rna" not in manifest_builder[
        : manifest_builder.index(verifier_import)
    ]
    assert "from d2t_rna" not in closure_builder
    assert "canonical_json_bytes," in closure_builder[
        closure_builder.index(verifier_import) :
    ]


def test_manifest_builder_rejects_unregistered_script_input(
    tmp_path: Path,
) -> None:
    for relative in EXPECTED_SOURCE_PATHS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    (tmp_path / "scripts" / "extra.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="dynamic Python execution closure",
    ):
        _source_index(tmp_path)
