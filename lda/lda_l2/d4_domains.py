# -*- coding: utf-8 -*-
"""LDA · D4 交付闭环扩面（ecore / 量子侧 · 统一「GDS → 双闸签核」编排）。

============================================================================
为什么需要它（W2 收官后的残留 P2）
----------------------------------------------------------------------------
W2 已把光子侧「设计 → GDS → 签核 → 下载」实测贯通（`/api/design_tapeout`
+ `/api/design_gds`，下载 sha256 与本地确定性重建逐位 MATCH）。但**平台另外
两条真产线仍是断的**：

  - **电子侧（ecore）**：E6 早就能出真 GDS（`ecore/layout.to_gds` +
    `run_edrc` + `elvs_signoff`），却**没有一条对外交付通路**——用户拿不走；
  - **量子侧（超导 transmon）**：`lda_qeda/sc_array.array_gds` +
    `run_sc_array_drc` + `sc_array_lvs_signoff` 同样齐全，同样无通路。

⇒ 本模块把这两条**既有真链路**收编进同一条 D4 编排：
    `build_domain(domain)` → GDS 字节 + sha256 + 双闸签核 + 交付报告。
**不重造几何、不重造 DRC/LVS**：只读消费 `ecore/layout` 与 `lda_qeda/sc_array`。

============================================================================
纪律（与光子侧 D4 同一口径）
----------------------------------------------------------------------------
1. **确定性**：同参数 ⇒ 同 sha256（GDS 编码零时间戳、零字典序依赖）；
   不同参数 ⇒ sha256 必须不同（否则「常数化假确定性」，门禁会拦）。
2. **双闸**：DRC（几何规则）+ LVS（ connectivity / netlist）皆 ACCEPT ⇒
   整体 verdict = ACCEPT；任一 REJECT ⇒ 整体 REJECT（不掩盖）。
3. **对外只给标量**：`deliver_report` 不吐 GDS 字节（WebUI/前端只读该报告）。
4. **诚实边界（逐条登记，不粉饰）**：
   - 层号/层序/规则 = **公开工艺近似的设计规则**，非 Foundry PDK 标定值；
   - DRC 为 **bbox 级**几何近似（光子 D4 同口径），非多边形布尔运算；
   - **不涉及流片**：verdict = 设计期签核，**非实测签核**、非流片结果；
   - 仍不报 TOPS / TOPS-W / fJ/op（红线）。
5. LLM 不进判决路径；零商业 EDA 依赖（纯标准库 + 平台自有 GDS 栈）。

判据全部为该模块内部闭式/几何自证，属**设计期预算**，不冒充实测。
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional

__all__ = [
    "D4_DOMAINS",
    "DOMAIN_LABELS",
    "HONEST_NOTES",
    "build_domain",
    "deliver_report",
    "d4_domains_self_check",
]

# 交付域 → 支持参数键（门禁用反向完备判据扫这份表，防「新域静默进盲区」）
D4_DOMAINS = ("ecore", "quantum_sc")

DOMAIN_LABELS = {
    "ecore": "电子计算核（模拟 MVM 交叉阵列 · NMOS 1T 交叉点单元）",
    "quantum_sc": "超导 transmon 量子阵列（S3 · 单元 + 读出/控制几何）",
}

HONEST_NOTES = (
    "层规为公开工艺近似设计规则（非 Foundry PDK 标定值）；"
    "DRC 为 bbox 级几何近似；verdict 属设计期签核·非流片实测·非实测签核；"
    "不报 TOPS / TOPS-W / fJ/op。"
)

# GDS HEADER 记录魔数（len=6 · HEADER · INTEGER_2），与光子侧 D4 同口径
GDS_HEADER_MAGIC = b"\x00\x06\x00\x02"


def _verdict_of(drc: Dict, lvs: Dict) -> str:
    """双闸 ⇒ 整体 verdict：任一 REJECT 即整体 REJECT（不掩盖、不取交集美化）。"""
    dv = str(drc.get("verdict") or "").upper()
    lv = str(lvs.get("verdict") or "").upper()
    if dv == "ACCEPT" and lv == "ACCEPT":
        return "ACCEPT"
    return "REJECT"


def _build_ecore(params: Optional[Dict[str, Any]] = None) -> Dict:
    """电子域：交叉阵列几何 → GDS → 几何 DRC → 几何 LVS 签核（只读消费 E6）。"""
    from lda_l2.ecore import layout as L

    p = dict(params or {})
    n = int(p.get("n", 4))
    m = int(p.get("m", 4))
    arr = L.crossbar_array(n, m, p or None)
    g = L.to_gds(n, m, p or None, hierarchical=True)
    drc = L.run_edrc(arr["descs"], {})
    lvs = L.elvs_signoff(arr["descs"], L.expected_netlist(n, m))
    return {
        "elements": arr["descs"],
        "gds_bytes": g["gds_bytes"],
        "n_elements": g["flat_elements"],
        "params": {"domain": "ecore", "n": n, "m": m},
        "drc": drc,
        "lvs": lvs,
    }


def _build_quantum_sc(params: Optional[Dict[str, Any]] = None) -> Dict:
    """超导量子域：transmon 阵列几何 → GDS → DRC → LVS 签核（只读消费 S3）。"""
    import tempfile
    from pathlib import Path

    from lda_qeda import sc_array as A

    p = dict(params or {})
    # 🔴 临时目录落盘：`array_gds` 默认 path="sc_array.gds" 会写进 cwd（≈仓库根），
    # 把构建产物污染成工作区垃圾文件（本次提交就误带进过一次）。字节内容不受影响。
    _tmp = Path(tempfile.mkdtemp(prefix="lda_d4_sc_"))
    el = A.array_cell(p or None)
    drc = A.run_sc_array_drc(el)
    lvs = A.sc_array_lvs_signoff(el)
    return {
        "elements": el,
        "gds_bytes": A.array_gds(p or None, path=str(_tmp / "sc_array.gds")),
        "n_elements": len(el),
        "params": {"domain": "quantum_sc"},
        "drc": drc,
        "lvs": lvs,
    }


def _builder_for(domain: str):
    """交付域 → 构建函数。

    🔴 调用期解析（不用导入期固化的 `_BUILDERS` 字典）：字典在 import 时就抓住了
    函数对象，进程内 `patch.object(module, '_build_quantum_sc', ...)` 打不进去 ⇒
    突变探针全部假绿。调用期从 globals() 取 ⇒ 探针可打、判决路径不变。
    """
    if domain == "ecore":
        return _build_ecore
    if domain == "quantum_sc":
        return _build_quantum_sc
    return None


def build_domain(domain: str, params: Optional[Dict[str, Any]] = None) -> Dict:
    """给定交付域，跑完「几何 → GDS → 双闸签核」，返回**含字节**的完整交付物。

    返回 {ok, domain, label, verdict, gds{n_bytes, sha256, header_ok},
          drc{verdict, n_violations}, lvs{verdict, n_checks},
          n_elements, honest_notes, errors}
    """
    fn = _builder_for(domain)
    if fn is None:
        return {"ok": False, "domain": domain,
                "errors": ["未知交付域：%s（已注册=%s）" % (domain, list(D4_DOMAINS))],
                "honest_notes": HONEST_NOTES}
    try:
        raw = fn(params)
    except Exception as exc:                      # 判决路径不吞异常：原样登记
        return {"ok": False, "domain": domain,
                "errors": ["%s 交付失败：%s" % (domain, exc)],
                "honest_notes": HONEST_NOTES}
    gds = raw["gds_bytes"] or b""
    sha = hashlib.sha256(gds).hexdigest()
    drc, lvs = raw["drc"], raw["lvs"]
    verdict = _verdict_of(drc, lvs)
    return {
        "ok": True,
        "domain": domain,
        "label": DOMAIN_LABELS.get(domain, domain),
        "verdict": verdict,
        "gds": {
            "n_bytes": len(gds),
            "sha256": sha,
            "header_ok": bytes(gds[:4]) == GDS_HEADER_MAGIC if gds else False,
        },
        "drc": {"verdict": drc.get("verdict"),
                "n_violations": len(drc.get("violations") or [])},
        "lvs": {"verdict": lvs.get("verdict"),
                "n_checks": len(lvs.get("issues") or [])},
        "n_elements": raw["n_elements"],
        "honest_notes": HONEST_NOTES,
        "errors": [],
    }


def deliver_report(domain: str, params: Optional[Dict[str, Any]] = None) -> Dict:
    """对外交付报告：**只给标量，不吐 GDS 字节**（WebUI/前端/案例卡消费此面）。

    字节面是原始字节（`gds_bytes`），只有它的**摘要**（n_bytes / sha256）属于标量，
    属交付物标识 ⇒ 照常给（「确定性 sha256 可重建」本身就是这条 D4 链的卖点）。
    """
    rep = build_domain(domain, params)
    if not rep.get("ok"):
        return rep
    return {k: v for k, v in rep.items() if k != "gds"} | {
        "gds": {"n_bytes": rep["gds"]["n_bytes"], "sha256": rep["gds"]["sha256"]}}


def d4_domains_self_check(verbose: bool = False) -> bool:
    """模块自检：每个注册域都必须出 GDS + 双闸 ACCEPT + 确定性。"""
    ok = True
    for d in D4_DOMAINS:
        a = build_domain(d)
        b = build_domain(d)
        good = (a.get("ok") and a["gds"]["n_bytes"] > 0
                and a["gds"]["header_ok"] and a["verdict"] == "ACCEPT"
                and a["gds"]["sha256"] == b["gds"]["sha256"])
        if verbose:
            print("[%s] %-11s bytes=%s sha=%s… verdict=%s"
                  % ("PASS" if good else "FAIL", d, a.get("gds", {}).get("n_bytes"),
                     str(a.get("gds", {}).get("sha256", ""))[:12], a.get("verdict")))
        ok = ok and good
    return ok


if __name__ == "__main__":
    print("D4 domains self-check:", "PASS" if d4_domains_self_check(verbose=True) else "FAIL")
