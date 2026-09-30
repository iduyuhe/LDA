"""LDA ecore · E7 寄生提取与后仿（IR drop / sneak path）（D-157）。

**为什么需要它（E7 逼出的平台接缝）**：
E1–E6 的所有电路仿真都建立在 **理想互连** 假设上（E2/E3 的交叉阵列把行线/列线当作
零阻理想节点）。真实芯片里行/列线是**有阻导线**：电流沿线的累积欧姆压降（**IR drop**）
会衰减交叉点实际看到的电压，且未选通的行/列会通过阵列拓扑形成**旁路电流（sneak path）**。
二者都是**随规模放大**的架构约束（IR drop ∝ N²），是「电路级模型 → 可流片架构」之间
必须补齐的一环。平台**此前无任何寄生注入后仿能力**（`parasitic_rc.py` 只做光子侧
几何量级估算，不注入电路仿真器）。

**本模块做什么**：
  1. **导线 RC 闭式提取**：从 E6 版图几何（节距 / 线宽 / 线长）按 **教科书闭式**
     `R = ρ·L/(W·t)`（等价 `R = R□·L/W`）与平行板电容 `C = ε₀ε_r·A/d` 提取每段寄生；
  2. **阵列 R 梯网络装配**：行线 = M 个抽头节点串联 `R_row_seg`，列线 = N 个抽头节点
     串联 `R_col_seg`，交叉点 = 电导 `g_ij`（E2 晶体管模型给出）；接 `mna.Circuit` 求解；
  3. **理想 golden**：`I_j = Σ_i g_ij·V_i`（解析闭式，纯 numpy）——R=0 的网络必须**精确**复现它；
  4. **IR drop 报告**：有阻 vs 理想互连的列电流相对误差 + 沿线电压剖面；
  5. **sneak 报告**：half-select **浮空**方案（驱动 row i0、读 col j0、其余行/列浮空）
     下「本应只有选通单元贡献」的旁路电流；
  6. **Elmore 延迟**闭式（`R·C/2` 极限）——互连时间常数/带宽量级。

🔴 **诚实边界**：
  - 工艺参数（ρ_Cu / 金属厚度 / ILD 介电常数与厚度 / 方块电阻）为**公开典型量级**，
    **非 Foundry PDK**；层规与真实寄生 deck 属 D5 外部依赖。
  - 提取为**一阶几何闭式**（无 3D 场解/无截面场提取），后仿为 **DC**（电容只进 Elmore
    时间常数量级，不进网络的 DC 解）。
  - 网络里的 `r_leak` 是**数值钉扎**（防浮空节点使矩阵奇异），**非物理漏电声明**。
  - 本引擎**非签核级 SPICE**；结论用于架构洞察（IR drop / sneak 的规模律），不宣称签核精度。
  - 纯 numpy（复用 E1 `mna`）/ LLM 不进判决路径 / 零商业 EDA 依赖。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import layout as LY
from .mna import Circuit

# ---------------------------------------------------------------------------
# 工艺参数（公开典型量级 · 非 PDK · 可覆盖）
# ---------------------------------------------------------------------------
ELEC_PROCESS: Dict[str, float] = {
    "rho_cu_ohm_um": 1.68e-2,     # Cu 电阻率（= 1.68e-8 Ω·m）
    "t_m1_um": 0.20,              # M1 金属厚度
    "t_m2_um": 0.30,              # M2 金属厚度
    "eps0_fF_per_um": 8.854e-3,   # 真空介电常数（fF/µm）
    "eps_r_ild": 3.9,             # ILD 相对介电常数（SiO₂）
    "ild_um": 0.30,               # 层间介质厚度
    "couple_factor": 0.5,         # 侧向耦合相对对地电容的经验系数（一阶）
    "r_leak_ohm": 1.0e9,          # **数值钉扎**（防浮空奇异）· 非物理漏电
}

PARASITIC_DISCLOSURE = {
    "role": "E7 = 寄生提取与后仿（IR drop / sneak path）· 从 E6 版图提 RC 注入 MNA 阵列",
    "process": "ρ_Cu / 金属厚度 / ILD ε_r 与厚度 = **公开典型量级占位（非 Foundry PDK）**",
    "extract": "一阶几何闭式：R=ρ·L/(W·t)（≡R□·L/W）· C=ε₀ε_r·A/d；**无 3D 场解/无截面提取**",
    "sim": "DC 后仿（mna 求解）；电容仅进 Elmore 时间常数量级，不进 DC 网络",
    "leak": "网络内 r_leak 是**数值钉扎**（防浮空节点奇异），**非物理漏电声明**",
    "red_line": "纯 numpy（复用 E1 mna）· LLM 不进判决路径 · 零商业 EDA 依赖 · 非签核级 SPICE",
}

# ---------------------------------------------------------------------------
# ① 导线 RC 闭式提取
# ---------------------------------------------------------------------------
def sheet_resistance(rho_ohm_um: float, t_um: float) -> float:
    """方块电阻 R□ = ρ/t（Ω/□）。"""
    if t_um <= 0:
        raise ValueError("金属厚度须 > 0")
    return float(rho_ohm_um) / float(t_um)


def wire_resistance(length_um: float, width_um: float,
                    rho_ohm_um: float, t_um: float) -> float:
    """导线电阻**教科书闭式** R = ρ·L/(W·t)（Ω）。"""
    if width_um <= 0 or t_um <= 0:
        raise ValueError("线宽/厚度须 > 0")
    return float(rho_ohm_um) * float(length_um) / (float(width_um) * float(t_um))


def cap_per_length(width_um: float, eps_r: float, ild_um: float,
                   eps0_fF_per_um: float) -> float:
    """单位长度对地平行板电容 C' = ε₀·ε_r·W/d（fF/µm）。"""
    if ild_um <= 0:
        raise ValueError("ILD 厚度须 > 0")
    return float(eps0_fF_per_um) * float(eps_r) * float(width_um) / float(ild_um)


def wire_capacitance(length_um: float, width_um: float,
                     proc: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """导线电容（fF）：对地 + 两侧耦合（一阶经验系数）。"""
    p = dict(ELEC_PROCESS)
    if proc:
        p.update(proc)
    c_pl = cap_per_length(width_um, p["eps_r_ild"], p["ild_um"], p["eps0_fF_per_um"])
    c_gnd = c_pl * float(length_um)
    c_couple = c_gnd * float(p["couple_factor"]) * 2.0
    return {"c_per_len_fF_per_um": c_pl, "c_ground_fF": c_gnd,
            "c_couple_fF": c_couple, "c_total_fF": c_gnd + c_couple}


def elmore_delay(n_seg: int, r_seg: float, c_seg: float) -> float:
    """均匀 R 梯的 **Elmore 延迟** = Σ_k (k·r)·c = r·c·n(n+1)/2（单位同 r·c）。

    闭式极限：n→∞ 时 → R_total·C_total/2（分布式 RC 线经典结果）。
    """
    if n_seg <= 0:
        return 0.0
    return float(r_seg) * float(c_seg) * n_seg * (n_seg + 1) / 2.0


# ---------------------------------------------------------------------------
# ② 从 E6 版图几何提取阵列寄生
# ---------------------------------------------------------------------------
def array_parasitics(n: int, m: int,
                     cell_params: Optional[Dict[str, float]] = None,
                     proc: Optional[Dict[str, float]] = None) -> Dict:
    """由 E6 的阵列版图几何（节距/线宽/线长）提取行线/列线**每段**寄生。

    节距即每段长度（相邻抽头间距）；行线在 M1、列线在 M2。
    """
    p = dict(LY.DEFAULT_CELL_PARAMS)
    if cell_params:
        p.update(cell_params)
    pr = dict(ELEC_PROCESS)
    if proc:
        pr.update(proc)
    px, py = p["pitch_x_um"], p["pitch_y_um"]
    fW, fH = LY.array_footprint(n, m, p)

    r_row_seg = wire_resistance(px, p["row_w_um"], pr["rho_cu_ohm_um"], pr["t_m1_um"])
    r_col_seg = wire_resistance(py, p["col_w_um"], pr["rho_cu_ohm_um"], pr["t_m2_um"])
    c_row_seg = wire_capacitance(px, p["row_w_um"], pr)["c_total_fF"]
    c_col_seg = wire_capacitance(py, p["col_w_um"], pr)["c_total_fF"]

    n_row_seg, n_col_seg = max(m - 1, 0), max(n - 1, 0)
    R_row, R_col = r_row_seg * n_row_seg, r_col_seg * n_col_seg
    C_row, C_col = c_row_seg * n_row_seg, c_col_seg * n_col_seg
    return {
        "n": n, "m": m,
        "footprint_um": [round(fW, 4), round(fH, 4)],
        "r_row_seg_ohm": r_row_seg, "r_col_seg_ohm": r_col_seg,
        "c_row_seg_fF": c_row_seg, "c_col_seg_fF": c_col_seg,
        "R_row_total_ohm": R_row, "R_col_total_ohm": R_col,
        "C_row_total_fF": C_row, "C_col_total_fF": C_col,
        "tau_row_s": elmore_delay(n_row_seg, r_row_seg, c_row_seg) * 1e-15,
        "tau_col_s": elmore_delay(n_col_seg, r_col_seg, c_col_seg) * 1e-15,
        "sheet_r_m1_ohm_sq": sheet_resistance(pr["rho_cu_ohm_um"], pr["t_m1_um"]),
        "process": pr,
    }


# ---------------------------------------------------------------------------
# ③ 阵列 R 梯网络（MNA）
# ---------------------------------------------------------------------------
def ideal_column_currents(g: np.ndarray, v_in: Sequence[float]) -> np.ndarray:
    """**解析 golden**：理想互连（全零阻、列节点虚地）下的列电流 I_j = Σ_i g_ij·V_i。"""
    G = np.asarray(g, dtype=float)
    v = np.asarray(v_in, dtype=float)
    if G.ndim != 2 or G.shape[0] != v.shape[0]:
        raise ValueError("g 形状 (n,m) 须与 v_in 长度 n 一致")
    return G.T @ v


def build_network(g: np.ndarray, r_row_seg: float, r_col_seg: float,
                  v_in: Sequence[float], mode: str = "dot",
                  sel: Optional[Tuple[int, int]] = None,
                  proc: Optional[Dict[str, float]] = None
                  ) -> Tuple[Circuit, Dict]:
    """装配阵列 R 梯网络（行线/列线分段串联 R + 交叉点电导）。

    mode:
      · 'dot'   —— 所有行驱动 v_in[i]；每列经 **0 V 电流表**（理想 TIA 虚地）接地 ⇒ 读列电流；
      · 'sneak' —— 仅 row sel[0] 驱动 v_in[sel[0]]；仅 col sel[1] 经电流表接地；
                   其余行/列**浮空**（half-select 浮空方案）+ 数值钉扎。
    R=0 时**不插**分段电阻（抽头合并为同一节点 = 理想互连）。
    """
    G = np.asarray(g, dtype=float)
    n, m = G.shape
    v = np.asarray(v_in, dtype=float)
    pr = dict(ELEC_PROCESS)
    if proc:
        pr.update(proc)
    r_leak = pr["r_leak_ohm"]

    row_ladder = r_row_seg > 0.0
    col_ladder = r_col_seg > 0.0
    row_off, row_span = 1, (n * m if row_ladder else n)
    col_off = row_off + row_span

    def rid(i: int, j: int) -> int:
        return row_off + (i * m + j if row_ladder else i)

    def cid(i: int, j: int) -> int:
        return col_off + (i * m + j if col_ladder else j)

    ckt = Circuit(f"xbar_{mode}")
    driven_rows = range(n) if mode == "dot" else [sel[0]]
    metered_cols = range(m) if mode == "dot" else [sel[1]]

    # 行线分段串联电阻
    if row_ladder:
        for i in range(n):
            for j in range(m - 1):
                ckt.resistor(rid(i, j), rid(i, j + 1), r_row_seg, f"rr{i}_{j}")
    # 列线分段串联电阻
    if col_ladder:
        for j in range(m):
            for i in range(n - 1):
                ckt.resistor(cid(i, j), cid(i + 1, j), r_col_seg, f"rc{i}_{j}")

    # 交叉点电导（跳过开路单元）
    for i in range(n):
        for j in range(m):
            if G[i, j] > 0.0:
                ckt.resistor(rid(i, j), cid(i, j), 1.0 / G[i, j], f"g{i}_{j}")

    # 行驱动 / 浮空钉扎
    for i in range(n):
        if i in driven_rows:
            ckt.vsource(rid(i, 0), 0, v[i], f"V{i}")
        elif mode == "sneak":
            ckt.resistor(rid(i, 0), 0, r_leak, f"leakR{i}")

    # 列电流表（0 V 虚地）/ 浮空钉扎
    for j in range(m):
        if j in metered_cols:
            ckt.vsource(cid(n - 1, j), 0, 0.0, f"I{j}")
        elif mode == "sneak":
            ckt.resistor(cid(n - 1, j), 0, r_leak, f"leakC{j}")

    meta = {"n": n, "m": m, "mode": mode,
            "rid": rid, "cid": cid,
            "meter_tags": [f"I{j}" for j in metered_cols],
            "row_tags": [f"V{i}" for i in driven_rows]}
    return ckt, meta


def solve_network(g: np.ndarray, r_row_seg: float, r_col_seg: float,
                  v_in: Sequence[float], mode: str = "dot",
                  sel: Optional[Tuple[int, int]] = None,
                  proc: Optional[Dict[str, float]] = None) -> Dict:
    """装配 + 求解，返回节点电压 / 列电流 / 行抽头电压。"""
    ckt, meta = build_network(g, r_row_seg, r_col_seg, v_in, mode=mode,
                              sel=sel, proc=proc)
    x = ckt.solve_dc()
    nv = ckt.node_voltages(x)
    ix = ckt.branch_currents(x)
    m_ = meta["m"]
    col_i = [float(ix[t]) for t in meta["meter_tags"]]
    row_v = [[nv[meta["rid"](i, j)] for j in range(m_)] for i in range(meta["n"])]
    return {"column_currents": col_i, "row_tap_voltages": row_v,
            "node_voltages": nv, "branch_currents": ix, "meta": meta}


# ---------------------------------------------------------------------------
# ④ IR drop 报告
# ---------------------------------------------------------------------------
def ir_drop_report(n: int, m: int, g: np.ndarray, v_in: Sequence[float],
                   r_row_seg: float, r_col_seg: float,
                   proc: Optional[Dict[str, float]] = None) -> Dict:
    """有阻互连 vs 理想互连：列电流相对误差 + 沿线电压剖面。"""
    ideal = ideal_column_currents(g, v_in)
    res = solve_network(g, r_row_seg, r_col_seg, v_in, mode="dot", proc=proc)
    meas = np.asarray(res["column_currents"], dtype=float)
    rel = np.abs(meas - ideal) / np.maximum(np.abs(ideal), 1e-300)
    prof = res["row_tap_voltages"]
    return {
        "n": n, "m": m,
        "ideal_column_currents": [float(v) for v in ideal],
        "measured_column_currents": [float(v) for v in meas],
        "rel_err_per_col": [float(v) for v in rel],
        "max_rel_err": float(np.max(rel)),
        "row0_tap_voltages": prof[0],
        "row_end_drop_v": float(v_in[0] - prof[0][-1]) if v_in[0] else 0.0,
        "r_row_seg": r_row_seg, "r_col_seg": r_col_seg,
    }


# ---------------------------------------------------------------------------
# ⑤ sneak path 报告（half-select 浮空方案）
# ---------------------------------------------------------------------------
def sneak_report(n: int, m: int, g: np.ndarray, v_read: float,
                 sel: Tuple[int, int],
                 proc: Optional[Dict[str, float]] = None) -> Dict:
    """half-select **浮空**方案：驱动 row sel[0]，读 col sel[1]，其余行/列浮空。

    理想（仅选通单元）读值 = `g[sel]·V_read`；实得 − 理想 = **旁路电流**（sneak）。
    """
    G = np.asarray(g, dtype=float)
    v = [0.0] * n
    v[sel[0]] = float(v_read)
    res = solve_network(G, 0.0, 0.0, v, mode="sneak", sel=sel, proc=proc)
    i_sel = float(res["column_currents"][0])          # 仅 sel[1] 有电流表
    i_ideal = float(G[sel[0], sel[1]] * v_read)
    return {
        "n": n, "m": m, "sel": list(sel),
        "i_ideal_a": i_ideal, "i_measured_a": i_sel,
        "sneak_a": i_sel - i_ideal,
        "sneak_ratio": (abs(i_sel - i_ideal) / abs(i_ideal)) if i_ideal else 0.0,
    }


# ---------------------------------------------------------------------------
# 自检（常驻断言）
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    msgs: List[Tuple[str, bool]] = []

    def chk(name: str, cond) -> bool:
        msgs.append((name, bool(cond)))
        return bool(cond)

    ok = True
    n, m = 4, 4
    rng = np.random.default_rng(7)
    G = 1.0e-3 * (1.0 + rng.random((n, m)))          # 单元电导 ~1-2 mS
    v_in = [0.1] * n

    # ① 导线 R 闭式：与 R□·L/W 等价（教科书两式一致）
    pr = ELEC_PROCESS
    r1 = wire_resistance(2.4, 0.4, pr["rho_cu_ohm_um"], pr["t_m1_um"])
    r2 = sheet_resistance(pr["rho_cu_ohm_um"], pr["t_m1_um"]) * (2.4 / 0.4)
    ok &= chk("① 导线 R = ρL/(Wt) ≡ R□·L/W", abs(r1 - r2) < 1e-15)

    # ② R=0 网络 ≡ 解析理想 golden（精确）
    ideal = ideal_column_currents(G, v_in)
    zero = np.asarray(solve_network(G, 0.0, 0.0, v_in)["column_currents"])
    ok &= chk("② R=0 网络 ≡ 解析 golden I_j=Σg_ij·V_i（精确）",
              np.max(np.abs(zero - ideal)) < 1e-15 * max(1.0, np.max(np.abs(ideal))))

    # ③ Elmore 闭式：n→∞ → R·C/2
    for ns in (1, 4, 16, 256):
        got = elmore_delay(ns, 1.0, 1.0)
        want = float(ns * (ns + 1)) / 2.0
        if abs(got - want) > 1e-9:
            ok &= chk(f"③ Elmore n={ns} = n(n+1)/2", False)
            break
    else:
        ok &= chk("③ Elmore 闭式 = n(n+1)/2（n→∞ → RC/2）", True)
    tau_inf = elmore_delay(200000, 1.0 / 200000, 1.0 / 200000)  # R总=C总=1
    ok &= chk("③b Elmore 大 n 极限 ≈ R·C/2", abs(tau_inf - 0.5) < 1e-3)

    # ④ IR drop：有阻必劣化，且随 R 单调增
    base = ir_drop_report(n, m, G, v_in, 0.5, 0.3)
    more = ir_drop_report(n, m, G, v_in, 2.0, 1.2)
    ok &= chk("④ 有阻互连列电流误差 > 0 且随 R 单调增",
              base["max_rel_err"] > 0.0 and more["max_rel_err"] > base["max_rel_err"])

    # ⑤ 行线电压沿线单调下降（物理）
    prof = base["row0_tap_voltages"]
    ok &= chk("⑤ 行线抽头电压沿线单调不增（IR drop 剖面）",
              all(prof[k] >= prof[k + 1] - 1e-12 for k in range(len(prof) - 1))
              and prof[-1] < prof[0])

    # ⑥ sneak：仅选通单元导通 ⇒ sneak ≡ 0（精确）；全导通 ⇒ sneak > 0
    G1 = np.zeros((n, m))
    G1[1, 1] = 1.2e-3
    s0 = sneak_report(n, m, G1, 0.1, (1, 1))
    ok &= chk("⑥ 仅选通单元导通 ⇒ sneak ≡ 0（精确）", abs(s0["sneak_a"]) < 1e-15)
    s1 = sneak_report(n, m, G, 0.1, (1, 1))
    ok &= chk("⑦ 全阵列导通 ⇒ sneak > 0（旁路电流存在）",
              s1["sneak_a"] > 0.0 and s1["sneak_ratio"] > 0.0)

    # ⑧ 规模律：IR drop 相对误差随 N 增（同 R）
    e8 = ir_drop_report(8, 8, 1.0e-3 * np.ones((8, 8)), [0.1] * 8, 0.5, 0.3)["max_rel_err"]
    e16 = ir_drop_report(16, 16, 1.0e-3 * np.ones((16, 16)), [0.1] * 16,
                         0.5, 0.3)["max_rel_err"]
    ok &= chk("⑧ IR drop 相对误差随阵列规模增（∝N² 量级）", e16 > e8 > 0.0)

    # ⑨ 从 E6 版图几何提寄生（与 layout 口径一致）
    ap = array_parasitics(n, m)
    ok &= chk("⑨ 阵列寄生提取：节距/线宽来自 E6 版图（footprint 一致）",
              abs(ap["footprint_um"][0] - LY.array_footprint(n, m)[0]) < 1e-6
              and ap["r_row_seg_ohm"] > 0 and ap["R_row_total_ohm"] > 0)

    if verbose:
        for nm, c in msgs:
            print(f"  [{'PASS' if c else 'FAIL'}] {nm}")
    return bool(ok)
