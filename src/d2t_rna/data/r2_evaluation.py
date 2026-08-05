"""D2T-RNA v7 §8.4 R2 retrospective-evaluation fail-closed framework.

R2 is the *retrospective evidence* evaluation over a **fixed observed dataset**
only.  Per contract §8.4 it is confined to empirical compression, degradation,
abstention, reason-code, and structural mapping, and is uniformly labelled
``POST_FREEZE_RETROSPECTIVE_EVALUATION``.  It is never held-out, blinded,
prospective, or independent validation (contract 8.4, 8.6).

This module is deliberately **fail-closed**: it never fabricates a certificate
or a metric.  An R2 certificate for a dataset is only produced when *every*
gate below holds.  If the observed data is not materialized within the
registered fixed dataset, or the observation model, dependency graph, or
independence proof is missing, the dataset status is ``NOT_ESTABLISHED`` with
the precise reason codes (contract 8.4: "failure is fail-closed, not a chance
to pick a laxer model and keep making a quantitative claim").

The module is self-contained (no dependency on the uncommitted manifest layer)
so it can be wired to the real manifests independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence

NOT_ESTABLISHED = "NOT_ESTABLISHED"
ESTABLISHED = "ESTABLISHED"

EVALUATION_LABEL = "POST_FREEZE_RETROSPECTIVE_EVALUATION"

# Contract §8.5 fixed roles for the three separate retrospective cases.
DATASET_ROLE: dict[str, str] = {
    "add": "COUNTERFACTUAL_RETROSPECTIVE_FULL_MATRIX_COMPRESSION",
    "sam-iii": "RETROSPECTIVE_MODALITY_TRANSFER_DIAGNOSTIC",
    "rorc": "HISTORICALLY_EXPOSED_THIRD_STATE_MISSPECIFICATION_STRESS",
}

REGISTERED_DATASETS = tuple(DATASET_ROLE)


class R2Metric(str, Enum):
    """The only metrics §8.4 permits for a retrospective evaluation."""

    EMPIRICAL_COMPRESSION = "empirical_compression"
    DEGRADATION = "degradation"
    ABSTENTION = "abstention"
    REASON_CODE = "reason_code"
    STRUCTURAL_MAPPING = "structural_mapping"


# All R2 gates are *positive* guarantees.  A missing guarantee closes the
# certificate (fail-closed).
_GATE_LABELS: tuple[str, ...] = (
    "within_registered_fixed_dataset",
    "observed_data_materialized",
    "observation_model_available",
    "dependency_graph_available",
    "independence_proof_available",
    "no_held_out_blinded_prospective",
)


@dataclass(frozen=True)
class R2DatasetStatus:
    """Fail-closed R2 status for one registered dataset."""

    dataset_id: str
    role: str
    gates: dict[str, bool] = field(default_factory=dict)
    missing_gates: tuple[str, ...] = field(default_factory=tuple)
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    status: str = NOT_ESTABLISHED
    label: str = EVALUATION_LABEL

    def as_dict(self) -> dict:
        return {
            "dataset_id": self.dataset_id,
            "role": self.role,
            "gates": dict(self.gates),
            "missing_gates": list(self.missing_gates),
            "reason_codes": list(self.reason_codes),
            "status": self.status,
            "label": self.label,
        }


def _reason_code(dataset_id: str, gate: str) -> str:
    if gate == "within_registered_fixed_dataset":
        return f"{dataset_id}: evaluation escapes the registered fixed dataset"
    if gate == "observed_data_materialized":
        return f"{dataset_id}: observed data not materialized within fixed dataset"
    if gate == "observation_model_available":
        return f"{dataset_id}: observation model unavailable"
    if gate == "dependency_graph_available":
        return f"{dataset_id}: dependency graph unavailable"
    if gate == "independence_proof_available":
        return f"{dataset_id}: independence proof unavailable"
    if gate == "no_held_out_blinded_prospective":
        return f"{dataset_id}: claim boundary breached (held-out/blinded/prospective)"
    raise ValueError(f"unknown gate {gate!r}")


def r2_dataset_status(
    dataset_id: str,
    *,
    within_registered_fixed_dataset: bool,
    observed_data_materialized: bool,
    observation_model_available: bool,
    dependency_graph_available: bool,
    independence_proof_available: bool,
    no_held_out_blinded_prospective: bool,
) -> R2DatasetStatus:
    """Evaluate one dataset's R2 gates and return a fail-closed status.

    ``role`` is taken from the registered roles (contract §8.5).  If any
    positive gate is missing the status is ``NOT_ESTABLISHED`` with the reason
    codes; it is never upgraded to a certificate.
    """
    if dataset_id not in DATASET_ROLE:
        raise ValueError(f"unknown registered dataset: {dataset_id!r}")
    gates = {
        "within_registered_fixed_dataset": within_registered_fixed_dataset,
        "observed_data_materialized": observed_data_materialized,
        "observation_model_available": observation_model_available,
        "dependency_graph_available": dependency_graph_available,
        "independence_proof_available": independence_proof_available,
        "no_held_out_blinded_prospective": no_held_out_blinded_prospective,
    }
    missing = [g for g, ok in gates.items() if not ok]
    if not missing:
        return R2DatasetStatus(
            dataset_id=dataset_id,
            role=DATASET_ROLE[dataset_id],
            gates=gates,
            status=ESTABLISHED,
            label=EVALUATION_LABEL,
        )
    return R2DatasetStatus(
        dataset_id=dataset_id,
        role=DATASET_ROLE[dataset_id],
        gates=gates,
        missing_gates=tuple(missing),
        reason_codes=tuple(_reason_code(dataset_id, g) for g in missing),
        status=NOT_ESTABLISHED,
        label=EVALUATION_LABEL,
    )


@dataclass(frozen=True)
class R2Report:
    """Aggregate §8.4 R2 fail-closed report over the registered datasets."""

    datasets: tuple[R2DatasetStatus, ...] = field(default_factory=tuple)
    all_established: bool = False
    label: str = EVALUATION_LABEL

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "all_established": self.all_established,
            "datasets": [d.as_dict() for d in self.datasets],
        }


def r2_evaluate_all(
    dataset_gates: Mapping[str, Mapping[str, bool]],
) -> R2Report:
    """Evaluate all registered datasets from a mapping of gate booleans.

    ``dataset_gates`` maps a registered dataset id to a dict of the six gate
    booleans (see :func:`r2_dataset_status`).  Unknown datasets are rejected.
    A dataset that is not producible (e.g. rorc ineligible) naturally closes.
    """
    statuses: list[R2DatasetStatus] = []
    for did in REGISTERED_DATASETS:
        if did not in dataset_gates:
            raise ValueError(f"missing gate profile for {did!r}")
        g = dataset_gates[did]
        statuses.append(r2_dataset_status(did, **g))
    all_established = all(s.status == ESTABLISHED for s in statuses)
    return R2Report(datasets=tuple(statuses), all_established=all_established)


def certificate_guard(report: R2Report) -> str:
    """Return ``PROCEED`` only if every dataset is established; else close.

    This is the hard fail-closed gate that maps §8.4 "failure is fail-closed"
    onto the R2 report.  No dataset may be force-fit into a certificate.
    """
    return ESTABLISHED if report.all_established else NOT_ESTABLISHED