# Task 4 exact enumeration and coverage engine

## Authority and scope

- Frozen contract: `contracts/D2T-RNA-v6.1-frozen-plan.md`
- Contract SHA-256: `87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d`
- Registered commit title: `feat(exact): add exhaustive risk and coverage verification`
- Entry gate:
  `/mnt/cunyuliu/d2t-rna/artifacts/gates/task4-entry-gate-open-20260730T012421p0800.json`
- Test-first evidence:
  `/mnt/cunyuliu/d2t-rna/artifacts/runs/task4-red-20260730T013744p0800/red-test.json`

Task 4 is a CPU exact-arithmetic software verification stage. It does not use
real RNA data, training, scientific scoring, or GPU validation. Its strongest
possible output is an exact synthetic risk–coverage report under a registered
finite known-channel model.

## Support preflight

The support contract keeps three quantities separate:

- the registered state count \(K\), with \(1\le K\le3\);
- the number of actions \(U\), with \(1\le U\le3\);
- each action alphabet size \(m_u\), with \(1\le m_u\le4\).

For one action, the sample size can reach 80. For two or three actions, the
joint total cannot exceed 40. Identifiers are unique and canonically ordered.
The support preflight computes

\[
\prod_u {N_u+m_u-1\choose m_u-1}
\]

with exact integer arithmetic and a capped multiplication check. A public
enumeration entry point performs this check synchronously before constructing
the internal composition iterator. It does not accept a caller-provided size
receipt as authorization. A support larger than \(10^7\) raises
`EnumerationTooLarge` before any Cartesian iterator or support-sized
allocation is created.

The support formula describes count-vector geometry only. It does not imply
independence. The Task 4 probability implementation therefore accepts only an
explicitly typed independent-multinomial law and binds that law to the exact
support hash. Unregistered dependence structures fail closed rather than being
silently factorized.

`ExactSupportPlan` is only a structural artifact. A downstream gate must call
`replay_support_plan` against the raw spec; parsing a plan is not acceptance.
The replay fixes the cap to \(10^7\), recomputes every factor, and requires
canonical object equality.

## Exact probability enumeration

Each action probability vector is a tuple of exact `Rational` values. Negative
probabilities, binary floats, non-unit sums, action mismatches, and alphabet
length mismatches are rejected. Count-vector mass is computed as

\[
\frac{N_u!}{\prod_j x_{uj}!}\prod_j p_{uj}^{x_{uj}}
\]

using `fractions.Fraction`; the joint law is the product of the explicitly
registered independent action laws. Zero-probability categories remain in the
support, so they cannot shrink the preflight count.

Enumeration is deterministic, lazy, and streaming. A successful mass audit
requires the observed outcome count to equal the preflight count and the exact
total mass to equal one. The exact path records zero omitted mass and zero
numerical error; it does not convert a floating-point tolerance into an exact
claim.

Likewise, a serialized `ProbabilityMassAudit` is not a bearer credential.
`replay_probability_mass_audit` re-enumerates the raw support and law and
requires exact equality of the support-plan hash, law hash, count, total mass,
and complete streaming transcript.

## Confidence sets and decisions

Each finite parameter point carries an exact loss. The engine derives its
hypothesis region from registered exact thresholds:

```text
loss <= tau0          -> H0
tau0 < loss < epsilon -> INDIFFERENCE
loss >= epsilon       -> H1
```

Callers cannot supply a separate region label. Confidence-set results are
bound to the complete parameter-universe hash and require sorted, unique,
known members. The parameter family carries the actual typed Task 2
`TrustedSemanticRegistry`, `ProbabilitySpaceSpec`,
`SyntheticKnownChannelPrerequisites`, and `ExactSamplingLawManifest`, rather
than accepting opaque caller-supplied digests. Construction replays the trusted
registry, derives the parameter registry from every exact loss/law point,
checks every sampling-law entry exactly once, and re-runs the Task 2 synthetic
scope assessment. The only accepted disposition remains
`SYNTHETIC_PENDING_TASK_4`, with risk-certificate abstention and no formal
scientific authorization. An empty confidence set is an explicit failure and
abstains.

The registered deterministic decision rule is:

```text
nonempty confidence set contained in H0 -> CERTIFY
nonempty confidence set contained in H1 -> REJECT
empty, mixed, or indifference-containing set -> ABSTAIN
```

This matches the frozen error fields: at an H0 point the wrong event is
`REJECT`; at an H1 point it is `CERTIFY`; at an indifference point the
decisive event is `CERTIFY or REJECT`.

Every finite parameter point is evaluated separately over the full count
support. The report uses the maximum H0 wrong-reject probability, maximum H1
wrong-certify probability, maximum indifference decisive probability, and
minimum coverage. Indifference points never enter the H0 or H1 aggregation.
The indifference registry must be nonempty, so the \(1/20\) gate cannot pass
vacuously or by averaging a bad point with safe points.

## Outer approximation

The outer verifier recomputes both confidence sets for every count outcome,
including zero-mass outcomes. It requires the same support and parameter
universe and checks the actual relation

\[
\mathcal C_{\mathrm{exact}}(y)
\subseteq
\mathcal C_{\mathrm{outer}}(y)
\]

for every \(y\). It then recomputes both decisions. The only permitted
transitions are:

```text
CERTIFY -> CERTIFY or ABSTAIN
REJECT  -> REJECT or ABSTAIN
ABSTAIN -> ABSTAIN
```

A missing member, new decisive output, or decision flip raises
`OuterApproximationViolation`; no success receipt is returned.

The confidence procedure spec must match a hash of the executing plain Python
function. The general runtime-closure hasher recursively binds normalized code
objects, defaults, closures, referenced functions, modules, classes, built-ins,
and canonical state. Registered confidence callbacks use a stricter subset:
mutable closure/global state, module dispatch, ordinary helper classes,
unresolved names, and non-allowlisted built-ins fail before enumeration.
Strict callbacks are self-contained: helper functions cannot be captured as
globals, defaults, or closure values. Actual global-versus-built-in lookup
resolution is recorded.
The callback returns data only:

```text
(canonically_sorted_member_id_tuple, failure_reason_or_none)
```

It cannot construct `ConfidenceSetResult` or any other runtime class. The
trusted verifier checks the frozen ID grammar, exact tuple types, uniqueness,
ordering, and empty/nonempty failure semantics; it then injects the registered
parameter-universe hash into the canonical transcript record.
Bound data is limited to exact immutable atoms and recursively exact tuples;
container subclasses and all set/frozenset dependencies fail closed. Set,
list, and mapping construction opcodes are forbidden, and frozenset code
constants are rejected recursively. This prevents a canonicalized container
view or a sorted hash descriptor from masking dynamic dispatch or
`PYTHONHASHSEED`-dependent execution order.
Function/class formatting, percent formatting, identity tests, and
float/complex constants are also excluded. Those forms can otherwise expose
process addresses or exploit non-reflexive NaN identity shortcuts while
leaving a value-only code descriptor unchanged. The broader non-strict
runtime-closure hash uses deterministic graph node IDs for executable aliases,
so rebinding a target to a different already-visited function changes the
closure hash.
No runtime builtin is allowlisted in the registered callback DSL, and
exception-handling control flow is forbidden. Environment- or
resource-dependent exceptions therefore abort verification instead of being
converted into an accepted decision. Class/mapping/sequence pattern opcodes
are forbidden because they can invoke dynamic attribute or protocol dispatch.
The remaining bytecode is checked against a positive opcode allowlist covering
only local/closure loads, immutable tuple operations, comparisons, bounded
control flow, and arithmetic. All call opcodes are excluded. Unknown current
or future interpreter opcodes fail closed.
At clean module import the verifier also freezes the construction, validation,
serialization, MRO, field, and compiled Pydantic runtime identities for every
Task 4 model in its execution closure. Class mutation makes both callback
hashing and engine hashing fail before enumeration.
The same import-time baseline binds `fractions.Fraction` construction,
numerator/denominator descriptors, every rich comparison, and every arithmetic
protocol used by the exact engine. Evaluation checks that baseline before raw
input revalidation and again through the post-enumeration engine hash, so a
runtime arithmetic mutation cannot preserve the registered engine identity.
The bound surface includes the complete class dictionary and MRO, inherited
construction, property accessors, nested function closures, referenced module
attributes, the actual `Fraction` aliases used by enumeration and coverage,
numeric-ABC dispatch identities, and exact arithmetic canaries. Raw type and
module lookup primitives are themselves identity-bound. This protects the
registered single-process CPython execution against persistent Python-level
mutation; it is not a claim against a privileged concurrent process that can
rewrite and restore interpreter memory.
This is deliberately a restricted pure-bytecode callback DSL, not an
authorization for arbitrary plain Python. Attribute or method dispatch,
comprehension-created nested functions, imports inside a callback, and other
unregistered bytecode forms fail closed even when a particular use would look
side-effect-free. Expanding that language requires a separately reviewed,
target-specific allowlist and new adversarial tests.
Source paths are removed from nested code objects, while the exact Python
runtime is explicitly bound. Each outcome is evaluated twice, and executable
state is re-hashed after completion.

The normalized function hash uses the non-adaptive baseline instruction stream
reported by CPython, plus exact constants, names, closure bindings, exception
tables, and line tables. It never serializes a live code object or hashes the
adaptive `co_code` buffer. This prevents Python 3.11 quickening from making a
cold callback and the same warmed callback look like different programs. The
acceptance suite starts a fresh interpreter and also builds the registered
fixture twice in one warmed process; both paths must produce byte-identical
artifacts.

The outer proof binds exact and outer results in one paired transcript with a
completion footer, the full local verifier source/runtime closure, and a
verifier-configuration hash. The runtime closure includes every local semantic
helper used by the verifier and the Task 2 probability-space, registry, and
scope-validation sources. A helper replacement changes the closure hash, and
the hash is checked again after enumeration. An
`OuterApproximationAssessment` deliberately has no replay status.
`replay_outer_approximation_assessment` re-executes every raw input and returns
a distinct `OuterApproximationReplayCredential`. The credential is explicitly
non-bearer, still requires an externally trusted source-manifest anchor, and
cannot authorize a scientific certificate.

## Claim boundary

A successful `ExactSyntheticCoverageReport` is fixed to:

```text
probability_scope: SYNTHETIC_KNOWN_CHANNEL
claim_domain: EXACT_SYNTHETIC_KNOWN_CHANNEL_ONLY
evidence_grade: EXACT_RATIONAL_ENUMERATION
risk_certificate_issued: false
formal_scientific_certificate_authorized: false
prospective_claim_authorized: false
new_library_claim_authorized: false
```

The report itself has no replay status. Live replay returns a distinct
`ExactSyntheticCoverageReplayCredential` that binds the rebuilt report,
complete transcript, input bundle, engine closure, and verifier configuration.
The credential records `serialized_bearer_authorization: false` and
`external_source_anchor_required: true`; possession or deserialization is not
acceptance. A consumer must re-run the raw typed inputs and compare the engine
closure with the source-file hashes committed in the Task 4 acceptance
manifest.

It is not a `RiskCertificate`, a formal Task 2 proof-verification receipt, or a
Task 5 per-scenario scientific proof. Task 2 remains fail closed at
`NOT_ISSUED_SYNTHETIC_PENDING_TASK_4`; later integration cannot infer a real
RNA, prospective, new-library, native T4, or population-level guarantee from
this exact synthetic artifact.

The \(10^7\) support cap is a refusal threshold, not a runtime promise.
Enumeration is constant in support-sized memory, but `Fraction` time and
integer bit complexity can still be substantial. Large registered runs require
a separate run ID, resource budget, transcript path, and safe stop record; the
Task 4 acceptance suite uses independent micro-cases and cap-boundary checks,
not a \(10^7\)-outcome smoke run.

The acceptance micro-case is also checked against
`tests/exact/naive_oracle.py`. That oracle independently enumerates raw symbol
sequences, collapses them to count vectors, computes sequence probabilities,
derives decisions directly from member regions, and aggregates all pointwise
risk/coverage quantities. It does not import the production support iterator,
multinomial PMF, decision helper, coverage accumulator, or
`fractions.Fraction`. Its arithmetic is a test-only normalized integer pair
with an independent Euclidean GCD, exact operations, and cross-multiplication
comparison. Golden checks include exact H0/H1 zero/one behavior,
indifference \(1/64\), and uniform coverage \(63/64\). A multi-action case must
match it exactly. The boundary suite also requires the explicit `m=16,N=80`
request to raise `EnumerationTooLarge` before an iterator exists.

## Executable artifact gate

The v2 acceptance manifest is a pre-commit record with status
`READY_FOR_COMMIT`; it cannot close Task 4 by itself. Its verifier runs only in
the recorded CPython 3.11 and Pydantic runtime, rejects duplicate or
non-canonical JSON, binds the complete current source and test closure, parses
every fixture object into its strict registered model, cross-checks the
report/replay, outer/replay, and three mass-audit bindings, and then rebuilds
the registered fixture in a new directory under
`/mnt/cunyuliu/d2t-rna/artifacts/runs/<candidate-run-id>/verifier-replays/`.
The live-run directory must be a real directory inside the artifact root;
outside paths and symlinks fail before replay. All six registered files must
be byte-identical to that live rebuild.

Both candidate and final runners invoke every Python target through a
registered launcher using CPython `-I -S` and a run-specific
`-X pycache_prefix`. The launcher requires isolated, no-site, no-user-site,
ignore-environment, and safe-path flags; it refuses preloaded `site`,
`sitecustomize`, or `usercustomize`, retains only interpreter stdlib paths,
then explicitly adds the verified 3.11 site-packages directory, project `src`,
and project root in that order. It never processes the environment's `.pth`
files. Before running a target, the launcher rejects importable root-level
files or packages and unregistered top-level import surfaces under `src`.
The shell independently rejects root-level execution configuration and
symlinks, sourceless bytecode, or project native extensions under the complete
`src/tests/scripts` execution trees, clears all `PYTHON*` and `PYTEST*`
variables, and disables pytest plugin autoload.

The post-candidate audit put Task 4 back in `PAUSED` state after finding three
nested test processes that directly invoked `sys.executable -c`. Those
children did not inherit the launcher's `-I -S` flags or dedicated cache
binding, so `.pth`, `sitecustomize`, environment, and import-path effects were
outside the parent process's runtime-closure audit. All three call sites now
use one reviewed helper from `tests/exact/conftest.py`. It fixes the pinned
`.venv/bin/python`, invokes the same registered launcher with `-I -S`, fixes
the repository root and a minimal non-Python environment, and creates a fresh
exclusive non-symlink cache directory below the canonical parent run's
`pycache` prefix. This prevents collisions when exact, combined, and full
pytest stages exercise the same test; only a developer invocation with no
bound parent prefix falls back to a canonical pytest temporary directory
outside the repository. Before target code runs, the child imports the
verifier to freeze its runtime baselines, builds the complete source and
dependency snapshots, and replays process isolation plus the loaded-module
closure. The target executes in a separate globals mapping. After it returns,
the child rebuilds both snapshots, requires exact equality with the pre-target
records, and repeats the process and actual loaded-module closure before
exclusively creating a canonical `0600` receipt below the child cache. The
receipt binds a parent-generated challenge, target-source hash, cache path,
and the post-check source/dependency digests. In canonical runners, the parent
independently requires those digests to equal its logged pre-test source and
dependency snapshots; stderr and stdout are not receipt channels. The wrapper
converts every `BaseException`, including
`SystemExit(0)`, into failure, while a direct `os._exit(0)` leaves no receipt
and is rejected by the parent. Thus target code cannot establish the verifier
baseline and loaded child modules are not inferred from the parent process. A
real CPython 3.11 regression checks the exact five-entry
`sys.path`, all isolation flags, the absence of `site`, `sitecustomize`, and
`usercustomize`, the exact child environment, containment of its cache below
the parent run prefix, and the runtime-closure receipt. An AST regression scans
all indexed `tests/**/*.py` inputs and rejects any direct subprocess or
`sys.executable` use outside the single helper.

This is an attestation boundary for the frozen, source-indexed test targets,
not a claim that arbitrary hostile Python can be sandboxed inside its own
process. The parent challenge is defense in depth, not an unforgeability claim
against code deliberately introspecting its interpreter frames. Regressions
therefore cover normal completion, fake-marker plus `SystemExit(0)`, and
fake-success via `os._exit(0)`; only the reviewed call sites may execute.

The read-only audit confirmed that the old seam was exercised, not merely
hypothetical. A raw child had `isolated=0`, `no_site=0`, `no_user_site=0`,
`ignore_environment=0`, and `safe_path=False`; it loaded `site`, retained the
absent `python311.zip` entry, and obtained `d2t_rna` from the editable source
path processed by
`.venv/lib/python3.11/site-packages/__editable__.d2t_rna-0.1.0.pth`
(SHA-256
`97ca17de554ac4538788351be82ded9fea0a2c849554e5606064ca2e176b4bf5`).
The same prefix contains `distutils-precedence.pth` (SHA-256
`2638ce9e2500e572a5e0de7faed6661eb569d1b696fcba07b0dd223da5f5d224`).
These are read-only diagnosis facts without a dedicated artifact receipt; they
invalidate the older candidate as closure evidence but are not promoted to a
new acceptance artifact.

The cross-process canonical-hash test does not create a privileged
`PYTHONHASHSEED` exception. It runs four independent isolated children with no
Python environment inputs, requires the golden canonical digest from every
child, and verifies that the interpreter-generated hash probes include at
least two distinct randomized seeds. This remediation does not itself close
the gate: Task 4 remains `PAUSED` until a fresh canonical candidate, manifest,
registered commit, public push, and post-commit closure all pass.

The frozen source closure is discovered dynamically across every
`.py`/`.pyi` input and `py.typed` marker under `src`, `tests`, and `scripts`;
it must match the literal reviewed source index exactly.

The interpreter is not treated as trusted merely because a file is below a
directory named `lib/python3.11`. The runtime snapshot hard-binds the installed
Conda CPython package:

- Python `3.11.15`, build `h17756b0_1`, channel
  `https://repo.anaconda.com/pkgs/main/linux-64`;
- package archive SHA-256
  `6944434fac2bd369561fb68c5c961e6dd684bdf1f96b78e002d0926bb1dd1237`;
- installed Conda record
  `.venv/conda-meta/python-3.11.15-h17756b0_1.json`, SHA-256
  `5e81a63d79d4ca20e5f041e80e8c45712c91df377721422a9855f1c3465ec080`;
- executable target `.venv/bin/python3.11`, SHA-256
  `9aac6e55779c2bd3332d6a5fbf3b07257cf3e95b7f24a32b9a4e43c0b896a382`.

The record has 2,122 unique paths. The registered runtime selection contains
exactly 1,028 hardlink records: `bin/python3.11` plus 1,027 files below
`lib/python3.11`, excluding `site-packages`, `__pycache__`, and `.pyc`. The
current selected tree must have exactly the same path set, and every current
file must match its record `sha256_in_prefix`; an extra, missing, changed,
symlinked, escaped, or wrong-kind file fails closed. `.venv/bin/python` must be
the relative symlink `python3.11` to that same-prefix target. The snapshot also
binds the raw and resolved executable/prefix layout, all four Python prefixes,
stdlib and platform-stdlib roots, `DESTSHARED`, `SOABI`, `EXT_SUFFIX`,
`MULTIARCH`, implementation, version, and cache tag.

The absent `.venv/lib/python311.zip` path inserted by CPython startup is
removed when the launcher reconstructs `sys.path`; if the archive later
appears, the runtime snapshot fails, and a later reinsertion of even the
still-absent lexical path fails the verifier's final `sys.path` check.
Classification order is fixed because
`site-packages` is nested below the stdlib root: first one of the 12 pinned
distribution file maps, then the Conda-recorded interpreter stdlib, then the
reviewed project source index, otherwise rejection. Loaded stdlib `.py` files
must use a genuine `SourceFileLoader`; loaded native extensions must use a
genuine `ExtensionFileLoader`; in both cases the module, loader, spec origin,
package search locations, record member, and current bytes must agree. The
generated module name
`_sysconfigdata__linux_x86_64-linux-gnu` is the only file-backed stdlib name
allowed outside `sys.stdlib_module_names`; it is bound to CPython's own
sysconfig name resolver, its exact Conda-recorded source file, and a
`SourceFileLoader`. Genuine builtin and frozen modules are bound to their
CPython importers and the pinned executable rather than accepted as pathless
caller assertions.

Other file-backed modules must resolve through one of the three registered
classes; an external path or unknown file kind is rejected. The only
non-file execution entries are separately checked: the single-location
project `scripts` namespace, `pyexpat.errors` and `pyexpat.model` bound to the
record-backed `pyexpat` extension, and the pre-third-party-import
`typing.io`/`typing.re` aliases. Other pathless entries fail closed. Both
runner shells clear leading-underscore `_PYTHON*` variables as well as the
ordinary Python and pytest injection variables, and the verifier independently
requires them to remain absent.

The dependency snapshot additionally binds the versions and hashes of every
installed non-cache file for the fixed Pydantic, pydantic-core, pytest,
Hypothesis, sortedcontainers, Pygments, and transitive runtime distributions.
Every loaded site-packages Python or native module must belong to that
snapshot and match its live file hash. The launcher also refuses a
site-packages provider for the reserved project roots `d2t_rna`, `scripts`,
or `tests`. Project-native modules and unindexed project or third-party shadow
modules fail closed.

The historical gate is not accepted from self-consistent caller data. The
verifier pins the exact Task 3 closure, Task 4 entry gate, red record, and red
log paths and SHA-256 values. It recursively validates the entry/red JSON,
matches the complete preserved red-log bytes, and checks the Task 3 closure's
commit, synchronized public `main`, clean state, zero scientific certificates,
and fail-closed scoring boundary.

Later non-passing attempts are retained rather than rewritten as success:

- CPython 3.11 full-suite regex portability failure:
  `/mnt/cunyuliu/d2t-rna/artifacts/runs/task4-py311-exact-v2-20260730T061500p0800/run.log`,
  SHA-256
  `dd3cb796712d14101042ab7741f3e54005612d2c54896fa5aa19dbd5f275da84`;
- source snapshot from that failure:
  `/mnt/cunyuliu/d2t-rna/artifacts/runs/task4-py311-exact-v2-20260730T061500p0800/test_confidence.py.failed-source`,
  SHA-256
  `f39fe11fe63afb2d09ed9328e985cabc892e5c770b019e0a62ebfc4178ad3580`;
- the earlier fixture-hash candidate failure remains at
  `/mnt/cunyuliu/d2t-rna/artifacts/runs/task4-acceptance-20260730T031209+0800/run.log`,
  with its diagnosis at
  `/mnt/cunyuliu/d2t-rna/artifacts/diagnostics/task4/hash-diagnosis-20260730T031653+0800.log`.

These records are diagnostic history, not substitute acceptance anchors. The
successful CPython 3.11 recovery log at
`/mnt/cunyuliu/d2t-rna/artifacts/runs/task4-py311-exact-recovery-v2-20260730T064300p0800/run.log`
has SHA-256
`3d53d7e72db563b36f89a4a671609642e2633d3e305dd175f19760a34ea104ed`;
it remains supporting evidence until a fresh canonical candidate and the
post-commit closure both pass.

The later canonical candidate
`task4-acceptance-20260730T075659+0800` completed 149 exact, 279 combined,
and 394 full tests, but it is also supporting evidence only because the
acceptance verifier subsequently required a source change. Its immutable log
is
`/mnt/cunyuliu/d2t-rna/artifacts/runs/task4-acceptance-20260730T075659+0800/run.log`,
SHA-256
`79f5a7f56a024eaa345b3f1aa94fad5f263d438e4499311dba4b8e6cf318c09d`.
The manifest builder then correctly failed on the prefix-local native module
`.venv/lib/python3.11/lib-dynload/_typing.cpython-311-x86_64-linux-gnu.so`
because the earlier classifier treated the project-contained Conda stdlib as
an unregistered project native extension. The failed builder log is
`/mnt/cunyuliu/d2t-rna/artifacts/runs/task4-acceptance-20260730T075659+0800/manifest-builder.log`,
SHA-256
`5abd2b628b79e2e85628c1e06c9386da9f2de8dcadfec5e7500b30b47955e27a`.
The read-only runtime diagnosis is retained at
`/mnt/cunyuliu/d2t-rna/artifacts/diagnostics/task4/stdlib-classification-20260730T085751p0800/run.log`,
SHA-256
`3050bedfc489096c912290a0dbed2977cd24b4ca3018592ea415ec3b3c23bf84`.
No repository acceptance manifest or Task 4 commit was produced from this
attempt. After the verifier change, a new run ID and complete canonical
candidate are mandatory.

The candidate runner emits ordered stage markers and three hashed JUnit XML
files. The verifier derives the exact/combined/full test counts from both the
marked log sections and the JUnit testcase sets; fabricated summary lines,
skips, failures, duplicate test identities, reordered markers, a nonterminal
closure, paths outside the artifact root, or symlinks fail closed.
Before and after the test stages, both candidate and final runners recompute
the canonical digest of all 74 registered execution and test-input paths. The
index includes the Task 2 abstain-all failure policy and Task 3 historical
exposure registry JSON files read by the full suite, not only discoverable
Python inputs. A drift aborts the
runner, and the manifest builder, manifest verifier, and post-commit closure
all require both logged digests to equal the manifest's current
`source_index_sha256`. The generated Task 4 acceptance manifest itself is not
part of that index, avoiding a self-reference.
`build_task4_acceptance_manifest.py` derives the counts and hashes from that
completed run, writes an immutable draft under the run directory, performs the
full live verifier replay, and only then writes the repository manifest.
Candidate stdout is still captured by the outer controller and is therefore
supporting pre-commit evidence rather than a standalone trust anchor.

After the exact registered commit is pushed, a distinct post-commit closure
does not accept a caller-supplied final log. Its builder first requires the
clean registered `main`, exclusively creates a canonical final run directory
and `run.log`, and directly launches the final runner through fixed
`/bin/bash` with a complete allowlist environment. Both runners remove shell
function, `BASH_ENV`/`ENV`, Git/GitHub, Python, and pytest injection inputs,
fix `PATH`, and use `/usr/bin/git`; repository-file audits consume NUL-delimited
paths. The closure strictly parses the full unique ordered stage sequence,
requires all dependency, Git, manifest, secret, and large-file markers, and
requires the exact/combined/full pytest counts to equal the candidate
manifest's monotone counts. It repeats the live manifest replay and then uses
an anonymous, noninteractive HTTPS `ls-remote --symref` from a clean Git
environment to prove the unchanged commit, public GitHub `main`, and default
branch `main`. The closure also requires the Task 4 commit's parent to be the
accepted Task 3 SHA and its changed-path set to equal the reviewed Task 4
whitelist exactly. That whitelist contains 28 paths, including
`tests/contracts/test_canonical.py`, because closing the nested-child seam
necessarily changed the cross-process canonical-hash test. Any nonzero
transcript is preserved. Only that
`CLOSED_ACCEPTED_PUSHED_PUBLIC` artifact closes Task 4. Neither the pre-commit
manifest nor any serialized replay credential is a bearer authorization.
