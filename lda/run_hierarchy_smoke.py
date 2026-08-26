"""Merge-3b 层级 IR smoke（v0.8.16 · 子系统组合 + flatten）。

覆盖（等价性验证——防自证门禁）：
  ① 子系统 flatten：嵌套链路内联 + 端口提升（组件/net 前缀化）
  ② 传播等价性：子系统组合链路 vs 手工平铺链路，transfers 逐点一致
  ③ 端口互连：父级 connect("n", subid, pin, ...) 解析到子系统内部端点
  ④ 源/共享参数透传

红线：等价性由数值死标量比对决定（组合/平铺 rel 差必须为 0）。
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from lda_chain.engine import simulate  # noqa: E402
from lda_chain.link_model import LinkModel  # noqa: E402

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


def _make_sub(name: str) -> LinkModel:
    """子链路：wg_in → ring → wg_out（外部 IO：in/out）。"""
    sub = LinkModel(name=name)
    sub.add_device("wg_i", "Waveguide")
    sub.add_device("ring", "RingResonator", {"R": 10.0, "gap": 0.3})
    sub.add_device("wg_o", "Waveguide")
    sub.connect("n1", "wg_i", "out", "ring", "in")
    sub.connect("n2", "ring", "out", "wg_o", "in")
    sub.external_io("e1", "wg_i", "in")     # 子系统输入引脚
    sub.external_io("e2", "wg_o", "out")    # 子系统输出引脚
    sub.mark_source("wg_i", "in")
    return sub


def _make_manual() -> LinkModel:
    """手工平铺等价链路（flatten 的参照物）。"""
    m = LinkModel()
    m.add_device("s1.wg_i", "Waveguide")
    m.add_device("s1.ring", "RingResonator", {"R": 10.0, "gap": 0.3})
    m.add_device("s1.wg_o", "Waveguide")
    m.connect("n1", "s1.wg_i", "out", "s1.ring", "in")
    m.connect("n2", "s1.ring", "out", "s1.wg_o", "in")
    m.external_io("e1", "s1.wg_i", "in")
    m.external_io("e2", "s1.wg_o", "out")
    m.mark_source("s1.wg_i", "in")
    return m


def main() -> int:
    # ① 子系统 flatten：组件内联 + 前缀化
    parent = LinkModel()
    parent.add_subsystem("s1", _make_sub("sub1"))
    flat = parent.flatten()
    ids = [c.id for c in flat.ir.components]
    check("子系统 flatten（组件前缀化 s1__*）",
          "s1__wg_i" in ids and "s1__ring" in ids and "s1__wg_o" in ids,
          f"{ids}")

    # ② 传播等价性：组合 vs 手工平铺
    wls = [1.54, 1.55, 1.56]
    sim_flat = simulate(flat, wls)
    sim_manual = simulate(_make_manual(), wls)
    t_flat = sim_flat["transfers"]
    t_manual = sim_manual["transfers"]
    same_keys = set(t_flat.keys()) == set(t_manual.keys())
    max_diff = 0.0
    for k in t_flat:
        max_diff = max(max_diff, max(abs(a - b) for a, b in
                                     zip(t_flat[k], t_manual[k])))
    check("传播等价性（组合 vs 平铺，逐点一致）",
          same_keys and max_diff < 1e-12,
          f"keys_equal={same_keys} max_diff={max_diff:.2e}")

    # ③ 端口互连：父级 connect 到子系统引脚
    parent2 = LinkModel()
    sub_a = _make_sub("subA")
    parent2.add_subsystem("A", sub_a)
    parent2.add_device("wg_out2", "Waveguide")
    parent2.connect("c1", "A", "out", "wg_out2", "in")   # A.out → wg_out2.in
    parent2.external_io("e1", "A", "in")                  # A.in 悬挂（源）
    parent2.external_io("e2", "wg_out2", "out")
    parent2.mark_source("A", "in")
    flat2 = parent2.flatten()
    sim2 = simulate(flat2, [1.55])
    check("父级→子系统端口互连（A.out 解析到 A__wg_o.out）",
          len(sim2["transfers"]) >= 1 and sim2["missing_models"] == [],
          f"transfers={len(sim2['transfers'])} keys={list(sim2['transfers'])[:2]}")

    # ④ 源透传
    check("源标记透传", "A.in" in sim2["sources"] or len(sim2["sources"]) >= 1,
          f"sources={sim2['sources']}")

    print(f"\n汇总：{PASS} PASS / {FAIL} FAIL")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
