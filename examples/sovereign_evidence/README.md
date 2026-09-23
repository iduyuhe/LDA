# 主权版图实证库（走法一 · 零 gdsfactory 依赖）

本目录是 LDA 主权全链路（**LinkModel → placement → routes → chip_layout_export.export_chip_gds**）
的真实版图实证库。所有版图**不依赖 gdsfactory（B 级）**，纯用 LDA 自有 L0/L1/L2，
全部经**主权几何 DRC + LVS 双闸签核**产出。

## 这是什么

这是「降标走法」下攒出的**流程跑通证据**：用同一套主权链，跨多类典型光子拓扑，
证明平台可用、链路可重复。每个版图都是**真实 GDSII**（非描述、非占位）。

| 文件 | 拓扑 | 组件 | 性质 |
|---|---|---|---|
| `lda_c1_dc_splitter.*` | 2×2 方向耦合器分束器（in2 留空） | 4 | 基元 |
| `lda_c2_ring_add_drop.*` | 环形 add-drop（drop 已接线） | 4 | 基元 |
| `lda_c3_dc_ring.*` | 2×2 方向耦合器 + 环形谐振器 | 6 | 组合 |
| `lda_c4_mmi_splitter.*` | MMI 1×2 多模干涉分束器 | 4 | 基元 |
| `lda_c5_ybranch_splitter.*` | 对称 Y 分支 1×2 分束器 | 4 | 基元 |
| `lda_c6_mzi_interferometer.*` | Mach-Zehnder 干涉仪（2×DC + 2 臂） | 7 | 组合 |
| `lda_c7_bragg_mirror.*` | Bragg 反射镜透射线 | 3 | 基元 |
| `lda_2x2_ring.*` | 首块最小证明件（拓扑同 C3） | 6 | 组合 |
| `lda_4x4_mzi_mesh.*` | 4×4 MZI 网格 P&R（4×4 光子计算核可行性：6 MZI + 跨层桥接化解交叉） | 14 | 计算核 |

汇总见 `sovereign_evidence_index.json`（`all_drc_pass` / `all_lvs_accept` 双布尔）。

## 怎么复跑

```bash
# 用项目 venv（Python 3.13，须自带 numpy）：<venv>/Scripts/python.exe（Linux/macOS 为 <venv>/bin/python）
python examples/sovereign_evidence/build_sovereign_evidence.py   # 7 例证据集
python examples/sovereign_evidence/build_2x2_ring_proof.py       # 最小证明件
```

产物直接落在**本目录**（自包含，无外部路径依赖）。

## LVS 硬契约（踩坑坐实）

- `routes` 的 dict key **必须 ==** `link.connect()` 的 net_id；
- 每条 route 首末端点必须落在对应 net 两端口锚点 **±1.0µm** 内（用 `port_abs` 取，别手写坐标）；
- 不同 net 布线**不得相交**（否则 `short_cross`）；
- 同一端口**不得**被多于一个 net 占用（否则 `short_port`）。

## 加新器件种类：端口名契约三处必须同步

一个新器件要过 LVS，端口名契约**三处必须同步**，否则必现假红：
1. `lda_chain/link_model._DEFAULT_PORTS` —— 注册 Port 名；
2. `lda_layout/placement.port_anchor` —— 局部端口坐标；
3. `connect()` / `route_specs` 里用的端口名。

（MMI / BraggMirror / SymmetricYBranch / DirectionalCoupler 均已补齐，见上述三处。）

## ⚠️ 诚实边界（重要）

- 这些版图是**几何合法性**证明（主权子集 DRC + LVS 拓扑一致），**非 foundry 工艺级全量 deck**。
- **尚无光学性能表征**（插损 IL / 串扰 XT / 自由光谱范围 FSR 等均为空）。
- 因此**尚未注册为可售 GP-\* 基元**，也**不能进入创新超市当货架商品**（创新超市收的是
  应用系统级预设计 IM-\*，由已锚定 GP-\* 组合而成）。
- 若要让它们"可售"，正路是：**表征锚定 → 注册 GP-\* → 回灌 IM-\* 货架**（几周表征工程，非摆放问题）。
- 真实 PDK 接入、晶圆实测回流、封装测试属发动期（物理/资源边界）。
