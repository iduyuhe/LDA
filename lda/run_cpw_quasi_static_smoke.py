#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CPW 准静态场解 + 版图反提 门禁 smoke（D-217 建 · D-224 扩 · 净增 0 锚 · 能力层）。

═══ 判什么（分五节 · 18 条）═══
A 闭式正确性 3 · X 极限与单调 4 · G 版图反提 6 · H 跨模块对账 2 · Z 负结果与红线 3。

🔴 **本门禁要守住的不是"公式对不对"，而是四件工程事实**：
  ① **半反提必须自曝**：`w` 从版图真回提，`g` 在 **legacy** 版图里**没有共面字段**
     （Transmon 的地建在 y=±gj 的**上下方**）⇒ `gap_source` 必须标 `ground_gap_equiv`，
     且 `caveat` 里必须出现"半反提"。不许把等效假设说成实测（G1/G2）。
  ② **真反提必须真**（v0.9.276 · D-224）：`cpw_ground="coplanar"` 版图带
     `coplanar_ground=True` 地条 ⇒ `gap_source="layout_true"` 且 `g` 从几何读回 1.0 µm
     残差 <1e-12（G4）；同 g 下 `layout_true` 与 `ground_gap_equiv` 的 n_eff/ε_eff/Z0
     **逐位相同** ⇒ 证明差异只在"g 从哪来"，不是另算一套物理（G5）。
  ③ **标记必须被消费**：抹掉 `coplanar_ground` ⇒ 必须回落到 `ground_gap_equiv`（G6）。
     否则该标记只是装饰，"真反提"是可自封的。
  ④ **不猜**：拿不到间隙就返回 `ok=False` 并给原因，不得默认一个 g（G3）。
  ⑤ **设计输入第一次被版图回答**：`n_eff=2.5`（既有 CPW 锚的默认设计值）与
     从几何反提的 `n_eff=2.4949`（w=10/g=6/Si）相对差 **0.2037%** ⇒ 判 CONSISTENT。
     这是"版图 → 参数"断点被补上的**可复算证据**（H 组）。

🔴 命名纪律：节标签 A/X/G/H/Z —— 避开 B/E/S（账本锚号前缀），防 K4 文本代理虚高覆盖。
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


def _read(rel):
    fp = os.path.join(_HERE, rel)
    if not os.path.exists(fp):
        return ""
    with io.open(fp, encoding="utf-8", errors="replace") as f:
        return f.read()


def main():
    from lda_qeda import cpw_quasi_static as QS
    from lda_qeda import sc_layout as SL

    # ═══════════════ A 闭式正确性 ═══════════════
    cf = QS.cpw_closed_form(10.0, 6.0, h_um=None, eps_r=11.45)
    check("A1 50 Ω 惯例：w=10/g=6/Si ⇒ Z0∈[50,52] ∧ εeff∈[6.2,6.25]",
          50.0 <= cf["Z0_ohm"] <= 52.0 and 6.2 <= cf["eps_eff"] <= 6.25,
          "Z0=%.3f εeff=%.4f" % (cf["Z0_ohm"], cf["eps_eff"]))

    fin = QS.cpw_closed_form(10.0, 6.0, h_um=500.0, eps_r=11.45)
    dev30 = abs(fin["Z0_30pi_ohm"] - fin["Z0_ohm"]) / fin["Z0_ohm"]
    check("A2 准 TEM 恒等 Z0·√(C_air·C_d)·c0 ≡ 1（两组残差<1e-12）∧ 30π 形式偏差∈(1e-4,2e-3)",
          abs(cf["zc_product"] - 1.0) < 1e-12 and abs(fin["zc_product"] - 1.0) < 1e-12
          and 1e-4 < dev30 < 2e-3,
          "dev30=%.3e" % dev30)

    import math
    check("A3 完全椭圆积分两点闭式：K(0)=π/2 ∧ K(1/√2)=1.8540746773013719",
          abs(QS.ellip_k(0.0) - math.pi / 2) < 1e-15
          and abs(QS.ellip_k(1.0 / math.sqrt(2.0)) - 1.8540746773013719) < 1e-13,
          "K(0)=%.15f" % QS.ellip_k(0.0))

    # ═══════════════ X 极限与单调 ═══════════════
    vac = QS.cpw_closed_form(10.0, 6.0, h_um=None, eps_r=1.0)
    check("X1 真空极限 εr=1 ⇒ n_eff=1（残差<1e-12）",
          abs(vac["n_eff"] - 1.0) < 1e-12, "n_eff=%.15f" % vac["n_eff"])

    lim = QS.cpw_closed_form(10.0, 6.0, h_um=1e7, eps_r=11.45)
    want = 0.5 * (1.0 + 11.45)
    check("X2 h→∞ ⇒ εeff→(1+εr)/2=%.4f（相对差<1e-4）" % want,
          abs(lim["eps_eff"] - want) / want < 1e-4,
          "εeff=%.6f vs %.6f" % (lim["eps_eff"], want))

    e500 = QS.cpw_closed_form(10.0, 6.0, h_um=500.0)["eps_eff"]
    e50 = QS.cpw_closed_form(10.0, 6.0, h_um=50.0)["eps_eff"]
    e10 = QS.cpw_closed_form(10.0, 6.0, h_um=10.0)["eps_eff"]
    check("X3 衬底变薄 ⇒ εeff 单调下降（500→50→10 µm：%.4f > %.4f > %.4f）"
          % (e500, e50, e10), e500 > e50 > e10 and e10 < 0.9 * e500,
          "下降 %.1f%%" % (100.0 * (1 - e10 / e500)))

    z_lo = QS.cpw_closed_form(6.0, 6.0, h_um=None)["Z0_ohm"]
    z_hi = QS.cpw_closed_form(20.0, 6.0, h_um=None)["Z0_ohm"]
    e_lo = QS.cpw_closed_form(10.0, 6.0, h_um=None, eps_r=4.0)
    e_hi = QS.cpw_closed_form(10.0, 6.0, h_um=None, eps_r=11.45)
    check("X4 单调性：w↑⇒Z0↓ ∧ εr↑⇒εeff↑ 且 Z0↓",
          z_hi < z_lo and e_hi["eps_eff"] > e_lo["eps_eff"] and e_hi["Z0_ohm"] < e_lo["Z0_ohm"],
          "Z0(6µm)=%.2f > Z0(20µm)=%.2f" % (z_lo, z_hi))

    # ═══════════════ G 版图反提（半反提必须自曝）═══════════════
    lay = QS.cpw_from_layout(SL.transmon_cell(), ground_gap_um=1.0)
    check("G1 Transmon 版图反提：w=0.5 µm 真回提 ∧ gap_source=ground_gap_equiv",
          lay.get("ok") is True and abs(lay["w_um"] - 0.5) < 1e-12
          and lay["gap_source"] == "ground_gap_equiv",
          "w=%.3f g=%.3f Z0=%.3f" % (lay["w_um"], lay["g_um"], lay["Z0_ohm"]))

    check("G2 🔴 caveat 明标「半反提」（等效假设不得说成实测）",
          "半反提" in lay.get("caveat", "") and "上下" in lay.get("caveat", ""),
          lay.get("caveat", "")[:60])

    miss = QS.cpw_from_layout(SL.transmon_cell())
    check("G3 无间隙输入 ⇒ ok=False 且给原因（不猜）",
          miss.get("ok") is False and "不猜" in miss.get("reason", ""),
          miss.get("reason", "")[:60])

    # ── G4–G6 · v0.9.276（D-224）：真反提档（gap_source="layout_true"）──
    cp_els = SL.transmon_cell(cpw_ground="coplanar")
    tr = QS.cpw_from_layout(cp_els)
    check("G4 共面地模式 ⇒ gap_source=layout_true ∧ g 从版图真读回 1.0 µm（残差<1e-12）"
          "∧ 共面地条 4 条",
          tr.get("ok") is True and tr["gap_source"] == "layout_true"
          and abs(tr["gap_um"] - 1.0) < 1e-12
          and tr.get("n_coplanar_grounds") == 4,
          "g=%.12f idx=%s n_cop=%s" % (tr.get("gap_um", -1),
                                        tr.get("gap_element_idx"),
                                        tr.get("n_coplanar_grounds")))

    # 同 g ⇒ 同物理量：真反提与等效反提必须**逐位相同**（差异只在"g 从哪来"）
    eq = QS.cpw_from_layout(SL.transmon_cell(), ground_gap_um=1.0)
    # 🔴 突变下必须**判红不崩溃**：两档任一 ok=False（如真反提被关掉）时不得索引缺键
    pair_ok = (tr.get("ok") is True and eq.get("ok") is True)
    d_n = abs(tr.get("n_eff", 0.0) - eq.get("n_eff", 0.0)) if pair_ok else float("nan")
    d_e = abs(tr.get("eps_eff", 0.0) - eq.get("eps_eff", 0.0)) if pair_ok else float("nan")
    d_z = abs(tr.get("Z0_ohm", 0.0) - eq.get("Z0_ohm", 0.0)) if pair_ok else float("nan")
    check("G5 同一 g 下 layout_true ≡ ground_gap_equiv（n_eff/eps_eff/Z0 逐位相同）"
          "⇒ 真反提不是另算一套物理",
          pair_ok and d_n < 1e-15 and d_e < 1e-15 and d_z < 1e-12,
          "pair_ok=%s Δn_eff=%.3e ΔZ0=%.3e" % (pair_ok, d_n, d_z))

    # 🔴 反向：抹掉 coplanar_ground 标记 ⇒ 必须回落契约（证明标记真被消费）
    stripped = [{k: v for k, v in e.items() if k != "coplanar_ground"} for e in cp_els]
    ng = QS.cpw_from_layout(stripped, ground_gap_um=1.0)
    check("G6 🔴 反向：抹掉 coplanar_ground 标记 ⇒ 必回 ground_gap_equiv（标记不是装饰）",
          ng.get("gap_source") == "ground_gap_equiv"
          and SL.cpw_gap_from_layout(stripped) is None,
          "src=%s" % ng.get("gap_source"))

    # ═══════════════ H 跨模块对账（本门禁的核心价值）═══════════════
    so = QS.layout_to_resonator_signoff(10.0, 6.0, 4000.0, h_um=500.0)
    check("H1 反提 n_eff=%.4f vs 设计输入 2.5 ⇒ 相对差 %.4f%% 判 CONSISTENT"
          % (so["n_eff_layout"], 100 * so["n_eff_rel_diff"]),
          so["verdict"] == "CONSISTENT" and so["n_eff_rel_diff"] < 0.02,
          "f0_layout=%.4f f0_design=%.4f GHz" % (so["f0_layout_ghz"], so["f0_design_ghz"]))

    ratio_f = so["f0_design_ghz"] / so["f0_layout_ghz"]
    ratio_n = so["n_eff_layout"] / so["n_eff_design"]
    check("H2 f0 同口径代数关系：f0_design/f0_layout ≡ n_eff_layout/n_eff_design（残差<1e-12）",
          abs(ratio_f - ratio_n) < 1e-12,
          "ratio_f=%.15f ratio_n=%.15f" % (ratio_f, ratio_n))

    # ═══════════════ Z 负结果与红线 ═══════════════
    w = QS.why_not_anchored()
    check("Z1 负结果机器化：anchorable=False ∧ 三问齐备 ∧ 候选实测记录 ∧ 重评条件",
          w["anchorable"] is False and w["q1_exact_combinatorial"] is False
          and "candidate_probe" in w and w["candidate_probe"].get("observed")
          and "revisit_condition" in w,
          "候选方法=%s" % w["candidate_probe"]["method"][:30])

    guard = 0
    for bad in (lambda: QS.cpw_closed_form(0.0, 6.0),
                lambda: QS.cpw_closed_form(10.0, 0.0),
                lambda: QS.cpw_closed_form(10.0, 6.0, eps_r=0.5),
                lambda: QS.resonator_f0_ghz(0.0, 2.5),
                lambda: QS.ellip_k(1.0)):
        try:
            bad()
        except ValueError:
            guard += 1
        except Exception:
            # 🔴 突变下必须「判红」不得「崩溃」：被 patch 的实现可能抛 ZeroDivisionError /
            # TypeError 等（实测 M8 λ/2 版本即抛 ZeroDivisionError ⇒ 旧窄捕令整门禁 rc=99、
            # 后续判据全丢）。非 ValueError 不算护栏生效，但不得让门禁崩。
            pass
    check("Z2 护栏：五例非法输入均抛 ValueError", guard == 5, "guard=%d/5" % guard)

    src = _read(os.path.join("lda_qeda", "cpw_quasi_static.py"))
    banned = ("qiskit", "cirq", "pennylane", "qutip", "requests", "urllib", "socket",
              "openai", "anthropic", "scipy")
    hit = [b for b in banned
           if ("import %s" % b) in src.lower() or ("from %s" % b) in src.lower()]
    check("Z3 零第三方 / 零网络 / 零 LLM / 零 scipy（静态扫描）",
          not hit and "open(" not in src, "hit=%s" % hit)

    bad_n = globals().get("FAIL", 0)
    good_n = globals().get("PASS", 0)
    print("")
    print("CPW 准静态 + 版图反提 门禁 smoke（D-217）：%d PASS / %d FAIL" % (good_n, bad_n))
    return 0 if bad_n == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
