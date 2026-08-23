"""D-88 · QEDA 求解器级补强：transmon-resonator 色散读出统一入口。

把三能级色散读出严格求解器（`lda_solver/qubit_resonator_solver.py`）包装为
设计→验收入口。死标量验收（LLM 不进判决路径）：
  (a) 色散区有效 Δ/g ≥ 5；
  (b) χ_num ↔ χ_an（Blais 三能级修正）rel ≤ 10%；
  (c) 共振拉比分裂自洽 g_rel ≤ 2%；
  (d) α 修正必要性：二能级近似误差 ≥ 3× 三能级。

求解器级补强点：现有 readout 验证（D-43）为二能级 JC（χ=g²/Δ，无非谐性）；
本求解器引入 |f⟩ 态严格对角化 → χ=g²α/(Δ(Δ+α))（α<0 时 χ 为负——符号即
非谐性标志），并输出 n_crit / Purcell 率 / AC Stark——readout 设计闭环所需
全套物理量。
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = os.path.dirname(_HERE)
if _LDA_ROOT not in sys.path:
    sys.path.insert(0, _LDA_ROOT)

from lda_solver.qubit_resonator_solver import solve_qubit_resonator  # noqa: E402


def design_qubit_resonator(f_q: float = 5.0, alpha: float = -0.3,
                           f_r: float = 6.0, g: float = 0.1,
                           kappa: float = 0.005, M: int = 25,
                           out: Optional[str] = None) -> Dict[str, Any]:
    """D-88 transmon-resonator 色散读出设计→验收（三能级严格求解）。"""
    t0 = time.perf_counter()
    r = solve_qubit_resonator(f_q=f_q, alpha=alpha, f_r=f_r, g=g,
                              kappa=kappa, M=M)
    r["elapsed_s"] = round(time.perf_counter() - t0, 2)
    r["ok"] = bool(r["acceptance"]["passed"])
    r["title"] = "D-88 QEDA 求解器级补强：transmon-resonator 色散读出"
    r["note"] = ("三能级 transmon + Fock 谐振器严格对角化 ↔ Blais 色散修正解析式"
                 "（χ=g²α/(Δ(Δ+α))）双路径；二能级 JC（χ=g²/Δ）误差 ≥3× 证明"
                 "非谐性修正必要。输出 n_crit/Purcell/AC Stark 全套 readout 物理量。")
    r["design"] = {
        "f_q_ghz": float(f_q), "alpha_ghz": float(alpha),
        "f_r_ghz": float(f_r), "g_ghz": float(g), "kappa_ghz": float(kappa),
        "M": M,
    }
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
    return r


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="D-88 QEDA 色散读出求解器")
    ap.add_argument("--f_q", type=float, default=5.0)
    ap.add_argument("--alpha", type=float, default=-0.3)
    ap.add_argument("--f_r", type=float, default=6.0)
    ap.add_argument("--g", type=float, default=0.1)
    ap.add_argument("--kappa", type=float, default=0.005)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    r = design_qubit_resonator(f_q=a.f_q, alpha=a.alpha, f_r=a.f_r,
                               g=a.g, kappa=a.kappa, out=a.out)
    print(json.dumps({k: r[k] for k in
                      ("chi_num_ghz", "chi_3level_ghz", "chi_2level_ghz",
                       "chi_rel_err_3level", "chi_rel_err_2level", "n_crit",
                       "t1_purcell_us", "ac_stark_1ph_ghz",
                       "acceptance", "verdict")},
                     ensure_ascii=False, indent=2)[:2500])
    return 0 if (r.get("ok") and r["acceptance"]["passed"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
