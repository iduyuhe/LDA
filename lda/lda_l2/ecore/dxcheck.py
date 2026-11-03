# -*- coding: utf-8 -*-
"""B4 对拍框架（differential cross-check）：**逐项差异表 + 归因 + 可复现**。

═══════════════════════════════════════════════════════════════════════════
为什么存在（把 P3/P5 从「登记为未启用」变成「机器守」）
═══════════════════════════════════════════════════════════════════════════
`run_xcheck_isolation_smoke` 早就把对拍的四类滑移写成判据，但其中两条一直是
**占位**：P3（对拍只读文本输出）与 P5（差异表每行归因非空且不得为「参考工具
如此」）—— 它们需要一份**差异表 schema** 才能落地。本模块就是那份 schema。

对拍（differential）与 golden 校验是**两件事**，本模块把两者显式分开：

  · `golden`   —— 闭式/物理律给出的**独立**答案（面积 = Σ 单元面积；
                  线长 = 闭式中心矩）。它**只能是物理律或闭式几何**，
                  外部工具名永不出现在这一位（P1 角色判据）。
  · `reference` —— 外部参考工具（OpenROAD / OpenSTA，B 级）给出的**候选值**。
                  只经**独立进程 + 文本**交换（P3）**只黑盒、不链接**
                  （OpenSTA 是 GPL-3.0 ⇒ 禁链接/禁 vendored）。
  · `target`   —— 设计约束（如目标周期 ⇒ WNS 正负）。不是「真值」，
                  但足以判定「超界/未超界」。

═══════════════════════════════════════════════════════════════════════════
三态纪律（别把「测不了」压扁成「通过」）
═══════════════════════════════════════════════════════════════════════════
每行 `exceeds` 取 **true / false / null** 三值：
  · `true`  = 超界（有基线且超了）；
  · `false` = 未超界（有基线且没超）；
  · `null`  = **无法判定**（无参考、无 golden、无 target）。
`null` 绝不写成 `false` —— 本仓已多次因「把边界声明压扁成合规」而失真。

同理 `evidence_level`：
  · `EXTERNAL_CROSSCHECK` —— 参考工具**实测**过（值来自独立进程 + 文本）；
  · `SELF_CONSISTENCY_ONLY` —— 只有 golden 同定义自检，**不构成对外对拍**。
「同定义自检通过」不得冒称「与 OpenROAD 一致」。

═══════════════════════════════════════════════════════════════════════════
可复现（同输入 ⇒ 同结果，字节级）
═══════════════════════════════════════════════════════════════════════════
`build_diff_table` 的输出**不含**时间戳、绝对路径、工具版本猜测、随机数；
浮点统一 `round(·, 6)`；`serialize()` 用 `sort_keys=True` ⇒ 两次构建字节一致，
`digest()` 给 sha256 供门禁机核（`run_ecore_s7_smoke` 直接比 hexdigest）。

🔴 **诚实边界**（对外引用须同给）：
  · 本模块**不做** P&R、不做 STA 本身，只消费平台已有结果；
  · 参考工具缺席时 `reference.status="unavailable"`，此时差异表仍完整，
    但**不声称**任何与商业/开源工具的一致性；
  · 文本解析器（`parse_*`）只吃**声明为合成样本**的文本，不是实测语料；
  · 面积/线长 golden 与平台实现**同定义**（`independent=False`）——
    真正的独立性只能来自外部工具实测，本仓当前不具备；
  · WNS 的 `target` 是**声明约束**，不是硅上实测。
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 常量：外部参考工具（B 级 · 只黑盒）与归因闭式词表
# ---------------------------------------------------------------------------
REFERENCE_TOOLS: Tuple[str, ...] = ("OpenROAD", "OpenSTA")

#: 归因**闭式**词表。新增成因必须在此登记，否则 `validate_table` 判红 ——
#: 「随手写一句解释」不算归因（本仓口径：不可枚举 = 不可机核）。
ATTRIBUTION_CODES = frozenset({
    "WITHIN_BAND_NO_CAUSE",        # 未超界，且无已知成因
    "UNVERIFIABLE_NO_BASELINE",    # 无参考、无 golden、无 target ⇒ 三态 null
    "NO_CLOCK_DOMAIN",             # 纯组合设计：WNS 无定义
    "REFERENCE_UNAVAILABLE",       # 参考工具缺席（只降级，不冒充）
    "DEFINITION_DIFF",             # 口径差异（含/不含 IO ring、填充、pin 代理）
    "ALGORITHM_DIFF",              # 算法差异（HPWL vs Steiner/RSMT）
    "DELAY_MODEL_DIFF",            # 延时模型差异（wire load / 角 / 无 SPEF）
    "UNIT_OR_DATUM_DIFF",          # 单位或基准点差异
    "TIMING_TARGET_VIOLATED",      # 违反声明约束（WNS < 0）
    "IMPLEMENTATION_DEFECT",       # 疑平台自身缺陷（需挂号，不是解释）
})

#: P5：这些「解释」等于把判决权交出去 ⇒ 一律判红（不可是归因文本的子串）。
FORBIDDEN_EXCUSES = ("参考工具如此", "以参考工具为准", "工具差异", "商业工具就是这样")

#: 证据级别（两值，不许含糊）。
EVIDENCE_LEVELS = frozenset({"EXTERNAL_CROSSCHECK", "SELF_CONSISTENCY_ONLY"})

#: 基线种类。
BASELINE_KINDS = frozenset({"reference", "golden", "target", "none"})

#: golden 允许的角色（外部工具名永不入此集合 —— P1 角色位）。
GOLDEN_ROLES = frozenset({"CLOSED_FORM_GEOMETRY", "SAME_DEFINITION_SELF_CHECK"})

DXC_CHECK_DIGITS = 6


class CrossCheckError(ValueError):
    """差异表结构/归因不合法（fail-closed）。"""


# ---------------------------------------------------------------------------
# 基础构件
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Band:
    """允许带：`|Δ| <= max(abs_tol, pct_tol·|baseline|)`。"""

    abs_tol: float = 0.0
    pct_tol: float = 0.0

    def allow(self, baseline: Optional[float]) -> float:
        a = float(self.abs_tol)
        p = float(self.pct_tol) * abs(float(baseline or 0.0))
        return max(a, p)

    def as_dict(self) -> Dict[str, float]:
        return {"abs": _q(self.abs_tol), "pct": _q(self.pct_tol)}


def _q(x: Optional[float], nd: int = DXC_CHECK_DIGITS) -> Optional[float]:
    """浮点归一（去 -0.0、固定小数位）—— 可复现的第一要件。"""
    if x is None:
        return None
    v = float(x)
    if v == 0.0:
        v = 0.0
    return round(v, nd)


def probe_reference(tools: Iterable[str] = REFERENCE_TOOLS) -> List[Dict[str, Any]]:
    """探测参考工具是否在场（**只看 PATH，不 import、不执行**）。

    刻意不返回绝对路径/版本：它们随机器变 ⇒ 会破坏「同输入同结果」。
    """
    out: List[Dict[str, Any]] = []
    for t in tools:
        present = bool(shutil.which(t.lower()) or shutil.which(t))
        out.append({"tool": t, "present": present, "version": None})
    return out


def _ref_status(tool: str, probe: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    probe = probe if probe is not None else probe_reference()
    hit = next((p for p in probe if p["tool"] == tool), None)
    present = bool(hit and hit.get("present"))
    return {
        "tool": tool,
        "value": None,
        "status": "unavailable" if not present else "not_run",
        "probe": _PROBE_NAMES.get(tool, ""),
    }


_PROBE_NAMES = {
    "OpenROAD": "report_design_area / report_wire_length",
    "OpenSTA": "report_checks -path_delay max",
}


# ---------------------------------------------------------------------------
# 闭式 golden（几何定义 ⇒ 与平台实现同定义，故 independent=False）
# ---------------------------------------------------------------------------
def golden_area_um2(nl, tech=None) -> float:
    """闭式面积：Σ 单元面积（几何定义，非估算）。"""
    from . import dcell as DC

    tech = tech or DC.DEFAULT_TECH
    return float(sum(DC.cell_area_um2(g.cell, tech) for g in nl.gates))


def golden_hpwl_center_um(nl, placement) -> float:
    """闭式半周长线长（以单元中心为引脚代理）。

    🔴 与 `dplac` 的报告值**同定义**（实测逐位一致）⇒ `independent=False`。
    它的价值是「量级锚 + 算法自洽」，**不是**外部独立性。
    """
    pos = {n: (x + w / 2.0, y + h / 2.0)
           for n, (x, y, w, h) in (placement.cell_xywh or {}).items()}
    pins: Dict[str, List[Tuple[float, float]]] = {}
    for g in nl.gates:
        p = pos.get(g.name)
        if p is None:
            continue
        for n in g.ins:
            if n == "CLK":
                continue
            pins.setdefault(n, []).append(p)
        pins.setdefault(g.out, []).append(p)
    total = 0.0
    for pts in pins.values():
        if len(pts) < 2:
            continue
        xs = [q[0] for q in pts]
        ys = [q[1] for q in pts]
        total += (max(xs) - min(xs)) + (max(ys) - min(ys))
    return float(total)


# ---------------------------------------------------------------------------
# 参考通道（P3：独立进程 + 只回文本；不链接、不 import 其库）
# ---------------------------------------------------------------------------
def run_reference_text(tool: str, argv: List[str], *, timeout: float = 60.0) -> Dict[str, Any]:
    """用**独立进程**调用参考工具，只取回文本（黑盒）。

    · OpenSTA 是 GPL-3.0：**只允许**这样调用（禁链接 / 禁 vendored）；
    · 工具缺席 ⇒ `status="unavailable"`，绝不回落到「猜一个值」；
    · 本函数在 CI 里**不会**被执行（工具缺席），但它的降级路径是可机核的。
    """
    if not (shutil.which(tool.lower()) or shutil.which(tool)):
        return {"tool": tool, "status": "unavailable", "text": None, "rc": None}
    try:
        r = subprocess.run([tool] + list(argv), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return {"tool": tool, "status": "measured", "text": r.stdout, "rc": r.returncode}
    except (OSError, subprocess.SubprocessError) as ex:
        return {"tool": tool, "status": "error", "text": None, "rc": None,
                "error": type(ex).__name__}


# ---------------------------------------------------------------------------
# 文本解析器（P3：只读文本，绝不 import 参考工具的库）
# ---------------------------------------------------------------------------
#: 🔴 合成样本（**不是实测语料**）—— 只为让「文本解析」这条通道可机核。
SYNTHETIC_OPENROAD_AREA_TEXT = """\
Design area 1234.56 u^2 80% utilization.
"""
SYNTHETIC_OPENSTA_WNS_TEXT = """\
worst slack max -12.34
worst slack min  0.55
"""


def parse_openroad_area_text(text: str) -> Optional[float]:
    """从 OpenROAD 文本报告里抽 `**Design area <x> u^2**`（µm²）。"""
    import re

    m = re.search(r"Design area\s+([0-9]*\.?[0-9]+)\s*u\^2", text or "")
    return float(m.group(1)) if m else None


def parse_opensta_wns_text(text: str) -> Optional[float]:
    """从 OpenSTA 文本报告里抽 `worst slack max <x>`（ps/ns 由调用方声明口径）。"""
    import re

    m = re.search(r"worst slack max\s+(-?[0-9]*\.?[0-9]+)", text or "")
    return float(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# 差异表构建
# ---------------------------------------------------------------------------
def _row(
    metric: str,
    unit: str,
    lda_value: Optional[float],
    lda_source: str,
    *,
    reference: Dict[str, Any],
    golden: Optional[Dict[str, Any]],
    baseline_used: str,
    band: Band,
    target: Optional[Dict[str, Any]] = None,
    attribution: Tuple[str, str],
    hint: Optional[str] = None,
) -> Dict[str, Any]:
    """构造一行（内部）：先算 delta/exceeds，再由调用方给归因。"""
    if baseline_used not in BASELINE_KINDS:
        raise CrossCheckError("baseline_used 非法：%r" % (baseline_used,))

    base_val: Optional[float] = None
    if baseline_used == "reference" and reference.get("status") == "measured":
        base_val = reference.get("value")
    elif baseline_used == "golden" and golden:
        base_val = golden.get("value")

    delta = None
    delta_pct = None
    exceeds: Optional[bool]
    if baseline_used == "target":
        # WNS 语义：负值 = 违约（target 是 0 阈值，不是真值）
        exceeds = None if lda_value is None else bool(float(lda_value) < 0.0)
    elif base_val is None or lda_value is None:
        exceeds = None
    else:
        delta = float(lda_value) - float(base_val)
        deny = abs(float(base_val))
        delta_pct = (delta / deny * 100.0) if deny else None
        exceeds = bool(abs(delta) > band.allow(float(base_val)))

    code, detail = attribution
    if code not in ATTRIBUTION_CODES:
        raise CrossCheckError("归因码不在闭式词表：%r" % (code,))
    if not str(detail).strip():
        raise CrossCheckError("归因文本为空（P5）")

    ext = reference.get("status") == "measured"
    row = {
        "metric": metric,
        "unit": unit,
        "lda": {"value": _q(lda_value), "source": lda_source},
        "reference": {
            "tool": reference.get("tool"),
            "value": _q(reference.get("value")),
            "status": reference.get("status"),
            "probe": reference.get("probe", ""),
        },
        "golden": None,
        "baseline_used": baseline_used,
        "target": target,
        "delta": _q(delta),
        "delta_pct": _q(delta_pct),
        "band": band.as_dict(),
        "exceeds": exceeds,
        "evidence_level": "EXTERNAL_CROSSCHECK" if ext else "SELF_CONSISTENCY_ONLY",
        "attribution": {"code": code, "detail": str(detail).strip()},
    }
    if golden is not None:
        row["golden"] = {
            "role": golden.get("role"),
            "value": _q(golden.get("value")),
            "definition": golden.get("definition", ""),
            "independent": bool(golden.get("independent", False)),
        }
    if hint:
        row["hint"] = hint
    return row


def build_diff_table(subject: str, rows: List[Dict[str, Any]],
                     *, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """把若干行组装成**确定性**差异表（按 metric 排序，无时间戳/无路径）。"""
    if not rows:
        raise CrossCheckError("差异表为空（fail-closed）")
    metrics = [r["metric"] for r in rows]
    if len(set(metrics)) != len(metrics):
        raise CrossCheckError("metric 重复：%r" % (metrics,))
    out = {
        "schema": "lda.b4_diff_table/1",
        "subject": subject,
        "meta": dict(sorted((meta or {}).items())),
        "rows": sorted(rows, key=lambda r: r["metric"]),
    }
    problems = validate_table(out)
    if problems:
        raise CrossCheckError("差异表不合法：" + "; ".join(problems))
    return out


def validate_table(table: Dict[str, Any]) -> List[str]:
    """结构 + P5 + 角色位 + 三态纪律的机核；返回问题列表（空 = 合法）。"""
    problems: List[str] = []
    rows = table.get("rows") or []
    if not rows:
        return ["rows 为空"]
    if [r.get("metric") for r in rows] != sorted(r.get("metric") for r in rows):
        problems.append("rows 未按 metric 排序（破坏可复现）")

    for r in rows:
        tag = r.get("metric")
        att = r.get("attribution") or {}
        code, detail = att.get("code"), str(att.get("detail") or "")
        if code not in ATTRIBUTION_CODES:
            problems.append("%s: 归因码非法 %r" % (tag, code))
        if not detail.strip():
            problems.append("%s: 归因文本为空（P5）" % tag)
        for bad in FORBIDDEN_EXCUSES:
            if bad in detail:
                problems.append("%s: 归因含禁用借口《%s》（P5：判决权不得交给参考工具）"
                                % (tag, bad))

        if r.get("exceeds") not in (True, False, None):
            problems.append("%s: exceeds 必须是 true/false/null 三态" % tag)
        if r.get("baseline_used") not in BASELINE_KINDS:
            problems.append("%s: baseline_used 非法" % tag)
        # 🔴 三态纪律的结构化版本：无基线 ⇒ 必须 null；有基线 ⇒ 不得 null。
        #    否则「测不了」会被静默压扁成「未超界」（本仓反复踩过的失真方向）。
        if r.get("baseline_used") == "none" and r.get("exceeds") is not None:
            problems.append("%s: baseline_used=none 却给了 exceeds（三态 null 被压扁）" % tag)
        if (r.get("baseline_used") == "golden"
                and (r.get("golden") or {}).get("value") is not None
                and r.get("exceeds") is None):
            problems.append("%s: 有 golden 却 exceeds=null（漏判）" % tag)
        if (r.get("baseline_used") == "reference"
                and (r.get("reference") or {}).get("status") == "measured"
                and r.get("exceeds") is None):
            problems.append("%s: 参考已实测却 exceeds=null（漏判）" % tag)
        if r.get("evidence_level") not in EVIDENCE_LEVELS:
            problems.append("%s: evidence_level 非法" % tag)

        ref = r.get("reference") or {}
        if r.get("evidence_level") == "EXTERNAL_CROSSCHECK":
            if ref.get("status") != "measured" or r.get("baseline_used") != "reference":
                problems.append("%s: 冒称外部对拍（参考未实测却标 EXTERNAL_CROSSCHECK）" % tag)
        if ref.get("status") == "unavailable" and r.get("evidence_level") != "SELF_CONSISTENCY_ONLY":
            problems.append("%s: 参考缺席却非 SELF_CONSISTENCY_ONLY" % tag)

        g = r.get("golden")
        if g:
            role = g.get("role")
            if role is not None and role not in GOLDEN_ROLES:
                problems.append("%s: golden.role 非法 %r（外部工具名永不入 golden 位）"
                                % (tag, role))
            if role is None and g.get("value") is not None:
                problems.append("%s: golden.role 为空却有值" % tag)
    return problems


def serialize(table: Dict[str, Any]) -> str:
    """确定性序列化（`sort_keys` + 固定分隔符 + 末尾换行）。"""
    return json.dumps(table, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def digest(table: Dict[str, Any]) -> str:
    """sha256(serialize(table)) —— 门禁用它核「同输入同结果」。"""
    import hashlib

    return hashlib.sha256(serialize(table).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 首个对拍对象：门级网表的 面积 / 线长 / WNS
# ---------------------------------------------------------------------------
def xcheck(nl, *, subject: str = "netlist", target_period_ps: Optional[float] = None,
           tech=None, probe: Optional[List[Dict[str, Any]]] = None,
           place=None) -> Dict[str, Any]:
    """对一份门级网表产出差异表（面积 / 线长 / WNS 三项）。

    · 面积：`lda = nl.area_um2(tech)`，golden = Σ 单元面积（同定义 ⇒ 必须逐位相等）；
    · 线长：`lda = dplac.place(nl).hpwl_um`，golden = 闭式中心矩（同定义）；
    · WNS ：`lda = target - t_clk_min`（纯组合 ⇒ 无定义，三态 null）。
    参考工具缺席时只是**降级**（`status=unavailable`），不冒充、不编数。
    """
    from . import dcell as DC
    from . import dplac, dsta

    tech = tech or DC.DEFAULT_TECH
    probe = probe if probe is not None else probe_reference()
    rows: List[Dict[str, Any]] = []

    # ---- ① 面积 ----
    lda_area = float(nl.area_um2(tech))
    g_area = golden_area_um2(nl, tech)
    rows.append(_row(
        "area_um2", "um^2", lda_area, "dsynth.Netlist.area_um2",
        reference=_ref_status("OpenROAD", probe),
        golden={"role": "CLOSED_FORM_GEOMETRY", "value": g_area,
                "definition": "sum(cell_area_um2)", "independent": False},
        baseline_used="golden",
        band=Band(abs_tol=1e-9),
        attribution=("WITHIN_BAND_NO_CAUSE",
                     "面积是几何量：LDA 与闭式 Σ 单元面积同定义 ⇒ 差值应恰为 0；"
                     "外部工具缺席 ⇒ 本行只作同定义自检，不构成对外一致性证据"),
        hint="golden 与平台实现同定义（independent=False）",
    ))

    # ---- ② 线长 ----
    p = place if place is not None else dplac.place(nl)
    lda_hpwl = float(p.hpwl_um)
    g_hpwl = golden_hpwl_center_um(nl, p)
    rows.append(_row(
        "hpwl_um", "um", lda_hpwl, "dplac.Placement.hpwl_um",
        reference=_ref_status("OpenROAD", probe),
        golden={"role": "SAME_DEFINITION_SELF_CHECK", "value": g_hpwl,
                "definition": "half-perimeter over cell centers", "independent": False},
        baseline_used="golden",
        band=Band(abs_tol=1e-9),
        attribution=("WITHIN_BAND_NO_CAUSE",
                     "线长为摆放后闭式量：LDA 与闭式中心矩同定义 ⇒ 差值应恰为 0；"
                     "与 Steiner/RSMT 的差异属 ALGORITHM_DIFF，本行未启用"),
        hint="若将来接入 OpenROAD，同一份 DEF 上的线长差才构成 ALGORITHM_DIFF 的实证",
    ))

    # ---- ③ WNS ----
    n_dff = int(getattr(nl, "n_dff", lambda: 0)())
    ref_sta = _ref_status("OpenSTA", probe)
    if n_dff <= 0:
        rows.append(_row(
            "wns_ps", "ps", None, "dsta.Timing.t_clk_min_ps",
            reference=ref_sta, golden=None, baseline_used="none",
            band=Band(abs_tol=0.0),
            attribution=("NO_CLOCK_DOMAIN",
                         "纯组合设计没有时钟域 ⇒ WNS 无定义（不是 0，也不判通过）"),
            hint="WNS 需要含 DFF 的设计；三态 null 明确表示「无定义」",
        ))
    else:
        t = dsta.sta(nl, tech)
        t_clk = t.t_clk_min_ps
        if t_clk is None or target_period_ps is None:
            wns = None
            base = "none"
            att = ("UNVERIFIABLE_NO_BASELINE",
                   "缺 t_clk_min 或未给目标周期 ⇒ 无法判定是否超界")
        else:
            wns = float(target_period_ps) - float(t_clk)
            base = "target"
            att = (("TIMING_TARGET_VIOLATED",
                    "WNS = 目标周期 − t_clk_min < 0 ⇒ 违反声明约束")
                   if wns < 0 else
                   ("WITHIN_BAND_NO_CAUSE",
                    "WNS ≥ 0 ⇒ 满足声明约束；t_clk_min 来自平台一阶 STA"
                    "（无 SPEF/单角）⇒ 不与 OpenSTA 比绝对值"))
        rows.append(_row(
            "wns_ps", "ps", wns, "target_period_ps - dsta.Timing.t_clk_min_ps",
            reference=ref_sta, golden=None, baseline_used=base,
            band=Band(abs_tol=0.0),
            target={"value": _q(target_period_ps), "source": "declared constraint"},
            attribution=att,
            hint="target 是声明约束，不是硅上实测；缺参考 ⇒ 不构成对外对拍",
        ))

    meta = {
        "n_gates_comb": int(nl.n_gates()),
        "n_dff": n_dff,
        "reference_available": any(p_["present"] for p_ in probe),
        "claimable": False,
        "claimable_reason": ("对拍框架骨架；参考工具缺席或仅同定义自检，"
                             "不得据此声称与 OpenROAD/OpenSTA 一致"),
    }
    return build_diff_table(subject, rows, meta=meta)


# ---------------------------------------------------------------------------
# 样本：首个对拍对象（ISCAS c17 纯组合 + 一条最小时序环）
# ---------------------------------------------------------------------------
def sample_seq_netlist():
    """最小时序环：DFF(q) → NAND2 → INV → DFF(d)。

    约定与 `dsta.sta` 对齐：DFF 的 Q 以 `("<reg>@q", w)` 暴露为**输入**
    （到达时间 = t_clk_q），D 以 `("...@d", ...)` 暴露为**输出**（查建立时间）。
    """
    from .dsynth import Gate, Netlist

    nl = Netlist(name="seq_min")
    nl.inputs = (("reg@q", 1), ("a", 1))
    nl.in_nets = {("reg@q", 0): "q_reg_0", ("a", 0): "in_a_0"}
    nl.gates = [
        Gate("g1", "NAND2", ("q_reg_0", "in_a_0"), "n1"),
        Gate("g2", "INV", ("n1",), "n2"),
        Gate("r1", "DFF", ("n2", "CLK"), "q_reg_0"),
    ]
    nl.outputs = {"reg@d": ("n2",)}
    return nl


DXCHECK_DISCLOSURE = {
    "route": "B4 · 对拍（differential）框架：逐项差异表 + 归因 + 可复现",
    "scope": "消费平台既有面积/线长/STA 结果，与闭式 golden 或外部参考（只黑盒 + 文本）对照",
    "not_included": "不做 P&R、不做 STA 本身；参考缺席时不产任何一致性声明",
    "golden": "只允许闭式几何/物理律；外部工具名永不入 golden 位（P1 角色判据）",
    "p3": "只读文本输出：不 import 参考工具库、不读其内存对象（门禁 AST 机核）",
    "p5": "每行 attribution 非空且在闭式词表内，且不得为「参考工具如此」式借口",
    "determinism": "无时间戳/路径/版本；浮点 round 6；sort_keys ⇒ 两次构建字节一致",
    "claimable": False,
    "claimable_reason": "框架骨架；参考工具缺席时证据级别只到同定义自检",
}
