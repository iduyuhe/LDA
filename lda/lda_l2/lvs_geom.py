"""LDA L2 · LVS 器件参数几何回提（G4 · 版图↔原理图双向一致 · v0.9.128）。

**为什么需要它（问题陈述）**：
`lvs.py` 的 `extract_layout_netlist` 只从布线几何恢复**连接关系**，器件
`kind` 与 `params` **全部来自原理图声明**（`lvs.py:419-420`）——
⇒ 版图侧只有「实例存在性」，**没有任何几何尺寸回提**。
后果：版图把波导画成 30µm 而原理图声明 20µm、把环半径画成 8µm 而声明 10µm，
**LVS 一律 ACCEPT**（连接关系没变）。这正是 D4 定义「几何↔原理图双向一致」
缺失的那一半 —— 交付物在「连接对」但「尺寸错」时不可信。

**本模块做什么**：
从**版图几何**（`chip_layout_export.device_geom_of` 的绝对坐标 `Geom` 列表）
**独立测量**器件参数，与 IR 声明的 `params` 逐字段比对，产出
`device_param_mismatch` 违规（由 `lvs.run_lvs` 注入判决）。

🔴 **方法学独立性的诚实边界（必读）**：
  - 本模块的「测量」是 **几何 → 尺寸的逆映射**，与 `gds_export.geometry_desc`
    的「尺寸 → 几何的正向映射」是**两段不同的代码**（不同文件、不同作者路径），
    故可检出「几何被改动而 IR 未同步」这一真实失配；
  - ⚠️ **但两者共享「几何约定」这一先验知识**（例如「Waveguide 的 PATH 从
    x=0 到 x=length」）。因此这是 **代码路径级独立**，**不是**物理方法级独立 ——
    若正向约定本身写错，本模块会**同样错**（自洽却全错，参见 U10 血案 13）。
    ⇒ 本模块**不构成对几何约定的验证**；它验证的是「版图几何与 IR 声明是否
    一致」，不是「几何约定是否符合 foundry 事实」（后者需真 PDK deck，属 D5）。
  - 测量一律使用**平移不变量**（距离 / 跨度 / 半径），故**不依赖 placement 原点**；
    ⚠️ 当前 `device_geom_of` 忽略旋转（只用 placement 的前两维）⇒ 本模块同样
    **不含旋转不变量**（器件带旋转时 x 跨度类度量会失真）。当前流水线 rot ≡ 0。

**覆盖范围（首版 · 实测驱动）**：7 类器件 / 7 个参数 —— 全部为几何**唯一可反推**者：

| kind | 回提参数 | 测量依据（实测几何） |
|---|---|---|
| `Waveguide` | `length` | 单 PATH 首末点距离 |
| `GratingCoupler` | `L` | 单 PATH 首末点距离（`device_geom_of` 只画输入波导） |
| `DirectionalCoupler` | `Lc` | 双 PATH 整体 x 跨度 |
| `RingResonator` | `R` | 环形 PATH 顶点 → 形心距离 |
| `RingAddDrop` | `R` | 同上 |
| `MMI` | `L_mmi` | 多模区 BOUNDARY（4 点、y 跨度最大）的 x 跨度 |
| `SymmetricYBranch` | `arm_length` | 两条 arm PATH 的端点距离 |

**显式不覆盖（不谎报覆盖率）**：
  - `MZI` / `MMIC` / `PhaseShifter` / `Splitter` / `MziModulator` /
    `Photodetector` —— `device_geom_of` 对它们**直接 raise**（无版图几何）
    ⇒ 记入 `geom_failed`，在报告中如实标注「几何不可生成」；
  - `GratingCoupler` 的 `Lambda`/`duty`/`n_tooth` —— 齿未绘制 ⇒ 几何不可反推；
  - `RingResonator`/`RingAddDrop` 的 `gap`/`wg_width` —— 需串联三项间接推算，
    鲁棒性不足，登记为 v2 候选（**不硬凑**）；
  - `BraggMirror` 的 `periods`/`corrugation` —— 侧壁调制段结构复杂，v2 候选；
  - `SymmetricYBranch` 的 `split_angle` —— 需区分 taper 与 arm，v2 候选；
  - 全部器件的 `width`/`W_mmi`/`L_tap`/`L_out` 等 —— v2 候选。

判决口径：全死标量（坐标几何 + 距离比对），LLM 不进判决路径。
主权：C 级自写零依赖（仅标准库）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

# 几何元组（与 chip_layout_export.Geom 同构）：
#   ("P", layer, width_um, pts)  —— PATH
#   ("B", layer, None, pt)       —— BOUNDARY（展平单环点列）
Geom = Tuple


# ---------------------------------------------------------------------------
# 1) 几何访问助手（不依赖任何正向映射代码）
# ---------------------------------------------------------------------------
def _paths(geoms: Sequence[Geom]) -> List[Sequence[Tuple[float, float]]]:
    """PATH 点列（"P"）。"""
    return [g[3] for g in geoms if g and g[0] == "P"]


def _boundaries(geoms: Sequence[Geom]) -> List[Sequence[Tuple[float, float]]]:
    """BOUNDARY 点列（"B"）。"""
    return [g[3] for g in geoms if g and g[0] == "B"]


def _dist(p: Tuple[float, float], q: Tuple[float, float]) -> float:
    """两点欧氏距离（平移不变量）。"""
    return math.hypot(q[0] - p[0], q[1] - p[1])


def _x_span(pts: Sequence[Tuple[float, float]]) -> float:
    """点列 x 跨度（平移不变量）。"""
    xs = [p[0] for p in pts]
    return max(xs) - min(xs)


def _y_span(pts: Sequence[Tuple[float, float]]) -> float:
    """点列 y 跨度（平移不变量）。"""
    ys = [p[1] for p in pts]
    return max(ys) - min(ys)


def _centroid(pts: Sequence[Tuple[float, float]]) -> Tuple[float, float]:
    """点列形心。"""
    n = len(pts)
    if n == 0:
        return (0.0, 0.0)
    return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)


# ---------------------------------------------------------------------------
# 2) 各 kind 的测量器（输入 = 该器件的全部 Geom，输出 = 尺寸 µm | None）
# ---------------------------------------------------------------------------
def _m_single_path_length(geoms: Sequence[Geom]) -> Optional[float]:
    """单 PATH 端点距离（Waveguide.length / GratingCoupler.L）。"""
    p = _paths(geoms)
    if len(p) != 1 or len(p[0]) < 2:
        return None
    return _dist(p[0][0], p[0][-1])


def _m_dc_Lc(geoms: Sequence[Geom]) -> Optional[float]:
    """双 PATH 整体 x 跨度（DirectionalCoupler.Lc）。"""
    p = _paths(geoms)
    if len(p) != 2:
        return None
    pts = list(p[0]) + list(p[1])
    return _x_span(pts) if pts else None


def _m_ring_R(geoms: Sequence[Geom]) -> Optional[float]:
    """环形 PATH 顶点 → 形心距离（RingResonator.R / RingAddDrop.R）。

    取**点数最多**的 PATH（环形离散点数 ≫ bus 的 2 点），不硬编码索引。
    离散顶点均匀采样于半径 R 的圆上 ⇒ 各顶点到形心距离相等 = R（机器精度）。
    """
    p = _paths(geoms)
    if not p:
        return None
    ring = max(p, key=len)
    if len(ring) < 8:
        return None
    c = _centroid(ring)
    return sum(_dist(v, c) for v in ring) / len(ring)


def _m_mmi_Lmmi(geoms: Sequence[Geom]) -> Optional[float]:
    """多模区 BOUNDARY 的 x 跨度（MMI.L_mmi）。

    多模区是**矩形**（4 点）且 y 跨度最大 ⇒ 按此二条件选取，不硬编码索引
    （MMI 共 7 个 geom：输入 PATH + 输入 taper B(66) + 多模区 B(4) +
    双输出 taper B(66) + 双输出 PATH）。
    """
    cands = [b for b in _boundaries(geoms) if len(b) == 4]
    if not cands:
        return None
    rect = max(cands, key=_y_span)
    return _x_span(rect)


def _m_ybranch_arm(geoms: Sequence[Geom]) -> Optional[float]:
    """两条 arm PATH 的端点距离（SymmetricYBranch.arm_length）。

    arm PATH = 2 点折线，起点在分叉点、终点在臂端 ⇒ 距离 = arm_length。
    取全部 2 点 PATH 的最大距离（taper 是 BOUNDARY，不参与）。
    """
    p = [q for q in _paths(geoms) if len(q) == 2]
    if not p:
        return None
    return max(_dist(q[0], q[1]) for q in p)


# ---------------------------------------------------------------------------
# 3) 可回提参数表 + 不覆盖表
# ---------------------------------------------------------------------------
#: kind → {声明参数名: 测量器}。**只有列在这里的 (kind, param) 会被比对。**
PARAM_MEASURERS: Dict[str, Dict[str, Any]] = {
    "Waveguide": {"length": _m_single_path_length},
    "GratingCoupler": {"L": _m_single_path_length},
    "DirectionalCoupler": {"Lc": _m_dc_Lc},
    "RingResonator": {"R": _m_ring_R},
    "RingAddDrop": {"R": _m_ring_R},
    "MMI": {"L_mmi": _m_mmi_Lmmi},
    "SymmetricYBranch": {"arm_length": _m_ybranch_arm},
}

#: 全部测量器名（供 smoke / 审计遍历，避免调用方硬编码名单）。
#: 🔴 一致性由 `run_lvs_geom_smoke` 判据把关：`PARAM_MEASURERS` 引用的每个
#: 测量器 `__name__` 必须落在此清单内（防「加了测量器忘登记」）。
MEASURER_NAMES: Tuple[str, ...] = (
    "_m_single_path_length",
    "_m_dc_Lc",
    "_m_ring_R",
    "_m_mmi_Lmmi",
    "_m_ybranch_arm",
)

#: 明确**不覆盖**的 (kind, param) → 原因（防「覆盖率」被误读为「全参数已验」）。
#: 未列在此表、又不在 PARAM_MEASURERS 的声明参数，一律记为「v2 候选」。
UNRECOVERABLE_PARAMS: Dict[str, List[Tuple[str, str]]] = {
    "GratingCoupler": [
        ("Lambda", "光栅齿未绘制（device_geom_of 只画输入波导）⇒ 几何不可反推"),
        ("duty", "同上"),
        ("n_tooth", "同上"),
    ],
    "RingResonator": [
        ("gap", "需由 bus 偏移串推（off=R+w/2+gap），鲁棒性不足 ⇒ v2 候选"),
        ("wg_width", "同上"),
    ],
    "RingAddDrop": [
        ("gap", "同上"),
        ("wg_width", "同上"),
    ],
    "BraggMirror": [
        ("periods", "侧壁调制段（14 个 4 点 BOUNDARY）结构复杂 ⇒ v2 候选"),
        ("corrugation", "同上"),
    ],
    "SymmetricYBranch": [
        ("split_angle", "需区分 taper 与 arm 起点 ⇒ v2 候选"),
    ],
}

#: 几何不可生成的 kind（device_geom_of 直接 raise）—— 报告中如实标注。
GEOM_UNSUPPORTED_KINDS = (
    "MZI", "MMIC", "PhaseShifter", "Splitter", "MziModulator",
    "Photodetector",
)


def measure_device_params(kind: str,
                          geoms: Sequence[Geom]) -> Dict[str, Optional[float]]:
    """从几何独立测量该 kind 的**全部**可回提参数。

    返回 {param: 测量值 µm | None}；None = 几何形态不满足测量前提
    （**不静默跳过**，由调用方登记为该参数的测量失败）。

    🔴 **测量独立性（机器可证）**：本函数与 `MEASURER_NAMES` 下的全部测量器
    **只接受 `geoms` 一个输入**（签名可断言），且源码不出现 `.params` /
    `declared` / `link` ⇒ **结构上无法读取 IR 声明**。这是「回提独立于声明」
    的机器验证依据，而非仅靠注释声称（判据见 `run_lvs_geom_smoke` ⑧）。
    """
    table = PARAM_MEASURERS.get(kind)
    if not table:
        return {}
    out: Dict[str, Optional[float]] = {}
    for param, fn in table.items():
        try:
            out[param] = fn(geoms)
        except Exception:                       # 测量器异常 ⇒ 记为不可测，不传播
            out[param] = None
    return out


# ---------------------------------------------------------------------------
# 4) 主入口：逐器件回提 + 与 IR 声明比对
# ---------------------------------------------------------------------------
def extract_layout_params(link, placement, wg_width: float = 0.5,
                          geom_of=None,
                          rel_tol: float = 1e-6,
                          abs_tol: float = 1e-9) -> Dict[str, Any]:
    """器件参数几何回提 + 比对（G4）。

    参数：
      link/placement : 与 run_lvs 同源
      wg_width       : 传给 geom_of 的默认波导宽（几何生成的兜底参数）
      geom_of        : 几何生成回调 (component, placement, wg_width) → [Geom]。
                       None ⇒ 惰性取 `chip_layout_export.device_geom_of`
                       （函数内 import，避免模块级循环依赖）。
      rel_tol/abs_tol: 比对容差。默认 (1e-6, 1e-9) —— 吸收浮点噪声
                       （cos/sin 离散），**远低于任何工艺意义**，故不掩盖真失配
                       （真失配是 µm 量级，见判据实测）。

    返回：
      {
        "devices": {inst: {"kind", "declared", "measured", "deltas", "ok"}},
        "violations": [{"inst","kind","param","declared","measured",
                        "abs_diff","rel_diff"}],
        "n_devices": int, "n_devices_checked": int,
        "n_params_checked": int,        # 实际比对成功的 (器件,参数) 对
        "n_params_recoverable": int,    # 落在可回提清单内的声明参数数
        "n_params_declared": int,       # 全部声明参数数
        "coverage_by_table": float,     # n_params_checked / n_params_recoverable
        "coverage_declared": float,     # n_params_checked / n_params_declared
        "geom_failed": {inst: 原因},
        "unrecoverable": [[kind, param, 原因], ...],
        "honest_note": str,
      }
    """
    if geom_of is None:
        from lda_l2.chip_layout_export import device_geom_of as geom_of  # noqa

    devices: Dict[str, Dict[str, Any]] = {}
    violations: List[Dict[str, Any]] = []
    geom_failed: Dict[str, str] = {}
    unrecoverable: List[List[str]] = []
    n_declared = 0
    n_recoverable = 0
    n_checked = 0

    for c in link.ir.components:
        declared = {k: float(v) for k, v in dict(c.params).items()
                    if isinstance(v, (int, float))}
        n_declared += len(declared)
        table = PARAM_MEASURERS.get(c.kind, {})
        decl_recoverable = [p for p in declared if p in table]
        n_recoverable += len(decl_recoverable)

        # 补登记「声明了但本模块不覆盖」的参数（去重）
        for p in declared:
            if p not in table:
                reason = next((r for (q, r) in
                               UNRECOVERABLE_PARAMS.get(c.kind, []) if q == p),
                              "未纳入首版可回提清单 ⇒ v2 候选")
                row = [c.kind, p, reason]
                if row not in unrecoverable:
                    unrecoverable.append(row)

        try:
            geoms = geom_of(c, placement, wg_width)
        except Exception as exc:
            geom_failed[c.id] = f"{type(exc).__name__}: {exc}"
            devices[c.id] = {"kind": c.kind, "declared": declared,
                             "measured": {}, "deltas": {}, "ok": False,
                             "geom_error": geom_failed[c.id]}
            continue

        measured = measure_device_params(c.kind, geoms)
        deltas: Dict[str, float] = {}
        okflags: Dict[str, bool] = {}
        measure_failed = [p for p in decl_recoverable
                          if measured.get(p) is None]
        for param in decl_recoverable:
            mv = measured.get(param)
            if mv is None:
                continue                       # 测量失败：不比对、不虚报通过
            dv = declared[param]
            d = mv - dv
            ok = math.isclose(mv, dv, rel_tol=rel_tol, abs_tol=abs_tol)
            deltas[param] = d
            okflags[param] = ok
            n_checked += 1
            if not ok:
                rel = abs(d) / abs(dv) if dv != 0 else float("inf")
                violations.append({
                    "inst": c.id, "kind": c.kind, "param": param,
                    "declared": dv, "measured": mv,
                    "abs_diff": d, "rel_diff": rel,
                })
        devices[c.id] = {"kind": c.kind, "declared": declared,
                         "measured": measured, "deltas": deltas, "ok": okflags,
                         "measure_failed": measure_failed}

    cov_table = (n_checked / n_recoverable) if n_recoverable else 1.0
    cov_decl = (n_checked / n_declared) if n_declared else 1.0
    n_dev_checked = sum(1 for v in devices.values() if v.get("ok"))
    return {
        "devices": devices,
        "violations": violations,
        "n_devices": len(list(link.ir.components)),
        "n_devices_checked": n_dev_checked,
        "n_params_checked": n_checked,
        "n_params_recoverable": n_recoverable,
        "n_params_declared": n_declared,
        "coverage_by_table": cov_table,
        "coverage_declared": cov_decl,
        "geom_failed": geom_failed,
        "unrecoverable": unrecoverable,
        "honest_note": (
            f"几何回提：{n_dev_checked}/{len(list(link.ir.components))} 器件"
            f"成功回提；比对 {n_checked} 个 (器件,参数) 对，失配 "
            f"{len(violations)} 项。覆盖 {len(PARAM_MEASURERS)} 类器件 × "
            f"{sum(len(v) for v in PARAM_MEASURERS.values())} 参数"
            f"（占声明参数 {cov_decl:.1%}）；几何不可生成 "
            f"{len(geom_failed)} 器件、显式不覆盖 "
            f"{len(unrecoverable)} 类参数。判决全死标量（几何独立测量 + "
            f"距离比对），LLM 不进判决路径。"
            "诚实边界：本模块验证「版图几何与 IR 声明是否一致」，"
            "**不验证几何约定是否符合 foundry 事实**（后者需真 PDK deck）。"),
    }
