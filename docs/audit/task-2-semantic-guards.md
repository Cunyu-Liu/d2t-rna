# Task 2 probability semantic guards

## Authority and scope

- Frozen contract: `contracts/D2T-RNA-v6.1-frozen-plan.md`
- Contract SHA-256: `87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d`
- Registered commit title: `feat(probability): separate empirical QA from model-conditional risk`
- Task 2 acceptance run: `task2-acceptance-20260730T001620p0800`

Task 2 implements structural semantic guards and exact rational candidate-bound arithmetic. It does not replay a scientific proof, execute observed-data QA, or issue a scientific RiskCertificate.

## Pinned semantic inputs

`manifests/task2_semantic_registry.json` is parsed with duplicate-key rejection and authenticated against canonical root:

```text
25604dac2cf94384d3c908293e2139c2f96321cb1582668647b651923fbb2c28
```

Registry membership authenticates an identifier, role, and release commitment. It does not turn a `RegistryRef` or `ProofArtifactRef` into a proof verdict.

The all-abstain failure policy has a committed canonical preimage at `manifests/task2_failure_policy_abstain_all.json`. QC, GOF, solver, yield, and unknown failures all map to `ABSTAIN`.

## Scope state machine

- `FINITE_OBSERVED_DATASET_SUBSAMPLING` is restricted to the `D_obs` commitment, subsampling index `I`, and the full-observed-dataset empirical feature-distribution target. It rejects `formal_scientific_risk_guarantee=true` and cannot emit latent, prospective, or new-library risk.
- `WITHIN_REALIZED_LIBRARY_MODEL_CONDITIONAL` binds the realized-library object and hash, sampling law, observation model, nuisance parameter space, weighting law, duplicate/ESS policy, target, and proof references. Complete references remain `PENDING_PROOF_REPLAY`.
- `SYNTHETIC_KNOWN_CHANNEL` binds a typed known-channel object, sampling law, target, estimand, support definition, and channel-registration proof. It remains `PENDING_TASK_4`.
- `NEW_LIBRARY_ROBUST_MODEL_CONDITIONAL` is a hard no-go in v1.

## Split and nuisance state machine

Zero read or dependency-unit overlap is never promoted to statistical independence. Task 2 has no verified-independent credential; its split assessments always require abstention for scientific issuance.

For `CONDITIONALLY_INDEPENDENT_UNITS_GIVEN_NUISANCE`, two structurally distinct paths are supported:

1. the certificate conditions on the same registered nuisance sigma-field; or
2. a typed, hash-bound uniform-worst-case-over-nuisance evidence object links the split sigma-field, certificate sigma-field, nuisance parameter space, and proof artifact.

Both paths remain pending proof replay. A random finite partition is marked as requiring a finite-population joint-law artifact and cannot be serialized as an iid or independent split.

## Risk and receipt boundary

Candidate arithmetic uses exact `Rational` values only:

- tower-uniform and abstain-outside-validity candidate arithmetic preserve `delta`;
- continue-decision outside a good event uses exactly `delta + (1-delta)rho`;
- `NOT_AVAILABLE` requires a null unconditional bound;
- the registered decisive-implies-noncoverage route uses the exact complement of uniform coverage;
- all v1 prospective unconditional bounds are rejected;
- effective-molecule conditioning requires a structured object cross-bound to the realized library, dependency unit, count definition, and conditioning sigma-field.

A caller-supplied fixture receipt is rebound to the probability space, split, scope prerequisites, nuisance handling, certificate, risk evidence, failure policy, semantic-registry root, verifier release, verifier configuration, and claim set. Its proof and log bytes are not authenticated in Task 2, so a fixture `PASS` can only yield `TEST_FIXTURE_BINDINGS_MATCHED` with:

```text
certificate_issued = false
scientific_claim_authorized = false
```

Caller-supplied formal receipts always return `NOT_ISSUED_FORMAL_VERIFIER_UNAVAILABLE`. Task 4 must introduce an authenticated replay runner and a separate verified credential rather than upgrading a Task 2 assessment.

## Acceptance wording

Verified engineering statements:

- Task 2 structural semantic guards pass.
- Exact candidate-bound arithmetic tests pass.
- Registry, reference, prerequisite, nuisance, receipt, and candidate hash bindings pass.
- Scientific certificates issued: 0.

Still unestablished:

- actual indifference probability or uniform coverage;
- statistical independence;
- within-library proof validity;
- exact synthetic risk-coverage proof;
- observed-dataset closure or empirical QA execution;
- truth blinding or Lock D reveal;
- prospective, new-library, native T4, or population-level guarantees.
