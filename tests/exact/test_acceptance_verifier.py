from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import sys
from types import MappingProxyType, ModuleType

import pytest
from pydantic import ValidationError

import scripts.verify_task4_acceptance_manifest as verifier
from d2t_rna.contracts.base import (
    DuplicateJsonKeyError,
    canonical_json_bytes,
    canonical_sha256,
)
from scripts.build_task4_acceptance_fixture import build_fixture
from scripts.verify_task4_acceptance_manifest import (
    EXPECTED_SOURCE_PATHS,
    _canonical_load,
    _discover_python_execution_paths,
    _runtime_dependency_snapshot,
    _verify_exact_external_path_binding,
    _verify_fixture,
    _verify_python_process_isolation,
    _verify_runtime_import_closure,
    _verify_test_log,
    runtime_dependency_snapshot_sha256,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ACCEPTANCE_FLAGS = {
    "mathematical_statement_verified": True,
    "risk_certificate_issued": False,
    "formal_scientific_certificate_authorized": False,
    "prospective_claim_authorized": False,
    "new_library_claim_authorized": False,
    "serialized_bearer_authorization": False,
    "external_source_anchor_required": True,
}


def _write_canonical(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _build_registered_fixture(
    artifact_root: Path,
    *,
    name: str,
) -> Path:
    output_dir = artifact_root / name
    build_fixture(
        project_root=PROJECT_ROOT,
        output_dir=output_dir,
        artifact_root=artifact_root,
    )
    return output_dir / "fixture_manifest.json"


def _live_run_dir(artifact_root: Path) -> Path:
    path = artifact_root / "runs" / "task4-unit-live"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_dynamic_python_execution_closure_matches_frozen_index() -> None:
    historical_task4 = frozenset(
        path
        for path in EXPECTED_SOURCE_PATHS
        if (
            path.startswith(("src/", "tests/", "scripts/"))
            and (
                path.endswith((".py", ".pyi"))
                or path.endswith("/py.typed")
            )
        )
    )
    registered_task5_descendants = frozenset(
        {
            "scripts/build_task5_acceptance_fixture.py",
            "scripts/build_task5_acceptance_manifest.py",
            "scripts/build_task5_post_commit_closure.py",
            "scripts/verify_task5_acceptance_manifest.py",
            "src/d2t_rna/evaluation/baselines.py",
            "src/d2t_rna/evaluation/milp_check.py",
            "src/d2t_rna/evaluation/planner.py",
            "src/d2t_rna/evaluation/risk_binding.py",
            "src/d2t_rna/evaluation/scenario.py",
            "tests/evaluation/__init__.py",
            "tests/evaluation/factories.py",
            "tests/evaluation/test_baselines.py",
            "tests/evaluation/test_planner.py",
            "tests/evaluation/test_scenario.py",
            "tests/evaluation/test_task5_acceptance_closure.py",
            "tests/evaluation/test_task5_acceptance_verifier.py",
        }
    )
    registered_task6_descendants = frozenset(
        {
            "src/d2t_rna/data/manifest.py",
            "src/d2t_rna/data/validate.py",
            "tests/data/test_manifests.py",
            "src/d2t_rna/data/r1_materialize.py",
            "src/d2t_rna/data/r1_materialize_sam_iii.py",
            "src/d2t_rna/data/r2_evaluation.py",
            "src/d2t_rna/data/r2_sam_iii_diagnostic.py",
            "tests/data/test_r1_materialize.py",
            "tests/data/test_r1_materialize_sam_iii.py",
            "tests/data/test_r2_evaluation.py",
            "tests/data/test_r2_sam_iii_diagnostic.py",
            "scripts/task6_r1_run.py",
            "scripts/task6_r1_samiii_run.py",
            "scripts/task6_r1_rorc_run.py",
            "scripts/task6_r2_run.py",
            "scripts/task6_r2_samiii_diagnostic_run.py",
            "src/d2t_rna/data/measured_add.py",
            "src/d2t_rna/data/measured_glycine.py",
            "src/d2t_rna/data/measured_mattr.py",
            "src/d2t_rna/data/measured_negative.py",
            "src/d2t_rna/data/observation_model.py",
            "tests/data/test_replicate_likelihood.py",
            "tests/data/test_measured_add.py",
            "tests/data/test_measured_glycine.py",
            "tests/data/test_measured_mattr.py",
            "tests/data/test_measured_negative.py",
        }
    )
    registered_t2_descendants = frozenset(
        {
            "src/d2t_rna/t2/__init__.py",
            "src/d2t_rna/t2/bounds.py",
            "src/d2t_rna/t2/costed.py",
            "src/d2t_rna/t2/costed_verify.py",
            "src/d2t_rna/t2/decision.py",
            "src/d2t_rna/t2/fixtures.py",
            "src/d2t_rna/t2/info.py",
            "src/d2t_rna/t2/lp.py",
            "src/d2t_rna/t2/model.py",
            "src/d2t_rna/t2/rna.py",
            "src/d2t_rna/t2/theorem.py",
            "src/d2t_rna/t2/verify.py",
            "src/d2t_rna/t2/witness.py",
            "src/d2t_rna/t2/spec.py",
            "tests/t2/test_semantic_counterexamples.py",
            "tests/t2/test_decision_semantics.py",
            "src/d2t_rna/evaluation/matrix.py",
            "src/d2t_rna/evaluation/t2_planner_binding.py",
            "src/d2t_rna/evaluation/validation.py",
            "tests/evaluation/test_matrix.py",
            "tests/evaluation/test_t2_planner_binding.py",
            "tests/evaluation/test_validation.py",
            "tests/t2/test_costed_design.py",
            "tests/t2/test_rna.py",
            "tests/t2/test_theorem_t2b.py",
            "tests/t2/test_theorem_t2c.py",
            "tests/t2/test_witness_engine.py",
            "tests/t2/test_paper_demo.py",
            "src/d2t_rna/t2/real_add.py",
            "tests/t2/test_real_add.py",
            "scripts/real_add_run.py",
            "scripts/real_add_measured_run.py",
            "scripts/real_glycine_measured_run.py",
            "scripts/real_mattr_measured_run.py",
            "scripts/real_negative_control_run.py",
            "scripts/search_greedy_gap.py",
            "scripts/t9_matrix_run.py",
            "scripts/t10_validation_run.py",
            "tests/t2/test_phase3_kernel.py",
            "scripts/t2_complexity_benchmark.py",
            "tests/evaluation/test_phase4_scale_grid.py",
            "tests/evaluation/test_phase4v2_catalog.py",
            "tests/evaluation/test_phase4v2_ablation.py",
            "scripts/t2_scale_grid_run.py",
            "scripts/t2_phase4v2_run.py",
            "scripts/t2_phase4v2_ablation.py",
            "tests/evaluation/test_phase4v2_baseline_suite.py",
            "scripts/t2_phase4v2_baseline_suite.py",
            "tests/evaluation/test_phase4v2_scalability.py",
            "scripts/t2_phase4v2_scalability.py",
            "scripts/t2_phase4v2_mechanism.py",
            "tests/evaluation/test_phase4v2_mechanism.py",
            "tests/evaluation/test_phase5_mechanism.py",
            "scripts/t2_mechanism_run.py",
        }
    )
    registered_delivery_descendants = frozenset(
        {
            "src/d2t_rna/contracts/submission_gate.py",
            "tests/contracts/test_submission_gate.py",
            "scripts/s12_3_submission_gate_run.py",
            "scripts/s14_delivery_bundle.py",
            "tests/scripts/test_s14_delivery_bundle.py",
            "scripts/m0_activate_v7.py",
            "scripts/paper_readiness_gate.py",
            "scripts/build_paper_demo_data.py",
            "scripts/redteam_p0_review.py",
            "src/d2t_rna/data/qualification.py",
            "tests/audit/test_certificate_roundtrip.py",
            "tests/audit/test_decision_metric_identity.py",
            "tests/audit/test_empty_discrete_convex.py",
            "tests/audit/test_measure_dispatch.py",
            "tests/audit/test_paper_readiness_gate_negative.py",
            "tests/audit/test_phase4_phase5_metric_identity.py",
            "tests/audit/test_provisional_authority.py",
            "tests/audit/test_p1_family_split.py",
            "tests/audit/test_phase1_acceptance_v2.py",
            "tests/audit/test_spec_dispatch.py",
            "tests/audit/test_t2c_constructive_status.py",
            "tests/data/test_data_qualification_v2.py",
            "tests/independent_oracles/__init__.py",
            "tests/independent_oracles/t2_raw_convex_oracle.py",
            "tests/independent_oracles/t2_raw_discrete_oracle.py",
        }
    )
    assert historical_task4.isdisjoint(registered_task5_descendants)
    assert historical_task4.isdisjoint(registered_task6_descendants)
    assert registered_task5_descendants.isdisjoint(registered_task6_descendants)
    all_registered = (
        historical_task4
        | registered_task5_descendants
        | registered_task6_descendants
        | registered_t2_descendants
        | registered_delivery_descendants
    )
    assert _discover_python_execution_paths(PROJECT_ROOT) == all_registered


def test_dynamic_execution_discovery_rejects_injection_inputs(
    tmp_path: Path,
) -> None:
    source_tree = tmp_path / "src"
    source_root = source_tree / "d2t_rna"
    tests_root = tmp_path / "tests"
    scripts_root = tmp_path / "scripts"
    source_root.mkdir(parents=True)
    tests_root.mkdir()
    scripts_root.mkdir()
    (source_root / "__init__.py").write_text("", encoding="utf-8")
    (tests_root / "__init__.py").write_text("", encoding="utf-8")
    extra = source_root / "extra.py"
    extra.write_text("VALUE = 1\n", encoding="utf-8")
    source_shadow = source_tree / "pytest.py"
    source_shadow.write_text("VALUE = 'shadow'\n", encoding="utf-8")
    script_extra = scripts_root / "extra.py"
    script_extra.write_text("VALUE = 2\n", encoding="utf-8")
    discovered = _discover_python_execution_paths(tmp_path)
    assert "src/d2t_rna/extra.py" in discovered
    assert "src/pytest.py" in discovered
    assert "scripts/extra.py" in discovered
    frozen_execution_paths = frozenset(
        path
        for path in EXPECTED_SOURCE_PATHS
        if (
            path.startswith(("src/", "tests/", "scripts/"))
            and (
                path.endswith((".py", ".pyi"))
                or path.endswith("/py.typed")
            )
        )
    )
    assert discovered != frozen_execution_paths

    legacy = source_root / "legacy.pyc"
    legacy.write_bytes(b"not executable bytecode")
    with pytest.raises(ValueError, match="sourceless bytecode"):
        _discover_python_execution_paths(tmp_path)
    legacy.unlink()

    native = source_root / (
        "native" + importlib.machinery.EXTENSION_SUFFIXES[0]
    )
    native.write_bytes(b"not a native extension")
    with pytest.raises(ValueError, match="native extension"):
        _discover_python_execution_paths(tmp_path)
    native.unlink()

    outside = tmp_path / "outside.py"
    outside.write_text("VALUE = 2\n", encoding="utf-8")
    (source_root / "linked.py").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        _discover_python_execution_paths(tmp_path)


def _fake_runtime_project(tmp_path: Path) -> tuple[Path, Path]:
    project_root = tmp_path / "project"
    (project_root / "src").mkdir(parents=True)
    (project_root / "tests").mkdir()
    (project_root / "scripts").mkdir()
    site_packages = (
        project_root
        / ".venv"
        / "lib"
        / "python3.11"
        / "site-packages"
    )
    site_packages.mkdir(parents=True)
    return project_root, site_packages


def _fake_conda_python_prefix(
    tmp_path: Path,
) -> tuple[
    Path,
    dict[str, object],
    dict[str, object],
    Path,
    dict[str, str],
]:
    project_root, site_packages = _fake_runtime_project(tmp_path)
    prefix = project_root / ".venv"
    bin_dir = prefix / "bin"
    conda_meta = prefix / "conda-meta"
    bin_dir.mkdir()
    conda_meta.mkdir()

    executable_bytes = b"fake anchored CPython 3.11 executable\n"
    python_target = bin_dir / "python3.11"
    python_target.write_bytes(executable_bytes)
    python_link = bin_dir / "python"
    python_link.symlink_to("python3.11")

    stdlib_root = site_packages.parent
    stdlib_source = stdlib_root / "os.py"
    stdlib_source.write_bytes(b"FAKE_STDLIB = True\n")
    stdlib_data = stdlib_root / "stdlib-data.txt"
    stdlib_data.write_bytes(b"fake stdlib data\n")

    package_sha = "a" * 64
    executable_sha = hashlib.sha256(executable_bytes).hexdigest()
    source_sha = hashlib.sha256(stdlib_source.read_bytes()).hexdigest()
    data_sha = hashlib.sha256(stdlib_data.read_bytes()).hexdigest()
    identity = {
        "name": "python",
        "version": "3.11.15",
        "build": "fake_build_1",
        "build_number": 1,
        "channel": "https://example.invalid/conda/linux-64",
        "subdir": "linux-64",
        "fn": "python-3.11.15-fake_build_1.conda",
        "url": (
            "https://example.invalid/conda/linux-64/"
            "python-3.11.15-fake_build_1.conda"
        ),
        "sha256": package_sha,
    }
    bin_entry = {
        "_path": "bin/python3.11",
        "file_mode": "binary",
        "path_type": "hardlink",
        "prefix_placeholder": "/fake/conda/prefix",
        "sha256": "b" * 64,
        "sha256_in_prefix": executable_sha,
        "size_in_bytes": len(executable_bytes),
    }
    source_entry = {
        "_path": "lib/python3.11/os.py",
        "path_type": "hardlink",
        "sha256": "c" * 64,
        "sha256_in_prefix": source_sha,
        "size_in_bytes": stdlib_source.stat().st_size,
    }
    data_entry = {
        "_path": "lib/python3.11/stdlib-data.txt",
        "path_type": "hardlink",
        "sha256": "d" * 64,
        "sha256_in_prefix": data_sha,
        "size_in_bytes": stdlib_data.stat().st_size,
    }
    paths = [bin_entry, source_entry, data_entry]
    record: dict[str, object] = {
        "build": identity["build"],
        "build_number": identity["build_number"],
        "channel": identity["channel"],
        "constrains": [],
        "depends": [],
        "extracted_package_dir": "python-fake",
        "files": [entry["_path"] for entry in paths],
        "fn": identity["fn"],
        "license": "PSF-2.0",
        "link": {},
        "md5": "0" * 32,
        "name": identity["name"],
        "package_tarball_full_path": "",
        "paths_data": {
            "paths": paths,
            "paths_version": 1,
        },
        "requested_spec": "python=3.11.15",
        "requested_specs": ["python=3.11.15"],
        "sha256": package_sha,
        "size": 1,
        "subdir": identity["subdir"],
        "timestamp": 1,
        "url": identity["url"],
        "version": identity["version"],
    }
    assert set(record) == verifier.EXPECTED_CONDA_RECORD_FIELDS
    record_relative_path = ".venv/conda-meta/python-fake.json"
    record_path = project_root / record_relative_path
    _write_canonical(record_path, record)

    runtime_binding = {
        "implementation": "CPython",
        "python_version": "3.11.15",
        "python_cache_tag": "cpython-311",
        "stdlib_module_names_count": len(
            verifier._FROZEN_STDLIB_MODULE_NAMES
        ),
        "stdlib_module_names_sha256": (
            verifier._FROZEN_STDLIB_MODULE_NAMES_SHA256
        ),
        "sysconfigdata_module_name": (
            verifier._FROZEN_SYSCONFIGDATA_MODULE_NAME
        ),
        "typing_pathless_aliases": tuple(
            sorted(verifier._FROZEN_TYPING_PATHLESS_ALIASES)
        ),
        "SOABI": "cpython-311-test-linux-gnu",
        "EXT_SUFFIX": ".cpython-311-test-linux-gnu.so",
        "MULTIARCH": "test-linux-gnu",
        "stdlib_relative": ".venv/lib/python3.11",
        "platstdlib_relative": ".venv/lib/python3.11",
        "DESTSHARED_relative": ".venv/lib/python3.11/lib-dynload",
    }
    authority: dict[str, object] = {
        "record_relative_path": record_relative_path,
        "record_sha256": hashlib.sha256(
            record_path.read_bytes()
        ).hexdigest(),
        "package_sha256": package_sha,
        "executable_sha256": executable_sha,
        "identity": identity,
        "record_fields": verifier.EXPECTED_CONDA_RECORD_FIELDS,
        "paths_count": len(paths),
        "runtime_paths_count": len(paths),
        "stdlib_paths_count": len(paths) - 1,
        "runtime_path_field_counts": {
            frozenset(bin_entry): 1,
            frozenset(source_entry): 2,
        },
        "bin_python_record": {
            key: bin_entry[key]
            for key in (
                "path_type",
                "file_mode",
                "sha256",
                "sha256_in_prefix",
                "size_in_bytes",
            )
        },
        "runtime_binding": runtime_binding,
    }
    observed_binding = {
        "implementation": runtime_binding["implementation"],
        "python_version": runtime_binding["python_version"],
        "python_cache_tag": runtime_binding["python_cache_tag"],
        "stdlib_module_names_count": runtime_binding[
            "stdlib_module_names_count"
        ],
        "stdlib_module_names_sha256": runtime_binding[
            "stdlib_module_names_sha256"
        ],
        "sysconfigdata_module_name": runtime_binding[
            "sysconfigdata_module_name"
        ],
        "typing_pathless_aliases": runtime_binding[
            "typing_pathless_aliases"
        ],
        "executable": str(python_link),
        "prefix": str(prefix),
        "base_prefix": str(prefix),
        "exec_prefix": str(prefix),
        "base_exec_prefix": str(prefix),
        "stdlib": str(stdlib_root),
        "platstdlib": str(stdlib_root),
        "SOABI": runtime_binding["SOABI"],
        "EXT_SUFFIX": runtime_binding["EXT_SUFFIX"],
        "MULTIARCH": runtime_binding["MULTIARCH"],
        "DESTSHARED": str(stdlib_root / "lib-dynload"),
    }
    registered_files = {
        ".venv/lib/python3.11/os.py": source_sha,
        ".venv/lib/python3.11/stdlib-data.txt": data_sha,
    }
    return (
        project_root,
        authority,
        observed_binding,
        record_path,
        registered_files,
    )


def _fake_file_module(
    name: str,
    path: Path,
    *,
    native: bool,
    package: bool = False,
) -> ModuleType:
    loader = (
        importlib.machinery.ExtensionFileLoader(name, str(path))
        if native
        else importlib.machinery.SourceFileLoader(name, str(path))
    )
    spec = importlib.util.spec_from_file_location(
        name,
        path,
        loader=loader,
        submodule_search_locations=(
            [str(path.parent)]
            if package
            else None
        ),
    )
    assert spec is not None
    module = ModuleType(name)
    module.__file__ = str(path)
    module.__loader__ = loader
    module.__spec__ = spec
    if package:
        module.__package__ = name
        module.__path__ = spec.submodule_search_locations
    return module


def _scan_only_runtime_modules(
    monkeypatch: pytest.MonkeyPatch,
    *module_names: str,
) -> None:
    selected = frozenset(module_names)
    monkeypatch.setattr(
        verifier,
        "_runtime_modules_snapshot",
        lambda: tuple(
            (name, sys.modules[name])
            for name in sorted(selected)
            if name in sys.modules
        ),
    )


def _fake_closure_dependency_snapshot(
    site_packages: Path,
    stdlib_files: tuple[Path, ...],
) -> dict[str, object]:
    site_record = site_packages / "registered.py"
    if not site_record.exists():
        site_record.write_bytes(b"REGISTERED = True\n")
    project_root = site_packages.parents[3]
    return {
        "stdlib_roots": (".venv/lib/python3.11",),
        "stdlib_files_sha256": {
            path.relative_to(project_root).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in stdlib_files
        },
        "dependencies": {
            "registered": {
                "files_sha256": {
                    "registered.py": hashlib.sha256(
                        site_record.read_bytes()
                    ).hexdigest(),
                },
            },
        },
    }


def test_conda_python_runtime_replays_duplicate_safe_fake_record(
    tmp_path: Path,
) -> None:
    (
        project_root,
        authority,
        observed_binding,
        record_path,
        registered_files,
    ) = _fake_conda_python_prefix(tmp_path)

    anchor, observed_files = verifier._verify_conda_python_runtime(
        project_root,
        authority=authority,
        observed_binding=observed_binding,
    )
    assert anchor["schema"] == "d2t_rna.conda_python_runtime_anchor.v1"
    assert anchor["record_sha256"] == authority["record_sha256"]
    assert anchor["python_executable_sha256"] == (
        authority["executable_sha256"]
    )
    assert observed_files == registered_files

    original_record = record_path.read_bytes()
    duplicate_record = original_record.replace(
        b"{",
        b'{"name":"duplicate-before-authoritative-name",',
        1,
    )
    record_path.write_bytes(duplicate_record)
    duplicate_authority = {
        **authority,
        "record_sha256": hashlib.sha256(
            duplicate_record
        ).hexdigest(),
    }
    with pytest.raises(ValueError, match="duplicate key 'name'"):
        verifier._verify_conda_python_runtime(
            project_root,
            authority=duplicate_authority,
            observed_binding=observed_binding,
        )

    record_path.write_bytes(original_record + b" ")
    with pytest.raises(ValueError, match="record bytes changed"):
        verifier._verify_conda_python_runtime(
            project_root,
            authority=authority,
            observed_binding=observed_binding,
        )
    record_path.write_bytes(original_record)

    original_record_value = json.loads(original_record)
    for field, replacement in (
        ("version", "3.11.14"),
        ("build", "wrong_build"),
        ("channel", "https://example.invalid/wrong-channel"),
    ):
        mutated_record = dict(original_record_value)
        mutated_record[field] = replacement
        _write_canonical(record_path, mutated_record)
        mutated_authority = {
            **authority,
            "record_sha256": hashlib.sha256(
                record_path.read_bytes()
            ).hexdigest(),
        }
        with pytest.raises(ValueError, match=f"identity changed: {field}"):
            verifier._verify_conda_python_runtime(
                project_root,
                authority=mutated_authority,
                observed_binding=observed_binding,
            )
    record_path.write_bytes(original_record)

    for mutation in ("missing", "extra"):
        mutated_record = json.loads(original_record)
        paths = mutated_record["paths_data"]["paths"]
        files = mutated_record["files"]
        if mutation == "missing":
            paths.pop()
            files.pop()
        else:
            injected = {
                "_path": "lib/python3.11/injected.py",
                "path_type": "hardlink",
                "sha256": "f" * 64,
                "sha256_in_prefix": "f" * 64,
                "size_in_bytes": 1,
            }
            paths.append(injected)
            files.append(injected["_path"])
        _write_canonical(record_path, mutated_record)
        mutated_authority = {
            **authority,
            "record_sha256": hashlib.sha256(
                record_path.read_bytes()
            ).hexdigest(),
        }
        with pytest.raises(ValueError, match="path count changed"):
            verifier._verify_conda_python_runtime(
                project_root,
                authority=mutated_authority,
                observed_binding=observed_binding,
            )
    record_path.write_bytes(original_record)

    wrong_package_authority = {
        **authority,
        "package_sha256": "e" * 64,
    }
    with pytest.raises(ValueError, match="package SHA changed"):
        verifier._verify_conda_python_runtime(
            project_root,
            authority=wrong_package_authority,
            observed_binding=observed_binding,
        )

    changed_binding = {
        **observed_binding,
        "SOABI": "injected-soabi",
    }
    with pytest.raises(ValueError, match="runtime binding changed: SOABI"):
        verifier._verify_conda_python_runtime(
            project_root,
            authority=authority,
            observed_binding=changed_binding,
        )

    python_target = project_root / ".venv" / "bin" / "python3.11"
    python_target.write_bytes(b"tampered executable\n")
    with pytest.raises(ValueError, match="executable bytes changed"):
        verifier._verify_conda_python_runtime(
            project_root,
            authority=authority,
            observed_binding=observed_binding,
        )


def test_conda_python_runtime_rejects_wrong_executable_links(
    tmp_path: Path,
) -> None:
    (
        project_root,
        authority,
        observed_binding,
        _record_path,
        _registered_files,
    ) = _fake_conda_python_prefix(tmp_path)
    python_link = project_root / ".venv" / "bin" / "python"
    python_target = project_root / ".venv" / "bin" / "python3.11"

    python_link.unlink()
    python_link.symlink_to("../bin/python3.11")
    with pytest.raises(ValueError, match="not bound to bin/python3.11"):
        verifier._verify_conda_python_runtime(
            project_root,
            authority=authority,
            observed_binding=observed_binding,
        )

    python_link.unlink()
    python_link.symlink_to("python3.11")
    target_bytes = python_target.read_bytes()
    python_target.unlink()
    outside_target = tmp_path / "outside-python3.11"
    outside_target.write_bytes(target_bytes)
    python_target.symlink_to(outside_target)
    with pytest.raises(ValueError, match="not bound to bin/python3.11"):
        verifier._verify_conda_python_runtime(
            project_root,
            authority=authority,
            observed_binding=observed_binding,
        )


def test_stdlib_tree_must_exactly_match_conda_registry() -> None:
    registered = {
        ".venv/lib/python3.11/os.py": "a" * 64,
        ".venv/lib/python3.11/data.txt": "b" * 64,
    }
    verifier._verify_stdlib_tree_against_conda(
        dict(registered),
        registered,
    )

    changed = dict(registered)
    changed[".venv/lib/python3.11/os.py"] = "c" * 64
    with pytest.raises(ValueError, match="bytes differ"):
        verifier._verify_stdlib_tree_against_conda(changed, registered)

    missing = dict(registered)
    del missing[".venv/lib/python3.11/data.txt"]
    with pytest.raises(ValueError, match="tree differs.*missing"):
        verifier._verify_stdlib_tree_against_conda(missing, registered)

    extra = {
        **registered,
        ".venv/lib/python3.11/injected.py": "d" * 64,
    }
    with pytest.raises(ValueError, match="tree differs.*extra"):
        verifier._verify_stdlib_tree_against_conda(extra, registered)


def test_stdlib_zip_cannot_be_reinserted_into_sys_path(
    tmp_path: Path,
) -> None:
    project_root, _site_packages = _fake_runtime_project(tmp_path)
    verifier._verify_stdlib_zip_not_on_sys_path(
        (str(project_root / ".venv" / "lib" / "python3.11"),),
        project_root=project_root,
    )
    with pytest.raises(ValueError, match="sys.path.*stdlib zip"):
        verifier._verify_stdlib_zip_not_on_sys_path(
            (
                str(project_root / ".venv" / "lib" / "python311.zip"),
                str(project_root / ".venv" / "lib" / "python3.11"),
            ),
            project_root=project_root,
        )


def test_runtime_import_closure_rejects_live_stdlib_registry_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, site_packages = _fake_runtime_project(tmp_path)
    stdlib_root = site_packages.parent
    sentinel = stdlib_root / "sentinel.py"
    sentinel.write_bytes(b"SENTINEL = True\n")
    site_record = site_packages / "registered.py"
    site_record.write_bytes(b"REGISTERED = True\n")
    dependency_snapshot = {
        "stdlib_roots": (".venv/lib/python3.11",),
        "stdlib_files_sha256": {
            ".venv/lib/python3.11/sentinel.py": hashlib.sha256(
                sentinel.read_bytes()
            ).hexdigest(),
        },
        "dependencies": {
            "registered": {
                "files_sha256": {
                    "registered.py": hashlib.sha256(
                        site_record.read_bytes()
                    ).hexdigest(),
                },
            },
        },
    }
    monkeypatch.setattr(
        sys,
        "stdlib_module_names",
        frozenset(
            {
                *verifier._FROZEN_STDLIB_MODULE_NAMES,
                "task4_injected_stdlib_name",
            }
        ),
    )
    with pytest.raises(ValueError, match="registry changed after startup"):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )


def test_sysconfigdata_name_accepts_real_linux_token_and_exact_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert verifier._validate_sysconfigdata_module_name(
        "_sysconfigdata__linux_x86_64-linux-gnu"
    ) == "_sysconfigdata__linux_x86_64-linux-gnu"
    with pytest.raises(RuntimeError, match="not canonical"):
        verifier._validate_sysconfigdata_module_name(
            "_sysconfigdata__linux/x86_64"
        )

    original_name = verifier._FROZEN_SYSCONFIGDATA_MODULE_NAME
    assert type(original_name) is str
    frozen_getter = verifier._FROZEN_SYSCONFIGDATA_NAME_GETTER
    monkeypatch.setattr(
        verifier.sysconfig,
        "_get_sysconfigdata_name",
        lambda: original_name,
    )
    with pytest.raises(ValueError, match="name getter changed"):
        verifier._verify_live_sysconfigdata_module_name()
    monkeypatch.setattr(
        verifier.sysconfig,
        "_get_sysconfigdata_name",
        frozen_getter,
    )

    exact_name = "_sysconfigdata__linux_x86_64-linux-gnu"

    def production_getter() -> str:
        return exact_name

    monkeypatch.setattr(
        verifier.sysconfig,
        "_get_sysconfigdata_name",
        production_getter,
    )
    monkeypatch.setattr(
        verifier,
        "_FROZEN_SYSCONFIGDATA_NAME_GETTER",
        production_getter,
    )
    monkeypatch.setattr(
        verifier,
        "_FROZEN_SYSCONFIGDATA_MODULE_NAME",
        exact_name,
    )

    project_root, site_packages = _fake_runtime_project(tmp_path)
    stdlib_root = site_packages.parent
    exact_path = stdlib_root / f"{exact_name}.py"
    exact_path.write_bytes(b"build_time_vars = {}\n")
    exact_module = _fake_file_module(
        exact_name,
        exact_path,
        native=False,
    )
    wrong_name = "_sysconfigdata__wrong-platform"
    wrong_path = stdlib_root / f"{wrong_name}.py"
    wrong_path.write_bytes(b"build_time_vars = {}\n")
    dependency_snapshot = _fake_closure_dependency_snapshot(
        site_packages,
        (exact_path, wrong_path),
    )
    _scan_only_runtime_modules(
        monkeypatch,
        exact_name,
        wrong_name,
    )
    monkeypatch.setitem(sys.modules, exact_name, exact_module)

    _verify_runtime_import_closure(
        project_root,
        {},
        dependency_snapshot=dependency_snapshot,
        stdlib_roots=(stdlib_root,),
    )

    wrong_module = _fake_file_module(
        wrong_name,
        wrong_path,
        native=False,
    )
    monkeypatch.setitem(sys.modules, wrong_name, wrong_module)
    with pytest.raises(ValueError, match="unexpected sysconfig-data"):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )


def test_stdlib_module_and_package_search_locations_are_exact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, site_packages = _fake_runtime_project(tmp_path)
    stdlib_root = site_packages.parent
    module_path = stdlib_root / "sched.py"
    module_path.write_bytes(b"VALUE = 1\n")
    package_path = stdlib_root / "wsgiref" / "__init__.py"
    package_path.parent.mkdir()
    package_path.write_bytes(b"VALUE = 2\n")
    dependency_snapshot = _fake_closure_dependency_snapshot(
        site_packages,
        (module_path, package_path),
    )
    module = _fake_file_module(
        "sched",
        module_path,
        native=False,
    )
    package = _fake_file_module(
        "wsgiref",
        package_path,
        native=False,
        package=True,
    )
    monkeypatch.setitem(sys.modules, "sched", module)
    monkeypatch.setitem(sys.modules, "wsgiref", package)
    _scan_only_runtime_modules(monkeypatch, "sched", "wsgiref")

    _verify_runtime_import_closure(
        project_root,
        {},
        dependency_snapshot=dependency_snapshot,
        stdlib_roots=(stdlib_root,),
    )

    module.__spec__.submodule_search_locations = [str(stdlib_root)]
    with pytest.raises(ValueError, match="gained package search paths"):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )
    module.__spec__.submodule_search_locations = None

    original_package_locations = package.__path__
    outside = tmp_path / "outside-package"
    outside.mkdir()
    package.__spec__.submodule_search_locations = [str(outside)]
    with pytest.raises(ValueError, match="external or non-canonical"):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )
    package.__spec__.submodule_search_locations = original_package_locations


@pytest.mark.parametrize(
    "file_kind",
    ("python", "native", "bytecode", "unknown"),
)
def test_runtime_import_closure_rejects_external_file_backed_modules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    file_kind: str,
) -> None:
    project_root, site_packages = _fake_runtime_project(tmp_path)
    stdlib_root = site_packages.parent
    sentinel = stdlib_root / "sentinel.py"
    sentinel.write_bytes(b"SENTINEL = True\n")
    dependency_snapshot = _fake_closure_dependency_snapshot(
        site_packages,
        (sentinel,),
    )
    if file_kind == "native":
        external_path = tmp_path / (
            "external" + importlib.machinery.EXTENSION_SUFFIXES[0]
        )
    elif file_kind == "bytecode":
        external_path = tmp_path / "external.pyc"
    elif file_kind == "unknown":
        external_path = tmp_path / "external.module-data"
    else:
        external_path = tmp_path / "external.py"
    external_path.write_bytes(b"untrusted external module bytes")
    module_name = f"task4_external_{file_kind}"
    external_module = ModuleType(module_name)
    external_module.__file__ = str(external_path)
    monkeypatch.setitem(sys.modules, module_name, external_module)
    _scan_only_runtime_modules(monkeypatch, module_name)

    with pytest.raises(ValueError, match="external"):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )


def test_registered_and_unknown_pathless_modules_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, site_packages = _fake_runtime_project(tmp_path)
    stdlib_root = site_packages.parent
    sentinel = stdlib_root / "sentinel.py"
    sentinel.write_bytes(b"SENTINEL = True\n")
    dependency_snapshot = _fake_closure_dependency_snapshot(
        site_packages,
        (sentinel,),
    )

    namespace_spec = importlib.machinery.PathFinder.find_spec(
        "scripts",
        [str(project_root)],
    )
    assert namespace_spec is not None
    scripts_namespace = importlib.util.module_from_spec(namespace_spec)
    monkeypatch.setitem(sys.modules, "scripts", scripts_namespace)
    _scan_only_runtime_modules(
        monkeypatch,
        "scripts",
        "task4_unknown_pathless",
    )
    _verify_runtime_import_closure(
        project_root,
        {},
        dependency_snapshot=dependency_snapshot,
        stdlib_roots=(stdlib_root,),
    )

    unknown = ModuleType("task4_unknown_pathless")
    monkeypatch.setitem(sys.modules, "task4_unknown_pathless", unknown)
    with pytest.raises(ValueError, match="unregistered pathless"):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )


def test_pyexpat_pathless_children_require_verified_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, site_packages = _fake_runtime_project(tmp_path)
    stdlib_root = site_packages.parent
    dynload = stdlib_root / "lib-dynload"
    dynload.mkdir()
    parent_path = dynload / (
        "pyexpat" + importlib.machinery.EXTENSION_SUFFIXES[0]
    )
    parent_path.write_bytes(b"fake record-backed pyexpat bytes")
    dependency_snapshot = _fake_closure_dependency_snapshot(
        site_packages,
        (parent_path,),
    )
    parent = _fake_file_module(
        "pyexpat",
        parent_path,
        native=True,
    )
    errors = ModuleType("pyexpat.errors")
    model = ModuleType("pyexpat.model")
    parent.errors = errors
    parent.model = model
    monkeypatch.setitem(sys.modules, "pyexpat", parent)
    monkeypatch.setitem(sys.modules, "pyexpat.errors", errors)
    monkeypatch.setitem(sys.modules, "pyexpat.model", model)
    _scan_only_runtime_modules(
        monkeypatch,
        "pyexpat",
        "pyexpat.errors",
        "pyexpat.model",
    )

    _verify_runtime_import_closure(
        project_root,
        {},
        dependency_snapshot=dependency_snapshot,
        stdlib_roots=(stdlib_root,),
    )

    forged = ModuleType("pyexpat.errors")
    monkeypatch.setitem(sys.modules, "pyexpat.errors", forged)
    with pytest.raises(ValueError, match="CPython child identity changed"):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )


def test_typing_pathless_alias_requires_preimport_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, site_packages = _fake_runtime_project(tmp_path)
    stdlib_root = site_packages.parent
    typing_path = stdlib_root / "typing.py"
    typing_path.write_bytes(b"VALUE = 1\n")
    dependency_snapshot = _fake_closure_dependency_snapshot(
        site_packages,
        (typing_path,),
    )
    parent = _fake_file_module(
        "typing",
        typing_path,
        native=False,
    )
    alias = object()
    parent.io = alias
    monkeypatch.setattr(verifier, "stdlib_typing", parent)
    monkeypatch.setattr(verifier, "_FROZEN_TYPING_MODULE", parent)
    monkeypatch.setattr(
        verifier,
        "_FROZEN_TYPING_PATHLESS_ALIASES",
        {"typing.io": alias},
    )
    monkeypatch.setitem(sys.modules, "typing", parent)
    monkeypatch.setitem(sys.modules, "typing.io", alias)
    _scan_only_runtime_modules(monkeypatch, "typing", "typing.io")

    _verify_runtime_import_closure(
        project_root,
        {},
        dependency_snapshot=dependency_snapshot,
        stdlib_roots=(stdlib_root,),
    )

    monkeypatch.setitem(sys.modules, "typing.io", object())
    with pytest.raises(
        ValueError,
        match="pathless typing alias identity changed",
    ):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )


def test_runtime_import_closure_allows_verified_site_python_and_native(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _scan_only_runtime_modules(
        monkeypatch,
        "task4_test_site_python",
        "task4_test_site_native",
        "task4_test_site_shadow",
        "task4_test_project_native",
    )
    project_root, site_packages = _fake_runtime_project(tmp_path)
    stdlib_root = site_packages.parent
    stdlib_sentinel = stdlib_root / "os.py"
    stdlib_sentinel.write_text("NAME = 'os'\n", encoding="utf-8")
    site_python = site_packages / "third_party.py"
    site_python.write_text("VALUE = 1\n", encoding="utf-8")
    site_native = site_packages / (
        "third_party" + importlib.machinery.EXTENSION_SUFFIXES[0]
    )
    site_native.write_bytes(b"registered native bytes")
    python_module = ModuleType("task4_test_site_python")
    python_module.__file__ = str(site_python)
    native_module = ModuleType("task4_test_site_native")
    native_module.__file__ = str(site_native)
    monkeypatch.setitem(
        sys.modules,
        "task4_test_site_python",
        python_module,
    )
    monkeypatch.setitem(
        sys.modules,
        "task4_test_site_native",
        native_module,
    )
    dependency_snapshot = {
        "stdlib_roots": (".venv/lib/python3.11",),
        "stdlib_files_sha256": {
            ".venv/lib/python3.11/os.py": hashlib.sha256(
                stdlib_sentinel.read_bytes()
            ).hexdigest(),
        },
        "dependencies": {
            "registered_test_dependency": {
                "files_sha256": {
                    "third_party.py": hashlib.sha256(
                        site_python.read_bytes()
                    ).hexdigest(),
                    site_native.name: hashlib.sha256(
                        site_native.read_bytes()
                    ).hexdigest(),
                }
            }
        }
    }

    _verify_runtime_import_closure(
        project_root,
        {},
        dependency_snapshot=dependency_snapshot,
        stdlib_roots=(stdlib_root,),
    )

    unregistered_shadow = site_packages / "pytest.py"
    unregistered_shadow.write_text(
        "raise RuntimeError('shadowed pytest')\n",
        encoding="utf-8",
    )
    shadow_module = ModuleType("task4_test_site_shadow")
    shadow_module.__file__ = str(unregistered_shadow)
    monkeypatch.setitem(
        sys.modules,
        "task4_test_site_shadow",
        shadow_module,
    )
    with pytest.raises(ValueError, match="unfingerprinted"):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )
    monkeypatch.delitem(sys.modules, "task4_test_site_shadow")

    project_package = project_root / "src" / "d2t_rna"
    project_package.mkdir()
    project_native = project_package / (
        "injected" + importlib.machinery.EXTENSION_SUFFIXES[0]
    )
    project_native.write_bytes(b"unregistered native bytes")
    injected = ModuleType("task4_test_project_native")
    injected.__file__ = str(project_native)
    monkeypatch.setitem(
        sys.modules,
        "task4_test_project_native",
        injected,
    )
    with pytest.raises(ValueError, match="project native extension"):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )


def test_runtime_import_closure_binds_venv_lib_dynload_native(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _scan_only_runtime_modules(
        monkeypatch,
        "_typing",
        "task4_not_stdlib",
    )
    project_root, site_packages = _fake_runtime_project(tmp_path)
    stdlib_root = site_packages.parent
    lib_dynload = stdlib_root / "lib-dynload"
    lib_dynload.mkdir()
    typing_native = lib_dynload / (
        "_typing" + importlib.machinery.EXTENSION_SUFFIXES[0]
    )
    typing_native.write_bytes(b"trusted _typing native bytes")
    site_record = site_packages / "registered.py"
    site_record.write_text("VALUE = 1\n", encoding="utf-8")
    dependency_snapshot = {
        "stdlib_roots": (".venv/lib/python3.11",),
        "stdlib_files_sha256": {
            (
                ".venv/lib/python3.11/lib-dynload/"
                f"{typing_native.name}"
            ): hashlib.sha256(typing_native.read_bytes()).hexdigest(),
        },
        "dependencies": {
            "registered_test_dependency": {
                "files_sha256": {
                    "registered.py": hashlib.sha256(
                        site_record.read_bytes()
                    ).hexdigest(),
                }
            }
        },
    }
    typing_module = _fake_file_module(
        "_typing",
        typing_native,
        native=True,
    )
    monkeypatch.setitem(sys.modules, "_typing", typing_module)

    _verify_runtime_import_closure(
        project_root,
        {},
        dependency_snapshot=dependency_snapshot,
        stdlib_roots=(stdlib_root,),
    )

    typing_module.__name__ = "typing"
    with pytest.raises(ValueError, match="loader/spec"):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )
    typing_module.__name__ = "_typing"

    monkeypatch.setattr(
        verifier,
        "_FROZEN_STDLIB_NATIVE_MODULE_DEFINITION_NAMES",
        MappingProxyType(
            {
                **verifier._FROZEN_STDLIB_NATIVE_MODULE_DEFINITION_NAMES,
                "_typing": "typing",
            }
        ),
    )
    typing_module.__name__ = "typing"
    _verify_runtime_import_closure(
        project_root,
        {},
        dependency_snapshot=dependency_snapshot,
        stdlib_roots=(stdlib_root,),
    )
    typing_module.__name__ = "tampered-typing"
    with pytest.raises(ValueError, match="loader/spec"):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )
    typing_module.__name__ = "typing"

    genuine_loader = typing_module.__loader__
    typing_module.__loader__ = importlib.machinery.SourceFileLoader(
        "_typing",
        str(typing_native),
    )
    with pytest.raises(ValueError, match="loader/spec"):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )
    typing_module.__loader__ = genuine_loader

    genuine_spec = typing_module.__spec__
    spoof_native = lib_dynload / (
        "_typing_spoof" + importlib.machinery.EXTENSION_SUFFIXES[0]
    )
    spoof_native.write_bytes(b"spoof native bytes")
    spoof_loader = importlib.machinery.ExtensionFileLoader(
        "_typing",
        str(spoof_native),
    )
    spoof_spec = importlib.util.spec_from_file_location(
        "_typing",
        spoof_native,
        loader=spoof_loader,
    )
    assert spoof_spec is not None
    typing_module.__loader__ = spoof_loader
    typing_module.__spec__ = spoof_spec
    with pytest.raises(ValueError, match="origin/path changed"):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )
    typing_module.__loader__ = genuine_loader
    typing_module.__spec__ = genuine_spec

    typing_native.write_bytes(b"mutated _typing native bytes")
    with pytest.raises(ValueError, match="stdlib.*bytes|bytes differ"):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )
    typing_native.write_bytes(b"trusted _typing native bytes")

    unregistered_native = lib_dynload / (
        "task4_not_stdlib"
        + importlib.machinery.EXTENSION_SUFFIXES[0]
    )
    unregistered_native.write_bytes(b"unregistered native bytes")
    unregistered_module = _fake_file_module(
        "task4_not_stdlib",
        unregistered_native,
        native=True,
    )
    monkeypatch.setitem(
        sys.modules,
        "task4_not_stdlib",
        unregistered_module,
    )
    with pytest.raises(ValueError, match="unfingerprinted"):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )
    unregistered_label = (
        ".venv/lib/python3.11/lib-dynload/"
        f"{unregistered_native.name}"
    )
    dependency_snapshot["stdlib_files_sha256"][
        unregistered_label
    ] = hashlib.sha256(unregistered_native.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="unregistered module name"):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )
    del dependency_snapshot["stdlib_files_sha256"][unregistered_label]
    monkeypatch.delitem(sys.modules, "task4_not_stdlib")

    outside_native = tmp_path / (
        "_decimal" + importlib.machinery.EXTENSION_SUFFIXES[0]
    )
    outside_native.write_bytes(b"outside native bytes")
    linked_native = lib_dynload / outside_native.name
    linked_native.symlink_to(outside_native)
    linked_module = _fake_file_module(
        "_decimal",
        linked_native,
        native=True,
    )
    _scan_only_runtime_modules(
        monkeypatch,
        "_typing",
        "_decimal",
    )
    monkeypatch.setitem(sys.modules, "_decimal", linked_module)
    with pytest.raises(ValueError, match="symlinked standard-library"):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )


def test_runtime_import_closure_rejects_builtin_loader_spoof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _scan_only_runtime_modules(
        monkeypatch,
        "task4_spoof_builtin",
    )
    project_root, site_packages = _fake_runtime_project(tmp_path)
    stdlib_root = site_packages.parent
    stdlib_file = stdlib_root / "os.py"
    stdlib_file.write_text("NAME = 'os'\n", encoding="utf-8")
    site_record = site_packages / "registered.py"
    site_record.write_text("VALUE = 1\n", encoding="utf-8")
    dependency_snapshot = {
        "stdlib_roots": (".venv/lib/python3.11",),
        "stdlib_files_sha256": {
            ".venv/lib/python3.11/os.py": hashlib.sha256(
                stdlib_file.read_bytes()
            ).hexdigest(),
        },
        "dependencies": {
            "registered_test_dependency": {
                "files_sha256": {
                    "registered.py": hashlib.sha256(
                        site_record.read_bytes()
                    ).hexdigest(),
                }
            }
        },
    }
    spoof = ModuleType("task4_spoof_builtin")
    spoof_loader = importlib.machinery.SourceFileLoader(
        "sys",
        str(stdlib_file),
    )
    spoof_spec = importlib.machinery.ModuleSpec(
        "sys",
        spoof_loader,
        origin="built-in",
    )
    spoof.__loader__ = spoof_loader
    spoof.__spec__ = spoof_spec
    monkeypatch.setitem(
        sys.modules,
        "task4_spoof_builtin",
        spoof,
    )

    with pytest.raises(ValueError, match="built-in/frozen"):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )

    exact_loader_spoof = ModuleType("sys")
    exact_loader_spoof.__loader__ = importlib.machinery.BuiltinImporter
    exact_loader_spoof.__spec__ = importlib.machinery.ModuleSpec(
        "sys",
        importlib.machinery.BuiltinImporter,
        origin="built-in",
    )
    monkeypatch.setitem(
        sys.modules,
        "task4_spoof_builtin",
        exact_loader_spoof,
    )
    with pytest.raises(ValueError, match="built-in/frozen"):
        _verify_runtime_import_closure(
            project_root,
            {},
            dependency_snapshot=dependency_snapshot,
            stdlib_roots=(stdlib_root,),
        )


def test_runtime_dependency_snapshot_binds_files_and_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, site_packages = _fake_runtime_project(tmp_path)
    stdlib_root = site_packages.parent
    stdlib_file = stdlib_root / "os.py"
    stdlib_file.write_text("NAME = 'os'\n", encoding="utf-8")
    stdlib_data = stdlib_root / "stdlib-data.txt"
    stdlib_data.write_text("registered data\n", encoding="utf-8")
    (stdlib_root / "legacy.pyc").write_bytes(b"excluded bytecode")
    pycache = stdlib_root / "__pycache__"
    pycache.mkdir()
    (pycache / "os.cpython-311.pyc").write_bytes(
        b"excluded cache bytecode"
    )
    monkeypatch.setattr(
        verifier,
        "_verified_runtime_stdlib_roots",
        lambda: (stdlib_root,),
    )
    registered_stdlib_files = {
        ".venv/lib/python3.11/os.py": hashlib.sha256(
            stdlib_file.read_bytes()
        ).hexdigest(),
        ".venv/lib/python3.11/stdlib-data.txt": hashlib.sha256(
            stdlib_data.read_bytes()
        ).hexdigest(),
    }
    fake_conda_anchor = {
        "schema": "d2t_rna.conda_python_runtime_anchor.v1",
        "record_sha256": "a" * 64,
    }
    monkeypatch.setattr(
        verifier,
        "_verify_conda_python_runtime",
        lambda project_root: (
            fake_conda_anchor,
            registered_stdlib_files,
        ),
    )
    executable = tmp_path / "python3.11"
    executable.write_bytes(b"python executable v1")
    monkeypatch.setattr(sys, "executable", str(executable))

    registered_names = {
        snapshot_name
        for snapshot_name, _ in verifier.RUNTIME_DISTRIBUTIONS
    }
    assert {
        "hypothesis",
        "pygments",
        "sortedcontainers",
    }.issubset(registered_names)
    assert "attrs" not in registered_names

    versions: dict[str, str] = {}
    records: dict[str, tuple[Path, ...]] = {}
    for index, (_, distribution_name) in enumerate(
        verifier.RUNTIME_DISTRIBUTIONS,
        start=1,
    ):
        versions[distribution_name] = f"{index}.0"
        module_file = (
            site_packages
            / distribution_name.replace("-", "_")
            / "__init__.py"
        )
        module_file.parent.mkdir()
        module_file.write_text(
            f"VERSION = {index!r}\n",
            encoding="utf-8",
        )
        entries = [module_file.relative_to(site_packages)]
        if distribution_name == "pytest":
            entries.append(Path("../../../bin/pytest"))
        records[distribution_name] = tuple(entries)

    class FakeDistribution:
        def __init__(self, name: str) -> None:
            self.version = versions[name]
            self.files = records[name]

        def locate_file(self, path: Path) -> Path:
            return site_packages / path

    monkeypatch.setattr(
        verifier.importlib_metadata,
        "distribution",
        lambda name: FakeDistribution(name),
    )

    first = runtime_dependency_snapshot_sha256(project_root)
    snapshot = _runtime_dependency_snapshot(project_root)
    assert len(first) == 64
    assert snapshot["schema"] == (
        "d2t_rna.task4_runtime_dependency_snapshot.v3"
    )
    assert snapshot["conda_python_runtime"] == fake_conda_anchor
    assert snapshot["python_executable_sha256"] == hashlib.sha256(
        executable.read_bytes()
    ).hexdigest()
    assert snapshot["stdlib_zip"] == {
        "path": ".venv/lib/python311.zip",
        "status": "ABSENT",
    }
    assert snapshot["sysconfigdata_module_name"] == (
        verifier._FROZEN_SYSCONFIGDATA_MODULE_NAME
    )
    assert snapshot["typing_pathless_aliases"] == tuple(
        sorted(verifier._FROZEN_TYPING_PATHLESS_ALIASES)
    )
    assert snapshot["stdlib_roots"] == (".venv/lib/python3.11",)
    assert snapshot["stdlib_files_sha256"] == {
        ".venv/lib/python3.11/os.py": hashlib.sha256(
            stdlib_file.read_bytes()
        ).hexdigest(),
        ".venv/lib/python3.11/stdlib-data.txt": hashlib.sha256(
            stdlib_data.read_bytes()
        ).hexdigest(),
    }
    assert (
        "../../../bin/pytest"
        not in snapshot["dependencies"]["pytest"]["files_sha256"]
    )

    stdlib_data.write_text("changed data\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Conda record"):
        runtime_dependency_snapshot_sha256(project_root)
    stdlib_data.write_text("registered data\n", encoding="utf-8")

    stdlib_zip = project_root / ".venv" / "lib" / "python311.zip"
    stdlib_zip.write_bytes(b"late-created unauthorized zip")
    with pytest.raises(ValueError, match="unauthorized stdlib zip"):
        runtime_dependency_snapshot_sha256(project_root)
    stdlib_zip.unlink()

    outside_stdlib = tmp_path / "outside-stdlib.py"
    outside_stdlib.write_text("VALUE = 1\n", encoding="utf-8")
    linked_stdlib = stdlib_root / "linked-stdlib.py"
    linked_stdlib.symlink_to(outside_stdlib)
    with pytest.raises(
        ValueError,
        match="trusted stdlib tree contains a symlink",
    ):
        runtime_dependency_snapshot_sha256(project_root)
    linked_stdlib.unlink()

    pydantic_file = (
        site_packages / "pydantic" / "__init__.py"
    )
    pydantic_file.write_text("VERSION = 'changed'\n", encoding="utf-8")
    second = runtime_dependency_snapshot_sha256(project_root)
    assert second != first

    pydantic_file.unlink()
    outside = tmp_path / "outside.py"
    outside.write_text("VALUE = 1\n", encoding="utf-8")
    pydantic_file.symlink_to(outside)
    with pytest.raises(ValueError, match="traverses a symlink"):
        runtime_dependency_snapshot_sha256(project_root)


def test_root_conftest_is_rejected_before_isolation_audit(
    tmp_path: Path,
) -> None:
    (tmp_path / "conftest.py").write_text("", encoding="utf-8")
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    with pytest.raises(ValueError, match="unregistered execution inputs"):
        _verify_python_process_isolation(tmp_path, artifact_root)


@pytest.mark.parametrize(
    "mutation",
    ("between", "after", "duplicate", "nonexistent", "symlink"),
)
def test_python_process_isolation_requires_exact_sys_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    project_root = tmp_path / "project"
    source_root = project_root / "src"
    site_packages = (
        project_root
        / ".venv"
        / "lib"
        / "python3.11"
        / "site-packages"
    )
    source_root.mkdir(parents=True)
    site_packages.mkdir(parents=True)

    stdlib_root = tmp_path / "interpreter" / "lib" / "python3.11"
    dynload_root = stdlib_root / "lib-dynload"
    dynload_root.mkdir(parents=True)
    injected = tmp_path / "injected"
    injected.mkdir()
    injected_link = tmp_path / "injected-link"
    injected_link.symlink_to(injected, target_is_directory=True)

    artifact_root = tmp_path / "artifacts"
    pycache_prefix = artifact_root / "runs" / "unit" / "pycache"
    pycache_prefix.mkdir(parents=True)

    monkeypatch.setattr(
        verifier,
        "_validate_project_root_import_surface",
        lambda _root: None,
    )
    monkeypatch.setattr(
        verifier,
        "_verify_runtime_isolation_flags",
        lambda _flags: None,
    )
    monkeypatch.setattr(
        verifier,
        "_verified_site_packages_path",
        lambda _root: site_packages,
    )
    monkeypatch.setattr(
        verifier.sysconfig,
        "get_paths",
        lambda: {
            "stdlib": str(stdlib_root),
            "platstdlib": str(stdlib_root),
        },
    )
    monkeypatch.setattr(sys, "pycache_prefix", str(pycache_prefix))
    for name in tuple(verifier.os.environ):
        if (
            name.startswith(("PYTHON", "_PYTHON"))
            or name in {"PYTEST_ADDOPTS", "PYTEST_PLUGINS"}
        ):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")

    exact = [
        str(stdlib_root),
        str(dynload_root),
        str(site_packages),
        str(source_root),
        str(project_root),
    ]
    monkeypatch.setattr(sys, "path", list(exact))
    _verify_python_process_isolation(project_root, artifact_root)

    if mutation == "between":
        observed = [*exact[:3], str(injected), *exact[3:]]
    elif mutation == "after":
        observed = [*exact, str(injected)]
    elif mutation == "duplicate":
        observed = [*exact, str(stdlib_root)]
    elif mutation == "nonexistent":
        observed = [*exact, str(tmp_path / "missing")]
    else:
        observed = [*exact, str(injected_link)]
    monkeypatch.setattr(sys, "path", observed)
    with pytest.raises(ValueError, match=r"sys\.path"):
        _verify_python_process_isolation(project_root, artifact_root)


@pytest.mark.slow
def test_fixture_requires_live_byte_identical_rebuild(
    tmp_path: Path,
) -> None:
    manifest_path = _build_registered_fixture(
        tmp_path,
        name="registered",
    )
    _verify_fixture(
        manifest_path,
        acceptance_record=ACCEPTANCE_FLAGS,
        project_root=PROJECT_ROOT,
        artifact_root=tmp_path,
        live_run_dir=_live_run_dir(tmp_path),
    )

    mass_path = manifest_path.parent / "probability_mass_audits.json"
    mass_audits = json.loads(mass_path.read_text(encoding="utf-8"))
    mass_audits[0]["enumeration_trace_hash"] = "f" * 64
    _write_canonical(mass_path, mass_audits)

    fixture = json.loads(manifest_path.read_text(encoding="utf-8"))
    fixture["artifacts_sha256"][
        "probability_mass_audits.json"
    ] = hashlib.sha256(mass_path.read_bytes()).hexdigest()
    _write_canonical(manifest_path, fixture)

    with pytest.raises(ValueError, match="live rebuild differs"):
        _verify_fixture(
            manifest_path,
            acceptance_record=ACCEPTANCE_FLAGS,
            project_root=PROJECT_ROOT,
            artifact_root=tmp_path,
            live_run_dir=_live_run_dir(tmp_path),
        )


def test_forged_outer_success_literal_is_rejected(
    tmp_path: Path,
) -> None:
    manifest_path = _build_registered_fixture(
        tmp_path,
        name="registered-outer",
    )
    outer_path = manifest_path.parent / "outer_assessment.json"
    outer = json.loads(outer_path.read_text(encoding="utf-8"))
    outer["inclusion_verified"] = False
    _write_canonical(outer_path, outer)

    fixture = json.loads(manifest_path.read_text(encoding="utf-8"))
    fixture["outer_assessment_hash"] = canonical_sha256(outer)
    fixture["artifacts_sha256"][
        "outer_assessment.json"
    ] = hashlib.sha256(outer_path.read_bytes()).hexdigest()
    _write_canonical(manifest_path, fixture)

    with pytest.raises(ValidationError):
        _verify_fixture(
            manifest_path,
            acceptance_record=ACCEPTANCE_FLAGS,
            project_root=PROJECT_ROOT,
            artifact_root=tmp_path,
            live_run_dir=_live_run_dir(tmp_path),
        )


def test_live_rebuild_directory_cannot_escape_or_be_a_symlink(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    manifest_path = _build_registered_fixture(
        artifact_root,
        name="registered-path-gate",
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(ValueError, match="escaped"):
        _verify_fixture(
            manifest_path,
            acceptance_record=ACCEPTANCE_FLAGS,
            project_root=PROJECT_ROOT,
            artifact_root=artifact_root,
            live_run_dir=outside,
        )

    inside = _live_run_dir(artifact_root)
    linked = artifact_root / "linked-run"
    linked.symlink_to(inside, target_is_directory=True)
    with pytest.raises(ValueError, match="non-symlink"):
        _verify_fixture(
            manifest_path,
            acceptance_record=ACCEPTANCE_FLAGS,
            project_root=PROJECT_ROOT,
            artifact_root=artifact_root,
            live_run_dir=linked,
        )


def test_noncanonical_json_and_fabricated_summary_log_fail_closed(
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_bytes(b'{"a":1,"a":1}\n')
    with pytest.raises(DuplicateJsonKeyError):
        _canonical_load(
            duplicate,
            label="duplicate fixture",
            expected_type=dict,
        )

    run_id = "task4-acceptance-20260730T010203+0800"
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True)
    log_path = run_dir / "run.log"
    log_path.write_text(
        "55 passed in 1.00s\n"
        "185 passed in 2.00s\n"
        "300 passed in 3.00s\n"
        "CPython 3.11.15\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="runner header"):
        _verify_test_log(
            log_path,
            run_id=run_id,
            runtime={
                "implementation": "CPython",
                "python_version": "3.11.15",
            },
            fixture_manifest_sha256="a" * 64,
            source_index_sha256="c" * 64,
            expected_counts=(55, 185, 300),
            artifact_root=tmp_path,
        )


def test_external_evidence_paths_reject_lexical_aliases(
    tmp_path: Path,
) -> None:
    run_id = "task4-acceptance-20260730T010203+0800"
    expected = tmp_path / "runs" / run_id / "run.log"
    expected.parent.mkdir(parents=True)
    expected.write_text("registered\n", encoding="utf-8")

    _verify_exact_external_path_binding(
        {"path": str(expected), "sha256": "a" * 64},
        expected.resolve(),
        expected_path=expected,
        artifact_root=tmp_path,
        label="Task 4 candidate run log",
    )

    lexical_aliases = (
        str(expected.parent / "subdirectory" / ".." / "run.log"),
        f"{expected.parent}/./run.log",
    )
    for lexical_alias in lexical_aliases:
        with pytest.raises(ValueError, match="path changed"):
            _verify_exact_external_path_binding(
                {"path": lexical_alias, "sha256": "a" * 64},
                expected.resolve(),
                expected_path=expected,
                artifact_root=tmp_path,
                label="Task 4 candidate run log",
            )
