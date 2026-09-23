# LDA 示例库（examples）

最小可跑示例，帮助新人 5 分钟跑通「设计 → 版图 → 主权几何 DRC / 寄生估算 → 报告」闭环。

## 1. 生成示例版图并跑主权几何 DRC

```bash
# 生成示例 GDS（环型器件 + 金属走线）
python examples/sample_layout.py sample_layout.gds

# 主权几何 DRC 快查（gds_drc，子集诚实标注非 foundry 全量）
lda check --gds sample_layout.gds
```

## 2. 端到端单命令：一句话目标 → GDS + 签核（最省事的一条路）

```bash
# goal JSON 里 design.target 的器件 ⇒ 参数由设计引擎（DesignEngine）闭环解出；
# params 的器件 ⇒ 参数已知，直接给定。一条命令出 GDS + DRC/LVS 签核报告。
lda build lda/examples/cli_build_goal.json --out reports
# 产物：reports/goal_ring_fsr.gds / .signoff.json / .signoff.md / .design_packages.json
```

## 3. 跑一个设计（CLI 薄壳）

```bash
# 签名： lda design <kind> --target <float> [--top-k N]
# 跑一个器件设计闭环，返回被真实求解器验证过的最优候选
lda design RingResonator --target 9.0 --top-k 3

# 生成对照报告（--quick 跑子集，更快）
lda report --quick
```

## 4. gdsfactory 兼容（可选，B 级依赖）

> gdsfactory 未安装时 `lda gf` 会打印指引并优雅退出（不阻断 LDA 自有路径）。

```bash
# 把 gdsfactory 组件转成 LDA 链路 spec
lda gf your_component.py --out your_component.lda_spec.json
```

## 5. 主权版图实证库（走法一，零 gdsfactory）

`examples/sovereign_evidence/` 是用纯 LDA 主权链（LinkModel → placement →
routes → chip_layout_export.export_chip_gds）跑出的**真实 GDSII 证据集**，全部经
主权几何 DRC + LVS 双闸签核，覆盖 7 类典型光子拓扑（分束器 / 环形 / MZI / Bragg 等）
外加 1 个最小证明件，构成「降标走法」的流程跑通证据。

```bash
# 用项目 venv（Python 3.13，须自带 numpy）：<venv>/Scripts/python.exe（Linux/macOS 为 <venv>/bin/python）
python examples/sovereign_evidence/build_sovereign_evidence.py   # 7 例证据集
python examples/sovereign_evidence/build_2x2_ring_proof.py       # 最小证明件
```

产物（GDSII + SVG 渲染 + 汇总索引）直接落在 `examples/sovereign_evidence/`，
自包含可复跑。详细拓扑表、LVS 硬契约、加新器件的端口名三处同步规则、以及
**诚实边界（仅几何合法、无光学表征、未注册 GP-\*、不进创新超市）**见该目录 `README.md`。

## 诚实边界

- 几何 DRC / 几何寄生估算为**主权子集**，标注"非 foundry 工艺级全量 deck"。
- 真实 PDK 接入、晶圆实测回流、封装测试属发动期（物理/资源边界）。

详见仓库根 `LDA_一页纸_概览.md` 与 `README.md` 的「当前账本」段。
