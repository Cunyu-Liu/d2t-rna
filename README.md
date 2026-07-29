# D2T-RNA

D2T-RNA is being implemented against the frozen v6.1 contract for exact synthetic risk–coverage proofs, finite-observed-dataset subsampling QA, carefully delimited within-realized-library model-conditional risk, and fail-closed RORC stress evaluation.

Current status: Tasks 1–2 provide immutable schema primitives, a payload-bound Lock A–C prefix, topology-only Lock A–D validation, and fail-closed structural guards for probability scopes, split relations, nuisance handling, and exact candidate-bound arithmetic. Task 2 issues no scientific certificate: within-library proof validity remains pending replay, the synthetic exact engine is deferred to Task 4, new-library certification is a hard no-go, and observed-dataset closure/QA has not yet been executed. Truth blinding, real-data QA, exact proofs, RORC stress results, and the payload-bound Lock D reveal are not yet implemented.

The sole active scientific and engineering authority is:

- `contracts/D2T-RNA-v6.1-frozen-plan.md`
- SHA-256 `87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d`

## Scientific boundary

Engineering checks, smoke tests, development results, and exact synthetic proofs do not establish prospective RNA coverage, new-library risk, native T4 validity, quantitative intervention consequences, or RNA population-level generalization.

If every later release gate passes, the only authorized final public wording is:

> exact synthetic risk–coverage proof；真实 RNA 数据上的经验有限数据集下采样 QA 和 coverage prediction；仅在注册 observation model、split relation 与条件化对象均可辩护时输出 model-conditional within-library risk certificate。不存在 prospective coverage、new-library risk、native T4 或 RNA population-level 保证。

## Layout

```text
src/d2t_rna/
  contracts/
  probability/
  exact/
  evaluation/
  data/
tests/
manifests/
docs/
```

Code and Git history live in `/home/cunyuliu/d2t-rna`. Datasets, checkpoints, weights, logs, and generated scientific artifacts live under `/mnt/cunyuliu/d2t-rna` and are never committed. The ignored bootstrap runtime is `/home/cunyuliu/d2t-rna/.venv`; its `/mnt` predecessor failed on a preserved NFS transaction and was not deleted.
