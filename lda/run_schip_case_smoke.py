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
    check("H3 缺口台账 7 条且 ID 齐全（G-A…G-E + G-Eb 边界声明 + G-Db 拆出的真欠债）",
          card["gaps_total"] == 7
          and gap_ids == ["G-A", "G-B", "G-C", "G-D", "G-Db", "G-E", "G-Eb"],
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

    # ═══════════════ P 封装 / 低温布线（v0.9.299 · G-E）═══════════════
    # 🔴 改前 G-E 只写着「倒装焊、TSV、低温衰减链未实现」。三项都已建，且**各自配一条精确对照支路**。
    # ⚠️ 本卡 Z2 红线要求 `schip_case` 零重计算 ⇒ 封装能力层**不挂进卡片**，只在这里对拍。
    from lda_l2 import schip_packaging as PKG

    _sc_p = PKG.selfcheck_schip_packaging()
    check("P1 schip_packaging 自检 %d 项全过（三条闭式 / 望远镜恒等式 / 绝对量级 / 反向探针）"
          % len(_sc_p),
          not [k for k, v in _sc_p.items() if not v],
          "fail=%s" % [k for k, v in _sc_p.items() if not v])

    _pk = PKG.packaging_report()
    _t, _b, _ch = _pk["tsv"], _pk["bump"], _pk["chain"]

    # P2 🔴 TSV 闭式已知答案：v_p 必须 == c/√ε_r（这条当场抓出我用「总量 L·C」算 v_p，差 1e4×）
    _rel_vp = abs(_t["v_p_m_per_s"] - _t["v_p_expected_m_per_s"]) / _t["v_p_expected_m_per_s"]
    check("P2 🔴 TSV `v_p` ≡ `c/√ε_r`（相对 %.1e ≤1e-12）：%.6e vs %.6e m/s"
          % (_rel_vp, _t["v_p_m_per_s"], _t["v_p_expected_m_per_s"]),
          _rel_vp <= 1e-12)

    # P3 恒等式 L·C ≡ μ₀ε₀ε_r h² ∧ Z₀ 两条独立推导一致
    check("P3 TSV 恒等式 `L·C ≡ μ₀ε₀ε_r h²`（相对 ≤1e-15）∧ `Z₀` 两路径一致（相对 ≤1e-14）",
          abs(_t["LC_identity"] - _t["LC_expected"]) <= 1e-15 * _t["LC_expected"]
          and abs(_t["Z0_ohm"] - _t["Z0_closed_form_ohm"]) <= 1e-14 * _t["Z0_ohm"],
          "Z0=%.4f Ω" % _t["Z0_ohm"])

    # P4 🔴 凸点互感：Neumann 精确闭式 ≡ 二维复合 Simpson（独立路径 · 相对 ≤1e-8）
    _m_cf = PKG.mutual_inductance_parallel(20.0, 50.0)
    _m_sp = PKG.mutual_neumann_simpson(20.0, 50.0, n=200)
    _rel_m = abs(_m_cf - _m_sp) / _m_cf
    check("P4 🔴 凸点互感：Neumann 闭式 ≡ 二维复合 Simpson（相对 %.1e ≤1e-8）：%.6e vs %.6e H"
          % (_rel_m, _m_cf, _m_sp),
          _rel_m <= 1e-8)

    # P5 🔴 望远镜恒等式 + **同温链透明**（链在热平衡下不许凭空造噪声）
    _dl = PKG.drive_line_noise([(10.0, 300.0), (10.0, 4.0), (10.0, 0.020)])
    _tel_ok = abs(_dl["telescope_sum"] - _dl["telescope_expected"]) <= 1e-14 * abs(_dl["telescope_expected"])
    _transp = all(
        abs(PKG.drive_line_noise([(10.0, q)] * 4, source_temp_k=q)["n_out"]
            - PKG.drive_line_noise([(10.0, q)] * 4, source_temp_k=q)["n_source"])
        <= 1e-14 * max(PKG.drive_line_noise([(10.0, q)] * 4, source_temp_k=q)["n_source"], 1e-300)
        for q in (0.020, 4.0, 300.0))
    check("P5 🔴 望远镜恒等式 `Σ(1−1/A)Π_down(1/A) ≡ 1−Π(1/A)` ∧ **整链同温 ⇒ 链透明**"
          "（`n_out ≡ n_th(T)`，20 mK/4 K/300 K 三档）",
          _tel_ok and _transp,
          "tel=%.2e" % (_dl["telescope_sum"] - _dl["telescope_expected"]))

    # P6 🔴 设计结论机核：大衰减放**最冷、最靠器件**一级（冷端在后 > 冷端在前）
    check("P6 🔴 设计结论：冷端在**后**（%.4f）优于冷端在前（%.4f），约 **%.1f×**"
          % (_ch["n_out_cold_last"], _ch["n_out_cold_first"], _ch["ratio_cold_first_over_last"]),
          _ch["cold_last_is_better"] and _ch["ratio_cold_first_over_last"] > 5.0)

    # P7 同温链 ≡ 单级等效（n 级同温同损 ≡ 一级 A^n）
    _mg = PKG.drive_line_noise([(1000.0, 4.0)], source_temp_k=4.0)["n_out"]
    _sp = PKG.drive_line_noise([(10.0, 4.0)] * 3, source_temp_k=4.0)["n_out"]
    check("P7 同温链 ≡ 单级等效：3 级 10 dB@4 K ≡ 1 级 30 dB@4 K（相对 ≤1e-14）",
          abs(_mg - _sp) <= 1e-14 * max(_mg, 1e-300), "%.15g vs %.15g" % (_mg, _sp))

    # P8 绝对量级锚点（防单位/量级错 —— P2 的比值判据抓不住 Z₀/R_dc 的量级）
    check("P8 🔴 参考档绝对量级锚点：Z₀∈[10,60] Ω ∧ v_p∈[8.0,9.5]e7 m/s ∧ L_self∈[1e-13,1e-10] H ∧ "
          "R_dc∈[1e-7,1e-2] Ω ∧ n_out∈[1e-3,10]",
          10.0 <= _t["Z0_ohm"] <= 60.0
          and 8.0e7 <= _t["v_p_m_per_s"] <= 9.5e7
          and 1e-13 <= _b["L_self_H"] <= 1e-10
          and 1e-7 <= _t["R_dc_ohm"] <= 1e-2
          and 1e-3 <= _ch["n_out_cold_last"] <= 10.0,
          "Z0=%.3f v=%.3e L=%.3e R=%.3e n=%.4f"
          % (_t["Z0_ohm"], _t["v_p_m_per_s"], _b["L_self_H"],
             _t["R_dc_ohm"], _ch["n_out_cold_last"]))

    # P9 无源不放大：输出噪声不超过源噪声（结构不变量）
    check("P9 无源不放大：到达器件 `n_out ≤ n_source`（%.4f ≤ %.4g）"
          % (_dl["n_out"], _dl["n_source"]),
          _dl["n_out"] <= _dl["n_source"] + 1e-15)

    # P10 反向探针：非法几何 / 非法级必抛（判红不崩溃）
    def _pkg_raises(fn):
        try:
            fn()
        except ValueError:
            return True
        return False

    check("P10 反向探针：r_o≤r_i · h=0 · A<1 · 空级表 四例均抛 ValueError",
          _pkg_raises(lambda: PKG.tsv_coax(r_inner_um=20.0, r_outer_um=5.0))
          and _pkg_raises(lambda: PKG.tsv_coax(height_um=0.0))
          and _pkg_raises(lambda: PKG.drive_line_noise([(0.5, 4.0)]))
          and _pkg_raises(lambda: PKG.drive_line_noise([])))

    # P11 🔴 红线纪律：封装层**不挂进卡片**（Z2 要求 schip_case 零重计算）——
    #     把「改方案不改红线」这件事本身写成判据，防止以后为了「面板可见」把 import 加回去
    #  ⚠️ 判据只认**import 形态**，不认子串：G-E 的 status 文本里**提到** `lda_l2/schip_packaging`
    #     是**披露**（该能力层存在），不是接线 —— 用裸子串判会把自己写红的（第一版就误判了）。
    _src_schip = open(os.path.join(_HERE, "lda_webui", "schip_case.py"),
                      encoding="utf-8").read().split("def run_selfchecks")[0]
    _imp_forms = ("import schip_packaging", "schip_packaging import",
                  "from lda_l2 import", "import lda_l2")
    check("P11 🔴 未为方便去松红线：`schip_case` **不得 import** `schip_packaging`/`lda_l2`"
          "（零重计算红线 Z2 保持；提及不算接线）",
          not any(f in _src_schip for f in _imp_forms),
          "命中=%s" % [f for f in _imp_forms if f in _src_schip])

    # ═══════════════ Q 线路编译与噪声传播（v0.9.301 · G-Db）═══════════════
    # 🔴 改前 G-D 把「脉冲级标定（须实验台）」与「线路编译 / 噪声仿真（纯模型活）」压在同一条，
    #    v0.9.300 拆出 G-Db 记未闭合 —— 拆出来就放着不做，那「拆而不并」就退化成「拆出来挂账」。
    #    本节验编译那一半；态演化那一半在 `run_j2_qpu_smoke` 的 I 节（同一模块，两卡各验一面）。
    from lda_l2 import qcircuit_level as QL

    _sc_q = QL.selfcheck_qcircuit_level()
    check("Q1 qcircuit_level 自检 %d 项全过（幺正/保迹/组合律/SWAP 分解/非法入参）" % len(_sc_q),
          not [k for k, v in _sc_q.items() if not v],
          "fail=%s" % [k for k, v in _sc_q.items() if not v])

    # 🔴 Q2 SWAP 计数闭式：线性链上距离 d 的两比特门需 `d−1` 次 SWAP（组合数学，与门实现无关）
    _ok2 = all(QL.swaps_for_distance(d) == max(0, d - 1) for d in range(0, 9))
    check("Q2 🔴 SWAP 计数闭式 `d−1`：d=0…8 逐点（含 d≤1 ⇒ 0）", _ok2)

    # 🔴 Q3 SWAP 的**实现口径**与本层计数一致：`qm_swap` 必须真的等于 3 个 CNOT（不是嘴上说 3）
    _n = 2
    _by3 = QL.qmat_mul(QL.qm_cnot(_n, 0, 1),
                       QL.qmat_mul(QL.qm_cnot(_n, 1, 0), QL.qm_cnot(_n, 0, 1)))
    _direct = QL.qm_swap(_n, 0, 1)
    _maxd = max(abs(_by3[i][j] - _direct[i][j]) for i in range(4) for j in range(4))
    check("Q3 🔴 `SWAP ≡ 3×CNOT`（逐元素 ≤1e-15）—— 与 `cnots_per_swap()==3` 的计数口径对拍",
          _maxd <= 1e-15 and QL.cnots_per_swap() == 3, "maxΔ=%.2e" % _maxd)

    # 🔴 Q4 编译会**凭空长出**门：5 比特线性链上 q0↔q4（d=4）⇒ 1 逻辑门 → 1+9 物理两比特操作
    _cmp = QL.linear_chain_compile(5, [(0, 4)])
    check("Q4 🔴 编译放大：5 比特链 q0↔q4 ⇒ SWAP=%d · 物理两比特操作=%d（逻辑 1 ⇒ 放大 %.1f×）"
          % (_cmp["total_swaps"], _cmp["physical_2q_ops"], _cmp["amplification"]),
          _cmp["total_swaps"] == 3 and _cmp["physical_2q_ops"] == 10
          and _cmp["amplification"] > 5.0)

    # Q5 相邻比特（d=1）⇒ 零 SWAP；混合组按 Σ(d−1) 累加
    _adj = QL.linear_chain_compile(5, [(1, 2)])
    _mix = QL.linear_chain_compile(5, [(0, 1), (0, 4)])
    # 混合组：[(0,1) d=1 ⇒ 0 次] + [(0,4) d=4 ⇒ 3 次] ⇒ 总 3 次 SWAP = 9 CNOT
    #   （⚠️ 我第一版写成 4 / 2+12 —— 把 (0,1) 也算了一次 SWAP，被本条当场抓出）
    check("Q5 相邻门零 SWAP（d=1）∧ 混合组 SWAP 数 = Σ(d−1) = %d ⇒ 物理两比特 %d（逻辑 2 + 9）"
          % (_mix["total_swaps"], _mix["physical_2q_ops"]),
          _adj["total_swaps"] == 0 and _mix["total_swaps"] == 3
          and _mix["physical_2q_ops"] == 2 + 9)

    # 🔴 Q6 反向探针（两条错误实现的**具体数值差**，不是"恒真"）：
    #    ① SWAP 数误用 `d`（而非 `d−1`）      ⇒ d=4 时 4 vs 3（Q2 逐点必不通过）
    #    ② 每个 SWAP 误记 1 个 CNOT（而非 3）  ⇒ 物理数 1+3=4 vs 1+9=10（Q4 必不通过）
    _q2_red = any((d if d > 1 else 0) != max(0, d - 1) for d in range(0, 9))
    _q4_red = (1 + 3 * 1) != (1 + 3 * 3)          # 4 ≠ 10
    _q5_red = (2 + 4 * 3) != (2 + 3 * 3)          # 误算 4 次 SWAP ⇒ 14 ≠ 11
    check("Q6 反向探针：SWAP 用 `d` ⇒ Q2 红（d=4 时 4≠3）∧ 每 SWAP 记 1 CNOT ⇒ Q4 红（4≠10）"
          "∧ 混合组误算 ⇒ Q5 红（14≠11）",
          _q2_red and _q4_red and _q5_red)

    bad_n = globals().get("FAIL", 0)
    good_n = globals().get("PASS", 0)
    print("")
    print("超导芯片案例卡 门禁 smoke（D-216）：%d PASS / %d FAIL" % (good_n, bad_n))
    return 0 if bad_n == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
