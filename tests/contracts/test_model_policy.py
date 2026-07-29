from __future__ import annotations

import pytest
from pydantic import ValidationError

from d2t_rna.contracts.enums import ProbabilityScope
from d2t_rna.contracts.primitives import ObjectCommitment, RegistryRef
from d2t_rna.contracts.probability import ProbabilitySpaceSpec

from .conftest import SHA_A, SHA_B, SHA_C, SHA_D, SHA_E, SHA_F


def make_probability_space() -> ProbabilitySpaceSpec:
    return ProbabilitySpaceSpec(
        probability_scope=ProbabilityScope.SYNTHETIC_KNOWN_CHANNEL,
        fixed_objects=(
            ObjectCommitment(object_id="fixed.channel", object_hash=SHA_A),
        ),
        random_objects=(
            ObjectCommitment(object_id="random.counts", object_hash=SHA_B),
        ),
        sampling_law_hash=SHA_C,
        parameter_space_hash=SHA_D,
        conditioning_sigma_field_hash=SHA_E,
        observation_model_hash=SHA_F,
        estimand=RegistryRef(
            registry_id="estimand.synthetic_decision",
            registry_hash=SHA_A,
        ),
        target=RegistryRef(
            registry_id="target.synthetic_known_channel",
            registry_hash=SHA_B,
        ),
        formal_scientific_risk_guarantee=True,
    )


def test_models_reject_unregistered_fields() -> None:
    payload = make_probability_space().model_dump(mode="python")
    payload["unregistered"] = 1
    with pytest.raises(ValidationError):
        ProbabilitySpaceSpec.model_validate(payload)


def test_models_are_frozen_at_every_nested_level() -> None:
    spec = make_probability_space()
    with pytest.raises(ValidationError):
        spec.formal_scientific_risk_guarantee = False
    with pytest.raises(ValidationError):
        spec.fixed_objects[0].object_id = "changed"
    with pytest.raises(TypeError):
        spec.fixed_objects[0] = ObjectCommitment(
            object_id="changed",
            object_hash=SHA_A,
        )


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("formal_scientific_risk_guarantee", 1),
        ("fixed_objects", []),
        ("sampling_law_hash", SHA_A.upper()),
    ],
)
def test_python_inputs_are_strict(field: str, bad_value: object) -> None:
    payload = make_probability_space().model_dump(mode="python")
    payload[field] = bad_value
    with pytest.raises(ValidationError):
        ProbabilitySpaceSpec.model_validate(payload)
