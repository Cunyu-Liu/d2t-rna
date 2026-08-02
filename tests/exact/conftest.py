from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys
import tempfile
from textwrap import dedent

import pytest

from d2t_rna.contracts.base import canonical_json_bytes, canonical_sha256
from d2t_rna.contracts.enums import ProbabilityScope
from d2t_rna.contracts.primitives import (
    ObjectCommitment,
    ProofArtifactRef,
    Rational,
)
from d2t_rna.contracts.probability import ProbabilitySpaceSpec
from d2t_rna.exact.confidence import (
    ExactSamplingLawEntry,
    ExactSamplingLawManifest,
    ExactParameterFamily,
    ExactParameterPoint,
    HypothesisThresholds,
    exact_parameter_registry_hash,
)
from d2t_rna.exact.enumerate import (
    IndependentActionProbabilities,
    IndependentMultinomialLaw,
)
from d2t_rna.exact.support import ExactActionSpec, ExactSupportSpec
from d2t_rna.probability.registry import (
    SemanticRegistryRole,
    TrustedSemanticRegistry,
    load_trusted_task2_registry,
)
from d2t_rna.probability.scopes import (
    SyntheticKnownChannelPrerequisites,
)


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
SHA_E = "e" * 64

TASK4_PROJECT_ROOT = Path(__file__).resolve().parents[2]
TASK4_ARTIFACT_ROOT = Path("/mnt/cunyuliu/d2t-rna/artifacts")
TASK4_CHILD_ENVIRONMENT = {
    "HOME": "/nonexistent",
    "USER": "cunyuliu",
    "LOGNAME": "cunyuliu",
    "PATH": "/usr/bin:/bin",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "TZ": "Asia/Shanghai",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
}
TASK4_CHILD_RECEIPT_SCHEMA = (
    "d2t_rna.task4_nested_child_runtime_closure_receipt.v1"
)
TASK4_PARENT_DEPENDENCY_DIGEST_ENV = (
    "TASK4_REGISTERED_DEPENDENCY_SNAPSHOT_SHA256"
)
TASK4_PARENT_SOURCE_DIGEST_ENV = "TASK4_REGISTERED_SOURCE_INDEX_SHA256"


def _task4_child_source_with_runtime_closure(
    *,
    source: str,
    artifact_root: Path,
    receipt_path: Path,
    receipt_nonce: str,
    target_source_sha256: str,
) -> str:
    """Freeze, execute, and replay the nested-child runtime closure."""

    return dedent(
        f"""\
        import hashlib as _task4_nested_hashlib
        import os as _task4_nested_os
        from pathlib import Path as _Task4NestedPath
        import sys as _task4_nested_sys
        from scripts.verify_task4_acceptance_manifest import (
            EXPECTED_SOURCE_PATHS as _task4_nested_historical_paths,
            _runtime_dependency_snapshot as _task4_nested_dependency_snapshot,
            _verify_python_process_isolation as _task4_nested_verify_process,
            _verify_runtime_import_closure as _task4_nested_verify_closure,
            canonical_json_bytes as _task4_nested_canonical_json_bytes,
            canonical_sha256 as _task4_nested_canonical_sha256,
        )

        def _task4_nested_historical_regression_index(root):
            index = {{}}
            for relative in sorted(_task4_nested_historical_paths):
                path = root / relative
                if path.is_symlink() or not path.is_file():
                    raise RuntimeError(
                        "Task 4 historical regression source is unavailable: "
                        + relative
                    )
                index[relative] = _task4_nested_hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
            return index

        _task4_nested_root = _Task4NestedPath.cwd()
        _task4_nested_artifact_root = _Task4NestedPath(
            {str(artifact_root)!r}
        )
        _task4_nested_receipt_path = _Task4NestedPath({str(receipt_path)!r})
        if (
            _task4_nested_receipt_path.exists()
            or _task4_nested_receipt_path.is_symlink()
            or _task4_nested_receipt_path.parent
            != _Task4NestedPath(_task4_nested_sys.pycache_prefix)
        ):
            raise RuntimeError("nested child receipt path is unsafe")

        _task4_nested_pre_index = (
            _task4_nested_historical_regression_index(
            _task4_nested_root
            )
        )
        _task4_nested_pre_dependencies = _task4_nested_dependency_snapshot(
            _task4_nested_root
        )
        _task4_nested_verify_process(
            _task4_nested_root,
            _task4_nested_artifact_root,
        )
        _task4_nested_verify_closure(
            _task4_nested_root,
            _task4_nested_pre_index,
            dependency_snapshot=_task4_nested_pre_dependencies,
        )

        _task4_nested_target_globals = {{
            "__builtins__": __builtins__,
            "__name__": "__main__",
            "__package__": None,
            "__spec__": None,
        }}
        try:
            exec(
                compile(
                    {source!r},
                    "<task4-nested-child>",
                    "exec",
                ),
                _task4_nested_target_globals,
                _task4_nested_target_globals,
            )
        except BaseException as _task4_nested_target_error:
            raise RuntimeError(
                "nested child target did not return normally"
            ) from _task4_nested_target_error

        _task4_nested_post_index = (
            _task4_nested_historical_regression_index(
            _task4_nested_root
            )
        )
        _task4_nested_post_dependencies = _task4_nested_dependency_snapshot(
            _task4_nested_root
        )
        if _task4_nested_post_index != _task4_nested_pre_index:
            raise RuntimeError("nested child changed the source index")
        if (
            _task4_nested_post_dependencies
            != _task4_nested_pre_dependencies
        ):
            raise RuntimeError("nested child changed the dependency snapshot")
        _task4_nested_verify_process(
            _task4_nested_root,
            _task4_nested_artifact_root,
        )
        _task4_nested_verify_closure(
            _task4_nested_root,
            _task4_nested_post_index,
            dependency_snapshot=_task4_nested_post_dependencies,
        )

        _task4_nested_receipt = {{
            "dependency_snapshot_sha256": _task4_nested_canonical_sha256(
                _task4_nested_post_dependencies
            ),
            "nonce": {receipt_nonce!r},
            "pycache_prefix": _task4_nested_sys.pycache_prefix,
            "schema": {TASK4_CHILD_RECEIPT_SCHEMA!r},
            "source_index_sha256": _task4_nested_canonical_sha256(
                _task4_nested_post_index
            ),
            "target_source_sha256": {target_source_sha256!r},
        }}
        _task4_nested_payload = (
            _task4_nested_canonical_json_bytes(_task4_nested_receipt) + b"\\n"
        )
        if not hasattr(_task4_nested_os, "O_NOFOLLOW"):
            raise RuntimeError("nested child requires O_NOFOLLOW")
        _task4_nested_fd = _task4_nested_os.open(
            str(_task4_nested_receipt_path),
            _task4_nested_os.O_WRONLY
            | _task4_nested_os.O_CREAT
            | _task4_nested_os.O_EXCL
            | _task4_nested_os.O_NOFOLLOW,
            0o600,
        )
        with _task4_nested_os.fdopen(_task4_nested_fd, "wb") as _stream:
            _stream.write(_task4_nested_payload)
            _stream.flush()
            _task4_nested_os.fsync(_stream.fileno())
        """
    )


def task4_isolated_child_command(
    *,
    child_artifact_dir: Path,
    source: str,
    arguments: Sequence[str] = (),
    pycache_prefix: Path | None = None,
) -> tuple[str, ...]:
    """Build the one registered command shape for nested test processes."""

    cache = (
        child_artifact_dir / "pycache"
        if pycache_prefix is None
        else pycache_prefix
    )
    python_bin = TASK4_PROJECT_ROOT / ".venv" / "bin" / "python"
    launcher = (
        TASK4_PROJECT_ROOT / "scripts" / "task4_isolated_python.py"
    )
    return (
        str(python_bin),
        "-I",
        "-S",
        "-X",
        f"pycache_prefix={cache}",
        str(launcher),
        "--project-root",
        str(TASK4_PROJECT_ROOT),
        "--pycache-prefix",
        str(cache),
        "--",
        "-c",
        source,
        *arguments,
    )


def run_task4_isolated_child(
    *,
    child_artifact_dir: Path,
    source: str,
    arguments: Sequence[str] = (),
) -> subprocess.CompletedProcess[str]:
    """Run a nested test target through the fixed Task 4 3.11 launcher."""

    python_bin = TASK4_PROJECT_ROOT / ".venv" / "bin" / "python"
    launcher = (
        TASK4_PROJECT_ROOT / "scripts" / "task4_isolated_python.py"
    )
    if not python_bin.is_file() or not os.access(python_bin, os.X_OK):
        pytest.skip(
            "registered Task 4 CPython 3.11 prefix is unavailable locally"
        )
    if not launcher.is_file() or launcher.is_symlink():
        raise RuntimeError("registered Task 4 isolated launcher is unsafe")

    artifact_dir = Path(os.path.abspath(child_artifact_dir))
    if artifact_dir.exists() or artifact_dir.is_symlink():
        raise FileExistsError(
            f"nested Task 4 artifact directory already exists: "
            f"{artifact_dir}"
        )
    artifact_dir.mkdir(parents=True)
    if artifact_dir.resolve() != artifact_dir:
        raise RuntimeError(
            "nested Task 4 artifact directory is not canonical"
        )
    try:
        artifact_dir.relative_to(TASK4_PROJECT_ROOT)
    except ValueError:
        pass
    else:
        raise RuntimeError(
            "nested Task 4 artifacts must remain outside the repository"
        )
    raw_parent_prefix = sys.pycache_prefix
    expected_dependency_digest: str | None = None
    expected_source_digest: str | None = None
    if type(raw_parent_prefix) is str:
        parent_prefix = Path(os.path.abspath(raw_parent_prefix))
        if (
            not parent_prefix.is_absolute()
            or parent_prefix.is_symlink()
            or not parent_prefix.is_dir()
            or parent_prefix.resolve() != parent_prefix
        ):
            raise RuntimeError(
                "parent Task 4 pycache prefix is unavailable or unsafe"
            )
        try:
            parent_prefix.relative_to(
                (TASK4_ARTIFACT_ROOT / "runs").resolve()
            )
        except ValueError as exc:
            raise RuntimeError(
                "parent Task 4 pycache prefix escaped the run root"
            ) from exc
        pycache_prefix = Path(
            tempfile.mkdtemp(
                prefix="nested-child-",
                dir=str(parent_prefix),
            )
        )
        isolation_artifact_root = TASK4_ARTIFACT_ROOT
        expected_dependency_digest = os.environ.get(
            TASK4_PARENT_DEPENDENCY_DIGEST_ENV
        )
        expected_source_digest = os.environ.get(
            TASK4_PARENT_SOURCE_DIGEST_ENV
        )
        for label, digest in (
            ("dependency", expected_dependency_digest),
            ("source", expected_source_digest),
        ):
            if (
                type(digest) is not str
                or len(digest) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in digest
                )
            ):
                raise RuntimeError(
                    f"parent Task 4 {label} digest is unavailable"
                )
    else:
        isolation_artifact_root = artifact_dir / "runtime-artifacts"
        pycache_prefix = (
            isolation_artifact_root
            / "runs"
            / "nested-child"
            / "pycache"
        )
        pycache_prefix.mkdir(parents=True)
    if (
        pycache_prefix.is_symlink()
        or not pycache_prefix.is_dir()
        or pycache_prefix.resolve() != pycache_prefix
    ):
        raise RuntimeError("nested Task 4 pycache prefix is unsafe")

    receipt_path = pycache_prefix / "runtime-closure-receipt.json"
    if receipt_path.exists() or receipt_path.is_symlink():
        raise RuntimeError("nested Task 4 receipt path already exists")
    receipt_nonce = secrets.token_hex(32)
    target_source_sha256 = hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()
    completed = subprocess.run(
        task4_isolated_child_command(
            child_artifact_dir=artifact_dir,
            source=_task4_child_source_with_runtime_closure(
                source=source,
                artifact_root=isolation_artifact_root,
                receipt_path=receipt_path,
                receipt_nonce=receipt_nonce,
                target_source_sha256=target_source_sha256,
            ),
            arguments=arguments,
            pycache_prefix=pycache_prefix,
        ),
        cwd=str(TASK4_PROJECT_ROOT),
        env=dict(TASK4_CHILD_ENVIRONMENT),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        if receipt_path.exists() or receipt_path.is_symlink():
            raise RuntimeError(
                "failed nested Task 4 child produced a closure receipt"
            )
        return completed
    if (
        receipt_path.is_symlink()
        or not receipt_path.is_file()
        or receipt_path.resolve() != receipt_path
        or stat.S_IMODE(receipt_path.stat().st_mode) != 0o600
    ):
        raise RuntimeError(
            "nested Task 4 child omitted its runtime-closure receipt"
        )
    raw_receipt = receipt_path.read_bytes()
    try:
        receipt = json.loads(raw_receipt)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "nested Task 4 child wrote an invalid runtime-closure receipt"
        ) from exc
    expected_fields = {
        "dependency_snapshot_sha256",
        "nonce",
        "pycache_prefix",
        "schema",
        "source_index_sha256",
        "target_source_sha256",
    }
    if (
        type(receipt) is not dict
        or set(receipt) != expected_fields
        or raw_receipt != canonical_json_bytes(receipt) + b"\n"
        or receipt["schema"] != TASK4_CHILD_RECEIPT_SCHEMA
        or receipt["nonce"] != receipt_nonce
        or receipt["pycache_prefix"] != str(pycache_prefix)
        or receipt["target_source_sha256"] != target_source_sha256
        or (
            expected_dependency_digest is not None
            and receipt["dependency_snapshot_sha256"]
            != expected_dependency_digest
        )
        or (
            expected_source_digest is not None
            and receipt["source_index_sha256"] != expected_source_digest
        )
        or any(
            type(receipt[name]) is not str
            or len(receipt[name]) != 64
            or any(
                character not in "0123456789abcdef"
                for character in receipt[name]
            )
            for name in (
                "dependency_snapshot_sha256",
                "source_index_sha256",
            )
        )
    ):
        raise RuntimeError(
            "nested Task 4 child runtime-closure receipt changed"
        )
    return completed


def rational(numerator: int, denominator: int = 1) -> Rational:
    return Rational(numerator=numerator, denominator=denominator)


def binary_support(sample_size: int = 1) -> ExactSupportSpec:
    return ExactSupportSpec(
        state_ids=("state.0", "state.1"),
        actions=(
            ExactActionSpec(
                action_id="action.0",
                sample_size=sample_size,
                alphabet=("symbol.0", "symbol.1"),
            ),
        ),
    )


def law(
    support: ExactSupportSpec,
    probabilities: Sequence[tuple[int, int]],
    *,
    law_id: str,
) -> IndependentMultinomialLaw:
    return IndependentMultinomialLaw(
        law_id=law_id,
        support_spec_hash=canonical_sha256(support),
        action_probabilities=(
            IndependentActionProbabilities(
                action_id="action.0",
                probabilities=tuple(
                    rational(numerator, denominator)
                    for numerator, denominator in probabilities
                ),
            ),
        ),
    )


@lru_cache(maxsize=1)
def trusted_registry() -> TrustedSemanticRegistry:
    manifest = (
        Path(__file__).parents[2]
        / "manifests"
        / "task2_semantic_registry.json"
    )
    return load_trusted_task2_registry(manifest.read_bytes())


def parameter_family(
    support: ExactSupportSpec,
    *,
    points: tuple[ExactParameterPoint, ...],
    thresholds: HypothesisThresholds,
) -> ExactParameterFamily:
    support_hash = canonical_sha256(support)
    manifest = ExactSamplingLawManifest(
        support_spec_hash=support_hash,
        entries=tuple(
            ExactSamplingLawEntry(
                parameter_id=point.parameter_id,
                law_hash=canonical_sha256(point.law),
            )
            for point in points
        ),
    )
    manifest_hash = canonical_sha256(manifest)
    registry = trusted_registry()
    probability_space = ProbabilitySpaceSpec(
        probability_scope=ProbabilityScope.SYNTHETIC_KNOWN_CHANNEL,
        fixed_objects=(
            ObjectCommitment(
                object_id="channel.synthetic.known",
                object_hash=SHA_A,
            ),
        ),
        random_objects=(
            ObjectCommitment(
                object_id="synthetic.observation",
                object_hash=SHA_B,
            ),
        ),
        sampling_law_hash=manifest_hash,
        parameter_space_hash=exact_parameter_registry_hash(
            thresholds,
            points,
        ),
        conditioning_sigma_field_hash=SHA_E,
        observation_model_hash=SHA_A,
        estimand=registry.ref(
            "estimand.synthetic_known_channel_decision_risk",
            SemanticRegistryRole.SYNTHETIC_ESTIMAND,
        ),
        target=registry.ref(
            "target.synthetic_known_channel_risk_coverage",
            SemanticRegistryRole.SYNTHETIC_TARGET,
        ),
        formal_scientific_risk_guarantee=True,
    )
    prerequisites = SyntheticKnownChannelPrerequisites(
        known_channel_object_id="channel.synthetic.known",
        known_channel_object_hash=SHA_A,
        sampling_law_hash=manifest_hash,
        support_definition_hash=support_hash,
        channel_registration_proof=ProofArtifactRef(
            proof_id="proof.synthetic_channel_registration",
            artifact_hash=SHA_D,
        ),
    )
    return ExactParameterFamily(
        support_spec_hash=support_hash,
        semantic_registry=registry,
        probability_space=probability_space,
        synthetic_prerequisites=prerequisites,
        sampling_law_manifest=manifest,
        thresholds=thresholds,
        points=points,
    )


def three_region_family(
    support: ExactSupportSpec,
    *,
    indifference_first_probability: tuple[int, int] = (1, 20),
) -> ExactParameterFamily:
    thresholds = HypothesisThresholds(
        tau0=rational(1),
        epsilon=rational(3),
    )
    points = (
            ExactParameterPoint(
                parameter_id="omega.h0",
                loss=rational(1),
                law=law(
                    support,
                    ((1, 1), (0, 1)),
                    law_id="law.h0",
                ),
            ),
            ExactParameterPoint(
                parameter_id="omega.h1",
                loss=rational(3),
                law=law(
                    support,
                    ((0, 1), (1, 1)),
                    law_id="law.h1",
                ),
            ),
            ExactParameterPoint(
                parameter_id="omega.indifference",
                loss=rational(2),
                law=law(
                    support,
                    (
                        indifference_first_probability,
                        (
                            indifference_first_probability[1]
                            - indifference_first_probability[0],
                            indifference_first_probability[1],
                        ),
                    ),
                    law_id="law.indifference",
                ),
            ),
        )
    return parameter_family(
        support,
        points=points,
        thresholds=thresholds,
    )
