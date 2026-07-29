# Task 1 schema design review

## Decision

Task 1 may freeze strict schema primitives and a structurally tamper-evident lock chain. It may not, by itself, establish chronology, external pre-registration, semantic blinding, probability validity, or a scientific risk certificate.

## Frozen canonical core

The canonical JSON representation permits only:

- UTF-8 strings;
- integers, with booleans kept distinct;
- booleans;
- null;
- arrays;
- objects with unique string keys;
- normalized rational objects with integer numerator and positive denominator.

Binary floats are excluded. Dictionary keys are sorted, separators are compact, Unicode is emitted directly as UTF-8, and no trailing newline is added. Raw JSON parsing rejects duplicate keys, invalid UTF-8, and non-finite number tokens before Pydantic validation.

Every contract model uses:

```python
ConfigDict(
    extra="forbid",
    frozen=True,
    strict=True,
    validate_default=True,
    allow_inf_nan=False,
    revalidate_instances="always",
)
```

Nested collections are tuples of frozen models. `model_construct()` and unchecked `model_copy(update=...)` are not accepted production construction paths. The verifier recursively checks exact registered model types and stored field sets, strictly rebuilds each object, and recomputes every digest. Top-level, nested, subclass, or extra-field injection therefore cannot pass merely because it is a Pydantic object.

## Registry references for underspecified fields

The source contract names several fields without freezing their member sets, including measurement modality, eligibility status without direction, dependency unit level, failure event policy, EvidenceRole, and estimand.

Task 1 does not place unconstrained prose in those fields. It uses a strict pair:

```text
registry_id
registry_hash
```

This freezes the schema shape while requiring later stages to commit to the actual registry. It does not claim that a registry is scientifically valid merely because it is hash-addressed.

## Hash meanings

Hash types accept exactly 64 lowercase hexadecimal characters.

- Canonical contract hash: SHA-256 of the canonical JSON bytes.
- Raw-file hash: SHA-256 of the exact file bytes.
- Truth payload hash: an opaque commitment field at Task 1.
- `asset_hash`: raw-file SHA-256 of the exact sealed reveal package bytes, including numeric, semantic, and decision-binding components. It is the pre-D root against which Task 3 must verify the complete reveal; the component hashes provide additional exact checks.

Hash-only truth fields, including `asset_hash`, are not assumed to hide low-entropy directional content. Task 3 must define and verify the sealed reveal construction and semantic sanitizer before any blinding claim is allowed.

## Lock-chain and payload-binding boundary

The A→B→C prefix is validated from duplicate-safe raw link and payload JSON. It enforces:

- a single chain ID;
- exact forward stage order through the requested terminal stage;
- exact `SealedTruthLockPayload` type and registered schema;
- equality of payload stage, schema ID/version, and canonical payload digest with the link;
- exact predecessor digest references;
- detection of historical payload edits, removals, insertions, reordering, or cross-chain splicing.

The A→B→C→D link topology separately enforces exact registered schema IDs, link digests, and predecessor order. Lock D's schema ID is reserved, but its reveal payload parser and hash recomputation are deliberately deferred to Task 3. Complete payload-bound A→D validation therefore fails closed with `NotImplementedError` in Task 1.

Task 3 must accept the raw A–D link/payload records, repeat duplicate-safe parsing and every A–C binding check, bind the Lock D reveal to `asset_hash` and all registered component hashes, and return a distinct successful verification credential required by scoring. A tuple that passed topology-only validation can never be promoted to that credential.

Neither result proves:

- when a node existed;
- that a node was externally registered;
- that no private alternative chain was recomputed;
- that a truth hash cryptographically hides a small candidate space.

An append-only or external anchor would be needed for chronology or pre-registration claims and is outside Task 1.

## Acceptance wording

If all Task 1 tests pass, the accurate result is:

```text
schema primitives PASS
A-C payload-bound prefix PASS
A-D link topology only PASS
Lock D payload verification NOT IMPLEMENTED until Task 3
```

It is not yet:

```text
probability semantics validated
truth blinding validated
prospective risk certified
new-library risk certified
native T4 validated
population generalization established
```
