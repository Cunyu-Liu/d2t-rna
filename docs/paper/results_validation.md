# D2T-RNA v7 — Results-as-Validation 表 (PAPER-1)

> 每一行必须同时具备 question / evidence / comparison / interpretation / boundary。
> 任何只有 runtime、hash、schema 或 test count 的段落不得作为主 Results 单元。

| Results unit | Contribution tested | Evidence | Allowed interpretation | Interpretation not allowed |
|---|---|---|---|---|
| T2 geometry | exact collision-or-separation over complete registered D | T2b manifest + rational checker | exact certificate within registered finite model | universal RNA identifiability |
| finite-sample consequence | quantitative fixed-horizon risk/budget consequence | T2c manifest + exact TV/Hellinger enumeration | finite registered pair-catalog bound | continuous composite guarantee |
| costed design | executable integer design and no-go | T2d manifest + LP dual checker | design-class cost/no-go certificate | universal wet-lab minimum cost |
| synthetic evaluation | theorem/code/scenario behavior | §9 manifest, 11 cases, 8 baselines | executed model-conditional evaluation | method superiority on real RNA |
| retrospective boundary | data qualification and fail-closed semantics | R2 + S12 | complete fail-closed audit | empirical validation or independent test |

## 逐行明细

### 1. T2 geometry
- question: 对完整注册差集 D，能否给出可检查的碰撞或分离判定？
- evidence: `manifests/t2/t2_2_acceptance.json`（PASS），rational primal/dual + independent checker。
- comparison: 相对"仅有 cycle generator 子集"的朴素做法，使用完整 D。
- interpretation: 在 registered finite model 内是 exact certificate。
- boundary: 不扩展到 universal RNA identifiability。

### 2. finite-sample consequence
- question: separation 如何转化为 fixed-horizon decision/risk/budget bound？
- evidence: `manifests/t2/t2_3_acceptance.json`（PASS），exact TV/Hellinger/decision 枚举交叉核验。
- comparison: 相对 generic Hellinger/Chernoff scaling，绑定 registered pair catalog 与 abstention。
- interpretation: 对 registered pair-catalog 是有限样本界。
- boundary: 无 composite-continuous covering theorem，无 real-data calibration guarantee。

### 3. costed design
- question: 在 action cost 不同时能否给出最小成本设计或 no-go？
- evidence: `manifests/t2/t2_4_acceptance.json`（PASS），LP dual bound + integrality gap。
- comparison: 相对 Test-Cover / generic information-source selection，给出 integer design + no-go。
- interpretation: design-class cost/no-go certificate。
- boundary: 不是 universal wet-lab minimum cost。

### 4. synthetic evaluation
- question: theorem/code/scenario 是否正确执行？
- evidence: `manifests/t9/t9_matrix_acceptance.json`（PASS），11 微案例 + 8 baseline 全部 EXECUTED。
- comparison: 8 种 baseline（含 oracle、EIG、Chernoff、LM2R-style、T2 design）。
- interpretation: executed model-conditional evaluation。
- boundary: 不推断 method superiority on real RNA。

### 5. retrospective boundary
- question: 三套公开 RNA 数据在注册框架下的证据资格如何？
- evidence: `manifests/task6r/task6r_r2_acceptance.json` + `manifests/s12/s12_3_submission_gate_acceptance.json`。
- comparison: add / sam-iii / rorc 各自独立 fail-closed。
- interpretation: 完整 fail-closed audit（无 qualified quantitative instance）。
- boundary: 不构成 empirical validation 或 independent test / third-state discovery。
