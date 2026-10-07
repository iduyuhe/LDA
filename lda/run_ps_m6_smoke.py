"""PS-M6 烟雾测试：运行 selfcheck_ps_m6 并把标准报告落盘到 outputs/ps_m6。

光子传感器新征程（PS-M6）· 规模与集成（阵列 + 读出 + 封装/对准）常驻门禁。
复用 B-37 内核（B466 密集阵列热串扰阻尼扩散闭式 × 1D FD 三对角 /
B467 TIA 读出噪声底 kT/C 频域闭式 × 时域冲激响应数值积分 /
B468 对准耦合效率高斯重叠闭式 × 采样-插值重叠积分）；
覆盖三锚对齐（tol 读自 BENCHMARK_DEFS）、阵列 pitch/密度、读出噪声底 R 无关性 + 带宽、
对准 1 dB 容差律、集成插损/帧率/面积一致性，28 项判据含反向探针。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lda_l2.ps_m6 import main  # noqa: E402

if __name__ == "__main__":
    _out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "ps_m6")
    raise SystemExit(main(out_dir=_out))
