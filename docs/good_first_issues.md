# Good First Issue 候选清单（阶段 B · 生态播种）

> 由维护者梳理，供社区新人认领。每个 issue 都应「小而明确、带自测、守住红线」。
> 首个 issue 已通过 GitHub API 实际 open（见仓库 Issues · `good first issue` 标签）。

---

## GFI-1 · 扩展 `examples/` 示例库（已 open）

**任务**：在 `examples/` 下新增 2–3 个最小可跑示例，覆盖更多器件类型：
- MZI 干涉仪（`MziInterferometer`）
- 光栅耦合器（`GratingCoupler2`）
- 量子 Transmon（`Transmon`）

**参考**：`examples/sample_layout.py`（环+金属走线范式）、`LDA_一页纸_概览.md`。
**验收**：每个示例可 `python examples/xxx.py` 生成 GDS；`lda check --gds` 跑通；`examples/README.md` 补用法。

---

## GFI-2 · `lda report --quick` 增加 CSV 导出开关

**任务**：`lda_design/cli.py` 的 `cmd_report` 目前只写 md/json。增加 `--csv <path>` 导出覆盖度表格（engines/anchors 通过率）。
**参考**：`lda/lda_harness/crosscheck_report.py` 的 `build_report` 返回值。
**验收**：`lda report --quick --csv out.csv` 生成合规 CSV；加一条轻量 smoke 验证列名。

---

## GFI-3 · `crosscheck_report` 增加覆盖度趋势图

**任务**：基于 `crosscheck_history/*.json` 画覆盖度趋势（引擎通过率 / 实证覆盖率随时间）。用 `matplotlib`（**可选依赖，未装则优雅跳过**）。
**参考**：`lda/lda_harness/crosscheck_report.py`、诚实边界标注。
**验收**：装 matplotlib 时生成 PNG；未装时打印「跳过趋势图」不报错；加 smoke 覆盖两种分支。

---

## GFI-4 · gdsfactory_bridge 增加更多组件映射

**任务**：`lda/lda_l1/gdsfactory_bridge.py` 的 `GF_TO_LDA_KIND` 当前约 7 项。补充常见组件（如 `mzi1x2`、`taper`、`bend_euler`、`straight_heater`）。
**参考**：gdsfactory 组件命名、LDA `device_library` kind 名。
**验收**：映射项增加且 `gf_component_to_spec` 对新增组件产出合法 spec；扩展现有 bridge smoke。

---

## GFI-5 · 新增一个光子 B 类解析锚示例（模板化）

**任务**：参考 `B2`（波导 FDTD↔EIM 闭式）、`B9`（Transmon 对角化↔Koch 闭式）的「真实交叉验证」范式，新增一个光子类解析锚题（如定向耦合器耦合长度解析解 vs FDTD）。
**参考**：`lda/lda_harness/benchmark_physics.py`、锚题模板。
**验收**：golden=闭式解、候选=数值法，双 ground 比对；进 `B` 题库且不破坏计数守护。

---

> 认领流程：评论 issue 认领 → 按 `CONTRIBUTING.md` 提 PR → CI core 全绿即合并。
