from __future__ import annotations

from d2t_rna.contracts.enums import (
    CoverageBoundMethod,
    ExtendedValueTag,
    LockStage,
    PlannerFailureState,
    ProbabilityScope,
    RorcReason,
    SplitRelation,
    TruthVisibility,
    UnconditionalDerivation,
)


def values(enum_type) -> set[str]:
    return {member.value for member in enum_type}


def test_probability_scopes_are_exactly_the_registered_four() -> None:
    assert values(ProbabilityScope) == {
        "FINITE_OBSERVED_DATASET_SUBSAMPLING",
        "WITHIN_REALIZED_LIBRARY_MODEL_CONDITIONAL",
        "NEW_LIBRARY_ROBUST_MODEL_CONDITIONAL",
        "SYNTHETIC_KNOWN_CHANNEL",
    }


def test_split_relations_are_exactly_the_registered_five() -> None:
    assert values(SplitRelation) == {
        "INDEPENDENT_LIBRARIES",
        "CONDITIONALLY_INDEPENDENT_UNITS_GIVEN_NUISANCE",
        "RANDOM_PARTITION_OF_FINITE_OBSERVED_DATASET",
        "SHARED_BATCH_DEPENDENT",
        "UNKNOWN",
    }


def test_unconditional_derivations_are_exactly_registered() -> None:
    assert values(UnconditionalDerivation) == {
        "TOWER_UNIFORM_ALMOST_SURE",
        "ABSTAIN_OUTSIDE_VALIDITY_EVENT",
        "GOOD_EVENT_UNION_BOUND",
        "NOT_AVAILABLE",
    }


def test_scenario_methods_preserve_monte_carlo_downgrade_state() -> None:
    assert values(CoverageBoundMethod) == {
        "EXACT_ENUMERATION",
        "VERIFIED_INTERVAL",
        "CERTIFIED_TRUNCATION",
        "MONTE_CARLO_ONLY",
    }


def test_all_four_planner_failure_states_remain_distinct() -> None:
    assert values(PlannerFailureState) == {
        "NO_CERTIFICATE_FOUND_BY_REGISTERED_PLANNER",
        "NO_CERTIFICATE_WITHIN_AVAILABLE_CONTROL_LIBRARY",
        "NO_FEASIBLE_FIXED_HORIZON_TEST_WITHIN_REGISTERED_DESIGN_CLASS",
        "PLANNER_UNRESOLVED",
    }


def test_rorc_reasons_do_not_require_one_unique_biological_diagnosis() -> None:
    assert values(RorcReason) == {
        "REGISTERED_MODEL_CLASS_REJECTED",
        "OUT_OF_SCOPE_STATE_DICTIONARY",
        "RIVAL_SUPPORT_INCOMPLETE",
        "ABSTAIN_INDETERMINATE",
    }


def test_lock_visibility_and_extended_tags_are_closed() -> None:
    assert tuple(member.value for member in LockStage) == ("A", "B", "C", "D")
    assert values(TruthVisibility) == {"HASH_ONLY"}
    assert values(ExtendedValueTag) == {"FINITE", "POS_INF", "NA"}
