# Task 5 scenario, planner, and baseline evaluation

## Authority and entry gate

- Frozen contract: `contracts/D2T-RNA-v6.1-frozen-plan.md`
- Contract SHA-256:
  `87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d`
- Registered commit title:
  `feat(evaluation): unify proof manifests and baseline feasibility`
- Task 5 entry gate:
  `/mnt/cunyuliu/d2t-rna/artifacts/gates/task5-entry-gate-open-20260730T165235p0800.json`
- Entry-gate SHA-256:
  `01f172eb9d1fa3ee92cb763b995e379a572c5a74c9d3da2678b704192521a725`
- Test-first record:
  `/mnt/cunyuliu/d2t-rna/artifacts/runs/task5-red-20260730T165809p0800/red-test.json`
- Test-first record SHA-256:
  `27fc9fb4ed15dd970d5e75e53a7437440cb797384163f7ca3e060eb67621629e`
- Raw red pytest transcript:
  `/mnt/cunyuliu/d2t-rna/artifacts/runs/task5-red-20260730T165809p0800/pytest-red.log`
- Raw red transcript SHA-256:
  `1e43f7ab5edbc879f54535ec8f560a4a1f82a52b80ff58d911ed580b8919ff84`

Task 5 is a CPU software and exact-synthetic evaluation stage. It does not use
real RNA outcomes, train a model, issue a `RiskCertificate`, or authorize a
prospective, new-library, native-T4, population, or other scientific
conclusion.

## Preserved rejected implementation evidence

The first integrated implementation passed 31 Task 5 tests under the
registered remote CPython 3.11 environment. That test pass was subsequently
rejected by adversarial review and was not promoted to acceptance.

- rejected green log:
  `/mnt/cunyuliu/d2t-rna/artifacts/runs/task5-green-20260730T172054p0800/evaluation.log`
- log SHA-256:
  `bd835c95635ccfd9c3f719175e45abe526979e622d6176fda303f43680437635`
- fail-closed pause:
  `/mnt/cunyuliu/d2t-rna/artifacts/runs/task5-green-20260730T172054p0800/adversarial-pause.json`
- pause SHA-256:
  `a4dd12f908d856f43340b383dd88b9f0ac0350807560a0e5768b2b84e10bc7f0`

The rejected design trusted hash-only scenario assertions, summary-only
baseline records, and mutable in-process checker behavior too far. Those
failures are retained as evidence; passing the original 31 tests is not an
acceptance condition for the corrected implementation.

The fail-closed repair subsequently passed the corrected targeted suite in the
registered remote CPython 3.11 environment. This is repair evidence, not the
Task 5 acceptance gate:

- corrected targeted run:
  `task5-repair-green-20260730T180030p0800`
- corrected evaluation log:
  `/mnt/cunyuliu/d2t-rna/artifacts/runs/task5-repair-green-20260730T180030p0800/evaluation.log`
- log SHA-256:
  `79a108f97f827b5dc5ef10b251d96ba318153c9fefc7afb37cda07e0263dd536`
- result:
  `56 passed, 0 skipped`
- repair evidence record:
  `/mnt/cunyuliu/d2t-rna/artifacts/runs/task5-repair-green-20260730T180030p0800/repair-test.json`
- repair evidence SHA-256:
  `e982547b0f3bc5de9a10fa0d806b01bdb41c1e6719ab7f4a09f87e2989684733`

That 56-test result was itself subjected to a second independent adversarial
review. The review found that the implementation still underestimated a
multi-event coverage union bound, allowed exact-formal provenance and a
complete RORC path claim to be supplied by callers, and did not freshly replay
the Task 2 semantics behind the `RiskCertificate` consumed by the feasibility
assessment. Task 5 therefore remained paused; the 56-test run was not
promoted:

- second fail-closed pause:
  `/mnt/cunyuliu/d2t-rna/artifacts/runs/task5-cross-audit-pause-20260730T181604p0800/cross-audit-pause.json`
- second pause SHA-256:
  `0315494d9dedc60730543773c1503c96df8122a738e8edec7ff309130f8f79e5`
- second pause status:
  `PAUSED_FOR_FORMAL_PROVENANCE_REPAIR`

Two subsequent integrity reviews found additional runtime and provenance
failures. First, the Task 2 evaluator was execution-bound but the Task 5
wrapper dispatching that evaluator was not. The risk replay and every
downstream CFA claim were paused again:

- risk-wrapper pause:
  `/mnt/cunyuliu/d2t-rna/artifacts/runs/task5-risk-wrapper-pause-20260730T192413p0800/risk-wrapper-pause.json`
- risk-wrapper pause SHA-256:
  `5de706de64c39aab350d1679242d62809dad94c48f9f0c656f604d44021a679c`
- risk-wrapper pause status:
  `PAUSED_FOR_RISK_WRAPPER_EXECUTION_CLOSURE_REPAIR`

The next review found that the live planner witness verifier was not bound,
the RORC 16-path count did not also prove path uniqueness, and a formal
scenario could share a conditioning sigma-field with a risk bundle while
using a different probability space. Those claims remained blocked:

- planner/RORC/CFA pause:
  `/mnt/cunyuliu/d2t-rna/artifacts/runs/task5-runtime-provenance-pause-20260730T194019p0800/runtime-provenance-pause.json`
- planner/RORC/CFA pause SHA-256:
  `9a4cd3aff53140e5cdef1a7a4cda4504d45fc6ed49db3a96288d15badb7ece8c`
- planner/RORC/CFA pause status:
  `PAUSED_FOR_PLANNER_RORC_CFA_PROVENANCE_REPAIR`

The preserved rejected-green and repair-green records remain immutable
historical evidence. None of these records is an acceptance artifact.

## Preserved combined-suite failure and parent-binding repair

The first full candidate run reached the combined gate after passing all 109
evaluation tests. It then failed six nested-isolation tests and terminated
before the full-suite stage:

- run ID:
  `task5-acceptance-20260730T201740+0800`
- evaluation result:
  `109 passed, 0 failed, 0 skipped`
- combined result:
  `416 passed, 6 failed, 0 errors, 0 skipped`
- terminal stage:
  `TASK5_CANDIDATE_FAILED_STAGE=pytest_combined EXIT_CODE=1`
- run-log SHA-256:
  `9d1a848de575342bbaaf67d530a214fe51ca94b63643688de69235de0186dfd4`
- evaluation JUnit SHA-256:
  `14324750b652ff4b686c58664e4d0a4c0a514100d8adc0d9213b32100ccdd82b`
- combined JUnit SHA-256:
  `a3c1e3dc175ddeef292c489adc9edece83c28148372ee6ad138592f2e1b9ae48`
- immutable failure record:
  `/mnt/cunyuliu/d2t-rna/artifacts/runs/task5-acceptance-20260730T201740+0800/failure-record.json`
- failure-record SHA-256:
  `84dd9e3767511faeb6b15991d3cce78befaba71a4016b5c27d528e6d9105ffce`

All six failures occurred before a nested child process was started. The Task 5
candidate and final runners set a run-specific `sys.pycache_prefix`, which
correctly activates the strict parent-digest checks in
`tests/exact/conftest.py`, but the runners had not exported the two pre-frozen
Task 4 subclosure digests. The resulting
`parent Task 4 dependency digest is unavailable` error was fail-closed
behavior, not evidence of an unstable canonical hash or a scientific failure.
The passing evaluation stage remains diagnostic evidence only; it is not
Task 5 acceptance.

The repair preserves that check. Each Task 5 runner now derives a distinct,
canonical parent-binding artifact from the already frozen pre-test snapshots:

- dependency digest: the inner Task 4 runtime-dependency snapshot, not the
  outer Task 5 snapshot;
- source digest: the current Task 5 source index projected onto the exact
  pinned Task 4 historical source-path set, not the full Task 5 index and not
  the old Task 4 acceptance digest.

The runners overwrite any caller-provided values, export both digests before
the first pytest stage, and record them in the transcript. The nested child
still starts with the fixed clean `TASK4_CHILD_ENVIRONMENT`, independently
recomputes its runtime/source closure, emits a nonce-bound receipt, and is
checked by the parent against the frozen digests. Missing, malformed,
wrong-domain, stale, or tampered digests remain hard failures. Because the
repair changes the source index, the failed run cannot be resumed or combined
with later JUnit files; acceptance requires a new run ID and every gate from
the beginning.

A first targeted-repair run then stopped before executing the six selected
tests because the verifier had registered the raw red transcript under the
nonexistent basename `evaluation.log`. The extant `pytest-red.log` bytes
matched the already registered SHA-256 exactly, so the only permitted repair
was to correct that path. The stopped run is preserved separately:

- run ID:
  `task5-parent-binding-repair-20260731T052401+0800`
- stopped stage:
  `historical_failure_replay`
- tests executed:
  `false`
- immutable failure record:
  `/mnt/cunyuliu/d2t-rna/artifacts/runs/task5-parent-binding-repair-20260731T052401+0800/failure-record.json`
- failure-record SHA-256:
  `39df71b945f826dcddcfe011c14f68c09f43866c6b1e925dc70d314324217f8d`

This path correction does not alter the transcript bytes, expected digest,
failure semantics, test selection, or acceptance gate. The next targeted
repair must use a fresh run directory and remains non-acceptance evidence.

The fresh targeted repair then replayed all historical failure evidence and
ran precisely the six previously failing nested-isolation nodes:

- run ID:
  `task5-parent-binding-repair-20260731T053556+0800`
- result:
  `6 passed, 0 failed, 0 errors, 0 skipped`
- source stability:
  pre-test and post-test snapshot SHA-256 both
  `1735169497a0c8988666b6710618c8ab2209f8ee353b7d72dac2ccac0be21605`
- Task 4 parent dependency digest:
  `f7ad6b454f64ce2d3174a01023f5a40ef88fd3c99e1d0dd38c939a13da18d26e`
- Task 4 parent source digest:
  `355d452bda9fd59cda6e4f88ba138cfce14f10097a825a54f9ed70b3f4abd134`
- canonical repair record:
  `/mnt/cunyuliu/d2t-rna/artifacts/runs/task5-parent-binding-repair-20260731T053556+0800/repair-record.json`
- repair-record SHA-256:
  `801b248a0677a213c921c899be928aa7970c6161619d3c66a5d4066cb0aec643`
- status:
  `CORRECTED_TARGETED_GREEN_NOT_ACCEPTANCE`

This establishes the runner-plumbing repair only. It is not a substitute for
the evaluation, combined, and full gates of a new candidate run.

## Preserved manifest-build canonical-container mismatch

A later candidate completed all three test stages, but it was never accepted:

- candidate run ID:
  `task5-acceptance-20260731T055458+0800`
- diagnostic results:
  `115 passed`, `428 passed`, and `543 passed`
- manifest-build run ID:
  `task5-manifest-build-20260731T234517+0800`
- terminal stage:
  `source_snapshot_equivalence`
- immutable failure record:
  `/mnt/cunyuliu/d2t-rna/artifacts/runs/task5-manifest-build-20260731T234517+0800/failure-record.json`
- failure-record SHA-256:
  `549d722e83d1e9e00ac804097abf12e96e1997505b54dbcc3f474c5b43c3ae63`
- build-log SHA-256:
  `f34ab4266d44fa6acb3db5ac48ab9638b8777e0dbc0106f84e3575abbe9b9732`
- exit-code evidence SHA-256:
  `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865`
- candidate pre/post source snapshot SHA-256:
  `10dbf88b480232e1ba3ee71a3b5ae1a12dba43f5eae601970f444ee2734f0fb8`
- result:
  `manifest_created=false`,
  `acceptance_authorized=false`, and
  `scientific_conclusion_authorized=false`

The loaded JSON snapshot represented arrays as Python lists while the live
builder represented the same registered values as tuples. The source
snapshot's canonical object SHA-256
`089ce9d1eca459ab753635ca5e5cfcc822e0d96a192539b90915e290ca048b7d`,
its inner source-index SHA-256
`07451efcb8e5a3eaadea3e192298e4153adc240772effcaf9644299d587054c7`,
and the runtime snapshot's canonical SHA-256
`1a84f1886c2dd66e8f264dd9bd4fa83cc6a5823c215809b3dc73276c5cf38358`
were identical on both sides. This was a Python container-identity mismatch,
not source or runtime drift and not a scientific result.

Builder, verifier, and post-commit closure now compare snapshot objects by
canonical JSON bytes. The immutable failed candidate ID is also explicitly
disallowed. Because both the correction and this evidence registration alter
the source index, the old candidate and all of its JUnit, fixture, snapshot,
and log artifacts remain diagnostic failure evidence only. A fresh run ID
must rerun evaluation, combined, and full before another manifest build.

## Scenario proof boundary

A scenario proof manifest is not authorized by possession of a caller-chosen
artifact hash. Formal status requires a registered method-specific artifact
whose law, probability mass, risk events, coverage events, numerical error,
and omitted mass are replayed by the executing verifier. In the present
implementation, the only formal path embeds the Task 4 exact synthetic report
and all of its raw replay inputs, resolves a fixed production confidence rule,
and freshly calls the Task 4 production replay engine. Generic caller-supplied
exact atoms, verified-interval records, and certified-truncation records remain
nonformal until a corresponding independent production replay runner exists.
Monte Carlo evidence must bind a schema-valid, internally bounded
`RiskCertificate`, is always labeled
`RISK_CERTIFIED_COVERAGE_PREDICTED`, and cannot be upgraded by wrapping it in
another model. Downstream feasibility use separately requires the full Task 2
semantic replay bundle.

Finite aggregation replays every per-scenario artifact and uses only:

```text
maximum risk upper bound across registered scenarios
minimum coverage lower bound across registered scenarios
```

The aggregate records its finite scenario probability law, accounted mass,
coverage union-bound derivation, and complete per-scenario manifests.
Hypothesis region, coverage core, conditioning sigma-field, bound registry,
and estimand bindings must be comparable. The claim scope remains
`FINITE_REGISTERED_SCENARIOS_ONLY`; interpolation or extrapolation to a
continuous uncertainty set is forbidden. The coverage union bound is the
capped sum of every registered coverage-failure upper bound within every
registered scenario. It deliberately does not substitute a maximum over
multiple required events.

## Independent bounded-integer checker and planner failures

The independent checker operates on a canonical, bounded integer feasibility
model with exact `Rational` arithmetic. It distinguishes the available control
library from the complete registered fixed-horizon design class. A hard global
state cap and schema complexity limits are checked before enumeration. A
complete exact witness establishes feasibility; only exhaustive enumeration
can establish infeasibility.

The checker binds and verifies its executing code/runtime closure before and
after enumeration. A serialized receipt is not a bearer proof: promotion of a
planner failure requires a fresh independent replay from the raw model.
Planner classification separately binds its own executing closure and the
live witness verifier before and after classification. A caller cannot replace
the witness predicate and retain a valid `planner_witness_verified` record.

Planner termination reasons are a closed enumeration. Timeout, solver error,
numerical failure, unknown termination, checker resource refusal, and
incomplete evidence all map to `PLANNER_UNRESOLVED`. A registered planner that
merely finds no certificate remains:

```text
NO_CERTIFICATE_FOUND_BY_REGISTERED_PLANNER
```

Only a freshly replayed exhaustive checker may promote the result to:

```text
NO_CERTIFICATE_WITHIN_AVAILABLE_CONTROL_LIBRARY
NO_FEASIBLE_FIXED_HORIZON_TEST_WITHIN_REGISTERED_DESIGN_CLASS
```

These are statements about the frozen registered finite model, not biological
infeasibility or a scientific RNA certificate.

The `CoverageFeasibilityAssessment` embeds the complete finite scenario
aggregate rather than accepting a caller-selected scenario hash. It freshly
replays all nested scenario artifacts, records the aggregate and per-scenario
manifest hashes as derived values, and requires the scenario aggregate and
`RiskCertificate` to bind the same conditioning sigma-field. It also embeds
the complete Task 2 risk-evaluation inputs and assessment, freshly invokes the
Task 2 production evaluator, and requires the nested and outer certificates to
be byte-identical. The assessment still authorizes no scientific claim and no
serialized object is a bearer credential. When the scenario aggregate is
formal, every Task 4 raw-input artifact is parsed again and its complete
`ProbabilitySpaceSpec` must be byte-identical to the risk bundle probability
space; a matching conditioning sigma-field alone is insufficient. The CFA
builder, model validator, parser, scenario replay, risk replay, and planner
classifier are also bound into a pre/post checked execution closure.

## Common feasibility binding and baseline semantics

The method and every registered baseline share one replayed binding containing
the same:

- `RiskCertificate`;
- `CoverageFeasibilityAssessment`;
- yield scope;
- cost table;
- expansion order;
- required baseline registry.

Each baseline registry member fixes its implementation hash, configuration
hash, and random-seed root. A baseline batch contains exactly the complete
ordered schedule of 100 domain-separated, hash-derived seeds. Every seed
result is bound to the baseline identity, common binding, seed root,
implementation, configuration, and execution artifact. The same result batch
cannot be renamed or attached to another binding.

Task 5 provides the wrapper and comparison semantics, not an authenticated
runner for arbitrary registered baseline implementations. Seed outcomes,
batches, summaries, method results, and comparisons therefore state
explicitly that their execution artifacts were not replayed, their outcomes
were not execution-verified, and no release or scientific claim is authorized.
Hash-consistent caller declarations cannot promote themselves by being nested
inside a comparison.

The summary and comparison layers intentionally remain structural,
execution-unverified non-bearers rather than authenticated runner receipts.
They must be rebuilt in the isolated acceptance process and replay from
serialized inputs under the frozen source/dependency snapshot. Runtime
statistics or dispositions from a modified in-process dependency graph are
not release evidence.

Summary statistics are rebuilt from the complete batch. `POS_INF` participates
in the extended median; `NA` never participates in ordering. Any unresolved
seed makes the primary extended median `NA`, while the resolved-only
diagnostic remains explicitly secondary. Feasible-only median and IQR use the
registered exact rational algorithm. There is no best-of-100 API.

A comparison must contain exactly every member of the frozen rival registry
and must replay every submitted batch and summary. A method result is itself
bound to the same common object. `FEASIBILITY_DOMINANCE` is available only
when the method is feasible and every registered rival completed as
infeasible; it carries no zero cost ratio and authorizes no scientific
superiority claim.

## RORC fail-closed evaluation

The production RORC assessment path always returns `ABSTAIN`, with stable,
deduplicated registered reason codes. A separate path audit enumerates the
complete powerset of the four frozen reason codes and actually executes every
path through the production assessment function; only that audit may state
that all registered paths abstain. The powerset is generated internally and
must contain 16 unique paths covering all four reasons; path count alone is
insufficient. Retrospective metrics are rebuilt from a
canonical per-case manifest rather than caller-supplied aggregate counts, but
remain explicitly observational and do not claim that their case set is a
complete registered execution path set. The manifest reports both total
decisive outputs and incorrect decisive outputs.

Coverage change after omitting the third state is retained with its sign. An
unexpected coverage increase is recorded as an anomalous result rather than
discarded to obtain a desired direction. RORC remains
`HISTORICALLY_SEMANTICALLY_EXPOSED_RETROSPECTIVE`, and no held-out claim or
diagnostic tuning authorization is produced.

## Historical Task 4 boundary

Task 4 was accepted at commit
`4793026c1e709b7ca78042b8a10294fe569d7b8c`. Its source-index builder remains
closed: invoking it on a descendant tree containing Task 5 execution paths
must fail rather than silently reissue a Task 4 manifest. Task 4 regression
tests operate on its explicit historical path set, while the immutable Task 4
closure and public Git commit remain the acceptance authority.

## Acceptance interpretation

Smoke tests, a synthetic fixture, a serialized manifest, a planner no-find
result, Monte Carlo coverage, a feasibility-dominance result, or training-set
performance cannot be reported as a final scientific conclusion. Task 5 may
close only after the corrected targeted suite, all adjacent regression suites,
full suite, source/dependency audit, independent manifest replay, focused Git
commit, public push, and post-commit closure all pass without skips hiding a
required check.
