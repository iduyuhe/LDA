"""PS-M5 烟雾测试：运行 selfcheck_ps_m5 并把标准报告落盘到 outputs/ps_m5。

光子传感器新征程（PS-M5）· 微流控 / Lab-on-chip 多物理场 常驻门禁。
复用 PS-M5 内核（B-36 批 · B463 矩形 Hagen-Poiseuille 级数 vs 红黑 SOR FD /
B464 Lucas-Washburn 闭式 vs 后向欧拉 / B465 圆柱径向热阻 Fourier 闭式 vs 1D FD）；
覆盖三道多物理场核心对齐、物理量纲合理、缩放律、反向红标，18 项判据含反向探针。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lda_l2.ps_m5 import main  # noqa: E402

if __name__ == "__main__":
    _out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "ps_m5")
    raise SystemExit(main(out_dir=_out))
