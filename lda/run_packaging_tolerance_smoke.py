"""LDA 可封装性链烟雾测试（CORE_SMOKES · v0.9.65+）。

死标量比对，LLM 不进判决路径。覆盖：
  ① 单调性反向测试：σ_align↑ → 封装良率↓（且反之不成立）
  ② 设计旋钮反馈：MFD↑ → 横向容差↑ → 封装良率↑（T3 验收：设计改动→良率同向变化）
  ③ 可复现性：固定种子 → 同输入同输出（自证互证 diff 一致）
  ④ 自证互证：解析 Rayleigh 闭式 == 蒙特卡洛（证明不是假闭式）
  ⑤ 耦合效率随横向/角向偏移单调下降
  ⑥ P-CPO 间距合规：pitch < 几何下界 → pitch_compliant=False（诚实不假绿）
  ⑦ provenance 标 self_authored_with_check 且注明待 T2 实测回填

退出码 0 = 全绿；非 0 = 有失败（CI 门禁拦截）。
"""
from __future__ import annotations

import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA = os.path.dirname(_HERE)
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_pdk.packaging_tolerance import (  # noqa: E402
    coupling_efficiency, lateral_tolerance_um, package_yield,
    design_to_packaging_yield, verify_packaging_anchor,
    package_yield_with_pitch, FIBER_MFD_UM, DEFAULT_SIGMA_ALIGN_UM,
)


def _chk(name: str, cond: bool, detail: str = "") -> bool:
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))
    return cond


def main() -> int:
    print("=== 可封装性链烟雾测试（self_authored_with_check · 假设分布待 T2 回填）===")
    ok = True

    # ① 单调性反向：σ_align 越大良率越低
    y_tight = package_yield(mfd_um=4.0, sigma_align_um=0.3)
    y_loose = package_yield(mfd_um=4.0, sigma_align_um=1.0)
    ok &= _chk("σ_align↑ → 封装良率↓", y_loose < y_tight,
               f"{y_loose:.4f} < {y_tight:.4f}")

    # ② 设计旋钮反馈：MFD 越大 → 横向容差越大 → 封装良率越高（单调、确定）
    d_small = design_to_packaging_yield(2.0)
    d_big = design_to_packaging_yield(8.0)
    ok &= _chk("MFD↑ → 横向容差↑",
               d_big["lateral_tolerance_um"] > d_small["lateral_tolerance_um"],
               f"{d_small['lateral_tolerance_um']:.3f} → {d_big['lateral_tolerance_um']:.3f}")
    ok &= _chk("MFD↑ → 封装良率↑", d_big["packaging_yield"] > d_small["packaging_yield"],
               f"{d_small['packaging_yield']:.4f} → {d_big['packaging_yield']:.4f}")

    # ③ 可复现性：固定种子 → 同输入同输出
    v1 = verify_packaging_anchor(seed=2026, mfd_um=4.0)
    v2 = verify_packaging_anchor(seed=2026, mfd_um=4.0)
    ok &= _chk("固定种子可复现（MC diff 一致）",
               abs(v1["monte_carlo"] - v2["monte_carlo"]) < 1e-12,
               f"{v1['monte_carlo']:.8f} == {v2['monte_carlo']:.8f}")

    # ④ 自证互证：解析 == 蒙特卡洛
    ok &= _chk("解析 Rayleigh 闭式 == 蒙特卡洛（Δ≤1e-2）", v1["ok"],
               f"analytic={v1['analytic']:.5f} mc={v1['monte_carlo']:.5f} Δ={v1['diff']:.5f}")

    # ⑤ 耦合效率随横向偏移单调下降
    eta0 = coupling_efficiency(0.0, 0.0, 0.0, mfd_um=4.0)
    eta_dx = coupling_efficiency(1.0, 0.0, 0.0, mfd_um=4.0)
    eta_dx2 = coupling_efficiency(2.0, 0.0, 0.0, mfd_um=4.0)
    ok &= _chk("η 随横向偏移单调下降", eta0 > eta_dx > eta_dx2,
               f"{eta0:.4f} > {eta_dx:.4f} > {eta_dx2:.4f}")

    # ⑤b 耦合效率随角向偏移下降
    eta_th = coupling_efficiency(0.0, 0.0, 1.0, mfd_um=4.0)
    ok &= _chk("η 随角向偏移下降", eta0 > eta_th, f"{eta0:.4f} > {eta_th:.4f}")

    # ⑥ P-CPO 间距合规：pitch 低于几何下界 → 不假绿
    bad = package_yield_with_pitch(4.0, pitch_um=1.0)        # 1µm << ITU MFD 下界
    good = package_yield_with_pitch(4.0, pitch_um=250.0)      # 250µm 合规
    ok &= _chk("pitch<几何下界 → pitch_compliant=False（不假绿）",
               bad["pitch_compliant"] is False, f"pitch={bad['pitch_um']}µm floor={bad['pitch_floor_um']}µm")
    ok &= _chk("pitch≥几何下界 → pitch_compliant=True", good["pitch_compliant"] is True)

    # ⑦ provenance 诚实标注
    ok &= _chk("provenance = self_authored_with_check", good["provenance"] == "self_authored_with_check")
    ok &= _chk("注明待 T2 实测回填", "T2" in good["note"] and "假设" in good["note"])

    # 默认入参应与公开标准一致
    ok &= _chk("默认 MFD 回退 ITU-T G.652 10.3µm", abs(FIBER_MFD_UM - 10.3) < 1e-9)
    ok &= _chk("默认 σ_align 假设值 > 0", DEFAULT_SIGMA_ALIGN_UM > 0)

    print()
    if ok:
        print("ALL PASS")
        return 0
    print("SOME FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
