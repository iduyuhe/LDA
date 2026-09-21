# -*- coding: utf-8 -*-
"""D-77 衍生 · 主权链路版图证据集回归护栏（v0.9.119 · 走法一，零 gdsfactory）。

把 `examples/sovereign_evidence/` 的 7 例主权版图证据集接入 CI 核心门禁：
任何主权链改动（placement.port_anchor / link_model._DEFAULT_PORTS / lvs / drc /
chip_layout_export）只要破坏任一例的 DRC PASS 或 LVS ACCEPT，本 smoke 必 FAIL。

设计：导入即运行 7 例真实构建（与货架脚本同款产物，写回货架目录），再断言
内存中的 `index` / `circuits` 判决全绿。这是「回归栅栏」而非产品展示——
主权链一旦回归失真，CI 立刻红，杜绝「一次性快照悄悄失真」。

不依赖 torch/numba/cupy/meep/tidy3d；纯 numpy 亚秒级（7 例约 <2s）。按准入准则
（<5s 且无重依赖）无权豁免，必须进 CORE_SMOKES。CI core 183->184。
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))   # lda/
ROOT = os.path.dirname(HERE)                          # D:/agent_LDA
sys.path.insert(0, os.path.join(ROOT, "examples", "sovereign_evidence"))

from lda_harness.smoke_kit import make_check  # noqa: E402

check = make_check(globals(), return_ok=True, detail_on="fail")


def main() -> int:
    # 导入即触发 7 例真实构建（DRC/LVS 双闸真跑），结果留在内存。
    import build_sovereign_evidence as be  # noqa: E402

    ok = True
    for c in be.circuits:
        ok &= check(f"DRC PASS · {c['name']}",
                    c["drc_verdict"] == "PASS",
                    detail=str(c["drc_devices"]))
        ok &= check(f"LVS ACCEPT · {c['name']}",
                    c["lvs_verdict"] == "ACCEPT",
                    detail=f"nets={c['lvs_nets']} matched={c['lvs_matched']} "
                           f"viol={c['lvs_violations']}")
    ok &= check("证据集全部电路 DRC PASS", bool(be.index.get("all_drc_pass")))
    ok &= check("证据集全部电路 LVS ACCEPT", bool(be.index.get("all_lvs_accept")))
    ok &= check("证据集电路数 >= 9（含 4×4 + 8×8 计算核）", be.index.get("n_circuits") >= 9)
    # 🔴 显式锚定 4×4 计算核已接入（防「标签≠行为」：只加数不加断言 = 静默缺口）
    mesh4 = next((c for c in be.circuits if c["name"] == "lda_4x4_mzi_mesh"), None)
    ok &= check("4×4 计算核 P&R 已接入证据集", mesh4 is not None)
    if mesh4:
        ok &= check("4×4 mesh DRC PASS", mesh4["drc_verdict"] == "PASS")
        ok &= check("4×4 mesh 多层 LVS ACCEPT", mesh4["lvs_verdict"] == "ACCEPT")
        ok &= check("4×4 mesh 多层路由（跨层桥接化解交叉）",
                    bool(mesh4.get("multilayer")))
        cc = mesh4.get("compute_core") or {}
        ok &= check("4×4 mesh 计算核保真度≈1.0",
                    abs((cc.get("fidelity") or 0.0) - 1.0) < 1e-3)
    # 🔴 显式锚定 8×8 通用主权 P&R 已接入（N×N 可扩展性的回归栅栏）
    mesh8 = next((c for c in be.circuits if c["name"] == "lda_8x8_mzi_mesh"), None)
    ok &= check("8×8 通用主权 P&R 已接入证据集", mesh8 is not None)
    if mesh8:
        ok &= check("8×8 mesh DRC PASS", mesh8["drc_verdict"] == "PASS")
        ok &= check("8×8 mesh 多层 LVS ACCEPT", mesh8["lvs_verdict"] == "ACCEPT")
        ok &= check("8×8 mesh 多层路由（跨层桥接化解交叉）",
                    bool(mesh8.get("multilayer")))
        cc = mesh8.get("compute_core") or {}
        ok &= check("8×8 mesh 计算核保真度≈1.0",
                    abs((cc.get("fidelity") or 0.0) - 1.0) < 1e-3)
    # 诚实边界：主权证据集仅几何合法，不得谎称已锚定为可售 GP-*。
    ok &= check("诚实边界已声明（未冒称已锚定 GP-*）",
                "已锚定" not in be.index.get("honest_note", "")
                and "性能已锚" not in be.index.get("honest_note", ""))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
