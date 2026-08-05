# D2T-RNA v7 — Claim Register (PAPER-1)

> 登记主文将要作出的每一项科学 claim、其证据位点、允许强度与授权状态。
> 机器可读版本见 `manifests/paper/paper_claim_register.json`。

## 允许的 claim（authorized）

| # | Claim | Evidence locus | Allowed strength |
|---|---|---|---|
| C1 | 对完整注册差集 D 给出 exact collision-or-separation certificate | t2_2 manifest + rational checker | within registered finite model only |
| C2 | 将 robust action-level separation 转化为 finite-sample decision/budget bounds | t2_3 manifest + exact oracle enumeration | finite registered pair catalog, fixed non-adaptive horizon |
| C3 | 给出 costed integer design 与 design-class no-go certificate | t2_4 manifest + LP dual + integrality gap | design-class level, not universal |
| C4 | 执行 11 微案例 + 8 baseline 的 model-conditional synthetic evaluation | t9_matrix manifest | executed model-conditional; no superiority claim |
| C5 | 提供 fail-closed retrospective evidence audit（add/sam-iii/rorc） | task6r_r2 + s12 manifests | complete fail-closed audit; no qualitative instance |
| C6 | 假设破坏时返回 NOT_ESTABLISHED / abstain（registered coupling） | t10 manifest | theory boundary, not real-data validation |

## 明确不作出的 claim（prohibited）

```text
P1  prospective / blinded / held-out / independent validation
P2  universal RNA identifiability / general RNA structure inference
P3  population-level RNA generalization / cross-lab generalization
P4  new-library guarantee / independent-library validation
P5  actual future wet-lab cost saving / increased success rate
P6  add / SAM-III / RORC 产生新生物学发现或对方法的独立验证
P7  pretrain / foundation model / representation learning / fine-tuning / neural architecture
P8  SHAPE/DMS continuous channel 上的 categorical T2 定量验证
P9  third-state discovery / unmodeled third state 的生物学发现
P10  reads/PCR/UMI/random seed 当作 biological replicates
```

## PAPER-CLAIM-BOUNDARY-GATE

```text
no_prohibited_claim: true   (P1–P10 均不出现/不授权)
scientific_claim_authorized: false   (全程)
retrospective_failure_omitted: false  (R2 三数据集 fail-closed 原样保留)
```
Gate 判定：**PASS**。
