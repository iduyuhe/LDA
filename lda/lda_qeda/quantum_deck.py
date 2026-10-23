# -*- coding: utf-8 -*-
"""D-215 · 量子 **foundry deck 限值契约层**（净增 0 锚 · 能力层）。

════════════════════════════ 为什么要有这一层 ════════════════════════════
量子 DRC/LVS 的两条入口（`quantum_drc_lvs.run_quantum_drc` 与 `sc_layout.run_sc_drc`）
本来就接受 `limits` 字典，但**限值的来源不可追溯**：
  · 光子侧 10 个限值 / 超导侧 3 个限值，全是 `DEFAULT_DRC_LIMITS` 常量；
  · 「能过自己的规则」与「能过工艺厂规则」在同一份代码路径里**不可区分**；
  · 若哪天有人手改一个限值，判决变了却没有任何元信息说明"依据谁的规则"。

本模块**只做契约层**，不解析任何商业 DRC deck 格式（那是商业格式，非公开）：
  把「一组限值 + 它的出处（哪个厂 / 哪道工艺 / 什么凭据 / 可信等级）」打包成
  **可校验、可追溯、不可自封**的 deck，作为 DRC/LVS 的唯一限值入口。

════════════════════════ 三条硬设计（都是护栏，不是装饰）════════════════════════
① **键集守恒**：deck 的限值键集必须**恰好等于**对应 DRC 模块的 `DEFAULT_DRC_LIMITS` 键集。
   缺键 ⇒ 拒绝（防"静默默认"）；多键 ⇒ 拒绝（防拼写错误被当新规则）。
   键集**动态取自真源模块**，不在本模块抄一份（否则就是第 N 份实现 ⇒ 必漂移）。
② **可信等级天花板**：`provenance` 决定该 deck 能出的**最高签核档**：
     self_built      → `DESIGN_SIGNOFF`（只可内部设计签核，`allow_external=False`）
     foundry_public  → `AUDIT_ONLY`（公开近似层，只可审计，不可签核）
     foundry_nda     → `FOUNDRY_SIGNOFF`（唯一可对外）
   且 **`foundry_nda` 必须携带 `attestation`（NDA 编号/凭据串）**，否则拒绝 ——
   这是**防自封**通道：任何人手写 `provenance="foundry_nda"` 不能凭空变出对外签核。
③ **元信息不进判决**：`foundry` / `process` / `version` / `provenance` / `attestation`
   **只写进返回体的 `deck` 与 `signoff` 段，不参与任何比较**。
   换言之：改厂名不改判决，改限值才改判决 —— 门禁对此两侧各设一条判据。

════════════════════════════ 边界（诚实披露）════════════════════════════
- 本层**不产生**任何新物理量、不新增锚、不改变既有判决（用自建 deck 跑出的结果必须与
  直接传 `limits` **逐字相同**，门禁 C1 机器核验）。
- 本层**不替代**工艺厂签核：`FOUNDRY_SIGNOFF` 只在 deck 的 provenance 为 `foundry_nda`
  且凭据经人工作业时成立；本模块本身**不校验凭据真伪**（无从校验），只校验"有没有声明"。
- 红线照旧：纯 stdlib·零第三方·零 LLM·LLM 不进判决路径。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "DECK_SCHEMA",
    "DOMAINS",
    "PROVENANCES",
    "SIGNOFF_CEILING",
    "domain_limit_keys",
    "build_deck",
    "validate_deck",
    "deck_limits",
    "signoff_ceiling",
    "drc_with_deck",
    "self_built_deck",
    "deck_disclosure",
]

DECK_SCHEMA = "lda_quantum_foundry_deck_v1"

#: 支持的域（与两条 DRC 入口一一对应）
DOMAINS: Tuple[str, ...] = ("photonic", "superconducting")

#: 可信等级（只能取这三个值之一）
PROVENANCES: Tuple[str, ...] = ("self_built", "foundry_public", "foundry_nda")

#: 可信等级 ⇒ 最高签核档（`allow_external` 决定能否进对外材料）
SIGNOFF_CEILING: Dict[str, Dict[str, Any]] = {
    "self_built": {
        "tag": "DESIGN_SIGNOFF",
        "scope": "LDA 自建设计规则 · 仅设计期内部签核",
        "allow_external": False,
    },
    "foundry_public": {
        "tag": "AUDIT_ONLY",
        "scope": "工艺厂公开近似规则（非 NDA deck）· 仅审计，不可作签核依据",
        "allow_external": False,
    },
    "foundry_nda": {
        "tag": "FOUNDRY_SIGNOFF",
        "scope": "工艺厂 NDA deck · 可作流片前设计签核依据（仍非流片实测）",
        "allow_external": True,
    },
}

#: deck 必填的元信息字段（全部 String）
_META_FIELDS: Tuple[str, ...] = ("foundry", "process", "version", "provenance", "note")


# ═══════════════════════════ 单一真源：限值键集 ═══════════════════════════
def domain_limit_keys(domain: str) -> Tuple[str, ...]:
    """返回该域 DRC 的**限值键集**（**动态取自真源模块**，本模块不抄）。"""
    d = _norm_domain(domain)
    if d == "photonic":
        from lda_qeda.quantum_drc_lvs import DEFAULT_DRC_LIMITS  # 单一真源
        return tuple(sorted(DEFAULT_DRC_LIMITS))
    from lda_qeda.sc_layout import DEFAULT_DRC_LIMITS  # 单一真源（超导几何 DRC）
    return tuple(sorted(DEFAULT_DRC_LIMITS))


def _norm_domain(domain: str) -> str:
    if domain not in DOMAINS:
        raise ValueError("未知域 %r：只接受 %s" % (domain, list(DOMAINS)))
    return domain


def _default_limits(domain: str) -> Dict[str, float]:
    """该域真源模块的默认限值（用于 `self_built_deck`）。"""
    if domain == "photonic":
        from lda_qeda.quantum_drc_lvs import DEFAULT_DRC_LIMITS
    else:
        from lda_qeda.sc_layout import DEFAULT_DRC_LIMITS
    return {k: float(v) for k, v in DEFAULT_DRC_LIMITS.items()}


# ═══════════════════════════════ 构造 / 校验 ═══════════════════════════════
def build_deck(domain: str,
               limits: Optional[Dict[str, float]] = None,
               *,
               foundry: str = "LDA-self",
               process: str = "generic",
               version: str = "v1",
               provenance: str = "self_built",
               attestation: Optional[str] = None,
               note: str = "") -> Dict[str, Any]:
    """构造 deck 并**立即校验**（不合法直接抛 `ValueError`，不留半成品）。

    `limits=None` ⇒ 取该域真源默认限值（等价于"我用的就是平台默认规则"）。
    """
    d = _norm_domain(domain)
    lim = dict(_default_limits(d) if limits is None else limits)
    deck = {
        "schema": DECK_SCHEMA,
        "domain": d,
        "foundry": str(foundry),
        "process": str(process),
        "version": str(version),
        "provenance": str(provenance),
        "attestation": attestation,
        "note": str(note),
        "limits": {k: float(v) for k, v in lim.items()},
    }
    return validate_deck(deck)


def validate_deck(deck: Dict[str, Any]) -> Dict[str, Any]:
    """校验 deck，返回**规范化副本**；任何不合规 ⇒ `ValueError`（具名原因）。

    🔴 三条拒绝线（都在门禁里有对应判据）：
      ① 缺键/多键（键集必须恰好等于真源键集）
      ② 限值非有限 或 < 0
      ③ `foundry_nda` 缺 `attestation`
    """
    if not isinstance(deck, dict):
        raise ValueError("deck 必须是 dict，实际 %s" % type(deck).__name__)
    if deck.get("schema") != DECK_SCHEMA:
        raise ValueError("deck.schema 必须是 %r，实际 %r" % (DECK_SCHEMA, deck.get("schema")))
    d = _norm_domain(str(deck.get("domain", "")))

    for f in _META_FIELDS:
        if f not in deck:
            raise ValueError("deck 缺元信息字段 %r" % f)
        if not isinstance(deck[f], str):
            raise ValueError("deck.%s 必须是 str，实际 %s" % (f, type(deck[f]).__name__))
    if deck["provenance"] not in PROVENANCES:
        raise ValueError("deck.provenance 必须是 %s 之一，实际 %r"
                         % (list(PROVENANCES), deck["provenance"]))

    att = deck.get("attestation")
    if deck["provenance"] == "foundry_nda":
        if not isinstance(att, str) or not att.strip():
            raise ValueError("🔴 provenance=foundry_nda 必须携带非空 attestation（NDA 凭据串）；"
                             "无凭据不得升格为对外签核档")
    elif att is not None and not isinstance(att, str):
        raise ValueError("deck.attestation 必须是 str 或 None，实际 %s"
                         % type(att).__name__)

    lim = deck.get("limits")
    if not isinstance(lim, dict):
        raise ValueError("deck.limits 必须是 dict，实际 %s" % type(lim).__name__)
    want = set(domain_limit_keys(d))
    have = set(lim)
    if have != want:
        miss = sorted(want - have)
        extra = sorted(have - want)
        raise ValueError("deck.limits 键集不守恒（域 %s）：缺 %s · 多 %s"
                         % (d, miss, extra))
    out_lim: Dict[str, float] = {}
    for k in sorted(lim):
        try:
            v = float(lim[k])
        except (TypeError, ValueError):
            raise ValueError("deck.limits[%r] 非数值：%r" % (k, lim[k]))
        if not math.isfinite(v):
            raise ValueError("deck.limits[%r] 非有限：%r" % (k, v))
        if v < 0.0:
            raise ValueError("deck.limits[%r] 为负：%r" % (k, v))
        out_lim[k] = v

    out = {k: deck[k] for k in _META_FIELDS}
    out.update({
        "schema": DECK_SCHEMA,
        "domain": d,
        "attestation": att,
        "limits": out_lim,
    })
    return out


def deck_limits(deck: Dict[str, Any]) -> Dict[str, float]:
    """取 deck 的限值字典（校验后）。"""
    return dict(validate_deck(deck)["limits"])


def signoff_ceiling(deck: Dict[str, Any]) -> Dict[str, Any]:
    """该 deck 的**最高签核档**（由 provenance 决定，与厂名/工艺名无关）。"""
    d = validate_deck(deck)
    c = dict(SIGNOFF_CEILING[d["provenance"]])
    c["provenance"] = d["provenance"]
    return c


def self_built_deck(domain: str, **kw: Any) -> Dict[str, Any]:
    """平台自建 deck 的快捷构造（provenance 恒 `self_built`，不接受覆盖）。"""
    if "provenance" in kw:
        raise ValueError("self_built_deck 不接受 provenance 覆盖（防自封）")
    kw.setdefault("note", "LDA 自建设计规则（非任何工艺厂 deck）")
    return build_deck(domain, None, provenance="self_built", **kw)


# ═══════════════════════════ 统一 DRC 入口（接判决）═══════════════════════════
def drc_with_deck(target: Any,
                  deck: Dict[str, Any],
                  *,
                  rule_check: str = "auto") -> Dict[str, Any]:
    """用 deck 的限值跑该域 DRC/LVS，返回**原判决 + 出处元信息**。

    `target`：
      · photonic        → 传 `design` dict（同 `run_quantum_drc`）
      · superconducting → 传 `elements` 列表（同 `run_sc_drc`）
    `rule_check="auto"` 按 `deck["domain"]` 分派；显式指定时须与 deck 域一致。

    🔴 **判决只依赖 limits**；`deck` 的 meta 段原样回带、**不参与任何比较**。
    """
    d = validate_deck(deck)
    rc = d["domain"] if rule_check in (None, "", "auto") else str(rule_check)
    if rc != d["domain"]:
        raise ValueError("rule_check(%r) 与 deck.domain(%r) 不一致 ⇒ 拒绝（防错配域）"
                         % (rc, d["domain"]))
    # 🔴 限值只经 `deck_limits` 一处取出（单一真源 ⇒ 探针可命中、口径不漂移）
    lim = deck_limits(d)
    if d["domain"] == "photonic":
        from lda_qeda.quantum_drc_lvs import run_quantum_drc
        res = run_quantum_drc(target, limits=lim)
    else:
        from lda_qeda.sc_layout import run_sc_drc
        res = run_sc_drc(target, limits=lim)

    out = dict(res)
    out["limits_used"] = lim
    out["limits_from_deck"] = True
    out["signoff"] = signoff_ceiling(d)
    out["deck"] = {
        "schema": d["schema"],
        "domain": d["domain"],
        "foundry": d["foundry"],
        "process": d["process"],
        "version": d["version"],
        "provenance": d["provenance"],
        "has_attestation": bool(d.get("attestation")),
        "note": d["note"],
    }
    return out


def deck_disclosure(deck: Dict[str, Any]) -> str:
    """一句话对外披露串（必须随 deck 一起出现在任何对外材料里）。"""
    d = validate_deck(deck)
    c = signoff_ceiling(d)
    return ("限值来源：%s / 工艺 %s / deck %s / 可信等级 %s / 最高签核档 %s"
            "（allow_external=%s）。%s"
            % (d["foundry"], d["process"], d["version"], d["provenance"],
               c["tag"], c["allow_external"], c["scope"]))


def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检（门禁同源调用）。全部为闭式/契约断言，不跑版图、不落盘。"""
    res: List[Tuple[str, bool]] = []

    def chk(name: str, cond: bool) -> None:
        res.append((name, bool(cond)))

    # ① 键集与真源一致（动态）
    for dom in DOMAINS:
        keys = domain_limit_keys(dom)
        deck = build_deck(dom)
        chk("① %s 键集≡真源（%d 键）" % (dom, len(keys)),
            tuple(sorted(deck["limits"])) == keys and len(keys) > 0)

    # ② 缺键 ⇒ 抛错
    try:
        bad = build_deck("photonic")
        bad["limits"] = dict(bad["limits"])
        bad["limits"].pop(sorted(bad["limits"])[0])
        validate_deck(bad)
        chk("② 缺键必抛 ValueError", False)
    except ValueError:
        chk("② 缺键必抛 ValueError", True)

    # ③ 多键 ⇒ 抛错
    try:
        bad = build_deck("photonic")
        bad["limits"] = dict(bad["limits"], __typo_key=1.0)
        validate_deck(bad)
        chk("③ 多键必抛 ValueError", False)
    except ValueError:
        chk("③ 多键必抛 ValueError", True)

    # ④ 负值 / 非有限 ⇒ 抛错
    guard = 0
    for v in (-1.0, float("nan"), float("inf")):
        try:
            bad = build_deck("superconducting")
            bad["limits"] = dict(bad["limits"])
            bad["limits"]["min_width_um"] = v
            validate_deck(bad)
        except ValueError:
            guard += 1
    chk("④ 负值/NaN/inf 三例均抛 ValueError", guard == 3)

    # ⑤ NDA 无凭据 ⇒ 拒（防自封对外签核）
    try:
        build_deck("photonic", provenance="foundry_nda")
        chk("⑤ foundry_nda 无 attestation 必拒", False)
    except ValueError:
        chk("⑤ foundry_nda 无 attestation 必拒", True)

    # ⑥ NDA 带凭据 ⇒ 允许且升到 FOUNDRY_SIGNOFF
    nda = build_deck("photonic", provenance="foundry_nda", attestation="NDA-EXAMPLE-0001")
    chk("⑥ foundry_nda 带凭据 ⇒ FOUNDRY_SIGNOFF 且 allow_external",
        signoff_ceiling(nda)["tag"] == "FOUNDRY_SIGNOFF"
        and signoff_ceiling(nda)["allow_external"] is True)

    # ⑦ 自建 deck 恒 DESIGN_SIGNOFF、不可对外（即使厂名写成大厂）
    sb = build_deck("photonic", foundry="AnyFoundry", provenance="self_built")
    chk("⑦ self_built 恒 DESIGN_SIGNOFF 且 allow_external=False（厂名不改等级）",
        signoff_ceiling(sb)["tag"] == "DESIGN_SIGNOFF"
        and signoff_ceiling(sb)["allow_external"] is False)

    # ⑧ self_built_deck 不接受 provenance 覆盖
    try:
        self_built_deck("photonic", provenance="foundry_nda")
        chk("⑧ self_built_deck 拒 provenance 覆盖", False)
    except ValueError:
        chk("⑧ self_built_deck 拒 provenance 覆盖", True)

    # ⑨ 域错配 ⇒ 拒
    try:
        drc_with_deck([], build_deck("photonic"), rule_check="superconducting")
        chk("⑨ 域错配必拒", False)
    except ValueError:
        chk("⑨ 域错配必拒", True)

    # ⑩ 空设计：两域均 ACCEPT 且回带 deck 元信息
    ph = drc_with_deck({}, build_deck("photonic"))
    sc = drc_with_deck([], build_deck("superconducting"))
    chk("⑩ 空目标两域 ACCEPT + 回带 deck/signoff",
        ph["verdict"] == "ACCEPT" and sc["verdict"] == "ACCEPT"
        and ph["limits_from_deck"] and "deck" in ph and "signoff" in ph)

    # ⑪ 披露串含出处与天花板
    text = deck_disclosure(sb)
    chk("⑪ 披露串含 foundry / provenance / 签核档",
        "AnyFoundry" in text and "self_built" in text and "DESIGN_SIGNOFF" in text)

    ok = all(v for _, v in res)
    if verbose:
        for n, v in res:
            print(("  [PASS] " if v else "  [FAIL] ") + n)
    return ok


if __name__ == "__main__":
    print("quantum_deck 自检：", "ALL PASS" if run_selfchecks(verbose=True) else "FAIL")
