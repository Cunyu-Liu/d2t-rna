from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from d2t_rna.contracts.base import validate_contract_json_syntax
from d2t_rna.contracts.enums import ExposureStatus, LockStage
from d2t_rna.data import sanitize as sanitize_module
from d2t_rna.data.sanitize import (
    HISTORICAL_EXPOSURE_REGISTRY,
    HistoricalExposureRecord,
    PreRevealDisposition,
    audit_planning_package,
    assert_pre_reveal_audit_clean,
    sanitizer_report_hash,
    validate_historical_exposure_registry,
)


def package_with_text(
    tmp_path: Path,
    *,
    filename: str = "sample.txt",
    content: str = "masked\n",
) -> Path:
    root = tmp_path / "package"
    root.mkdir(parents=True)
    (root / filename).write_text(content, encoding="utf-8")
    return root


def audit(
    root: Path,
    *,
    evaluation_id: str = "evaluation.sanitizer.001",
    stage: LockStage = LockStage.A,
):
    return audit_planning_package(
        evaluation_id=evaluation_id,
        stage=stage,
        package_root=root,
    )


@pytest.mark.parametrize(
    "secret",
    [
        "ON",
        "on",
        "oN",
        "ＯＮ",
        "O\u200bN",
        "O\u2060N",
        "O\u00adN",
        "O\u0301N",
        "ᴏɴ",
        "O_N",
        "O-N",
        "O.N",
        "OFF",
        "ReScUe",
        "ОΝ",
        r"O\u004e",
        "%4f%4e",
        "%2525254f%2525254e",
        "O&#78;",
    ],
)
@pytest.mark.parametrize(
    "surface",
    ["filename", "header", "metadata_key", "metadata_value"],
)
def test_real_package_registered_tokens_are_detected_after_normalization(
    tmp_path: Path,
    secret: str,
    surface: str,
) -> None:
    root = tmp_path / "package"
    root.mkdir()
    if surface == "filename":
        (root / f"sample_{secret}.txt").write_text("masked\n", encoding="utf-8")
    elif surface == "header":
        (root / "sample.txt").write_text(
            f"sample: {secret}\n",
            encoding="utf-8",
        )
    elif surface == "metadata_key":
        (root / "sample.json").write_text(
            json.dumps({secret: "masked"}),
            encoding="utf-8",
        )
    else:
        (root / "sample.json").write_text(
            json.dumps({"group": secret}),
            encoding="utf-8",
        )

    report = audit(root)
    assert (
        report.disposition
        is PreRevealDisposition.EVALUATION_INVALIDATED_PRE_LOCK_D
    )
    assert report.public_findings
    assert sanitizer_report_hash(report)


@pytest.mark.parametrize(
    "safe_text",
    ["condition", "office", "only", "rescuers", "turnover", "none"],
)
def test_registered_tokens_use_boundaries_without_substring_false_positives(
    tmp_path: Path,
    safe_text: str,
) -> None:
    root = package_with_text(
        tmp_path,
        filename=f"{safe_text}.txt",
        content=f"description: {safe_text}\n",
    )
    report = audit(root)
    assert (
        report.disposition
        is PreRevealDisposition.NO_REGISTERED_LEAKAGE_DETECTED
    )
    assert report.public_findings == ()
    assert_pre_reveal_audit_clean(report)


@pytest.mark.parametrize(
    "forbidden_name",
    [
        "population_estimate",
        "x_population_estimate_v2",
        "confidence_region",
        "directional_evidence",
        "metadata.directional_evidence.value",
        "state_preservation_result",
        "projected_state_proportions",
        "h0_h1_core_binding",
        "action_effect_labels",
        "native_t4_eligible",
    ],
)
def test_nested_pre_d_truth_fields_in_real_json_invalidate(
    tmp_path: Path,
    forbidden_name: str,
) -> None:
    root = tmp_path / "package"
    root.mkdir()
    (root / "sample.json").write_text(
        json.dumps({"outer": {"nested": {forbidden_name: "sealed"}}}),
        encoding="utf-8",
    )
    report = audit(root)
    assert (
        report.disposition
        is PreRevealDisposition.EVALUATION_INVALIDATED_PRE_LOCK_D
    )


def test_scanner_owns_enumeration_and_cannot_omit_hidden_leaking_file(
    tmp_path: Path,
) -> None:
    root = tmp_path / "package"
    root.mkdir()
    (root / "safe.txt").write_text("masked\n", encoding="utf-8")
    (root / "hidden_ON.fastq").write_text("@masked\nACGU\n+\n!!!!\n", encoding="utf-8")
    report = audit(root)
    assert report.scanned_entry_count == 2
    assert (
        report.disposition
        is PreRevealDisposition.EVALUATION_INVALIDATED_PRE_LOCK_D
    )


def test_file_content_hash_and_size_change_the_locked_package_root(
    tmp_path: Path,
) -> None:
    root = package_with_text(tmp_path, content="masked-one\n")
    first = audit(root)
    (root / "sample.txt").write_text("masked-two\n", encoding="utf-8")
    second = audit(root)
    assert first.source_package_hash != second.source_package_hash
    assert sanitizer_report_hash(first) != sanitizer_report_hash(second)


def test_atomic_regular_file_to_symlink_swap_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = package_with_text(tmp_path)
    target = root / "sample.txt"
    backup = root / "sample.backup"
    real_open = sanitize_module.os.open
    swapped = False

    def swapping_open(path, flags):
        nonlocal swapped
        if Path(path) == target and not swapped:
            swapped = True
            target.rename(backup)
            target.symlink_to(backup)
        return real_open(path, flags)

    monkeypatch.setattr(sanitize_module.os, "open", swapping_open)
    report = audit(root)
    assert swapped is True
    assert (
        report.disposition
        is PreRevealDisposition.AUDIT_INCOMPLETE_FAIL_CLOSED
    )


def test_public_findings_never_copy_secret_surfaces(
    tmp_path: Path,
) -> None:
    secret_path = "population_4815162342_ON.json"
    secret_value = "directional_evidence=OFF; estimate=0.987654321"
    root = tmp_path / "package"
    root.mkdir()
    (root / secret_path).write_text(
        json.dumps({"cohort": secret_value}),
        encoding="utf-8",
    )
    report = audit(root)
    serialized = json.dumps(report.model_dump(mode="json"), sort_keys=True)
    assert secret_path not in serialized
    assert secret_value not in serialized
    assert "4815162342" not in serialized
    assert "0.987654321" not in serialized
    assert all(
        set(finding.model_dump(mode="json"))
        == {
            "schema_id",
            "schema_version",
            "entry_index",
            "path_hash",
            "surface",
            "locator_hash",
            "rule_id",
        }
        for finding in report.public_findings
    )


def test_empty_opaque_archive_symlink_and_invalid_utf8_fail_closed(
    tmp_path: Path,
) -> None:
    roots: list[Path] = []

    empty = tmp_path / "empty"
    empty.mkdir()
    roots.append(empty)

    opaque = tmp_path / "opaque"
    opaque.mkdir()
    (opaque / "data.bin").write_bytes(b"opaque")
    roots.append(opaque)

    archive = tmp_path / "archive"
    archive.mkdir()
    (archive / "disguised.txt").write_bytes(b"PK\x03\x04payload")
    roots.append(archive)

    invalid_utf8 = tmp_path / "invalid"
    invalid_utf8.mkdir()
    (invalid_utf8 / "sample.txt").write_bytes(b"\xff\xfe")
    roots.append(invalid_utf8)

    symlink = tmp_path / "symlink"
    symlink.mkdir()
    target = symlink / "target.txt"
    target.write_text("masked\n", encoding="utf-8")
    (symlink / "alias.txt").symlink_to(target)
    roots.append(symlink)

    for index, root in enumerate(roots):
        report = audit(
            root,
            evaluation_id=f"evaluation.failclosed.{index}",
        )
        assert (
            report.disposition
            is PreRevealDisposition.AUDIT_INCOMPLETE_FAIL_CLOSED
        )
        with pytest.raises(ValueError):
            assert_pre_reveal_audit_clean(report)


def test_casefold_colliding_paths_and_unsafe_evaluation_id_fail_closed(
    tmp_path: Path,
) -> None:
    root = tmp_path / "package"
    root.mkdir()
    (root / "Sample.txt").write_text("masked\n", encoding="utf-8")
    (root / "sample.txt").write_text("masked\n", encoding="utf-8")
    collision = audit(root)
    assert (
        collision.disposition
        is PreRevealDisposition.AUDIT_INCOMPLETE_FAIL_CLOSED
    )

    safe_root = package_with_text(tmp_path / "second")
    leaked_id = audit(
        safe_root,
        evaluation_id="evaluation.ON.001",
    )
    assert (
        leaked_id.disposition
        is PreRevealDisposition.EVALUATION_INVALIDATED_PRE_LOCK_D
    )


def test_report_invariants_reject_model_copy_or_construct_forgery(
    tmp_path: Path,
) -> None:
    clean = audit(package_with_text(tmp_path))
    invalid = clean.model_copy(update={"scanned_entry_count": -7})
    with pytest.raises((ValidationError, ValueError)):
        assert_pre_reveal_audit_clean(invalid)

    leaking_root = tmp_path / "leaking"
    leaking_root.mkdir()
    (leaking_root / "sample_ON.txt").write_text("masked\n", encoding="utf-8")
    leaking = audit(leaking_root)
    forged = leaking.model_copy(
        update={
            "disposition": PreRevealDisposition.NO_REGISTERED_LEAKAGE_DETECTED
        }
    )
    with pytest.raises((ValidationError, ValueError)):
        assert_pre_reveal_audit_clean(forged)


def test_report_and_source_roots_are_deterministic(
    tmp_path: Path,
) -> None:
    root = package_with_text(tmp_path)
    left = audit(root)
    right = audit(root)
    assert left == right
    assert sanitizer_report_hash(left) == sanitizer_report_hash(right)


def test_historical_exposure_registry_is_exact_and_not_downgradable() -> None:
    validated = validate_historical_exposure_registry(
        HISTORICAL_EXPOSURE_REGISTRY
    )
    assert tuple(record.dataset_id for record in validated) == (
        "add",
        "rorc",
        "sam-iii",
    )
    assert all(
        record.exposure_status
        is ExposureStatus.HISTORICALLY_SEMANTICALLY_EXPOSED_RETROSPECTIVE
        and record.held_out_claim_allowed is False
        and record.prospective_claim_allowed is False
        for record in validated
    )

    downgraded = validated[0].model_copy(
        update={
            "display_name": "PROSPECTIVE HELD-OUT",
            "basis_section_id": "unrelated.section",
        }
    )
    with pytest.raises((ValidationError, ValueError)):
        validate_historical_exposure_registry((downgraded, *validated[1:]))

    extra = HistoricalExposureRecord(
        dataset_id="unregistered",
        display_name="unregistered",
        exposure_status=(
            ExposureStatus.HISTORICALLY_SEMANTICALLY_EXPOSED_RETROSPECTIVE
        ),
        held_out_claim_allowed=False,
        prospective_claim_allowed=False,
        basis_contract_hash="8" * 64,
        basis_section_id="task3.historical_exposure",
    )
    with pytest.raises(ValueError):
        validate_historical_exposure_registry((*validated, extra))


def test_versioned_historical_exposure_manifest_matches_registry() -> None:
    manifest_path = (
        Path(__file__).resolve().parents[2]
        / "manifests"
        / "task3_historical_exposure_registry.json"
    )
    raw = manifest_path.read_bytes()
    validate_contract_json_syntax(raw)
    manifest = json.loads(raw)
    assert set(manifest) == {"schema_id", "schema_version", "records"}
    assert manifest["schema_id"] == "d2t_rna.historical_exposure_registry"
    records = tuple(
        HistoricalExposureRecord.model_validate(item, strict=True)
        for item in manifest["records"]
    )
    assert validate_historical_exposure_registry(records) == (
        HISTORICAL_EXPOSURE_REGISTRY
    )
