#!/usr/bin/env python3
"""Run a Python target inside the registered Task 4 isolation envelope.

The shell runners start this file with CPython ``-I -S`` and a run-specific
``-X pycache_prefix``.  This launcher then reconstructs the smallest useful
import path without invoking :mod:`site`: trusted interpreter stdlib entries,
the pinned Python 3.11 virtual-environment packages, the project's ``src``,
and finally the project root.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import importlib.machinery
import os
from pathlib import Path
import platform
import runpy
import sys
import sysconfig
from typing import NoReturn


class IsolationViolation(RuntimeError):
    """Raised when the Task 4 Python trust boundary is not satisfied."""


REGISTERED_ROOT_DIRECTORIES = frozenset(
    {
        "contracts",
        "docs",
        "manifests",
        "scripts",
        "src",
        "tests",
    }
)
REGISTERED_SOURCE_PACKAGES = frozenset({"d2t_rna"})
RESERVED_PROJECT_TOP_LEVEL_NAMES = frozenset(
    {"d2t_rna", "scripts", "tests"}
)


def _reject_python_environment_inputs(
    environ: Mapping[str, str],
) -> None:
    """Reject Python control variables, including leading-underscore forms."""

    forbidden = tuple(
        sorted(
            name
            for name in environ
            if name.startswith(("PYTHON", "_PYTHON"))
        )
    )
    if forbidden:
        raise IsolationViolation(
            "Task 4 isolated launcher retained Python environment inputs: "
            + ", ".join(forbidden)
        )


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validate_runtime_envelope(
    *,
    flags: object,
    version_info: Sequence[int],
    implementation: str,
    loaded_module_names: frozenset[str],
    actual_pycache_prefix: str | None,
    expected_pycache_prefix: Path,
) -> None:
    """Fail closed unless the process is the registered isolated CPython."""

    if implementation != "CPython" or tuple(version_info[:2]) != (3, 11):
        raise IsolationViolation(
            "Task 4 requires CPython 3.11 under the isolated launcher"
        )
    required_flags = {
        "isolated": 1,
        "no_site": 1,
        "no_user_site": 1,
        "ignore_environment": 1,
        "safe_path": True,
    }
    for name, expected in required_flags.items():
        if getattr(flags, name, None) != expected:
            raise IsolationViolation(
                f"Task 4 Python isolation flag is not bound: {name}"
            )
    loaded_site_modules = frozenset(
        {"site", "sitecustomize", "usercustomize"} & loaded_module_names
    )
    if loaded_site_modules:
        raise IsolationViolation(
            "Task 4 Python started after site initialization: "
            + ", ".join(sorted(loaded_site_modules))
        )
    if type(actual_pycache_prefix) is not str:
        raise IsolationViolation(
            "Task 4 Python requires an explicit pycache prefix"
        )
    if (
        not expected_pycache_prefix.is_absolute()
        or expected_pycache_prefix.is_symlink()
        or not expected_pycache_prefix.is_dir()
    ):
        raise IsolationViolation(
            "Task 4 pycache prefix must be an existing absolute "
            "non-symlink directory"
        )
    if (
        Path(actual_pycache_prefix).resolve()
        != expected_pycache_prefix.resolve()
    ):
        raise IsolationViolation(
            "Task 4 Python pycache prefix does not match the runner binding"
        )


def _trusted_interpreter_paths(
    raw_paths: Sequence[str],
    *,
    stdlib_roots: Sequence[Path],
    version_info: Sequence[int],
) -> tuple[str, ...]:
    """Retain only interpreter-provided stdlib paths from isolated startup."""

    roots = tuple(root.resolve() for root in stdlib_roots)
    zip_name = f"python{version_info[0]}{version_info[1]}.zip"
    zip_paths = frozenset((root.parent / zip_name).resolve() for root in roots)
    trusted: list[str] = []
    for raw_path in raw_paths:
        if type(raw_path) is not str or not raw_path:
            raise IsolationViolation(
                "Task 4 isolated startup exposed a relative import path"
            )
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            raise IsolationViolation(
                "Task 4 isolated startup exposed a non-absolute import path"
            )
        lexical = Path(os.path.abspath(candidate))
        if lexical in zip_paths:
            if lexical.exists() or lexical.is_symlink():
                raise IsolationViolation(
                    "Task 4 isolated startup exposed an unauthorized "
                    f"stdlib zip archive: {raw_path}"
                )
            # CPython inserts this absent archive path by default.  The
            # launcher deliberately removes it from the rebuilt sys.path.
            continue
        try:
            resolved = lexical.resolve(strict=True)
        except OSError as exc:
            raise IsolationViolation(
                "Task 4 isolated startup exposed an unavailable stdlib "
                f"path: {raw_path}"
            ) from exc
        if (
            lexical != resolved
            or resolved.is_symlink()
            or not resolved.is_dir()
        ):
            raise IsolationViolation(
                "Task 4 isolated startup exposed an unsafe stdlib path: "
                f"{raw_path}"
            )
        if not (
            any(_is_within(resolved, root) for root in roots)
        ):
            raise IsolationViolation(
                "Task 4 isolated startup exposed a non-stdlib import path: "
                f"{raw_path}"
            )
        rendered = str(resolved)
        if rendered not in trusted:
            trusted.append(rendered)
    if not trusted:
        raise IsolationViolation(
            "Task 4 isolated startup exposed no trusted stdlib paths"
        )
    return tuple(trusted)


def _has_symlink_component(root: Path, path: Path) -> bool:
    """Return whether ``path`` traverses a symlink at or below ``root``."""

    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    cursor = root
    if cursor.is_symlink():
        return True
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            return True
    return False


def _is_native_extension(path: Path) -> bool:
    """Return whether a root entry has a CPython native-module suffix."""

    return any(
        path.name.endswith(suffix)
        for suffix in importlib.machinery.EXTENSION_SUFFIXES
    )


def _validate_project_root_import_surface(project_root: Path) -> None:
    """Reject project-root import shadowing before any target is imported."""

    unregistered: list[str] = []
    for path in project_root.iterdir():
        if path.is_symlink():
            if (
                path.name in REGISTERED_ROOT_DIRECTORIES
                or path.name.isidentifier()
                or path.suffix in {".py", ".pyi", ".pyc"}
                or _is_native_extension(path)
            ):
                unregistered.append(path.name)
            continue
        if path.is_file():
            if (
                path.suffix in {".py", ".pyi", ".pyc"}
                or _is_native_extension(path)
            ):
                unregistered.append(path.name)
            continue
        if (
            path.is_dir()
            and path.name.isidentifier()
            and path.name not in REGISTERED_ROOT_DIRECTORIES
        ):
            unregistered.append(path.name)
    if unregistered:
        raise IsolationViolation(
            "Task 4 project root contains an unregistered import surface: "
            + ", ".join(sorted(unregistered))
        )


def _validate_source_import_surface(source_root: Path) -> None:
    """Reject top-level source modules that could shadow trusted imports."""

    unregistered: list[str] = []
    for path in source_root.iterdir():
        if path.is_symlink():
            if (
                path.name in REGISTERED_SOURCE_PACKAGES
                or path.name.isidentifier()
                or path.suffix in {".py", ".pyi", ".pyc"}
                or _is_native_extension(path)
            ):
                unregistered.append(path.name)
            continue
        if path.is_file():
            if (
                path.suffix in {".py", ".pyi", ".pyc"}
                or _is_native_extension(path)
            ):
                unregistered.append(path.name)
            continue
        if (
            path.is_dir()
            and path.name.isidentifier()
            and path.name not in REGISTERED_SOURCE_PACKAGES
        ):
            unregistered.append(path.name)
    if unregistered:
        raise IsolationViolation(
            "Task 4 source root contains an unregistered import surface: "
            + ", ".join(sorted(unregistered))
        )


def _validate_site_packages_reserved_names(site_packages: Path) -> None:
    """Reject third-party paths that can shadow project-owned top-level names."""

    shadowed = tuple(
        name
        for name in sorted(RESERVED_PROJECT_TOP_LEVEL_NAMES)
        if importlib.machinery.PathFinder.find_spec(
            name,
            [str(site_packages)],
        )
        is not None
    )
    if shadowed:
        raise IsolationViolation(
            "Task 4 site-packages can resolve reserved project imports: "
            + ", ".join(shadowed)
        )


def _explicit_project_paths(project_root: Path) -> tuple[str, str, str]:
    """Validate and return the only project-controlled import directories."""

    if not project_root.is_absolute():
        raise IsolationViolation("Task 4 project root must be absolute")
    if (
        not project_root.is_dir()
        or project_root.is_symlink()
        or project_root.resolve() != project_root
    ):
        raise IsolationViolation(
            "Task 4 project root must be a canonical non-symlink directory"
        )
    _validate_project_root_import_surface(project_root)
    src = project_root / "src"
    site_packages = (
        project_root
        / ".venv"
        / "lib"
        / "python3.11"
        / "site-packages"
    )
    for label, path in (
        ("source", src),
        ("virtual-environment site-packages", site_packages),
    ):
        if (
            not path.is_dir()
            or _has_symlink_component(project_root, path)
            or not _is_within(path.resolve(), project_root)
        ):
            raise IsolationViolation(
                f"Task 4 {label} import directory is unavailable or unsafe"
            )
    _validate_site_packages_reserved_names(site_packages)
    _validate_source_import_surface(src)
    return str(site_packages), str(src), str(project_root)


def _build_import_path(
    *,
    trusted_interpreter_paths: Sequence[str],
    project_paths: Sequence[str],
) -> list[str]:
    """Build a deterministic path without processing ``.pth`` files."""

    result: list[str] = []
    for raw_path in (*trusted_interpreter_paths, *project_paths):
        if raw_path not in result:
            result.append(raw_path)
    return result


def _parse_launcher_arguments(
    argv: Sequence[str],
) -> tuple[Path, Path, tuple[str, ...]]:
    parser = argparse.ArgumentParser(
        description="Run one Python target in the Task 4 isolation envelope"
    )
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--pycache-prefix", required=True, type=Path)
    parser.add_argument("target", nargs=argparse.REMAINDER)
    parsed = parser.parse_args(tuple(argv))
    target = tuple(parsed.target)
    if target[:1] == ("--",):
        target = target[1:]
    if not target:
        parser.error("a Python target is required after --")
    return parsed.project_root, parsed.pycache_prefix, target


def _run_target(project_root: Path, target: Sequence[str]) -> None:
    """Execute the supported subset of Python's CLI without another process."""

    head = target[0]
    if head == "-m":
        if len(target) < 2 or not target[1] or target[1].startswith("-"):
            raise IsolationViolation("Task 4 -m requires a module name")
        module_name = target[1]
        sys.argv = [module_name, *target[2:]]
        runpy.run_module(module_name, run_name="__main__", alter_sys=True)
        return
    if head == "-c":
        if len(target) < 2:
            raise IsolationViolation("Task 4 -c requires source text")
        sys.argv = ["-c", *target[2:]]
        namespace = {
            "__builtins__": __builtins__,
            "__name__": "__main__",
            "__package__": None,
            "__spec__": None,
        }
        exec(compile(target[1], "<string>", "exec"), namespace, namespace)
        return
    if head.startswith("-"):
        raise IsolationViolation(
            f"Task 4 launcher does not support Python option: {head}"
        )

    raw_script = Path(head)
    script = (
        raw_script if raw_script.is_absolute() else project_root / raw_script
    )
    if (
        script.suffix != ".py"
        or not script.is_file()
        or _has_symlink_component(project_root, script)
        or not _is_within(script.resolve(), project_root)
    ):
        raise IsolationViolation(
            "Task 4 script target must be a non-symlink project Python file"
        )
    sys.argv = [str(script), *target[1:]]
    runpy.run_path(str(script), run_name="__main__")


def _abort(message: str) -> NoReturn:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main(argv: Sequence[str] | None = None) -> int:
    project_root, pycache_prefix, target = _parse_launcher_arguments(
        sys.argv[1:] if argv is None else argv
    )
    try:
        _reject_python_environment_inputs(os.environ)
        _validate_runtime_envelope(
            flags=sys.flags,
            version_info=sys.version_info,
            implementation=platform.python_implementation(),
            loaded_module_names=frozenset(sys.modules),
            actual_pycache_prefix=sys.pycache_prefix,
            expected_pycache_prefix=pycache_prefix,
        )
        paths = sysconfig.get_paths()
        trusted = _trusted_interpreter_paths(
            tuple(sys.path),
            stdlib_roots=(
                Path(paths["stdlib"]),
                Path(paths["platstdlib"]),
            ),
            version_info=sys.version_info,
        )
        project_paths = _explicit_project_paths(project_root)
        sys.path[:] = _build_import_path(
            trusted_interpreter_paths=trusted,
            project_paths=project_paths,
        )
        _run_target(project_root, target)
    except IsolationViolation as exc:
        _abort(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
