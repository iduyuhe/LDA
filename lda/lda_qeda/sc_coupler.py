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
