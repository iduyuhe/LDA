"""PS-M3 烟雾测试：运行 selfcheck_ps_m3 并把标准报告落盘到 outputs/ps_m3。

光子传感器新征程（PS-M3）· 灵敏度物理链对齐（B460）+ 真实波导几何 LOD 实测 常驻门禁。
复用 PS-M2 `lod_real` 噪声模型单一真源；B460（Hellmann-Feynman 灵敏度闭式 vs 有限差分）
由账本守卫独立覆盖，本 smoke 负责「真实几何 LOD + 灵敏度对齐 + 反向探针」常驻。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lda_l2.ps_m3 import main  # noqa: E402

if __name__ == "__main__":
    _out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "ps_m3")
    raise SystemExit(main(out_dir=_out))
