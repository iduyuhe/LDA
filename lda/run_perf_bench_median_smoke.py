"""D-77 补充 · 计时基线「中位数化」门禁。

验证 run_perf_bench 的基线不再写「单次运行样本」，而是 N 次运行取中位数：

  (1) 纯聚合 `_aggregate_baseline` 非空转：偏斜样本下 median ≠ 首项
      （证明确实在做统计聚合，而非把 run#1 原样回写 ⇒ 防假绿）；
  (2) 退化样本（全相同）median == 该值、runs == N（正确性下限）；
  (3) 基线 schema 存活：⑬ 判定所需的 greens/spectrum/greens.speedup 键仍在线；
  (4) 集成 `_write_baseline`：monkeypatch bench_* 喂入脚本化时序序列，
      写临时文件 ⇒ 落盘值 == 序列中位数，且 `_quantile.samples` 与喂入一致
      （证明「首跑 + N-1 次补充」拼成的样本池完整、未丢样本）。

全部纯函数 + monkeypatch，不依赖 numba / 真实 FDTD，瞬时可跑。
LLM 不进判决路径。
"""
from __future__ import annotations

import json
import os
import tempfile

import numpy as np
import run_perf_bench as m

_CASES = []


def check(name, ok, detail=""):
    _CASES.append((name, bool(ok), detail))
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name}" + (f" — {detail}" if detail else ""))


# (1) 纯聚合：偏斜样本 ⇒ median 与首项不同（反向探针·证非空转）
def test_aggregate_skewed():
    g_np = [2.0, 2.2, 2.1, 2.3, 2.0]
    g_nb = [0.40, 0.30, 0.35, 0.30, 0.40]
    g_sp = [5.0, 7.0, 6.0, 8.0, 5.0]          # 首项 5.0 是偶发低值（被 numba 偶发加速）
    s_ov = [3.0, 3.5, 3.2, 3.6, 3.1]
    bl = m._aggregate_baseline(g_np, g_nb, g_sp, s_ov, len(g_sp))
    # 期望中位数（手算与 numpy 双核对）
    exp_sp = round(float(np.median(g_sp)), 3)   # 6.0
    exp_np = round(float(np.median(g_np)), 3)   # 2.1
    exp_nb = round(float(np.median(g_nb)), 3)   # 0.35
    exp_ov = round(float(np.median(s_ov)), 3)   # 3.2
    ok = (bl["greens"]["speedup"] == exp_sp
          and bl["greens"]["numpy_s"] == exp_np
          and bl["greens"]["numba_s"] == exp_nb
          and bl["spectrum"]["overall_speedup"] == exp_ov)
    check("聚合: 偏斜样本 median == numpy 中位数（且 != 首项 5.0）",
          ok, f"speedup={bl['greens']['speedup']} (首项 5.0) "
              f"numpy_s={bl['greens']['numpy_s']} numba_s={bl['greens']['numba_s']} "
              f"spectrum={bl['spectrum']['overall_speedup']}")
    # 关键反向：median 必须 ≠ 首项，否则「中位数化」是空转
    check("聚合: median 与 run#1 首项不同（证非空转·防假绿）",
          bl["greens"]["speedup"] != g_sp[0],
          f"median={bl['greens']['speedup']} vs first={g_sp[0]}")


# (2) 退化：全相同 ⇒ median == 该值、runs == N
def test_aggregate_degenerate():
    g_np = [1.5] * 5
    g_nb = [0.3] * 5
    g_sp = [10.0] * 5
    s_ov = [4.0] * 5
    bl = m._aggregate_baseline(g_np, g_nb, g_sp, s_ov, 5)
    ok = (bl["greens"]["speedup"] == 10.0
          and bl["greens"]["numpy_s"] == 1.5
          and bl["greens"]["numba_s"] == 0.3
          and bl["spectrum"]["overall_speedup"] == 4.0
          and bl["_quantile"]["runs"] == 5
          and bl["_quantile"]["method"] == "median")
    check("聚合: 全相同样本 median==该值 ∧ runs==5", ok,
          f"speedup={bl['greens']['speedup']} runs={bl['_quantile']['runs']}")


# (3) schema 存活（供 ⑬ 判定）
def test_schema_survives():
    g_np = [2.0, 2.2, 2.1, 2.3, 2.0]
    g_nb = [0.40, 0.30, 0.35, 0.30, 0.40]
    g_sp = [5.0, 7.0, 6.0, 8.0, 5.0]
    s_ov = [3.0, 3.5, 3.2, 3.6, 3.1]
    bl = m._aggregate_baseline(g_np, g_nb, g_sp, s_ov, 5)
    ok_pb = (isinstance(bl, dict) and "greens" in bl and "spectrum" in bl
             and isinstance(bl["greens"], dict)
             and "speedup" in bl["greens"])
    check("基线 schema 存活（⑬: greens/spectrum/greens.speedup 在线）", ok_pb,
          "keys=%s" % sorted(bl)[:8])


# (4) 集成：monkeypatch bench_* ⇒ 写临时文件 == 中位数 ∧ 样本池完整
def test_write_integration():
    g_list = [
        {"numpy_s": 2.0, "numba_s": 0.40, "speedup": 5.0, "rel_diff": 1e-3, "ok": True},
        {"numpy_s": 2.2, "numba_s": 0.30, "speedup": 7.0, "rel_diff": 1e-3, "ok": True},
        {"numpy_s": 2.1, "numba_s": 0.35, "speedup": 6.0, "rel_diff": 1e-3, "ok": True},
        {"numpy_s": 2.3, "numba_s": 0.30, "speedup": 8.0, "rel_diff": 1e-3, "ok": True},
        {"numpy_s": 2.0, "numba_s": 0.40, "speedup": 5.0, "rel_diff": 1e-3, "ok": True},
    ]
    s_list = [
        {"overall_speedup": 3.0, "ok": True},
        {"overall_speedup": 3.5, "ok": True},
        {"overall_speedup": 3.2, "ok": True},
        {"overall_speedup": 3.6, "ok": True},
        {"overall_speedup": 3.1, "ok": True},
    ]
    gi = iter(g_list[1:])   # 首跑已贡献 run#1，迭代器只放 run#2..#5
    si = iter(s_list[1:])
    orig_g, orig_s = m.bench_greens, m.bench_spectrum
    m.bench_greens = lambda: next(gi)
    m.bench_spectrum = lambda quick=False: next(si)
    try:
        first_run = {"benchmarks": {"greens": g_list[0], "spectrum": s_list[0]}}
        fd, tmp = tempfile.mkstemp(suffix=".json", prefix="perf_baseline_probe_")
        os.close(fd)
        m._write_baseline(first_run, quick=False, n_runs=5, path=tmp)
        on_disk = json.load(open(tmp, encoding="utf-8"))
    finally:
        m.bench_greens, m.bench_spectrum = orig_g, orig_s
        if os.path.exists(tmp):
            os.remove(tmp)
    exp_sp = round(float(np.median([g["speedup"] for g in g_list])), 3)   # 6.0
    exp_np = round(float(np.median([g["numpy_s"] for g in g_list])), 3)   # 2.1
    exp_nb = round(float(np.median([g["numba_s"] for g in g_list])), 3)   # 0.35
    exp_ov = round(float(np.median([s["overall_speedup"] for s in s_list])), 3)  # 3.2
    ok = (on_disk["greens"]["speedup"] == exp_sp
          and on_disk["greens"]["numpy_s"] == exp_np
          and on_disk["greens"]["numba_s"] == exp_nb
          and on_disk["spectrum"]["overall_speedup"] == exp_ov
          and on_disk["_quantile"]["runs"] == 5
          and on_disk["_quantile"]["greens_speedup_samples"] == [5.0, 7.0, 6.0, 8.0, 5.0])
    check("集成: 落盘基线 == 5 次序列中位数 ∧ 样本池完整(5 项)", ok,
          f"on_disk speedup={on_disk['greens']['speedup']} "
          f"samples={on_disk['_quantile']['greens_speedup_samples']}")
    # 反向：若只回写 run#1 会得 5.0，落盘是 6.0 ⇒ 证明确实聚合了补充运行
    check("集成: 落盘值(6.0) ≠ run#1(5.0)（证补充运行被纳入）",
          on_disk["greens"]["speedup"] != 5.0,
          f"on_disk={on_disk['greens']['speedup']} first=5.0")


def main() -> int:
    test_aggregate_skewed()
    test_aggregate_degenerate()
    test_schema_survives()
    test_write_integration()
    fails = [c for c in _CASES if not c[1]]
    print(f"\nRESULT: {'ALL_OK' if not fails else 'FAIL'} "
          f"({len(_CASES) - len(fails)}/{len(_CASES)} passed)")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
