from __future__ import annotations

from pathlib import Path

import pytest

from scripts.build_task5_post_commit_closure import (
    TASK4_ACCEPTANCE_COMMIT,
    _parse_public_refs,
    _resolve_output_path,
    _verify_candidate_final_fixture_payload,
)
from scripts.verify_task5_acceptance_manifest import (
    CLAIM_BOUNDARY,
    CONTRACT_SHA256,
    EXPECTED_FIXTURE_ARTIFACTS,
    FIXTURE_SCHEMA,
)


HEAD = "a" * 40


def test_public_refs_require_anonymous_main_and_head_identity() -> None:
    output = (
        "ref: refs/heads/main\tHEAD\n"
        f"{HEAD}\tHEAD\n"
        f"{HEAD}\trefs/heads/main\n"
    )
    assert _parse_public_refs(output, expected_head=HEAD) == {
        "default_branch": "main",
        "origin_main": HEAD,
        "repository": "Cunyu-Liu/d2t-rna",
        "visibility": "PUBLIC",
    }
    with pytest.raises(ValueError, match="anonymous GitHub"):
        _parse_public_refs(
            output.replace(HEAD, TASK4_ACCEPTANCE_COMMIT, 1),
            expected_head=HEAD,
        )


def test_closure_output_is_exclusive_and_under_artifact_root(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    run_id = "task5-final-20260730T210203+0800"
    valid = artifact_root / "runs" / run_id / "closure.json"
    assert _resolve_output_path(
        valid,
        run_id=run_id,
        artifact_root=artifact_root,
    ) == valid.resolve()
    with pytest.raises(ValueError, match="registered run closure path"):
        _resolve_output_path(
            artifact_root / "runs" / run_id / "other.json",
            run_id=run_id,
            artifact_root=artifact_root,
        )
    valid.parent.mkdir(parents=True)
    valid.write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        _resolve_output_path(
            valid,
            run_id=run_id,
            artifact_root=artifact_root,
        )
    with pytest.raises(ValueError, match="artifact root"):
        _resolve_output_path(
            tmp_path / "outside.json",
            run_id=run_id,
            artifact_root=artifact_root,
        )

    symlink_root = tmp_path / "symlink-artifacts"
    (symlink_root / "runs").mkdir(parents=True)
    symlink_target = tmp_path / "outside-run"
    symlink_target.mkdir()
    (symlink_root / "runs" / run_id).symlink_to(
        symlink_target,
        target_is_directory=True,
    )
    with pytest.raises(ValueError, match="symlink component"):
        _resolve_output_path(
            symlink_root / "runs" / run_id / "closure.json",
            run_id=run_id,
            artifact_root=symlink_root,
        )

    real_parent = tmp_path / "real-parent"
    (real_parent / "artifacts").mkdir(parents=True)
    parent_link = tmp_path / "parent-link"
    parent_link.symlink_to(real_parent, target_is_directory=True)
    linked_artifact_root = parent_link / "artifacts"
    with pytest.raises(ValueError, match="symlink component"):
        _resolve_output_path(
            linked_artifact_root / "runs" / run_id / "closure.json",
            run_id=run_id,
            artifact_root=linked_artifact_root,
        )


def _fixture_manifest(*, prefix: str = "a") -> dict[str, object]:
    return {
        "schema": FIXTURE_SCHEMA,
        "fixture_id": "task5.registered.synthetic-microcase.v1",
        "contract_sha256": CONTRACT_SHA256,
        "artifacts": {
            name: {
                "path": f"/mnt/cunyuliu/{prefix}/{name}.json",
                "sha256": f"{index + 1:x}" * 64,
            }
            for index, name in enumerate(sorted(EXPECTED_FIXTURE_ARTIFACTS))
        },
        "replay": {
            "all_registered_replays_passed": True,
            "scenario_count": 1,
            "baseline_seed_count": 100,
            "rorc_observational_case_count": 2,
            "rorc_registered_path_count": 16,
            "all_registered_rorc_paths_abstain": True,
            "observed_case_set_all_abstain": True,
            "risk_certificate_issued": False,
            "scientific_claim_authorized": False,
            "serialized_bearer_authorization": False,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }


def test_final_fixture_must_match_candidate_scientific_payload() -> None:
    candidate = _fixture_manifest(prefix="candidate")
    final = _fixture_manifest(prefix="final")
    digest = _verify_candidate_final_fixture_payload(candidate, final)
    assert len(digest) == 64

    final["artifacts"]["scenario_aggregate"]["sha256"] = "f" * 64
    with pytest.raises(ValueError, match="differs from candidate"):
        _verify_candidate_final_fixture_payload(candidate, final)
