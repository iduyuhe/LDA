r"""独立性证据分档 —— 回答「这道锚的独立性，是靠什么证明的」。

═══════════════════ 这份文件解决什么问题（F-11）═══════════════════

平台早就有一道成熟的「假独立」判据（`harness.candidate_responds`，v0.9.24 从 B10
身上学来、v0.9.25 从常量缩放桩身上加固、v0.9.223 从 B487 身上修掉尺度盲）。
它判的是两件事：

  ① 残差 `|cand − golden|` 非零  ⇒ 两条路径给出了不同但接近的值（数值证据）
  ② 残差为零时，看候选**对参数扰动有没有物理响应** ⇒ 候选真在算，不是 `return golden`

**但这两件事的结果从来没进过报告。** `verification_report.json` 里只有
`golden / candidate / tol / passed / independent / candidate_class` ——
于是 519 道独立锚里有 **87 道（16.8%）的 golden 与 candidate 数值逐位相同**，
任何外部读者（包括写这份文件的我，第一次统计时也判错）第一反应都是
「候选取了黄金值」。**实际不是** —— 它们全部通过了 ② 的扰动响应检验，
否则 `run_harness` 的 `assert not _fake_independent` 会直接失败、报告根本生成不出来。

⇒ 这是「**判据存在、证据丢失**」，与 F-8（K4 看不见纪律门禁）、
F-10（17/95 分母错）同族：三次都是同一个病 —— **判据做了事，但没人能看见它做了什么**。

═══════════════════ 五档（前三档进报告，后两档不进）═══════════════════

| 档 | 判据 | 能证明什么 | **不能**证明什么 |
|---|---|---|---|
| `RESIDUAL_NONZERO` | `\|Δ\| ≥ 1e-12` | 两条路径给出了**不同但接近**的值 | **不能**证明两条路径都对 |
| **`PERTURBATION_RESPONSE`** | `\|Δ\| < 1e-12` **且**扰动有响应 | **候选真在算**（不是 `return golden`） | 🔴 **不能**证明方法学独立 —— 它只排除"跟着 golden 走"这一种最坏情形 |
| `NON_SCALAR` | 结果非标量 | — | 无法用残差判，只能放行（诚实标注） |
| `PERTURBATION_UNVERIFIED` | `\|Δ\| < 1e-12` 但本次**没算**扰动响应 | — | **未验证**（不是"已验证"） |
| `STUB` | 分类为自证桩 | 它就是自证桩 | 不构成"验证" |
| `SUSPECT` | `\|Δ\| < 1e-12` 且扰动**无响应** | 疑似假独立 | 🔴 **不进报告**：一旦出现就说明 `run_harness` 的 assert 已经失败、报告生成不出来。它只存在于分类器与反向探针里 |

🔴🔴 **`PERTURBATION_RESPONSE` 必须被如实降级陈述**：它是「候选真在算」的证据，
**不是**「两条方法独立」的证据。把它说成后者，就是用新字段制造新的虚报 ——
那比不做这件事更糟。本模块的 `STRENGTH` 字段把这个区别写进机器可读面。

═══════════════════ 口径纪律（本轮踩到的）═══════════════════

阈值是**绝对差** `|Δ| < 1e-12`（与 `run_harness.py` 的判据**同源**），**不是相对残差**。
我第一版统计用了相对残差，得出「432 / 87」；按本模块口径是 **426 / 93**（差 6 条：
`0 < |Δ| < 1e-12` 的锚在相对口径下算"有证据"、在本口径下要走扰动分支）。
**统计口径必须与被检查的判据同源** —— 否则登记出来的数字与实现打架。

═══════════════════ 边界 ═══════════════════

- 本模块**不改任何判决**：只把已经算出来的结论分档存下来；
- 它不产生锚、不改棘轮、不构成新的验证；
- 分档**不能**替代 `candidate_responds` —— 后者是唯一权威定义处，本模块只消费其结果。
"""

from typing import Any, Dict, Iterable, List, Optional

ROLE = ("D-228 · 独立性证据分档器 —— 把「这道锚的独立性靠什么证明」变成机器可读，"
        "修正 87 道逐位相同锚被误读为「候选取了黄金值」的可观测性缺口。非门禁模块。")
ANCHORABLE = False

#: 🔴 **绝对差阈值**：与 `run_harness.py` 的判据同源（不许改成相对口径）
RESIDUAL_THRESH = 1e-12

#: 各档的语义与**证据强度**（门禁断言：用到的每个档必须在此登记，防自造新分类）
EVIDENCE_CLASSES: Dict[str, str] = {
    "RESIDUAL_NONZERO":
        "残差 |Δ| ≥ 1e-12 ⇒ 两条路径给出不同但接近的值。"
        "证明「候选不是在抄 golden」，**不证明**两条路径都对",
    "PERTURBATION_RESPONSE":
        "残差 |Δ| < 1e-12 但候选对参数扰动有物理响应 ⇒ 候选真在算。"
        "**只排除「跟着 golden 走」这一种最坏情形**，比 RESIDUAL_NONZERO 弱",
    "NON_SCALAR":
        "结果非标量（dict/复数等），无法用残差判 ⇒ 放行并如实标注",
    "PERTURBATION_UNVERIFIED":
        "残差 |Δ| < 1e-12 且本次未计算扰动响应 ⇒ **未验证**（不得表述为已验证）",
    "STUB":
        "分类为自证桩（候选直接跟 golden 走）⇒ 不构成验证",
    "SUSPECT":
        "残差 |Δ| < 1e-12 且扰动无响应 ⇒ 疑似假独立。"
        "🔴 不进报告：真出现则 run_harness 的 assert 已失败、报告不会生成",
}

#: 进报告的档（`SUSPECT` 刻意排除）
REPORTED = ("RESIDUAL_NONZERO", "PERTURBATION_RESPONSE", "NON_SCALAR",
            "PERTURBATION_UNVERIFIED", "STUB")

#: 证据强度序（数字越大越强；`STUB` 与 `SUSPECT` 不参与排序）
STRENGTH: Dict[str, int] = {
    "RESIDUAL_NONZERO": 3,
    "PERTURBATION_RESPONSE": 2,
    "NON_SCALAR": 1,
    "PERTURBATION_UNVERIFIED": 0,
    "STUB": -1,
    "SUSPECT": -2,
}

#: 自证桩分类的字符串（与 `harness.CANDIDATE_CLASS_STUB` 一致；此处不 import 以避免环）
_STUB_CLASS = "self_consistent_stub"


def classify(golden: Any, candidate: Any,
             responds: Optional[bool] = None,
             candidate_class: Optional[str] = None) -> str:
    """把一条判决结果分到证据档（**纯函数**，不跑任何求解）。

    参数
    ----
    golden, candidate : 判决用的两个值（标量或非标量）
    responds : 扰动响应结论 —— True/False/None(=本次没算)
    candidate_class : 三分类字符串（`self_consistent_stub` 等），None 表示旧路径未标注

    判定顺序（**顺序即语义，不可调**）：
      ① `candidate_class == stub` ⇒ `STUB`（分类优先：桩就是桩，不看残差）
      ② 任一非数值 ⇒ `NON_SCALAR`（残差不可用）
      ③ `|Δ| ≥ 1e-12` ⇒ `RESIDUAL_NONZERO`
      ④ `responds is True` ⇒ `PERTURBATION_RESPONSE`
      ⑤ `responds is False` ⇒ `SUSPECT`（疑似假独立）
      ⑥ `responds is None` ⇒ `PERTURBATION_UNVERIFIED`（**未验证 ≠ 已验证**）
    """
    if candidate_class == _STUB_CLASS:
        return "STUB"
    g = _as_float(golden)
    c = _as_float(candidate)
    if g is None or c is None:
        return "NON_SCALAR"
    if abs(c - g) >= RESIDUAL_THRESH:
        return "RESIDUAL_NONZERO"
    if responds is True:
        return "PERTURBATION_RESPONSE"
    if responds is False:
        return "SUSPECT"
    return "PERTURBATION_UNVERIFIED"


def _as_float(x: Any) -> Optional[float]:
    """尽力转 float（bool 不算数值 —— 它没有"残差"语义）。"""
    if isinstance(x, bool):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def summary_of(results: Iterable[Any]) -> Dict[str, Any]:
    """现算证据分布（读结果对象的 `independence_evidence` 字段）。

    返回：各档计数 + `verified_total`（= 非 STUB 的条数）+ 守恒结论。
    **不写死任何数字**，每次从结果现算。
    """
    rows = list(results)
    dist: Dict[str, int] = {}
    missing: List[str] = []
    for r in rows:
        ev = getattr(r, "independence_evidence", None)
        bid = getattr(r, "bid", getattr(r, "id", "?"))
        if ev is None:
            missing.append(str(bid))
            continue
        dist[ev] = dist.get(ev, 0) + 1
    n_total = len(rows)
    n_stub = dist.get("STUB", 0)
    # 🔴 `non_stub_total` = 非自证桩总数（含**降级量级参考**，它们不是"独立验证"）；
    #    `verified_total` = 严格独立（strict）= 非桩 − 降级。
    #    第一版把两者混成一个数（541−19=522），与 `summary.verified=519` 差 3，
    #    正是那 3 道 degraded —— **计量口径必须与账本三分类对齐**。
    n_non_stub = n_total - n_stub
    n_deg = sum(1 for r in rows
                if getattr(r, "candidate_class", None) == "degraded_ordinal")
    n_verified = n_non_stub - n_deg
    n_reported = sum(dist.get(k, 0) for k in REPORTED if k != "STUB")
    # 🔴 `strict_dist`：**只统计严格独立**的那一份。
    #   对外文案说的是「这 519 道里 N 道有残差证据」，用的是这个 N，
    #    而不是全体 `dist`（全体含 3 道降级，会把 505 说成 508 —— 本轮实测踩过）。
    _strict = [r for r in rows
               if getattr(r, "candidate_class", None) == "strict_independent"]
    strict_dist = {k: sum(1 for r in _strict
                          if getattr(r, "independence_evidence", None) == k)
                   for k in REPORTED}
    return {
        "dist": {k: dist.get(k, 0) for k in REPORTED},
        "strict_dist": strict_dist,
        "strict_total": len(_strict),
        "total": n_total,
        "verified_total": n_verified,
        "degraded_total": n_deg,
        "non_stub_total": n_non_stub,
        "stub_total": n_stub,
        "missing_evidence": missing,
        # 守恒：非 STUB 的每一道都必须落到某一档（含降级）
        "conserved": (not missing) and (n_reported == n_non_stub),
        "suspect": dist.get("SUSPECT", 0),
    }


def why_not_anchored() -> Dict[str, Any]:
    """本模块为什么不出锚（自身也遵守 `ANCHORABLE=False` 的登记纪律）。"""
    return {
        "reason": "纯分类器：输入是别的模块已经算出来的判决结果，不产生任何数值",
        "candidates_tried": [],
        "reevaluate_if": "若将来出现「独立性的机器可判代理量」（例如两实现的符号级依赖图对比），"
                         "那是新能力而不是本模块扩展",
    }


def run_selfchecks(verbose: bool = True) -> bool:
    """契约自检（8 条）：分档互斥完备 + 顺序正确 + 强度与档一致 + 汇总守恒。"""
    ok = True
    checks = []

    def chk(name, cond, detail=""):
        nonlocal ok
        checks.append((name, bool(cond), detail))
        if not cond:
            ok = False

    # 1 每个档都有语义登记
    chk("E1 档位与语义一一登记（无自造分类）",
        set(EVIDENCE_CLASSES) == set(STRENGTH) and set(REPORTED) <= set(EVIDENCE_CLASSES),
        "classes=%d reported=%d" % (len(EVIDENCE_CLASSES), len(REPORTED)))

    # 2 SUSPECT 不进报告
    chk("E2 `SUSPECT` 不在 REPORTED 内（它出现即报告生成失败）",
        "SUSPECT" not in REPORTED, "reported=%s" % (REPORTED,))

    # 3 残差非零优先于 responds（顺序）
    chk("E3 顺序：|Δ|≥thresh 时 responds 不改变分档（残差优先）",
        classify(1.0, 1.0 + 1e-9, responds=False) == "RESIDUAL_NONZERO"
        and classify(1.0, 1.0 + 1e-9, responds=True) == "RESIDUAL_NONZERO")

    # 4 残差为零 + 响应 ⇒ PERTURBATION_RESPONSE
    chk("E4 残差为零 ∧ responds=True ⇒ PERTURBATION_RESPONSE",
        classify(1.0, 1.0, responds=True) == "PERTURBATION_RESPONSE")

    # 5 残差为零 + 无响应 ⇒ SUSPECT（不是 PERTURBATION_RESPONSE）
    chk("E5 🔴 残差为零 ∧ responds=False ⇒ SUSPECT（不得误报为扰动响应）",
        classify(1.0, 1.0, responds=False) == "SUSPECT")

    # 6 没算 ⇒ UNVERIFIED（不是 RESPONSE）
    chk("E6 🔴 残差为零 ∧ responds=None ⇒ PERTURBATION_UNVERIFIED（未验证≠已验证）",
        classify(1.0, 1.0, responds=None) == "PERTURBATION_UNVERIFIED")

    # 7 桩分类优先 + 非标量
    chk("E7 stub 分类优先于残差；非标量 ⇒ NON_SCALAR；bool 不算数值",
        classify(1.0, 1.0, responds=True, candidate_class=_STUB_CLASS) == "STUB"
        and classify({"a": 1}, {"a": 1}) == "NON_SCALAR"
        and classify(True, True) == "NON_SCALAR")

    # 8 汇总守恒（合成 3 条：1 残差 + 1 响应 + 1 桩）
    class _R:
        def __init__(self, bid, ev):
            self.bid, self.independence_evidence = bid, ev

    s = summary_of([_R("X1", "RESIDUAL_NONZERO"),
                    _R("X2", "PERTURBATION_RESPONSE"),
                    _R("X3", "STUB")])
    chk("E8 汇总守恒（非 STUB 全部分档 ∧ missing 为空）",
        s["conserved"] and s["verified_total"] == 2 and s["stub_total"] == 1
        and s["dist"]["RESIDUAL_NONZERO"] == 1,
        "verified=%d stub=%d conserved=%s" % (s["verified_total"], s["stub_total"],
                                             s["conserved"]))

    if verbose:
        for n, c, d in checks:
            print("  [%s] %s%s" % ("PASS" if c else "FAIL", n, ("  |  " + d) if d else ""))
        print("  独立性证据分档器自检：%d/%d PASS"
              % (sum(1 for _, c, _ in checks if c), len(checks)))
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if run_selfchecks() else 1)
