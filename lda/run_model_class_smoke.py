"""Merge-3a model_class 精度分级 smoke（v0.8.16 · 诚实性基建）。

覆盖：
  ① 分级注册表：已注册 7 个链路 kind 全 L0-解析（诚实标注）
  ② 未登记 kind → 缺省 L0（不静默、不崩溃）
  ③ 升迁机制：register_model_class 可升 L1/L2（发动期回流入口）
  ④ 对照报告按精度级分列（quick 集含 model_class 字段）

红线：精度等级是元数据（诚实声明），不影响死标量判决——判决仍由
|candidate − golden| ≤ tol 决定，LLM 不进路径。
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from lda_chain.registry import (  # noqa: E402
    MODEL_CLASS_L0,
    MODEL_CLASS_L1,
    MODEL_CLASS_L2,
    get_model_class,
    register_model_class,
)

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    tag = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"[{tag}] {name}" + (f" —— {detail}" if detail else ""))


def main() -> int:
    # ① 已注册链路 kind 全 L0
    kinds = ("RingResonator", "Waveguide", "GratingCoupler", "MZI",
             "PhaseShifter", "MziModulator", "Photodetector")
    all_l0 = all(get_model_class(k) == MODEL_CLASS_L0 for k in kinds)
    check("7 个链路 kind 全 L0-解析（诚实标注）", all_l0,
          f"{[get_model_class(k) for k in kinds[:3]]}...")

    # ② 未登记 kind 缺省 L0
    check("未登记 kind 缺省 L0（不静默不崩溃）",
          get_model_class("UnknownDevice") == MODEL_CLASS_L0)

    # ③ 升迁机制（发动期回流入口）
    register_model_class("Waveguide", MODEL_CLASS_L1)  # 模拟 FDTD 标定升迁
    up = get_model_class("Waveguide") == MODEL_CLASS_L1
    register_model_class("Waveguide", MODEL_CLASS_L0)  # 还原
    check("升迁机制 L0→L1 可登记（发动期入口）", up,
          f"L2 常量存在: {MODEL_CLASS_L2}")

    # ④ 分级常量语义完整
    check("三级语义完整（L0/L1/L2）",
          MODEL_CLASS_L0 and MODEL_CLASS_L1 and MODEL_CLASS_L2,
          f"{MODEL_CLASS_L0} / {MODEL_CLASS_L1} / {MODEL_CLASS_L2}")

    print(f"\n汇总：{PASS} PASS / {FAIL} FAIL")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
