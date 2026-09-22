# P1-A 物理综合闭合报告 · MZI 网格版图级保真度 = 机器精度（1.0）

> 前序：P0 已闭合"酉分解 → 摆位 → 连波导 → GDS → DRC/LVS"死缺口（分解级保真度 1.0）。
> 本报告推进 **P1-A 物理综合**：把分解 op **逐 op 物理绑定**到版图 MZI 传输 + 输出相移，
> 使**版图级（物理级联网表前向下行传输）保真度**也达到机器精度 1.0——即版图不再只是
> "可出版"，而是"**真算该酉**"。

## 1. 物理综合绑定（核心做法）

Clements 矩形分解的矩阵约定：`U_target = (Π_k G_k)† · D`，其中 `G_k = _mzi(θ_k, φ_k)`
是第 k 个 MZI 的 2×2 传输，D 是分解残差对角相位矩阵。

经 DFT4 + 30 个随机酉（N=4/5/7/8/16）**实测**锁定物理网格的正确实现：

| 要素 | 实现 |
|---|---|
| 每个 MZI 的传输 | **伴随** `G_k† = _mzi(θ_k, φ_k).conj().T`（标准 MZI+相移器可实现；耦合器几何不变，仅内部相移设置不同） |
| MZI 摆放序 | **反转分解序**（op[-1] 在输入侧最低 x），光自左向右先遇 op[-1] |
| 输出相移器 | 末端 **N 个 PhaseShifter** 实现对角相位 `D[k,k] = arg(D[k,k])` |
| 版级前向传输 | `U_layout = (Π_k G_k†)〔反转序〕· D` |

代数验证：`U_target = (Π G_k)† · D = (G_1†·…·G_M†)·D`，而反转序 adjoint 网格
`(Π G_k†)〔反转序〕 = G_1†·…·G_M†`，二者一致 ⇒ `U_layout == U_target`。

> ⚠️ 顺序/共轭是 Clements 矩形网格的物理关键：直接用 `G_k`（非伴随）或正序摆放，
> 保真度掉到 0.56–0.65（实测）——这是 P1-A 唯一的"坑"，已用穷举实测锁定正确约定。

## 2. 主权签核（全死标量，LLM 不进判决路径）

- `placement.py`：新增 `PhaseShifter` 端口锚点（in/out @ (0,0)/(L,0)）与 bbox。
- `drc.py`：新增 `PhaseShifter` 器件级 DRC 分支（min_width）。
- `mesh_pnr.py`：MZI 反转序摆放 + 输出相移器串入每条 rail 链（gc_in → MZI 序列
  → ps_out → gc_out）；**关键修正**：MZI 的 `in` 是入网终点、`out` 是出网起点，
  二者绝不直接相连（否则同一端口被两网共享 → LVS `short_port`）。

## 3. 硬证据（P1-A 接受闸 `examples/demo_mesh_pnr_4x4.py`，EXIT=0）

| 指标 | 4×4 DFT | 5×5 DFT | 7×7 DFT |
|---|---|---|---|
| MZI 单元数 | 6 (=N(N−1)/2) | 10 | 21 |
| 输出相移器 | 4 | 5 | 7 |
| 分解保真度 | **1.000000** | 1.000000 | 1.000000 |
| **版级保真度** | **1.000000** | **1.000000** | **1.000000** |
| DRC | PASS | PASS | PASS |
| LVS | **ACCEPT** (0 违规) | ACCEPT | ACCEPT |
| GDS 元件 | 14 (4 rail+6 MZI PS+4 PS) | — | — |

随机酉抽查（N=5/7 各 5 例）：**最小版级保真度 = 1.0000000000**，全部 LVS ACCEPT。

`examples/mesh_4x4_dft.gds` 已重新生成（含输出相移器金属 patch，14 条 PATH/BOUNDARY）。

## 4. 诚实边界（必读）

- 版级保真度 1.0 = **物理级联网表前向下行传输** == U_target 的数学证据（拓扑实现正确）。
- PDK 仍为**演示近似 SOI 180nm**（非真 foundry NDA-PDK）；MZI 实现 `G_k†` 是标准
  MZI+相移器可实现的抽象 2×2（具体相移器设置→电压映射属 P1-B 工艺映射）。
- LVS 为**单层波导**网表签核（端口几何恢复 + 线段交叉短判），多层金属/通孔完整
  LVS 属发动期 PDK 对接后扩展。
- 仿真用抽象 MZI 2×2 传输；未含波导损耗/非理想耦合/串扰——属 P1-B 工艺级精度。
- **未含**：规模爬升 16×16 / 128×128 光子张量核（P1-B）、Clements vs Reck 免交叉
  收益量化（P1-C）。

## 5. 交付物

- `lda/lda_layout/mesh_pnr.py` — P1-A 物理综合（反转序 MZI + 输出相移 + 版级保真度函数）
- `lda/lda_layout/placement.py` — PhaseShifter 端口锚点/bbox
- `lda/lda_l2/drc.py` — PhaseShifter DRC 分支
- `examples/demo_mesh_pnr_4x4.py` — P1-A 接受闸（版级保真度纳入硬门禁）
- `examples/mesh_4x4_dft.gds` — 真实主权 GDSII（含输出相移器）
- `examples/probe_mesh_random.py` — 一般公式回归测试（随机酉验证）
- `examples/verify_clements.py` — 分解级保真度回归测试

## 6. 下一步（待裁定）

**P1-B 规模爬升**（16×16 / 128×128 光子张量核 + 工艺映射 T→V）+ **P1-C 跨分解对照**
（Clements vs Reck 免交叉收益量化）。P1-A 已证明"任意酉可物理综合为版图且真算该酉"。
