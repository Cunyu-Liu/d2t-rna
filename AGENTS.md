# D2T-RNA execution rules

## Authority

The active scientific and engineering contract is the **D2T-RNA v7** contract
(`ACTIVE_SUCCESSOR_FOR_FUTURE_TASKS`, id `D2T-RNA-v7-THEORETICAL-RNA-METHODS`),
as activated in `manifests/m0/m0_v7_activation.json` and amended by
`docs/contracts/amendments/v7_amend_12_3_6_20260805.md` (`V7_AMEND_12_3_6_20260805`,
`APPROVED_BY_USER`).

The approved semantic decision for the corrected TheoremSpec is
**DISCRETE_CATALOG** (registered finite control library is the certified semantics;
`CONVEX_HULL` is only a derived feasibility relaxation). See
`docs/spec/t2_semantics_v2_draft.md` and `manifests/audit/semantic_diff.json`.

The previous contract, `contracts/D2T-RNA-v6.1-frozen-plan.md` (SHA-256
`87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d`), is **retained as
legacy** for historical task 1-5 interpretation and is **not** deleted.

`scientific_claim_authorized=false` remains in force: no prospective coverage,
new-library risk, native T4 validity, or RNA population-level guarantee is authorized.

Do not alter the center question, gates, estimands, probability scopes, failure
semantics, or claim boundaries without an explicit replacement contract from the user.

## Paths

- Code and Git metadata: `/home/cunyuliu/d2t-rna`
- Large data: `/mnt/cunyuliu/d2t-rna/data`
- Task 1 bootstrap environment: `/home/cunyuliu/d2t-rna/.venv`
- Failed NFS environment attempt and evidence: `/mnt/cunyuliu/d2t-rna/envs/py311` and `/mnt/cunyuliu/d2t-rna/logs/`
- Generated artifacts and logs: `/mnt/cunyuliu/d2t-rna/artifacts`
- Checkpoints and weights: `/mnt/cunyuliu/d2t-rna/checkpoints`

Never commit data, environments, weights, checkpoints, caches, secrets, or generated run artifacts.

The Python environment was moved into the ignored project-local `.venv` only after the `/mnt` Conda transaction stopped making progress in NFS RPC wait. This is a software environment, not a dataset, weight, checkpoint, or scientific artifact. Its exact failure and recovery evidence is in `docs/audit/environment-bootstrap-2026-07-29.md`.

## Forward-only scientific execution

- Preserve all failures and negative results.
- Never weaken a gate, change a test split, relabel a probability scope, or tune on a held-out stress result.
- Smoke tests, proxies, development metrics, and train results are not final scientific evidence.
- A failed assumption follows the registered falsification or alternative path; it does not justify changing the evaluation rule.
- A stage begins only after the previous stage's acceptance record is hash-verified and passing.

## GPU fail-closed rule

- Training and GPU validation must explicitly require CUDA.
- Record run ID, resolved config, code commit, data/split/contract hashes, GPU index and UUID, command, log paths, metrics path, system-metrics path, checkpoint path, and failure-bundle path before launch.
- Immediately stop and preserve evidence on CUDA loss, device mismatch, CPU fallback, NaN/Inf, resource exhaustion risk, no progress, or five unchanged validation events when no stricter threshold exists.
- Never signal an unrelated process. Free memory does not transfer ownership of an existing job.
- Monitor at the contract's low frequency; use waiting time for read-only audits, tests, and documentation.

## Git discipline

- Use TDD and the registered commit title for each task.
- Inspect status and diff before staging.
- Stage explicit task paths; never use a broad stage in a mixed worktree.
- Run the task acceptance suite and `git diff --check` before commit.
- Push each accepted task commit to GitHub as requested by the user.
- Never force-push or rewrite published history.
