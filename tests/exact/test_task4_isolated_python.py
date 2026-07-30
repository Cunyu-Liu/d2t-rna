from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import tests.exact.conftest as exact_conftest
from tests.exact.conftest import (
    TASK4_CHILD_ENVIRONMENT,
    TASK4_CHILD_RECEIPT_SCHEMA,
    TASK4_PROJECT_ROOT,
    run_task4_isolated_child,
    task4_isolated_child_command,
)
from scripts.task4_isolated_python import (
    IsolationViolation,
    _build_import_path,
    _explicit_project_paths,
    _parse_launcher_arguments,
    _reject_python_environment_inputs,
    _trusted_interpreter_paths,
    _validate_project_root_import_surface,
    _validate_runtime_envelope,
    _validate_site_packages_reserved_names,
    _validate_source_import_surface,
)
from scripts.verify_task4_acceptance_manifest import EXPECTED_SOURCE_PATHS


def _flags(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "isolated": 1,
        "no_site": 1,
        "no_user_site": 1,
        "ignore_environment": 1,
        "safe_path": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _fake_project(tmp_path: Path) -> Path:
    project_root = tmp_path / "project"
    (project_root / "src").mkdir(parents=True)
    (
        project_root
        / ".venv"
        / "lib"
        / "python3.11"
        / "site-packages"
    ).mkdir(parents=True)
    return project_root


def test_runtime_envelope_accepts_registered_cpython311(
    tmp_path: Path,
) -> None:
    pycache = tmp_path / "run" / "pycache"
    pycache.mkdir(parents=True)

    _validate_runtime_envelope(
        flags=_flags(),
        version_info=(3, 11, 15),
        implementation="CPython",
        loaded_module_names=frozenset({"sys", "pathlib"}),
        actual_pycache_prefix=str(pycache),
        expected_pycache_prefix=pycache,
    )


def test_python_environment_inputs_include_leading_underscore_forms() -> None:
    _reject_python_environment_inputs({"PATH": "/usr/bin"})
    for name in (
        "PYTHONPATH",
        "PYTHONHASHSEED",
        "_PYTHON_SYSCONFIGDATA_NAME",
        "_PYTHON_HOST_PLATFORM",
    ):
        with pytest.raises(IsolationViolation, match=name):
            _reject_python_environment_inputs(
                {"PATH": "/usr/bin", name: "injected"}
            )


@pytest.mark.parametrize(
    ("override", "message"),
    (
        ({"isolated": 0}, "isolated"),
        ({"no_site": 0}, "no_site"),
        ({"no_user_site": 0}, "no_user_site"),
        ({"ignore_environment": 0}, "ignore_environment"),
        ({"safe_path": False}, "safe_path"),
    ),
)
def test_runtime_envelope_rejects_missing_isolation_flag(
    tmp_path: Path,
    override: dict[str, object],
    message: str,
) -> None:
    pycache = tmp_path / "pycache"
    pycache.mkdir()

    with pytest.raises(IsolationViolation, match=message):
        _validate_runtime_envelope(
            flags=_flags(**override),
            version_info=(3, 11),
            implementation="CPython",
            loaded_module_names=frozenset(),
            actual_pycache_prefix=str(pycache),
            expected_pycache_prefix=pycache,
        )


@pytest.mark.parametrize(
    ("version_info", "implementation"),
    (
        ((3, 12), "CPython"),
        ((3, 11), "PyPy"),
    ),
)
def test_runtime_envelope_rejects_wrong_interpreter(
    tmp_path: Path,
    version_info: tuple[int, int],
    implementation: str,
) -> None:
    pycache = tmp_path / "pycache"
    pycache.mkdir()

    with pytest.raises(IsolationViolation, match="CPython 3.11"):
        _validate_runtime_envelope(
            flags=_flags(),
            version_info=version_info,
            implementation=implementation,
            loaded_module_names=frozenset(),
            actual_pycache_prefix=str(pycache),
            expected_pycache_prefix=pycache,
        )


def test_runtime_envelope_rejects_unbound_pycache(
    tmp_path: Path,
) -> None:
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    expected.mkdir()
    actual.mkdir()

    with pytest.raises(IsolationViolation, match="does not match"):
        _validate_runtime_envelope(
            flags=_flags(),
            version_info=(3, 11),
            implementation="CPython",
            loaded_module_names=frozenset(),
            actual_pycache_prefix=str(actual),
            expected_pycache_prefix=expected,
        )


def test_runtime_envelope_rejects_loaded_site_module(
    tmp_path: Path,
) -> None:
    pycache = tmp_path / "pycache"
    pycache.mkdir()

    with pytest.raises(IsolationViolation, match="site initialization"):
        _validate_runtime_envelope(
            flags=_flags(),
            version_info=(3, 11),
            implementation="CPython",
            loaded_module_names=frozenset({"sitecustomize"}),
            actual_pycache_prefix=str(pycache),
            expected_pycache_prefix=pycache,
        )


def test_trusted_interpreter_paths_retain_only_stdlib(
    tmp_path: Path,
) -> None:
    stdlib = tmp_path / "lib" / "python3.11"
    dynload = stdlib / "lib-dynload"
    dynload.mkdir(parents=True)
    stdlib_zip = stdlib.parent / "python311.zip"

    observed = _trusted_interpreter_paths(
        (str(stdlib_zip), str(stdlib), str(dynload)),
        stdlib_roots=(stdlib,),
        version_info=(3, 11),
    )

    assert observed == (
        str(stdlib.resolve()),
        str(dynload.resolve()),
    )
    stdlib_zip.write_bytes(b"unauthorized zip bytes")
    with pytest.raises(IsolationViolation, match="zip archive"):
        _trusted_interpreter_paths(
            (str(stdlib_zip), str(stdlib), str(dynload)),
            stdlib_roots=(stdlib,),
            version_info=(3, 11),
        )
    stdlib_zip.unlink()
    with pytest.raises(
        IsolationViolation,
        match="unavailable stdlib|non-stdlib",
    ):
        _trusted_interpreter_paths(
            (*observed, str(tmp_path / "injected")),
            stdlib_roots=(stdlib,),
            version_info=(3, 11),
        )


def test_project_import_paths_are_exact_and_do_not_process_pth(
    tmp_path: Path,
) -> None:
    project_root = _fake_project(tmp_path)
    site_packages = (
        project_root
        / ".venv"
        / "lib"
        / "python3.11"
        / "site-packages"
    )
    sentinel = tmp_path / "pth-executed"
    (site_packages / "untrusted.pth").write_text(
        f"import pathlib; pathlib.Path({str(sentinel)!r}).touch()\n",
        encoding="utf-8",
    )

    project_paths = _explicit_project_paths(project_root)
    result = _build_import_path(
        trusted_interpreter_paths=("/trusted/stdlib",),
        project_paths=project_paths,
    )

    assert result == [
        "/trusted/stdlib",
        str(site_packages),
        str(project_root / "src"),
        str(project_root),
    ]
    assert not sentinel.exists()


@pytest.mark.parametrize("filename", ("pydantic.py", "pytest.py"))
def test_project_root_rejects_dependency_shadow_modules(
    tmp_path: Path,
    filename: str,
) -> None:
    project_root = _fake_project(tmp_path)
    (project_root / filename).write_text(
        "raise RuntimeError('shadowed')\n",
        encoding="utf-8",
    )

    with pytest.raises(
        IsolationViolation,
        match="unregistered import surface",
    ):
        _validate_project_root_import_surface(project_root)
    with pytest.raises(
        IsolationViolation,
        match="unregistered import surface",
    ):
        _explicit_project_paths(project_root)


def test_project_root_rejects_unregistered_namespace_package(
    tmp_path: Path,
) -> None:
    project_root = _fake_project(tmp_path)
    (project_root / "pydantic").mkdir()

    with pytest.raises(
        IsolationViolation,
        match="unregistered import surface",
    ):
        _validate_project_root_import_surface(project_root)


def test_source_root_rejects_pytest_shadow_before_target(
    tmp_path: Path,
) -> None:
    project_root = _fake_project(tmp_path)
    source_root = project_root / "src"
    (source_root / "pytest.py").write_text(
        "raise RuntimeError('shadowed pytest')\n",
        encoding="utf-8",
    )

    with pytest.raises(
        IsolationViolation,
        match="source root contains an unregistered import surface",
    ):
        _validate_source_import_surface(source_root)
    with pytest.raises(
        IsolationViolation,
        match="source root contains an unregistered import surface",
    ):
        _explicit_project_paths(project_root)


@pytest.mark.parametrize(
    ("name", "as_namespace"),
    (
        ("d2t_rna", False),
        ("scripts", False),
        ("tests", True),
    ),
)
def test_site_packages_cannot_resolve_reserved_project_names(
    tmp_path: Path,
    name: str,
    as_namespace: bool,
) -> None:
    project_root = _fake_project(tmp_path)
    site_packages = (
        project_root
        / ".venv"
        / "lib"
        / "python3.11"
        / "site-packages"
    )
    if as_namespace:
        (site_packages / name).mkdir()
    else:
        (site_packages / f"{name}.py").write_text(
            "raise RuntimeError('shadowed project import')\n",
            encoding="utf-8",
        )

    with pytest.raises(
        IsolationViolation,
        match="reserved project imports",
    ):
        _validate_site_packages_reserved_names(site_packages)
    with pytest.raises(
        IsolationViolation,
        match="reserved project imports",
    ):
        _explicit_project_paths(project_root)


def test_project_import_paths_reject_symlinked_site_packages(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    (project_root / "src").mkdir(parents=True)
    outside = tmp_path / "outside-site-packages"
    outside.mkdir()
    site_parent = (
        project_root / ".venv" / "lib" / "python3.11"
    )
    site_parent.mkdir(parents=True)
    (site_parent / "site-packages").symlink_to(
        outside,
        target_is_directory=True,
    )

    with pytest.raises(IsolationViolation, match="unsafe"):
        _explicit_project_paths(project_root)


def test_launcher_argument_parser_preserves_target_cli() -> None:
    project_root, pycache, target = _parse_launcher_arguments(
        (
            "--project-root",
            "/project",
            "--pycache-prefix",
            "/artifacts/run/pycache",
            "--",
            "-m",
            "pytest",
            "-q",
            "tests/exact",
            "--junitxml=/artifacts/run/junit.xml",
        )
    )

    assert project_root == Path("/project")
    assert pycache == Path("/artifacts/run/pycache")
    assert target == (
        "-m",
        "pytest",
        "-q",
        "tests/exact",
        "--junitxml=/artifacts/run/junit.xml",
    )


def test_nested_child_command_is_the_registered_isolated_shape(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "child"
    command = task4_isolated_child_command(
        child_artifact_dir=artifact_dir,
        source="print('registered child')",
        arguments=("argument",),
    )

    pycache = artifact_dir / "pycache"
    assert command == (
        str(TASK4_PROJECT_ROOT / ".venv" / "bin" / "python"),
        "-I",
        "-S",
        "-X",
        f"pycache_prefix={pycache}",
        str(
            TASK4_PROJECT_ROOT
            / "scripts"
            / "task4_isolated_python.py"
        ),
        "--project-root",
        str(TASK4_PROJECT_ROOT),
        "--pycache-prefix",
        str(pycache),
        "--",
        "-c",
        "print('registered child')",
        "argument",
    )
    assert not any(
        name.startswith(("PYTHON", "_PYTHON"))
        for name in TASK4_CHILD_ENVIRONMENT
    )


def test_registered_nested_call_sites_cannot_bypass_the_helper() -> None:
    expected_helper_calls = {
        "tests/exact/test_coverage.py": 2,
        "tests/contracts/test_canonical.py": 1,
        "tests/exact/test_task4_isolated_python.py": 3,
    }
    test_sources = tuple(
        sorted(
            relative
            for relative in EXPECTED_SOURCE_PATHS
            if relative.startswith("tests/") and relative.endswith(".py")
            and relative != "tests/exact/conftest.py"
        )
    )
    assert set(expected_helper_calls).issubset(test_sources)
    for relative in test_sources:
        tree = ast.parse(
            (TASK4_PROJECT_ROOT / relative).read_text(encoding="utf-8")
        )
        helper_calls = tuple(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "run_task4_isolated_child"
        )
        direct_executable_reads = tuple(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "sys"
            and node.attr == "executable"
        )
        direct_subprocess_calls = tuple(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
        )
        assert len(helper_calls) == expected_helper_calls.get(relative, 0), (
            relative
        )
        assert direct_executable_reads == (), relative
        assert direct_subprocess_calls == (), relative


def test_nested_child_helper_binds_parent_cache_and_live_closure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    python_bin = project_root / ".venv" / "bin" / "python"
    launcher = project_root / "scripts" / "task4_isolated_python.py"
    python_bin.parent.mkdir(parents=True)
    launcher.parent.mkdir(parents=True)
    python_bin.write_text("registered python bytes\n", encoding="utf-8")
    python_bin.chmod(0o755)
    launcher.write_text("registered launcher bytes\n", encoding="utf-8")

    artifact_root = tmp_path / "registered-artifacts"
    parent_pycache = (
        artifact_root / "runs" / "candidate" / "pycache"
    )
    parent_pycache.mkdir(parents=True)
    monkeypatch.setattr(
        exact_conftest,
        "TASK4_PROJECT_ROOT",
        project_root,
    )
    monkeypatch.setattr(
        exact_conftest,
        "TASK4_ARTIFACT_ROOT",
        artifact_root,
    )
    monkeypatch.setattr(sys, "pycache_prefix", str(parent_pycache))

    observed: dict[str, object] = {}
    receipt_nonce = "f" * 64
    target_source = "print('target output')"
    monkeypatch.setattr(
        exact_conftest.secrets,
        "token_hex",
        lambda size: receipt_nonce,
    )
    monkeypatch.setenv(
        exact_conftest.TASK4_PARENT_DEPENDENCY_DIGEST_ENV,
        "a" * 64,
    )
    monkeypatch.setenv(
        exact_conftest.TASK4_PARENT_SOURCE_DIGEST_ENV,
        "b" * 64,
    )

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed.update(kwargs)
        cache = Path(
            next(
                item.partition("=")[2]
                for item in command
                if item.startswith("pycache_prefix=")
            )
        )
        receipt = {
            "dependency_snapshot_sha256": "a" * 64,
            "nonce": receipt_nonce,
            "pycache_prefix": str(cache),
            "schema": TASK4_CHILD_RECEIPT_SCHEMA,
            "source_index_sha256": "b" * 64,
            "target_source_sha256": exact_conftest.hashlib.sha256(
                target_source.encode("utf-8")
            ).hexdigest(),
        }
        receipt_path = cache / "runtime-closure-receipt.json"
        receipt_path.write_bytes(
            exact_conftest.canonical_json_bytes(receipt) + b"\n"
        )
        receipt_path.chmod(0o600)
        return SimpleNamespace(
            args=command,
            returncode=0,
            stdout="target output\n",
            stderr="target diagnostics are not a receipt channel\n",
        )

    monkeypatch.setattr(exact_conftest.subprocess, "run", fake_run)
    completed = run_task4_isolated_child(
        child_artifact_dir=tmp_path / "child-artifact",
        source=target_source,
    )

    command = observed["command"]
    assert isinstance(command, tuple)
    cache_argument = next(
        item.partition("=")[2]
        for item in command
        if item.startswith("pycache_prefix=")
    )
    nested_cache = Path(cache_argument)
    assert nested_cache.parent == parent_pycache
    assert nested_cache.is_dir()
    assert observed["cwd"] == str(project_root)
    assert observed["env"] == TASK4_CHILD_ENVIRONMENT
    assert command[:4] == (
        str(python_bin),
        "-I",
        "-S",
        "-X",
    )
    wrapped_source = command[command.index("-c") + 1]
    assert "_verify_python_process_isolation" in wrapped_source
    assert "_verify_runtime_import_closure" in wrapped_source
    assert str(artifact_root) in wrapped_source
    verifier_import = wrapped_source.index(
        "from scripts.verify_task4_acceptance_manifest import"
    )
    target_execution = wrapped_source.index(
        "exec("
    )
    pre_snapshot = wrapped_source.index(
        "_task4_nested_pre_dependencies ="
    )
    post_snapshot = wrapped_source.index(
        "_task4_nested_post_dependencies ="
    )
    assert verifier_import < pre_snapshot < target_execution < post_snapshot
    assert (
        "_task4_nested_post_index != _task4_nested_pre_index"
        in wrapped_source
    )
    assert "nested child changed the dependency snapshot" in wrapped_source
    assert "except BaseException as _task4_nested_target_error" in (
        wrapped_source
    )
    assert TASK4_CHILD_RECEIPT_SCHEMA in wrapped_source
    assert receipt_nonce in wrapped_source
    assert completed.returncode == 0


def test_real_nested_child_has_exact_isolated_runtime(
    tmp_path: Path,
) -> None:
    source = """
import _decimal
import importlib.machinery
import json
import os
import sys
from scripts.verify_task4_acceptance_manifest import (
    _FROZEN_STDLIB_NATIVE_MODULE_DEFINITION_NAMES,
)

print("TASK4_NESTED_CHILD_RUNTIME_CLOSURE_PASS", file=sys.stderr)
print(json.dumps(
    {
        "decimal_metadata": {
            "frozen_definition_name": (
                _FROZEN_STDLIB_NATIVE_MODULE_DEFINITION_NAMES["_decimal"]
            ),
            "loader_is_exact_extension": (
                type(_decimal.__spec__.loader)
                is importlib.machinery.ExtensionFileLoader
            ),
            "module_name": _decimal.__name__,
            "spec_name": _decimal.__spec__.name,
        },
        "environment": dict(os.environ),
        "flags": {
            "ignore_environment": sys.flags.ignore_environment,
            "isolated": sys.flags.isolated,
            "no_site": sys.flags.no_site,
            "no_user_site": sys.flags.no_user_site,
            "safe_path": sys.flags.safe_path,
        },
        "pycache_prefix": sys.pycache_prefix,
        "site_modules": sorted(
            {"site", "sitecustomize", "usercustomize"} & set(sys.modules)
        ),
        "sys_path": list(sys.path),
        "version": list(sys.version_info[:2]),
    },
    sort_keys=True,
))
"""
    artifact_dir = tmp_path / "real-isolated-child"
    completed = run_task4_isolated_child(
        child_artifact_dir=artifact_dir,
        source=source,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)

    stdlib = TASK4_PROJECT_ROOT / ".venv" / "lib" / "python3.11"
    observed_pycache = Path(payload.pop("pycache_prefix"))
    if type(sys.pycache_prefix) is str:
        assert observed_pycache.parent == Path(sys.pycache_prefix)
    else:
        assert observed_pycache == (
            artifact_dir
            / "runtime-artifacts"
            / "runs"
            / "nested-child"
            / "pycache"
        )
    assert observed_pycache.is_dir()
    assert not observed_pycache.is_symlink()
    assert observed_pycache.resolve() == observed_pycache
    receipt_path = observed_pycache / "runtime-closure-receipt.json"
    assert receipt_path.is_file()
    receipt = json.loads(receipt_path.read_bytes())
    assert "TASK4_NESTED_CHILD_RUNTIME_CLOSURE_PASS" in completed.stderr
    assert receipt["schema"] == TASK4_CHILD_RECEIPT_SCHEMA
    assert receipt["pycache_prefix"] == str(observed_pycache)
    if type(sys.pycache_prefix) is str:
        assert receipt["dependency_snapshot_sha256"] == (
            exact_conftest.os.environ[
                exact_conftest.TASK4_PARENT_DEPENDENCY_DIGEST_ENV
            ]
        )
        assert receipt["source_index_sha256"] == (
            exact_conftest.os.environ[
                exact_conftest.TASK4_PARENT_SOURCE_DIGEST_ENV
            ]
        )
    assert payload == {
        "decimal_metadata": {
            "frozen_definition_name": "decimal",
            "loader_is_exact_extension": True,
            "module_name": "decimal",
            "spec_name": "_decimal",
        },
        "environment": TASK4_CHILD_ENVIRONMENT,
        "flags": {
            "ignore_environment": 1,
            "isolated": 1,
            "no_site": 1,
            "no_user_site": 1,
            "safe_path": True,
        },
        "site_modules": [],
        "sys_path": [
            str(stdlib),
            str(stdlib / "lib-dynload"),
            str(stdlib / "site-packages"),
            str(TASK4_PROJECT_ROOT / "src"),
            str(TASK4_PROJECT_ROOT),
        ],
        "version": [3, 11],
    }


@pytest.mark.parametrize(
    ("source", "abrupt_success"),
    (
        (
            "import sys\n"
            "print('TASK4_NESTED_CHILD_RUNTIME_CLOSURE_PASS', "
            "file=sys.stderr)\n"
            "raise SystemExit(0)\n",
            False,
        ),
        (
            "import os\n"
            "os._exit(0)\n",
            True,
        ),
    ),
)
def test_nested_child_cannot_forge_runtime_closure_receipt(
    tmp_path: Path,
    source: str,
    abrupt_success: bool,
) -> None:
    artifact_dir = tmp_path / (
        "abrupt-success" if abrupt_success else "system-exit"
    )
    try:
        completed = run_task4_isolated_child(
            child_artifact_dir=artifact_dir,
            source=source,
        )
    except RuntimeError as exc:
        assert abrupt_success is True
        assert "omitted" in str(exc) and "receipt" in str(exc)
    else:
        assert abrupt_success is False
        assert completed.returncode != 0
        assert "target did not return normally" in completed.stderr
