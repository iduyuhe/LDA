"""D-134 · 超导耦合 transmon 对 版图 + 几何 DRC/LVS + 物理签核（S2 · 吃狗粮）。

S1（D-133）把平台从「只能仿真 transmon」补到「能画出单 transmon 单元并走完
DRC/LVS 签核」。S2 把能力推进到**多比特**：设计「控制 qubit + 目标 qubit +
可调电容耦合器」的耦合对，并做：
  • 几何：两 transmon 单元平移排布 + 耦合器（桥接两 qubit 导体的 FILM 元件）
    + 整框地平面；复用 S1 的 run_sc_drc（最小线宽/间隙/JJ/地间距/短接）。
  • 几何 LVS（多网连通）：JJ 须桥接 ≥2 qubit 导体；耦合器须桥接两 qubit 分量
    （否则两 qubit 分列 → REJECT）；地与 qubit 不重叠；≥2 端口臂。
  • 物理签核（双验证纪律）：
      - coupler_solver 严格对角化 J_num ↔ 解析闭式 J_analytic（rel≤5%）——两条
        方法学独立的路径交叉验证耦合强度（确定性物理定律锚）。
      - cross_resonance 有效模型（Schrieffer-Wolff 主导阶）：J, Δ, α → 有效 ZX
        耦合 g_CR、门时间 t_CR、残余 ZZ σ_zz，并落 ORACLE 验收窗
        （|g_CR|∈[0.02,10]MHz · t_CR≤T2 · 参数区 |Δ|<|α|）。

诚实边界（与 S1 一致）：
  • 耦合器是电容耦合 Cc 的物理实现；Cc 为设计参数，**不**由 GDS 几何反推
    （反推需静电场求解器，属 D5 外部依赖，平台不沾）。
  • cross_resonance 是**有效模型**（SW 主导阶），非完整 transmon 多能级数值；
    σ_zz 为残余 ZZ 估计（真实器件用 echoed-CR 抵消）。ORACLE 为器件物理已知范围。
红线：纯几何（标准库即可）、零量子 SDK、LLM 不进判决路径、DRC 限值为设计规则。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from lda_l2 import gds_export as G
from lda_qeda import sc_layout as SCD
from lda_solver import coupler_solver as CS
from lda_qeda import cross_resonance as CR

# 超导层（与 gds_export / sc_layout 同源）
FILM = G.LIB_LAYER_SC_FILM
JJ = G.LIB_LAYER_SC_JJ
GROUND = G.LIB_LAYER_SC_GROUND

# 复用 S1 DRC 规则名与默认限值
PAIR_DRC_RULES = SCD.SCD_RULES
DEFAULT_DRC_LIMITS = SCD.DEFAULT_DRC_LIMITS

RED_LINE_DISCLOSURE = {
    "role": "D-134 = 超导耦合 transmon 对（控制+目标+可调电容耦合器）版图 + 几何 "
            "DRC/LVS + 物理签核（S2）：把平台「能设计超导芯片」从单比特推进到多比特",
    "layers": "SC_FILM=10 / SC_JJ=11 / SC_GROUND=12（gds_export 定义，非 Foundry PDK）",
    "limits": "min_width/min_jj/min_ground_gap 为**设计规则 · 可覆盖 · 非实测 golden**"
              "（Foundry PDK 层规/金属栈属 D5 外部依赖，平台不沾）",
    "lvs": "几何 LVS 对**实际 produced 几何**做 bbox 重叠网表提取（不重放意图）；"
           "耦合器须桥接两 qubit 分量，否则两 qubit 分列判 REJECT",
    "physics": "J 用 coupler_solver 严格对角化↔解析闭式双验证（确定性锚）；"
               "g_CR/ZZ 用 cross_resonance 有效模型（SW 主导阶），落 ORACLE 验收窗",
    "red_line": "纯几何（标准库，零 numpy 也够）、零量子 SDK、LLM 不进判决路径、"
                "耦合 Cc 为设计参数（不反推 GDS 几何）",
}
ROLE = RED_LINE_DISCLOSURE["role"]

# 单 transmon 单元几何尺寸（与 gds_export Transmon 默认一致，用于耦合器定位）
_T_MONO_PAD_W = 3.0
_T_MONO_ARM_LEN = 6.0
_T_MONO_PAD_H = 2.0


# ---------------------------------------------------------------------------
# 几何工具（bbox / 重叠 / 平移）
# ---------------------------------------------------------------------------
def _bbox(d: Dict) -> Tuple[float, float, float, float]:
    if d["kind"] == "path":
        w = float(d.get("width_um", 0.0)) / 2.0
        xs = [p[0] for p in d["points_um"]]
        ys = [p[1] for p in d["points_um"]]
        return (min(xs) - w, max(xs) + w, min(ys) - w, max(ys) + w)
    pts = [p for r in d["rings_um"] for p in r]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), max(xs), min(ys), max(ys))


def _overlap(a: Tuple[float, float, float, float],
             b: Tuple[float, float, float, float], tol: float = 1e-9) -> bool:
    xmin_a, xmax_a, ymin_a, ymax_a = a
    xmin_b, xmax_b, ymin_b, ymax_b = b
    return not (xmax_a < xmin_b - tol or xmin_a > xmax_b + tol
                or ymax_a < ymin_b - tol or ymin_a > ymax_b + tol)


def _translate(descs: List[Dict], dx: float, dy: float) -> List[Dict]:
    """平移几何元素（path 搬 points_um；boundary 搬 rings_um）。"""
    out: List[Dict] = []
    for d in descs:
        d2 = dict(d)
        if d["kind"] == "path":
            d2["points_um"] = [(x + dx, y + dy) for (x, y) in d["points_um"]]
        else:
            d2["rings_um"] = [[(x + dx, y + dy) for (x, y) in r]
                              for r in d["rings_um"]]
        out.append(d2)
    return out


def _tmon_without_ground(params: Optional[Dict] = None) -> List[Dict]:
    """单 transmon 单元的全部导体（去掉各自的地平面框，改由整框地覆盖）。"""
    return [d for d in SCD.transmon_cell(params or {})
            if d.get("net") != "ground"]


# ---------------------------------------------------------------------------
# 耦合对几何单元
# ---------------------------------------------------------------------------
def coupled_pair_cell(params: Optional[Dict] = None) -> List[Dict]:
    """耦合 transmon 对几何元素（带 net 标签）。

    组成：控制 qubit A（左，平移 -dx）+ 目标 qubit B（右，平移 +dx）+ 耦合器
    （桥接两 qubit 右/左端口臂的 FILM 元件，net="coupler"）+ 整框地平面。
    单一真源 = gds_export.geometry_desc("Transmon") + 本模块的平移/耦合器重组。
    """
    p = dict(params or {})
    dx = float(p.get("pair_dx", 14.0))          # 两 transmon 中心半间距
    gg = float(p.get("ground_gap", 1.0))        # 整框地内边间隙
    cw = float(p.get("coupler_cw", 0.25))       # 耦合器半高（y 方向）
    mono_params = {k: v for k, v in p.items()
                   if k in ("pad_w", "pad_h", "gap_x", "jj_len", "jj_h",
                            "cpw_w", "arm_len")}

    a = _translate(_tmon_without_ground(mono_params), -dx, 0.0)
    b = _translate(_tmon_without_ground(mono_params), dx, 0.0)

    # 耦合器：桥接 A 右端口臂末端 (x=-dx+pad_w+arm_len) 与 B 左端口臂末端
    ax = -dx + _T_MONO_PAD_W + _T_MONO_ARM_LEN
    bx = dx - _T_MONO_PAD_W - _T_MONO_ARM_LEN
    coupler = [{"kind": "boundary", "layer": FILM, "net": "coupler",
                "rings_um": [[(ax, -cw), (bx, -cw), (bx, cw), (ax, cw)]]}]

    # 整框地平面（4 矩形环形，内袋包住两 qubit + 耦合器，留 ground_gap）
    px = dx + _T_MONO_PAD_W + _T_MONO_ARM_LEN + gg   # 内边 x 半幅
    py = _T_MONO_PAD_H + gg                          # 内边 y 半幅
    co = dx + 15.0                                   # 外框半幅
    ground = [
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(-co, py), (co, py), (co, co), (-co, co)]]},
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(-co, -py), (co, -py), (co, -co), (-co, -co)]]},
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(-co, -py), (-px, -py), (-px, py), (-co, py)]]},
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(px, -py), (co, -py), (co, py), (px, py)]]},
    ]
    return a + b + coupler + ground


# ---------------------------------------------------------------------------
# GDS / SVG 出口
# ---------------------------------------------------------------------------
def coupled_pair_gds(params: Optional[Dict] = None,
                     path: str = "sc_pair.gds") -> bytes:
    """真出 GDSII（零依赖自写编码器）。返回文件字节。"""
    # 耦合对需自定义结构（两 transmon + 耦合器 + 整框地），故直接由
    # coupled_pair_cell 组装元素，再逐条编码为 GDSII 记录。
    descs = coupled_pair_cell(params)
    recs: List[bytes] = []
    for d in descs:
        if d["kind"] == "path":
            recs.append(G.path(d["layer"], d["width_um"], d["points_um"]))
        else:
            recs.append(G.boundary(d["layer"], G._flatten_rings(d.get("rings_um"))))
    data = G.gds_library("LDA-SC-PAIR", {"sc_pair": recs})
    G.write_gds(path, data)
    return data


def coupled_pair_svg_preview(params: Optional[Dict] = None, width: int = 520) -> str:
    """版图 SVG 预览（按 net 上色：qubit=蓝 / jj=红 / coupler=橙 / ground=灰）。"""
    descs = coupled_pair_cell(params)
    layer_color = {FILM: "#2563eb", JJ: "#e11d48", GROUND: "#94a3b8"}
    net_color = {"qubit": "#2563eb", "jj": "#e11d48",
                 "coupler": "#f59e0b", "ground": "#94a3b8"}
    xs, ys = [], []
    for d in descs:
        pts = d.get("points_um") or [p for r in d.get("rings_um", []) for p in r]
        xs += [p[0] for p in pts]
        ys += [p[1] for p in pts]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    span = max(xmax - xmin, ymax - ymin, 1e-6)
    pad = 24
    S = (width - 2 * pad) / span
    X = lambda x: pad + (x - xmin) * S
    Y = lambda y: pad + (ymax - y) * S
    out = [f'<svg width="{width}" height="{width}" '
           'style="background:#fff;border:1px solid #ddd;border-radius:6px">']
    for d in descs:
        col = net_color.get(d.get("net"), layer_color.get(d["layer"], "#2563eb"))
        pts = d.get("points_um") or [p for r in d.get("rings_um", []) for p in r]
        dd = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in pts)
        if d["kind"] == "path":
            out.append(f'<polyline points="{dd}" fill="none" stroke="{col}" '
                       f'stroke-width="{max(d.get("width_um", 0.5) * S, 2):.1f}"/>')
        else:
            out.append(f'<polygon points="{dd}" fill="{col}" fill-opacity="0.7"/>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------------------
# 耦合对 DRC（复用 S1 规则集）
# ---------------------------------------------------------------------------
def run_sc_pair_drc(elements: List[Dict], limits: Optional[Dict] = None) -> Dict:
    """耦合对几何 DRC：直接复用 S1 的 run_sc_drc（最小线宽/JJ/地间距/短接）。

    耦合器作为 FILM boundary 自动进入「qubit_boxes」参与最小线宽与地间距检查；
    整框地平面覆盖两 qubit。返回 {verdict, violations, n_rules, limits}。
    """
    return SCD.run_sc_drc(elements, limits)


# ---------------------------------------------------------------------------
# 耦合对 几何 LVS（多网连通：耦合器桥接两 qubit）
# ---------------------------------------------------------------------------
def sc_pair_lvs_signoff(elements: List[Dict]) -> Dict:
    """耦合对几何 LVS：对**实际 produced 几何**做 bbox 重叠网表提取。

    判据：① 每导体有 net（零悬空标签）② 存在 JJ 且每个 JJ 桥接 ≥2 qubit 导体
    ③ 存在耦合器且桥接 ≥2 qubit 导体（否则两 qubit 分列）④ qubit+耦合器全在
    同一连通分量（经 JJ/耦合器桥接）⑤ 地与导体不重叠（短接）⑥ ≥2 根 qubit
    端口臂（readout + flux）。
    返回 {verdict, issues, netlist, n_checks}。
    """
    issues: List[str] = []
    n_checks = 0

    cond = [(d["layer"], d.get("net", ""), _bbox(d))
            for d in elements if d["kind"] in ("path", "boundary")]
    n_checks += 1
    if any(not net for (_L, net, _bb) in cond):
        issues.append("SCD-LVS-NO-NET: 存在无 net 标签的导体元素")

    qubit = [(L, net, bb) for (L, net, bb) in cond if net == "qubit"]
    coupler = [(L, net, bb) for (L, net, bb) in cond if net == "coupler"]
    jj = [(L, net, bb) for (L, net, bb) in cond if net == "jj"]
    ground = [(L, net, bb) for (L, net, bb) in cond if net == "ground"]

    n_checks += 1
    if not jj:
        issues.append("SCD-LVS-NO-JJ: 无约瑟夫森结元素")
    else:
        for (_L, _n, jbb) in jj:
            touched = [bb for (L, net, bb) in qubit if _overlap(jbb, bb)]
            if len(touched) < 2:
                issues.append("SCD-LVS-JJ-NOT-BRIDGING: JJ 未同时桥接 ≥2 个 qubit 导体")

    n_checks += 1
    if not coupler:
        issues.append("SCD-LVS-NO-COUPLER: 耦合对缺耦合元件（控制/目标未连接）")
    else:
        for (_L, _n, cbb) in coupler:
            touched = [bb for (L, net, bb) in qubit if _overlap(cbb, bb)]
            if len(touched) < 2:
                issues.append("SCD-LVS-COUPLER-NOT-BRIDGING: 耦合器未桥接 ≥2 个 qubit 导体")

    # 连通性：qubit + coupler 经相互重叠与 JJ 桥接须合并为单分量
    n_checks += 1
    allq = qubit + coupler
    parent = list(range(len(allq)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(len(allq)):
        for j in range(i + 1, len(allq)):
            if _overlap(allq[i][2], allq[j][2]):
                union(i, j)
    for (_L, _n, jbb) in jj:
        idxs = [k for k, (L, net, bb) in enumerate(allq) if _overlap(jbb, bb)]
        for k in range(1, len(idxs)):
            union(idxs[0], idxs[k])
    comps = set(find(i) for i in range(len(allq)))
    if allq and len(comps) > 1:
        issues.append(f"SCD-LVS-FLOATING-QUBIT: qubit+耦合器分成 {len(comps)} 个"
                      "孤立分量（耦合器未连通两 qubit）")

    n_checks += 1
    short = any(_overlap(qbb, gbb) for (_Lq, _nq, qbb) in allq
                for (_Lg, _ng, gbb) in ground)
    if short:
        issues.append("SCD-LVS-QUBIT-GROUND-SHORT: 导体与地平面重叠（短接）")

    n_checks += 1
    arms = [d for d in elements if d.get("net") == "qubit" and d["kind"] == "path"]
    if len(arms) < 2:
        issues.append("SCD-LVS-PORTS: qubit 端口臂 < 2（readout/flux 须各一）")

    verdict = "ACCEPT" if not issues else "REJECT"
    return {"verdict": verdict, "issues": issues,
            "netlist": {"qubit": len(qubit), "coupler": len(coupler),
                        "jj": len(jj), "ground": len(ground),
                        "components": len(comps) if allq else 0},
            "n_checks": n_checks}


# ---------------------------------------------------------------------------
# 物理签核（双验证纪律：严格 J ↔ 解析 J + CR 有效模型 + ZZ）
# ---------------------------------------------------------------------------
def coupled_pair_physics(params: Optional[Dict] = None) -> Dict:
    """耦合对物理签核。

    输入（设计参数）：E_J1/E_C1（控制 qubit A）、E_J2/E_C2（目标 qubit B）、
    Cc/C1/C2（电容耦合）。单位：能量 GHz，电容归一化。
    返回：每 qubit f01/α（Koch 闭式）、失谐 Δ、耦合 J（严格↔解析双验证）、
    有效 ZX 耦合 g_CR、门时间 t_CR、残余 ZZ σ_zz、验收与 verdict。
    """
    p = dict(params or {})
    # 默认采用**规范 transmon 工作区**：f01≈5.8 GHz、失谐 Δ≈213 MHz（< |α|=250 MHz
    # 满足 CR 有效模型参数区）、耦合 J 经严格对角化↔解析闭式双验证 rel≈4.3%。
    EJ1 = float(p.get("E_J1", 18.0))
    EC1 = float(p.get("E_C1", 0.25))
    EJ2 = float(p.get("E_J2", 19.3))
    EC2 = float(p.get("E_C2", 0.25))
    Cc = float(p.get("Cc", 0.007))
    C1 = float(p.get("C1", 1.0))
    C2 = float(p.get("C2", 1.0))

    fA = CS.koch_f01(EJ1, EC1)
    fB = CS.koch_f01(EJ2, EC2)
    alpha = -EC2                                   # 目标 qubit 非谐性（GHz）
    delta = fB - fA                                # 失谐 Δ=ω_t−ω_c（GHz）

    sol = CS.solve_coupler(EJ1, EC1, EJ2, EC2, Cc, C1, C2)
    J_num = float(sol["J_num"])                    # 严格对角化（GHz）
    J_an = float(sol["J_analytic"])                # 解析闭式（GHz）
    relJ = abs(J_num - J_an) / (abs(J_an) + 1e-12)
    J_mhz = J_num * 1000.0

    cr = CR.cross_resonance(J_mhz, delta * 1000.0, alpha * 1000.0)

    j_ok = bool(relJ <= 0.05)                       # 双验证容差 5%
    cr_ok = bool(cr.get("ok", False))
    verdict = "ACCEPT" if (j_ok and cr_ok) else "REJECT"

    return {
        "verdict": verdict,
        "f01_A_ghz": float(fA),
        "f01_B_ghz": float(fB),
        "alpha_B_ghz": float(alpha),
        "detune_ghz": float(delta),
        "J_num_ghz": J_num,
        "J_analytic_ghz": J_an,
        "J_rel_err": float(relJ),
        "J_double_validated": j_ok,
        "g_CR_mhz": cr.get("g_CR_MHz"),
        "abs_g_CR_mhz": cr.get("abs_g_CR_MHz"),
        "t_CR_us": cr.get("t_CR_us"),
        "sigma_zz_mhz": cr.get("sigma_zz_MHz"),
        "cr_valid_regime": cr.get("valid_regime"),
        "cr_in_real_band": cr.get("in_real_band"),
        "cr_within_T2": cr.get("within_T2"),
        "cr_ok": cr_ok,
        "cr_formula": cr.get("formula"),
        "acceptance": {
            "J_double_validated": j_ok,
            "g_CR_in_real_band": bool(cr.get("in_real_band", False)),
            "t_CR_within_T2": bool(cr.get("within_T2", False)),
            "valid_regime": bool(cr.get("valid_regime", False)),
        },
        "note": ("J 用 coupler_solver 严格对角化↔解析闭式双验证（确定性物理定律锚，"
                 "容差 5%）；g_CR/ZZ 用 cross_resonance 有效模型（Schrieffer-Wolff "
                 "主导阶），落 ORACLE 验收窗 |g_CR|∈[0.02,10]MHz、t_CR≤T2、|Δ|<|α|。"
                 "耦合 Cc 为设计参数，不反推 GDS 几何。LLM 不进判决路径。"),
    }


# ---------------------------------------------------------------------------
# 自检（常驻断言：合法 ACCEPT/ACCEPT；各违规 REJECT）
# ---------------------------------------------------------------------------
def run_selfchecks(verbose: bool = False) -> bool:
    ok = True
    msgs: List[Tuple[str, bool]] = []

    def chk(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        msgs.append((name, bool(cond)))

    pair = coupled_pair_cell({})
    chk("① 合法耦合对 DRC ACCEPT", run_sc_pair_drc(pair)["verdict"] == "ACCEPT")
    chk("② 合法耦合对 LVS ACCEPT（JJ+耦合器桥接 · 单连通分量）",
        sc_pair_lvs_signoff(pair)["verdict"] == "ACCEPT")

    no_coup = [d for d in pair if d.get("net") != "coupler"]
    chk("③ 缺耦合器 ⇒ LVS REJECT（COUPLER-NOT-BRIDGING / FLOATING）",
        sc_pair_lvs_signoff(no_coup)["verdict"] == "REJECT")

    thin = coupled_pair_cell({"coupler_cw": 0.05})
    vt = run_sc_pair_drc(thin)
    chk("④ 耦合器太薄(高0.1<0.2) ⇒ DRC REJECT（SCD-MIN-WIDTH）",
        vt["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-MIN-WIDTH" for v in vt["violations"]))

    short = coupled_pair_cell({"ground_gap": -0.5})
    vs = run_sc_pair_drc(short)
    vsl = sc_pair_lvs_signoff(short)
    chk("⑤ 地短接 ⇒ DRC REJECT（SCD-QUBIT-GROUND-SHORT）",
        vs["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-QUBIT-GROUND-SHORT" for v in vs["violations"]))
    chk("⑥ 地短接 ⇒ LVS REJECT（QUBIT-GROUND-SHORT）",
        vsl["verdict"] == "REJECT"
        and any("GROUND-SHORT" in i for i in vsl["issues"]))

    phys = coupled_pair_physics({})
    chk("⑦ 合法耦合对物理 ACCEPT（J 双验证 + CR 有效模型落窗）",
        phys["verdict"] == "ACCEPT")

    if verbose:
        for n, c in msgs:
            print(f"  [{'PASS' if c else 'FAIL'}] {n}")
    return ok


# ===========================================================================
# G3 · D-139 可调耦合器（flux-tunable SQUID coupler · S5 P1）
# ===========================================================================
# S2 的耦合器是**固定**电容 Cc（桥接两 qubit 的 FILM 元件）。G3 把耦合器升级为
# **flux 可调**：SQUID 环（两个 JJ 并联）被一根 flux 偏置线穿过/邻近，环的有效
# E_J 随外加磁通 Φ 变化 ⇒ 耦合可开可关（真实 Sycamore/IBM 架构用可调耦合器）。
#
# 几何：qubit A/B（复用 S2 的 _tmon_without_ground）+ SQUID 环（左右两条竖向
# bar + 上下两个 JJ 连成闭环）+ 两条 lead（把环接到两 qubit 的端口臂）+ flux 偏置
# 线（环下方水平走线，间隙隔离，电感性耦合）+ 整框地。单一真源 = S2 原语。
#
# 物理（全部闭式 · 方法学独立，LLM 不进判决路径）：
#   ① SQUID 有效临界电流（精确式，含结不对称）：
#        E_J(Φ) = sqrt( (E_J1+E_J2)²·cos²(πf) + (E_J1−E_J2)²·sin²(πf) )
#      f = Φ/Φ0；对称时退化为 2E_J0·|cos(πf)|。f=0.5 时取极小 = |E_J1−E_J2|。
#   ② qubit↔coupler 耦合 J_qc：coupler_solver 严格对角化 ↔ 解析闭式**双验证**（同 S2 纪律）。
#   ③ 经耦合器的二阶虚交换有效 qubit-qubit 耦合：J_eff(Φ) = J_qc(Φ)²/Δ_c(Φ)，
#      Δ_c = f_c(Φ) − f_q（Rayleigh-Schrödinger 二阶；设计预算，非完整多能级数值）。
#   验收：J 双验证 rel ≤ 5% · J_on 落 CR 带 [0.02,10] MHz · 可关比 J_on/J_off ≥ 阈值。

TUNABLE_DRC_RULES = tuple(list(PAIR_DRC_RULES) + [
    "SCD-SQUID-JJ-COUNT",      # SQUID 环上的 JJ 数须恰为 2（并联 SQUID 定义）
    "SCD-FLUX-LINE-GAP",       # flux 偏置线到最近导体间隙 ≥ 下限（隔离，防短接）
    "SCD-SQUID-LOOP-AREA",     # SQUID 环闭合面积 ≥ 下限（足量磁通耦合）
])
DEFAULT_TUNABLE_LIMITS = dict(DEFAULT_DRC_LIMITS)
DEFAULT_TUNABLE_LIMITS.update({
    "min_flux_line_gap_um": 0.3,   # flux 线-导体最小间距（设计规则 · 可覆盖）
    "min_squid_loop_area_um2": 0.2,
})

TUNABLE_OFF_RATIO_MIN = 5.0            # 可关比下限（设计目标：耦合器能“关断”）
TUNABLE_J_BAND_MHZ = (0.02, 10.0)      # 有效耦合验收带（与 S2 CR ORACLE 窗同口径）

TUNABLE_RED_LINE_DISCLOSURE = {
    "role": "D-139 = 超导征程 S5 P1：flux 可调耦合器（SQUID）版图 + 几何 DRC/LVS + "
            "可调性物理签核（把 S2 的固定电容耦合器升级为磁通可调）",
    "layers": "SC_FILM=10 / SC_JJ=11 / SC_GROUND=12（gds_export 定义，非 Foundry PDK）；"
              "SQUID 环与 lead 布 FILM 层，JJ 布 SC_JJ 层，flux 线布 FILM 层以 net=flux 区分",
    "limits": "min_flux_line_gap / min_squid_loop_area 为**设计规则 · 可覆盖 · 非实测 golden**"
              "（Foundry PDK 属 D5 外部依赖）",
    "lvs": "几何 LVS 对**实际 produced 几何**做 bbox 重叠网表提取：SQUID 须恰 2 个 JJ 桥接"
           "两条 coupler 岛，环经 JJ 闭合为单连通分量，flux 线与导体零重叠（电感性）",
    "physics": "SQUID E_J(Φ) 为**精确闭式**（含结不对称，golden）；J_qc 用 coupler_solver "
               "严格对角化↔解析闭式双验证（rel≤5%）；J_eff=J_qc²/Δ_c 为二阶虚交换设计预算",
    "red_line": "纯几何（标准库 + 平台 numpy 物理锚）、零量子 SDK、LLM 不进判决路径、"
                "flux 线为片内几何（外磁场/封装屏蔽片外未建模）",
}

# SQUID 环默认几何（小环 ⇒ JJ 短、耦合强）
_LOOP_HW = 0.6      # 环半宽（x）
_LOOP_HH = 0.7      # 环半高（y）
_LOOP_BAR = 0.25    # 环壁厚（bar 宽）
_JJ_H = 0.2         # JJ 高（y 向）


def squid_ej(E_J1: float, E_J2: float, flux_fraction: float) -> float:
    """SQUID 有效 E_J（GHz，精确闭式，含结不对称）。

        E_J(Φ) = sqrt( (E_J1+E_J2)²·cos²(πf) + (E_J1−E_J2)²·sin²(πf) )，f=Φ/Φ0。
    对称结（E_J1=E_J2）退化为 2·E_J0·|cos(πf)|。f=0.5 取极小 = |E_J1−E_J2|（非零 ⇒ 物理真实）。
    """
    f = float(flux_fraction)
    s = math.sin(math.pi * f)
    c = math.cos(math.pi * f)
    return float(math.sqrt((E_J1 + E_J2) ** 2 * c * c + (E_J1 - E_J2) ** 2 * s * s))


def tunable_coupler_cell(params: Optional[Dict] = None) -> List[Dict]:
    """可调耦合器（SQUID）几何元素（带 net 标签）。

    组成：qubit A（左，-dx）+ qubit B（右，+dx）+ 两条 lead（net=coupler，接环到端口臂）
    + SQUID 环（左右两条竖向 bar，net=coupler）+ 上下两个 JJ（net=jj，连成闭环）
    + flux 偏置线（net=flux，环下方水平，间隙隔离）+ 整框地。
    """
    p = dict(params or {})
    dx = float(p.get("pair_dx", 14.0))
    gg = float(p.get("ground_gap", 1.0))
    lwh = float(p.get("loop_hw", _LOOP_HW))
    lhh = float(p.get("loop_hh", _LOOP_HH))
    bar = float(p.get("loop_bar", _LOOP_BAR))
    jjh = float(p.get("squid_jj_h", _JJ_H))
    flux_w = float(p.get("flux_line_w", 0.3))
    flux_gap = float(p.get("flux_line_gap", 0.5))
    flux_span = float(p.get("flux_line_span", 1.0))     # 水平半长
    mono_params = {k: v for k, v in p.items()
                   if k in ("pad_w", "pad_h", "gap_x", "jj_len", "jj_h",
                            "cpw_w", "arm_len")}

    a = _translate(_tmon_without_ground(mono_params), -dx, 0.0)
    b = _translate(_tmon_without_ground(mono_params), dx, 0.0)

    ax = -dx + _T_MONO_PAD_W + _T_MONO_ARM_LEN     # A 右端口臂末端
    bx = dx - _T_MONO_PAD_W - _T_MONO_ARM_LEN      # B 左端口臂末端
    half = bar / 2.0

    # 两条 lead（把环接到端口臂），水平、跨越断口
    lead_l = [{"kind": "path", "layer": FILM, "net": "coupler",
               "width_um": bar, "points_um": [(ax - 0.5, 0.0), (-lwh, 0.0)]}]
    lead_r = [{"kind": "path", "layer": FILM, "net": "coupler",
               "width_um": bar, "points_um": [(lwh, 0.0), (bx + 0.5, 0.0)]}]

    # SQUID 环：左右两条竖向 bar
    bar_l = [{"kind": "boundary", "layer": FILM, "net": "coupler",
              "rings_um": [[(-lwh - half, -lhh), (-lwh + half, -lhh),
                            (-lwh + half, lhh), (-lwh - half, lhh)]]}]
    bar_r = [{"kind": "boundary", "layer": FILM, "net": "coupler",
              "rings_um": [[(lwh - half, -lhh), (lwh + half, -lhh),
                            (lwh + half, lhh), (lwh - half, lhh)]]}]

    # 上下两个 JJ：跨接两 bar（左 bar 右缘 → 右 bar 左缘）
    jj_top = [{"kind": "boundary", "layer": JJ, "net": "jj",
               "rings_um": [[(-lwh - half, lhh - jjh), (lwh + half, lhh - jjh),
                             (lwh + half, lhh), (-lwh - half, lhh)]]}]
    jj_bot = [{"kind": "boundary", "layer": JJ, "net": "jj",
               "rings_um": [[(-lwh - half, -lhh), (lwh + half, -lhh),
                             (lwh + half, -lhh + jjh), (-lwh - half, -lhh + jjh)]]}]

    # flux 偏置线：环下方水平走线（间隙隔离，电感性）
    yf = -lhh - flux_gap - flux_w / 2.0
    flux = [{"kind": "path", "layer": FILM, "net": "flux",
             "width_um": flux_w,
             "points_um": [(-lwh - flux_span, yf), (lwh + flux_span, yf)]}]

    body = a + b + lead_l + lead_r + bar_l + bar_r + jj_top + jj_bot + flux

    # 整框地（内袋包住全部导体 + gg 间隙）
    boxes = [_bbox(d) for d in body]
    px = max(abs(b[0]) for b in boxes) + gg
    py = max(abs(b[2]) for b in boxes) + gg
    co = max(px, py) + 15.0
    ground = [
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(-co, py), (co, py), (co, co), (-co, co)]]},
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(-co, -py), (co, -py), (co, -co), (-co, -co)]]},
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(-co, -py), (-px, -py), (-px, py), (-co, py)]]},
        {"kind": "boundary", "layer": GROUND, "net": "ground",
         "rings_um": [[(px, -py), (co, -py), (co, py), (px, py)]]},
    ]
    return body + ground


def tunable_coupler_gds(params: Optional[Dict] = None,
                        path: str = "sc_tunable.gds") -> bytes:
    """真出 GDSII（零依赖自写编码器）。返回文件字节。"""
    descs = tunable_coupler_cell(params)
    recs: List[bytes] = []
    for d in descs:
        if d["kind"] == "path":
            recs.append(G.path(d["layer"], d["width_um"], d["points_um"]))
        else:
            recs.append(G.boundary(d["layer"], G._flatten_rings(d.get("rings_um"))))
    data = G.gds_library("LDA-SC-TUNABLE", {"sc_tunable": recs})
    G.write_gds(path, data)
    return data


def tunable_coupler_svg_preview(params: Optional[Dict] = None,
                                width: int = 560) -> str:
    """版图 SVG 预览（qubit=蓝 / jj=红 / coupler=橙 / flux=紫 / ground=灰）。"""
    descs = tunable_coupler_cell(params)
    net_color = {"qubit": "#2563eb", "jj": "#e11d48", "coupler": "#f59e0b",
                 "flux": "#7c3aed", "ground": "#94a3b8"}
    xs, ys = [], []
    for d in descs:
        pts = d.get("points_um") or [p for r in d.get("rings_um", []) for p in r]
        xs += [p[0] for p in pts]
        ys += [p[1] for p in pts]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    span = max(xmax - xmin, ymax - ymin, 1e-6)
    pad = 24
    S = (width - 2 * pad) / span
    X = lambda x: pad + (x - xmin) * S          # noqa: E731
    Y = lambda y: pad + (ymax - y) * S          # noqa: E731
    out = [f'<svg width="{width}" height="{width}" '
           'style="background:#fff;border:1px solid #ddd;border-radius:6px">']
    for d in descs:
        col = net_color.get(d.get("net"), "#2563eb")
        pts = d.get("points_um") or [p for r in d.get("rings_um", []) for p in r]
        dd = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in pts)
        if d["kind"] == "path":
            out.append(f'<polyline points="{dd}" fill="none" stroke="{col}" '
                       f'stroke-width="{max(d.get("width_um", 0.5) * S, 2):.1f}"/>')
        else:
            out.append(f'<polygon points="{dd}" fill="{col}" fill-opacity="0.7"/>')
    out.append("</svg>")
    return "".join(out)


def _squid_jjs(elements: List[Dict]) -> List[Dict]:
    """挑出桥接 coupler 岛的 JJ（SQUID 结，区别于 qubit 自身的 transmon 结）。"""
    coup = [_bbox(d) for d in elements if d.get("net") == "coupler"]
    out = []
    for d in elements:
        if d.get("net") != "jj":
            continue
        bb = _bbox(d)
        if sum(1 for cb in coup if _overlap(bb, cb)) >= 2:
            out.append(d)
    return out


def run_tunable_drc(elements: List[Dict],
                    limits: Optional[Dict] = None) -> Dict:
    """可调耦合器几何 DRC = S2 四则 + SQUID 三则。"""
    lim = dict(DEFAULT_TUNABLE_LIMITS)
    if limits:
        lim.update(limits)
    base = run_sc_pair_drc(elements, lim)
    violations = list(base["violations"])

    # SCD-SQUID-JJ-COUNT：恰 2 个 SQUID 结
    n_squid = len(_squid_jjs(elements))
    if n_squid != 2:
        violations.append({"rule": "SCD-SQUID-JJ-COUNT",
                           "detail": f"SQUID 环结数={n_squid}≠2"})

    # SCD-FLUX-LINE-GAP：flux 线到最近导体间隙 ≥ 下限
    flux = [_bbox(d) for d in elements if d.get("net") == "flux"]
    others = [_bbox(d) for d in elements
              if d.get("net") not in ("flux", "ground")]
    min_gap = float("inf")
    for fb in flux:
        for ob in others:
            dx = max(fb[0] - ob[1], ob[0] - fb[1], 0.0)
            dy = max(fb[2] - ob[3], ob[2] - fb[3], 0.0)
            min_gap = min(min_gap, math.hypot(dx, dy))
    if flux and min_gap < lim["min_flux_line_gap_um"]:
        violations.append({"rule": "SCD-FLUX-LINE-GAP",
                           "detail": f"flux 线-导体间隙={min_gap:.3f}"
                                     f"<{lim['min_flux_line_gap_um']}"})

    # SCD-SQUID-LOOP-AREA：环闭合面积 ≥ 下限
    coup_boxes = [_bbox(d) for d in elements if d.get("net") == "coupler"]
    loop_area = 0.0
    if coup_boxes:
        lx0 = min(b[0] for b in coup_boxes); lx1 = max(b[1] for b in coup_boxes)
        ly0 = min(b[2] for b in coup_boxes); ly1 = max(b[3] for b in coup_boxes)
        loop_area = (lx1 - lx0) * (ly1 - ly0)
    if loop_area < lim["min_squid_loop_area_um2"]:
        violations.append({"rule": "SCD-SQUID-LOOP-AREA",
                           "detail": f"环面积={loop_area:.3f}"
                                     f"<{lim['min_squid_loop_area_um2']}"})

    verdict = "ACCEPT" if not violations else "REJECT"
    return {"verdict": verdict, "violations": violations,
            "n_rules": len(TUNABLE_DRC_RULES),
            "n_squid_jj": n_squid, "flux_min_gap_um": (None if min_gap == float("inf")
                                                       else float(min_gap)),
            "loop_area_um2": float(loop_area)}


def tunable_coupler_lvs(elements: List[Dict]) -> Dict:
    """可调耦合器几何 LVS（SQUID 语义）。

    判据：① 每导体有 net ② ≥2 qubit 网 ③ SQUID 恰 2 结且每结桥接两条 coupler 岛
    ④ 每 qubit 有端口臂（path）⑤ {qubit∪coupler∪jj} 单连通分量 ⑥ 地与导体不重叠
    ⑦ flux 线与导体零重叠（电感性耦合，不短路）。
    """
    issues: List[str] = []
    n_checks = 0
    cond = [(d["layer"], d.get("net", ""), _bbox(d))
            for d in elements if d["kind"] in ("path", "boundary")]

    n_checks += 1
    if any(not net for (_L, net, _bb) in cond):
        issues.append("SCD-LVS-NO-NET: 存在无 net 标签的导体元素")

    qubit = [(L, net, bb) for (L, net, bb) in cond if net == "qubit"]
    coupler = [(L, net, bb) for (L, net, bb) in cond if net == "coupler"]
    jj = [(L, net, bb) for (L, net, bb) in cond if net == "jj"]
    ground = [(L, net, bb) for (L, net, bb) in cond if net == "ground"]
    flux = [(L, net, bb) for (L, net, bb) in cond if net == "flux"]

    n_checks += 1
    qb = [_bbox(d) for d in elements if d.get("net") == "qubit"]
    qparent = list(range(len(qb)))

    def qfind(x):
        while qparent[x] != x:
            qparent[x] = qparent[qparent[x]]
            x = qparent[x]
        return x

    for i in range(len(qb)):
        for j in range(i + 1, len(qb)):
            if _overlap(qb[i], qb[j]):
                ri, rj = qfind(i), qfind(j)
                if ri != rj:
                    qparent[ri] = rj
    n_qcomp = len({qfind(i) for i in range(len(qb))}) if qb else 0
    if n_qcomp < 2:
        issues.append(f"SCD-LVS-QUBIT-COUNT: qubit 连通分量={n_qcomp} < 2")

    n_checks += 1
    squid_jj = _squid_jjs(elements)
    if len(squid_jj) != 2:
        issues.append(f"SCD-LVS-SQUID-JJ-COUNT: SQUID 结数={len(squid_jj)}≠2")
    else:
        for sj in squid_jj:
            if sum(1 for (_L, _n, cb) in coupler if _overlap(_bbox(sj), cb)) < 2:
                issues.append("SCD-LVS-SQUID-JJ-NOT-BRIDGING: SQUID 结未桥接两条 coupler 岛")

    n_checks += 1
    arms = [d for d in elements if d.get("net") == "qubit" and d["kind"] == "path"]
    if len(arms) < 2:
        issues.append("SCD-LVS-PORTS: qubit 端口臂 < 2")

    n_checks += 1
    allq = qubit + coupler
    parent = list(range(len(allq)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(len(allq)):
        for j in range(i + 1, len(allq)):
            if _overlap(allq[i][2], allq[j][2]):
                union(i, j)
    for (_L, _n, jbb) in jj:                    # 全部 JJ（transmon 结 + SQUID 结）都桥接
        idxs = [k for k, (L, net, bb) in enumerate(allq) if _overlap(jbb, bb)]
        for k in range(1, len(idxs)):
            union(idxs[0], idxs[k])
    comps = set(find(i) for i in range(len(allq)))
    if allq and len(comps) > 1:
        issues.append(f"SCD-LVS-FLOATING: qubit+coupler 分成 {len(comps)} 个孤立分量")

    n_checks += 1
    short = any(_overlap(qbb, gbb) for (_Lq, _nq, qbb) in allq
                for (_Lg, _ng, gbb) in ground)
    if short:
        issues.append("SCD-LVS-QUBIT-GROUND-SHORT: 导体与地平面重叠（短接）")

    n_checks += 1
    flux_short = any(_overlap(fbb, cbb) for (_Lf, _nf, fbb) in flux
                     for (_Lc, _nc, cbb) in (qubit + coupler + jj))
    if flux_short:
        issues.append("SCD-LVS-FLUX-SHORT: flux 线与导体重叠（应电感性耦合，不得短路）")

    verdict = "ACCEPT" if not issues else "REJECT"
    return {"verdict": verdict, "issues": issues,
            "netlist": {"qubit": len(qubit), "coupler": len(coupler),
                        "jj": len(jj), "squid_jj": len(squid_jj),
                        "flux": len(flux), "ground": len(ground),
                        "components": len(comps) if allq else 0},
            "n_checks": n_checks}


def tunable_coupler_physics(params: Optional[Dict] = None) -> Dict:
    """可调耦合器物理签核（SQUID 可调性 + J 双验证）。

    输入（设计参数）：E_J1_squid/E_J2_squid（两结，含不对称）、E_C_coupler、
    Cc_qc（qubit↔coupler 电容）、E_J_q/E_C_q（qubit）。单位 GHz。
    返回：E_J(Φ) 扫描、J_qc(Φ)、J_eff(Φ)、J_on/J_off、可关比、验收与 verdict。

    🔴 双验证的**有效区**（诚实边界）：coupler_solver 的 J_num 由「第一激发双态分裂」
    提取，仅在 qubit–coupler 近共振（|Δ_c| ≤ valid_detune_max）时可分辨；深失谐（耦合器
    关断区）该提取退化 ⇒ 只在有效区做 J_num↔J_analytic 双验证，有效区外 J_qc 取解析闭式
    （设计预算）。LLM 不进判决路径。
    """
    p = dict(params or {})
    # 默认工作区：coupler E_J_max=16 GHz（f_c≈5.19 < f_q≈5.74）⇒ 全程 f_c < f_q，
    # 磁通增大时 f_c 单调下移、|Δ_c| 单调增大、J_eff 单调下降（无共振穿越，扰动式成立）。
    EJ1 = float(p.get("E_J1_squid", 8.2))
    EJ2 = float(p.get("E_J2_squid", 7.8))       # 轻微不对称 ⇒ E_J_min=0.4（f=0.5 不归零）
    ECc = float(p.get("E_C_coupler", 0.23))
    Cc = float(p.get("Cc_qc", 0.01))
    EJq = float(p.get("E_J_q", 18.0))
    ECq = float(p.get("E_C_q", 0.25))
    valid_detune = float(p.get("valid_detune_ghz", 1.0))
    flux_pts = p.get("flux_points") or [i / 20.0 for i in range(11)]   # 0 … 0.5

    samples: List[Dict] = []
    max_rel = 0.0
    n_validated = 0
    for f in flux_pts:
        EJc = squid_ej(EJ1, EJ2, float(f))
        sol = CS.solve_coupler(EJc, ECc, EJq, ECq, Cc, 1.0, 1.0)
        fc = float(sol["f01_1_num_ghz"])        # coupler 的**数值** f01
        fq = float(sol["f01_2_num_ghz"])
        J_num = float(sol["J_num"])             # 严格对角化（仅近共振可分辨）
        J_an = float(CS.coupling_analytic(EJc, ECc, EJq, ECq, Cc, 1.0, 1.0))
        delta_c = fc - fq
        validated = bool(abs(delta_c) <= valid_detune)
        rel = abs(J_num - J_an) / (abs(J_an) + 1e-15)
        if validated:
            max_rel = max(max_rel, rel)
            n_validated += 1
        J_eff = (J_an * J_an / delta_c) if abs(delta_c) > 1e-9 else 0.0
        samples.append({
            "flux_frac": float(f), "E_J_coupler_ghz": EJc,
            "f_coupler_ghz": fc, "f_qubit_ghz": fq, "delta_c_ghz": float(delta_c),
            "J_qc_ghz": J_an, "J_qc_num_ghz": J_num, "J_rel_err": float(rel),
            "validated": validated,
            "J_eff_ghz": float(J_eff), "J_eff_mhz": float(J_eff * 1000.0),
        })

    J_on_mhz = abs(samples[0]["J_eff_mhz"])                        # Φ=0（最大耦合）
    J_off_mhz = abs(samples[-1]["J_eff_mhz"])                      # Φ=0.5Φ0（最小耦合）
    off_ratio = (J_on_mhz / J_off_mhz) if J_off_mhz > 1e-12 else float("inf")
    band = TUNABLE_J_BAND_MHZ
    on_validated = bool(samples[0]["validated"])
    j_ok = bool(max_rel <= 0.05 and on_validated and n_validated >= 3)
    on_in_band = bool(band[0] <= J_on_mhz <= band[1])
    off_ok = bool(off_ratio >= TUNABLE_OFF_RATIO_MIN)
    verdict = "ACCEPT" if (j_ok and on_in_band and off_ok) else "REJECT"

    return {
        "verdict": verdict,
        "E_J1_squid_ghz": EJ1, "E_J2_squid_ghz": EJ2,
        "E_J_max_ghz": squid_ej(EJ1, EJ2, 0.0),
        "E_J_min_ghz": squid_ej(EJ1, EJ2, 0.5),
        "Cc_qc": Cc, "E_J_q_ghz": EJq, "E_C_q_ghz": ECq,
        "J_on_mhz": J_on_mhz, "J_off_mhz": J_off_mhz,
        "off_ratio": (None if off_ratio == float("inf") else float(off_ratio)),
        "off_ratio_min": TUNABLE_OFF_RATIO_MIN,
        "j_band_mhz": list(band),
        "max_J_rel_err": float(max_rel),
        "n_validated": n_validated,
        "valid_detune_ghz": valid_detune,
        "J_double_validated": j_ok,
        "J_on_in_band": on_in_band,
        "tunable_off_ok": off_ok,
        "samples": samples,
        "acceptance": {"J_double_validated": j_ok,
                       "J_on_in_band": on_in_band,
                       "tunable_off": off_ok},
        "note": (f"SQUID E_J(Φ)=sqrt((E_J1+E_J2)²cos²πf+(E_J1−E_J2)²sin²πf) 为精确闭式（golden）；"
                 f"J_qc 在近共振有效区（|Δ_c|≤{valid_detune:.1f}GHz）用 coupler_solver 严格对角化"
                 f"↔解析闭式双验证（容差 5%），深失谐区取解析闭式（设计预算）；"
                 f"J_eff=J_qc²/Δ_c 为经耦合器的二阶虚交换。"
                 f"Cc/结参数为设计参数，不由 GDS 几何反推。LLM 不进判决路径。"),
    }


def run_tunable_selfchecks(verbose: bool = False) -> bool:
    """G3 自检（常驻断言：合法 ACCEPT/ACCEPT；各违规 REJECT）。"""
    ok = True
    msgs: List[Tuple[str, bool]] = []

    def chk(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        msgs.append((name, bool(cond)))

    tc = tunable_coupler_cell({})
    chk("① 合法可调耦合器 DRC ACCEPT（S2 四则 + SQUID 三则）",
        run_tunable_drc(tc)["verdict"] == "ACCEPT")
    chk("② 合法可调耦合器 LVS ACCEPT（SQUID 2 结桥接 + 单连通 + flux 隔离）",
        tunable_coupler_lvs(tc)["verdict"] == "ACCEPT")
    chk("③ SQUID 结数 = 2（区别于 transmon 结）", len(_squid_jjs(tc)) == 2)

    # 少一个 SQUID 结 ⇒ DRC REJECT
    squid_ids = {id(d) for d in _squid_jjs(tc)}
    out = []
    removed = False
    for d in tc:
        if (not removed) and id(d) in squid_ids:
            removed = True
            continue
        out.append(d)
    vo = run_tunable_drc(out)
    chk("④ SQUID 少一结 ⇒ DRC/LVS REJECT（SCD-SQUID-JJ-COUNT）",
        vo["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-SQUID-JJ-COUNT" for v in vo["violations"])
        and any("SQUID-JJ-COUNT" in i for i in tunable_coupler_lvs(out)["issues"]))

    # flux 线贴太近（gap 过小）⇒ DRC REJECT
    near = tunable_coupler_cell({"flux_line_gap": -0.3})
    vn = run_tunable_drc(near)
    chk("⑤ flux 线贴环(gap<0.3/重叠) ⇒ DRC REJECT（SCD-FLUX-LINE-GAP）",
        vn["verdict"] == "REJECT"
        and any(v["rule"] == "SCD-FLUX-LINE-GAP" for v in vn["violations"]))

    # flux 与导体重叠 ⇒ LVS REJECT
    flux_overlap = tunable_coupler_cell({"flux_line_gap": -0.6})
    vl = tunable_coupler_lvs(flux_overlap)
    chk("⑥ flux 线穿导体 ⇒ LVS REJECT（FLUX-SHORT）",
        vl["verdict"] == "REJECT" and any("FLUX-SHORT" in i for i in vl["issues"]))

    # 物理：合法可调耦合器 ACCEPT（J 双验证 + on 落带 + 可关）
    ph = tunable_coupler_physics({})
    chk("⑦ 物理 ACCEPT（J 双验证 rel≤5% + J_on 落带 + 可关比≥阈值）",
        ph["verdict"] == "ACCEPT")

    # SQUID 精确闭式：对称结 f=0.5 时 E_J→0（≈0）；f=0 时 = 2E_J0
    chk("⑧ SQUID 闭式：E_J(0)=2E_J0 · 对称结 E_J(0.5)≈0",
        abs(squid_ej(10.0, 10.0, 0.0) - 20.0) < 1e-9
        and squid_ej(10.0, 10.0, 0.5) < 1e-9
        and abs(squid_ej(10.0, 9.0, 0.5) - 1.0) < 1e-9)

    if verbose:
        for n, c in msgs:
            print(f"  [{'PASS' if c else 'FAIL'}] {n}")
    return ok
