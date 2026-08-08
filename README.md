# D2T-RNA

D2T-RNA is being implemented against the frozen v6.1 contract for exact synthetic risk–coverage proofs, finite-observed-dataset subsampling QA, carefully delimited within-realized-library model-conditional risk, and fail-closed RORC stress evaluation.

Current status: Tasks 1–4 are accepted on public `main`. This tree contains the Task 5 finite-scenario proof, independent bounded-integer checker, planner-failure, structural baseline, and RORC evaluation implementation. Task 5 engineering acceptance requires its candidate manifest, public focused commit, and external post-commit closure; a passing synthetic fixture or baseline comparison is not a scientific result. Task 3 does not prove real access chronology or scientific truth validity; its credential must be replayed from raw inputs and is not a bearer token. Task 4 reports and replay credentials are distinct, synthetic-only, non-bearer artifacts and do not open the Task 2 certificate path. No scientific certificate has been issued: within-library proof validity remains pending replay, new-library certification is a hard no-go, and observed-data closure/QA has not been executed. add, SAM-III, and RORC remain historically semantically exposed and retrospective-only.

The sole active scientific and engineering authority is the **D2T-RNA v7** contract
(`ACTIVE_SUCCESSOR_FOR_FUTURE_TASKS`, id `D2T-RNA-v7-THEORETICAL-RNA-METHODS`),
activated in `manifests/m0/m0_v7_activation.json` and amended by
`docs/contracts/amendments/v7_amend_12_3_6_20260805.md`. The corrected TheoremSpec
semantics are **DISCRETE_CATALOG** (certified), with `CONVEX_HULL` as a derived
relaxation only. The former v6.1 contract
(`contracts/D2T-RNA-v6.1-frozen-plan.md`, SHA-256
`87ccadd245a02133d1da0dfc41537c90b56e68a22592ad026b53449259dd455d`) is **retained
as legacy** (historical tasks 1-5) and is not deleted. `scientific_claim_authorized=false`
remains in force.

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
