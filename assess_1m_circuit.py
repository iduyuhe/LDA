"""百万级器件规模评估 · 电路仿真层（DFS 路径枚举的规模行为）。

两种拓扑对照：
  C1 链/总线（CPO 真实形态）— 路径数 O(N)，测每器件开销
  C2 菱形级联（MZI mesh / crossbar 形态）— 路径数 2^k，暴露指数爆炸
"""
from __future__ import annotations

import sys
import time

sys.path.insert(0, "D:/agent_LDA/lda")

from lda_chain.link_model import LinkModel  # noqa: E402
from lda_chain.engine import simulate  # noqa: E402

WL = [1.27354, 1.27789, 1.28226, 1.28666, 1.29110,
      1.29550, 1.29992, 1.30442]   # LAN-WDM 8 波（µm），对齐 CPO 250k 报告


def hdr(t: str) -> None:
    print(f"\n{'='*72}\n{t}\n{'='*72}", flush=True)


def build_chain(n: int) -> LinkModel:
    """链式/总线拓扑：wg_i.out -> wg_{i+1}.in（CPO 形态，路径数 O(1)）。"""
    link = LinkModel(name=f"chain_{n}")
    for i in range(n):
        link.add_device(f"wg{i}", "Waveguide", {"length": 20.0})
    for i in range(n - 1):
        link.connect(f"net_{i}", f"wg{i}", "out", f"wg{i+1}", "in")
    return link


def build_diamond(k: int) -> LinkModel:
    """菱形级联：每级 2 个并联器件，级间全连 → 路径数 2^k。

    对应 MZI mesh / crossbar / 冗余光路等真实拓扑形态。
    """
    link = LinkModel(name=f"diamond_{k}")
    for i in range(k):
        link.add_device(f"a{i}", "Waveguide", {"length": 20.0})
        link.add_device(f"b{i}", "Waveguide", {"length": 20.0})
    # 级间：上一级 {a,b} 的 out 与下一级 {a,b} 的 in 用同一个 net 全连
    for i in range(k - 1):
        link.connect(f"nxt_{i}",
                     f"a{i}", "out", f"b{i}", "out",
                     f"a{i+1}", "in", f"b{i+1}", "in")
    return link


def part_c1():
    hdr("C1 · 链式/总线拓扑（CPO 真实形态，路径数 O(1)）")
    print(f"{'N_dev':>8} {'t_sim_s':>10} {'x/2x':>7} {'us/dev':>9}", flush=True)
    prev = None
    for n in (500, 1000, 2000, 4000, 8000, 16000):
        link = build_chain(n)
        t0 = time.perf_counter()
        try:
            out = simulate(link, WL, sources=[("wg0", "in")])
            dt = time.perf_counter() - t0
        except RecursionError as e:
            print(f"{n:>8} {'RecursionError':>10}  ← 递归深度上限击穿", flush=True)
            break
        x = "" if prev is None else f"{dt/prev:6.2f}x"
        print(f"{n:>8} {dt:>10.3f} {x:>7} {dt/n*1e6:>9.2f}", flush=True)
        prev = dt
        del link, out


def part_c2():
    hdr("C2 · 菱形级联（MZI mesh 形态，路径数 2^k —— 指数爆炸探测）")
    print(f"{'k级':>6} {'n_dev':>7} {'paths=2^k':>12} {'t_sim_s':>10} "
          f"{'note':>16}", flush=True)
    for k in (8, 10, 12, 14, 16, 18, 20):
        link = build_diamond(k)
        t0 = time.perf_counter()
        try:
            simulate(link, WL, sources=[("a0", "in"), ("b0", "in")])
            dt = time.perf_counter() - t0
            note = ""
            flag = False
        except RecursionError:
            dt = time.perf_counter() - t0
            note = "RecursionError"
            flag = True
        print(f"{k:>6} {2*k:>7} {2**k:>12} {dt:>10.3f} {note:>16}", flush=True)
        if dt > 60 or flag:
            print("  → 已超可用阈值，停止外推", flush=True)
            break
        del link


def part_c3():
    """C3：CPO 真实形态 —— 1M 器件的电路仿真外推基线（不实跑，用 C1 斜率）。"""
    hdr("C3 · 1M 器件仿真外推（由 C1 实测斜率线性外推，非实测）")
    # 占位：由 C1 数据人工合成，脚本只打印提示
    print("  见 C1 斜率；1M = C1(16k) × 62.5", flush=True)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "c1"):
        part_c1()
    if which in ("all", "c2"):
        part_c2()
    print("\nDONE", flush=True)
