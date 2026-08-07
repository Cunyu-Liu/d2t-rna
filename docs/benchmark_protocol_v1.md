# D2T-RNA v7 Benchmark Protocol (v1)

审计日期：2026-08-07（Asia/Shanghai）
适用范围：`src/d2t_rna/evaluation/matrix.py` 的 §9 evaluation matrix 与 T9 基线比较。
本协议修正 v7 审计第 4 条阻断（baseline/SOTA 比较不成立）并固定第 6 条阻断（异质
multi-action Bhattacharyya 乘积错误）的评估口径。本协议不授权任何 formal scientific claim
（`scientific_claim_authorized=false`）。

## 1. 目的与范围

原 §9.3 的 88 个运行（11 microcases × 8 方法标签）不能被当作 superiority/scalability 证据，
原因有三：(a) 三个 baseline（greedy Test-Cover、EIG、LM2R-style）使用同一分数与 allocator，
是同构标签；(b) "Chernoff" 并非标准 Chernoff information；(c) exhaustive oracle 把每个 action
的 allocation 硬截断在 6，即使预算更大。本协议重定义评估口径，使每个标签可独立审计，并明示
旧 88-run 仅作 historical 保留。

## 2. 任务分表（不同任务必须分表）

一个 "task" 由五元组唯一确定：`(action library, action costs, budget, decision rule, stopping
rule)`。只有五元组完全相同的运行才可放入同一张比较表。否则须标记该对比较为
`NOT_COMPARABLE_BY_REGISTERED_ACTION_SPACE`（见 §14.3 终止条件）。

- 证书正确性任务（与 exact oracle 的一致性）与成本化试验设计任务（fixed-budget risk /
  fixed-risk minimum cost）必须分表。
- 任何 action/cost/budget/rule 不同构的方法不得出现在同一张表。

## 3. 单一实验 spec（same-stopping 约束）

所有基线在同一 `ExperimentSpec` 下执行：相同 `costs`、`budget`、`p0`、`p1`、
`abstain_ratio`（固定非自适应 horizon，无 stopping-time 差异）。这样比较的是同一任务下的
分配质量，而非不同 stopping/objective 的伪优劣。

## 4. Cap-free complete oracle

exhaustive oracle 必须枚举所有 `cost <= budget` 的整数分配，即对每个 action `u`，
`n_u in [0, floor(budget / cost_u)]` 的完整笛卡尔积，**无**任意每-action 硬截断（旧代码的
`cap = 6` 已移除）。

验收标准：oracle 的 minimax error 不劣于任何可行分配（全局最小化）。参考测试
`test_oracle_is_global_minimizer_across_feasible_allocations` 用独立暴力枚举核对该属性。

## 5. product Bhattacharyya 乘积

对异质 multi-action 分配 `n = (n_1, ..., n_U)`，正确乘积 bound 为

```
prod_u BC_u ** n_u,   BC_u = sum_y sqrt(q0_u[y] * q1_u[y])
```

旧实现只取第一个 action 并计算 `BC_0 ** sum(n)`，仅在所有 action 的 BC 恰好相同时才巧合
正确。受影响的 `product_bhattacharyya`、theory/oracle cross-validation 与相关表格必须撤回并
重算。参考测试 `test_product_bhattacharyya_is_product_over_actions` 固定两个 BC 不同的 action
微例（`BC_a=1/2`，`BC_b=1`），断言 `prod_u BC_u^{n_u}` 而非 `BC_0^{sum n}`。

## 6. 每个标签的独立实现/引用

| 标签 | 分数/算法 | 独立来源引用 | 与历史同构性 |
|---|---|---|---|
| `exhaustive_oracle` | 枚举全部可行分配，minimax error 全局最小 | 独立 brute-force oracle（correctness reference） | 无 |
| `full_matrix` | 全矩阵 round-robin 均分 | uniform/full-matrix 基线 | 无 |
| `random` | 固定 seed 的预算内随机分配 | random baseline | 无 |
| `greedy_test_cover` | 每-action TV 分离度 `sum_y|q0-q1|/2` | Moret & Shapiro, *SIAM J. Comput.* 1991（Test Cover） | 重建（旧用 EIG 分数） |
| `eig` | 每-action Hellinger information（Bhattacharyya 区间中点） | Lindley 1956; Chaloner & Verdinelli 1995（Bayesian EIG） | 保留 |
| `chernoff` | 真 Chernoff information `-log min_{0<=s<=1} sum_y q0^s q1^{1-s}` | Chernoff 1952; Kailath 1967 | 重建（旧为 `1-sum min`，非真 Chernoff） |
| `lm2r_heuristic` | 项目自定义：TV × Hellinger information 的乘积 | 项目定义的 mutate-and-map 风格启发式（项目自定义，非文献标准 allocator） | 重建（旧与 greedy/EIG 同分） |
| `t2_integer_lp` | 成本化整数设计与 LP dual lower bound | Pukelsheim 2006（T-optimal）；项目 LP 积分 gap | 保留 |

每个标签必须：有独立实现或显式引用；不同标签不得共享同一分数向量。参考测试
`test_baseline_scores_are_distinct` 在 TV 与 Hellinger info 对两个 action 排序相反、且
`test_true_chernoff_matches_reference` 固定真 Chernoff value 的微例上断言分配不同。

## 7. 旧 88-run 的处理

旧 88-run（11 microcases × 8 标签，含同构 greedy/EIG/LM2R 与硬截断 oracle、伪 Chernoff）
仅作 historical 保留，不得作为 superiority/scalability 证据。其内容前向追加，不删除、不重命名。

## 8. 相关参考测试

- `tests/evaluation/test_matrix.py::test_product_bhattacharyya_is_product_over_actions`
- `tests/evaluation/test_matrix.py::test_single_action_bc_is_unchanged`
- `tests/evaluation/test_matrix.py::test_oracle_is_cap_free_single_action`
- `tests/evaluation/test_matrix.py::test_oracle_is_global_minimizer_across_feasible_allocations`
- `tests/evaluation/test_matrix.py::test_true_chernoff_matches_reference`
- `tests/evaluation/test_matrix.py::test_per_action_tv_in_unit_interval`
- `tests/evaluation/test_matrix.py::test_baseline_scores_are_distinct`

## 9. 状态

本协议修正为 v7 审计第 4、6 条阻断的评估口径。所有数字结果仍为 model-conditional synthetic
evaluation；不授权任何正式科学结论。