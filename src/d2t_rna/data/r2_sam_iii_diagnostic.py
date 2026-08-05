"""D2T-RNA v7 §8.5 SAM-III R2 modality-transfer diagnostic (contract 8.4/8.5).

SAM-III/GSE278422 is assigned the role
``RETROSPECTIVE_MODALITY_TRANSFER_DIAGNOSTIC`` (contract 8.5).  Its R2
evaluation is *not* a merged benchmark; it is a diagnostic that answers three
questions against the registered T2 objects:

1. **Can T2 objects map onto the smCCP/DMS observation model?**  The DANCE-MaP
   supplement exposes per-nucleotide DMS reactivity (a continuous, per-position
   profile).  To reuse a T2 ``Action`` (a categorical channel ``Q[y][w]`` over
   latent states) we would need a *registered* mapping from reactivity to a
   categorical observation law indexed by registered latent structural states.
   Without such a registered channel the mapping is not established.
2. **Are the action semantics comparable?**  T2 actions are categorical
   observation channels over a finite latent state space.  DMS reactivity is a
   continuous per-nucleotide measure; "SAM vs noSAM" is a ligand condition, not
   a registered categorical action over latent structural states.  If the
   semantics are not comparable we report
   ``NOT_COMPARABLE_BY_REGISTERED_ACTION_SPACE`` (contract 8.5) and do not force
   the data into a unifying benchmark.
3. **Does the model degrade correctly when incomplete?**  Any missing piece
   (no registered categorical observation model, unknown dependency unit, NaN /
   uncovered positions, non-independent reads) must degrade to
   ``NOT_ESTABLISHED`` rather than a fabricated quantitative claim
   (contract 8.4 / 10.2).

This module is fail-closed: it never upgrades a diagnostic to a certificate.
It only reports the worked, auditable diagnostic result
(``scientific_claim_authorized=false``).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

NOT_ESTABLISHED = "NOT_ESTABLISHED"
NOT_COMPARABLE = "NOT_COMPARABLE_BY_REGISTERED_ACTION_SPACE"
DIAGNOSTIC = "POST_FREEZE_RETROSPECTIVE_EVALUATION"

# Registered couplings / action semantics under which T2's categorical
# observation-law reuse is permitted (contract 2.1 / 2.3 / 8.5).
_REGISTERED_ACTION_SEMANTICS = frozenset(
    {"CATEGORICAL_OBSERVATION_CHANNEL_OVER_LATENT_STATES"}
)


@dataclass(frozen=True)
class SamIIIConditionReact:
    """Empirical reactivity statistics for one construct x condition."""

    construct: str
    condition: str
    n_positions: int
    covered: int                     # positions with non-NaN reactivity
    coverage: float                  # covered / n_positions
    mean_reactivity: float | None
    min_reactivity: float | None
    max_reactivity: float | None
    # comp1_raw (index 1) is the modified-channel DMS reactivity rate.
    raw: tuple[float, ...]           # per-position comp1_raw

    def as_dict(self) -> dict:
        return {
            "construct": self.construct,
            "condition": self.condition,
            "n_positions": self.n_positions,
            "covered": self.covered,
            "coverage": round(self.coverage, 6),
            "mean_reactivity": (
                None if self.mean_reactivity is None else round(self.mean_reactivity, 6)
            ),
            "min_reactivity": (
                None if self.min_reactivity is None else round(self.min_reactivity, 6)
            ),
            "max_reactivity": (
                None if self.max_reactivity is None else round(self.max_reactivity, 6)
            ),
        }


@dataclass(frozen=True)
class SamIIIModalityDiagnostic:
    """Fail-closed §8.5 diagnostic for the SAM-III DMS modality transfer."""

    dataset_id: str = "sam-iii"
    role: str = "RETROSPECTIVE_MODALITY_TRANSFER_DIAGNOSTIC"
    conditions: tuple[SamIIIConditionReact, ...] = field(default_factory=tuple)
    observation_model_registered: bool = False
    action_semantics_comparable: bool = False
    dependency_unit_known: bool = False
    reads_independent: bool = False
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    verdict: str = NOT_ESTABLISHED
    label: str = DIAGNOSTIC

    def as_dict(self) -> dict:
        return {
            "dataset_id": self.dataset_id,
            "role": self.role,
            "conditions": [c.as_dict() for c in self.conditions],
            "observation_model_registered": self.observation_model_registered,
            "action_semantics_comparable": self.action_semantics_comparable,
            "dependency_unit_known": self.dependency_unit_known,
            "reads_independent": self.reads_independent,
            "reason_codes": list(self.reason_codes),
            "verdict": self.verdict,
            "label": self.label,
        }


def _per_condition_react(
    conditions: Sequence[dict],
) -> list[SamIIIConditionReact]:
    out: list[SamIIIConditionReact] = []
    for c in conditions:
        raw_vals: list[float] = []
        for row in c["rows"]:
            # row = [comp1_count, comp1_raw, comp2_count, comp2_raw, background]
            v = row[1]
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                raw_vals.append(float(v))
        covered = len(raw_vals)
        n = len(c["positions"])
        coverage = covered / n if n else 0.0
        mean_v = sum(raw_vals) / covered if covered else None
        min_v = min(raw_vals) if covered else None
        max_v = max(raw_vals) if covered else None
        out.append(
            SamIIIConditionReact(
                construct=c["construct"],
                condition=c["condition"],
                n_positions=n,
                covered=covered,
                coverage=coverage,
                mean_reactivity=mean_v,
                min_reactivity=min_v,
                max_reactivity=max_v,
                raw=tuple(raw_vals),
            )
        )
    return out


def sam_iii_modality_diagnostic(
    canonical_path: Path | str,
    *,
    action_semantics_registered: bool = False,
    dependency_unit_known: bool = False,
    reads_independent: bool = False,
) -> SamIIIModalityDiagnostic:
    """Run the §8.5 SAM-III modality-transfer diagnostic.

    ``action_semantics_registered`` indicates whether the DMS reactivity is
    wired to a registered categorical observation channel over latent states
    (i.e. the T2 action library).  All three flags default to ``False`` and the
    diagnostic is fail-closed: unless the semantics are registered and the
    dependency unit / independence are established, the verdict closes.
    """
    data = json.loads(Path(canonical_path).read_bytes())
    conditions = _per_condition_react(data["conditions"])

    reason: list[str] = []
    if not action_semantics_registered:
        reason.append(
            "DMS reactivity is continuous per-nucleotide; no registered "
            "categorical observation channel over latent states maps T2 actions"
        )
    if not dependency_unit_known:
        reason.append("dependency unit is not known for the DANCE-MaP reads")
    if not reads_independent:
        reason.append("cross-position DANCE-MaP reads are not independent")

    # Action semantics comparable only when a registered categorical channel
    # exists.  DMS reactivity alone does not satisfy this (contract 8.5).
    comparable = action_semantics_registered

    # Verdict: fail-closed.  If semantics not comparable -> NOT_COMPARABLE.
    # If comparable but other guarantees missing -> NOT_ESTABLISHED.
    if not comparable:
        verdict = NOT_COMPARABLE
        reason = [
            "action semantics not comparable: DMS reactivity is not a "
            "registered categorical observation channel over latent states"
        ]
        if not dependency_unit_known:
            reason.append("dependency unit unknown")
        if not reads_independent:
            reason.append("reads not independent")
    else:
        verdict = NOT_ESTABLISHED if reason else NOT_ESTABLISHED  # never upgrade

    return SamIIIModalityDiagnostic(
        conditions=tuple(conditions),
        observation_model_registered=action_semantics_registered,
        action_semantics_comparable=comparable,
        dependency_unit_known=dependency_unit_known,
        reads_independent=reads_independent,
        reason_codes=tuple(reason),
        verdict=verdict,
    )