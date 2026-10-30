"""B3+ · 电源网格全域 IR 求解（真矩阵解，替代「均匀抽流一阶」）。

═══════════════════════════════════════════════════════════════════════════════
这一步补的是什么
───────────────────────────────────────────────────────────────────────────────
B3 的 `ir_drop_closed` 只有一条假设链：
    **单根轨** · **电流沿轨均匀抽走** · **只在末端看压降** ⇒ `V = I·R/2`。
真实的电源网格不是一根轨，而是 **M3 横条 × M4 竖条 + 每个交叉一个 via** 的**网**：
电流从少数几个电源凸点注入，分散到上千个负载点，走的是**二维路径**。
在这张网上，"最坏压降点" 既不在末端也不由 `R/2` 决定 —— 它由**拓扑 + 源位置 + 负载分布**
共同决定，只能靠解 `G·V = I` 得到。

本模块做三件事：
 ① **建网**：给出按 pitch 排布的 M3 横条 / M4 竖条 / 交叉 via 的双层网格（节点分 M3/M4 两套，
    由 via 电阻连接 —— 这样 via 电阻才真的进方程，而不是被吸收掉）。
 ② **求解**：两套**互相独立**的实现
    · `solve_reduced` —— 自己组装的电导矩阵 + Dirichlet 边界（源节点固定 Vdd）+ numpy 稠密解；
    · `solve_mna`     —— 复用仓内 E1 的 `mna.Circuit`（电阻 + 电压源 + 电流源，通用 MNA）。
    两者必须给出同一组节点电压（相对差 <1e-9）。这是「换一条算法路径得同一答案」，
    不是把同一个式子抄两遍。
 ③ **判据**：KCL 残差 / 能量恒等式 / 与 B3 一阶闭式的**退化关系** / 网格数增加必降最坏压降。

═══════════════════════════════════════════════════════════════════════════════
它和一阶闭式的关系（只有下面两条是可证的，别的都不许说）
───────────────────────────────────────────────────────────────────────────────
① **退化**：把网格退化成「单链 + 均匀抽流」，全域解必须**精确等于** B3 的
   `dsignoff.ir_drop_ladder` = `R·I·(n+1)/(2n)`，n→∞ 收敛到 `I·R/2`。
   这是本模块最强的一条 —— 通式必须退化为已实现的特例。
② **均匀 vs 点负载差 2×**：闭式 `I·R/2` 的前提是**沿轨均匀抽流**。若同一总电流
   是**集中在一个远端负载**上，单链解 = `I·R`，正好是闭式的 **2 倍**。
   所以「用 I·R/2 报 IR」在点负载工况下**系统性低估一半**，这与实现精度无关，
   是**假设**的问题。

🔴 反面：**不能说「网格压降一定大于闭式」**。本模块第一次试算就证伪了这条 ——
   8×8 网格的最坏压降只有单条轨闭式的 0.46×（因为 `ny` 条横条是**并联**的）。
   所以比值是**拓扑相关**的，本模块只**报告**它，不把它写成判据、也不给带宽。
   同理「加列数一定降压降」也不成立（加列同时把网格**拉宽**，远端更远）——
   实测 nx=8→16 反而升 27.8%。**能证伪的单调性只有下面两条**：
   · 线性：所有电阻 ×k ⇒ 所有压降 ×k（精确）；
   · 降低任一支路电阻（如 via 减半、加第二个源）⇒ 最坏压降**不升**（Rayleigh 单调性）。

═══════════════════════════════════════════════════════════════════════════════
诚实边界（必须随任何引用一起给）
───────────────────────────────────────────────────────────────────────────────
1. 🔴 **只解静态（DC）IR**：不含 `di/dt` 动态压降、不含 decap 电荷供给、不含封装/板级阻抗。
   真实签核的动态 IR 需要电流波形 + 片上电容模型，本项目都没有。
2. 🔴 **单角**：用 tt 的方块电阻；无 PVT/OCV 降额、无温度梯度（电阻不随位置变）。
3. 🔴 **负载是理想电流沉**：不建模标准单元的电压相关电流（真实单元在低压下电流会下降，
   即 IR 有自限效应 ⇒ 本模型**偏保守**）。
4. 🔴 **EM 用平均电流**：段电流是 DC 解出来的，不含峰值/开关噪声；`J_MAX` 仍是量级假设。
5. 🔴 **网格是规则网格**：真实 PG 有非均匀 pitch、宽窄混排、阻挡与打孔；本模块只做规则网格，
   不支持障碍与多源不等压。
6. 🔴 `claimable=False`，**净增 0 锚**（线性方程解 ⇒ 残差恒 0 ⇒ 门禁形态，E44）。
"""
from __future__ import annotations

import numpy as np

from . import dsignoff as SG
from .mna import Circuit

# ═══════════════════════════════════════════════════════════════════════════
# 默认工艺量（全部显式，便于外部替换；与 B3 同源）
# ═══════════════════════════════════════════════════════════════════════════
PG_PITCH_UM = 2.0          # 电源网格节距（比信号布线粗）
PG_WIDTH_UM = 0.5          # 电源条宽（比信号线宽）
R_VIA_OHM = 0.5            # 电源 via 电阻（比信号 via 小：孔更大/更多）
VDD_V = 1.0                # 标称电源电压（演示量级）
J_MAX_A_M2 = SG.J_MAX_A_M2  # 复用 B3 的电流密度上限（同一假设，不另造）

LAYER_H = "M3"             # 横条层
LAYER_V = "M4"             # 竖条层


# ═══════════════════════════════════════════════════════════════════════════
# ① 建网
# ═══════════════════════════════════════════════════════════════════════════
def build_grid(nx: int, ny: int, pitch_um: float = PG_PITCH_UM,
               width_um: float = PG_WIDTH_UM, via_r: float = R_VIA_OHM) -> dict:
    """规则电源网格：`nx` 列 M4 竖条 × `ny` 行 M3 横条，交叉处一个 via。

    节点分两套（`("h",i,j)` 在 M3、`("v",i,j)` 在 M4），via 电阻把同一交叉的两点连起来
    —— 这样 via 电阻**真的进方程**，而不是被并进金属段里。
    源固定在 `("h",0,0)`（左上角），返回结构供 `solve_*` 使用。
    """
    if nx < 1 or ny < 1:
        raise ValueError("网格至少 1×1")
    if nx * ny < 2:
        raise ValueError("网格退化：至少要有 2 个交叉点才有电阻通路")

    r_h = SG.RSH[LAYER_H] * pitch_um / width_um
    r_v = SG.RSH[LAYER_V] * pitch_um / width_um

    nodes: list = []
    idx: dict = {}
    for i in range(ny):
        for j in range(nx):
            for lay in ("h", "v"):
                idx[(lay, i, j)] = len(nodes)
                nodes.append((lay, i, j))

    edges: list = []          # [(a_idx, b_idx, R, kind, length_um)]
    for i in range(ny):
        for j in range(nx):
            if j + 1 < nx:
                edges.append((idx[("h", i, j)], idx[("h", i, j + 1)], r_h, "M3", pitch_um))
            if i + 1 < ny:
                edges.append((idx[("v", i, j)], idx[("v", i + 1, j)], r_v, "M4", pitch_um))
            if via_r > 0:
                edges.append((idx[("h", i, j)], idx[("v", i, j)], float(via_r), "VIA", 0.0))

    src = idx[("h", 0, 0)]
    return {"nodes": nodes, "idx": idx, "edges": edges, "source": src, "sources": [src],
            "nx": nx, "ny": ny, "pitch_um": pitch_um, "width_um": width_um,
            "r_per_seg": {"M3": r_h, "M4": r_v}, "via_r": via_r}


def build_ladder(n: int, r_seg: float) -> dict:
    """单链（1D）：节点 0..n，第 k 段电阻 `r_seg`。用于与 B3 的 `ir_drop_ladder` 对齐。"""
    if n < 1:
        raise ValueError("段数至少 1")
    nodes = [("h", 0, k) for k in range(n + 1)]
    idx = {nd: k for k, nd in enumerate(nodes)}
    edges = [(idx[("h", 0, k - 1)], idx[("h", 0, k)], float(r_seg), "M3", 0.0)
             for k in range(1, n + 1)]
    return {"nodes": nodes, "idx": idx, "edges": edges, "source": 0, "sources": [0],
            "nx": n + 1, "ny": 1, "pitch_um": 0.0, "width_um": 0.0,
            "r_per_seg": {"M3": float(r_seg), "M4": 0.0}, "via_r": 0.0}


def add_source(grid: dict, node: int) -> dict:
    """给同一张网再挂一个等压源（模拟多个电源凸点）。返回**新的** grid（不改原对象）。"""
    if not (0 <= int(node) < len(grid["nodes"])):
        raise ValueError("源节点越界: %r" % (node,))
    g = dict(grid)
    srcs = list(grid.get("sources") or [grid["source"]])
    if int(node) not in srcs:
        srcs.append(int(node))
    g["sources"] = srcs
    return g


# ═══════════════════════════════════════════════════════════════════════════
# ② 求解（两条独立路径）
# ═══════════════════════════════════════════════════════════════════════════
def _check_inputs(grid: dict, loads: dict, vdd: float) -> None:
    n = len(grid["nodes"])
    for k, v in loads.items():
        if not (0 <= int(k) < n):
            raise ValueError("负载节点越界: %r" % (k,))
        if float(v) < 0:
            raise ValueError("负载电流必须 ≥0: %r" % (v,))
    for s in (grid.get("sources") or [grid["source"]]):
        if not (0 <= s < n):
            raise ValueError("源节点越界")
    if vdd <= 0:
        raise ValueError("Vdd 必须 >0")
    for (_a, _b, r, _k, _l) in grid["edges"]:
        if not (r > 0):
            raise ValueError("电阻必须 >0（边长 %r）" % (r,))

    # 连通性：每个节点都必须有到电源的通路（否则矩阵奇异，且真实版图里就是悬空）
    adj: dict = {}
    for (a, b, _r, _k, _l) in grid["edges"]:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen = set()
    stack = list(grid.get("sources") or [grid["source"]])
    seen.update(stack)
    while stack:
        u = stack.pop()
        for v in adj.get(u, ()):
            if v not in seen:
                seen.add(v)
                stack.append(v)
    if len(seen) != n:
        raise ValueError("有 %d 个节点与电源不连通（悬空网络）" % (n - len(seen)))


def solve_reduced(grid: dict, loads: dict, vdd: float = VDD_V) -> dict:
    """降阶节点法：电导矩阵 + Dirichlet 边界（源固定 Vdd），numpy 稠密解。

    节点方程（非源节点 i）：`Σ_j (V_i − V_j)/R_ij + I_load_i = 0`。
    把源节点移项到右端 ⇒ `A·x = b`，`A` 对称正定。
    """
    _check_inputs(grid, loads, vdd)
    n = len(grid["nodes"])
    g = np.zeros((n, n), dtype=float)
    for (a, b, r, _k, _l) in grid["edges"]:
        c = 1.0 / r
        g[a, a] += c
        g[b, b] += c
        g[a, b] -= c
        g[b, a] -= c

    srcs = np.array(grid.get("sources") or [grid["source"]], dtype=int)
    load = np.zeros(n, dtype=float)
    for k, v in loads.items():
        load[int(k)] += float(v)

    free = np.array([i for i in range(n) if i not in set(srcs.tolist())], dtype=int)
    a_mat = g[np.ix_(free, free)]
    b_vec = -load[free] - g[np.ix_(free, srcs)].sum(axis=1) * vdd
    x = np.linalg.solve(a_mat, b_vec)

    v = np.empty(n, dtype=float)
    v[srcs] = vdd
    v[free] = x
    return _report(grid, v, load, vdd)


def solve_mna(grid: dict, loads: dict, vdd: float = VDD_V) -> dict:
    """同一张网用仓内 E1 的通用 MNA 求解（**独立实现**，用来互证 `solve_reduced`）。

    MNA 侧把负载建成「节点 → 地」的电流源，源建成理想电压源；节点号整体 +1（0 为地）。
    """
    _check_inputs(grid, loads, vdd)
    ckt = Circuit("pgrid")
    for (a, b, r, _k, _l) in grid["edges"]:
        ckt.resistor(a + 1, b + 1, r)
    for s in (grid.get("sources") or [grid["source"]]):
        ckt.vsource(s + 1, 0, float(vdd))
    for k, v in loads.items():
        if float(v) > 0:
            ckt.isource(int(k) + 1, 0, float(v))
    x = ckt.solve_dc()
    nv = ckt.node_voltages(x)

    n = len(grid["nodes"])
    v = np.array([nv.get(i + 1, 0.0) for i in range(n)], dtype=float)
    load = np.zeros(n, dtype=float)
    for k, vv in loads.items():
        load[int(k)] += float(vv)
    return _report(grid, v, load, vdd)


def _report(grid: dict, v: np.ndarray, load: np.ndarray, vdd: float) -> dict:
    """从节点电压派生：段电流、KCL 残差、能量、最坏压降、EM。"""
    src = grid["source"]
    n = len(grid["nodes"])
    i_edge = []
    p_diss = 0.0
    net_out = np.zeros(n, dtype=float)   # 经支路**离开**节点的净电流
    for (a, b, r, _k, _l) in grid["edges"]:
        ie = (v[a] - v[b]) / r
        i_edge.append(ie)
        p_diss += ie * ie * r
        net_out[a] += ie
        net_out[b] -= ie

    # 每个源节点注入的电流 = 该节点净流出 + 该节点上的负载
    res = net_out + load
    i_src = 0.0
    for s in (grid.get("sources") or [src]):
        inj = float(res[s])
        i_src += inj
        res[s] -= inj          # 扣掉注入后，源节点的 KCL 也应闭合

    src = grid["source"]

    p_load = float(np.dot(v, load))
    drop = float(vdd - v.min())
    return {"v": v, "i_edge": i_edge, "p_diss": p_diss, "p_load": p_load,
            "i_source": i_src, "worst_drop_v": drop,
            "worst_node": int(np.argmin(v)),
            "kcl_residual": float(np.max(np.abs(res))) if n else 0.0,
            "power_balance_rel": (abs(vdd * i_src - (p_diss + p_load))
                                  / max(abs(vdd * i_src), 1e-30)),
            "vdd": vdd, "n_nodes": n, "n_edges": len(grid["edges"])}


def compare_solvers(grid: dict, loads: dict, vdd: float = VDD_V) -> dict:
    """两条独立求解路径的相对差（以 Vdd 为尺度）。"""
    r1 = solve_reduced(grid, loads, vdd)
    r2 = solve_mna(grid, loads, vdd)
    d = float(np.max(np.abs(r1["v"] - r2["v"])) / vdd)
    return {"rel_diff": d, "reduced": r1, "mna": r2}


# ═══════════════════════════════════════════════════════════════════════════
# ③ 判据辅助
# ═══════════════════════════════════════════════════════════════════════════
def uniform_loads(grid: dict, i_total_a: float, skip_source: bool = True) -> dict:
    """把总电流均摊到所有节点（默认跳过源节点）。"""
    ids = [i for i in range(len(grid["nodes"])) if not (skip_source and i == grid["source"])]
    if not ids:
        raise ValueError("没有可加负载的节点")
    per = float(i_total_a) / len(ids)
    return {i: per for i in ids}


def em_segments(grid: dict, res: dict, width_um: float = PG_WIDTH_UM,
                t_um: float = SG.T_METAL_UM) -> dict:
    """逐段电流密度与裕量（只对金属段；via 不参与，因为其截面不同）。"""
    worst = {"j_a_m2": 0.0, "margin_x": float("inf"), "kind": ""}
    area = (width_um * 1e-6) * (t_um * 1e-6)
    for (e, ie) in zip(grid["edges"], res["i_edge"]):
        if e[3] == "VIA":
            continue
        j = abs(ie) / area
        if j > worst["j_a_m2"]:
            worst = {"j_a_m2": j, "margin_x": (J_MAX_A_M2 / j) if j > 0 else float("inf"),
                     "kind": e[3]}
    worst["j_a_m2"] = float(worst["j_a_m2"])
    worst["margin_x"] = float(worst["margin_x"])
    worst["ok"] = bool(worst["j_a_m2"] <= J_MAX_A_M2)   # 显式 bool：numpy.bool_ 不是 False
    worst["j_max"] = J_MAX_A_M2
    return worst


def topology_report(nx: int, ny: int, i_total_a: float, pitch_um: float = PG_PITCH_UM,
                    width_um: float = PG_WIDTH_UM, via_r: float = R_VIA_OHM,
                    vdd: float = VDD_V) -> dict:
    """**只报告**三种口径的压降（不设带宽、不作判据）。

    · `uniform`：总电流均摊到全网格（全域解）；
    · `point`  ：总电流全部压在**最远角**一个负载上（全域解）；
    · `rail`   ：B3 单轨闭式 `I·R/2`（取一条 M3 横条的长度）——**这是另一个问题**，
      列出来只为说明「闭式在假设上就不同」，比值随拓扑变，不能当误差看。
    """
    grid = build_grid(nx, ny, pitch_um, width_um, via_r)
    u = solve_reduced(grid, uniform_loads(grid, i_total_a), vdd)
    far = grid["idx"][("h", ny - 1, nx - 1)]
    pt = solve_reduced(grid, {far: i_total_a}, vdd)
    rail_len = max(1, nx - 1) * pitch_um
    rail = SG.ir_drop_closed(i_total_a, SG.RSH[LAYER_H], rail_len, width_um)
    return {"uniform_drop_v": u["worst_drop_v"], "point_drop_v": pt["worst_drop_v"],
            "rail_closed_v": rail, "rail_len_um": rail_len,
            "point_over_uniform": (pt["worst_drop_v"] / u["worst_drop_v"])
            if u["worst_drop_v"] > 0 else None,
            "uniform_over_rail": (u["worst_drop_v"] / rail) if rail > 0 else None,
            "point_over_rail": (pt["worst_drop_v"] / rail) if rail > 0 else None,
            "n_nodes": u["n_nodes"], "n_edges": u["n_edges"]}


# ═══════════════════════════════════════════════════════════════════════════
# ④ 诚实清单
# ═══════════════════════════════════════════════════════════════════════════
DPGRID_DISCLOSURE = {
    "what": "电源网格全域 IR（规则网格 · 静态 DC · 双解法互证）",
    "claimable": False,
    "not_signoff": True,
    "limits": [
        "只解静态 DC IR：不含 di/dt 动态压降、不含 decap 电荷供给、不含封装/板级阻抗",
        "单角 tt 方块电阻：无 PVT/OCV 降额，无温度梯度",
        "负载是理想电流沉：不建模电压相关电流（真实单元在低压下电流下降 ⇒ 本模型偏保守）",
        "EM 用 DC 段电流：无峰值/开关噪声；J_MAX 仍是量级假设",
        "规则网格：不支持非均匀 pitch、宽窄混排、阻挡/打孔、多源不等压",
        "via 电阻为常数假设，未按孔数与工艺分布建模",
    ],
}
