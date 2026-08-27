"""最小可跑示例：生成一个示例版图并演示主权几何 DRC + 寄生估算。

运行：
    python examples/sample_layout.py out.gds
    lda check --gds out.gds        # 主权几何 DRC 快查

兼容两种运行环境：
  - 已 pip install lda-design（顶层 import lda）
  - 源码树直接跑（把 ./lda 加入 sys.path）
"""
import os
import sys

try:
    from lda.lda_l2 import gds_export
except ImportError:  # 源码树直接运行
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lda"))
    from lda_l2 import gds_export


def build_sample_gds(path: str) -> None:
    """生成一个含「有源硅器件 + 金属走线」的示例版图。

    - RING：layer 1（有源硅），一个 4µm×4µm 方块
    - WG  ：layer 11（金属），0.5µm 宽、总长 15µm 的走线
    """
    gds = gds_export.gds_library(
        "SAMPLE",
        {
            "RING": [gds_export.boundary(1, [(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)])],
            "WG": [gds_export.path(11, 0.5, [(0, 10), (10, 10), (10, 15)])],
        },
    )
    with open(path, "wb") as f:
        f.write(gds)
    print(f"wrote {path}  (RING@layer1 + WG@layer11, 0.5um wide)")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "sample_layout.gds"
    build_sample_gds(out)
