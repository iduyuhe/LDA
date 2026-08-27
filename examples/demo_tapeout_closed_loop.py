"""主权闭环演示：设计 → 版图 → 主权 DRC/LVS/工艺角/几何寄生（阶段 B 分享用）。

演示「设计侧主权闭环」：从版图几何出发，跑完 tapeout 管道五段
（PDK→DRC→工艺角→LVS→几何寄生），全部主权零外部依赖。

运行：
    python examples/demo_tapeout_closed_loop.py

诚实边界：几何 DRC / 寄生为**主权子集**（非 foundry 工艺级全量）；
真实 PDK/晶圆实测/封装属发动期。
"""
import os
import sys
import json

try:
    from lda.lda_l2 import gds_export
    from lda.lda_pdk import tapeout_pipeline as tp
except ImportError:  # 源码树直接运行
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lda"))
    from lda_l2 import gds_export
    from lda_pdk import tapeout_pipeline as tp


def main() -> None:
    # 1) 构造一个含「有源硅器件 + 金属走线」的版图（主权几何）
    gds = gds_export.gds_library(
        "DEMO",
        {
            "DEVICE": [gds_export.boundary(1, [(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)])],
            "METAL": [gds_export.path(11, 0.5, [(0, 10), (10, 10), (10, 15)])],
        },
    )

    # 2) 跑设计侧主权闭环管道（提供 GDS → S3.5 几何寄生实跑）
    res = tp.run_tapeout_pipeline(
        {"RingAddDrop": {"R": 10.0, "gap": 0.3}}, gds=gds
    )

    # 3) 打印关键结果（死标量，LLM 不进判决）
    print("=== LDA 设计侧主权闭环演示 ===")
    print(f"DRC 通过        : {res.drc_passed}")
    print(f"工艺角全过      : {res.corners_all_pass}")
    print(f"LVS 判决        : {res.lvs_result.get('verdict') if res.lvs_result else 'SKIP(无版图网表)'}")
    p = res.parasitic_result
    print(f"几何寄生 R/C    : {p.total_r_ohm:.2f} Ω / {p.total_c_ff:.2f} fF (passed={p.passed})")
    print(f"签核 accepted   : {res.accepted}")
    print(f"诚实边界        : {res.honest_note[:60]}...")

    # 4) 导出 JSON 报告（不入库，演示产物）
    out = "demo_tapeout_report.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(tp.tapeout_to_dict(res), f, ensure_ascii=False, indent=2)
    print(f"报告已写        : {out}")


if __name__ == "__main__":
    main()
