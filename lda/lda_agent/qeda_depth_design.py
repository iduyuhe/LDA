"""D-91 · QEDA 纵深三件套统一入口（多能级展开 / 驱动场 / 读出串扰）。

把 `lda_solver/qeda_depth_solver.py` 包装为设计→验收入口。死标量验收
（LLM 不进判决路径）：①多能级 χ 收敛 3→6 <1% + Blais 解析 rel≤10%；
②Rabi 自洽 ≤1% + AC Stark 解析 ≤10%；③串扰 ZZ 耦合自洽 + 对称 + 弱耦合量级。
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

from lda_solver.qeda_depth_solver import solve_qeda_depth  # noqa: E402


def design_qeda_depth(f_q: float = 5.0, alpha: float = -0.3,
                      f_r: float = 6.0, g: float = 0.1,
                      Omega: float = 0.05, delta_d: float = 0.4,
                      f_q2: float = 5.2, g2: float = 0.08,
                      out: Optional[str] = None) -> Dict[str, Any]:
    """D-91 QEDA 纵深三件套设计→验收。"""
    t0 = time.perf_counter()
    r = solve_qeda_depth(f_q=f_q, alpha=alpha, f_r=f_r, g=g,
                         Omega=Omega, delta_d=delta_d,
                         f_q2=f_q2, g2=g2)
    r["elapsed_s"] = round(time.perf_counter() - t0, 2)
    r["ok"] = bool(r["passed"])
    r["title"] = "D-91 QEDA 纵深三件套（多能级展开 / 驱动场 / 读出串扰）"
    r["note"] = ("①多能级电荷基底展开：χ 3→6 能级收敛 <1% 证明三能级模型自洽；"
                 "②驱动场 RWA：共振 Rabi 自洽 + 失谐 AC Stark 解析对拍；"
                 "③共享谐振器媒介 ZZ 耦合：自洽 + 互换对称 + 弱耦合量级。")
    r["design"] = {
        "f_q_ghz": float(f_q), "alpha_ghz": float(alpha),
        "f_r_ghz": float(f_r), "g_ghz": float(g),
        "Omega_ghz": float(Omega), "delta_d_ghz": float(delta_d),
        "f_q2_ghz": float(f_q2), "g2_ghz": float(g2),
    }
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
    return r


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="D-91 QEDA 纵深三件套")
    ap.add_argument("--f_q", type=float, default=5.0)
    ap.add_argument("--alpha", type=float, default=-0.3)
    ap.add_argument("--f_r", type=float, default=6.0)
    ap.add_argument("--g", type=float, default=0.1)
    ap.add_argument("--Omega", type=float, default=0.05)
    ap.add_argument("--delta_d", type=float, default=0.4)
    ap.add_argument("--f_q2", type=float, default=5.2)
    ap.add_argument("--g2", type=float, default=0.08)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    r = design_qeda_depth(f_q=a.f_q, alpha=a.alpha, f_r=a.f_r, g=a.g,
                          Omega=a.Omega, delta_d=a.delta_d,
                          f_q2=a.f_q2, g2=a.g2, out=a.out)
    print(json.dumps({k: r[k] for k in ("passed", "acceptance", "verdict")},
                     ensure_ascii=False, indent=2)[:1500])
    return 0 if (r.get("ok") and r["passed"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
