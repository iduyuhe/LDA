# P1-B 续 · 2D 压实网格（Clements 平方分解 + 总线-抽头）闭合报告

**日期**：2026-09-22 ｜ **模块**：`lda/lda_layout/mesh_pnr.py` ｜ **路线**：B+C 自研（主权光电接口 + light-EIC 光子核）
**红线**：A 级永不外借 · C 级自主零依赖 · 三不做（电域求解器/Foundry TCAD 真值/封测产线）· 解锁前置=独立锚 · **LLM 不进判决路径** · 零外部求解器依赖。

---

## 一、结论

P1-B 续的「2D 压实网格」已闭合。在 P1-B（规模爬升 + 工艺映射，蛇形折叠）已证的基础上，把
**Clements 平方（矩形）分解**（每列**非重叠**相邻配对）接入 `mesh_pnr`，用**冲突图着色列分配**
把 N(N−1)/2 个 MZI 压实为 **O(N) 列**的 2D 总线-抽头网格：

- 128×128 网格：footprint 从蛇形 **146.2 mm²**（8126 列、展开 ~28 cm）降到 grid2d
  **2.34 mm²**（128 列、~4.6 mm 宽）——**面积 ↓≈63×**，进入真实可流片量级。
- 分解级保真度（数学定理）= 1.000000；版级（按列序物理前向下行传输）保真度 = 1.000000；
  二者相等 ⇒ 压实布局物理上「真算该酉」。
- DRC **PASS** · LVS **ACCEPT**（0 违例）· 几何最小间距 3.2 µm（≥ DRC）· V_max = 7.50 V
  （red-line 预算 25 V·cm 见下；Vπ·L = 7.5 V·mm 代表生产值）。

---

## 二、数学前提（此前诚实边界列为「布局工程后续步」，今已证）

### 2.1 旧分解为何强制 O(N²) 蛇形
P1-B 的 `clements_decompose`（三角式零化）每列 c 耦合重叠配对 (j,j+1) 且 j 遍历
[N−2..c] ⇒ **同一波导对 (j,j+1) 跨列重复** ⇒ 任一轨链上的 MZI 必在不同 x ⇒
唯一 x + 无共线重叠 + 无回折 ⇒ 宽 = N(N−1)/2·pitch（O(N²)）。这是数学不可兼得，非工程疏忽。

### 2.2 平方分解（clementsw/interferometer 权威实现，已复刻验证）
`clements_rect_decompose`（三阶段：偶数迭代右乘 invT、奇数左乘 T、reverse left_T 重零化）
输出相邻配对 (j, j+1) 且**每列配对互不共享波导** ⇒ 同列可共享 x（抽头）。

### 2.3 冲突图着色列分配 `_rect_column_assignment`（O(n)，n = N(N−1)/2）
- 节点 = MZI，边 = 共享波导（|Δj| ≤ 1）。
- `color_k = max(末色[mode jₖ], 末色[mode jₖ+1]) + 1`，`末色[m]` = 用过波导 m 的 MZI 最高列号。
- **两个硬保证**：
  1. 同列配对互不共享波导 ⇒ 同列共享 x 不撞端口（LVS 不报短/短路）；
  2. 列序对「不交换对」（共享波导的 MZI）保序 ⇒ 光自左向右列序施加 = 分解序 ⇒
     版级传输 `D @ Π_列(Π_列内 T)` = `D @ Π_网格序 T` = U_target（机器精度）。
- 列数 = max color + 1 ≈ **N**（O(N)，非 O(N²)）。

> 注：版级物理块用平方约定 `ref_T`（全角 θ，split = sin²θ ⇒ κL = θ），
> 旧 `clements_decompose` 用半角 `_mzi`。同 CMT 锚统一：
> `Lc = θ/κ = coupler_length_from_theta(2θ)`，几何与工艺映射与蛇形一致。

---

## 三、三级规模硬证据（serpentine vs grid2d 同 U=DFT(N)）

| N | 模式 | n_mzi | 列数 | 分解保真 | 版级保真 | DRC | LVS | geo_min_space | footprint |
|---|------|-------|------|----------|----------|-----|-----|---------------|-----------|
| 4 | serpentine | 6 | 6 | 1.000000 | 1.000000 | PASS | ACCEPT(0) | 3.20 µm | 0.003 mm² |
| 4 | grid2d | 6 | **4** | 1.000000 | 1.000000 | PASS | ACCEPT(0) | 3.20 µm | 0.002 mm² |
| 16 | serpentine | 120 | 120 | 1.000000 | 1.000000 | PASS | ACCEPT(0) | 3.20 µm | 0.255 mm² |
| 16 | grid2d | 120 | **16** | 1.000000 | 1.000000 | PASS | ACCEPT(0) | 3.20 µm | **0.036 mm²** |
| 128 | serpentine | 8126 | 8126 | 1.000000 | 1.000000 | PASS | ACCEPT(0) | 3.20 µm | 146.235 mm² |
| 128 | grid2d | 8128 | **128** | 1.000000 | 1.000000 | PASS | ACCEPT(0) | 3.20 µm | **2.336 mm²** |

列内共享波导冲突数自检 = **0**（N=16）；分解级保真度 − 版级保真度 = **0.00e+00**（须≈0）。

---

## 四、压实面积对比（核心交付）

| N | 蛇形展开长边 | grid2d 长边 | 面积比（蛇形/grid2d） |
|---|-------------|------------|----------------------|
| 16 | ~3.96 mm | ~0.53 mm | ~7× |
| 128 | ~285 mm（不可流片） | ~4.6 mm | **~63×** |

grid2d 把「光子张量核」从「展开蛇形（概念验证）」压实到「mm² 级真实芯片」，
且**分解 / 版级保真度 / DRC / LVS 网表一致性 / 驱动映射全部与蛇形同判据、同结论**。

---

## 五、工艺映射一致性（P1-B 已闭合，grid2d 沿用）

- **θ → 耦合器长度 Lc**：CMT，`Lc = (θ/2)·λ/(π·|Δn|)`；平方全角 θ 经 `coupler_length_from_theta(2θ)` 桥接，
  与蛇形半角约定同锚（N_E=2.45 / N_O=2.40，λ=1.55 µm）。
- **φ / D[k,k] → 驱动电压**：Vπ·L 定律，`V = φ·(Vπ·L)/(π·L_arm)`，相位取主值 (−π,π]。
  `Vπ·L = 7.5 V·mm`（代表生产值，red-line 预算 250 V·mm = 25 V·cm）。
- **V_max = 7.50 V**（DFT 三规模，≤ red-line）；绝对电压为闭环标定常量（设 φ→测输出→调 V），非一次性计算值。
- **PDK**：演示近似 SOI（非真 foundry NDA-PDK）。LVS 网表由布线几何独立恢复（端点→端口锚点容差 1 µm），
  判决全死标量，LLM 不进路径。

---

## 六、诚实边界（防纸糊楼）

1. **2D 压实是布局工程，不改变数学判决**：酉分解（机器精度）、版级保真度、DRC、LVS 网表一致性、
   工艺映射均与「如何摆位」无关；grid2d 仅把摆位从 O(N²) 蛇形改为 O(N) 总线-抽头，
   且已证同列不撞端口、列序保序 ⇒ 物理传输不变。
2. **未做**：真实 foundry PDK 圆片流片、相干实测标定闭环（L3 控制校准，对经典光子外置可绕，不破红线）、
   热串扰/工艺角仿真。本报告网格为**主权几何+P&R 正确性证明**，非 tape-out sign-off。
3. **总线-抽头折中**：同列共享 x 抽头 → 总线波导在列间为连续长直线（无蛇形回折），
   波导传播损耗随列数线性增长（设计预算 2 dB/cm，已计入 mesh_cascade_loss 估算，非本布局判决项）。
4. **列数 ≈ N 而非 N−1**：冲突图着色下界使 128×128 用 128 列（非 127）；仍 O(N)，面积结论不变。

---

## 七、交付物清单（examples/）

| 文件 | 内容 |
|------|------|
| `mesh4x4_grid2d.gds` | 4×4 2D 压实网格版图（1.35 KB） |
| `mesh16x16_grid2d.gds` | 16×16 2D 压实网格版图（18.6 KB） |
| `mesh128x128_grid2d.gds` | 128×128 2D 压实网格版图（1.15 MB，2.34 mm²） |
| `mesh4x4_grid2d_drive_manifest.csv` | 10 行驱动清单（6 MZI + 4 OUT） |
| `mesh16x16_grid2d_drive_manifest.csv` | 136 行驱动清单（120 MZI + 16 OUT） |
| `mesh128x128_grid2d_drive_manifest.csv` | 8256 行驱动清单（8128 MZI + 128 OUT） |
| `lda/lda_layout/mesh_pnr.py` | 新增 `clements_rect_decompose` / `_ref_T` / `_rect_column_assignment` / `mesh_rect_*_fidelity`；`build_mesh_pnr(layout_mode='grid2d')` |

代码入口：`mp.build_mesh_pnr(dft_matrix(N), layout_mode="grid2d")`；默认 `layout_mode="serpentine"` 行为不变。

---

## 八、系统级代价专题闭环状态（D1/D2/D3 全闭合）

- **D1 总线损耗预算 —— 已闭合**：见 `D1_bus_loss_budget_2026-09-22.md`。
  结论：损耗 ∝N（L_bus≈35.6·N µm），路径方差由抽头耦合器插入损耗主导（≈9–10× 传播项）；
  128 需 α_tap≤.02 免幅度均衡，256 需绝热 MMI(α_tap≤.01)+评估幅度均衡，512 必须幅度均衡 PDK。
- **D2 同列抽头热串扰 —— 已闭合**：见 `D2_thermal_crosstalk_budget_2026-09-22.md`。
  结论：d_min=4µm 恒定、**N 无关**；Γ 对角占优 ⇒ 一次原位标定全补偿静态串扰，非阻断；
  深槽隔离在 N≥128 为推荐项（收紧时漂/标定负担），非强制。
- **D1+D2 合并专题**：见 `grid2d_system_cost_2026-09-22.md`（两代价本质对比 + 合并规模裁决表 + 待钉 PDK 参数）。
- **D3 规模再上探 —— 已闭合（含验证函数 bug 修正 + 512 全量实跑）**：见 `D3_scale_up_2026-09-22.md`。
  - O(N⁵) 瓶颈定位 + 回填等价 **O(N³) 快版为默认 API** `clements_rect_decompose`（bs_list bit-identical，加速 13.4–28.9×）。
  - 4/16/128/256/512 分解全绿（n_cols=N）；**256 全量主权 P&R 绿**（9.34 mm²、DRC PASS、LVS ACCEPT n=0、
    V_max 7.5 V、GDS 4.6 MB、驱动清单 32896 行，已落盘）。
  - **512 全量主权 P&R 已绿**（2026-09-22 续）：tdec=3.15s · tbuild=202.8s · layout_fid=1.0 · DRC PASS ·
    LVS ACCEPT(n=0) · cols=512 · **footprint=37.292 mm²** · x_max=18209 µm · V_max=7.5 V · GDS=18 MB ·
    驱动清单 131328 行，已落盘 `mesh512x512_grid2d.gds` + `_drive_manifest.csv`。
  - **性能连带修复**：保真度检查 `mesh_layout_transfer`(两 mode)/`mesh_rect_fidelity`/`mesh_rect_decomp_fidelity`
    原每 op 分配 `np.eye(N)` ⇒ O(N⁴)（512 ~550GB OOM）；新增 `_ref_T_apply_rows`/`_mzi_apply_rows` 改 O(N³) 后 512 跑通。
  - **物理保真度验证函数根因修正**：早前 `theta_is_full_angle` 补丁**错误**（`_mzi` 与 `_ref_T` 是不同
    SU(2) 相位约定，非 2θ 桥接）。现以 `mode='grid2d'|'serpentine'` 分路，两路均 = 1.0（机器精度，验至 N=512）。
    build 内部 `mesh_rect_fidelity` 本就正确 ⇒ 256/512 GDS 产物从未错，仅独立验证通道已对齐。
  - **判定（不变）**：D3 不独立，规模天花板由 D1（幅度均衡）决定；256+ 投产仍须绑 D1 幅度均衡 PDK（工程投产前置，非 P&R 正确前置）。
- **收官建议**：网格 P&R（P0 死缺口）+ 物理综合（P1-A）+ 规模爬升与工艺映射（P1-B）+ 2D 压实（P1-B 续）
  + 系统级代价（D1/D2/D3）五环+两专题已闭合，可作为 LDA 光子计算「主权编译→版图→流片量级」主链路对外演示锚点。
