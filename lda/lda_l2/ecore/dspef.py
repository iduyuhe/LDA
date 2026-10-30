"""B3+ · SPEF 级提取（IEEE 1481-1998 子集）—— 把寄生交成**网络**而不是两个标量。

═══════════════════════════════════════════════════════════════════════════════
这一步补的是什么
───────────────────────────────────────────────────────────────────────────────
B3 的 `dsignoff.net_rc` 只给 `{r_ohm, c_ff}` 两个**标量**。真实时序工具要的不是两个数，
而是一个**分布式 RC 网络**：节点 + 每节点的地电容 + 节点对之间的电阻 + 耦合电容。
没有网络，「延迟」只能靠 `R·(C/2+C_load)` 这种整段集中假设，串扰、屏蔽、
局部热点全部不可见，也无法交给任何第三方工具去复查。

本模块给三件：

 ① **提取**：从 B2 真实布出的矩形几何（M3/M4 金属 + VIA2）建分布式 RC 树。
    同一层同一「线中心」上的重叠矩形先按**区间并集去重**（真实的焊盘是画在线上面的，
    逐矩形求和会重复计面积）；长段按 `seg_um` 切分；via 作为电阻接入。
 ② **写出**：SPEF v1.0 文本（`*NAME_MAP` / `*PORTS` / `*D_NET` / `*CONN` / `*CAP` / `*RES`）。
 ③ **读回**：自己的解析器把文本还原成网络，并**逐位相等**（不是"近似相等"）。

═══════════════════════════════════════════════════════════════════════════════
为什么能「逐位相等」
───────────────────────────────────────────────────────────────────────────────
因为数值不写成浮点，而是**整数定点网格**：
    R 以 mΩ 为单位存整数（1e-3 Ω），C 以 aF 为单位存整数（1e-3 fF）
文本按 `"%d.%03d"` 输出三位小数、按三位小数读回 ⇒ 十进制 ↔ 整数**双射**，无舍入。
这不是"运气好"，是**约定**：任何超出网格的数值在解析期就报错，而不是悄悄截断。

═══════════════════════════════════════════════════════════════════════════════
诚实边界（必须随任何引用一起给）
───────────────────────────────────────────────────────────────────────────────
1. 🔴 **本仓没有第三方工具回读验证**。格式按 IEEE 1481-1998 的常见子集写，
   但"能被商业 STA 工具吃下"这件事**未验证**（无 license、无 PDK）。所以只能宣称
   「格式合规 + 自解析可逆」，不能宣称「与商业流程互通」。
2. 🔴 **精度没有提升**：SPEF 只是**搬运算**，不是**改物理**。提取公式仍是 B3 的一阶
   平板 + 边缘修正，仍需 foundry ITF / 3D 场 / 硅实测才能谈精度。SPEF 让结果
   **可交换、可复查**，不让它更准。
3. 🔴 **耦合只算相邻同层平行段**（侧壁平板 `ε₀ε_r·t·L/s`），耦合电容集中挂到
   最近节点；不做全场求解、不做多层耦合、不做屏蔽效应。
4. 🔴 **同层连通只按共线合并**：非共线的同层相接（真实版图常见的 T 型/十字）不建链。
5. 🔴 **via 电阻是常数假设** `R_VIA_OHM`；真实值依赖工艺与孔数。
6. 🔴 节点必须先由 `*CAP` 地电容或 `*CONN` 引入（本子集限制；真实工具允许
   `*RES` 直接引入 0 容节点）—— 遇到这类文件本解析器会报错而不是猜。
7. 🔴 `claimable=False`，**净增 0 锚**（整数定点 ⇒ `resid≡0`）⇒ 门禁形态（E43）。
"""
from __future__ import annotations

import re
from fractions import Fraction

from . import dsignoff as SG
from .ddetail import L_M3, L_M4, L_VIA2, Shape

# ═══════════════════════════════════════════════════════════════════════════
# 约定常量
# ═══════════════════════════════════════════════════════════════════════════
SPEF_VERSION_TAG = "IEEE 1481-1998"
PROGRAM = "LDA dspef"
PROGRAM_VERSION = "0.9.346"

R_GRID = 10 ** 6         # 每 Ω 的定点步数 ⇒ R 存 µΩ 整数（分辨率 1e-6 Ω）
C_GRID = 10 ** 6         # 每 fF 的定点步数 ⇒ C 分辨率 1e-6 fF（量级 ~0.07 fF ⇒ 相对 1e-5）

R_VIA_OHM = 5.0          # 单个 VIA2 的电阻（**演示量级假设**，非工艺数据）
COUPLE_MAX_GAP_UM = 0.50  # 只算间距 ≤ 此值的相邻平行段（µm）
FIXED_DATE = "2026-10-30T00:00:00"   # 🔴 不取墙钟：确定性判据要求两次写出字节相同

LAYER_NAME = {L_M3: "M3", L_M4: "M4"}

# 单位换算表（SPEF 的 `*C_UNIT <num> <unit>`；数表以 fF / Ω 为基准）
_C_UNIT_F = {"FF": 1, "PF": 1000, "NF": 10 ** 6, "UF": 10 ** 9, "MF": 10 ** 12}
_R_UNIT_OHM = {"OHM": 1, "KOHM": 1000, "MOHM": 10 ** 6}
_TIME_UNIT_FS = {"FS": Fraction(1), "PS": Fraction(1000), "NS": Fraction(10 ** 6)}


class SpefError(ValueError):
    """SPEF 文本不合规（本子集口径）。"""


# ═══════════════════════════════════════════════════════════════════════════
# ① 定点数：十进制文本 ⇄ 整数网格（双射，无舍入）
# ═══════════════════════════════════════════════════════════════════════════
def q_r(ohm: float) -> int:
    """Ω → mΩ 整数。"""
    return int(round(float(ohm) * R_GRID))


def q_c(ff: float) -> int:
    """fF → aF 整数。"""
    return int(round(float(ff) * C_GRID))


def fmt_fixed(q: int, grid: int = R_GRID) -> str:
    """整数网格 → 定点十进制文本（恰好 `log10(grid)` 位小数）。"""
    sign = "-" if q < 0 else ""
    q = abs(int(q))
    nd = len(str(grid)) - 1
    return "%s%d.%0*d" % (sign, q // grid, nd, q % grid)


_FIXED_RE = re.compile(r"^([+-]?)(\d+)(?:\.(\d+))?$")


def parse_fixed(tok: str, grid: int = R_GRID) -> int:
    """定点十进制（或科学计数）文本 → 整数网格。超出网格一律报错，不静默截断。"""
    t = str(tok).strip()
    if not t:
        raise SpefError("空数值")
    nd = len(str(grid)) - 1
    if "e" in t or "E" in t:
        try:
            v = Fraction(t) * grid
        except (ValueError, ZeroDivisionError):
            raise SpefError("无法解析数值: %r" % (tok,))
        if v.denominator != 1:
            raise SpefError("数值 %r 超出定点网格（1/%d 单位）" % (tok, grid))
        return int(v)
    m = _FIXED_RE.match(t)
    if not m:
        raise SpefError("无法解析数值: %r" % (tok,))
    sign, ip, fp = m.group(1), m.group(2), (m.group(3) or "")
    if len(fp) > nd:
        if int(fp[nd:] or "0") != 0:
            raise SpefError("数值 %r 精度超出定点网格（%d 位小数）" % (tok, nd))
        fp = fp[:nd]
    fp = (fp + "0" * nd)[:nd]
    q = int(ip) * grid + (int(fp) if fp else 0)
    return -q if sign == "-" else q


# ═══════════════════════════════════════════════════════════════════════════
# ② 几何 → 分布式 RC 网络
# ═══════════════════════════════════════════════════════════════════════════
def _nm(v: float) -> int:
    """µm → nm 整数（全部节点身份用 nm，避免浮点比较）。"""
    return int(round(float(v) * 1000.0))


def _axis(rect) -> tuple:
    """返回 (orient, along0, along1, cross_lo, cross_hi, width)；退化返回 None。"""
    x0, y0, x1, y1 = _nm(rect.x0), _nm(rect.y0), _nm(rect.x1), _nm(rect.y1)
    dx, dy = x1 - x0, y1 - y0
    if dx <= 0 or dy <= 0:
        return None
    if dx >= dy:
        return ("H", x0, x1, y0, y1, dy)
    return ("V", y0, y1, x0, x1, dx)


def _union(ivs: list) -> list:
    """闭区间并集（相邻/相接即合并）。"""
    out: list = []
    for a, b in sorted(ivs):
        if out and a <= out[-1][1]:
            if b > out[-1][1]:
                out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


def _pieces(a0: int, a1: int, juncs, seg_nm: int) -> list:
    """把 [a0,a1] 按 junction 切点 + 等长细分，返回若干 (s,e) nm 区间。"""
    pts = sorted({a0, a1} | {j for j in juncs if a0 < j < a1})
    out: list = []
    for p, q in zip(pts, pts[1:]):
        span = q - p
        n = max(1, -(-span // seg_nm))
        for k in range(n):
            s = p + span * k // n
            e = p + span * (k + 1) // n
            if e > s:
                out.append((s, e))
    return out


def _rsh_of(layer: int) -> float:
    return SG.RSH[LAYER_NAME[layer]]


def _apportion(vals: list, total_q: int, grid: int) -> list:
    """最大余数法：把精确值列表量化成整数，**保证 Σ量化 == total_q**（确定性）。

    逐项 `round()` 会累积误差（8 段各 312.5 mΩ ⇒ 2496 ≠ 2500），而网络总量必须与
    B3 的标量口径**逐位相等**才谈得上对拍，故此处分摊余数而不是各round各的。
    并列时按索引取先者 ⇒ 同一输入两次运行结果相同。
    """
    if not vals:
        return []
    scaled = [v * grid for v in vals]
    base = [int(s) if s >= 0 else -int(-s) for s in scaled]     # 截断（此处恒正）
    rem = [s - b for s, b in zip(scaled, base)]
    diff = int(total_q) - sum(base)
    order = sorted(range(len(vals)), key=lambda i: (-rem[i], i))
    n = len(vals)
    for k in range(diff):
        base[order[k % n]] += 1
    return base


def extract_network(shapes, design: str = "LDA", seg_um: float = 1.0,
                    with_coupling: bool = True, ports=None) -> dict:
    """从真实布线几何建每网的分布式 RC 树。

    `ports` 形如 `{net: {"in": [(x_um,y_um), ...], "out": [(x_um,y_um), ...]}}`，
    用来把引脚坐标吸附成驱动/负载节点（SPEF 的 `*PORTS`/`*CONN` 有真实对象）。

    返回 `{"design", "nets", "merged", "stats"}`；`nets[net]` 含
    `nodes{name:{c(aF)}} / res[[a,b,mΩ]] / coupling[[a,b,aF]] / ports{in,out}`。
    """
    seg_nm = max(1, _nm(seg_um))
    by_net: dict = {}
    for s in shapes:
        if getattr(s, "net", None):
            by_net.setdefault(s.net, []).append(s)

    nets: dict = {}
    merged: dict = {}
    coords: dict = {}
    stats = {"seg_um": seg_um, "naive_rects": 0, "union_rects": 0,
             "naive_len_um": 0.0, "union_len_um": 0.0, "n_via": 0, "dropped": 0}

    for net in sorted(by_net):
        ss = by_net[net]
        metals = [s for s in ss if s.kind == "metal" and s.layer in (L_M3, L_M4)]
        vias = [s for s in ss if s.layer == L_VIA2]
        stats["naive_rects"] += len(metals)

        # —— 按 (层, 朝向, 线中心) 分组 → 区间并集（去重焊盘/重叠）——
        groups: dict = {}
        for r in metals:
            ax = _axis(r)
            if not ax:
                stats["dropped"] += 1
                continue
            orient, a0, a1, c_lo, c_hi, width = ax
            cross = (c_lo + c_hi) // 2
            groups.setdefault((r.layer, orient, cross), []).append((a0, a1, width))
            stats["naive_len_um"] += (a1 - a0) / 1000.0

        keys: dict = {}       # (layer, orient, cross, along) → 节点键
        r_raw: list = []      # [(keyA, keyB, Ω 精确值)]  ← 先不量化
        cap_raw: dict = {}    # key → fF 精确值
        merged_rects: list = []

        for (layer, orient, cross) in sorted(groups):
            ivs = [(a, b) for (a, b, _w) in groups[(layer, orient, cross)]]
            width = max(w for (_a, _b, w) in groups[(layer, orient, cross)])
            uni = _union(ivs)
            for (u0, u1) in uni:
                stats["union_len_um"] += (u1 - u0) / 1000.0
                if orient == "H":
                    merged_rects.append((layer, u0 / 1000.0, (cross - width / 2) / 1000.0,
                                         u1 / 1000.0, (cross + width / 2) / 1000.0))
                else:
                    merged_rects.append((layer, (cross - width / 2) / 1000.0, u0 / 1000.0,
                                         (cross + width / 2) / 1000.0, u1 / 1000.0))
            # junction：落在本线上的 via 中心
            juncs = []
            for v in vias:
                vx, vy = (_nm(v.x0) + _nm(v.x1)) // 2, (_nm(v.y0) + _nm(v.y1)) // 2
                a = vx if orient == "H" else vy
                c = vy if orient == "H" else vx
                if c == cross and any(u0 <= a <= u1 for (u0, u1) in uni):
                    juncs.append(a)
            rsh = _rsh_of(layer)
            width_um = width / 1000.0
            for (u0, u1) in uni:
                for (p, q) in _pieces(u0, u1, juncs, seg_nm):
                    ka = (layer, orient, cross, p)
                    kb = (layer, orient, cross, q)
                    keys[ka] = None
                    keys[kb] = None
                    r_raw.append((ka, kb, rsh * ((q - p) / 1000.0) / width_um))
                    c_half = SG.wire_c((q - p) / 1000.0, width_um) / 2.0
                    cap_raw[ka] = cap_raw.get(ka, 0.0) + c_half
                    cap_raw[kb] = cap_raw.get(kb, 0.0) + c_half

        # —— 量化（最大余数法：逐项之和 == 量化总量，与 B3 标量口径逐位可对拍）——
        metal_r_q = _apportion([x[2] for x in r_raw],
                               q_r(sum(x[2] for x in r_raw)), R_GRID)
        r_edges = [(a, b, rq) for (a, b, _r), rq in zip(r_raw, metal_r_q)]

        # —— 节点命名：按 (层, 朝向, 线中心, 沿线坐标) 排序，确定且可复现 ——
        ordered = sorted(keys)
        name = {k: "%s:%d" % (net, i + 1) for i, k in enumerate(ordered)}
        cap_q = _apportion([cap_raw.get(k, 0.0) for k in ordered],
                           q_c(sum(cap_raw.get(k, 0.0) for k in ordered)), C_GRID)
        nodes = {name[k]: {"c": cq} for k, cq in zip(ordered, cap_q)}

        # —— via：同坐标跨层接一条电阻 ——
        n_via = 0
        for v in vias:
            vx, vy = (_nm(v.x0) + _nm(v.x1)) // 2, (_nm(v.y0) + _nm(v.y1)) // 2
            k3 = (L_M3, "H", vy, vx)
            k4 = (L_M4, "V", vx, vy)
            if k3 in name and k4 in name:
                r_edges.append((k3, k4, q_r(R_VIA_OHM)))
                n_via += 1
        stats["n_via"] += n_via

        res = [[name[a], name[b], r] for (a, b, r) in r_edges]

        # —— 端口吸附（引脚坐标 → 最近节点）——
        pt = {"in": [], "out": []}
        for role in ("in", "out"):
            for (x_um, y_um) in ((ports or {}).get(net, {}).get(role) or []):
                xn, yn = _nm(x_um), _nm(y_um)
                best, bd = None, None
                for k in ordered:
                    layer, orient, cross, along = k
                    px, py = (along, cross) if orient == "H" else (cross, along)
                    d = abs(px - xn) + abs(py - yn)
                    if bd is None or d < bd:
                        best, bd = k, d
                if best is not None:
                    pt[role].append(name[best])

        nets[net] = {"nodes": nodes, "res": res, "coupling": [], "ports": pt,
                     "n_via": n_via}
        merged[net] = merged_rects
        coords[net] = {name[k]: k for k in ordered}
        stats["union_rects"] += len(merged_rects)

    # —— 耦合：不同网上相邻同层平行段（侧壁平板）——
    if with_coupling:
        _add_coupling(nets, merged, coords)

    return {"design": design, "nets": nets, "merged": merged, "stats": stats}


def _add_coupling(nets: dict, merged: dict, coords: dict) -> None:
    """相邻同层 M3 平行段的侧壁耦合，集中挂到最近的既有节点。

    `coords[net][node_name] = (layer, orient, cross_nm, along_nm)` 是**建网时的
    规范坐标**（不是从名字里猜），耦合只挂到已存在的节点上。
    """
    lines: dict = {}
    for net in sorted(merged):
        hs = []
        for (layer, x0, y0, x1, y1) in merged[net]:
            if layer != L_M3:
                continue
            if (x1 - x0) > (y1 - y0):
                hs.append((_nm(y0), _nm(y1), _nm(x0), _nm(x1)))
        if hs:
            lines[net] = hs

    def nearest(net: str, cross_nm: int, along_nm: int):
        best, bd = None, None
        for nm_, (layer, _o, cross, along) in coords[net].items():
            if layer != L_M3:
                continue
            d = abs(cross - cross_nm) + abs(along - along_nm)
            if bd is None or d < bd:
                best, bd = nm_, d
        return best

    names = sorted(lines)
    gap_max = _nm(COUPLE_MAX_GAP_UM)
    for ia in range(len(names)):
        for ib in range(ia + 1, len(names)):
            na, nb = names[ia], names[ib]
            for (ya0, ya1, xa0, xa1) in lines[na]:
                for (yb0, yb1, xb0, xb1) in lines[nb]:
                    gap = abs(ya0 - yb0) - ((ya1 - ya0) + (yb1 - yb0)) // 2
                    if gap <= 0 or gap > gap_max:
                        continue
                    o0, o1 = max(xa0, xb0), min(xa1, xb1)
                    if o1 <= o0:
                        continue
                    area_m2 = (SG.T_METAL_UM * 1e-6) * ((o1 - o0) / 1e9)   # o1-o0 单位 nm
                    c_ff = SG.EPS0 * SG.EPSR_ILD * area_m2 / (gap / 1e9) * 1e15
                    c_aF = q_c(c_ff)
                    if c_aF <= 0:
                        continue
                    mid = (o0 + o1) // 2
                    ka = nearest(na, (ya0 + ya1) // 2, mid)
                    kb = nearest(nb, (yb0 + yb1) // 2, mid)
                    if ka and kb:
                        nets[na]["coupling"].append([ka, kb, c_aF])
                        nets[nb]["coupling"].append([kb, ka, c_aF])


# ═══════════════════════════════════════════════════════════════════════════
# ③ 网络总量（供与 B3 的标量口径对拍）
# ═══════════════════════════════════════════════════════════════════════════
def net_totals(net: dict) -> dict:
    """网络的总电阻（金属 / via 分开报）与总电容（地 / 耦合分开报）。"""
    r_all = sum(r for (_a, _b, r) in net["res"]) / R_GRID
    n_via = int(net.get("n_via") or 0)
    r_via = n_via * R_VIA_OHM
    c_gnd = sum(v["c"] for v in net["nodes"].values()) / C_GRID
    c_cpl = sum(c for (_a, _b, c) in net["coupling"]) / C_GRID
    return {"r_ohm": r_all, "r_metal_ohm": r_all - r_via, "r_via_ohm": r_via,
            "n_via": n_via, "c_gnd_ff": c_gnd, "c_cpl_ff": c_cpl,
            "c_total_ff": c_gnd + c_cpl}


def net_decl_total(net: dict) -> int:
    """SPEF `*D_NET` 的 total：地电容和 + 耦合电容和（**耦合计全值，不折半**）。

    约定显式写明：IEEE 1481 未强制折半，各工具不同；本仓取「全值」并在此单点定义，
    解析器把 total 与 `Σ地 + Σ耦合` 对比即可发现约定不一致。
    """
    return sum(v["c"] for v in net["nodes"].values()) + sum(c for (_a, _b, c) in net["coupling"])


# ═══════════════════════════════════════════════════════════════════════════
# ④ Elmore（在**网络**上求，不是在两个标量上求）
# ═══════════════════════════════════════════════════════════════════════════
def elmore_network(net: dict, driver: str = None, c_load_ff: float = 0.0,
                   loads=None) -> dict:
    """树上 Elmore：`τ_i = Σ_{边 k ∈ 驱动→i 路径} R_k · C_downstream(k)`。

    单位：R 取 Ω、C 取 fF ⇒ `Ω·fF = fs`（1e-15 s）。**返回 fs**。
    耦合电容按**两端各半**计入节点电容（约定；显式写明而非隐含）。
    """
    nodes = net["nodes"]
    if not nodes:
        raise ValueError("空网络")
    if driver is None:
        pins = (net.get("ports") or {}).get("in") or []
        driver = pins[0] if pins else sorted(nodes)[0]
    if driver not in nodes:
        raise ValueError("驱动节点不在网络内: %r" % (driver,))

    adj = {n: [] for n in nodes}
    for a, b, r in net["res"]:
        if a not in adj or b not in adj:
            raise ValueError("电阻引用未知节点: %r-%r" % (a, b))
        if a == b:
            raise ValueError("自环电阻: %r" % (a,))
        adj[a].append((b, r))
        adj[b].append((a, r))

    cap = {n: float(v["c"]) / C_GRID for n, v in nodes.items()}
    for a, b, c in (net.get("coupling") or []):
        half = float(c) / C_GRID / 2.0
        if a in cap:
            cap[a] += half
        if b in cap:
            cap[b] += half

    parent = {driver: (None, 0.0)}
    order = [driver]
    qi = 0
    while qi < len(order):
        u = order[qi]
        qi += 1
        for v, r in adj[u]:
            if v in parent:
                continue
            parent[v] = (u, float(r) / R_GRID)
            order.append(v)
    if len(parent) != len(nodes):
        raise ValueError("网络不连通：%d/%d 可达" % (len(parent), len(nodes)))

    down = {n: cap.get(n, 0.0) for n in nodes}
    if loads is None:
        loads = (net.get("ports") or {}).get("out") or []
    for n in loads:
        if n in down:
            down[n] += c_load_ff
    for n in reversed(order[1:]):
        down[parent[n][0]] += down[n]

    tau = {driver: 0.0}
    for n in order[1:]:
        p, r = parent[n]
        tau[n] = tau[p] + r * down[n]
    return {"driver": driver, "tau_fs": tau,
            "max_fs": max(tau.values()) if tau else 0.0,
            "n_nodes": len(nodes), "n_edges": len(net["res"])}


def build_wire_network(length_um: float, width_um: float, n: int,
                       net: str = "w0", layer: int = L_M3) -> dict:
    """单根直导线的控制用例（走**同一条**提取路径，不另写特例）。"""
    sh = Shape(layer, 0.0, 0.0, float(length_um), float(width_um), net=net, kind="metal")
    mid = float(width_um) / 2.0
    return extract_network(
        [sh], design="WIRE", seg_um=float(length_um) / max(1, n),
        with_coupling=False,
        ports={net: {"in": [(0.0, mid)], "out": [(float(length_um), mid)]}})


# ═══════════════════════════════════════════════════════════════════════════
# ⑤ 写出 SPEF
# ═══════════════════════════════════════════════════════════════════════════
def spef_write(network: dict, design: str = None, date: str = FIXED_DATE,
               version: str = PROGRAM_VERSION) -> str:
    """网络 → SPEF 文本。**确定性**：日期不取墙钟，一切按名排序。"""
    nets = network["nets"]
    design = design or network.get("design") or "LDA"

    idx: dict = {}
    for net in sorted(nets):
        if net not in idx:
            idx[net] = len(idx) + 1
    for net in sorted(nets):
        for nd in sorted(nets[net]["nodes"]):
            if nd not in idx:
                idx[nd] = len(idx) + 1

    out = [
        '*SPEF "%s"' % SPEF_VERSION_TAG,
        '*DESIGN "%s"' % design,
        '*DATE "%s"' % date,
        '*VENDOR "LDA"',
        '*PROGRAM "%s"' % PROGRAM,
        '*VERSION "%s"' % version,
        '*DESIGN_FLOW "PIN_CAP NONE"',
        "*DIVIDER /",
        "*DELIMITER :",
        "*BUS_DELIMITER [ ]",
        "*T_UNIT 1 PS",
        "*C_UNIT 1 FF",
        "*R_UNIT 1 OHM",
        "*L_UNIT 1 HENRY",
        "*NAME_MAP",
    ]
    for nm, k in idx.items():
        out.append("*%d %s" % (k, nm))

    ports = []
    for net in sorted(nets):
        for role in ("in", "out"):
            for nd in nets[net]["ports"].get(role) or []:
                if nd in idx:
                    ports.append((nd, "I" if role == "in" else "O", net))
    if ports:
        out.append("*PORTS")
        for nd, direction, net in ports:
            out.append("%s %s *%d" % (nd, direction, idx[net]))

    for net in sorted(nets):
        d = nets[net]
        out.append("*D_NET *%d %s" % (idx[net], fmt_fixed(net_decl_total(d), C_GRID)))
        out.append("*CONN")
        for role in ("in", "out"):
            for nd in d["ports"].get(role) or []:
                if nd in idx:
                    out.append("*P *%d %s" % (idx[nd], "I" if role == "in" else "O"))
        out.append("*CAP")
        k = 0
        for nd in sorted(d["nodes"]):
            k += 1
            out.append("%d *%d %s" % (k, idx[nd], fmt_fixed(d["nodes"][nd]["c"], C_GRID)))
        for (a, b, c) in sorted(d["coupling"]):
            k += 1
            out.append("%d *%d *%d %s" % (k, idx[a], idx[b], fmt_fixed(c, C_GRID)))
        if d["res"]:
            out.append("*RES")
            for i, (a, b, r) in enumerate(sorted(d["res"]), 1):
                out.append("%d *%d *%d %s" % (i, idx[a], idx[b], fmt_fixed(r, R_GRID)))
        out.append("*END")
    return "\n".join(out) + "\n"


# ═══════════════════════════════════════════════════════════════════════════
# ⑥ 读回 SPEF
# ═══════════════════════════════════════════════════════════════════════════
_NAMEDIRECTIVES = ("*SPEF", "*DESIGN", "*DATE", "*VENDOR", "*PROGRAM", "*VERSION",
                   "*DESIGN_FLOW", "*DIVIDER", "*DELIMITER", "*BUS_DELIMITER",
                   "*L_UNIT", "*T_UNIT", "*C_UNIT", "*R_UNIT")


def _is_directive(ln: str) -> bool:
    """`*<字母>` 才是指令；`*<数字>` 是 NAME_MAP 引用（在 *PORTS/数据区里出现）。"""
    if not ln.startswith("*"):
        return False
    return bool(re.match(r"^\*[A-Za-z_]", ln.split()[0]))


def _scale_of(args: list, table: dict, what: str):
    if len(args) != 2:
        raise SpefError("*%s_UNIT 需要 2 个字段，得到 %d" % (what, len(args)))
    try:
        num = Fraction(args[0])
    except (ValueError, ZeroDivisionError):
        raise SpefError("*%s_UNIT 的倍率不是数: %r" % (what, args[0]))
    unit = args[1].upper()
    if unit not in table:
        raise SpefError("未知 *%s_UNIT 单位: %r" % (what, unit))
    return num * table[unit]


def _resolve(tok: str, name_map: dict) -> str:
    """`*<数字>` 是 NAME_MAP 引用：未定义即报错（不把 `*9` 当成名字混过去）。"""
    if tok is None:
        return None
    if tok not in name_map and re.match(r"^\*\d+$", tok):
        raise SpefError("未定义的 NAME_MAP 引用: %s" % tok)
    return name_map.get(tok, tok)


def spef_parse(text: str) -> dict:
    """SPEF 文本 → 网络（结构与 `extract_network` 同形，另含 `total_*`）。"""
    lines = []
    for raw in text.splitlines():
        s = raw.split("//")[0].strip()
        if s:
            lines.append(s)

    design = None
    c_scale = None
    r_scale = None
    name_map: dict = {}
    nets: dict = {}
    top_ports: dict = {}
    cur = None
    sec = None
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        i += 1
        if _is_directive(ln):
            head = ln.split()[0]
            args = ln.split()[1:]

            if head == "*NAME_MAP":
                while i < n and re.match(r"^\*\d+\s", lines[i]):
                    mm = re.match(r"^\*(\d+)\s+(\S+)$", lines[i])
                    i += 1
                    if not mm:
                        raise SpefError("NAME_MAP 行格式错: %r" % lines[i - 1])
                    name_map["*" + mm.group(1)] = mm.group(2)
                continue
            if head == "*SPEF":
                continue
            if head == "*DESIGN":
                design = " ".join(args).strip('"')
                continue
            if head == "*C_UNIT":
                c_scale = _scale_of(args, _C_UNIT_F, "C")
                continue
            if head == "*R_UNIT":
                r_scale = _scale_of(args, _R_UNIT_OHM, "R")
                continue
            if head in _NAMEDIRECTIVES:
                continue
            if head == "*PORTS":
                while i < n and not _is_directive(lines[i]):
                    f = lines[i].split()
                    i += 1
                    if len(f) < 2:
                        raise SpefError("*PORTS 行字段不足: %r" % " ".join(f))
                    pname = _resolve(f[0], name_map)
                    direction = f[1].upper()
                    netname = _resolve(f[2], name_map) if len(f) > 2 else None
                    if direction not in ("I", "O", "B"):
                        raise SpefError("*PORTS 方向非法: %r" % f[1])
                    top_ports.setdefault(netname, {"in": [], "out": []})
                    top_ports[netname]["in" if direction == "I" else "out"].append(pname)
                continue
            if head == "*D_NET":
                if len(args) != 2:
                    raise SpefError("*D_NET 需要 2 个字段: %r" % ln)
                if c_scale is None:
                    raise SpefError("缺少 *C_UNIT，无法解释电容值")
                netname = _resolve(args[0], name_map)
                if netname in nets:
                    raise SpefError("重复 *D_NET: %s" % netname)
                cur = {"nodes": {}, "res": [], "coupling": [],
                       "ports": {"in": [], "out": []},
                       "total_declared": _to_grid(args[1], c_scale, C_GRID)}
                nets[netname] = cur
                sec = None
                continue
            if head in ("*P", "*I"):
                if cur is None or sec != "conn":
                    raise SpefError("*P/*I 必须位于 *D_NET 内的 *CONN 段")
                if len(args) < 2:
                    raise SpefError("*CONN 行字段不足: %r" % ln)
                nd = _resolve(args[0], name_map)
                direction = args[1].upper()
                cur["ports"]["in" if direction.startswith("I") else "out"].append(nd)
                cur["nodes"].setdefault(nd, {"c": 0})
                continue
            if head == "*CONN":
                sec = "conn"
                continue
            if head == "*CAP":
                sec = "cap"
                continue
            if head == "*RES":
                sec = "res"
                continue
            if head == "*END":
                if cur is None:
                    raise SpefError("*END 出现在 *D_NET 之外")
                cur = None
                sec = None
                continue
            raise SpefError("未支持的 SPEF 段/指令: %s" % head)

        # —— 段内数据行 ——
        if cur is None:
            if re.match(r"^\*\d+\s", ln):
                raise SpefError("NAME_MAP 条目出现在 *NAME_MAP 段之外: %r" % ln)
            raise SpefError("数据行出现在 *D_NET 之外: %r" % ln)
        f = ln.split()
        if sec == "cap":
            if len(f) == 3:
                nd = _resolve(f[1], name_map)
                v = _to_grid(f[2], c_scale, C_GRID)
                if v < 0:
                    raise SpefError("*CAP 出现负电容: %r" % ln)
                # 地电容条目**就是**节点的定义（本子集允许 CAP/CONN 引入节点）
                cur["nodes"].setdefault(nd, {"c": 0})["c"] += v
            elif len(f) == 4:
                a, b = _resolve(f[1], name_map), _resolve(f[2], name_map)
                v = _to_grid(f[3], c_scale, C_GRID)
                if v < 0:
                    raise SpefError("*CAP 出现负电容: %r" % ln)
                # 耦合的另一端可能属于**别的网**（该网的 *D_NET 尚未读到）
                # ⇒ 此处只存，全部读完后统一校验端点存在性。
                cur["coupling"].append([a, b, v])
            else:
                raise SpefError("*CAP 行字段数错: %r" % ln)
        elif sec == "res":
            if len(f) != 4:
                raise SpefError("*RES 行字段数错: %r" % ln)
            a, b = _resolve(f[1], name_map), _resolve(f[2], name_map)
            if r_scale is None:
                raise SpefError("缺少 *R_UNIT，无法解释电阻值")
            v = _to_grid(f[3], r_scale, R_GRID)
            if v <= 0:
                raise SpefError("*RES 出现非正电阻: %r" % ln)
            for x in (a, b):
                if x not in cur["nodes"]:
                    raise SpefError("*RES 引用未定义节点: %s" % x)
            if a == b:
                raise SpefError("*RES 自环: %s" % a)
            cur["res"].append([a, b, v])
        else:
            raise SpefError("数据行不在 *CAP/*RES/*CONN 段内: %r" % ln)

    if cur is not None:
        raise SpefError("文件在 *D_NET 内结束，缺少 *END")
    if c_scale is None or r_scale is None:
        raise SpefError("缺少 *C_UNIT 或 *R_UNIT")

    # —— 跨网耦合的端点校验（读完全部 *D_NET 才有全局节点表）——
    owner: dict = {}
    for net, d in nets.items():
        for nd in d["nodes"]:
            owner[nd] = net
    for net, d in nets.items():
        for (a, b, _c) in d["coupling"]:
            for x in (a, b):
                if x not in owner:
                    raise SpefError("耦合电容引用未知节点: %s（网 %s）" % (x, net))
            if net not in (owner[a], owner[b]):
                raise SpefError("耦合电容 %s-%s 与本网 %s 无关" % (a, b, net))

    for net, d in nets.items():
        tp = top_ports.get(net) or {}
        for role in ("in", "out"):
            for nd in tp.get(role) or []:
                if nd in d["nodes"] and nd not in d["ports"][role]:
                    d["ports"][role].append(nd)
        d["total_computed"] = sum(v["c"] for v in d["nodes"].values()) + \
            sum(c for (_a, _b, c) in d["coupling"])

    return {"design": design, "nets": nets, "ports": top_ports}


def _to_grid(tok: str, scale, grid: int) -> int:
    """按单位倍率把文本换算到网格整数；不可整除即报错（不静默舍入）。"""
    raw = Fraction(parse_fixed(tok, grid))
    v = raw * Fraction(scale)
    if v.denominator != 1:
        raise SpefError("数值 %r 在单位倍率 %s 下不能精确落到定点网格" % (tok, scale))
    return int(v)


# ═══════════════════════════════════════════════════════════════════════════
# ⑦ 对拍
# ═══════════════════════════════════════════════════════════════════════════
def net_signature(net: dict) -> tuple:
    """网络的规范形（顺序无关），供 round-trip 逐位比较。"""
    nodes = tuple(sorted((k, int(v["c"])) for k, v in net["nodes"].items()))
    res = tuple(sorted((tuple(sorted((a, b))), int(r)) for a, b, r in net["res"]))
    cpl = tuple(sorted((tuple(sorted((a, b))), int(c)) for a, b, c in net["coupling"]))
    ports = tuple(sorted((role, nd) for role in ("in", "out")
                         for nd in (net.get("ports") or {}).get(role) or []))
    return (nodes, res, cpl, ports)


def compare_networks(a: dict, b: dict) -> list:
    """两个网络逐网、逐字段比较，返回人类可读的差异列表（空 = 完全一致）。"""
    diffs = []
    na, nb = a["nets"], b["nets"]
    for net in sorted(set(na) | set(nb)):
        if net not in na:
            diffs.append("网 %s 只在 B 侧" % net)
            continue
        if net not in nb:
            diffs.append("网 %s 只在 A 侧" % net)
            continue
        sa, sb = net_signature(na[net]), net_signature(nb[net])
        if sa[0] != sb[0]:
            da = dict(sa[0])
            db = dict(sb[0])
            for k in sorted(set(da) | set(db)):
                if da.get(k) != db.get(k):
                    diffs.append("%s 节点 %s 电容 %r vs %r" % (net, k, da.get(k), db.get(k)))
        if sa[1] != sb[1]:
            diffs.append("%s 电阻集不同：A=%d 条 B=%d 条" % (net, len(sa[1]), len(sb[1])))
        if sa[2] != sb[2]:
            diffs.append("%s 耦合集不同：A=%d 条 B=%d 条" % (net, len(sa[2]), len(sb[2])))
        if sa[3] != sb[3]:
            diffs.append("%s 端口不同：A=%r B=%r" % (net, sa[3], sb[3]))
    return diffs


# ═══════════════════════════════════════════════════════════════════════════
# ⑧ 诚实清单
# ═══════════════════════════════════════════════════════════════════════════
SPEF_DISCLOSURE = {
    "what": "SPEF v1.0 子集：分布式 RC 网络提取 + 写出 + 自解析（整数定点，逐位可逆）",
    "claimable": False,
    "not_signoff": True,
    "no_third_party_roundtrip": True,
    "limits": [
        "未经任何商业 STA / 提取工具回读验证（无 license、无 PDK）⇒ 只能宣称「格式合规 + 自解析可逆」，不能宣称「与商业流程互通」",
        "精度未提升：提取公式仍是 B3 一阶平板+边缘修正；SPEF 只搬运算不改物理",
        "耦合只算相邻同层平行段（侧壁平板），集中挂最近节点；无多层耦合、无屏蔽效应、无 3D 场",
        "同层连通只按共线合并；非共线同层相接（T 型/十字）不建链",
        "via 电阻为常数假设 R_VIA_OHM，非工艺数据",
        "节点须由 *CAP 或 *CONN 先引入（本子集限制；真实工具允许 *RES 引入 0 容节点）",
        "不含 *L（电感）、不含 reduced model、不含 *POWER_NETS、不含 *DELAY/*VARIATION",
        "total 电容约定为「地电容和 + 耦合全值」（不折半）；各工具约定不同，跨工具比对前须先对齐",
    ],
}
