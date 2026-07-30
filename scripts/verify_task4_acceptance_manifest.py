#!/usr/bin/env python3
"""Executable, fail-closed verifier for Task 4 acceptance evidence."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import importlib.machinery
import importlib.metadata as importlib_metadata
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import sys
import sysconfig
import tempfile
import typing as stdlib_typing
from types import MappingProxyType, ModuleType
from xml.etree import ElementTree


def _stdlib_module_names_sha256(names: frozenset[str]) -> str:
    """Hash a CPython stdlib-name registry with an unambiguous encoding."""

    return hashlib.sha256(
        ("\n".join(sorted(names)) + "\n").encode("utf-8")
    ).hexdigest()


def _validate_sysconfigdata_module_name(name: object) -> str:
    """Validate CPython's platform-token syntax without requiring an identifier."""

    if (
        type(name) is not str
        or re.fullmatch(
            r"_sysconfigdata__[A-Za-z0-9_-]+",
            name,
        )
        is None
    ):
        raise RuntimeError(
            "Task 4 sysconfig-data module name is not canonical"
        )
    return name


def _current_sysconfigdata_module_name() -> str | None:
    """Return CPython's one generated sysconfig-data module name, if any."""

    getter = getattr(sysconfig, "_get_sysconfigdata_name", None)
    if getter is None:
        return None
    if not callable(getter):
        raise RuntimeError(
            "Task 4 sysconfig-data name getter is not callable"
        )
    return _validate_sysconfigdata_module_name(getter())


def _freeze_typing_pathless_aliases() -> dict[str, object]:
    """Freeze CPython 3.11 typing pseudo-modules before third-party imports."""

    aliases: dict[str, object] = {}
    for name, attribute in (
        ("typing.io", "io"),
        ("typing.re", "re"),
    ):
        module_entry = sys.modules.get(name)
        attribute_value = getattr(stdlib_typing, attribute, None)
        if module_entry is None and attribute_value is None:
            continue
        if module_entry is None or module_entry is not attribute_value:
            raise RuntimeError(
                f"Task 4 typing pathless alias is inconsistent: {name}"
            )
        aliases[name] = module_entry
    return aliases


def _freeze_loaded_stdlib_native_module_definition_names(
) -> MappingProxyType:
    """Freeze genuine extension definition names before target execution.

    A CPython extension's ``PyModuleDef.m_name`` can legitimately differ from
    its import key and ``ModuleSpec.name``.  For example, the registered
    ``_decimal`` extension exposes ``__name__ == "decimal"``.  Bind any
    already-loaded stdlib extension to the exact startup value; extensions
    loaded later must use their import name.
    """

    frozen: dict[str, str] = {}
    for module_key, module in tuple(sys.modules.items()):
        spec = getattr(module, "__spec__", None)
        loader = getattr(spec, "loader", None)
        if type(loader) is not importlib.machinery.ExtensionFileLoader:
            continue
        spec_name = getattr(spec, "name", None)
        if (
            type(module_key) is not str
            or type(spec_name) is not str
            or module_key != spec_name
            or spec_name.partition(".")[0]
            not in _FROZEN_STDLIB_MODULE_NAMES
            or sys.modules.get(spec_name) is not module
        ):
            continue
        definition_name = getattr(module, "__name__", None)
        if type(definition_name) is not str or not definition_name:
            raise RuntimeError(
                "Task 4 loaded stdlib extension has no module definition name"
            )
        prior = frozen.setdefault(spec_name, definition_name)
        if prior != definition_name:
            raise RuntimeError(
                "Task 4 loaded stdlib extension definition name is ambiguous"
            )
    return MappingProxyType(frozen)


if (
    type(getattr(sys, "stdlib_module_names", None)) is not frozenset
    or any(
        type(name) is not str or not name
        for name in sys.stdlib_module_names
    )
):
    raise RuntimeError(
        "Task 4 requires an immutable CPython stdlib module-name registry"
    )
_FROZEN_STDLIB_MODULE_NAMES = sys.stdlib_module_names
_FROZEN_STDLIB_MODULE_NAMES_SHA256 = _stdlib_module_names_sha256(
    _FROZEN_STDLIB_MODULE_NAMES
)
_FROZEN_SYSCONFIGDATA_MODULE_NAME = (
    _current_sysconfigdata_module_name()
)
_FROZEN_SYSCONFIGDATA_NAME_GETTER = getattr(
    sysconfig,
    "_get_sysconfigdata_name",
    None,
)
_FROZEN_TYPING_MODULE = stdlib_typing
_FROZEN_TYPING_PATHLESS_ALIASES = MappingProxyType(
    _freeze_typing_pathless_aliases()
)

import pydantic

from d2t_rna.contracts.base import (
    canonical_json_bytes,
    canonical_sha256,
    parse_contract_json,
    strict_revalidate_contract_model,
    validate_contract_json_syntax,
)
from d2t_rna.exact import (
    ExactSyntheticCoverageReplayCredential,
    ExactSyntheticCoverageReport,
    OuterApproximationAssessment,
    OuterApproximationReplayCredential,
    ProbabilityMassAudit,
    confidence_module_sha256,
    coverage_module_sha256,
)
from scripts.build_task4_acceptance_fixture import build_fixture
from scripts.task4_isolated_python import (
    IsolationViolation,
    _explicit_project_paths,
    _has_symlink_component,
    _trusted_interpreter_paths,
    _validate_project_root_import_surface,
)

_FROZEN_STDLIB_NATIVE_MODULE_DEFINITION_NAMES = (
    _freeze_loaded_stdlib_native_module_definition_names()
)


CONTRACT_SHA256 = (
    "87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d"
)
COMMIT_TITLE = "feat(exact): add exhaustive risk and coverage verification"
ARTIFACT_ROOT = Path("/mnt/cunyuliu/d2t-rna/artifacts")
TASK3_ACCEPTANCE_COMMIT = "5f3a0301fb0051fcee173a08c98677bc1ea20ec5"
TASK3_CLOSURE_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task3-acceptance-recovery-20260730T011748p0800/closure.json"
)
TASK3_CLOSURE_SHA256 = (
    "60353d49876cc87217d983dd97a7bbd872b2ea3bd96396d74bd49402626c21de"
)
TASK4_ENTRY_GATE_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/gates/"
    "task4-entry-gate-open-20260730T012421p0800.json"
)
TASK4_ENTRY_GATE_SHA256 = (
    "afb3582a5dcb4fd6c06505068299731687c4a2ab5d401d1d008d61103283a28d"
)
TASK4_RED_RECORD_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task4-red-20260730T013744p0800/red-test.json"
)
TASK4_RED_RECORD_SHA256 = (
    "f6403baa1a22a9009b23cd961ccade8e98c7843667e378c03769277d4ce5c30c"
)
TASK4_RED_LOG_PATH = Path(
    "/mnt/cunyuliu/d2t-rna/artifacts/runs/"
    "task4-red-20260730T013744p0800/pytest-red.log"
)
TASK4_RED_LOG_SHA256 = (
    "24b29268333094fb9c2236e2a9338ed95d499072b6eedc241afb73292e8b8bee"
)
EXPECTED_GATE_EVIDENCE_RECORDS = {
    "entry_gate": {
        "path": str(TASK4_ENTRY_GATE_PATH),
        "sha256": TASK4_ENTRY_GATE_SHA256,
    },
    "red_test_record": {
        "path": str(TASK4_RED_RECORD_PATH),
        "sha256": TASK4_RED_RECORD_SHA256,
    },
    "red_test_log": {
        "path": str(TASK4_RED_LOG_PATH),
        "sha256": TASK4_RED_LOG_SHA256,
    },
}
EXPECTED_TASK4_ENTRY_GATE = {
    "audited_at": "2026-07-30T01:24:21+08:00",
    "authority": {"contract_sha256": CONTRACT_SHA256},
    "entry_gate": {
        "result": (
            "OPEN_AFTER_TASK3_ACCEPTANCE_CLOSURE_AND_GITHUB_PUSH_VERIFIED"
        )
    },
    "github_state": {
        "default_branch": "main",
        "local_head": TASK3_ACCEPTANCE_COMMIT,
        "origin_main": TASK3_ACCEPTANCE_COMMIT,
        "repository": "Cunyu-Liu/d2t-rna",
        "visibility": "PUBLIC",
    },
    "prior_task_closure": str(TASK3_CLOSURE_PATH),
    "prior_task_closure_sha256": TASK3_CLOSURE_SHA256,
    "preflight": {
        "code_root": "/home/cunyuliu/d2t-rna",
        "evidence_root": "/mnt/cunyuliu/d2t-rna",
        "working_tree": "CLEAN_SYNCHRONIZED_WITH_ORIGIN_MAIN",
    },
    "scientific_claim_boundary": {
        "gpu_required": False,
        "real_data_used": False,
        "scientific_scoring_authorized": False,
        "scope": "EXACT_SYNTHETIC_SOFTWARE_AND_PROBABILITY_VERIFICATION",
    },
    "task_contract": {
        "joint_support_limit": 10_000_000,
        "probability_error_tolerance": 1e-12,
        "required_indifference_bound": 0.05,
        "required_modules": [
            "src/d2t_rna/exact/support.py",
            "src/d2t_rna/exact/enumerate.py",
            "src/d2t_rna/exact/confidence.py",
            "src/d2t_rna/exact/coverage.py",
        ],
    },
    "schema_id": "d2t_rna.task_entry_gate_transition",
    "schema_version": "1.0",
    "task_id": "TASK_4",
}
EXPECTED_TASK4_RED_RECORD = {
    "contract_sha256": CONTRACT_SHA256,
    "entry_gate": {
        "path": str(TASK4_ENTRY_GATE_PATH),
        "sha256": TASK4_ENTRY_GATE_SHA256,
    },
    "expected_failure": {
        "exit_code": 4,
        "reason": "TASK4_EXACT_MODULES_NOT_IMPLEMENTED",
        "root_exception": (
            "ModuleNotFoundError: No module named "
            "'d2t_rna.exact.confidence'"
        ),
    },
    "pytest_log": str(TASK4_RED_LOG_PATH),
    "pytest_log_sha256": TASK4_RED_LOG_SHA256,
    "run_id": "task4-red-20260730T013744p0800",
    "schema_id": "d2t_rna.tdd_red_evidence",
    "schema_version": "1.0",
    "status": "EXPECTED_RED_CONFIRMED",
    "task_id": "TASK_4",
}
EXPECTED_TASK4_RED_LOG_BYTES = (
    b"ImportError while loading conftest "
    b"'/home/cunyuliu/d2t-rna/tests/exact/conftest.py'.\n"
    b"tests/exact/conftest.py:7: in <module>\n"
    b"    from d2t_rna.exact.confidence import (\n"
    b"E   ModuleNotFoundError: No module named "
    b"'d2t_rna.exact.confidence'\n"
)
EXPECTED_TASK3_CLOSURE_FIELDS = frozenset(
    {
        "claim_state",
        "closed_at",
        "contract_sha256",
        "git_commit",
        "git_tree",
        "github",
        "historical_exposure_registry_sha256",
        "preserved_failed_acceptance_attempt",
        "pytest",
        "registered_commit_title",
        "run_id",
        "run_log",
        "run_log_sha256",
        "schema_id",
        "schema_version",
        "source_snapshot_index",
        "source_snapshot_index_sha256",
        "task_entry_gate",
        "task_id",
        "tdd_red_evidence",
        "verified_results",
        "verifier_code_sha256",
        "working_tree",
    }
)
EXPECTED_SOURCE_PATHS = frozenset(
    {
        "README.md",
        "contracts/D2T-RNA-v6.1-frozen-plan.md",
        "docs/audit/task-4-exact-engine.md",
        "manifests/project_contract.json",
        "manifests/task2_failure_policy_abstain_all.json",
        "manifests/task2_semantic_registry.json",
        "manifests/task3_historical_exposure_registry.json",
        "pyproject.toml",
        "scripts/build_task4_acceptance_fixture.py",
        "scripts/build_task4_acceptance_manifest.py",
        "scripts/build_task4_post_commit_closure.py",
        "scripts/run_task4_acceptance.sh",
        "scripts/run_task4_candidate.sh",
        "scripts/task4_isolated_python.py",
        "scripts/verify_task4_acceptance_manifest.py",
        "src/d2t_rna/__init__.py",
        "src/d2t_rna/contracts/__init__.py",
        "src/d2t_rna/contracts/base.py",
        "src/d2t_rna/contracts/enums.py",
        "src/d2t_rna/contracts/extended.py",
        "src/d2t_rna/contracts/locks.py",
        "src/d2t_rna/contracts/primitives.py",
        "src/d2t_rna/contracts/probability.py",
        "src/d2t_rna/contracts/risk.py",
        "src/d2t_rna/contracts/scenario.py",
        "src/d2t_rna/contracts/splits.py",
        "src/d2t_rna/contracts/truth.py",
        "src/d2t_rna/data/__init__.py",
        "src/d2t_rna/data/sanitize.py",
        "src/d2t_rna/evaluation/__init__.py",
        "src/d2t_rna/exact/__init__.py",
        "src/d2t_rna/exact/confidence.py",
        "src/d2t_rna/exact/coverage.py",
        "src/d2t_rna/exact/enumerate.py",
        "src/d2t_rna/exact/support.py",
        "src/d2t_rna/probability/__init__.py",
        "src/d2t_rna/probability/registry.py",
        "src/d2t_rna/probability/risk.py",
        "src/d2t_rna/probability/scopes.py",
        "src/d2t_rna/probability/splits.py",
        "src/d2t_rna/py.typed",
        "tests/__init__.py",
        "tests/contracts/__init__.py",
        "tests/contracts/conftest.py",
        "tests/contracts/test_canonical.py",
        "tests/contracts/test_contract_snapshot.py",
        "tests/contracts/test_enums.py",
        "tests/contracts/test_extended.py",
        "tests/contracts/test_lock_chain.py",
        "tests/contracts/test_model_policy.py",
        "tests/contracts/test_primitives.py",
        "tests/contracts/test_probability_schema.py",
        "tests/contracts/test_truth_commitment.py",
        "tests/data/__init__.py",
        "tests/data/test_sanitizer.py",
        "tests/data/test_truth_locks.py",
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
        "tests/probability/__init__.py",
        "tests/probability/conftest.py",
        "tests/probability/test_registry.py",
        "tests/probability/test_risk.py",
        "tests/probability/test_scopes.py",
        "tests/probability/test_splits.py",
    }
)
EXPECTED_FIXTURE_ARTIFACTS = frozenset(
    {
        "exact_synthetic_report.json",
        "exact_synthetic_replay_credential.json",
        "outer_assessment.json",
        "outer_replay_credential.json",
        "probability_mass_audits.json",
    }
)
FORBIDDEN_ROOT_EXECUTION_INPUTS = (
    "conftest.py",
    "sitecustomize.py",
    "usercustomize.py",
    "pytest.ini",
    "tox.ini",
    "setup.cfg",
)
RUNTIME_DISTRIBUTIONS = (
    ("annotated_types", "annotated-types"),
    ("hypothesis", "hypothesis"),
    ("iniconfig", "iniconfig"),
    ("packaging", "packaging"),
    ("pluggy", "pluggy"),
    ("pydantic", "pydantic"),
    ("pydantic_core", "pydantic-core"),
    ("pygments", "Pygments"),
    ("pytest", "pytest"),
    ("sortedcontainers", "sortedcontainers"),
    ("typing_extensions", "typing-extensions"),
    ("typing_inspection", "typing-inspection"),
)
CONDA_PYTHON_RECORD_RELATIVE_PATH = (
    ".venv/conda-meta/python-3.11.15-h17756b0_1.json"
)
CONDA_PYTHON_RECORD_SHA256 = (
    "5e81a63d79d4ca20e5f041e80e8c45712c91df377721422a9855f1c3465ec080"
)
CONDA_PYTHON_PACKAGE_SHA256 = (
    "6944434fac2bd369561fb68c5c961e6dd684bdf1f96b78e002d0926bb1dd1237"
)
CONDA_PYTHON_EXECUTABLE_SHA256 = (
    "9aac6e55779c2bd3332d6a5fbf3b07257cf3e95b7f24a32b9a4e43c0b896a382"
)
STDLIB_ZIP_RELATIVE_PATH = ".venv/lib/python311.zip"
EXPECTED_CONDA_PYTHON_IDENTITY = {
    "name": "python",
    "version": "3.11.15",
    "build": "h17756b0_1",
    "build_number": 1,
    "channel": "https://repo.anaconda.com/pkgs/main/linux-64",
    "subdir": "linux-64",
    "fn": "python-3.11.15-h17756b0_1.conda",
    "url": (
        "https://repo.anaconda.com/pkgs/main/linux-64/"
        "python-3.11.15-h17756b0_1.conda"
    ),
    "sha256": CONDA_PYTHON_PACKAGE_SHA256,
}
EXPECTED_CONDA_RECORD_FIELDS = frozenset(
    {
        "build",
        "build_number",
        "channel",
        "constrains",
        "depends",
        "extracted_package_dir",
        "files",
        "fn",
        "license",
        "link",
        "md5",
        "name",
        "package_tarball_full_path",
        "paths_data",
        "requested_spec",
        "requested_specs",
        "sha256",
        "size",
        "subdir",
        "timestamp",
        "url",
        "version",
    }
)
EXPECTED_CONDA_PATHS_COUNT = 2_122
EXPECTED_CONDA_RUNTIME_PATHS_COUNT = 1_028
EXPECTED_CONDA_STDLIB_PATHS_COUNT = 1_027
EXPECTED_CONDA_RUNTIME_PATH_FIELD_COUNTS = {
    frozenset(
        {
            "_path",
            "file_mode",
            "path_type",
            "prefix_placeholder",
            "sha256",
            "sha256_in_prefix",
            "size_in_bytes",
        }
    ): 7,
    frozenset(
        {
            "_path",
            "path_type",
            "sha256",
            "sha256_in_prefix",
            "size_in_bytes",
        }
    ): 1_021,
}
EXPECTED_CONDA_RUNTIME_BINDING = {
    "implementation": "CPython",
    "python_version": "3.11.15",
    "python_cache_tag": "cpython-311",
    "stdlib_module_names_count": 305,
    "stdlib_module_names_sha256": (
        "a1dc64a3fd9ca52778578637b95f285fb7e6529439a80100b06a51fe988d3e83"
    ),
    "sysconfigdata_module_name": (
        "_sysconfigdata__linux_x86_64-linux-gnu"
    ),
    "typing_pathless_aliases": ("typing.io", "typing.re"),
    "SOABI": "cpython-311-x86_64-linux-gnu",
    "EXT_SUFFIX": ".cpython-311-x86_64-linux-gnu.so",
    "MULTIARCH": "x86_64-linux-gnu",
    "stdlib_relative": ".venv/lib/python3.11",
    "platstdlib_relative": ".venv/lib/python3.11",
    "DESTSHARED_relative": ".venv/lib/python3.11/lib-dynload",
}
CANDIDATE_RUN_ID = re.compile(
    r"^task4-acceptance-(?P<stamp>[0-9]{8}T[0-9]{6})\+0800$"
)


def _validate_candidate_run_id(run_id: object) -> str:
    """Require a canonical Task 4 run ID with a real calendar timestamp."""

    if type(run_id) is not str:
        raise ValueError("Task 4 candidate run ID is not canonical")
    match = CANDIDATE_RUN_ID.fullmatch(run_id)
    if match is None:
        raise ValueError("Task 4 candidate run ID is not canonical")
    try:
        parsed = datetime.strptime(match.group("stamp"), "%Y%m%dT%H%M%S")
    except ValueError as exc:
        raise ValueError(
            "Task 4 candidate run ID does not contain a real calendar time"
        ) from exc
    if parsed.strftime("%Y%m%dT%H%M%S") != match.group("stamp"):
        raise ValueError(
            "Task 4 candidate run ID timestamp is not canonical"
        )
    return run_id


def _verify_runtime_isolation_flags(flags: object) -> None:
    expected = {
        "isolated": 1,
        "no_site": 1,
        "ignore_environment": 1,
        "no_user_site": 1,
        "safe_path": True,
    }
    changed = tuple(
        name
        for name, expected_value in expected.items()
        if type(getattr(flags, name, None)) is not type(expected_value)
        or getattr(flags, name, None) != expected_value
    )
    if changed:
        raise ValueError(
            "Task 4 verifier lacks required Python isolation flags: "
            + ", ".join(changed)
        )


def _discover_python_execution_paths(project_root: Path) -> frozenset[str]:
    """Discover every Python execution input under src, tests, and scripts."""

    paths: set[str] = set()
    for relative_root in ("src", "tests", "scripts"):
        root = project_root / relative_root
        if not root.is_dir() or root.is_symlink():
            raise ValueError(
                f"Task 4 execution root is unavailable: {relative_root}"
            )
        for path in root.rglob("*"):
            if path.is_symlink():
                raise ValueError(
                    "Task 4 source/test closure contains a symlink: "
                    f"{path.relative_to(project_root)}"
                )
            if not path.is_file():
                continue
            if (
                path.suffix == ".pyc"
                and "__pycache__" not in path.parts
            ):
                raise ValueError(
                    "Task 4 source/test closure contains legacy or "
                    f"sourceless bytecode: {path.relative_to(project_root)}"
                )
            if any(
                path.name.endswith(suffix)
                for suffix in importlib.machinery.EXTENSION_SUFFIXES
            ):
                raise ValueError(
                    "Task 4 source/test closure contains an unregistered "
                    f"native extension: {path.relative_to(project_root)}"
                )
            if (
                path.suffix in {".py", ".pyi"}
                or path.name == "py.typed"
            ):
                paths.add(path.relative_to(project_root).as_posix())
    return frozenset(paths)


def _is_path_within(path: Path, root: Path) -> bool:
    """Return whether an absolute path is lexically within an absolute root."""

    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _verified_site_packages_path(project_root: Path) -> Path:
    """Resolve the launcher-registered site-packages trust root."""

    try:
        site_packages, _, _ = _explicit_project_paths(project_root)
    except IsolationViolation as exc:
        raise ValueError(str(exc)) from exc
    path = Path(site_packages)
    if (
        path.is_symlink()
        or not path.is_dir()
        or path.resolve() != path
    ):
        raise ValueError(
            "Task 4 site-packages trust root is unavailable or unsafe"
        )
    return path


def _verified_runtime_stdlib_roots() -> tuple[Path, ...]:
    """Return canonical stdlib roots trusted by the isolated launcher."""

    configured = sysconfig.get_paths()
    roots: list[Path] = []
    for key in ("stdlib", "platstdlib"):
        raw_path = configured.get(key)
        if type(raw_path) is not str or not raw_path:
            raise ValueError(
                f"Task 4 runtime has no configured {key} root"
            )
        lexical = Path(os.path.abspath(raw_path))
        try:
            resolved = lexical.resolve(strict=True)
        except OSError as exc:
            raise ValueError(
                f"Task 4 runtime {key} root is unavailable"
            ) from exc
        if (
            lexical != resolved
            or resolved.is_symlink()
            or not resolved.is_dir()
        ):
            raise ValueError(
                f"Task 4 runtime {key} root is not a canonical directory"
            )
        if resolved not in roots:
            roots.append(resolved)
    if not roots:
        raise ValueError("Task 4 runtime has no trusted stdlib roots")
    return tuple(roots)


def _verify_stdlib_zip_absent(project_root: Path) -> str:
    """Require the unregistered CPython startup zip path to remain absent."""

    zip_path = project_root / STDLIB_ZIP_RELATIVE_PATH
    if zip_path.exists() or zip_path.is_symlink():
        raise ValueError(
            "Task 4 unauthorized stdlib zip path exists: "
            f"{zip_path}"
        )
    return STDLIB_ZIP_RELATIVE_PATH


def _verify_stdlib_zip_not_on_sys_path(
    raw_paths: tuple[str, ...],
    *,
    project_root: Path,
) -> None:
    """Reject late reinsertion of the absent stdlib zip into ``sys.path``."""

    expected = project_root / STDLIB_ZIP_RELATIVE_PATH
    for raw_path in raw_paths:
        if type(raw_path) is not str or not raw_path:
            continue
        if Path(os.path.abspath(raw_path)) == expected:
            raise ValueError(
                "Task 4 sys.path contains the unauthorized stdlib zip path"
            )


def _runtime_path_label(path: Path, project_root: Path) -> str:
    """Render a canonical runtime path without losing project provenance."""

    resolved = path.resolve(strict=True)
    try:
        relative = resolved.relative_to(project_root.resolve())
    except ValueError:
        return resolved.as_posix()
    return relative.as_posix()


def _stdlib_files_snapshot(
    project_root: Path,
    *,
    stdlib_roots: tuple[Path, ...],
) -> tuple[tuple[str, ...], dict[str, str]]:
    """Hash the trusted stdlib trees while excluding site and bytecode cache."""

    site_packages = _verified_site_packages_path(project_root)
    root_labels: list[str] = []
    files: dict[str, str] = {}

    def fail_walk(error: OSError) -> None:
        raise ValueError(
            f"Task 4 cannot traverse a trusted stdlib tree: {error}"
        ) from error

    for root in sorted(stdlib_roots, key=lambda path: path.as_posix()):
        root_label = _runtime_path_label(root, project_root)
        if root_label not in root_labels:
            root_labels.append(root_label)
        for raw_directory, directory_names, file_names in os.walk(
            root,
            topdown=True,
            followlinks=False,
            onerror=fail_walk,
        ):
            directory = Path(raw_directory)
            retained_directories: list[str] = []
            for name in sorted(directory_names):
                child = directory / name
                if child.is_symlink():
                    raise ValueError(
                        "Task 4 trusted stdlib tree contains a symlink: "
                        f"{child}"
                    )
                if child == site_packages or name == "__pycache__":
                    continue
                resolved_child = child.resolve(strict=True)
                if not _is_path_within(resolved_child, root):
                    raise ValueError(
                        "Task 4 trusted stdlib directory escaped its root: "
                        f"{child}"
                    )
                retained_directories.append(name)
            directory_names[:] = retained_directories

            for name in sorted(file_names):
                path = directory / name
                if path.is_symlink():
                    raise ValueError(
                        "Task 4 trusted stdlib tree contains a symlink: "
                        f"{path}"
                    )
                if path.suffix == ".pyc":
                    continue
                resolved = path.resolve(strict=True)
                if not _is_path_within(resolved, root):
                    raise ValueError(
                        "Task 4 trusted stdlib file escaped its root: "
                        f"{path}"
                    )
                if not resolved.is_file():
                    continue
                label = _runtime_path_label(resolved, project_root)
                observed = hashlib.sha256(
                    resolved.read_bytes()
                ).hexdigest()
                prior = files.setdefault(label, observed)
                if prior != observed:
                    raise ValueError(
                        "Task 4 stdlib snapshot assigns conflicting hashes "
                        f"to {label}"
                    )
    if not files:
        raise ValueError("Task 4 trusted stdlib snapshot contains no files")
    return tuple(root_labels), {
        label: files[label]
        for label in sorted(files)
    }


def _default_conda_python_authority() -> dict[str, object]:
    """Return the immutable production authority for the Python package."""

    return {
        "record_relative_path": CONDA_PYTHON_RECORD_RELATIVE_PATH,
        "record_sha256": CONDA_PYTHON_RECORD_SHA256,
        "package_sha256": CONDA_PYTHON_PACKAGE_SHA256,
        "executable_sha256": CONDA_PYTHON_EXECUTABLE_SHA256,
        "identity": EXPECTED_CONDA_PYTHON_IDENTITY,
        "record_fields": EXPECTED_CONDA_RECORD_FIELDS,
        "paths_count": EXPECTED_CONDA_PATHS_COUNT,
        "runtime_paths_count": EXPECTED_CONDA_RUNTIME_PATHS_COUNT,
        "stdlib_paths_count": EXPECTED_CONDA_STDLIB_PATHS_COUNT,
        "runtime_path_field_counts": (
            EXPECTED_CONDA_RUNTIME_PATH_FIELD_COUNTS
        ),
        "bin_python_record": {
            "path_type": "hardlink",
            "file_mode": "binary",
            "sha256": (
                "1d9883d34033a6cd944993cb9b01f3ee76e377f5bbd694d79ecdc0e649b6a5cd"
            ),
            "sha256_in_prefix": CONDA_PYTHON_EXECUTABLE_SHA256,
            "size_in_bytes": 25_548_416,
        },
        "runtime_binding": EXPECTED_CONDA_RUNTIME_BINDING,
    }


def _verify_live_stdlib_module_names_registry() -> dict[str, object]:
    """Reject mutation of the CPython registry frozen before third-party code."""

    live_names = getattr(sys, "stdlib_module_names", None)
    if (
        type(live_names) is not frozenset
        or live_names != _FROZEN_STDLIB_MODULE_NAMES
    ):
        raise ValueError(
            "Task 4 live stdlib module-name registry changed after startup"
        )
    live_digest = _stdlib_module_names_sha256(live_names)
    if live_digest != _FROZEN_STDLIB_MODULE_NAMES_SHA256:
        raise ValueError(
            "Task 4 live stdlib module-name registry digest changed"
        )
    return {
        "stdlib_module_names_count": len(
            _FROZEN_STDLIB_MODULE_NAMES
        ),
        "stdlib_module_names_sha256": (
            _FROZEN_STDLIB_MODULE_NAMES_SHA256
        ),
    }


def _verify_live_sysconfigdata_module_name() -> str | None:
    """Reject a changed or injected CPython sysconfig-data module name."""

    if (
        getattr(sysconfig, "_get_sysconfigdata_name", None)
        is not _FROZEN_SYSCONFIGDATA_NAME_GETTER
    ):
        raise ValueError(
            "Task 4 sysconfig-data name getter changed after startup"
        )
    try:
        live_name = _current_sysconfigdata_module_name()
    except RuntimeError as exc:
        raise ValueError(str(exc)) from exc
    if live_name != _FROZEN_SYSCONFIGDATA_MODULE_NAME:
        raise ValueError(
            "Task 4 live sysconfig-data module name changed after startup"
        )
    return live_name


def _verify_live_typing_pathless_aliases() -> tuple[str, ...]:
    """Require the pre-third-party typing pseudo-module identities."""

    if (
        stdlib_typing is not _FROZEN_TYPING_MODULE
        or sys.modules.get("typing") is not _FROZEN_TYPING_MODULE
    ):
        raise ValueError("Task 4 trusted typing module identity changed")
    for name, frozen_alias in _FROZEN_TYPING_PATHLESS_ALIASES.items():
        attribute = name.partition(".")[2]
        if (
            sys.modules.get(name) is not frozen_alias
            or getattr(_FROZEN_TYPING_MODULE, attribute, None)
            is not frozen_alias
        ):
            raise ValueError(
                f"Task 4 typing pathless alias changed: {name}"
            )
    return tuple(sorted(_FROZEN_TYPING_PATHLESS_ALIASES))


def _observed_python_runtime_binding() -> dict[str, object]:
    """Capture prefix, ABI, and loader roots from the live interpreter."""

    configured_paths = sysconfig.get_paths()
    return {
        "implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_cache_tag": sys.implementation.cache_tag,
        "executable": sys.executable,
        "prefix": sys.prefix,
        "base_prefix": sys.base_prefix,
        "exec_prefix": sys.exec_prefix,
        "base_exec_prefix": sys.base_exec_prefix,
        "stdlib": configured_paths.get("stdlib"),
        "platstdlib": configured_paths.get("platstdlib"),
        "SOABI": sysconfig.get_config_var("SOABI"),
        "EXT_SUFFIX": sysconfig.get_config_var("EXT_SUFFIX"),
        "MULTIARCH": sysconfig.get_config_var("MULTIARCH"),
        "DESTSHARED": sysconfig.get_config_var("DESTSHARED"),
        "sysconfigdata_module_name": (
            _verify_live_sysconfigdata_module_name()
        ),
        "typing_pathless_aliases": (
            _verify_live_typing_pathless_aliases()
        ),
        **_verify_live_stdlib_module_names_registry(),
    }


def _is_registered_conda_runtime_path(relative_path: str) -> bool:
    if relative_path == "bin/python3.11":
        return True
    return (
        relative_path.startswith("lib/python3.11/")
        and not relative_path.startswith(
            "lib/python3.11/site-packages/"
        )
        and "/__pycache__/" not in relative_path
        and not relative_path.endswith(".pyc")
    )


def _validate_conda_relative_path(value: object) -> str:
    if type(value) is not str or not value:
        raise TypeError("Conda path record must contain a string _path")
    parsed = PurePosixPath(value)
    if (
        parsed.is_absolute()
        or parsed.as_posix() != value
        or any(part in {"", ".", ".."} for part in parsed.parts)
    ):
        raise ValueError(f"Conda path record is not canonical: {value!r}")
    return value


def _verify_conda_python_runtime(
    project_root: Path,
    *,
    authority: dict[str, object] | None = None,
    observed_binding: dict[str, object] | None = None,
) -> tuple[dict[str, object], dict[str, str]]:
    """Replay the installed Python prefix against its hard Conda record."""

    if authority is None:
        authority = _default_conda_python_authority()
    if type(authority) is not dict:
        raise TypeError("Conda Python authority must be an object")
    if observed_binding is None:
        observed_binding = _observed_python_runtime_binding()
    if type(observed_binding) is not dict:
        raise TypeError("Observed Python runtime binding must be an object")

    lexical_project_root = Path(os.path.abspath(project_root))
    try:
        resolved_project_root = lexical_project_root.resolve(strict=True)
    except OSError as exc:
        raise ValueError("Task 4 project root is unavailable") from exc
    if (
        lexical_project_root != resolved_project_root
        or resolved_project_root.is_symlink()
        or not resolved_project_root.is_dir()
    ):
        raise ValueError(
            "Task 4 project root is not a canonical directory"
        )
    project_root = resolved_project_root

    record_relative_path = authority["record_relative_path"]
    if type(record_relative_path) is not str:
        raise TypeError("Conda authority record path must be a string")
    record_path = project_root / record_relative_path
    if (
        record_path.is_symlink()
        or not record_path.is_file()
        or _has_symlink_component(project_root, record_path)
    ):
        raise ValueError(
            "Task 4 Conda Python record is unavailable or symlinked"
        )
    expected_record_sha = _require_sha(
        authority["record_sha256"],
        label="Conda Python record SHA-256",
    )
    record_bytes = record_path.read_bytes()
    if hashlib.sha256(record_bytes).hexdigest() != expected_record_sha:
        raise ValueError("Task 4 Conda Python record bytes changed")
    record = _load_json_object_without_duplicates(
        record_path,
        label="Task 4 Conda Python record",
        raw_bytes=record_bytes,
    )
    record_fields = authority["record_fields"]
    if type(record_fields) is not frozenset or set(record) != record_fields:
        raise ValueError("Task 4 Conda Python record fields changed")

    identity = authority["identity"]
    if type(identity) is not dict:
        raise TypeError("Conda Python authority identity is malformed")
    for field, expected in identity.items():
        observed = record.get(field)
        if type(observed) is not type(expected) or observed != expected:
            raise ValueError(
                f"Task 4 Conda Python identity changed: {field}"
            )
    if record["sha256"] != authority["package_sha256"]:
        raise ValueError("Task 4 Conda Python package SHA changed")

    paths_data = record.get("paths_data")
    if (
        type(paths_data) is not dict
        or set(paths_data) != {"paths", "paths_version"}
        or type(paths_data["paths_version"]) is not int
        or paths_data["paths_version"] != 1
        or type(paths_data["paths"]) is not list
    ):
        raise ValueError("Task 4 Conda paths_data schema changed")
    paths = paths_data["paths"]
    expected_paths_count = authority["paths_count"]
    if (
        type(expected_paths_count) is not int
        or len(paths) != expected_paths_count
    ):
        raise ValueError("Task 4 Conda path count changed")

    files = record.get("files")
    if (
        type(files) is not list
        or len(files) != expected_paths_count
        or any(type(path) is not str for path in files)
        or len(set(files)) != len(files)
    ):
        raise ValueError("Task 4 Conda files registry changed")

    all_paths: dict[str, dict[str, object]] = {}
    runtime_paths: dict[str, dict[str, object]] = {}
    runtime_field_counts: Counter[frozenset[str]] = Counter()
    for item in paths:
        if type(item) is not dict:
            raise TypeError("Task 4 Conda path entry is not an object")
        relative = _validate_conda_relative_path(item.get("_path"))
        if relative in all_paths:
            raise ValueError(
                f"Task 4 Conda record repeats path: {relative}"
            )
        all_paths[relative] = item
        if not _is_registered_conda_runtime_path(relative):
            continue
        if item.get("path_type") != "hardlink":
            raise ValueError(
                "Task 4 Conda runtime path is not a hardlink record: "
                f"{relative}"
            )
        _require_sha(
            item.get("sha256"),
            label=f"Conda package path SHA-256 {relative}",
        )
        _require_sha(
            item.get("sha256_in_prefix"),
            label=f"Conda prefix path SHA-256 {relative}",
        )
        runtime_paths[relative] = item
        runtime_field_counts[frozenset(item)] += 1

    if set(files) != set(all_paths):
        raise ValueError(
            "Task 4 Conda files and paths_data registries disagree"
        )
    if len(runtime_paths) != authority["runtime_paths_count"]:
        raise ValueError("Task 4 Conda runtime path count changed")
    if runtime_field_counts != authority["runtime_path_field_counts"]:
        raise ValueError("Task 4 Conda runtime path fields changed")

    bin_record = runtime_paths.get("bin/python3.11")
    expected_bin_record = authority["bin_python_record"]
    if type(bin_record) is not dict or type(expected_bin_record) is not dict:
        raise ValueError("Task 4 Conda bin/python3.11 record is unavailable")
    for field, expected in expected_bin_record.items():
        observed = bin_record.get(field)
        if type(observed) is not type(expected) or observed != expected:
            raise ValueError(
                f"Task 4 Conda bin/python3.11 field changed: {field}"
            )

    prefix = project_root / ".venv"
    try:
        resolved_prefix = prefix.resolve(strict=True)
    except OSError as exc:
        raise ValueError("Task 4 Python prefix is unavailable") from exc
    if (
        prefix != resolved_prefix
        or prefix.is_symlink()
        or not prefix.is_dir()
        or _has_symlink_component(project_root, prefix)
    ):
        raise ValueError(
            "Task 4 Python prefix is not a canonical directory"
        )
    expected_runtime_binding = authority["runtime_binding"]
    if type(expected_runtime_binding) is not dict:
        raise TypeError("Conda runtime binding authority is malformed")
    expected_observed_binding = {
        "implementation": expected_runtime_binding["implementation"],
        "python_version": expected_runtime_binding["python_version"],
        "python_cache_tag": expected_runtime_binding["python_cache_tag"],
        "stdlib_module_names_count": (
            expected_runtime_binding["stdlib_module_names_count"]
        ),
        "stdlib_module_names_sha256": (
            expected_runtime_binding["stdlib_module_names_sha256"]
        ),
        "sysconfigdata_module_name": (
            expected_runtime_binding["sysconfigdata_module_name"]
        ),
        "typing_pathless_aliases": (
            expected_runtime_binding["typing_pathless_aliases"]
        ),
        "prefix": str(prefix),
        "base_prefix": str(prefix),
        "exec_prefix": str(prefix),
        "base_exec_prefix": str(prefix),
        "stdlib": str(
            project_root
            / expected_runtime_binding["stdlib_relative"]
        ),
        "platstdlib": str(
            project_root
            / expected_runtime_binding["platstdlib_relative"]
        ),
        "SOABI": expected_runtime_binding["SOABI"],
        "EXT_SUFFIX": expected_runtime_binding["EXT_SUFFIX"],
        "MULTIARCH": expected_runtime_binding["MULTIARCH"],
        "DESTSHARED": str(
            project_root
            / expected_runtime_binding["DESTSHARED_relative"]
        ),
    }
    for field, expected in expected_observed_binding.items():
        observed = observed_binding.get(field)
        if type(observed) is not type(expected) or observed != expected:
            raise ValueError(
                f"Task 4 Python runtime binding changed: {field}"
            )

    python_link = prefix / "bin" / "python"
    python_target = prefix / "bin" / "python3.11"
    if (
        not python_link.parent.is_dir()
        or _has_symlink_component(prefix, python_link.parent)
        or not python_link.is_symlink()
        or os.readlink(python_link) != "python3.11"
        or python_target.is_symlink()
        or not python_target.is_file()
        or _has_symlink_component(prefix, python_target)
        or python_target.resolve(strict=True) != python_target
        or python_link.resolve(strict=True) != python_target
    ):
        raise ValueError(
            "Task 4 Python executable link is not bound to bin/python3.11"
        )
    executable = observed_binding.get("executable")
    if type(executable) is not str or Path(executable) != python_link:
        raise ValueError("Task 4 sys.executable changed")
    executable_sha = hashlib.sha256(
        python_target.read_bytes()
    ).hexdigest()
    expected_executable_sha = _require_sha(
        authority["executable_sha256"],
        label="Conda Python executable SHA-256",
    )
    if (
        executable_sha != expected_executable_sha
        or bin_record["sha256_in_prefix"] != expected_executable_sha
    ):
        raise ValueError("Task 4 Python executable bytes changed")

    expected_stdlib_files = {
        f".venv/{relative}": item["sha256_in_prefix"]
        for relative, item in runtime_paths.items()
        if relative != "bin/python3.11"
    }
    if len(expected_stdlib_files) != authority["stdlib_paths_count"]:
        raise ValueError("Task 4 Conda stdlib path count changed")

    anchor = {
        "schema": "d2t_rna.conda_python_runtime_anchor.v1",
        "record_path": record_relative_path,
        "record_sha256": expected_record_sha,
        "package_sha256": authority["package_sha256"],
        "identity": identity,
        "record_paths_count": expected_paths_count,
        "runtime_paths_count": authority["runtime_paths_count"],
        "stdlib_paths_count": authority["stdlib_paths_count"],
        "prefix": ".venv",
        "python_executable": ".venv/bin/python",
        "python_executable_target": ".venv/bin/python3.11",
        "python_executable_sha256": expected_executable_sha,
        "runtime_binding": expected_runtime_binding,
    }
    return anchor, expected_stdlib_files


def _verify_python_process_isolation(
    project_root: Path,
    artifact_root: Path,
) -> None:
    """Require the same isolated interpreter envelope as the shell runners."""

    forbidden = tuple(
        name
        for name in FORBIDDEN_ROOT_EXECUTION_INPUTS
        if (project_root / name).exists()
    )
    if forbidden:
        raise ValueError(
            "Task 4 project root contains unregistered execution inputs: "
            + ", ".join(forbidden)
        )
    try:
        _validate_project_root_import_surface(project_root)
    except IsolationViolation as exc:
        raise ValueError(str(exc)) from exc
    _verify_runtime_isolation_flags(sys.flags)
    if (
        os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") != "1"
        or any(
            name.startswith(("PYTHON", "_PYTHON"))
            or name in {"PYTEST_ADDOPTS", "PYTEST_PLUGINS"}
            for name in os.environ
        )
    ):
        raise ValueError(
            "Task 4 verifier process is not isolated from Python/pytest "
            "injection inputs"
        )
    site_packages = _verified_site_packages_path(project_root)
    source_root = (project_root / "src").resolve()
    root = project_root.resolve()
    _verify_stdlib_zip_absent(root)
    _verify_stdlib_zip_not_on_sys_path(
        tuple(sys.path),
        project_root=root,
    )
    resolved_sys_path: list[Path] = []
    for raw_path in sys.path:
        if type(raw_path) is not str or not raw_path:
            raise ValueError(
                "Task 4 verifier sys.path contains a relative entry"
            )
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            raise ValueError(
                "Task 4 verifier sys.path contains a non-absolute entry"
            )
        lexical = Path(os.path.abspath(candidate))
        try:
            resolved = lexical.resolve(strict=True)
        except OSError as exc:
            raise ValueError(
                "Task 4 verifier sys.path contains an unavailable entry"
            ) from exc
        if (
            raw_path != str(resolved)
            or lexical != resolved
            or lexical.is_symlink()
            or not resolved.is_dir()
        ):
            raise ValueError(
                "Task 4 verifier sys.path contains a non-canonical, "
                "symlinked, or non-directory entry"
            )
        resolved_sys_path.append(resolved)
    required_paths = (site_packages, source_root, root)
    observed_sys_path = tuple(str(path) for path in resolved_sys_path)
    if len(set(observed_sys_path)) != len(observed_sys_path):
        raise ValueError(
            "Task 4 verifier sys.path contains a duplicate entry"
        )
    site_packages_path = str(site_packages)
    try:
        site_packages_position = observed_sys_path.index(
            site_packages_path
        )
    except ValueError as exc:
        raise ValueError(
            "Task 4 verifier sys.path does not contain the registered "
            "site-packages root"
        ) from exc
    paths = sysconfig.get_paths()
    try:
        trusted_interpreter_paths = _trusted_interpreter_paths(
            observed_sys_path[:site_packages_position],
            stdlib_roots=(
                Path(paths["stdlib"]),
                Path(paths["platstdlib"]),
            ),
            version_info=sys.version_info,
        )
    except IsolationViolation as exc:
        raise ValueError(
            "Task 4 verifier import path before site-packages is not "
            f"trusted stdlib: {exc}"
        ) from exc
    expected_sys_path = (
        *trusted_interpreter_paths,
        *(str(path) for path in required_paths),
    )
    if observed_sys_path != expected_sys_path:
        raise ValueError(
            "Task 4 verifier sys.path must exactly equal the trusted "
            "interpreter paths followed by site-packages, src, and root"
        )
    raw_prefix = sys.pycache_prefix
    if type(raw_prefix) is not str:
        raise ValueError("Task 4 verifier requires a dedicated pycache prefix")
    prefix = Path(raw_prefix)
    if (
        not prefix.is_absolute()
        or prefix.is_symlink()
        or not prefix.is_dir()
    ):
        raise ValueError(
            "Task 4 verifier pycache prefix is not an existing absolute "
            "non-symlink directory"
        )
    try:
        prefix.resolve().relative_to(
            (artifact_root / "runs").resolve()
        )
    except ValueError as exc:
        raise ValueError(
            "Task 4 verifier pycache prefix escaped the run artifact root"
        ) from exc


def _python_executable_sha256() -> str:
    """Hash the resolved interpreter bytes used by this process."""

    if type(sys.executable) is not str or not sys.executable:
        raise ValueError("Task 4 runtime has no bound Python executable")
    executable = Path(sys.executable)
    try:
        resolved = executable.resolve(strict=True)
    except OSError as exc:
        raise ValueError(
            "Task 4 Python executable cannot be resolved"
        ) from exc
    if resolved.is_symlink() or not resolved.is_file():
        raise ValueError(
            "Task 4 Python executable is not a regular resolved file"
        )
    return hashlib.sha256(resolved.read_bytes()).hexdigest()


def _distribution_snapshot(
    *,
    site_packages: Path,
    snapshot_name: str,
    distribution_name: str,
) -> dict[str, object]:
    """Hash all installed distribution files that remain in site-packages."""

    try:
        distribution = importlib_metadata.distribution(distribution_name)
    except importlib_metadata.PackageNotFoundError as exc:
        raise ValueError(
            f"Task 4 runtime dependency is unavailable: {distribution_name}"
        ) from exc
    version = distribution.version
    if type(version) is not str or not version:
        raise ValueError(
            f"Task 4 runtime dependency has no version: {distribution_name}"
        )
    distribution_root = Path(
        os.path.abspath(distribution.locate_file(""))
    )
    if (
        _has_symlink_component(site_packages, distribution_root)
        or distribution_root.resolve() != site_packages
    ):
        raise ValueError(
            "Task 4 runtime dependency metadata is outside the verified "
            f"site-packages root: {distribution_name}"
        )
    registered_files = distribution.files
    if registered_files is None:
        raise ValueError(
            "Task 4 runtime dependency has no installed-file registry: "
            f"{distribution_name}"
        )

    files: dict[str, str] = {}
    for registered in registered_files:
        candidate = Path(distribution.locate_file(registered))
        lexical = Path(os.path.abspath(candidate))
        try:
            lexical.relative_to(site_packages)
        except ValueError:
            # Console entrypoints such as ../../../bin/pytest are outside the
            # import trust root and are neither imported nor fingerprinted.
            continue
        if _has_symlink_component(site_packages, lexical):
            raise ValueError(
                "Task 4 runtime dependency traverses a symlink: "
                f"{snapshot_name}:{registered}"
            )
        try:
            resolved = lexical.resolve(strict=True)
        except FileNotFoundError:
            # RECORD may retain optional files that were not installed.
            continue
        try:
            relative = resolved.relative_to(site_packages)
        except ValueError as exc:
            raise ValueError(
                "Task 4 runtime dependency escaped site-packages: "
                f"{snapshot_name}:{registered}"
            ) from exc
        if "__pycache__" in relative.parts or resolved.suffix == ".pyc":
            continue
        if not resolved.is_file():
            continue
        relative_text = relative.as_posix()
        observed = hashlib.sha256(resolved.read_bytes()).hexdigest()
        prior = files.setdefault(relative_text, observed)
        if prior != observed:
            raise ValueError(
                "Task 4 runtime dependency registry is path-ambiguous: "
                f"{snapshot_name}:{relative_text}"
            )
    if not files:
        raise ValueError(
            "Task 4 runtime dependency has no verified site-packages files: "
            f"{distribution_name}"
        )
    return {
        "distribution": distribution_name,
        "version": version,
        "files_sha256": {
            relative: files[relative]
            for relative in sorted(files)
        },
    }


def _runtime_dependency_snapshot(
    project_root: Path,
) -> dict[str, object]:
    """Build the canonical, replayable Task 4 runtime dependency snapshot."""

    site_packages = _verified_site_packages_path(project_root)
    stdlib_zip_path = _verify_stdlib_zip_absent(project_root)
    conda_runtime, registered_stdlib_files = (
        _verify_conda_python_runtime(project_root)
    )
    stdlib_roots = _verified_runtime_stdlib_roots()
    stdlib_root_labels, stdlib_files = _stdlib_files_snapshot(
        project_root,
        stdlib_roots=stdlib_roots,
    )
    _verify_stdlib_tree_against_conda(
        stdlib_files,
        registered_stdlib_files,
    )
    dependencies = {
        snapshot_name: _distribution_snapshot(
            site_packages=site_packages,
            snapshot_name=snapshot_name,
            distribution_name=distribution_name,
        )
        for snapshot_name, distribution_name in RUNTIME_DISTRIBUTIONS
    }
    return {
        "schema": "d2t_rna.task4_runtime_dependency_snapshot.v3",
        "implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_cache_tag": sys.implementation.cache_tag,
        "python_executable_sha256": _python_executable_sha256(),
        "stdlib_zip": {
            "path": stdlib_zip_path,
            "status": "ABSENT",
        },
        "sysconfigdata_module_name": (
            _verify_live_sysconfigdata_module_name()
        ),
        "typing_pathless_aliases": (
            _verify_live_typing_pathless_aliases()
        ),
        "site_packages": ".venv/lib/python3.11/site-packages",
        "conda_python_runtime": conda_runtime,
        "stdlib_roots": stdlib_root_labels,
        "stdlib_files_sha256": stdlib_files,
        "dependencies": dependencies,
    }


def _verify_stdlib_tree_against_conda(
    current_files: dict[str, str],
    registered_files: dict[str, str],
) -> None:
    """Require exact current/record path and byte equality for the stdlib."""

    if type(current_files) is not dict or type(registered_files) is not dict:
        raise TypeError("Task 4 stdlib registries must be objects")
    for registry_name, registry in (
        ("current", current_files),
        ("Conda", registered_files),
    ):
        if not registry:
            raise ValueError(
                f"Task 4 {registry_name} stdlib registry is empty"
            )
        for path, digest in registry.items():
            if type(path) is not str or not path:
                raise TypeError(
                    f"Task 4 {registry_name} stdlib path is malformed"
                )
            _require_sha(
                digest,
                label=f"Task 4 {registry_name} stdlib path {path}",
            )
    if set(current_files) != set(registered_files):
        missing = sorted(set(registered_files) - set(current_files))
        extra = sorted(set(current_files) - set(registered_files))
        raise ValueError(
            "Task 4 current stdlib tree differs from the Conda record: "
            f"missing={missing}, extra={extra}"
        )
    changed = tuple(
        path
        for path in sorted(current_files)
        if current_files[path] != registered_files[path]
    )
    if changed:
        raise ValueError(
            "Task 4 current stdlib bytes differ from the Conda record: "
            + ", ".join(changed)
        )


def runtime_dependency_snapshot_sha256(project_root: Path) -> str:
    """Return the canonical digest used by runners and acceptance manifests."""

    return canonical_sha256(_runtime_dependency_snapshot(project_root))
EXPECTED_FIXTURE_FIELDS = frozenset(
    {
        "schema",
        "fixture_id",
        "fixture_definition_hash",
        "contract_sha256",
        "runtime",
        "artifact_model_schemas",
        "mass_audit_count",
        "support_spec_hash",
        "parameter_universe_hash",
        "coverage_engine_code_hash",
        "outer_verifier_code_hash",
        "report_hash",
        "report_replay_credential_hash",
        "outer_assessment_hash",
        "outer_replay_credential_hash",
        "mathematical_statement_verified",
        "risk_certificate_issued",
        "formal_scientific_certificate_authorized",
        "prospective_claim_authorized",
        "new_library_claim_authorized",
        "serialized_bearer_authorization",
        "external_source_anchor_required",
        "artifacts_sha256",
    }
)
EXPECTED_ARTIFACT_MODEL_SCHEMAS = {
    "exact_synthetic_report.json": (
        "d2t_rna.exact_synthetic_coverage_report@1.0"
    ),
    "exact_synthetic_replay_credential.json": (
        "d2t_rna.exact_coverage_replay_credential@1.0"
    ),
    "outer_assessment.json": (
        "d2t_rna.outer_approximation_assessment@1.0"
    ),
    "outer_replay_credential.json": (
        "d2t_rna.outer_approximation_replay_credential@1.0"
    ),
    "probability_mass_audits.json": (
        "tuple[d2t_rna.probability_mass_audit@1.0]"
    ),
}
EXPECTED_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema",
        "task",
        "status",
        "contract_sha256",
        "registered_commit_title",
        "runtime",
        "gate_evidence",
        "test_evidence",
        "fixture_evidence",
        "source_index",
        "source_index_sha256",
        "claim_boundary",
        "github",
        "post_commit_closure_required",
    }
)
PYTEST_SUMMARY = re.compile(
    r"^(\d+) passed(?:, \d+ warnings?)? in [0-9.]+s"
    r"(?: \([0-9:]+\))?$"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_index(project_root: Path) -> dict[str, str]:
    """Rebuild the complete, non-self-referential Task 4 source index."""

    lexical_root = Path(os.path.abspath(project_root))
    try:
        resolved_root = lexical_root.resolve(strict=True)
    except OSError as exc:
        raise ValueError("Task 4 source-index root is unavailable") from exc
    if (
        not lexical_root.is_dir()
        or lexical_root.is_symlink()
        or resolved_root != lexical_root
    ):
        raise ValueError("Task 4 source-index root is not canonical")
    if len(EXPECTED_SOURCE_PATHS) != 74:
        raise ValueError("Task 4 source path count changed from 74")
    if "manifests/task4_acceptance.json" in EXPECTED_SOURCE_PATHS:
        raise ValueError("Task 4 source index became self-referential")

    index: dict[str, str] = {}
    for relative in sorted(EXPECTED_SOURCE_PATHS):
        path = lexical_root / relative
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise ValueError(
                f"Task 4 registered source is unavailable: {relative}"
            ) from exc
        if (
            path.is_symlink()
            or not path.is_file()
            or resolved != path
            or _has_symlink_component(lexical_root, path)
        ):
            raise ValueError(
                f"Task 4 registered source is unavailable: {relative}"
            )
        index[relative] = _sha256(path)

    registered_execution_paths = frozenset(
        relative
        for relative in EXPECTED_SOURCE_PATHS
        if (
            relative.startswith(("src/", "tests/", "scripts/"))
            and (
                relative.endswith((".py", ".pyi"))
                or relative.endswith("/py.typed")
            )
        )
    )
    discovered_execution_paths = _discover_python_execution_paths(
        lexical_root
    )
    if discovered_execution_paths != registered_execution_paths:
        missing = sorted(
            registered_execution_paths - discovered_execution_paths
        )
        unindexed = sorted(
            discovered_execution_paths - registered_execution_paths
        )
        raise ValueError(
            "Task 4 dynamic Python execution closure differs from the frozen "
            f"source index: missing={missing}, unindexed={unindexed}"
        )
    return index


def source_index_sha256(project_root: Path) -> str:
    """Return the canonical digest of all 74 registered Task 4 input files."""

    return canonical_sha256(_source_index(project_root))


def _require_sha(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be lowercase SHA-256 hex")
    return value


def _canonical_load(
    path: Path,
    *,
    label: str,
    expected_type: type[dict] | type[list],
) -> dict[str, object] | list[object]:
    raw = path.read_bytes()
    text = validate_contract_json_syntax(raw)
    value = json.loads(text)
    if type(value) is not expected_type:
        raise TypeError(f"{label} has the wrong JSON container type")
    if raw != canonical_json_bytes(value) + b"\n":
        raise ValueError(f"{label} is not canonical JSON plus one newline")
    return value


def _path_within(path: Path, root: Path, *, label: str) -> Path:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError(
            f"{label} must be an existing absolute non-symlink file"
        )
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} must remain under {root}") from exc
    return resolved


def _verify_external_file(
    record: object,
    *,
    label: str,
    artifact_root: Path,
) -> Path:
    if type(record) is not dict or set(record) != {"path", "sha256"}:
        raise ValueError(f"{label} must contain exactly path and sha256")
    if type(record["path"]) is not str:
        raise TypeError(f"{label}.path must be a string")
    path = _path_within(
        Path(record["path"]),
        artifact_root,
        label=f"{label}.path",
    )
    expected = _require_sha(record["sha256"], label=f"{label}.sha256")
    if _sha256(path) != expected:
        raise ValueError(f"{label} file hash does not match")
    return path


def _verify_exact_external_path_binding(
    record: dict[str, object],
    resolved_path: Path,
    *,
    expected_path: Path,
    artifact_root: Path,
    label: str,
) -> None:
    """Reject lexical aliases after an external path has been resolved."""

    if (
        record["path"] != str(expected_path)
        or resolved_path != expected_path
        or _has_symlink_component(
            artifact_root.resolve(),
            expected_path,
        )
    ):
        raise ValueError(f"{label} path changed")


def _load_json_object_without_duplicates(
    path: Path,
    *,
    label: str,
    raw_bytes: bytes | None = None,
) -> dict[str, object]:
    def object_hook(pairs):
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    def reject_constant(token: str) -> None:
        raise ValueError(f"{label} contains non-finite token {token}")

    if raw_bytes is None:
        raw_bytes = path.read_bytes()
    if type(raw_bytes) is not bytes:
        raise TypeError(f"{label} raw JSON payload must be bytes")
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} is not valid UTF-8 JSON") from exc
    value = json.loads(
        text,
        object_pairs_hook=object_hook,
        parse_constant=reject_constant,
    )
    if type(value) is not dict:
        raise TypeError(f"{label} must contain a JSON object")
    return value


def _require_exact_json(
    value: object,
    expected: object,
    *,
    label: str,
) -> None:
    """Require recursively exact JSON values, including scalar types."""

    if type(value) is not type(expected):
        raise TypeError(
            f"{label} has type {type(value).__name__}; "
            f"expected {type(expected).__name__}"
        )
    if type(expected) is dict:
        if set(value) != set(expected):
            raise ValueError(f"{label} fields are not exact")
        for key in expected:
            _require_exact_json(
                value[key],
                expected[key],
                label=f"{label}.{key}",
            )
        return
    if type(expected) is list:
        if len(value) != len(expected):
            raise ValueError(f"{label} list length changed")
        for index, (item, expected_item) in enumerate(
            zip(value, expected, strict=True)
        ):
            _require_exact_json(
                item,
                expected_item,
                label=f"{label}[{index}]",
            )
        return
    if value != expected:
        raise ValueError(f"{label} value changed")


def _verify_task3_closure_semantics(
    closure: dict[str, object],
) -> None:
    if set(closure) != EXPECTED_TASK3_CLOSURE_FIELDS:
        raise ValueError("Task 3 closure fields are not exact")
    expected_identity = {
        "schema_id": "d2t_rna.acceptance_closure",
        "schema_version": "1.0",
        "task_id": "TASK_3",
        "contract_sha256": CONTRACT_SHA256,
        "git_commit": TASK3_ACCEPTANCE_COMMIT,
        "registered_commit_title": (
            "feat(data-lock): seal truth payloads until "
            "post-certificate audit"
        ),
        "run_id": (
            "task3-acceptance-recovery-20260730T011748p0800"
        ),
        "working_tree": "CLEAN_SYNCHRONIZED_WITH_ORIGIN_MAIN",
    }
    for field, expected in expected_identity.items():
        _require_exact_json(
            closure[field],
            expected,
            label=f"Task 3 closure.{field}",
        )
    _require_exact_json(
        closure["github"],
        {
            "commit_url": (
                "https://github.com/Cunyu-Liu/d2t-rna/commit/"
                f"{TASK3_ACCEPTANCE_COMMIT}"
            ),
            "default_branch": "main",
            "github_main": TASK3_ACCEPTANCE_COMMIT,
            "origin_main": TASK3_ACCEPTANCE_COMMIT,
            "repository": "Cunyu-Liu/d2t-rna",
            "visibility": "PUBLIC",
        },
        label="Task 3 closure.github",
    )
    _require_exact_json(
        closure["claim_state"],
        {
            "authenticated_chronology_and_access_audit": "UNAVAILABLE",
            "bound_certificate_decision_plan_scoring_byte_replay": (
                "UNAVAILABLE"
            ),
            "lock_d_credential_status": (
                "STRUCTURAL_A_D_PAYLOAD_BOUND_VERIFIED"
            ),
            "scientific_certificates_issued": 0,
            "scoring_allowed": False,
        },
        label="Task 3 closure.claim_state",
    )


def _verify_historical_gate_records(
    records: dict[str, object],
) -> None:
    _require_exact_json(
        records,
        EXPECTED_GATE_EVIDENCE_RECORDS,
        label="Task 4 gate evidence records",
    )


def _verify_task4_entry_gate_semantics(
    entry: dict[str, object],
) -> None:
    _require_exact_json(
        entry,
        EXPECTED_TASK4_ENTRY_GATE,
        label="Task 4 entry gate",
    )


def _verify_task4_red_record_semantics(
    red: dict[str, object],
) -> None:
    _require_exact_json(
        red,
        EXPECTED_TASK4_RED_RECORD,
        label="Task 4 red evidence",
    )


def _verify_task4_red_log(path: Path) -> None:
    if path.read_bytes() != EXPECTED_TASK4_RED_LOG_BYTES:
        raise ValueError("Task 4 red log bytes changed")


def _verify_gate_evidence(
    records: dict[str, object],
    paths: dict[str, Path],
    *,
    artifact_root: Path,
) -> None:
    _verify_historical_gate_records(records)
    expected_paths = {
        "entry_gate": TASK4_ENTRY_GATE_PATH,
        "red_test_record": TASK4_RED_RECORD_PATH,
        "red_test_log": TASK4_RED_LOG_PATH,
    }
    for name, expected_path in expected_paths.items():
        if paths[name] != expected_path.resolve():
            raise ValueError(
                f"Task 4 historical path changed: gate_evidence.{name}"
            )

    entry = _load_json_object_without_duplicates(
        paths["entry_gate"],
        label="Task 4 entry gate",
    )
    _verify_task4_entry_gate_semantics(entry)
    closure_path = _path_within(
        TASK3_CLOSURE_PATH,
        artifact_root,
        label="Task 3 closure",
    )
    if _sha256(closure_path) != TASK3_CLOSURE_SHA256:
        raise ValueError("Task 4 prior closure hash changed")
    closure = _load_json_object_without_duplicates(
        closure_path,
        label="Task 3 closure",
    )
    _verify_task3_closure_semantics(closure)

    red = _load_json_object_without_duplicates(
        paths["red_test_record"],
        label="Task 4 red record",
    )
    _verify_task4_red_record_semantics(red)
    _verify_task4_red_log(paths["red_test_log"])


def _parse_model(path: Path, model_type, *, label: str):
    raw = path.read_bytes()
    value = _canonical_load(
        path,
        label=label,
        expected_type=dict,
    )
    parsed = parse_contract_json(model_type, raw)
    checked = strict_revalidate_contract_model(parsed)
    if canonical_json_bytes(checked) != canonical_json_bytes(value):
        raise ValueError(f"{label} does not round-trip through its strict model")
    return checked


def _parse_mass_audits(path: Path) -> tuple[ProbabilityMassAudit, ...]:
    values = _canonical_load(
        path,
        label="probability mass audits",
        expected_type=list,
    )
    audits = tuple(
        strict_revalidate_contract_model(
            ProbabilityMassAudit.model_validate(value, strict=True)
        )
        for value in values
    )
    if canonical_json_bytes(audits) + b"\n" != path.read_bytes():
        raise ValueError("probability mass audits do not strictly round-trip")
    return audits


def _unique_line_position(lines: list[str], value: str) -> int:
    positions = [index for index, line in enumerate(lines) if line == value]
    if len(positions) != 1:
        raise ValueError(f"Task 4 run log requires exactly one {value!r}")
    return positions[0]


def _summary_between(
    lines: list[str],
    begin: str,
    end: str,
) -> int:
    begin_index = _unique_line_position(lines, begin)
    end_index = _unique_line_position(lines, end)
    if begin_index >= end_index:
        raise ValueError(f"Task 4 log stage is reversed: {begin}")
    matches = tuple(
        match
        for line in lines[begin_index + 1 : end_index]
        if (match := PYTEST_SUMMARY.fullmatch(line))
    )
    if len(matches) != 1:
        raise ValueError(f"Task 4 log stage lacks one pytest summary: {begin}")
    return int(matches[0].group(1))


def _verify_source_index_log_markers(
    lines: list[str],
    *,
    source_index_sha256: str,
) -> tuple[str, str]:
    expected_sha = _require_sha(
        source_index_sha256,
        label="Task 4 current source-index digest",
    )
    marker_names = (
        "TASK4_PRE_TEST_SOURCE_INDEX_SHA256",
        "TASK4_POST_TEST_SOURCE_INDEX_SHA256",
    )
    markers: list[str] = []
    for marker_name in marker_names:
        prefix = f"{marker_name}="
        observed = [
            line
            for line in lines
            if line.startswith(prefix)
        ]
        if len(observed) != 1:
            raise ValueError(
                "Task 4 run log requires exactly one "
                f"{marker_name} marker"
            )
        observed_sha = _require_sha(
            observed[0][len(prefix) :],
            label=f"Task 4 {marker_name} digest",
        )
        if observed_sha != expected_sha:
            raise ValueError(
                "Task 4 logged source-index digest does not match the "
                "current manifest source_index_sha256"
            )
        markers.append(observed[0])
    return markers[0], markers[1]


def _verify_junit(
    path: Path,
    *,
    expected_count: int,
    label: str,
) -> None:
    root = ElementTree.parse(path).getroot()
    suites = tuple(root.iter("testsuite"))
    if len(suites) != 1:
        raise ValueError(f"{label} must contain exactly one testsuite")
    suite = suites[0]
    required = {"tests", "failures", "errors", "skipped"}
    if not required.issubset(suite.attrib):
        raise ValueError(f"{label} lacks required aggregate fields")
    counts = {
        name: int(suite.attrib[name])
        for name in required
    }
    if (
        counts["tests"] != expected_count
        or counts["failures"] != 0
        or counts["errors"] != 0
        or counts["skipped"] != 0
    ):
        raise ValueError(f"{label} does not prove an all-pass test run")
    testcases = tuple(suite.iter("testcase"))
    identities = tuple(
        (
            case.attrib.get("classname"),
            case.attrib.get("name"),
        )
        for case in testcases
    )
    if len(testcases) != expected_count or len(set(identities)) != len(
        identities
    ):
        raise ValueError(f"{label} testcase collection is incomplete")
    if any(
        child.tag.rsplit("}", 1)[-1] in {"failure", "error", "skipped"}
        for case in testcases
        for child in case
    ):
        raise ValueError(f"{label} contains a non-pass testcase outcome")


def _verify_test_log(
    path: Path,
    *,
    run_id: str,
    runtime: dict[str, object],
    fixture_manifest_sha256: str,
    source_index_sha256: str,
    expected_counts: tuple[int, int, int],
    artifact_root: Path | None = None,
) -> None:
    _validate_candidate_run_id(run_id)
    if artifact_root is None:
        raise TypeError("Task 4 run-log verification requires artifact_root")
    lexical_artifact_root = Path(os.path.abspath(artifact_root))
    try:
        resolved_artifact_root = lexical_artifact_root.resolve(strict=True)
    except OSError as exc:
        raise ValueError(
            "Task 4 candidate artifact root is unavailable"
        ) from exc
    if (
        not artifact_root.is_absolute()
        or lexical_artifact_root != resolved_artifact_root
        or resolved_artifact_root.is_symlink()
        or not resolved_artifact_root.is_dir()
    ):
        raise ValueError(
            "Task 4 candidate artifact root is not canonical"
        )
    candidate_run_dir = resolved_artifact_root / "runs" / run_id
    expected_log = candidate_run_dir / "run.log"
    checked_log = _path_within(
        path,
        resolved_artifact_root,
        label="Task 4 candidate run log",
    )
    if (
        candidate_run_dir.is_symlink()
        or not candidate_run_dir.is_dir()
        or _has_symlink_component(
            resolved_artifact_root,
            candidate_run_dir,
        )
        or Path(os.path.abspath(path)) != checked_log
        or checked_log != expected_log
    ):
        raise ValueError(
            "Task 4 candidate run log is not canonically bound to "
            "artifact_root/runs/run_id/run.log"
        )
    lines = checked_log.read_text(encoding="utf-8").splitlines()
    nonempty = [line for line in lines if line]
    if not nonempty or nonempty[0] != (
        "TASK4_RUNNER_SCHEMA=d2t_rna.task4_candidate_runner.v1"
    ):
        raise ValueError("Task 4 run log has no registered runner header")
    candidate_pycache = candidate_run_dir / "pycache"
    if (
        candidate_pycache.is_symlink()
        or not candidate_pycache.is_dir()
        or _has_symlink_component(
            resolved_artifact_root,
            candidate_pycache,
        )
    ):
        raise ValueError(
            "Task 4 candidate pycache isolation directory is unavailable"
        )
    pre_source_marker, post_source_marker = (
        _verify_source_index_log_markers(
            lines,
            source_index_sha256=source_index_sha256,
        )
    )
    required_markers = (
        "TASK4_RUNNER_SCHEMA=d2t_rna.task4_candidate_runner.v1",
        f"TASK4_RUN_ID={run_id}",
        (
            "TASK4_RUNTIME="
            f"{runtime['implementation']} {runtime['python_version']}"
        ),
        f"TASK4_CONTRACT_SHA256={CONTRACT_SHA256}",
        (
            "TASK4_DEPENDENCY_SNAPSHOT_SHA256="
            f"{runtime['dependency_snapshot_sha256']}"
        ),
        (
            "TASK4_PYTHON_ISOLATION_PASS="
            f"{artifact_root}/runs/{run_id}/pycache"
        ),
        pre_source_marker,
        "TASK4_EXACT_TESTS_BEGIN",
        "TASK4_EXACT_TESTS_END",
        "TASK4_COMBINED_TESTS_BEGIN",
        "TASK4_COMBINED_TESTS_END",
        "TASK4_FULL_TESTS_BEGIN",
        "TASK4_FULL_TESTS_END",
        post_source_marker,
        "TASK4_COMPILE_PASS",
        f"TASK4_FIXTURE_MANIFEST_SHA256={fixture_manifest_sha256}",
        "TASK4_GIT_DIFF_CHECK_PASS",
        "TASK4_EXISTING_MANIFEST_JSON_PASS",
        "TASK4_CANDIDATE_PASS",
    )
    positions = tuple(
        _unique_line_position(lines, marker)
        for marker in required_markers
    )
    if positions != tuple(sorted(positions)):
        raise ValueError("Task 4 run stages are out of order")
    if nonempty[-1] != "TASK4_CANDIDATE_PASS":
        raise ValueError("Task 4 candidate closure is not terminal")
    observed_counts = (
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
    if observed_counts != expected_counts:
        raise ValueError("Task 4 test counts do not replay from the run log")


def _verify_builtin_or_frozen_module(
    module: object,
    *,
    module_key: object,
) -> bool:
    """Verify executable-anchored modules with no filesystem code payload."""

    spec = getattr(module, "__spec__", None)
    origin = getattr(spec, "origin", None)
    if origin not in {"built-in", "frozen"}:
        return False
    if type(spec) is not importlib.machinery.ModuleSpec:
        raise ValueError(
            "Task 4 built-in/frozen module has a spoofed ModuleSpec"
        )
    expected_loader = (
        importlib.machinery.BuiltinImporter
        if origin == "built-in"
        else importlib.machinery.FrozenImporter
    )
    if (
        type(module_key) is not str
        or sys.modules.get(module_key) is not module
        or spec.loader is not expected_loader
        or getattr(module, "__loader__", None) is not expected_loader
        or type(spec.name) is not str
        or sys.modules.get(spec.name) is not module
        or type(getattr(module, "__name__", None)) is not str
        or spec.name.partition(".")[0]
        not in _FROZEN_STDLIB_MODULE_NAMES
        or getattr(module, "__name__").partition(".")[0]
        not in _FROZEN_STDLIB_MODULE_NAMES
        or spec.has_location is not False
    ):
        raise ValueError(
            "Task 4 built-in/frozen module loader or origin is not genuine: "
            f"{getattr(spec, 'name', None)!r}"
        )
    found_spec = expected_loader.find_spec(spec.name)
    if (
        type(found_spec) is not importlib.machinery.ModuleSpec
        or found_spec.name != spec.name
        or found_spec.origin != origin
        or found_spec.loader is not expected_loader
        or found_spec.has_location is not False
        or found_spec.submodule_search_locations
        != spec.submodule_search_locations
    ):
        raise ValueError(
            "Task 4 built-in/frozen module failed genuine importer lookup: "
            f"{spec.name!r}"
        )
    return True


def _verify_stdlib_file_module_metadata(
    module: object,
    *,
    module_key: object,
    resolved_path: Path,
    is_native: bool,
) -> str:
    """Bind a stdlib file module to its genuine CPython file loader."""

    spec = getattr(module, "__spec__", None)
    if type(spec) is not importlib.machinery.ModuleSpec:
        raise ValueError(
            "Task 4 standard-library file module has no genuine ModuleSpec"
        )
    expected_loader_type = (
        importlib.machinery.ExtensionFileLoader
        if is_native
        else importlib.machinery.SourceFileLoader
    )
    loader = spec.loader
    observed_definition_name = getattr(module, "__name__", None)
    expected_definition_name = (
        _FROZEN_STDLIB_NATIVE_MODULE_DEFINITION_NAMES.get(
            spec.name,
            spec.name,
        )
        if is_native
        else spec.name
    )
    if (
        type(module_key) is not str
        or sys.modules.get(module_key) is not module
        or type(loader) is not expected_loader_type
        or getattr(module, "__loader__", None) is not loader
        or spec.has_location is not True
        or type(spec.origin) is not str
        or type(spec.name) is not str
        or sys.modules.get(spec.name) is not module
        or observed_definition_name != expected_definition_name
    ):
        raise ValueError(
            "Task 4 standard-library module loader/spec is not genuine: "
            f"{getattr(spec, 'name', None)!r}"
        )
    is_exact_sysconfigdata = (
        _FROZEN_SYSCONFIGDATA_MODULE_NAME is not None
        and spec.name == _FROZEN_SYSCONFIGDATA_MODULE_NAME
    )
    if is_exact_sysconfigdata and is_native:
        raise ValueError(
            "Task 4 sysconfig-data module is not source-backed"
        )
    if (
        spec.name.partition(".")[0]
        not in _FROZEN_STDLIB_MODULE_NAMES
        and not is_exact_sysconfigdata
    ):
        raise ValueError(
            "Task 4 standard-library file has an unregistered module name: "
            f"{spec.name!r}"
        )
    origin = Path(os.path.abspath(spec.origin))
    loader_path = getattr(loader, "path", None)
    loader_name = getattr(loader, "name", None)
    if (
        type(loader_path) is not str
        or type(loader_name) is not str
        or loader_name != spec.name
    ):
        raise ValueError(
            "Task 4 standard-library loader identity changed"
        )
    try:
        resolved_origin = origin.resolve(strict=True)
        resolved_loader_path = Path(
            os.path.abspath(loader_path)
        ).resolve(strict=True)
    except OSError as exc:
        raise ValueError(
            "Task 4 standard-library loader path is unavailable"
        ) from exc
    if (
        origin != resolved_origin
        or resolved_origin != resolved_path
        or resolved_loader_path != resolved_path
    ):
        raise ValueError(
            "Task 4 standard-library loader origin/path changed"
        )
    try:
        is_package = loader.is_package(spec.name)
    except (AttributeError, ImportError) as exc:
        raise ValueError(
            "Task 4 standard-library loader cannot classify its module"
        ) from exc
    if type(is_package) is not bool:
        raise ValueError(
            "Task 4 standard-library package classification changed"
        )
    if is_package:
        _verified_single_location(
            spec.submodule_search_locations,
            expected=resolved_path.parent,
            label=f"stdlib package {spec.name}",
        )
        _verified_single_location(
            getattr(module, "__path__", None),
            expected=resolved_path.parent,
            label=f"stdlib package object {spec.name}",
        )
    elif (
        spec.submodule_search_locations is not None
        or getattr(module, "__path__", None) is not None
    ):
        raise ValueError(
            "Task 4 standard-library module gained package search paths: "
            f"{spec.name!r}"
        )

    search_root = (
        resolved_path.parent.parent
        if is_package
        else resolved_path.parent
    )
    suffixes = (
        importlib.machinery.EXTENSION_SUFFIXES
        if is_native
        else importlib.machinery.SOURCE_SUFFIXES
    )
    direct_finder = importlib.machinery.FileFinder(
        str(search_root),
        (expected_loader_type, suffixes),
    )
    independently_found = (
        direct_finder.find_spec(spec.name),
        importlib.machinery.PathFinder.find_spec(
            spec.name,
            [str(search_root)],
        ),
    )
    for found_spec in independently_found:
        found_loader = getattr(found_spec, "loader", None)
        found_origin = getattr(found_spec, "origin", None)
        if (
            type(found_spec) is not importlib.machinery.ModuleSpec
            or found_spec.name != spec.name
            or type(found_loader) is not expected_loader_type
            or type(found_origin) is not str
            or getattr(found_loader, "name", None) != spec.name
        ):
            raise ValueError(
                "Task 4 standard-library module failed genuine importer "
                f"lookup: {spec.name!r}"
            )
        try:
            found_is_package = found_loader.is_package(found_spec.name)
            found_path = Path(
                os.path.abspath(found_origin)
            ).resolve(strict=True)
            found_loader_path = Path(
                os.path.abspath(found_loader.path)
            ).resolve(strict=True)
        except (AttributeError, ImportError, OSError) as exc:
            raise ValueError(
                "Task 4 standard-library importer returned an unavailable "
                f"path: {spec.name!r}"
            ) from exc
        if (
            type(found_is_package) is not bool
            or found_is_package is not is_package
            or found_path != resolved_path
            or found_loader_path != resolved_path
        ):
            raise ValueError(
                "Task 4 standard-library importer resolved different bytes: "
                f"{spec.name!r}"
            )
        if is_package:
            _verified_single_location(
                found_spec.submodule_search_locations,
                expected=resolved_path.parent,
                label=f"found stdlib package {spec.name}",
            )
        elif found_spec.submodule_search_locations is not None:
            raise ValueError(
                "Task 4 found stdlib module gained package search paths: "
                f"{spec.name!r}"
            )
    return spec.name


def _runtime_modules_snapshot() -> tuple[tuple[object, object], ...]:
    """Snapshot the live module registry for fail-closed closure checking."""

    return tuple(sys.modules.items())


def _verified_single_location(
    value: object,
    *,
    expected: Path,
    label: str,
) -> None:
    """Require one canonical import location and no external search roots."""

    if value is None or isinstance(value, (str, bytes)):
        raise ValueError(f"Task 4 {label} has no location registry")
    try:
        locations = tuple(value)
    except TypeError as exc:
        raise ValueError(
            f"Task 4 {label} location registry is malformed"
        ) from exc
    if len(locations) != 1 or type(locations[0]) is not str:
        raise ValueError(
            f"Task 4 {label} must have exactly one string location"
        )
    lexical = Path(os.path.abspath(locations[0]))
    try:
        resolved = lexical.resolve(strict=True)
    except OSError as exc:
        raise ValueError(
            f"Task 4 {label} location is unavailable"
        ) from exc
    if (
        lexical != resolved
        or resolved != expected
        or resolved.is_symlink()
        or not resolved.is_dir()
    ):
        raise ValueError(
            f"Task 4 {label} location is external or non-canonical"
        )


def _verify_scripts_namespace_module(
    module: object,
    *,
    module_key: str,
    project_root: Path,
) -> None:
    """Verify the one registered project namespace package."""

    expected = project_root / "scripts"
    spec = getattr(module, "__spec__", None)
    loader = getattr(spec, "loader", None)
    if (
        module_key != "scripts"
        or type(module) is not ModuleType
        or type(spec) is not importlib.machinery.ModuleSpec
        or spec.name != "scripts"
        or type(loader) is not importlib.machinery.NamespaceLoader
        or getattr(module, "__loader__", None) is not loader
        or getattr(module, "__name__", None) != "scripts"
        or getattr(module, "__package__", None) != "scripts"
        or spec.origin is not None
        or spec.has_location is not False
        or sys.modules.get("scripts") is not module
        or getattr(module, "__path__", None)
        is not spec.submodule_search_locations
    ):
        raise ValueError(
            "Task 4 scripts namespace module identity changed"
        )
    _verified_single_location(
        spec.submodule_search_locations,
        expected=expected,
        label="scripts namespace",
    )
    for label, found_spec in (
        (
            "direct scripts namespace",
            importlib.machinery.FileFinder(
                str(project_root)
            ).find_spec("scripts"),
        ),
        (
            "PathFinder scripts namespace",
            importlib.machinery.PathFinder.find_spec(
                "scripts",
                [str(project_root)],
            ),
        ),
    ):
        if (
            type(found_spec) is not importlib.machinery.ModuleSpec
            or found_spec.name != "scripts"
            or found_spec.loader is not None
            or found_spec.origin is not None
        ):
            raise ValueError(
                f"Task 4 {label} lookup identity changed"
            )
        _verified_single_location(
            found_spec.submodule_search_locations,
            expected=expected,
            label=label,
        )


def _verify_pyexpat_pathless_child(
    module: object,
    *,
    module_key: str,
    module_registry: dict[str, object],
) -> None:
    """Bind pyexpat's two C-created child modules to their parent object."""

    if module_key not in {"pyexpat.errors", "pyexpat.model"}:
        raise ValueError("Task 4 pyexpat child name is unregistered")
    parent = module_registry.get("pyexpat")
    attribute = module_key.partition(".")[2]
    if (
        type(module) is not ModuleType
        or sys.modules.get(module_key) is not module
        or parent is None
        or sys.modules.get("pyexpat") is not parent
        or getattr(parent, attribute, None) is not module
        or getattr(module, "__name__", None) != module_key
        or getattr(module, "__spec__", None) is not None
        or getattr(module, "__loader__", None) is not None
        or getattr(module, "__package__", None) is not None
        or getattr(module, "__file__", None) is not None
        or getattr(module, "__path__", None) is not None
    ):
        raise ValueError(
            f"Task 4 pathless CPython child identity changed: {module_key}"
        )


def _verify_typing_pathless_alias(
    module: object,
    *,
    module_key: str,
    module_registry: dict[str, object],
) -> None:
    """Bind CPython 3.11 typing aliases to their pre-import identities."""

    frozen = _FROZEN_TYPING_PATHLESS_ALIASES.get(module_key)
    attribute = module_key.partition(".")[2]
    if (
        frozen is None
        or module is not frozen
        or sys.modules.get(module_key) is not frozen
        or getattr(_FROZEN_TYPING_MODULE, attribute, None) is not frozen
        or module_registry.get("typing") is not _FROZEN_TYPING_MODULE
        or sys.modules.get("typing") is not _FROZEN_TYPING_MODULE
        or getattr(module, "__spec__", None) is not None
        or getattr(module, "__loader__", None) is not None
        or getattr(module, "__file__", None) is not None
        or getattr(module, "__path__", None) is not None
    ):
        raise ValueError(
            f"Task 4 pathless typing alias identity changed: {module_key}"
        )


def _verify_runtime_import_closure(
    project_root: Path,
    source_index: dict[str, object],
    *,
    dependency_snapshot: dict[str, object] | None = None,
    stdlib_roots: tuple[Path, ...] | None = None,
) -> None:
    _verify_live_stdlib_module_names_registry()
    exact_sysconfigdata_name = _verify_live_sysconfigdata_module_name()
    loaded_paths: set[str] = set()
    root = project_root.resolve()
    site_packages = _verified_site_packages_path(project_root)
    if stdlib_roots is None:
        trusted_stdlib_roots = _verified_runtime_stdlib_roots()
    else:
        validated_roots: list[Path] = []
        for raw_root in stdlib_roots:
            if not raw_root.is_absolute():
                raise ValueError(
                    "Task 4 supplied stdlib root is not absolute"
                )
            lexical_root = Path(os.path.abspath(raw_root))
            try:
                resolved_root = lexical_root.resolve(strict=True)
            except OSError as exc:
                raise ValueError(
                    "Task 4 supplied stdlib root is unavailable"
                ) from exc
            if (
                lexical_root != resolved_root
                or resolved_root.is_symlink()
                or not resolved_root.is_dir()
            ):
                raise ValueError(
                    "Task 4 supplied stdlib root is not canonical"
                )
            if resolved_root not in validated_roots:
                validated_roots.append(resolved_root)
        if not validated_roots:
            raise ValueError("Task 4 supplied no trusted stdlib roots")
        trusted_stdlib_roots = tuple(validated_roots)
    if dependency_snapshot is None:
        dependency_snapshot = _runtime_dependency_snapshot(project_root)
    dependencies = dependency_snapshot.get("dependencies")
    if type(dependencies) is not dict:
        raise TypeError("Task 4 dependency snapshot has no dependency map")
    dependency_files: dict[str, str] = {}
    for name, record in dependencies.items():
        if type(name) is not str or type(record) is not dict:
            raise TypeError("Task 4 dependency snapshot record is malformed")
        files = record.get("files_sha256")
        if type(files) is not dict or not files:
            raise ValueError(
                f"Task 4 dependency snapshot has no files for {name}"
            )
        for relative, expected_hash in files.items():
            if type(relative) is not str:
                raise TypeError(
                    "Task 4 dependency snapshot file path is not a string"
                )
            _require_sha(
                expected_hash,
                label=f"dependency_snapshot.{name}.{relative}",
            )
            prior = dependency_files.setdefault(relative, expected_hash)
            if prior != expected_hash:
                raise ValueError(
                    "Task 4 dependency snapshot assigns conflicting hashes "
                    f"to {relative}"
                )
    expected_stdlib_root_labels = tuple(
        _runtime_path_label(trusted_root, project_root)
        for trusted_root in sorted(
            trusted_stdlib_roots,
            key=lambda candidate: candidate.as_posix(),
        )
    )
    if dependency_snapshot.get("stdlib_roots") != (
        expected_stdlib_root_labels
    ):
        raise ValueError(
            "Task 4 dependency snapshot stdlib roots changed"
        )
    stdlib_files = dependency_snapshot.get("stdlib_files_sha256")
    if type(stdlib_files) is not dict or not stdlib_files:
        raise ValueError(
            "Task 4 dependency snapshot has no stdlib file registry"
        )
    for relative, expected_hash in stdlib_files.items():
        if type(relative) is not str:
            raise TypeError(
                "Task 4 stdlib snapshot path is not a string"
            )
        _require_sha(
            expected_hash,
            label=f"dependency_snapshot.stdlib.{relative}",
        )
    module_items = _runtime_modules_snapshot()
    module_registry: dict[str, object] = {}
    for module_name, module in module_items:
        if (
            type(module_name) is not str
            or not module_name
            or module_name in module_registry
            or sys.modules.get(module_name) is not module
        ):
            raise ValueError(
                "Task 4 live module registry is malformed or changed"
            )
        module_registry[module_name] = module
    verified_stdlib_file_names: set[str] = set()
    required_stdlib_parent_names: set[str] = set()
    for _module_name, module in module_items:
        spec = getattr(module, "__spec__", None)
        spec_name = getattr(spec, "name", None)
        for generated_name in (_module_name, spec_name):
            if (
                type(generated_name) is str
                and generated_name.startswith("_sysconfigdata_")
                and generated_name != exact_sysconfigdata_name
            ):
                raise ValueError(
                    "Task 4 loaded an unexpected sysconfig-data module: "
                    f"{generated_name!r}"
                )
        if (
            type(_module_name) is str
            and _module_name.startswith("_sysconfigdata_")
            and spec_name != exact_sysconfigdata_name
        ):
            raise ValueError(
                "Task 4 canonical sysconfig-data module identity changed"
            )
        if _verify_builtin_or_frozen_module(
            module,
            module_key=_module_name,
        ):
            continue
        raw_path = getattr(module, "__file__", None)
        if raw_path is None:
            if spec_name == exact_sysconfigdata_name:
                raise ValueError(
                    "Task 4 sysconfig-data module is not file-backed"
                )
            if _module_name == "scripts":
                _verify_scripts_namespace_module(
                    module,
                    module_key=_module_name,
                    project_root=root,
                )
                continue
            if _module_name in {"pyexpat.errors", "pyexpat.model"}:
                _verify_pyexpat_pathless_child(
                    module,
                    module_key=_module_name,
                    module_registry=module_registry,
                )
                required_stdlib_parent_names.add("pyexpat")
                continue
            if _module_name in _FROZEN_TYPING_PATHLESS_ALIASES:
                _verify_typing_pathless_alias(
                    module,
                    module_key=_module_name,
                    module_registry=module_registry,
                )
                required_stdlib_parent_names.add("typing")
                continue
            raise ValueError(
                "Task 4 loaded an unregistered pathless module: "
                f"{_module_name!r}"
            )
        if type(raw_path) is not str or not raw_path:
            raise ValueError(
                "Task 4 loaded module has a non-canonical __file__: "
                f"{_module_name!r}"
            )
        path = Path(raw_path)
        if path.suffix == ".pyc":
            try:
                path = Path(importlib.util.source_from_cache(str(path)))
            except (ValueError, NotImplementedError) as exc:
                try:
                    path.resolve().relative_to(root)
                except (OSError, ValueError):
                    raise ValueError(
                        "Task 4 loaded external bytecode without a "
                        f"canonical source path: {raw_path}"
                    ) from exc
                raise ValueError(
                    "Task 4 loaded project bytecode without a canonical "
                    "source path"
                ) from exc
        lexical = Path(os.path.abspath(path))
        is_native = any(
            lexical.name.endswith(suffix)
            for suffix in importlib.machinery.EXTENSION_SUFFIXES
        )
        try:
            resolved = lexical.resolve(strict=True)
        except OSError as exc:
            raise ValueError(
                f"Task 4 loaded file-backed module is unavailable: {path}"
            ) from exc

        if (
            spec_name == exact_sysconfigdata_name
            and not any(
                _is_path_within(lexical, trusted_root)
                for trusted_root in trusted_stdlib_roots
            )
        ):
            raise ValueError(
                "Task 4 sysconfig-data module is outside the trusted stdlib"
            )

        if _is_path_within(lexical, site_packages):
            if _has_symlink_component(site_packages, lexical):
                raise ValueError(
                    "Task 4 loaded a symlinked site-packages module: "
                    f"{path}"
                )
            if not _is_path_within(resolved, site_packages):
                raise ValueError(
                    "Task 4 loaded site-packages module escaped its "
                    f"trusted root: {path}"
                )
            if not (
                lexical.suffix in {".py", ".pyi", ".pyc"}
                or is_native
            ):
                raise ValueError(
                    "Task 4 loaded a site-packages module with an unknown "
                    f"file type: {path}"
                )
            relative_site_path = resolved.relative_to(
                site_packages
            ).as_posix()
            expected_hash = dependency_files.get(relative_site_path)
            if expected_hash is None:
                raise ValueError(
                    "Task 4 loaded an unfingerprinted site-packages module: "
                    f"{relative_site_path}"
                )
            observed_hash = hashlib.sha256(
                resolved.read_bytes()
            ).hexdigest()
            if observed_hash != expected_hash:
                raise ValueError(
                    "Task 4 loaded site-packages bytes differ from the "
                    f"dependency snapshot: {relative_site_path}"
                )
            continue

        stdlib_root = next(
            (
                trusted_root
                for trusted_root in sorted(
                    trusted_stdlib_roots,
                    key=lambda candidate: len(candidate.parts),
                    reverse=True,
                )
                if _is_path_within(lexical, trusted_root)
            ),
            None,
        )
        if stdlib_root is not None:
            if _has_symlink_component(stdlib_root, lexical):
                raise ValueError(
                    "Task 4 loaded a symlinked standard-library module: "
                    f"{path}"
                )
            if not _is_path_within(resolved, stdlib_root):
                raise ValueError(
                    "Task 4 loaded standard-library module escaped its "
                    f"trusted root: {path}"
                )
            stdlib_label = _runtime_path_label(resolved, project_root)
            expected_hash = stdlib_files.get(stdlib_label)
            if expected_hash is None:
                raise ValueError(
                    "Task 4 loaded an unfingerprinted standard-library "
                    f"module: {stdlib_label}"
                )
            observed_hash = hashlib.sha256(
                resolved.read_bytes()
            ).hexdigest()
            if observed_hash != expected_hash:
                raise ValueError(
                    "Task 4 loaded standard-library bytes differ from the "
                    f"runtime snapshot: {stdlib_label}"
                )
            verified_name = _verify_stdlib_file_module_metadata(
                module,
                module_key=_module_name,
                resolved_path=resolved,
                is_native=is_native,
            )
            verified_stdlib_file_names.add(verified_name)
            continue

        if not _is_path_within(lexical, root):
            raise ValueError(
                "Task 4 loaded an external file-backed module outside all "
                f"trusted roots: {_module_name!r} -> {path}"
            )
        if _has_symlink_component(root, lexical):
            raise ValueError(
                "Task 4 loaded a symlinked project module: "
                f"{path}"
            )
        if not _is_path_within(resolved, root):
            raise ValueError(
                "Task 4 loaded project module escaped its trusted root: "
                f"{path}"
            )
        relative = resolved.relative_to(root)
        if is_native:
            raise ValueError(
                "Task 4 loaded an unregistered project native extension: "
                f"{relative.as_posix()}"
            )
        if lexical.suffix not in {".py", ".pyi"}:
            raise ValueError(
                "Task 4 loaded a project module with an unknown file type: "
                f"{relative.as_posix()}"
            )
        loaded_paths.add(relative.as_posix())
    missing = loaded_paths - set(source_index)
    if missing:
        raise ValueError(
            "Task 4 runtime imported unindexed project sources: "
            + ", ".join(sorted(missing))
        )
    missing_parents = (
        required_stdlib_parent_names - verified_stdlib_file_names
    )
    if missing_parents:
        raise ValueError(
            "Task 4 pathless module parent was not verified from stdlib "
            "bytes: " + ", ".join(sorted(missing_parents))
        )


def _verify_fixture(
    path: Path,
    *,
    acceptance_record: dict[str, object],
    project_root: Path,
    artifact_root: Path,
    live_run_dir: Path,
) -> Path:
    if (
        not live_run_dir.is_absolute()
        or live_run_dir.is_symlink()
        or not live_run_dir.is_dir()
    ):
        raise ValueError(
            "Task 4 live-run directory must be an existing absolute "
            "non-symlink directory"
        )
    try:
        live_run_dir.resolve().relative_to(artifact_root.resolve())
    except ValueError as exc:
        raise ValueError(
            "Task 4 live-run directory escaped the artifact root"
        ) from exc

    fixture = _canonical_load(
        path,
        label="fixture_evidence.manifest",
        expected_type=dict,
    )
    if set(fixture) != EXPECTED_FIXTURE_FIELDS:
        raise ValueError("Task 4 fixture manifest fields are not exact")
    if (
        fixture["schema"]
        != "d2t_rna.task4_acceptance_fixture_manifest.v2"
        or fixture["fixture_id"]
        != "task4.registered.synthetic-microcase.v1"
        or fixture["contract_sha256"] != CONTRACT_SHA256
    ):
        raise ValueError("Task 4 fixture authority changed")
    _require_sha(
        fixture["fixture_definition_hash"],
        label="fixture.fixture_definition_hash",
    )
    fixture_runtime = fixture["runtime"]
    if type(fixture_runtime) is not dict or fixture_runtime != {
        "implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_cache_tag": sys.implementation.cache_tag,
        "pydantic_version": pydantic.__version__,
    }:
        raise ValueError("Task 4 fixture runtime is not the live runtime")
    if (
        fixture["artifact_model_schemas"]
        != EXPECTED_ARTIFACT_MODEL_SCHEMAS
        or fixture["mass_audit_count"] != 3
    ):
        raise ValueError("Task 4 fixture model registry changed")

    artifacts = fixture["artifacts_sha256"]
    if (
        type(artifacts) is not dict
        or set(artifacts) != EXPECTED_FIXTURE_ARTIFACTS
    ):
        raise ValueError("Task 4 fixture artifact set changed")
    artifact_paths: dict[str, Path] = {}
    for filename, expected_hash in artifacts.items():
        _require_sha(
            expected_hash,
            label=f"fixture.artifacts_sha256.{filename}",
        )
        artifact_path = _path_within(
            path.parent / filename,
            artifact_root,
            label=f"fixture artifact {filename}",
        )
        if _sha256(artifact_path) != expected_hash:
            raise ValueError(
                f"Task 4 fixture artifact hash changed: {filename}"
            )
        artifact_paths[filename] = artifact_path

    report = _parse_model(
        artifact_paths["exact_synthetic_report.json"],
        ExactSyntheticCoverageReport,
        label="exact synthetic report",
    )
    report_replay = _parse_model(
        artifact_paths["exact_synthetic_replay_credential.json"],
        ExactSyntheticCoverageReplayCredential,
        label="exact synthetic replay credential",
    )
    outer = _parse_model(
        artifact_paths["outer_assessment.json"],
        OuterApproximationAssessment,
        label="outer approximation assessment",
    )
    outer_replay = _parse_model(
        artifact_paths["outer_replay_credential.json"],
        OuterApproximationReplayCredential,
        label="outer approximation replay credential",
    )
    mass_audits = _parse_mass_audits(
        artifact_paths["probability_mass_audits.json"]
    )

    for field in (
        "mathematical_statement_verified",
        "risk_certificate_issued",
        "formal_scientific_certificate_authorized",
        "prospective_claim_authorized",
        "new_library_claim_authorized",
        "serialized_bearer_authorization",
        "external_source_anchor_required",
    ):
        if fixture[field] is not acceptance_record[field]:
            raise ValueError(
                f"Task 4 fixture and acceptance disagree on {field}"
            )
    if (
        canonical_sha256(report) != fixture["report_hash"]
        or canonical_sha256(report_replay)
        != fixture["report_replay_credential_hash"]
        or canonical_sha256(outer) != fixture["outer_assessment_hash"]
        or canonical_sha256(outer_replay)
        != fixture["outer_replay_credential_hash"]
        or report.support_spec_hash != fixture["support_spec_hash"]
        or report.parameter_universe_hash
        != fixture["parameter_universe_hash"]
        or report.engine_code_hash
        != fixture["coverage_engine_code_hash"]
        or outer.verifier_code_hash
        != fixture["outer_verifier_code_hash"]
        or fixture["coverage_engine_code_hash"]
        != coverage_module_sha256()
        or fixture["outer_verifier_code_hash"]
        != confidence_module_sha256()
    ):
        raise ValueError("Task 4 fixture object or runtime binding changed")
    if (
        report_replay.report_hash != canonical_sha256(report)
        or report_replay.evaluation_input_bundle_hash
        != report.evaluation_input_bundle_hash
        or report_replay.evaluation_transcript_hash
        != report.evaluation_transcript_hash
        or report_replay.engine_code_hash != report.engine_code_hash
        or report_replay.verifier_configuration_hash
        != report.verifier_configuration_hash
    ):
        raise ValueError("Task 4 report replay is not bound to the report")
    if (
        outer_replay.assessment_hash != canonical_sha256(outer)
        or outer_replay.evaluation_input_bundle_hash
        != outer.evaluation_input_bundle_hash
        or outer_replay.exact_result_decision_transcript_hash
        != outer.exact_result_decision_transcript_hash
        or outer_replay.outer_result_decision_transcript_hash
        != outer.outer_result_decision_transcript_hash
        or outer_replay.paired_comparison_transcript_hash
        != outer.paired_comparison_transcript_hash
        or outer_replay.verifier_code_hash != outer.verifier_code_hash
        or outer_replay.verifier_configuration_hash
        != outer.verifier_configuration_hash
    ):
        raise ValueError("Task 4 outer replay is not bound to the assessment")
    if (
        outer.support_spec_hash != report.support_spec_hash
        or outer.support_plan_hash != report.support_plan_hash
        or outer.parameter_universe_hash != report.parameter_universe_hash
        or outer.probability_space_hash != report.probability_space_hash
        or outer.synthetic_prerequisites_hash
        != report.synthetic_prerequisites_hash
        or outer.sampling_law_manifest_hash
        != report.sampling_law_manifest_hash
        or outer.exact_procedure_hash
        != report.confidence_procedure_hash
        or outer.decision_rule_hash != report.decision_rule_hash
        or outer.outcome_count != report.outcome_count
    ):
        raise ValueError("Task 4 report and outer assessment disagree")
    if (
        len(mass_audits) != 3
        or len({audit.law_hash for audit in mass_audits}) != 3
        or any(
            audit.support_spec_hash != report.support_spec_hash
            or audit.support_plan_hash != report.support_plan_hash
            or audit.outcome_count != report.outcome_count
            for audit in mass_audits
        )
    ):
        raise ValueError("Task 4 mass audits do not cover the registered family")

    replay_root = live_run_dir / "verifier-replays"
    if replay_root.is_symlink():
        raise ValueError("Task 4 verifier replay root cannot be a symlink")
    replay_root.mkdir(exist_ok=True)
    replay_parent = Path(
        tempfile.mkdtemp(prefix="task4-live-replay-", dir=replay_root)
    )
    replay_fixture = replay_parent / "fixture"
    summary = build_fixture(
        project_root=project_root,
        output_dir=replay_fixture,
        artifact_root=artifact_root,
    )
    registered_names = EXPECTED_FIXTURE_ARTIFACTS | {
        "fixture_manifest.json"
    }
    for filename in registered_names:
        registered = path.parent / filename
        rebuilt = replay_fixture / filename
        if (
            rebuilt.is_symlink()
            or not rebuilt.is_file()
            or registered.read_bytes() != rebuilt.read_bytes()
        ):
            raise ValueError(
                f"Task 4 live rebuild differs from registered {filename}"
            )
    if summary["fixture_manifest_sha256"] != _sha256(path):
        raise ValueError("Task 4 live rebuild manifest hash changed")
    print(f"TASK4_LIVE_REPLAY_DIR={replay_parent}")
    return replay_parent


def verify_manifest(
    project_root: Path,
    manifest_path: Path,
    *,
    artifact_root: Path = ARTIFACT_ROOT,
) -> dict[str, object]:
    _verify_python_process_isolation(project_root, artifact_root)
    raw = _canonical_load(
        manifest_path,
        label="Task 4 acceptance manifest",
        expected_type=dict,
    )
    if set(raw) != EXPECTED_TOP_LEVEL_FIELDS:
        raise ValueError("Task 4 manifest top-level fields are not exact")
    if raw["schema"] != "d2t_rna.task4_acceptance_manifest.v2":
        raise ValueError("Task 4 manifest schema is unregistered")
    if raw["task"] != 4 or raw["status"] != "READY_FOR_COMMIT":
        raise ValueError("Task 4 manifest is not at its pre-commit gate")
    if raw["contract_sha256"] != CONTRACT_SHA256:
        raise ValueError("Task 4 manifest contract hash changed")
    if raw["registered_commit_title"] != COMMIT_TITLE:
        raise ValueError("Task 4 registered commit title changed")
    if raw["post_commit_closure_required"] is not True:
        raise ValueError("Task 4 must require a post-commit closure artifact")

    runtime = raw["runtime"]
    if type(runtime) is not dict or set(runtime) != {
        "python_version",
        "implementation",
        "python_cache_tag",
        "pydantic_version",
        "pydantic_core_version",
        "pytest_version",
        "python_executable_sha256",
        "dependency_snapshot_sha256",
        "gpu_required",
        "arithmetic",
    }:
        raise ValueError("Task 4 runtime record is not exact")
    live_dependency_snapshot = _runtime_dependency_snapshot(project_root)
    live_dependencies = live_dependency_snapshot["dependencies"]
    if type(live_dependencies) is not dict:
        raise TypeError("Task 4 live dependency snapshot is malformed")
    live_dependency_snapshot_sha256 = canonical_sha256(
        live_dependency_snapshot
    )
    _require_sha(
        runtime["python_executable_sha256"],
        label="runtime.python_executable_sha256",
    )
    _require_sha(
        runtime["dependency_snapshot_sha256"],
        label="runtime.dependency_snapshot_sha256",
    )
    if (
        runtime["implementation"] != platform.python_implementation()
        or runtime["implementation"] != "CPython"
        or runtime["python_version"] != platform.python_version()
        or type(runtime["python_version"]) is not str
        or not runtime["python_version"].startswith("3.11.")
        or runtime["python_cache_tag"] != sys.implementation.cache_tag
        or runtime["pydantic_version"] != pydantic.__version__
        or runtime["pydantic_version"]
        != live_dependencies["pydantic"]["version"]
        or runtime["pydantic_core_version"]
        != live_dependencies["pydantic_core"]["version"]
        or runtime["pytest_version"]
        != live_dependencies["pytest"]["version"]
        or runtime["python_executable_sha256"]
        != live_dependency_snapshot["python_executable_sha256"]
        or runtime["dependency_snapshot_sha256"]
        != live_dependency_snapshot_sha256
        or runtime["gpu_required"] is not False
        or runtime["arithmetic"] != "fractions.Fraction"
    ):
        raise ValueError("Task 4 runtime record violates the live frozen gate")

    gate_evidence = raw["gate_evidence"]
    if type(gate_evidence) is not dict or set(gate_evidence) != {
        "entry_gate",
        "red_test_record",
        "red_test_log",
    }:
        raise ValueError("Task 4 gate evidence is not exact")
    gate_paths = {
        name: _verify_external_file(
            record,
            label=f"gate_evidence.{name}",
            artifact_root=artifact_root,
        )
        for name, record in gate_evidence.items()
    }
    if len(set(gate_paths.values())) != len(gate_paths):
        raise ValueError("Task 4 gate evidence files must be distinct")
    _verify_gate_evidence(
        gate_evidence,
        gate_paths,
        artifact_root=artifact_root,
    )

    fixture_evidence = raw["fixture_evidence"]
    if type(fixture_evidence) is not dict or set(fixture_evidence) != {
        "manifest",
        "mathematical_statement_verified",
        "risk_certificate_issued",
        "formal_scientific_certificate_authorized",
        "prospective_claim_authorized",
        "new_library_claim_authorized",
        "serialized_bearer_authorization",
        "external_source_anchor_required",
    }:
        raise ValueError("Task 4 fixture evidence is not exact")
    fixture_path = _verify_external_file(
        fixture_evidence["manifest"],
        label="fixture_evidence.manifest",
        artifact_root=artifact_root,
    )
    if (
        fixture_evidence["mathematical_statement_verified"] is not True
        or fixture_evidence["risk_certificate_issued"] is not False
        or fixture_evidence[
            "formal_scientific_certificate_authorized"
        ]
        is not False
        or fixture_evidence["prospective_claim_authorized"] is not False
        or fixture_evidence["new_library_claim_authorized"] is not False
        or fixture_evidence["serialized_bearer_authorization"] is not False
        or fixture_evidence["external_source_anchor_required"] is not True
    ):
        raise ValueError("Task 4 fixture claim boundary changed")

    test_evidence = raw["test_evidence"]
    if type(test_evidence) is not dict or set(test_evidence) != {
        "run_id",
        "exact_tests_passed",
        "contract_probability_exact_tests_passed",
        "full_tests_passed",
        "run_log",
        "junit_evidence",
    }:
        raise ValueError("Task 4 test evidence is not exact")
    counts = (
        test_evidence["exact_tests_passed"],
        test_evidence["contract_probability_exact_tests_passed"],
        test_evidence["full_tests_passed"],
    )
    _validate_candidate_run_id(test_evidence["run_id"])
    if (
        any(type(count) is not int for count in counts)
        or counts[0] < 53
        or counts[1] < counts[0]
        or counts[2] < counts[1]
    ):
        raise ValueError("Task 4 test counts do not satisfy the acceptance gate")
    run_log_path = _verify_external_file(
        test_evidence["run_log"],
        label="test_evidence.run_log",
        artifact_root=artifact_root,
    )
    expected_run_log_path = (
        artifact_root
        / "runs"
        / test_evidence["run_id"]
        / "run.log"
    )
    _verify_exact_external_path_binding(
        test_evidence["run_log"],
        run_log_path,
        expected_path=expected_run_log_path,
        artifact_root=artifact_root,
        label="Task 4 candidate run log",
    )
    expected_fixture_path = (
        artifact_root
        / "runs"
        / test_evidence["run_id"]
        / "fixture"
        / "fixture_manifest.json"
    )
    _verify_exact_external_path_binding(
        fixture_evidence["manifest"],
        fixture_path,
        expected_path=expected_fixture_path,
        artifact_root=artifact_root,
        label="Task 4 fixture",
    )
    _verify_test_log(
        run_log_path,
        run_id=test_evidence["run_id"],
        runtime=runtime,
        fixture_manifest_sha256=fixture_evidence["manifest"]["sha256"],
        source_index_sha256=raw["source_index_sha256"],
        expected_counts=counts,
        artifact_root=artifact_root,
    )
    junit_evidence = test_evidence["junit_evidence"]
    if type(junit_evidence) is not dict or set(junit_evidence) != {
        "exact",
        "combined",
        "full",
    }:
        raise ValueError("Task 4 JUnit evidence set changed")
    for name, expected_count, filename in (
        ("exact", counts[0], "exact.xml"),
        ("combined", counts[1], "combined.xml"),
        ("full", counts[2], "full.xml"),
    ):
        junit_path = _verify_external_file(
            junit_evidence[name],
            label=f"test_evidence.junit_evidence.{name}",
            artifact_root=artifact_root,
        )
        expected_path = (
            artifact_root
            / "runs"
            / test_evidence["run_id"]
            / "junit"
            / filename
        )
        _verify_exact_external_path_binding(
            junit_evidence[name],
            junit_path,
            expected_path=expected_path,
            artifact_root=artifact_root,
            label=f"Task 4 {name} JUnit",
        )
        _verify_junit(
            junit_path,
            expected_count=expected_count,
            label=f"Task 4 {name} JUnit",
        )

    source_index = raw["source_index"]
    if (
        type(source_index) is not dict
        or set(source_index) != EXPECTED_SOURCE_PATHS
    ):
        raise ValueError("Task 4 source index is incomplete or contains extras")
    source_index_digest = _require_sha(
        raw["source_index_sha256"],
        label="source_index_sha256",
    )
    if source_index_digest != canonical_sha256(source_index):
        raise ValueError("Task 4 source-index digest does not replay")
    current_source_index = _source_index(project_root)
    for relative_path, expected_hash in source_index.items():
        _require_sha(expected_hash, label=f"source_index.{relative_path}")
        if current_source_index[relative_path] != expected_hash:
            raise ValueError(
                f"Task 4 source hash does not match: {relative_path}"
            )
    if source_index_digest != canonical_sha256(current_source_index):
        raise ValueError(
            "Task 4 source_index_sha256 does not match current source"
        )
    _verify_runtime_import_closure(
        project_root,
        source_index,
        dependency_snapshot=live_dependency_snapshot,
    )

    claim_boundary = raw["claim_boundary"]
    if type(claim_boundary) is not dict or claim_boundary != {
        "probability_scope": "SYNTHETIC_KNOWN_CHANNEL",
        "claim_domain": "EXACT_SYNTHETIC_KNOWN_CHANNEL_ONLY",
        "risk_certificate_issued": False,
        "formal_scientific_certificate_authorized": False,
        "prospective_claim_authorized": False,
        "new_library_claim_authorized": False,
        "observed_dataset_qa_completed": False,
        "scientific_conclusion_authorized": False,
    }:
        raise ValueError("Task 4 acceptance claim boundary changed")
    github = raw["github"]
    if type(github) is not dict or github != {
        "repository": "Cunyu-Liu/d2t-rna",
        "visibility": "PUBLIC",
        "branch": "main",
        "push_required_after_commit": True,
    }:
        raise ValueError("Task 4 GitHub publication contract changed")

    _verify_fixture(
        fixture_path,
        acceptance_record=fixture_evidence,
        project_root=project_root,
        artifact_root=artifact_root,
        live_run_dir=(
            artifact_root / "runs" / test_evidence["run_id"]
        ),
    )
    return raw


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    manifest_path = project_root / "manifests" / "task4_acceptance.json"
    verify_manifest(project_root, manifest_path)
    print("TASK4_MANIFEST_VERIFIED")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"TASK4_MANIFEST_REJECTED: {exc}", file=sys.stderr)
        raise
