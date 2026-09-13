"""反向偏压简化模型局限诚实护栏 smoke（v0.9.77 · Task #4）。

守护三件事：
  ① 正偏（V≥0）为已验证区间：V=+0.6 收敛、电流符号/量级符合短二极管闭式、
     且 reverse_bias_unvalidated=False（诚实标记未被误标）。
  ② 🔴 反偏（V<0）必带 reverse_bias_unvalidated=True —— 机器可发现的诚实标记，
     防止未来重构静默移除该局限披露（届时 I(V) 非物理、绝不可进判决）。
  ③ 反偏输出与饱和电流量级脱钩（非饱和 / 非物理），印证局限文档 §2 实测结论。

运行：python run_t1_reverse_bias_limitation_smoke.py（~3s，纯 numpy/scipy）
"""
from __future__ import annotations

import math
import sys

sys.path.insert(0, "lda")
from lda_solver.drift_diffusion_2d import (
    solve_pn_junction_2d_bias,
    sze_pn_junction_2d_closed_form,
)

VT = 0.02585


def _chk(name: str, ok: bool, detail: str = "") -> bool:
    mark = "[PASS]" if ok else "[FAIL]"
    print(f"  {mark} {name}" + (f" —— {detail}" if detail else ""))
    return ok


def main() -> int:
    print("=" * 68)
    print("反向偏压简化模型局限诚实护栏（reverse_bias_unvalidated）")
    print("=" * 68)
    results = []

    gold = sze_pn_junction_2d_closed_form()

    # ① 正偏已验证区间
    s_fwd = solve_pn_junction_2d_bias(0.6, nx=40, ny=40)
    I_fwd = s_fwd["I"]
    I_short_ideal = gold["I_s_short"] * (math.exp(0.6 / VT) - 1.0)
    results.append(_chk(
        "正偏 V=+0.6 收敛", s_fwd.get("converged") is True,
        f"converged={s_fwd.get('converged')}"))
    results.append(_chk(
        "正偏 V=+0.6 电流为正", I_fwd > 0.0, f"I={I_fwd:.3e} A"))
    results.append(_chk(
        "正偏 V=+0.6 量级符合短二极管闭式（0.1×~10×）",
        0.1 * I_short_ideal <= I_fwd <= 10.0 * I_short_ideal,
        f"cand={I_fwd:.3e}  ideal_short={I_short_ideal:.3e}"))
    results.append(_chk(
        "正偏 V=+0.6 reverse_bias_unvalidated=False（诚实标记未被误标）",
        s_fwd.get("reverse_bias_unvalidated") is False,
        f"flag={s_fwd.get('reverse_bias_unvalidated')}"))

    # ② 反偏必带诚实标记
    s_r1 = solve_pn_junction_2d_bias(-1.0, nx=40, ny=40)
    s_r2 = solve_pn_junction_2d_bias(-2.0, nx=40, ny=40)
    results.append(_chk(
        "反偏 V=−1.0 必带 reverse_bias_unvalidated=True",
        s_r1.get("reverse_bias_unvalidated") is True,
        f"flag={s_r1.get('reverse_bias_unvalidated')}"))
    results.append(_chk(
        "反偏 V=−2.0 必带 reverse_bias_unvalidated=True",
        s_r2.get("reverse_bias_unvalidated") is True,
        f"flag={s_r2.get('reverse_bias_unvalidated')}"))

    # ③ 反偏输出非物理（印证局限文档 §2）：与饱和电流完全脱钩
    I_sat = gold["I_s_short"]
    # V=−1.0 下模型给出巨流；正确饱和电流应 ≈ −I_s（nA 量级）。
    # 断言：反偏电流绝对值 >> 饱和电流（即未饱和、非物理），与文档实测一致。
    results.append(_chk(
        "反偏 V=−1.0 电流非饱和（|I| ≫ I_s，印证局限）",
        abs(s_r1["I"]) > 1.0e3 * I_sat,
        f"|I|={abs(s_r1['I']):.3e}  I_s={I_sat:.3e}  ratio={abs(s_r1['I'])/I_sat:.2e}"))
    results.append(_chk(
        "反偏 V=−2.0 迭代不收敛（conv=False，印证发散）",
        s_r2.get("converged") is False,
        f"converged={s_r2.get('converged')}"))

    npass = sum(1 for r in results if r)
    nfail = len(results) - npass
    print("-" * 68)
    print(f"反向偏压局限护栏：{npass} PASS / {nfail} FAIL")
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
