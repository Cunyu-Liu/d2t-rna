"""task_reduction.py -- P0-9 external task-reduction registry (9 categories).

This module classifies the external-method prior art that the D2T task could be
"reduced to" or compared against.  It is a *registry of reductions*, not a set
of claims: every category carries a ``verdict`` drawn from exactly one of

    MATCHED_COMPARABLE
    COMPARABLE_ON_SEPARATE_TRACK
    NOT_COMPARABLE_WITH_REASON
    UNKNOWN_FULL_TEXT_OR_REDUCTION_MISSING

The D2T task (Track C, frozen decision registry, see
``d2t_rna.evaluation.track_registry``) is: choose an integer, cost-constrained
allocation across a finite set of *actions* (experiments / sensing modalities)
that each induce a categorical observation law under two simple hypotheses
``H0``/``H1``, to minimise expected Bayes average error / randomized-minimax
risk, or (Track C) to reach a fixed risk endpoint ``1/10`` at minimal total
cost, with exact rational computation and interval-arithmetic-verified
achievability / no-go certificates.

Each category record carries the thirteen fields required by the contract:

    hypothesis_space, action_control_space, observation_model, fixed_sequential,
    adaptive_nonadaptive, budget_cost, loss_endpoint, robustness_nuisance,
    external_information, certificate_capability, computational_guarantee,
    rna_action_realism, official_implementation_version, verdict

Where the original full text / an exact reduction is not available to this
auditor, the field is set to ``UNKNOWN_FULL_TEXT_OR_REDUCTION_MISSING`` and no
value is guessed.  Verdicts that rest on the repository analysis (the frozen
comparator set in ``track_c_primary_decision.json``) are labelled with their
source.

This registry feeds the Phase-2 novelty assessment: it identifies which
category(ies) constitute genuine closest prior art leaving a nontrivial D2T
capability.
"""

from __future__ import annotations

import hashlib
import json
from typing import Optional

UNKNOWN = "UNKNOWN_FULL_TEXT_OR_REDUCTION_MISSING"

# ---- verdict vocabulary (exactly these four strings are legal) ------------
VERDICT_MATCHED = "MATCHED_COMPARABLE"
VERDICT_SEPARATE_TRACK = "COMPARABLE_ON_SEPARATE_TRACK"
VERDICT_NOT_COMPARABLE = "NOT_COMPARABLE_WITH_REASON"
VERDICT_UNKNOWN = "UNKNOWN_FULL_TEXT_OR_REDUCTION_MISSING"
VERDICTS = frozenset(
    {VERDICT_MATCHED, VERDICT_SEPARATE_TRACK, VERDICT_NOT_COMPARABLE,
     VERDICT_UNKNOWN}
)

# category ids (EXACTLY the 9 external-method categories of P0-9)
CATEGORY_IDS = (
    "controlled_sensing_fixed_sample_open_loop",
    "fixed_horizon_active_hypothesis_testing",
    "active_sequential_ht_separate_track",
    "robust_T_KL_discrimination",
    "bayesian_eig_decision_region",
    "test_cover",
    "rna_rational_design",
    "M2_M2R_M2seq_action_realism",
    "SHAPEseq_DMS_MaP_count_likelihood_calibration",
)

# The thirteen required fields (contract order).
REQUIRED_FIELDS = (
    "hypothesis_space",
    "action_control_space",
    "observation_model",
    "fixed_sequential",
    "adaptive_nonadaptive",
    "budget_cost",
    "loss_endpoint",
    "robustness_nuisance",
    "external_information",
    "certificate_capability",
    "computational_guarantee",
    "rna_action_realism",
    "official_implementation_version",
    "verdict",
)


class TaskReductionError(RuntimeError):
    """Fail-closed error for a malformed task-reduction record."""


def _cat(
    cid: str,
    *,
    name: str,
    key_refs: list[str],
    hypothesis_space,
    action_control_space,
    observation_model,
    fixed_sequential,
    adaptive_nonadaptive,
    budget_cost,
    loss_endpoint,
    robustness_nuisance,
    external_information,
    certificate_capability,
    computational_guarantee,
    rna_action_realism,
    official_implementation_version,
    verdict: str,
    reduction_reasoning: str,
    d2t_capability_gap: str,
) -> dict:
    """Build one category record, validating the verdict vocabulary."""
    if verdict not in VERDICTS:
        raise TaskReductionError(
            f"illegal verdict {verdict!r} for category {cid!r}; must be one of "
            f"{sorted(VERDICTS)}"
        )
    return {
        "category_id": cid,
        "category_name": name,
        "key_references": key_refs,
        "hypothesis_space": hypothesis_space,
        "action_control_space": action_control_space,
        "observation_model": observation_model,
        "fixed_sequential": fixed_sequential,
        "adaptive_nonadaptive": adaptive_nonadaptive,
        "budget_cost": budget_cost,
        "loss_endpoint": loss_endpoint,
        "robustness_nuisance": robustness_nuisance,
        "external_information": external_information,
        "certificate_capability": certificate_capability,
        "computational_guarantee": computational_guarantee,
        "rna_action_realism": rna_action_realism,
        "official_implementation_version": official_implementation_version,
        "verdict": verdict,
        "reduction_reasoning": reduction_reasoning,
        "d2t_capability_gap": d2t_capability_gap,
    }


# ---------------------------------------------------------------------------
# the nine category records
# ---------------------------------------------------------------------------

# 1. controlled sensing, fixed-sample / open-loop
_C1 = _cat(
    "controlled_sensing_fixed_sample_open_loop",
    name="Controlled sensing (fixed-sample / open-loop)",
    key_refs=[
        "Chernoff 1959, Ann. Math. Statist. 30(3):345-360 (sequential design of "
        "experiments; delta^A) -- fixed-sample open-loop control is the special "
        "case",
        "Nitinawarat, Atia & Veeravalli 2013, IEEE TAC 58(10):2451-2464 "
        "(controlled sensing for multihypothesis testing; fixed-sample open-loop "
        "is asymptotically optimal for binary HT; pure stationary open-loop "
        "policy)",
    ],
    hypothesis_space="M-ary simple hypotheses (binary in Chernoff core); fully "
        "specified laws under each hypothesis",
    action_control_space="Finite set of repeatable sensing actions/experiments; "
        "open-loop (pre-planned) integer allocation of samples to actions",
    observation_model="Each action induces a categorical/multinomial observation "
        "law; conditionally independent given the chosen control",
    fixed_sequential="Fixed sample size (fixed-sample open-loop); sequential "
        "variant exists (Chernoff sequential design) but the open-loop case is "
        "fixed-sample",
    adaptive_nonadaptive="Non-adaptive (open-loop) for the fixed-sample case; "
        "adaptive for the sequential variant",
    budget_cost="Sampling cost / fixed total sample size; per-action non-uniform "
        "costs in the 2013 extension",
    loss_endpoint="Maximal error probability driven to zero asymptotically "
        "(error exponent / Chernoff information); decision-making risk in the "
        "sequential variant",
    robustness_nuisance="None -- laws fully specified; technical 'positivity' "
        "assumption in Chernoff",
    external_information=UNKNOWN,
    certificate_capability="Asymptotic (exponent) optimality only; no "
        "finite-budget exact risk certificate in the classical work",
    computational_guarantee="Polynomial per-step allocation; asymptotic "
        "exponent-optimality; no exact finite-horizon guarantee",
    rna_action_realism="N/A (generic sensing; no RNA action model)",
    official_implementation_version=UNKNOWN,
    verdict=VERDICT_MATCHED,
    reduction_reasoning=(
        "The repo already runs a `chernoff` comparator (Chernoff-information "
        "greedy allocator, see evaluation/matrix.py), which is the frozen "
        "strongest comparator in track_c_primary_decision.json (coverage "
        "60/64, family_cluster_mean_cost 8.0). This is a faithful instance of "
        "fixed-sample controlled sensing under the SAME task / information / "
        "cost / horizon / endpoint as D2T."
    ),
    d2t_capability_gap=(
        "GENUINE CLOSEST PRIOR ART. Nontrivial D2T capability left open: exact, "
        "finite-budget, interval-arithmetic-verified achievability upper bound "
        "and no-go lower bound for Track-C cost-to-fixed-risk-endpoint "
        "minimization, plus explicit oracle cross-validation -- none of which "
        "appear in the asymptotic (exponent-based) controlled-sensing "
        "literature (Chernoff delta^A is asymptotic and not second-order "
        "efficient; Keener 1984)."
    ),
)

# 2. fixed-horizon active hypothesis testing
_C2 = _cat(
    "fixed_horizon_active_hypothesis_testing",
    name="Fixed-horizon active hypothesis testing",
    key_refs=[
        "Naghshvar & Javidi 2013, Ann. Statist. 41(6):2703-2738 (active "
        "sequential hypothesis testing; dynamic-programming lower bounds; "
        "fixed-horizon is the non-stopping specialisation)",
        "Naghshvar et al. 'Fixed-Horizon Active Hypothesis Testing and Anomaly "
        "Detection', IEEE TSP (adaptive allocation over a fixed horizon)",
    ],
    hypothesis_space="M-ary simple hypotheses, Bayesian prior over hypotheses",
    action_control_space="Finite set K of sensing actions; adaptive within a "
        "fixed horizon (or open-loop when adaptivity is disallowed)",
    observation_model="Categorical observation laws per action, conditionally "
        "independent given action; Bayesian belief state update",
    fixed_sequential="Fixed horizon (bounded number of observations); no "
        "early-stopping in the fixed-horizon form",
    adaptive_nonadaptive="Adaptive (feedback) within the horizon in the active "
        "form; the repo comparator base is open-loop fixed-budget",
    budget_cost="Fixed total cost / horizon length; sampling cost per action",
    loss_endpoint="Error probability (or risk) minimised for a fixed horizon; "
        "DP lower bounds on optimal total cost",
    robustness_nuisance="None",
    external_information=UNKNOWN,
    certificate_capability="Dynamic-programming lower bounds and asymptotic "
        "optimality; no exact finite-budget rational certificate for the "
        "randomised-minimax endpoint",
    computational_guarantee="DP is exponential in state for M>2; heuristic "
        "policies give asymptotic optimality; no poly exact solver for the "
        "cost-to-endpoint problem",
    rna_action_realism="N/A",
    official_implementation_version=UNKNOWN,
    verdict=VERDICT_MATCHED,
    reduction_reasoning=(
        "A fixed-horizon, non-adaptive allocation is the SAME framework as the "
        "D2T fixed-budget-to-fixed-endpoint problem (allocation vector over a "
        "finite action set, bounded total cost, minimising risk). The repo "
        "comparators (full_matrix, random, chernoff, eig) are all fixed-budget "
        "open-loop allocations of this type and are run on the identical task."
    ),
    d2t_capability_gap=(
        "Leaves the same nontrivial D2T capability open as #1: exact certified "
        "finite-budget randomised-minimax and a certified no-go lower bound, "
        "rather than asymptotic exponents or unverified DP bounds."
    ),
)

# 3. active sequential HT (explicitly a separate track)
_C3 = _cat(
    "active_sequential_ht_separate_track",
    name="Active sequential hypothesis testing (separate track)",
    key_refs=[
        "Chernoff 1959 (sequential design, delta^A randomized policy)",
        "Naghshvar & Javidi 2013, Ann. Statist. 41(6):2703-2738",
        "Bessler 1960 (general M-ary sequential design)",
    ],
    hypothesis_space="M-ary simple hypotheses, Bayesian prior",
    action_control_space="Finite set K of sensing actions chosen adaptively at "
        "each time step; stopping rule included",
    observation_model="Categorical per-action laws; sequential belief update",
    fixed_sequential="Sequential (variable-length): stopping time is part of "
        "the policy",
    adaptive_nonadaptive="Adaptive (full feedback + stopping)",
    budget_cost="Total cost = cumulative control cost up to the stopping time; "
        "non-uniform control cost",
    loss_endpoint="Expected total cost (delay + wrong-declaration penalty); "
        "asymptotic optimality in the Chernoff sense",
    robustness_nuisance="None",
    external_information=UNKNOWN,
    certificate_capability="Lower bounds via DP and asymptotic optimality; no "
        "exact finite-budget rational endpoint certificate",
    computational_guarantee="Asymptotic optimality / positive information "
        "acquisition rate; DP exponential",
    rna_action_realism="N/A",
    official_implementation_version=UNKNOWN,
    verdict=VERDICT_SEPARATE_TRACK,
    reduction_reasoning=(
        "The stopping-time (sequential) structure uses a genuinely different "
        "information/cost model than D2T: D2T Track C fixes the budget and "
        "minimises cost to a fixed risk endpoint with an integer open-loop "
        "allocation; active sequential HT adaptively stops. It is therefore "
        "COMPARABLE only on a SEPARATE track, not the same task/horizon/endpoint."
    ),
    d2t_capability_gap=(
        "Not the primary comparator track; a valid separate-track comparison "
        "would require its own pre-registered endpoint, not the frozen Track C "
        "endpoint."
    ),
)

# 4. robust T / KL discrimination
_C4 = _cat(
    "robust_T_KL_discrimination",
    name="Robust T / KL discrimination (Huber, Wasserstein/TV uncertainty sets)",
    key_refs=[
        "Huber 1965 (epsilon-contamination robust testing; least favourable "
        "distributions)",
        "Chen, Gao & Ren 2015/2021 (general decision theory for Huber "
        "epsilon-contamination; robust minimax)",
        "Wasserstein-uncertainty robust HT (DRO reformulations)",
    ],
    hypothesis_space="Composite hypothesis classes / uncertainty sets around "
        "nominal laws (epsilon-contamination, TV/Wasserstein/KL balls)",
    action_control_space="No action control in the classical framework (passive "
        "single observation stream); no multi-action allocation",
    observation_model="Observation law lies in an uncertainty/contamination "
        "neighbourhood; minimax over the set",
    fixed_sequential="Mostly fixed-sample; sequential e-value variants exist",
    adaptive_nonadaptive="Non-adaptive (passive) in the classical framework",
    budget_cost="Sample complexity to bound worst-case error; no action-cost "
        "allocation",
    loss_endpoint="Worst-case (robust minimax) type-I/II error over the "
        "uncertainty set",
    robustness_nuisance="YES -- the entire problem is defined by the nuisance "
        "uncertainty/contamination set; D2T has no such set",
    external_information=UNKNOWN,
    certificate_capability="LFD / robust-minimax characterisation; no "
        "interval-arithmetic certificate machinery",
    computational_guarantee="Some tractable convex reformulations (Wasserstein); "
        "generally harder than D2T's exact finite enumeration",
    rna_action_realism="N/A",
    official_implementation_version=UNKNOWN,
    verdict=VERDICT_NOT_COMPARABLE,
    reduction_reasoning=(
        "Different optimisation problem: D2T assumes fully-specified categorical "
        "laws (no nuisance/contamination set) and optimises a multi-action "
        "cost-constrained allocation; robust discrimination instead minimaxes "
        "over distributional uncertainty sets with a passive stream. The "
        "robustness_nuisance axis is structurally absent from D2T."
    ),
    d2t_capability_gap=(
        "D2T would need an explicit nuisance/uncertainty set to be comparable; "
        "adding one is out of the current scope and would change the problem."
    ),
)

# 5. Bayesian EIG / decision-region determination
_C5 = _cat(
    "bayesian_eig_decision_region",
    name="Bayesian expected-information-gain / decision-region determination",
    key_refs=[
        "Lindley 1956 (Bayesian experimental design / information gain)",
        "DeGroot 1962 (uncertainty, information and sequential experiments)",
        "Bernardo / Bayesian OED (EIG maximisation)",
    ],
    hypothesis_space="Simple/composite hypotheses with a Bayesian prior; "
        "decision-region (acceptance) geometry under uncertainty",
    action_control_space="Finite set of experiments; allocation chosen to "
        "maximise expected information gain",
    observation_model="Categorical/likelihood models; posterior (belief) "
        "evolution",
    fixed_sequential="Both fixed-sample and sequential OED variants",
    adaptive_nonadaptive="Adaptive in sequential OED; open-loop in "
        "non-adaptive OED",
    budget_cost="Cost budget for experiments",
    loss_endpoint="Expected information gain (EIG) / expected posterior "
        "uncertainty -- an INFORMATION objective, not a risk/error objective",
    robustness_nuisance="None",
    external_information=UNKNOWN,
    certificate_capability="No exact finite-budget risk certificate; EIG is "
        "typically estimated (MC / bounds)",
    computational_guarantee="EIG estimation is expensive; no exact rational "
        "solution for the D2T risk endpoint",
    rna_action_realism="N/A",
    official_implementation_version=UNKNOWN,
    verdict=VERDICT_MATCHED,
    reduction_reasoning=(
        "The repo runs an `eig` comparator (Hellinger-information greedy "
        "allocator, evaluation/matrix.py), i.e. Bayesian-EIG-style allocation on "
        "the SAME task / cost / horizon / endpoint. It is a registered "
        "comparator (coverage 4/64, family_cluster_mean_cost 8.0) in the frozen "
        "decision registry, though its objective (information) differs from "
        "D2T's (risk)."
    ),
    d2t_capability_gap=(
        "Runs the same task as a comparator, but maximises information rather "
        "than certified risk; D2T's exact cost-to-endpoint with certificate is "
        "the residual capability."
    ),
)

# 6. Test Cover
_C6 = _cat(
    "test_cover",
    name="Test Cover (minimum test set for exact identification)",
    key_refs=[
        "Moret & Shapiro 1985/1991, 'On Minimizing a Set of Tests', SIAM J. Sci. "
        "Stat. Comput. (test cover theory; greedy heuristics)",
        "Crowston, Gutin et al. 2012 (parameterized complexity of Test Cover; "
        "O(log n) approx via Set Cover)",
        "Garey & Johnson (NP-hardness)",
    ],
    hypothesis_space="Finite set of items/candidates to identify uniquely; "
        "binary separability between every pair",
    action_control_space="Finite set of binary tests; choose a minimum-cost "
        "subcollection that separates every pair (a test cover)",
    observation_model="Binary test outcomes (which side of the test each item "
        "falls on); deterministic separation, no probabilities",
    fixed_sequential="Fixed (set selection); no sequential stopping",
    adaptive_nonadaptive="Non-adaptive (open-loop selection of a covering set)",
    budget_cost="Cost of the chosen tests; minimise total cost of the cover",
    loss_endpoint="Exact unique identification (zero discrimination error) via a "
        "covering set; NOT a probabilistic risk endpoint",
    robustness_nuisance="None",
    external_information=UNKNOWN,
    certificate_capability="NP-hard; approximation ratio O(log n) vs optimal; "
        "no risk certificate",
    computational_guarantee="NP-hard, O(log n)-approx greedy; no exact "
        "polynomial algorithm",
    rna_action_realism="Deterministic test separation only; no probabilistic "
        "RNA observation model",
    official_implementation_version=UNKNOWN,
    verdict=VERDICT_MATCHED,
    reduction_reasoning=(
        "The repo runs a `greedy_test_cover` comparator (TV-separation greedy "
        "allocator, evaluation/matrix.py) on the SAME task/cost/horizon/endpoint; "
        "it is a registered comparator (coverage 0/64, family_cluster_mean_cost "
        "8.0) in the frozen decision registry. Test Cover is genuine closest "
        "prior art for the action-selection combinatorial core."
    ),
    d2t_capability_gap=(
        "Test Cover is a deterministic binary covering problem (exact "
        "identification, no probabilities, no risk endpoint). D2T replaces this "
        "with probabilistic multi-action allocation under a randomised-minimax "
        "risk endpoint and a cost budget, with exact rational certificates -- a "
        "nontrivial extension beyond binary covering."
    ),
)

# 7. RNA rational design
_C7 = _cat(
    "rna_rational_design",
    name="RNA rational design (inverse folding / sequence design)",
    key_refs=[
        "Inverse-folding / RNA design literature (e.g. NUPACK, RNAinverse, "
        "linearFold / Eterna-style design)",
        "D2T-RNA is the motivating application of the D2T task",
    ],
    hypothesis_space="RNA sequence space to be designed; objective is a target "
        "structure/function, not a statistical hypothesis",
    action_control_space="Sequence / modification choices; no sensing-allocation "
        "control",
    observation_model="Thermodynamic folding / structure-prediction models "
        "(minimum free energy), not categorical observation laws",
    fixed_sequential="Fixed (one-shot design or iterative refinement)",
    adaptive_nonadaptive="Iterative heuristic design",
    budget_cost="Design/optimisation cost, not measurement sampling cost",
    loss_endpoint="Structural/functional fitness (e.g. MFE distance, expression "
        "level); no error-probability endpoint",
    robustness_nuisance="Uncertainty in folding parameters",
    external_information=UNKNOWN,
    certificate_capability="No formal risk/error certificate (heuristic "
        "optimisers)",
    computational_guarantee="NP-hard / heuristic search (stochastic, dynamic "
        "programming); no exact guarantees",
    rna_action_realism="Directly RNA; defines the DESIGN objective, not the "
        "discrimination action model",
    official_implementation_version=UNKNOWN,
    verdict=VERDICT_NOT_COMPARABLE,
    reduction_reasoning=(
        "RNA rational design solves the sequence-design / inverse-folding "
        "problem (optimise a target structure), which is a DIFFERENT task from "
        "the D2T budgeted-hypothesis-test discrimination problem. RNA is only "
        "the motivating application domain of D2T; the design methods are not "
        "solution methods for the D2T decision problem."
    ),
    d2t_capability_gap=(
        "Not a comparator; relevant only as application framing for the D2T "
        "action model (see categories #8, #9)."
    ),
)

# 8. M2 / M2R / M2-seq action realism
_C8 = _cat(
    "M2_M2R_M2seq_action_realism",
    name="M2 / M2R / M2-seq mutational-profiling action realism",
    key_refs=[
        "M2-seq style mutational profiling / MA (mutagenesis) action realism "
        "for the D2T action model (repo: data/measured_mattr.py, rna.py)",
    ],
    hypothesis_space="D2T two-hypothesis discrimination (H0/H1 over sequence "
        "states); the actions are mutational-profiling experiments",
    action_control_space="Realistic mutational-profiling actions (what a "
        "measurement actually observes); informs rna_action_realism of D2T",
    observation_model="Mutational profile / read-count observation channel",
    fixed_sequential="Fixed",
    adaptive_nonadaptive="Non-adaptive",
    budget_cost="Measurement cost of running a mutational-profiling assay",
    loss_endpoint="None of its own -- it is a realism/specification input, not "
        "a loss-endpoint method",
    robustness_nuisance="Protocol-dependent noise",
    external_information=UNKNOWN,
    certificate_capability="None (experimental protocol realism)",
    computational_guarantee="None (experimental)",
    rna_action_realism="HIGH -- this is precisely the action-realism axis",
    official_implementation_version=UNKNOWN,
    verdict=VERDICT_NOT_COMPARABLE,
    reduction_reasoning=(
        "M2/M2R/M2-seq are experimental mutational-profiling protocols that "
        "specify the REALISM of the D2T action model (the channel a measurement "
        "induces); they are not competing solution algorithms for the D2T "
        "decision problem and carry no loss endpoint of their own."
    ),
    d2t_capability_gap=(
        "Feeds the rna_action_realism field of the D2T action model; not a "
        "comparator."
    ),
)

# 9. SHAPE-Seq / DMS-MaP count likelihood / calibration
_C9 = _cat(
    "SHAPEseq_DMS_MaP_count_likelihood_calibration",
    name="SHAPE-Seq / DMS-MaP count-likelihood and calibration",
    key_refs=[
        "SHAPE-Seq (structure probing) count-likelihood calibration",
        "DMS-MaPseq (mutational profiling with next-gen reads) count model / "
        "calibration",
    ],
    hypothesis_space="D2T hypotheses; these methods provide the OBSERVATION "
        "MODEL (count likelihood) for structure-probing reads",
    action_control_space="None (a single probing assay); informs the D2T "
        "observation model",
    observation_model="Count-likelihood / calibration of probing read counts "
        "to structural state",
    fixed_sequential="Fixed",
    adaptive_nonadaptive="Non-adaptive",
    budget_cost="Sequencing depth / read count",
    loss_endpoint="None of its own -- calibration of the observation model",
    robustness_nuisance="Read-depth / bias calibration",
    external_information=UNKNOWN,
    certificate_capability="None (empirical calibration)",
    computational_guarantee="None",
    rna_action_realism="HIGH -- defines the probabilistic RNA observation "
        "channel",
    official_implementation_version=UNKNOWN,
    verdict=VERDICT_NOT_COMPARABLE,
    reduction_reasoning=(
        "SHAPE-Seq / DMS-MaP supply the count-likelihood / calibration of the "
        "D2T RNA OBSERVATION MODEL (the probabilistic channel an action "
        "induces); they are data/calibration sources, not solution methods for "
        "the budgeted discrimination problem, and have no loss endpoint."
    ),
    d2t_capability_gap=(
        "Feeds the observation_model field of D2T; not a comparator."
    ),
)

# deterministic order
_CATEGORIES = (_C1, _C2, _C3, _C4, _C5, _C6, _C7, _C8, _C9)


def category_records() -> list[dict]:
    """Return the nine category records in fixed order."""
    return [dict(c) for c in _CATEGORIES]


def validate_record(record: dict) -> None:
    """Fail-closed: check all required fields and verdict vocabulary."""
    for field in REQUIRED_FIELDS:
        if field not in record:
            raise TaskReductionError(
                f"task-reduction record {record.get('category_id')!r} missing "
                f"field {field!r}"
            )
    if record["verdict"] not in VERDICTS:
        raise TaskReductionError(
            f"record {record['category_id']!r} illegal verdict "
            f"{record['verdict']!r}"
        )


def _closest_prior_art() -> list[dict]:
    """Categories that are genuine closest prior art leaving a nontrivial D2T
    capability (feeds the Phase-2 novelty assessment)."""
    out = []
    for r in _CATEGORIES:
        if r["verdict"] == VERDICT_MATCHED:
            out.append(
                {
                    "category_id": r["category_id"],
                    "category_name": r["category_name"],
                    "verdict": r["verdict"],
                    "d2t_capability_gap": r["d2t_capability_gap"],
                }
            )
    return out


def build_task_reduction_registry(
    *,
    generator: str = "task_reduction.py",
    phase: str = "P0-9",
    schema: str = "d2t_rna.task_reduction_registry.v3",
    paper_eligible: bool = False,
    purpose: str = "DECISION_REGISTRY_OR_METHOD_ROLE",
) -> dict:
    """Assemble the full P0-9 task-reduction registry document."""
    for r in _CATEGORIES:
        validate_record(r)
    records = [dict(r) for r in _CATEGORIES]
    # verdict bucket summary
    buckets: dict[str, list[str]] = {}
    for r in records:
        buckets.setdefault(r["verdict"], []).append(r["category_id"])
    registry = {
        "schema": schema,
        "phase": phase,
        "generator": generator,
        "paper_eligible": paper_eligible,
        "purpose": purpose,
        "is_result_artifact": False,
        "n_categories": len(records),
        "verdict_bucket_summary": {
            v: sorted(buckets.get(v, [])) for v in sorted(VERDICTS)
        },
        "closest_prior_art_with_nontrivial_d2t_capability": _closest_prior_art(),
        "categories": records,
        "note": (
            "Task-reduction registry (P0-9). Fields not verifiable from full "
            "text are marked UNKNOWN_FULL_TEXT_OR_REDUCTION_MISSING; no value "
            "is guessed. Verdicts grounded in repo analysis reference the "
            "frozen comparator set of track_c_primary_decision.json."
        ),
    }
    return registry


def registry_sha256(registry: Optional[dict] = None) -> str:
    """Deterministic sha256 of the registry's canonical payload."""
    reg = registry if registry is not None else build_task_reduction_registry()
    canonical = json.dumps(reg, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def write_registry(path: str) -> dict:
    """Write the registry JSON to ``path`` (UTF-8, atomically)."""
    import os
    import tempfile

    reg = build_task_reduction_registry()
    text = json.dumps(reg, indent=2, ensure_ascii=False) + "\n"
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".task_reduction.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return reg
