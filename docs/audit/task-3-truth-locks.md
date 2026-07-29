# Task 3 truth commitment, semantic audit, and Lock D

## Authority and scope

- Frozen contract: `contracts/D2T-RNA-v6.1-frozen-plan.md`
- Contract SHA-256: `87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d`
- Registered commit title: `feat(data-lock): seal truth payloads until post-certificate audit`
- Entry gate: `/mnt/cunyuliu/d2t-rna/artifacts/gates/task3-entry-gate-open-20260730T003558p0800.json`
- Test-first evidence: `/mnt/cunyuliu/d2t-rna/artifacts/runs/task3-red-20260730T004410p0800/red-test.json`

Task 3 implements a software protocol for pre-D package scanning, salted reveal commitments, raw A–D replay, and retrospective exposure classification. It has not ingested a truth dataset, authenticated an external chronology/access-control system, executed scientific scoring, or issued a scientific certificate.

## Pre-D commitment boundary

The Task 1 `TruthAssetCommitment` field set and schema version remain unchanged. A, B, and C contain a nonempty, unique, `truth_asset_id`-sorted commitment set. Raw-chain validation requires the canonical commitment-set root to remain identical across all three stages; additions, removals, replacements, duplicates, and reorderings fail.

The public identifiers in each stub are screened for the registered ON, OFF, rescue, and forbidden truth-field rules. This is a registered-rule check, not proof that an identifier or external registry definition contains no other semantic side channel.

Numeric and semantic payload commitments use separate 32-byte nonces, domain-separated canonical envelopes, and the frozen contract, evaluation, chain, asset, sequence, condition, modality, and direction-free eligibility context. The decision-binding commitment additionally binds both component hashes, H0, H1, coverage core, certificate, frozen decision output, evaluation plan, scoring specification, and `native_t4_eligible`.

The implementation rejects repeated component nonces and the all-zero nonce. It does not estimate entropy from a nonce value. Operational key generation, secrecy, and access control remain external requirements and must be audited before a real evaluation.

## Planning-package semantic audit

The scanner accepts an actual package directory, owns deterministic traversal without following symlinks, reads each regular file, and binds its byte size and raw SHA-256. It identifies supported UTF-8 text and duplicate-safe JSON formats from registered suffix and magic rules, derives headers/metadata itself, and checks normalized file names, locators, header names and values, and metadata keys and values. The registered transform applies bounded recursive percent, HTML, and JSON-style escape decoding, Unicode NFKD, case folding, selected cross-script confusable folding, default-ignorable/control detection, and boundary-aware separator collapse.

The audit fails closed for:

- absolute or traversing paths;
- symlink, hardlink, archive, device, or opaque entries;
- unsupported media types;
- files that the scanner cannot completely parse;
- duplicate indices or Unicode/casefold path collisions;
- ambiguous control characters not otherwise classified as a registered leak.

Archives, hardlinks, symlinks, oversized files, changing files, and opaque bytes are not silently declared clean. They require a later registered reader or a new evaluation package. The current scanner therefore proves only that the exact content-bound, supported package surfaces passed the registered rules.

Public findings contain entry indices, path and locator hashes, surface categories, and generic rule IDs. They do not copy source paths, headers, metadata values, numeric estimates, or snippets. The source-package and evidence hashes are integrity bindings, not cryptographic hiding claims for low-entropy inputs.

A clean sanitizer report is bound to each exact A, B, or C `public_payload_hash`. Lock D re-enumerates and rereads all three directories. Reusing a clean receipt for an omitted, added, or byte-modified file fails verification.

## Lock D raw replay

The complete validator restarts from four raw link/payload pairs. It duplicate-safely reparses A–C, repeats each payload binding, checks immutable commitment roots, rescans the exact A/B/C package directories, parses the D bundle, validates exact chain topology and the C predecessor, and rejects an invalid or incomplete claimed pre-reveal audit status.

Each D asset wrapper must match the A–C asset set exactly once. The verifier then:

1. duplicate-safely parses the embedded canonical UTF-8 reveal bytes;
2. hashes those exact bytes and compares them with `asset_hash`;
3. compares asset, sequence, condition, modality, and eligibility context;
4. recomputes salted numeric, semantic, and decision-binding hashes;
5. checks numeric and semantic hashes against the A–C stub and the binding hash inside the raw precommitted package;
6. requires all assets to bind the same frozen certificate, decision output, evaluation plan, scoring specification, H0, H1, and coverage core.

Any single failure aborts the whole validation. No partial credential or metric is returned.

Successful replay returns a distinct `LockDVerificationCredential` binding the frozen contract, all four lock hashes, commitment root, reveal payload, raw-asset manifest, validated asset IDs, replayed sanitizer reports, claimed pre-reveal audit hash, executing verifier code, historical-exposure registry, certificate, decision, plan, and scoring hashes.

The credential status is deliberately `STRUCTURAL_A_D_PAYLOAD_BOUND_VERIFIED`, with `scoring_allowed=false`. Neither a hash chain nor a caller-provided access-audit hash authenticates chronology, absence of early access, or the bytes behind certificate/decision/plan/scoring hashes. `require_lock_d_scoring_authorization` therefore fails closed with `AUTHENTICATED_CHRONOLOGY_AND_BOUND_ARTIFACT_REPLAY_UNAVAILABLE`. The serialized credential is an audit receipt, not a bearer token.

## Historical exposure

`manifests/task3_historical_exposure_registry.json` and the typed in-code registry contain exactly:

- add;
- RORC;
- SAM-III.

All three are `HISTORICALLY_SEMANTICALLY_EXPOSED_RETROSPECTIVE`, with held-out and prospective claims set to false. This classification is monotone in the current contract. A clean rerun or sanitization cannot restore prospective or held-out identity.

## Claim boundary

If Task 3 acceptance passes, the accurate statement is:

```text
exact supported pre-D package surfaces are content-bound and fail closed
salted domain-separated reveal commitments are byte-bound
structural raw A-D software replay passes its synthetic tests
historical exposure registry is retrospective-only
scientific scoring remains unauthorized
```

It is not evidence that:

- no unregistered or external channel leaked truth;
- a real reveal remained inaccessible before D;
- the truth values or confidence regions are scientifically correct;
- the H0, H1, coverage core, certificate, or scoring rule is scientifically valid;
- any dataset is prospective or held out;
- native T4, new-library risk, population generalization, or a biological result is established.
