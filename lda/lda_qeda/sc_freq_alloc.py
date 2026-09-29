"""D-142 · 超导征程 S5 · G6：频率避撞分配器（吃狗粮）。

S5 首刀 G1（D-137）把 N 个 qubit 的读出/控制路由到焊盘；紧接着的硬卡点不是几何，而是
**频率规划**：53+ / 千比特级阵列里，若两 qubit 频率靠太近（"碰撞"）或落到 ZZ 共振极点
（|Δ|≈|α|）上，残余静态 ZZ 会击穿 spectator。S4 的 `crosstalk_budget` 已能**给定** EJ_list
算全 pair ZZ；G6 补上**怎么定** EJ_list（= 频率分配），使杂散 ZZ 落预算内。

方法（纯 numpy/标准库组合优化，零量子 SDK）：
  • 约束：任意两 qubit |Δf| ≥ min_detune（防碰撞）；最近邻 |Δf| ≥ nn_detune（CR 门工作区
    & ZZ 抑制）；任意两 qubit |‖Δf‖ − |α|| ≥ resonance_avoid（远离 ζ_zz 极点 Δ=−α）。
  • `allocate_distinct`：确定性阶梯贪心（逐 qubit 取满足约束的最小频率）。
  • `allocate_reuse`：二维模着色 tone=(r+2c) mod M（远隔 qubit 复用频率，规模扩到千比特级）。
  • `freq_zz_report`：把分配后的频率反推 E_J（Koch 逆式）→ 调 S4.crosstalk_budget 复核
    全 pair 杂散 ZZ ≤ 上限 ⇒ 频率规划与器件物理**闭环**。
  • `frequency_capacity`：带宽/步长 → 可容纳的不碰撞频率数（闭式）。

诚实边界：f/E_J 为设计参数；σ_zz 为残余 ZZ 估计（真实器件用 echoed-CR 抵消）；本模块只做
**设计预算**，不做量子线路仿真（属 B 类外部依赖）。频率复用于**远隔** qubit（真实芯片实践）。
红线：纯几何 + 闭式物理、零量子 SDK、LLM 不进判决路径、阈值为设计规则。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from lda_qeda import sc_readout as S4
from lda_solver import coupler_solver as CS

# 频率规划阈值（设计参数 · 可覆盖 · 非实测 golden）
DEFAULT_FREQ_LIMITS = {
    "min_detune_mhz": 10.0,        # 任意两 qubit 最小失谐（防碰撞）
    "nn_detune_mhz": 40.0,         # 最近邻最小失谐（CR 工作区 & ZZ 抑制）
    "resonance_avoid_mhz": 30.0,   # |Δ| 须远离 |α|（ZZ 极点 Δ=−α）
    "collision_win_mhz": 5.0,      # |Δ| < 此值 ⇒ 判为碰撞
    "alpha_mhz": 250.0,            # 非谐性幅度（|α|=E_C·1000，与 S4 同口径）
}
DEFAULT_PLAN = {
    "f_min_ghz": 4.0,              # 频带下限
    "step_mhz": 100.0,             # 阶梯步长（须 > 2·resonance_avoid 且避极点）
    "band_ghz": 2.0,               # 单频带宽度（distinct 模式容量）
    "reuse_tones": 4,              # 复用模式 tone 数 M
    "reuse_tone_step_mhz": 100.0,  # 复用模式 tone 间距
}

RED_LINE_DISCLOSURE = {
    "role": "D-142 = 超导征程 S5 · G6：频率避撞分配器——给定阵列拓扑，确定性分配 qubit "
            "频率（防碰撞 + 避 ZZ 共振极点），并用 S4 闭式 ZZ 复核，把 S4 的「给定频率算"
            "串扰」补成「怎么定频率」的闭环",
    "limits": "min_detune/nn_detune/resonance_avoid/collision_win 为**设计规则 · 可覆盖 · "
              "非实测 golden**（真实器件频率容差/退相干为实测项，属 B 类外部依赖）",
    "method": "distinct=阶梯贪心（小 N 不碰撞）；reuse=二维模着色 tone=(r+2c) mod M"
              "（远隔 qubit 复用频率，规模扩到千比特级）",
    "physics": "复核用 S4 全 pair 静态 ZZ ζ_zz=2J²α/(α²−Δ²)（Blais 2004 色散同口径）"
               "＋ coupler_solver 严格 J（确定性锚）；E_J 由频率经 Koch 逆式推得",
    "red_line": "纯几何 + 闭式物理（标准库 + 平台 numpy 物理锚）、零量子 SDK、"
                "LLM 不进判决路径、阈值为设计规则",
}
ROLE = RED_LINE_DISCLOSURE["role"]


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _limits(params: Optional[Dict]) -> Dict:
    lim = dict(DEFAULT_FREQ_LIMITS)
    pl = dict(DEFAULT_PLAN)
    p = dict(params or {})
    for k in lim:
        if k in p:
            lim[k] = float(p[k])
    for k in pl:
        if k in p:
            pl[k] = float(p[k])
    return {"lim": lim, "plan": pl}


def _topology(params: Optional[Dict]):
    return S4._array_topology(params)


def detect_collisions(freqs_mhz: List[float], win_mhz: float) -> List[Dict]:
    """碰撞检测：返回 |Δf| < win 的 pair 列表。"""
    out = []
    for i in range(len(freqs_mhz)):
        for j in range(i + 1, len(freqs_mhz)):
            d = abs(freqs_mhz[i] - freqs_mhz[j])
            if d < win_mhz - 1e-9:
                out.append({"pair": [i, j], "delta_mhz": float(d)})
    return out


def check_plan(freqs_mhz: List[float], edges: List[Tuple[int, int]],
               params: Optional[Dict] = None) -> Dict:
    """频率规划校验：**近邻/相邻**对的碰撞 + 最小失谐 + 最近邻失谐 + 共振极点回避。

    约束只施加在**相互作用范围**内（相邻耦合边 ∪ 几何距 ≤ interact_radius）：远隔 qubit
    允许复用频率（真实芯片实践），其残余 ZZ 由全 pair 闭式复核兜底（见 stray_zz_max）。
    """
    lim = _limits(params)["lim"]
    p = dict(params or {})
    alpha = abs(float(lim["alpha_mhz"]))
    edge_set = {tuple(sorted(e)) for e in edges}
    pos, _ = _topology(p)
    pitch_x = float(p.get("pitch_x", 22.0))
    radius = float(p.get("interact_radius_um", 1.5 * pitch_x))
    min_detune = float(lim["min_detune_mhz"])
    nn_detune = float(lim["nn_detune_mhz"])
    avoid = float(lim["resonance_avoid_mhz"])
    win = float(lim["collision_win_mhz"])

    N = len(freqs_mhz)
    collisions = []
    detune_viol = []
    nn_viol = []
    resonance_hits = []
    min_pair = float("inf")
    min_nn = float("inf")
    for i in range(N):
        for j in range(i + 1, N):
            if i in pos and j in pos:
                d = math.hypot(pos[i][0] - pos[j][0], pos[i][1] - pos[j][1])
            else:
                d = float("inf")
            adjacent = tuple(sorted((i, j))) in edge_set
            if not (adjacent or d <= radius + 1e-9):
                continue
            dd = abs(freqs_mhz[i] - freqs_mhz[j])
            min_pair = min(min_pair, dd)
            if dd < win - 1e-9:
                collisions.append({"pair": [i, j], "delta_mhz": float(dd)})
            if dd < min_detune - 1e-9:
                detune_viol.append({"pair": [i, j], "delta_mhz": float(dd)})
            if adjacent:
                min_nn = min(min_nn, dd)
                if dd < nn_detune - 1e-9:
                    nn_viol.append({"pair": [i, j], "delta_mhz": float(dd)})
            if abs(dd - alpha) < avoid - 1e-9:
                resonance_hits.append({"pair": [i, j], "delta_mhz": float(dd),
                                       "dist_to_alpha_mhz": float(abs(dd - alpha))})

    ok = not (collisions or detune_viol or nn_viol or resonance_hits)
    return {
        "ok": ok,
        "n_qubits": N,
        "interact_radius_um": radius,
        "min_pair_detune_mhz": (None if min_pair == float("inf") else float(min_pair)),
        "min_nn_detune_mhz": (None if min_nn == float("inf") else float(min_nn)),
        "collisions": collisions, "n_collisions": len(collisions),
        "detune_violations": detune_viol, "nn_violations": nn_viol,
        "resonance_hits": resonance_hits, "n_resonance_hits": len(resonance_hits),
        "alpha_mhz": alpha,
        "limits": lim,
    }


def _freqs_to_ej(freqs_ghz: List[float], ec_ghz: float) -> List[float]:
    """Koch 逆式：f01 = sqrt(8·E_J·E_C) − E_C ⇒ E_J = (f + E_C)²/(8·E_C)。"""
    return [((f + ec_ghz) ** 2) / (8.0 * ec_ghz) for f in freqs_ghz]


def _candidate_ok(f: float, assigned: List[float], assigned_neighbors: List[float],
                  lim: Dict) -> bool:
    alpha = abs(float(lim["alpha_mhz"]))
    for fj in assigned:
        d = abs(f - fj)
        if d < float(lim["min_detune_mhz"]) - 1e-9:
            return False
        if abs(d - alpha) < float(lim["resonance_avoid_mhz"]) - 1e-9:
            return False
    for fj in assigned_neighbors:
        if abs(f - fj) < float(lim["nn_detune_mhz"]) - 1e-9:
            return False
    return True


def allocate_distinct(params: Optional[Dict] = None) -> Dict:
    """确定性阶梯贪心：逐 qubit 取满足约束的最小频率（distinct 模式）。"""
    cfg = _limits(params)
    lim, pl = cfg["lim"], cfg["plan"]
    p = dict(params or {})
    rows, cols = int(p.get("rows", 2)), int(p.get("cols", 2))
    N = rows * cols
    pos, edges = _topology(p)
    nbrs: Dict[int, List[int]] = {i: [] for i in range(N)}
    for (a, b) in edges:
        nbrs[a].append(b)
        nbrs[b].append(a)
    f_min = float(pl["f_min_ghz"]) * 1000.0
    step = float(pl["step_mhz"])
    band = float(pl["band_ghz"]) * 1000.0
    K = int(band // step)
    freqs: List[float] = [0.0] * N
    assigned: Dict[int, float] = {}
    feasible = True
    for qid in range(N):
        nn_assigned = [assigned[nb] for nb in nbrs[qid] if nb in assigned]
        chosen = None
        for k in range(K + 1):
            f = f_min + k * step
            if _candidate_ok(f, list(assigned.values()), nn_assigned, lim):
                chosen = f
                break
        if chosen is None:
            feasible = False
            chosen = f_min + qid * step        # 退化回填（仍报告 infeasible）
        freqs[qid] = chosen
        assigned[qid] = chosen
    return {"mode": "distinct", "freqs_mhz": freqs, "feasible": feasible,
            "step_mhz": step, "band_mhz": band, "capacity": K + 1,
            "n_qubits": N, "edges": edges}


def allocate_reuse(params: Optional[Dict] = None) -> Dict:
    """二维模着色：tone=(r+2c) mod M（远隔 qubit 复用频率，扩到千比特级）。"""
    cfg = _limits(params)
    pl = cfg["plan"]
    p = dict(params or {})
    rows, cols = int(p.get("rows", 2)), int(p.get("cols", 2))
    N = rows * cols
    _pos, edges = _topology(p)
    M = max(2, int(pl["reuse_tones"]))
    tone_step = float(pl["reuse_tone_step_mhz"])
    f_min = float(pl["f_min_ghz"]) * 1000.0
    freqs: List[float] = []
    tones: List[int] = []
    for r in range(rows):
        for c in range(cols):
            t = (r + 2 * c) % M
            tones.append(t)
            freqs.append(f_min + t * tone_step)
    return {"mode": "reuse", "freqs_mhz": freqs, "tones": tones, "n_tones": M,
            "tone_step_mhz": tone_step, "feasible": True,
            "n_qubits": N, "edges": edges}


def frequency_capacity(band_ghz: float, step_mhz: float) -> int:
    """单频带可容纳的不碰撞频率数（闭式）。"""
    if step_mhz <= 0:
        return 1
    return int(band_ghz * 1000.0 // step_mhz) + 1


# ---------------------------------------------------------------------------
# 规模化的杂散 ZZ 复核（向量化；与 S4 逐对闭式同口径）
# ---------------------------------------------------------------------------
def stray_zz_max(params: Optional[Dict] = None,
                 freqs_mhz: Optional[List[float]] = None) -> Dict:
    """向量化全 pair 杂散 ZZ（仅非耦合对）。

    规模优化：**避开** S4 逐边 solve_coupler 的 O(N)·eigh（N=1000 时 ~160s）；改用
    • 代表近邻 J：coupling_analytic 闭式（= S4 双验证的**解析臂**，与 solve_coupler
      严格对角化 rel≤5% 同源）；
    • 非最近邻 J_bg = J_nn·(pitch/d)³（与 S4 同式）；
    • ζ_zz = 2J²α/(α²−Δ²)（与 S4 同式）。
    与 S4.crosstalk_budget 在中小 N 交叉复核（见 run_selfchecks）。
    """
    p = dict(params or {})
    rows, cols = int(p.get("rows", 2)), int(p.get("cols", 2))
    N = rows * cols
    ec = float(p.get("E_C", 0.25))
    alpha_mhz = -ec * 1000.0
    cc = float(p.get("Cc", 0.007))
    pitch = float(p.get("pitch_x", 22.0))
    pos, edges = _topology(p)
    if freqs_mhz is None:
        ej_list = p.get("EJ_list") or [18.0 + 0.3 * i for i in range(N)]
        freqs_mhz = [CS.koch_f01(float(ej), ec) * 1000.0 for ej in ej_list]
    ej_ref = float(p.get("EJ_ref") or
                   (float(np.median(p["EJ_list"])) if p.get("EJ_list") else 18.0))
    j_nn_rep = abs(float(CS.coupling_analytic(ej_ref, ec, ej_ref, ec, cc, 1.0, 1.0)))

    f = np.asarray(freqs_mhz, dtype=float)
    x = np.array([pos[i][0] for i in range(N)], dtype=float)
    y = np.array([pos[i][1] for i in range(N)], dtype=float)
    d = np.sqrt((x[:, None] - x[None, :]) ** 2 + (y[:, None] - y[None, :]) ** 2)
    d = np.where(d < 1e-9, 1.0, d)
    J = j_nn_rep * (pitch / d) ** 3.0
    mask = np.ones((N, N), dtype=bool)
    np.fill_diagonal(mask, False)
    for (a, b) in edges:                                     # 排除最近邻对
        mask[a, b] = False
        mask[b, a] = False
    delta = f[:, None] - f[None, :]
    denom = alpha_mhz * alpha_mhz - delta * delta
    denom = np.where(np.abs(denom) < 1e-12, np.nan, denom)
    zeta = np.abs(2.0 * (J * 1000.0) ** 2 * alpha_mhz / denom)
    zeta = np.nan_to_num(zeta, nan=0.0)
    stray = float(np.max(np.where(mask, zeta, 0.0)))
    return {"max_stray_zz_mhz": stray, "j_nn_rep_ghz": j_nn_rep,
            "zz_stray_limit_mhz": S4.ZZ_STRAY_LIMIT_MHZ,
            "n_pairs": N * (N - 1) // 2, "method": "vectorized-closed-form"}


# ---------------------------------------------------------------------------
# 顶层：规划（选模式 + 校验 + S4 闭式 ZZ 复核）
# ---------------------------------------------------------------------------
def plan(params: Optional[Dict] = None) -> Dict:
    """频率规划总入口：选模式 → 分配 → 校验 → ZZ 复核。

    mode 选择：N ≤ distinct 容量 ⇒ distinct；否则 reuse。
    ZZ 复核：小 N（≤ 阈值）走 S4.crosstalk_budget（逐边 solve_coupler + 全 pair，权威）；
    大 N 走向量化 stray_zz_max（同闭式，避开 O(N)·eigh 的规模瓶颈）。
    返回 verdict（规划 ok 且 杂散 ZZ ≤ 上限 ⇒ ACCEPT）。
    """
    cfg = _limits(params)
    pl = cfg["plan"]
    p = dict(params or {})
    rows, cols = int(p.get("rows", 2)), int(p.get("cols", 2))
    N = rows * cols
    cap = frequency_capacity(float(pl["band_ghz"]), float(pl["step_mhz"]))
    auto = "distinct" if N <= cap else "reuse"
    mode = str(p.get("mode", auto))
    alloc = allocate_distinct(p) if mode == "distinct" else allocate_reuse(p)
    freqs_mhz = alloc["freqs_mhz"]
    edges = alloc["edges"]
    chk = check_plan(freqs_mhz, edges, p)

    # 反推 E_J → ZZ 复核
    ec_ghz = float(p.get("E_C", 0.25))
    ej_list = _freqs_to_ej([fm / 1000.0 for fm in freqs_mhz], ec_ghz)
    full_threshold = int(p.get("full_zz_threshold", 25))
    if N <= full_threshold:
        xt = S4.crosstalk_budget({**p, "EJ_list": ej_list})
        zz_max = xt["max_stray_zz_mhz"]
        zz_limit = xt["zz_stray_limit_mhz"]
        zz_path = "s4-full"
    else:
        sr = stray_zz_max({**p, "EJ_list": ej_list}, freqs_mhz)
        zz_max = sr["max_stray_zz_mhz"]
        zz_limit = sr["zz_stray_limit_mhz"]
        zz_path = sr["method"]
    zz_ok = bool(zz_max <= zz_limit)
    verdict = "ACCEPT" if (chk["ok"] and zz_ok) else "REJECT"
    return {
        "verdict": verdict,
        "mode": alloc["mode"], "auto_mode": auto,
        "n_qubits": N, "capacity_distinct": cap,
        "feasible": alloc.get("feasible", True),
        "freqs_mhz": freqs_mhz,
        "freq_min_mhz": float(min(freqs_mhz)), "freq_max_mhz": float(max(freqs_mhz)),
        "n_distinct_freqs": len(set(round(fm, 6) for fm in freqs_mhz)),
        "check": chk,
        "ej_list_ghz": ej_list,
        "max_stray_zz_mhz": zz_max,
        "zz_stray_limit_mhz": zz_limit,
        "zz_path": zz_path,
        "zz_ok": zz_ok,
        "note": ("频率分配（distinct 阶梯贪心 / reuse 二维模着色）+ 全 pair 闭式 ZZ 复核。"
                 "阈值为设计规则；σ_zz 为残余 ZZ 估计；不做量子线路仿真（B 类外部依赖）。"
                 "LLM 不进判决路径。"),
    }


# ---------------------------------------------------------------------------
# 自检（常驻断言：合法 ACCEPT；各违规 REJECT）
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    ok = True
    msgs: List[Tuple[str, bool]] = []

    def chk(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        msgs.append((name, bool(cond)))

    # ① 2×2 distinct 规划 ACCEPT
    pl22 = plan({"rows": 2, "cols": 2})
    chk("① 2×2 distinct 规划 ACCEPT（无碰撞 + 无共振 + 杂散 ZZ ≤ 上限）",
        pl22["verdict"] == "ACCEPT" and pl22["mode"] == "distinct")

    # ② 3×3 distinct 规划 ACCEPT
    pl33 = plan({"rows": 3, "cols": 3})
    chk("② 3×3 distinct 规划 ACCEPT", pl33["verdict"] == "ACCEPT")

    # ③ 碰撞检测：全同频 ⇒ 检出碰撞
    coll = detect_collisions([5000.0] * 4, 5.0)
    chk("③ detect_collisions：全同频 ⇒ 6 对碰撞",
        len(coll) == 6)

    # ④ 全同频规划 ⇒ REJECT（碰撞）
    same = check_plan([5000.0] * 4, [(0, 1), (1, 2), (2, 3)], {"resonance_avoid_mhz": 30.0})
    chk("④ 全同频 ⇒ check_plan ok=False（碰撞）",
        same["ok"] is False and same["n_collisions"] == 6)

    # ⑤ 共振极点：两频相距 = |α| ⇒ 命中共振
    res = check_plan([4000.0, 4250.0], [(0, 1)], {"resonance_avoid_mhz": 30.0})
    chk("⑤ 频距=|α|=250 ⇒ 命中 ZZ 共振极点（ok=False）",
        res["ok"] is False and res["n_resonance_hits"] >= 1)

    # ⑥ 最近邻失谐不足 ⇒ nn_violations
    nnv = check_plan([4000.0, 4020.0], [(0, 1)], {"nn_detune_mhz": 40.0,
                                                  "min_detune_mhz": 10.0})
    chk("⑥ 最近邻失谐 20 < nn_detune 40 ⇒ nn_violations",
        len(nnv["nn_violations"]) >= 1)

    # ⑦ 规模 7×8=56（超 distinct 容量）⇒ 自动切 reuse，规划 ACCEPT
    pl56 = plan({"rows": 7, "cols": 8})
    chk("⑦ 7×8=56 超 distinct 容量 ⇒ 自动 reuse 且 ACCEPT",
        pl56["mode"] == "reuse" and pl56["verdict"] == "ACCEPT")

    # ⑧ 千比特级 32×32=1024 reuse 规划 ACCEPT（杂散 ZZ ≤ 上限）
    plbig = plan({"rows": 32, "cols": 32})
    chk("⑧ 32×32=1024 reuse 规划 ACCEPT", plbig["verdict"] == "ACCEPT")

    # ⑨ 复用 tone 数 = M；全同 tone 的 qubit 图距 ≥2（无最近邻同频）
    au = allocate_reuse({"rows": 4, "cols": 4})
    tones = au["tones"]
    edge_ok = all(tones[a] != tones[b] for (a, b) in au["edges"])
    chk("⑨ 复用 tone：最近邻必不同 tone（4×4 模着色无相邻同频）", edge_ok)

    # ⑩ 容量闭式：band 2GHz / step 100MHz ⇒ 21 个不碰撞频率
    chk("⑩ frequency_capacity(2.0GHz,100MHz)=21",
        frequency_capacity(2.0, 100.0) == 21)

    # ⑪ E_J 反推自洽：Koch 正逆往返
    ej = _freqs_to_ej([5.0], 0.25)[0]
    chk("⑪ E_J 反推自洽（Koch 正逆往返 rel<1e-9）",
        abs(CS.koch_f01(ej, 0.25) - 5.0) < 1e-9)

    # ⑫ S4 ZZ 复核字段齐备 + verdict 一致
    chk("⑫ 规划字段齐备（verdict/mode/freqs/zz_ok/max_stray_zz_mhz/zz_path）",
        all(k in pl22 for k in ("verdict", "mode", "freqs_mhz", "zz_ok",
                                 "max_stray_zz_mhz", "zz_path"))
        and pl22["zz_ok"] is True)

    # ⑬ 向量化 ZZ ↔ S4 逐对 ZZ 交叉复核（3×3，rel ≤ 20%）
    al33 = allocate_distinct({"rows": 3, "cols": 3})
    ej33 = _freqs_to_ej([fm / 1000.0 for fm in al33["freqs_mhz"]], 0.25)
    vec = stray_zz_max({"rows": 3, "cols": 3, "EJ_list": ej33}, al33["freqs_mhz"])
    s4v = S4.crosstalk_budget({"rows": 3, "cols": 3, "EJ_list": ej33})
    rel = abs(vec["max_stray_zz_mhz"] - s4v["max_stray_zz_mhz"]) / (
        s4v["max_stray_zz_mhz"] + 1e-12)
    chk("⑬ 向量化 ZZ ↔ S4 逐对 ZZ 交叉复核（3×3 rel ≤ 20%，方法学独立两路）",
        rel <= 0.20)

    if verbose:
        for n, c in msgs:
            print(f"  [{'PASS' if c else 'FAIL'}] {n}")
    return ok
