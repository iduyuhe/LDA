#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""超导 transmon 芯片案例卡门禁 smoke（D-216 · 净增 0 锚 · 补审计发现 F-1）。

═══ 背景（这条门禁为什么存在）═══
2026-10-23 量子域全景审计发现：`lda/lda_webui/schip_case.py` 的 `run_selfchecks`
（12 条自检，docstring 自称「门禁同源调用」）**此前没有任何 CI 门禁调用它** ——
自检本体是绿的，但**回归改坏它不会亮红**。本门禁把它接进 CI core，并补上
对照 `qchip_case` 缺失的**跨源一致性**与**面板接线**判据。

═══ 判什么（分五节 · 15 条）═══
A 模块自检与卡结构 2 · X 跨源一致性 3 · G 面板接线 3 · H 诚实边界 3 · Z 护栏与红线 4。

🔴 **本门禁最有价值的一条 = X2**：案例卡的 heavy-hex 4×5「91 比特」是**闭式现算**，
而 `lda_qeda.sc_topology_core.heavy_hex_topology` 的度直方图是**另一条独立引擎**
数出来的节点数 —— 两者必须相等。任一侧漂移（例如误用 brick-wall 错构型给出度 1/2
节点），本判据当场红。

🔴 命名纪律：节标签用 A / X / G / H / Z —— **刻意避开 B/E/S 前缀**（这三个是账本锚号
前缀，写进 CORE 门禁源码会被 K4 的文本代理误判成「覆盖了那些锚」⇒ 覆盖率虚高）。
"""

from __future__ import annotations

import io
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.smoke_kit import make_check          # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")

_ROWS, _COLS = 32, 32        # 旗舰版图容量（方阵）
_HH = (4, 5)                 # heavy-hex 对标 IBM 的档位


def _read(rel):
    fp = os.path.join(_HERE, rel)
    if not os.path.exists(fp):
        return ""
    with io.open(fp, encoding="utf-8", errors="replace") as f:
        return f.read()


def main():
    from lda_webui import schip_case as SC

    card = SC.case_card()

    # ═══════════════ A 模块自检与卡结构 ═══════════════
    check("A1 模块自检 12/12 PASS（**本门禁的存在意义：把它接进 CI**）",
          SC.run_selfchecks(verbose=False),
          "此前无任何 CORE 门禁调用 run_selfchecks ⇒ 改坏不亮红；本门禁闭环")
    check("A2 卡结构：endpoint / verdict / 三域字段齐备",
          card.get("endpoint") == "/api/schip_demo"
          and card.get("verdict") == "DESIGN_SIGNOFF"
          and all(k in card for k in ("identity", "flagship", "milestones",
                                      "findings", "gaps", "positioning")),
          "keys=%d" % len(card))

    # ═══════════════ X 跨源一致性（防文案漂移）═══════════════
    f = SC.capacity_closed_form(_ROWS, _COLS)
    want_coup = _ROWS * (_COLS - 1) + (_ROWS - 1) * _COLS      # 方阵边数闭式
    check("X1 方阵 %d×%d：n_qubits=%d · n_couplings=%d ≡ 闭式 r(c−1)+(r−1)c"
          % (_ROWS, _COLS, f["n_qubits"], f["n_couplings"]),
          f["n_qubits"] == _ROWS * _COLS and f["n_couplings"] == want_coup,
          "qubits=%d coup=%d want=%d" % (f["n_qubits"], f["n_couplings"], want_coup))

    hh = SC.heavy_hex_closed_form(*_HH)
    from lda_qeda import sc_topology_core as TC
    st = TC.topology_degree_stats(TC.heavy_hex_topology(*_HH))
    n_from_core = sum(int(v) for v in st["histogram"].values())
    check("X2 heavy-hex %d×%d：卡片闭式 %d 比特 ≡ 拓扑内核度直方图节点数 %d（两条独立引擎）"
          % (_HH[0], _HH[1], hh["n_qubits"], n_from_core),
          hh["n_qubits"] == n_from_core,
          "closed=%d core=%d hist=%s" % (hh["n_qubits"], n_from_core, st["histogram"]))

    check("X3 heavy-hex 无 4 邻居（max_degree=3 且内核 within_limit / no_four_neighbor）",
          hh["max_degree"] == 3 and st.get("max_degree") == 3
          and st.get("within_limit") is True and st.get("no_four_neighbor") is True,
          "closed_max=%s core_max=%s" % (hh["max_degree"], st.get("max_degree")))

    # ═══════════════ G 面板接线（免登录 · 零重计算）═══════════════
    rt = _read(os.path.join("lda_webui", "routes.py"))
    heavy = ""
    if "HEAVY_POST_PATHS = {" in rt:
        heavy = rt.split("HEAVY_POST_PATHS = {")[1].split("}")[0]
    check("G1 /api/schip_demo 不进 HEAVY_POST_PATHS（访客可直接打开）",
          '"/api/schip_demo"' not in heavy and "/api/schip_demo" not in heavy,
          "heavy 段长=%d" % len(heavy))
    check("G2 /api/schip_demo 注册为 GET 路由（与 qchip_demo 同属公开只读）",
          '"/api/schip_demo"' in rt.split("GET_ROUTES = {")[1].split("}")[0],
          "GET_ROUTES 段命中")

    gate_now = sum(int(m["gate"]) for m in SC.MILESTONES)
    check("G3 卡声明 gate_checks=%d ≡ MILESTONES 现算求和 %d"
          % (card["span"]["gate_checks"], gate_now),
          int(card["span"]["gate_checks"]) == gate_now and gate_now > 0,
          "declared=%s now=%d" % (card["span"]["gate_checks"], gate_now))

    # ═══════════════ H 诚实边界 ═══════════════
    check("H1 verdict 恒 DESIGN_SIGNOFF 且明标「非流片实测」",
          card["verdict"] == "DESIGN_SIGNOFF"
          and "设计期签核" in card.get("verdict_label", "")
          and "非流片实测" in card.get("verdict_label", ""),
          "label=%s" % card.get("verdict_label"))
    check("H2 规模口径明标「版图容量」（防被读成已制备芯片）",
          "版图容量" in card["scale_tiers"]["note"],
          "note=%s" % card["scale_tiers"]["note"][:40])
    gap_ids = [g["id"] for g in card["gaps"]]
    check("H3 缺口台账 5 条且 ID 齐全（G-A…G-E，如实登记未闭合）",
          card["gaps_total"] == 5
          and gap_ids == ["G-A", "G-B", "G-C", "G-D", "G-E"],
          "ids=%s" % gap_ids)

    # ═══════════════ Z 护栏与红线 ═══════════════
    guard = 0
    for bad in (lambda: SC.capacity_closed_form(0, 4),
                lambda: SC.capacity_closed_form(4, 0),
                lambda: SC.heavy_hex_closed_form(9, 9),
                lambda: SC.hilbert_space_log2(0)):
        try:
            bad()
        except ValueError:
            guard += 1
    check("Z1 护栏：rows/cols<1 · 未登记 hex 档位 · n_qubits<1 四例均抛 ValueError",
          guard == 4, "guard=%d/4" % guard)

    src = _read(os.path.join("lda_webui", "schip_case.py"))
    head = src.split("def run_selfchecks")[0]
    check("Z2 零重计算：卡模块不 import 求解器 / P&R / numpy（只复述闭式）",
          all(k not in head for k in ("import lda_qeda", "import lda_l2", "import lda_layout",
                                      "import numpy")),
          "静态扫描 head 段 %d 字符" % len(head))
    banned = ("qiskit", "cirq", "pennylane", "qutip", "braket")
    hit = [b for b in banned if ("import %s" % b) in src.lower()]
    check("Z3 零量子 SDK（静态扫描）", not hit, "hit=%s" % hit)

    check("Z4 无 LLM / 无网络调用（静态扫描）",
          all(k not in src for k in ("openai", "anthropic", "requests.get", "urllib.request")),
          "静态扫描 source")

    bad_n = globals().get("FAIL", 0)
    good_n = globals().get("PASS", 0)
    print("")
    print("超导芯片案例卡 门禁 smoke（D-216）：%d PASS / %d FAIL" % (good_n, bad_n))
    return 0 if bad_n == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
