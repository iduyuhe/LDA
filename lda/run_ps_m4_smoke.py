"""PS-M4 烟雾测试：运行 selfcheck_ps_m4 并把标准报告落盘到 outputs/ps_m4。

光子传感器新征程（PS-M4）· 生物/化学功能化与表面传感 常驻门禁。
复用 PS-M3 平板求解器 + B-35 内核（B461 表面灵敏度 HF 闭式 vs 三层 TMM-FD、
B462 朗缪尔闭式 vs RK4）；覆盖 adlayer 场 L² 分数 Γ_adlayer、倏逝穿透深度 1/γ、
体/表灵敏度比、谐振波长位移 Δλ=λ·Δn_eff/n_g、Langmuir 平衡 θ + 动力学 θ(t)、
de Feijter 表面质量标定，14 项判据含反向探针。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lda_l2.ps_m4 import main  # noqa: E402

if __name__ == "__main__":
    _out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "ps_m4")
    raise SystemExit(main(out_dir=_out))
