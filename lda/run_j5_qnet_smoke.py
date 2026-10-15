# -*- coding: utf-8 -*-
"""J5 量子网络与接口征程 · **M0 常驻门禁**（B519 分发后两体纠缠保真度 + 信道层）。

判据分节：
  A 锚项（B519 · 读自 BENCHMARK_DEFS 不硬编码）：tol 内 / 残差 >0 非代数恒等 /
    判据 D（严格单调 + 比值形态符合 RK4 标称阶）/ 反自证桩（候选 ≠ golden）/
    🔴 反向探针必须打「离散参数 n」（候选是数值收敛 ⇒ 物理参数扰动同时改 golden 与候选，
    残差仍 < tol ⇒ 无鉴别力，同 J4 血案）/ 防回退候选键
  B 能力层：`qnet_channel` 14 自检 + `qnet_distribution` 10 自检
  C 跨模块同源：`qnet_distribution.distribution_fidelity` ≡ B519 golden（逐位）；
    `qnet_channel.werner_fidelity` ≡ 数值核同律
  D 三表一致：`_TOL_BY_BID` ≡ DEFS tol；`_M_BY_BID` = 扫描格末端；默认档 ≡ DEFS default_params
  E 红线：零量子 SDK（不依赖 Qiskit/Cirq/PennyLane/QuTiP）；纯 numpy/math

🔴 `main()` 返回「真值」而非恒 0 —— 判据红必须让进程退出码非 0（J4 血案：恒 `return 0` = 假绿）。
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness import _batch_j5_numeric as J5  # noqa: E402
from lda_harness.benchmarks import BENCHMARK_DEFS  # noqa: E402
from lda_harness.smoke_kit import make_check  # noqa: E402  # 助手单一来源（棘轮 J3：禁自定义检查函数）
from lda_l2 import qnet_channel as CH  # noqa: E402
from lda_l2 import qnet_distribution as DS  # noqa: E402

check = make_check(globals(), ok_key="PASS", bad_key="FAIL", detail_fmt="  |  {d}")


def main() -> int:
    d519 = BENCHMARK_DEFS["B519"]
    p519 = dict(d519.get("default_params") or {})
    tol515 = float(d519["tol"])
    gold = float(d519["golden_fn"](**p519))

    print("=" * 78)
    print("J5 M0 门禁（B519 分发后两体纠缠保真度 · tol=%.1e · golden=%.15e）"
          % (tol515, gold))
    print("=" * 78)

    # ── A 锚项 ────────────────────────────────────────────────────────────
    print("\n[A] 锚项（B519）")
    n_end = int(J5._M_BY_BID["B519"])
    grid = list(J5._GRID_BY_BID["B519"])
    d_res = abs(J5.cand_b519(**p519) - gold)
    check("A1 默认档残差 > 0（非代数恒等）", d_res > 0.0, "resid=%.4e" % d_res)
    check("A2 默认档残差 < tol（判决通过）", d_res < float(d519["tol"]),
          "resid=%.4e < tol=%.1e" % (d_res, float(d519["tol"])))
    check("A3 基线残差 > 1e-12（不沉双精度地板）", d_res > 1e-12, "resid=%.4e" % d_res)

    chain = [(n, abs(J5.cand_b519(n=n, **p519) - gold)) for n in grid]
    mono = all(chain[i][1] > chain[i + 1][1] for i in range(len(chain) - 1))
    check("A4 判据 D：残差链严格单调递减", mono,
          " → ".join("%d:%.2e" % (n, d) for n, d in chain))
    # 🔴 防 0 除：候选≡golden（自证桩）时末档残差恒 0 ⇒ 必须判红而非崩溃（否则 A7 永不执行）
    ratios = [chain[i - 1][1] / chain[i][1] if chain[i][1] > 0 else float("inf")
              for i in range(1, len(chain))]
    check("A5 判据 D：比值形态符合 RK4 标称阶（趋向 16，粗端偏高）",
          4.0 <= ratios[-1] <= 22.0 and ratios[-1] <= ratios[0],
          " / ".join("%.2f" % r for r in ratios))
    dyn = (chain[0][1] / chain[-1][1]) if chain[-1][1] > 0 else float("nan")
    check("A6 动态范围 ≥ 1e4×（末档残差须 > 0）", bool(dyn >= 1e4),
          "dyn=%.3g×" % dyn)

    cand_end = J5.cand_b519(n=n_end, **p519)
    check("A7 反自证桩：候选 ≠ golden（非恒等）", abs(cand_end - gold) > 0.0,
          "cand=%.15e" % cand_end)
    check("A8 防回退候选键：DEFS 指向 J5 专用候选",
          d519.get("candidate") == "b519_entanglement_distribution_fidelity_cand",
          "key=%s" % d519.get("candidate"))

    # 🔴 反向探针：必须打「离散参数 n」（同 J4 血案）
    coarse = abs(J5.cand_b519(n=16, **p519) - gold)
    fine = abs(J5.cand_b519(n=n_end, **p519) - gold)
    check("A9 反向探针（离散参数 n）：粗档残差 ≫ 默认档残差（可被判据区分）",
          coarse > fine * 1e3, "coarse=%.3e vs fine=%.3e" % (coarse, fine))
    # 物理参数扰动虽有响应，但**两侧同扰动**后判决残差仍 < tol ⇒ 证明「必须用离散参数」这一纪律
    p_pert = {**p519, "l_depol_m": p519["l_depol_m"] * 1.1}
    pert_resid = abs(J5.cand_b519(n=n_end, **p_pert) - J5.golden_b519(**p_pert))
    check("A10 纪律佐证：物理参数扰动（两侧同扰动）后判决残差仍 < tol ⇒ 无判别力的反向探针",
          pert_resid < tol515, "pert_resid=%.3e < tol=%.1e" % (pert_resid, tol515))
    raised = False
    try:
        J5.cand_b519(n=0, **p519)
    except ValueError:
        raised = True
    check("A11 反向：n=0 必抛 ValueError", raised)

    # ── B 能力层 ──────────────────────────────────────────────────────────
    print("\n[B] 能力层自检")
    sc_ch = CH.selfcheck_qnet_channel()
    bad_ch = [k for k, v in sc_ch.items() if not v]
    check("B1 qnet_channel 全部自检通过", not bad_ch,
          "%d 项 · 失败=%s" % (len(sc_ch), bad_ch or "无"))
    sc_ds = DS.selfcheck_qnet_distribution()
    bad_ds = [k for k, v in sc_ds.items() if not v]
    check("B2 qnet_distribution 全部自检通过", not bad_ds,
          "%d 项 · 失败=%s" % (len(sc_ds), bad_ds or "无"))

    # ── C 跨模块同源 ──────────────────────────────────────────────────────
    print("\n[C] 跨模块同源（逐位）")
    ds_f = DS.distribution_fidelity(1.0e5, 2.2e4)
    check("C1 qnet_distribution.distribution_fidelity ≡ B519 golden（逐位）",
          abs(ds_f - gold) < 1e-15, "ds=%.15e vs golden=%.15e" % (ds_f, gold))
    ch_f = CH.link_fidelity(1.0e5, 2.2e4)
    check("C2 qnet_channel.link_fidelity ≡ B519 golden（逐位）",
          abs(ch_f - gold) < 1e-15, "ch=%.15e" % ch_f)
    check("C3 qnet_channel.werner_fidelity(p) ≡ 数值核同律",
          abs(CH.werner_fidelity(0.3) - (1.0 + 3.0 * 0.3) / 4.0) < 1e-15)

    # ── D 三表一致 ────────────────────────────────────────────────────────
    print("\n[D] 三表 / 默认档一致")
    check("D1 _TOL_BY_BID ≡ BENCHMARK_DEFS tol",
          float(J5._TOL_BY_BID["B519"]) == float(d519["tol"]),
          "tbl=%.1e defs=%.1e" % (J5._TOL_BY_BID["B519"], d519["tol"]))
    check("D2 _M_BY_BID = 扫描格末端", n_end == grid[-1], "n=%d end=%d" % (n_end, grid[-1]))
    check("D3 B519_DEFAULT_PARAMS ≡ DEFS default_params",
          dict(J5.B519_DEFAULT_PARAMS) == p519,
          "j5=%s defs=%s" % (J5.B519_DEFAULT_PARAMS, p519))

    # ── E 红线 ────────────────────────────────────────────────────────────
    print("\n[E] 红线")
    src = ""
    for fn in ("lda_l2/qnet_channel.py", "lda_l2/qnet_distribution.py",
               "lda_harness/_batch_j5_numeric.py"):
        p = os.path.join(_HERE, fn)
        if os.path.exists(p):
            src += open(p, encoding="utf-8").read()
    sdk = [s for s in ("qiskit", "cirq", "pennylane", "qutip", "qiskit_aer")
           if ("import " + s) in src]
    check("E1 主权边界：零量子 SDK（不依赖 Qiskit/Cirq/PennyLane/QuTiP）",
          not sdk, "命中=%s" % (sdk or "无"))

    bad = globals().get("FAIL", 0)
    print("\n" + "=" * 78)
    print("J5 门禁：%s（FAIL=%d）" % ("ALL PASS" if bad == 0 else "有红色", bad))
    print("=" * 78)
    return 0 if bad == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
