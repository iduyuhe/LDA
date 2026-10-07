"""PS-M2 烟雾测试：运行 selfcheck_ps_m2 并把标准报告落盘到 outputs/ps_m2/。

光子传感器新征程（PS-M2）指标框架 + LOD_real 噪声模型（几何无关）常驻门禁：
LOD_real = √(LOD_elec² + LOD_temp²)（LOD_temp 与灵敏度 S 解耦，是 PS-M2 的头号
物理结论）；四情景（v0_baseline / cited / degraded / bench_referenced）现算 + 口径
自洽 + 反向探针。纯 stdlib，实测 <5s，入 CI core 集（run_ci_regression.py）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_l2.ps_m2 import main  # noqa: E402

if __name__ == "__main__":
    _out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "ps_m2")
    raise SystemExit(main(out_dir=_out))
