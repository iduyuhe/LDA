"""D-121 · 时间复用架构的**可编程酉实现**（M4 延伸）——把「真路线是时间复用」
从架构口号变成：可构造 · 可数值验证 · 可机器判死。

════════════════════════════════════════════════════════════════════════════
问题（承接 D-120 / M4 的挂起结论）
────────────────────────────────────────────────────────────────────────────
D-120 给出的架构结论是：

  「静态被动网格元件 O(N²)、单路径损耗 O(N) dB ⇒ 规模上不可行；
    真路线是时间复用（Borealis a=6,L=3 ⇒ 216 模，仅 3 环，省 507 dB）。」

**但这句结论里藏着一个未验证的跳跃**：Borealis 的时间复用环是**固定晶格**
（为 GBS 采样设计的定值电路），它**不是**一个可编程通用干涉仪。于是必须追问：

  ❓ **时间复用架构能不能实现「任意 N 模酉」？** 若能，损耗墙是否就绕过去了？

本模块（D-121）就回答这个追问，并把答案钉成可判据。

════════════════════════════════════════════════════════════════════════════
模型（时空映射 · 显式且可数值复算）
────────────────────────────────────────────────────────────────────────────
N 个模 = N 个时间格（间隔 τ），光子在一根波导里以脉冲串形式飞行：

  ① **延迟环 = 模置换**：延迟 m·τ 把格子 (k, k+m) 带到同一时刻重叠
     ⇒ 一个酉置换 S_m（循环移位）。物理上由一段光纤延迟实现，**无有源元件**。
  ② **门层 = 匹配（matching）**：一片物理 MZI（EOM 按格子速率重配）在一轮次内
     把「不相交的相邻模对」(p, p+1) 各自按独立 (θ, φ) 旋转 ⇒ 一层**匹配层**。
     非相邻对由 S_m 共轭得到（引理 L1）。
  ③ **时间表（schedule）** = 一串步骤，每步 ∈ {对角相位层, 延迟, 匹配门层}。
     **深度 = 门层步数**（每个光子每步穿过物理 MZI 一次 ⇒ 每步一份插损）。

由此得到三条**可机器判定**的结论（本模块全部以闭式 + 构造性数值验证给出）：

  ★ 结论 1（可构造 · 通用性成立）
    存在**显式**时间复用时间表，用 **1 片物理 MZI** 重现任意 N 模酉到机器精度。
    构造：取平台 Reck 三角分解 D = G_k···G_1·U，把 op 序列**按光路程序**重排，
    再把其中**两两不相交**（因而对易 ⇒ 可同步）的门贪心聚合成匹配层。
    ⇒ 「时间复用能不能做通用酉」= **能**（实测 fid=1.0，N=4…64）。
    （构造深度落在 [N−1, N(N−1)/2]；三角 Reck 的 op 集**本质是串行链**
      —— 同列内相邻对共享模且顺序不可换 ⇒ 朴素构造深度 O(N²)。
      故本模块的损耗判定**不依赖**构造深度，而依赖下界，见结论 2/3。）

  ★ 结论 2（深度下界：参数计数，硬件无关 · **非紧下界**）
    N 模酉有 N² 个实参数；一片 2 模无损门只提供 1 个独立参数（一个 Givens 角），
    而一层最多容纳 ⌊N/2⌋ 片不相交门 ⇒ **参数计数下界 D ≥ N(N−1)/2 / ⌊N/2⌋**。
    N 偶 ⇒ **N−1**；N 奇 ⇒ **N**。（本模块以精确整数恒等式验证。）
    🔴 该下界**非紧**（2b 节给出收紧与可达性判定）。

  ★ 结论 2b（🔴 浅并行调度 + 深度界收敛：下界可达吗？**否**）
    朴素贪心构造「遇冲突即封步」⇒ 深度 = 门数 O(N²)。本模块给出**浅并行调度器**
    `schedule_shallow`：按依赖 DAG（共享模 ⇒ 有向边）的**关键路径分层** ⇒
    层 = 反链 = 匹配 ⇒ 深度 = 关键路径 = 任意合法调度的下界，且**达到**该下界
    ⇒ 对该 op 集**最优**。实测：Reck op 集最优深度恰为 **2N−3**（经典 Reck 光学深度）。
      ① **紧下界收紧**：偶 N 时相邻路径 P_N 的**唯一**最大匹配是偶数对 E ⇒
         若每层皆最大匹配则每层皆 E ⇒ 乘积是两两配对的块对角 ⇒ 非通用 ⇒ 至少一层
         非最大 ⇒ D·⌊N/2⌋−1 ≥ n_mzi ⇒ **D ≥ N**（> 参数下界 N−1）⇒ N−1 **不可达**。
      ② **平台可达值**：三角 Reck op 集最优 = 2N−3（构造 fid=1.0 + 关键路径下界双证）。
      ③ 诚实结论：D-121 的 N−1 是**合法但不紧**的下界；相邻耦合紧下界 = N；
         平台现有网格的**最优**深度 = 2N−3（N=216：23220 → **429** 层，**54×** 加速）。
         达 N 层需换**矩形网格分解**（登记为下一步，不在本模块声称）。

  ★ 结论 3（🔴 修正 M4 的口号：时间复用买元件数，**不买**深度/损耗）
    时间复用把**物理元件数**从 O(N²) 降到 O(1)（1 片 MZI + 1 条延迟）——
    这击败的是**可制造性墙 / 版图面积墙 / 耦合比越域墙**（D-118 实测 1077/23220
    片 MZI 分束比越域）；但**每模损耗 = 深度 × 单件损耗**，而深度下界是 Ω(N)
    ⇒ **通用酉的损耗墙原样保留**（甚至略差：多了环/开关损耗）。
    Borealis 之所以 216 模 @ ~9 dB，靠的是**放弃通用性**（深度 3 的固定晶格；
    可及参数 ≪ N²，维度计数直接判死），**不是**靠时间复用本身。

    结论：**「通用」与「省损」不可兼得 —— 这是参数计数决定的硬约束。**
    M4 的正确表述应为：「真路线是**时间复用 + 浅电路（放弃通用性）**」。

════════════════════════════════════════════════════════════════════════════
🔴 诚实边界（必读）
  · 本模块是**架构-资源模型**（设计预算口径），不是任一真机的实测比对。
  · 每轮次损耗 PER_ROUNDTRIP_LOSS_DB 为设计预算（MZI + 环/延迟/开关），非实测 PDK。
  · 与 Borealis 只比**规模/架构/参数计数**，**不比对数值**（其物理形态为 CV GBS，
    本平台为 DV 被动 LOQC；数据取自公开文献 A 级事实，仅引用不复算）。
  · 「深度下界」是**参数计数下界**（不问硬件细节），非可达性证明本身；
    可达性由结论 1 的**构造性时间表**独立给出（实测深度 ≥ 下界）。

════════════════════════════════════════════════════════════════════════════
红线自检标注：
- C 级自主：纯 numpy + 平台模块（lda_l2 / lda_qeda），零外部 EDA / 量子 SDK。
- LLM 不进判决路径：全部为整数恒等式 / numpy 线性代数 / 死标量判据。
- 数学锚（闭式，非拟合非仿真）：循环置换酉性 · S^N=I · 2 模门 = 酉 · Givens 参数
  计数 · ⌈n_mzi/⌊N/2⌋⌉ · 10^(−dB/10) —— 且「时间表重建 ≡ 目标酉」是**构造性实证**。
════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import math
from collections import OrderedDict

import numpy as np

from lda_l2 import mzi_mesh_matmul as MMM
from lda_qeda import scale_bench as SBM

__all__ = [
    "PER_MZI_LOSS_DB",
    "DELAY_LOSS_DB",
    "PER_ROUNDTRIP_LOSS_DB",
    "cyclic_shift_unitary",
    "pair_rotation_unitary",
    "gate_matching_ok",
    "matching_layer_unitary",
    "schedule_unitary",
    "schedule_from_reck_ops",
    "critical_path_layers",
    "schedule_shallow",
    "temporal_schedule_profile",
    "temporal_shallow_profile",
    "random_unitary",
    "universality_gate_count",
    "universality_depth_lower_bound",
    "adjacency_max_matching",
    "tight_depth_lower_bound",
    "depth_bound_report",
    "static_mesh_resources",
    "temporal_mesh_resources",
    "temporal_loss_at_depth",
    "temporal_loss_wall_n",
    "programmability_frontier",
    "fixed_lattice_programmability",
    "benchmark_against_borealis_temporal",
    "temporal_mesh_verdict",
    "run_selfchecks",
    "RED_LINE_DISCLOSURE",
]


# ---------------------------------------------------------------------------
# 物理常量（设计预算 · 与 D-120/lda_l2 同源）
# ---------------------------------------------------------------------------
# 单件 MZI 级联插损（dB）——直接复用 D-120 的同源常数（2.4 dB）
PER_MZI_LOSS_DB = float(SBM.PER_MZI_LOSS_DB)
# 每**轮次**额外损耗（dB）：延迟环比 MZI 多出的光纤延迟段 + 开关/解复用
# （设计预算，非实测 PDK；取 0.2 dB 量级——比 D-120 的整环 PER_LOOP_LOSS_DB=3.0
#  更保守，因为此处的「轮次」只是复用同一片 MZI + 一段固定延迟，不含独立 VBS 组）
DELAY_LOSS_DB = 0.20
# 每个时间步（= 光子穿过物理 MZI 一次）的插损（dB）
PER_ROUNDTRIP_LOSS_DB = PER_MZI_LOSS_DB + DELAY_LOSS_DB


# ---------------------------------------------------------------------------
# 1) 时空映射原语（golden：全部闭式、可精确验证）
# ---------------------------------------------------------------------------
def cyclic_shift_unitary(n_modes: int, m: int) -> np.ndarray:
    """延迟 m·τ 实现的模置换：输出格 i 收到输入格 (i−m) mod N 的光。

    即 (S_m x)_i = x_{(i−m) mod N} ⇒ S_m[i, (i−m) mod N] = 1。酉置换阵。
    物理实现：一段延迟 = m·τ 的光纤（或 N·τ 主环 + 附加延迟），**无有源元件**。
    """
    n = int(n_modes)
    if n < 2:
        raise ValueError("n_modes ≥ 2")
    mm = int(m) % n
    S = np.zeros((n, n), dtype=complex)
    for i in range(n):
        S[i, (i - mm) % n] = 1.0
    return S


def pair_rotation_unitary(n_modes: int, i: int, j: int,
                          theta: float, phi: float = 0.0) -> np.ndarray:
    """把平台的 MZI 单元 `mzi_unit_cell(θ, φ)` 嵌到模对 (i, j)（i<j）上，余恒等。

    这是「任意对可寻址」引理 L1 的代数形态：非相邻对 (i,j) 由延迟共轭得到：
        G(i,j) = S_m^{−i} · G(0, m) · S_m^{i},  m = j − i
    本函数直接给出嵌入结果（用于引理验证与 2 模 golden 对拍）。
    """
    n = int(n_modes)
    i, j = int(i), int(j)
    if n < 2:
        raise ValueError("n_modes ≥ 2")
    if not (0 <= i < j < n):
        raise ValueError("需 0 ≤ i < j < n_modes")
    U = np.eye(n, dtype=complex)
    U[np.ix_([i, j], [i, j])] = MMM.mzi_unit_cell(float(theta), float(phi))
    return U


def _gate_block(theta: float, phi: float, inv: bool = False) -> np.ndarray:
    """2 模门块：`inv=False` ⇒ 正向 MZI；`inv=True` ⇒ 其共轭转置（光路程上的朝向）。

    时间表的门一律以 `inv=True` 出现（与平台 `assemble_triangular_mesh` 的
    `G_m†` 装配约定逐位一致；把 MZI 转置视为一种版图朝向约定，非新物理）。
    """
    G = MMM.mzi_unit_cell(float(theta), float(phi))
    return G.conj().T if inv else G


def gate_matching_ok(gates, n_modes: int | None = None) -> bool:
    """一组门（每个形如 (i, θ, φ, inv)）是否构成**匹配**（相邻对 (i, i+1) 两两不相交）。

    匹配是「同一时间步内可同步施加」的充要条件：
    不相交的块作用于不同坐标 ⇒ 彼此对易 ⇒ 可并行、且与施加顺序无关。
    """
    used: set[int] = set()
    for (i, _th, _ph, _inv) in gates:
        ii = int(i)
        if n_modes is not None and not (0 <= ii and ii + 1 < int(n_modes)):
            return False
        if ii in used or ii + 1 in used:
            return False
        used.add(ii)
        used.add(ii + 1)
    return True


def matching_layer_unitary(n_modes: int, gates) -> np.ndarray:
    """把一层匹配门做成 N×N 酉矩阵（门形如 (i, θ, φ, inv)，作用于相邻对 (i, i+1)）。

    必须构成匹配（否则抛 ValueError —— 与「同一步内两门共享一个模」在物理上
    不可实现是同一条约束）。
    """
    n = int(n_modes)
    gates = [(int(i), float(th), float(ph), bool(inv)) for (i, th, ph, inv) in gates]
    if not gate_matching_ok(gates, n):
        raise ValueError("gate 集合不是匹配（存在共享模 / 越界）")
    T = np.eye(n, dtype=complex)
    for (i, th, ph, inv) in gates:
        G = _gate_block(th, ph, inv)
        ra, rb = T[i].copy(), T[i + 1].copy()
        T[i] = G[0, 0] * ra + G[0, 1] * rb
        T[i + 1] = G[1, 0] * ra + G[1, 1] * rb
    return T


def schedule_unitary(schedule, n_modes: int) -> np.ndarray:
    """把时间表逐步骤左乘成 N×N 传递矩阵（光按列表**顺序**穿过）。

    step 形态：
      {"kind": "diag",  "diag": 长度 N 复向量} —— 对角相位层（输入相位）
      {"kind": "shift", "m": int}              —— 延迟 m·τ（模置换）
      {"kind": "gates", "gates": [(i,θ,φ),…]}  —— 一层匹配门

    复杂度：门层按**行块**原地作用（每门 O(N)）⇒ 总计 O(#门 · N) = O(N³)。
    （与 D-120 记录的「独立装配路径 O(N⁵)」陷阱对照：此处不复用稠密矩阵乘法。）
    """
    n = int(n_modes)
    T = np.eye(n, dtype=complex)
    if not schedule:
        raise ValueError("schedule 非空")
    for step in schedule:
        kind = step.get("kind")
        if kind == "diag":
            d = np.asarray(step["diag"], dtype=complex)
            if d.shape != (n,):
                raise ValueError("diag 长度须为 N")
            T = d[:, None] * T
        elif kind == "shift":
            T = cyclic_shift_unitary(n, step["m"]) @ T
        elif kind == "gates":
            gates = [(int(i), float(th), float(ph), bool(inv))
                     for (i, th, ph, inv) in step["gates"]]
            if not gate_matching_ok(gates, n):
                raise ValueError("gates 步不是匹配")
            for (i, th, ph, inv) in gates:
                G = _gate_block(th, ph, inv)
                ra, rb = T[i].copy(), T[i + 1].copy()
                T[i] = G[0, 0] * ra + G[0, 1] * rb
                T[i + 1] = G[1, 0] * ra + G[1, 1] * rb
        else:
            raise ValueError(f"未知 step kind：{kind!r}")
    return T


# ---------------------------------------------------------------------------
# 2) 构造性通用时间表（★ 结论 1：时间复用确实能做通用酉）
# ---------------------------------------------------------------------------
def schedule_from_reck_ops(ops, D: np.ndarray, n_modes: int, *,
                           group: bool = True):
    """把平台 Reck 分解结果编译成**时间复用时间表**（光路程序 + 匹配聚合）。

    光路程序：先穿对角相位层 D，再按 ops **逆序**逐片穿 G_m†（与
    `assemble_triangular_mesh` 逐位一致）。
    匹配聚合：贪心把「与已入本步的门不相交」的下一个门并入同一步
    （不相交 ⇒ 对易 ⇒ 可同步）。group=False 则每门独占一步（朴素串行基线）。

    返回 (schedule, n_steps_gates)。
    """
    n = int(n_modes)
    if n < 2:
        raise ValueError("n_modes ≥ 2")
    d = np.diag(np.asarray(D, dtype=complex))
    schedule = [{"kind": "diag", "diag": d}]
    # 光程顺序：ops 逆序，每片取共轭转置块（G_m† 嵌入 (p, p+1)，inv=True）
    seq = []
    for (c, p, theta, phi) in reversed(list(ops)):
        seq.append((int(p), float(theta), float(phi), True))
    if not group:
        for g in seq:
            schedule.append({"kind": "gates", "gates": [g]})
        return schedule, len(seq)
    steps = 0
    i = 0
    while i < len(seq):
        cur = [seq[i]]
        used = {seq[i][0], seq[i][0] + 1}
        j = i + 1
        while j < len(seq):
            pj = seq[j][0]
            if pj in used or pj + 1 in used:
                break                       # 贪心：遇冲突即封步（保序）
            cur.append(seq[j])
            used.add(pj)
            used.add(pj + 1)
            j += 1
        schedule.append({"kind": "gates", "gates": cur})
        steps += 1
        i = j
    return schedule, steps


def random_unitary(n_modes: int, seed: int = 0) -> np.ndarray:
    """Haar 随机酉（QR 法 · 纯 numpy）：用于「任意酉」而非单一 benchmark 的验证。"""
    n = int(n_modes)
    rng = np.random.default_rng(int(seed))
    A = rng.normal(size=(n, n)) + 1j * rng.normal(size=(n, n))
    Q, R = np.linalg.qr(A)
    dg = np.diag(R)
    ph = dg / np.abs(dg)
    return Q * ph.conj()                    # 列相位归一 ⇒ Q 仍为酉


def temporal_schedule_profile(n_modes: int, *, seed: int = 0,
                              target: str = "random") -> dict:
    """建一条真实时间表并**实测**重建保真度（构造性通用性的实证）。

    时间表 = 光路程（对角相位层 → 逆序门）经「匹配贪心聚合」压缩步数。
    深度语义：`n_gate_steps` = 光子在物理 MZI 上停留的**同步步数**（每步一份插损）；
    它落在 [通用性下界 D_min, 门数 n_mzi] 之间 —— **任何**合法时间表都不低于下界。
    """
    n = int(n_modes)
    U = MMM.dft_matrix(n) if target == "dft" else random_unitary(n, seed=seed)
    ops, D = MMM.reck_triangular_mesh(U)
    sched, steps = schedule_from_reck_ops(ops, D, n, group=True)
    U_rec = schedule_unitary(sched, n)
    fid = MMM.unitary_fidelity(U_rec, U)
    gates_per_step = [len(s["gates"]) for s in sched if s["kind"] == "gates"]
    dmin = universality_depth_lower_bound(n)
    n_gates = int(len(ops))
    return {
        "n_modes": n,
        "target": target,
        "n_gates": n_gates,
        "n_gate_steps": int(steps),
        "max_gates_per_step": int(max(gates_per_step)) if gates_per_step else 0,
        "fidelity": float(fid),
        "unitary_ok": bool(float(np.max(np.abs(U_rec @ U_rec.conj().T
                                             - np.eye(n)))) < 1e-9),
        "n_physical_mzi": 1,
        "depth_lower_bound": dmin,
        "depth_within_bounds": bool(dmin <= int(steps) <= n_gates),
    }


# ---------------------------------------------------------------------------
# 2b) ★ 浅并行调度器（把「朴素 O(N²) 构造」压到该 op 集的**最优深度**）
# ---------------------------------------------------------------------------
# 朴素贪心 `schedule_from_reck_ops(group=True)`「遇冲突即封步」⇒ 深度 ≈ 门数 O(N²)。
# 本节改为**依赖 DAG 的关键路径分层**：两片门共享模 ⇒ 不可对易 ⇒ 有向边（按序列序）；
# 层 = 反链 = 匹配 ⇒ 可同步。关键路径 = 任意合法调度的深度下界，且本分层**达到**它
# ⇒ 对该 op 集**最优**。实测：Reck op 集的关键路径恰为 **2N−3**（经典 Reck 光学深度）。


def _pair_share_mode(a, b) -> bool:
    """两片门（元素至少含模索引 p，作用于相邻对 (p,p+1)）是否共享模。"""
    pa, pb = int(a[0]), int(b[0])
    return pa == pb or pa + 1 == pb or pb + 1 == pa


def critical_path_layers(seq):
    """按「最长有向路」把门序列分层。返回 (layers, depth)。

    dp[i] = 1 + max{ dp[j] : j<i 且 seq[j] 与 seq[i] 共享模 }。
    同层两门不共享模 ⇒ 对易 ⇒ 可同步；且层内**两两不相交** ⇒ 是真匹配
    （满足 `gate_matching_ok`）。depth = 依赖 DAG 关键路径。
    """
    L = len(seq)
    if L == 0:
        raise ValueError("seq 非空")
    dp = [1] * L
    for i in range(L):
        best = 0
        for j in range(i):
            if _pair_share_mode(seq[j], seq[i]) and dp[j] > best:
                best = dp[j]
        dp[i] = best + 1
    depth = max(dp)
    layers = [[] for _ in range(depth)]
    for i in range(L):
        layers[dp[i] - 1].append(seq[i])
    return layers, int(depth)


def schedule_shallow(ops, D, n_modes):
    """★ 浅并行调度器：把 Reck op 集编成**关键路径最优**的时间表。

    光路程序与 `schedule_from_reck_ops` **逐位一致**（对角层 D → ops 逆序穿 G†），
    只改聚合策略：`group=False` 的最优版 —— 关键路径分层（而非贪心封步）。
    返回 (schedule, depth, max_gates_per_layer, layers_are_matchings)。
    """
    n = int(n_modes)
    if n < 2:
        raise ValueError("n_modes ≥ 2")
    d = np.diag(np.asarray(D, dtype=complex))
    seq = [(int(p), float(th), float(ph), True)
           for (_c, p, th, ph) in reversed(list(ops))]
    layers, depth = critical_path_layers(seq)
    ok = all(gate_matching_ok(lay, n) for lay in layers)
    schedule = [{"kind": "diag", "diag": d}]
    for lay in layers:
        schedule.append({"kind": "gates", "gates": lay})
    return schedule, int(depth), int(max((len(l) for l in layers), default=0)), bool(ok)


def temporal_shallow_profile(n_modes, *, seed: int = 0, target: str = "random") -> dict:
    """浅调度实测：深度 = 关键路径 2N−3 · 重建 fid = 1.0 · 相对朴素贪心的加速。"""
    n = int(n_modes)
    U = MMM.dft_matrix(n) if target == "dft" else random_unitary(n, seed=seed)
    ops, D = MMM.reck_triangular_mesh(U)
    sched, depth, mx, ok = schedule_shallow(ops, D, n)
    U_rec = schedule_unitary(sched, n)
    _sched_serial, naive_depth = schedule_from_reck_ops(ops, D, n, group=False)
    n_gates = int(len(ops))
    return {
        "n_modes": n,
        "target": target,
        "n_gates": n_gates,
        "shallow_depth": int(depth),
        "critical_path": int(depth),
        "max_gates_per_layer": int(mx),
        "layers_are_matchings": bool(ok),
        "naive_serial_depth": int(naive_depth),
        "speedup_vs_serial": float(naive_depth) / float(depth),
        "depth_over_2N_3": float(depth - (2 * n - 3)),
        "fidelity": float(MMM.unitary_fidelity(U_rec, U)),
        "unitary_ok": bool(float(np.max(np.abs(U_rec @ U_rec.conj().T - np.eye(n)))) < 1e-9),
        "n_physical_mzi": 1,
    }


def adjacency_max_matching(n_modes: int) -> dict:
    """相邻模路径 P_N（节点 0..N−1，可耦合对 (p,p+1)）的最大匹配的信息。

    ⌊N/2⌋ = 最大匹配尺寸；**偶 N 时唯一**（偶数对 E={(0,1),(2,3),…}），
    奇 N 时多解（可从端点留 1 个节点）—— 这条「唯一性」是收紧深度下界的关键。
    """
    n = int(n_modes)
    if n < 2:
        raise ValueError("n_modes ≥ 2")
    size = n // 2
    unique = (n % 2 == 0)
    return {
        "n_modes": n,
        "max_matching_size": int(size),
        "unique_max_matching": bool(unique),
        "unique_pattern": ([(2 * i, 2 * i + 1) for i in range(size)] if unique else None),
    }


def tight_depth_lower_bound(n_modes: int) -> int:
    """相邻耦合下的**紧**深度下界。

    · 参数计数下界 ⌈n_mzi/⌊N/2⌋⌉（N 偶 ⇒ N−1）**非紧**：
      偶 N 时 P_N 的**唯一**最大匹配是偶数对 E；若每层都是最大匹配则每层皆 E
      ⇒ 乘积是「两两配对」的块对角 ⇒ **非通用** ⇒ 至少一层 ≤ ⌊N/2⌋−1
      ⇒ D·⌊N/2⌋ − 1 ≥ n_mzi ⇒ D ≥ N−1 + 2/N ⇒ **D ≥ N**（D 取整）。
    · N=2 例外（只有一对，E 即整个 2×2）⇒ 1。
    · 奇 N：参数计数下界已是 N（唯一性论证不适用，取参数界）。
    """
    n = int(n_modes)
    if n < 2:
        raise ValueError("n_modes ≥ 2")
    if n == 2:
        return 1
    return int(n)


def depth_bound_report(n_modes: int) -> dict:
    """★ 三口径深度界（一张表说清「下界 / 收紧 / 可达」）。

      · parameter_count_bound：⌈n_mzi/⌊N/2⌋⌉（D-121 原口径；**非紧**）
      · tight_adjacency_bound：N（偶 N 由唯一最大匹配收紧，见 tight_depth_lower_bound）
      · reck_mesh_optimum：2N−3（平台三角 Reck op 集的**最优**深度，本模块给出调度）
    ⇒ 诚实结论：D-121 的 N−1 **不可达**；紧下界 ≥ N；平台现有网格的最优 = 2N−3。
    """
    n = int(n_modes)
    if n < 2:
        raise ValueError("n_modes ≥ 2")
    nm = universality_gate_count(n)
    per = n // 2
    pc = int(-(-nm // per))
    tight = tight_depth_lower_bound(n)
    mm = adjacency_max_matching(n)
    return {
        "n_modes": n,
        "n_mzi": int(nm),
        "parameter_count_bound": pc,
        "parameter_count_tight": bool(pc == tight),
        "tight_adjacency_bound": int(tight),
        "unique_max_matching": mm["unique_max_matching"],
        "reck_mesh_optimum": int(2 * n - 3),
        "reck_over_tight": int(2 * n - 3 - tight),
        "derivation": ("偶 N：唯一最大匹配 ⇒ 至少一层非最大 ⇒ D·⌊N/2⌋−1 ≥ n_mzi"
                       " ⇒ D ≥ N；奇 N：参数界即 N。"),
        "verdict": (f"参数下界 {pc}（D-121 原口径）**不可达**；相邻耦合紧下界 = {tight}；"
                    f"平台三角 Reck op 集的最优深度 = {2 * n - 3}（本模块调度达到，"
                    "关键路径同时给出下界）⇒ 「下界可达性」的诚实答案：**否**"
                    "（对该网格），但可达深度已从朴素 O(N²) 压到 O(N) 的最优值。"),
    }


# ---------------------------------------------------------------------------
# 3) 资源 / 下界（★ 结论 2 & 3）
# ---------------------------------------------------------------------------
def universality_gate_count(n_modes: int) -> int:
    """通用 N 模酉所需 2 模门数 = N(N−1)/2（Reck/Clements 定理，精确整数）。"""
    n = int(n_modes)
    if n < 2:
        raise ValueError("n_modes ≥ 2")
    return int(n * (n - 1) // 2)


def universality_depth_lower_bound(n_modes: int) -> int:
    """**通用性深度下界**（参数计数 · 硬件无关）：

        每片 2 模无损门提供 1 个独立实参数（一个 Givens 角；其余为局部相位规范）；
        一层最多容纳 ⌊N/2⌋ 片**不相交**相邻门 ⇒
            D ≥ ⌈ n_mzi / ⌊N/2⌋ ⌉,  n_mzi = N(N−1)/2

    N 偶：N(N−1)/2 ÷ (N/2) = N−1（整除）⇒ 下界 = **N−1**；
    N 奇：N(N−1)/2 ÷ ((N−1)/2) = N（整除）⇒ 下界 = **N**。
    用精确整数上取整（禁浮点 ceil：`math.ceil` 在 N=216 上曾因 log/除法抖动误判）。
    """
    n = int(n_modes)
    if n < 2:
        raise ValueError("n_modes ≥ 2")
    per_layer = n // 2
    if per_layer < 1:
        raise ValueError("n_modes ≥ 2")
    return int(-(-universality_gate_count(n) // per_layer))


def static_mesh_resources(n_modes: int) -> dict:
    """静态被动网格资源（复用 D-120 同源规模律）：元件 O(N²)、深度 N−1。"""
    laws = SBM.mesh_scaling_laws(n_modes)
    return {
        "kind": "static_passive_mesh",
        "n_modes": int(n_modes),
        "n_physical_mzi": laws["n_mzi"],
        "depth": laws["mzi_per_path"],
        "loss_per_mode_db": laws["loss_per_path_db"],
        "components_order": "O(N^2)",
        "depth_order": "O(N)",
    }


def temporal_mesh_resources(n_modes: int, depth: int) -> dict:
    """时间复用资源：**1 片物理 MZI** + 1 条主延迟（+EOM 重配）⇒ 元件 O(1)。

    深度语义：`depth` = 光子依次穿过物理 MZI 的**同步步数**（= 每模损耗的份数）。
    调用方若传 `universality_depth_lower_bound(N)`，即得**理论最优情形**（对时间复用
    最有利的假设）——本模块的「不省损」结论正是在此最有利假设下给出的。
    """
    n = int(n_modes)
    if n < 2:
        raise ValueError("n_modes ≥ 2")
    dep = int(depth)
    if dep < 1:
        raise ValueError("depth ≥ 1")
    loss = dep * PER_ROUNDTRIP_LOSS_DB
    return {
        "kind": "time_multiplexed_universal",
        "n_modes": n,
        "n_physical_mzi": 1,
        "n_delay_lines": 1,
        "n_eom_settings": int(dep * (n // 2)),       # 需按格子速率重配的次数
        "depth": dep,
        "depth_basis": ("lower_bound_best_case"
                        if dep == universality_depth_lower_bound(n) else "given"),
        "loss_per_mode_db": float(loss),
        "per_path_eta": float(10.0 ** (-loss / 10.0)),
        "components_order": "O(1)",
        "depth_order": "O(N)",
        "per_roundtrip_loss_db": float(PER_ROUNDTRIP_LOSS_DB),
    }


def temporal_loss_at_depth(n_modes: int, depth: int) -> float:
    """时间复用表在给定深度下**每模**插损（dB）= 深度 × 单轮次损耗。"""
    return float(int(depth) * PER_ROUNDTRIP_LOSS_DB)


def temporal_loss_wall_n(eta_threshold: float, *, cap: int = 100000) -> int:
    """时间复用**通用**表的损耗关门点：使 η(N) < eta_threshold 的最小 N（≥2）。

    深度取通用性下界 D_min(N)（因通用性必须付这个深度）⇒
        η(N) = 10^(−D_min(N)·per_rt/10)
    返回 cap+1 表示在 cap 内未关门。用**整数逐步扫描**（禁闭式浮点反解，
    避 D_min 的分段整数行为导致的解析陷阱）。
    """
    if not (0.0 < eta_threshold <= 1.0):
        raise ValueError("eta_threshold ∈ (0,1]")
    if PER_ROUNDTRIP_LOSS_DB <= 0.0:
        return 0
    for n in range(2, int(cap) + 1):
        if temporal_loss_at_depth(n, universality_depth_lower_bound(n)) \
                > -10.0 * math.log10(eta_threshold):
            return int(n)
    return int(cap) + 1


def programmability_frontier(n_modes: int, depths=None) -> dict:
    """★ 可编程性前沿：深度 D ↔ 可及参数数 / 损耗 / 是否通用（一张表看清取舍）。

        可及参数 ≈ ⌊N/2⌋ · D   （每门 1 个独立参数）
        通用 ⟺ ⌊N/2⌋·D ≥ N(N−1)/2 ⟺ D ≥ D_min
    """
    n = int(n_modes)
    if n < 2:
        raise ValueError("n_modes ≥ 2")
    dmin = universality_depth_lower_bound(n)
    need = universality_gate_count(n)
    if depths is None:
        depths = sorted({1, 2, 3, 4, 8, 16, 32, 64, dmin})
    rows = []
    for d in sorted({int(x) for x in depths if 1 <= int(x) <= dmin}):
        reach = (n // 2) * d
        rows.append({
            "depth": int(d),
            "max_gates": int(reach),
            "reachable_params": int(reach),
            "param_fraction_of_unitary": float(reach) / float(n * n),
            "loss_db": temporal_loss_at_depth(n, d),
            "universal": bool(reach >= need),
        })
    return {
        "n_modes": n,
        "gates_needed_universal": int(need),
        "depth_lower_bound": int(dmin),
        "max_gates_per_step": int(n // 2),
        "rows": rows,
        "headline": (f"通用性需 D ≥ {dmin}（参数计数下界）⇒ 每模损耗 ≥ "
                     f"{temporal_loss_at_depth(n, dmin):.0f} dB —— 与静态网格同阶。"),
    }


def fixed_lattice_programmability(n_modes: int, *, lattice_a: int = 6) -> dict:
    """固定晶格（Borealis 式）的可编程性上界：深度 = 环数 L = ⌈log_a N⌉，可及参数 ≈ ⌊M/2⌋·L。

    ⇒ 维度计数直接判「固定浅晶格**不可能**通用」：可及参数 ≪ M(M−1)/2。
    """
    n = int(n_modes)
    a = int(lattice_a)
    if n < 2:
        raise ValueError("n_modes ≥ 2")
    if a < 2:
        raise ValueError("lattice_a ≥ 2")
    loops, realized = 0, 1
    while realized < n:
        realized *= a
        loops += 1
    reach = (realized // 2) * loops
    need = universality_gate_count(realized)
    return {
        "kind": "fixed_lattice",
        "n_modes_requested": n,
        "lattice_a": a,
        "n_loops_depth": int(loops),
        "n_modes_realized": int(realized),
        "reachable_params_model": int(reach),
        "gates_needed_universal": int(need),
        "param_fraction": float(reach) / float(realized * realized),
        "universal": bool(reach >= need),
        "depth_order": "O(log_a N)",
    }


# ---------------------------------------------------------------------------
# 4) 对标 Borealis（外部 A 级事实 · 只比规模/架构/参数计数）
# ---------------------------------------------------------------------------
def benchmark_against_borealis_temporal(n_modes: int = 216) -> dict:
    """Borealis 216 模 vs 本平台（静态网格 / 时间复用通用表）的**架构-参数计数**对照。"""
    n = int(n_modes)
    st = static_mesh_resources(n)
    dmin = universality_depth_lower_bound(n)
    tm = temporal_mesh_resources(n, dmin)
    lat = fixed_lattice_programmability(n, lattice_a=SBM.BOREALIS_LATTICE_A)
    ref = SBM.BOREALIS_REF
    rows = [
        {"axis": "模式数", "borealis": ref["squeezed_modes"], "lda_temporal_universal": n,
         "match": ref["squeezed_modes"] == n},
        {"axis": "架构", "borealis": "时间复用**固定**晶格（3 环，a=6⇒a³=216）",
         "lda_temporal_universal": f"时间复用**通用**表（1 片 MZI × 深度 {dmin}）",
         "match": False},
        {"axis": "电路深度", "borealis": lat["n_loops_depth"],
         "lda_temporal_universal": dmin, "match": False},
        {"axis": "可及参数（模型计数）", "borealis": lat["reachable_params_model"],
         "lda_temporal_universal": universality_gate_count(n), "match": False},
        {"axis": "报称可编程参数", "borealis": ref["programmable_parameters"],
         "lda_temporal_universal": universality_gate_count(n), "match": False},
        {"axis": "通用性（任意酉？）", "borealis": "否（维度计数判死）",
         "lda_temporal_universal": "是（构造性时间表实测 fid=1.0）", "match": False},
        {"axis": "每模损耗", "borealis": "≈ 数十 dB 内（3 环量级）",
         "lda_temporal_universal": f"{tm['loss_per_mode_db']:.0f} dB（深度 {dmin}）",
         "match": False},
    ]
    return {
        "n_modes": n,
        "gates_needed_universal": universality_gate_count(n),
        "borealis_ref": ref,
        "borealis_lattice": lat,
        "lda_static_mesh": st,
        "lda_temporal_universal": tm,
        "comparison": rows,
        "mode_count_matches": ref["squeezed_modes"] == n,
        "same_modality": False,
        "reported_params_fraction": float(ref["programmable_parameters"]) / float(n * n),
        "honest_boundary": (
            "① 模数对标成立（216=216），但**物理形态不同**（CV GBS vs DV 被动 LOQC），"
            "**不比对具体数值**；② Borealis 数据为外部 A 级事实（Nature 606, 75-81 (2022)），"
            "仅引用不复算；③ **核心对照在参数计数**：Borealis 报称可编程参数 "
            f"{ref['programmable_parameters']} ≪ N²={n * n}（占比 "
            f"{ref['programmable_parameters'] / (n * n) * 100:.1f}%）⇒ 其浅晶格架构"
            "**不可能**实现任意 216 模酉 —— 它用「放弃通用性」换来「浅深度/低损耗」。"
            "④ 本平台的损耗为设计预算口径，非实测 PDK（属 D5 外部依赖）。"),
    }


def temporal_mesh_verdict(n_modes: int = 216) -> dict:
    """★ 结论 3 的机器判据：时间复用**买什么、不买什么**（在最有利假设下判定）。

    取**理论最优深度** D_min（对时间复用最有利）作为基准：
      · 任何合法通用时间表的深度 ≥ D_min（参数计数下界）⇒ 每模损耗 ≥ D_min·per_rt；
      · 静态网格单路径损耗 = (N−1)·per_mzi；
      · per_rt = per_mzi + 0.2 > per_mzi 且 D_min ≈ N−1 ⇒ **时间复用严格更差**。
    ⇒ 「省损耗」这条路被参数计数堵死；时间复用真正的价值在**元件数**。
    """
    n = int(n_modes)
    st = static_mesh_resources(n)
    dmin = universality_depth_lower_bound(n)
    tm = temporal_mesh_resources(n, dmin)
    loss_saved = st["loss_per_mode_db"] - tm["loss_per_mode_db"]
    return {
        "n_modes": n,
        "universal_constructible": True,
        "depth_required_lower_bound": int(dmin),
        "depth_basis": "theoretical lower bound（对时间复用最有利的假设）",
        "static_n_physical_mzi": st["n_physical_mzi"],
        "temporal_n_physical_mzi": 1,
        "element_saving_factor": float(st["n_physical_mzi"]),
        "static_loss_per_mode_db": st["loss_per_mode_db"],
        "temporal_loss_lower_bound_db": tm["loss_per_mode_db"],
        "loss_saved_db_by_time_multiplexing": float(loss_saved),
        "loss_saving_strictly_negative": bool(loss_saved < 0.0),
        "buys": ["物理元件数 O(N²)→O(1)（可制造性 / 版图面积 / 对准难度）",
                 "耦合比越域风险：只需 1 片 MZI 落在可实现域"
                 "（D-118 曾报 1077/23220 片越域）",
                 "可重配代价：同一硬件换表即换电路"],
        "does_not_buy": ["每模损耗（= 深度 × 单件损耗，而通用性下界 D ≥ N−1 ⇒ Ω(N) dB）",
                         "通用性所付的深度（参数计数硬约束）",
                         "标定相位数（仍 O(N²)）"],
        "proof_sketch": (
            "① 通用 N 模酉需 n_mzi=N(N−1)/2 片 2 模门（Clements 必要性定理）；"
            "② 一层最多 ⌊N/2⌋ 片不相交门 ⇒ 任何时间表深度 D ≥ ⌈n_mzi/⌊N/2⌋⌉ = N−1（N 偶）；"
            f"③ 故每模损耗 ≥ D_min·per_rt = {tm['loss_per_mode_db']:.0f} dB > "
            f"静态网格 (N−1)·per_mzi = {st['loss_per_mode_db']:.0f} dB。"),
        "headline": (
            f"时间复用**能**实现任意 {n} 模酉（构造性时间表已实测 fid=1.0），"
            f"但即便取理论最优深度 {dmin}，每模损耗 {tm['loss_per_mode_db']:.0f} dB —— "
            f"比静态网格（{st['loss_per_mode_db']:.0f} dB）**严格更差**（多了环/开关损耗）。"
            "⇒ 「通用」与「省损」不可兼得（参数计数硬约束）：M4 的正确表述是"
            "「真路线 = 时间复用 + 浅电路（放弃通用性）」。"),
    }


# ---------------------------------------------------------------------------
# 5) 自检锚
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    """D-121 自检：时空原语 / 任意对可寻址 / 2 模 golden / 匹配合法性 /
    构造性通用性（多 N 多酉）/ 深度下界整数恒等式 / 资源对比 / 损耗墙不省 /
    Borealis 维度计数判死 / 前沿表自洽 / 护栏。"""
    from lda_qeda import loqc_states as LS
    res = OrderedDict()

    # ① 循环移位是酉置换，且 S^N = I
    ok1 = True
    for n in (4, 7, 216):
        for m in (1, 3, n - 1):
            S = cyclic_shift_unitary(n, m)
            if not (np.allclose(S @ S.conj().T, np.eye(n))
                    and np.allclose(S.sum(axis=0), 1.0)
                    and np.allclose(S.sum(axis=1), 1.0)):
                ok1 = False
        if not np.allclose(np.linalg.matrix_power(cyclic_shift_unitary(n, 1), n),
                           np.eye(n)):
            ok1 = False
    res["① 延迟环=酉置换：S_m 酉性 + S_1^N=I（N=4/7/216）"] = ok1

    # ② 任意对可寻址引理 L1：非相邻对由延迟共轭得到（与直接嵌入逐位一致）
    n, m, i = 7, 3, 2
    th, ph = 0.7, 0.4
    direct = pair_rotation_unitary(n, i, i + m, th, ph)
    # 显式置换 P（把模 k 搬到模 k+i）共轭：P·G(0,m)·P† 把门搬到 (i, i+m)
    # 🔴 必须从**零阵**起建（用 np.eye 起手会残留对角 1 ⇒ 置换不成立 ⇒ 假红/假绿）
    P = np.zeros((n, n), dtype=complex)
    for k in range(n):
        P[(k + i) % n, k] = 1.0
    conj = P @ pair_rotation_unitary(n, 0, m, th, ph) @ P.conj().T
    res["② ★引理 L1★ 任意对由延迟共轭寻址：(i,i+m) ≡ P·(0,m)·P†（逐位一致）"] = bool(
        float(np.max(np.abs(direct - conj))) < 1e-14)

    # ③ 2 模 golden：与 loqc_states.bs_unitary 同分束比（θ↔θ/2）+ 仅差局部相位规范
    theta = 0.9
    U_lda = MMM.mzi_unit_cell(theta, 0.3)
    U_bs = LS.bs_unitary(theta / 2.0, 0.3 + math.pi / 2.0)
    gauge = U_lda @ U_bs.conj().T
    diag_gauge = bool(float(np.max(np.abs(gauge - np.diag(np.diag(gauge))))) < 1e-13)
    mag_match = bool(float(np.max(np.abs(np.abs(U_lda) - np.abs(U_bs)))) < 1e-13)
    res["③ 2 模 golden：MZI 与 bs_unitary 同分束比 + 差一个对角相位规范（闭式）"] = (
        diag_gauge and mag_match)

    # ④ 匹配合法性护栏：共享模 / 越界 / 非酉门层的门必须抛错
    guard4 = True
    for bad in ((lambda: matching_layer_unitary(4, [(0, 0.1, 0.0, False),
                                                    (1, 0.1, 0.0, False)])),
                (lambda: matching_layer_unitary(4, [(3, 0.1, 0.0, False)])),
                (lambda: pair_rotation_unitary(4, 2, 1, 0.1)),
                (lambda: cyclic_shift_unitary(1, 1)),
                (lambda: universality_depth_lower_bound(1))):
        try:
            bad()
            guard4 = False
        except ValueError:
            pass
    res["④ 护栏：共享模门层 / 越界门 / i≥j / N<2 抛 ValueError"] = guard4

    # ⑤ ★核心★ 构造性通用性：时间表重建 ≡ 目标酉（机器精度，多 N 多酉）
    ok5 = True
    detail5 = []
    for n_ in (4, 8, 16, 32, 64):
        for tgt in ("dft", "random"):
            pr = temporal_schedule_profile(n_, target=tgt, seed=n_ * 7)
            detail5.append(f"N={n_}/{tgt}:fid={pr['fidelity']:.12f}")
            if not (abs(pr["fidelity"] - 1.0) < 1e-11 and pr["unitary_ok"]):
                ok5 = False
    res["⑤ ★构造性通用性★ 时间表（1 片 MZI）重建任意酉=机器精度"] = ok5

    # ⑥ 深度下界整数恒等式：N 偶⇒N−1，N 奇⇒N
    ok6 = True
    for n_ in (2, 3, 4, 5, 8, 16, 32, 64, 100, 128, 216):
        d = universality_depth_lower_bound(n_)
        if n_ % 2 == 0 and d != n_ - 1:
            ok6 = False
        if n_ % 2 == 1 and d != n_:
            ok6 = False
    res["⑥ 深度下界闭式：N 偶⇒N−1 · N 奇⇒N（含 216⇒215，精确整数）"] = ok6

    # ⑦ 构造性时间表自洽：门数 = N(N−1)/2 · 深度 ∈ [D_min, 门数] · 每步为真匹配
    ok7 = True
    detail7 = []
    for n_ in (4, 16, 64):
        pr = temporal_schedule_profile(n_, target="dft")
        d = universality_depth_lower_bound(n_)
        detail7.append(f"N={n_}:gates={pr['n_gates']} steps={pr['n_gate_steps']} dmin={d}")
        if not (pr["n_gates"] == n_ * (n_ - 1) // 2
                and pr["depth_within_bounds"] is True
                and pr["n_gate_steps"] >= d):
            ok7 = False
    res["⑦ 构造时间表自洽：门数=N(N−1)/2 · 深度∈[下界, 门数]（任何时间表 ≥ 下界）"] = ok7

    # ⑧ 元件数：静态 O(N²) vs 时间复用 1 片 MZI（省 2.3 万倍 @216）
    st = static_mesh_resources(216)
    vd = temporal_mesh_verdict(216)
    res[f"⑧ 元件数：静态 {st['n_physical_mzi']} 片 vs 时间复用 1 片（省 {vd['element_saving_factor']:.0f}×）"] = (
        st["n_physical_mzi"] == 23220 and vd["temporal_n_physical_mzi"] == 1
        and vd["element_saving_factor"] > 20000.0)

    # ⑨ ★修正 M4 口号★ 在**最有利假设**（理论最优深度）下时间复用仍不省损（严格更差）
    res[f"⑨ ★修正★ 最有利假设下时间复用仍更差：静态 {vd['static_loss_per_mode_db']:.0f} dB vs "
        f"复用下界 {vd['temporal_loss_lower_bound_db']:.0f} dB（省 "
        f"{vd['loss_saved_db_by_time_multiplexing']:.0f} dB < 0）"] = (
        vd["loss_saving_strictly_negative"] is True
        and vd["universal_constructible"] is True
        and vd["depth_required_lower_bound"] == 215)

    # ⑩ Borealis 固定晶格维度计数判死（可及参数 ≪ N²）
    lat = fixed_lattice_programmability(216, lattice_a=6)
    bm = benchmark_against_borealis_temporal(216)
    res[f"⑩ Borealis 晶格（3 环）维度判死：可及 {lat['reachable_params_model']} ≪ "
        f"N²={lat['n_modes_realized'] ** 2} ⇒ 非通用"] = (
        lat["n_loops_depth"] == 3 and lat["universal"] is False
        and lat["reachable_params_model"] < lat["n_modes_realized"] ** 2
        and bm["reported_params_fraction"] < 0.05)

    # ⑪ 前沿表自洽：可及参数随 D 线性；通用 ⟺ D ≥ D_min
    fr = programmability_frontier(216)
    ok11 = (fr["depth_lower_bound"] == 215
            and all(r["universal"] == (r["depth"] >= 215) for r in fr["rows"])
            and all(r["max_gates"] == 108 * r["depth"] for r in fr["rows"]))
    res["⑪ 前沿表自洽：可及参数=⌊N/2⌋·D 线性 · 通用⟺D≥215"] = ok11

    # ⑫ 时间复用通用表的损耗关门点存在，且**不比静态网格更晚**（不构成规模出路）
    w_tm = temporal_loss_wall_n(1e-2)
    w_st = SBM.loss_wall_n(1e-2)
    res[f"⑫ 时间复用通用表损耗关门点 N*={w_tm} ≤ 静态网格 N*={w_st} ⇒ 不构成规模出路"] = (
        2 <= w_tm <= w_st)

    # ⑬ 跨模块桥：时间表的门层酉 ≡ 平台 mesh 单列语义（对角相位层 + 逆序块）
    n_ = 6
    U_ = random_unitary(n_, seed=3)
    ops_, D_ = MMM.reck_triangular_mesh(U_)
    sched_, _ = schedule_from_reck_ops(ops_, D_, n_)
    U_rec_ = schedule_unitary(sched_, n_)
    U_plain = MMM.assemble_triangular_mesh(ops_, D_, n_)
    res["⑬ 跨模块桥：时间表重建 ≡ 平台 assemble_triangular_mesh（逐位一致）"] = bool(
        float(np.max(np.abs(U_rec_ - U_plain))) < 1e-13)

    # ⑭ ★核心★ 浅并行调度：深度 = 关键路径 2N−3 · 每层真匹配 · 重建 fid=1.0
    ok14 = True
    detail14 = []
    for n_ in (4, 5, 8, 16, 32, 64):
        for tgt in ("dft", "random"):
            pr = temporal_shallow_profile(n_, target=tgt, seed=n_ * 3 + 1)
            detail14.append(f"N={n_}/{tgt}:d={pr['shallow_depth']}")
            if not (pr["shallow_depth"] == 2 * n_ - 3 and pr["layers_are_matchings"]
                    and abs(pr["fidelity"] - 1.0) < 1e-11 and pr["unitary_ok"]):
                ok14 = False
    res["⑭ ★浅调度★ 深度=关键路径 2N−3 · 每层真匹配 · 重建 fid=1.0（N=4…64）"] = ok14

    # ⑮ 浅调度相对朴素串行（group=False）的加速
    ok15 = True
    detail15 = []
    for n_ in (8, 16, 64):
        pr = temporal_shallow_profile(n_, target="dft")
        detail15.append(f"N={n_}:{pr['naive_serial_depth']}→{pr['shallow_depth']}"
                        f"({pr['speedup_vs_serial']:.1f}×)")
        if not (pr["naive_serial_depth"] == n_ * (n_ - 1) // 2
                and pr["speedup_vs_serial"] > 1.5):
            ok15 = False
    res["⑮ 浅调度加速：朴素串行 n_mzi → 2N−3（N=8/16/64 的加速比）"] = ok15

    # ⑯ ★紧界论证★ 偶 N 最大匹配唯一 ⇒ 紧下界 N（> 参数下界 N−1）；N=2 例外
    ok16 = True
    for n_ in (4, 6, 8, 16, 32, 64):
        mm = adjacency_max_matching(n_)
        if not (mm["unique_max_matching"] and mm["max_matching_size"] == n_ // 2):
            ok16 = False
        if tight_depth_lower_bound(n_) != n_:
            ok16 = False
        if not (universality_depth_lower_bound(n_) == n_ - 1
                and tight_depth_lower_bound(n_) > universality_depth_lower_bound(n_)):
            ok16 = False
    for n_ in (3, 5, 7):                      # 奇 N：唯一性论证不适用，取参数界 N
        if tight_depth_lower_bound(n_) != n_:
            ok16 = False
    res["⑯ ★紧界★ 偶 N 唯一最大匹配 ⇒ 紧下界 = N > 参数下界 N−1（N=2 例外=1）"] = ok16

    # ⑰ 三口径界自洽：参数界 ≤ 紧界 ≤ 平台网格最优(=2N−3)
    ok17 = True
    detail17 = []
    for n_ in (4, 8, 16, 64, 216):
        b = depth_bound_report(n_)
        detail17.append(f"N={n_}:{b['parameter_count_bound']}/"
                        f"{b['tight_adjacency_bound']}/{b['reck_mesh_optimum']}")
        if not (b["parameter_count_bound"] <= b["tight_adjacency_bound"]
                <= b["reck_mesh_optimum"] == 2 * n_ - 3):
            ok17 = False
        if n_ % 2 == 0 and (b["parameter_count_bound"] != n_ - 1
                            or b["tight_adjacency_bound"] != n_):
            ok17 = False
    res["⑰ 三口径界自洽：参数界 ≤ 紧界 ≤ Reck 最优(=2N−3)（含 216）"] = ok17

    # ⑱ 跨模块桥：浅调度重建 ≡ 平台 assemble_triangular_mesh（逐位一致）
    n_ = 10
    U_ = random_unitary(n_, seed=11)
    ops_, D_ = MMM.reck_triangular_mesh(U_)
    sched_sh, _d, _mx, _ok = schedule_shallow(ops_, D_, n_)
    res["⑱ 跨模块桥：浅调度重建 ≡ 平台 assemble_triangular_mesh（逐位一致）"] = bool(
        float(np.max(np.abs(schedule_unitary(sched_sh, n_) -
                            MMM.assemble_triangular_mesh(ops_, D_, n_)))) < 1e-13)

    if verbose:
        for k, v in res.items():
            print(f"[{'PASS' if v else 'FAIL'}] {k}")
        print("⑤ 明细：" + " · ".join(detail5))
        print("⑭ 明细：" + " · ".join(detail14))
        print("⑮ 明细：" + " · ".join(detail15))
        print("⑰ 明细：" + " · ".join(detail17))
    return bool(all(res.values()))


RED_LINE_DISCLOSURE = {
    "role": "D-121 = 时间复用架构的可编程酉实现（M4 延伸）：构造性通用时间表 + "
            "深度下界 + 「买元件数不买损耗」的机器判据。",
    "golden": "只用闭式/构造性：S_m 酉置换 · S^N=I · 2 模门酉性 · Givens 参数计数 "
              "⌈N(N−1)/2 / ⌊N/2⌋⌉ · 10^(−dB/10)；且时间表重建 ≡ 目标酉为**构造性实证**"
              "（非仿真拟合）。",
    "external_a_level": "BOREALIS_REF 复用 D-120 的 Nature 606, 75-81 (2022) "
                        "（doi:10.1038/s41586-022-04725-x）——仅引用架构/规模/报称参数，**不复算**数值。",
    "sovereignty": "C 级自主（纯 numpy + 平台 lda_l2/lda_qeda），零量子 SDK；LLM 不进判决路径。",
    "honest_boundary": "① 本模块是**架构-资源模型**（设计预算口径），非真机实测比对；"
                       "② 每轮次损耗为设计预算，非实测 PDK（属 D5 外部依赖）；"
                       "③ 与 Borealis 只比规模/架构/参数计数，不比数值（物理形态不同："
                       "CV GBS vs DV 被动 LOQC）；④ 深度下界为参数计数下界（不问硬件细节），"
                       "可达性由构造性时间表独立给出。",
}


if __name__ == "__main__":
    ok = run_selfchecks(verbose=True)
    print(f"temporal_mesh 自检：{'全 PASS' if ok else '有 FAIL'}")
