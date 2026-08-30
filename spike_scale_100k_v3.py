"""LVS O(n) 治理后 · 规模 scaling 实测（v0.8.44 线段网格）。

复用 S11 全链路（构建+放置+多层布线+LVS），跑 4k→256k，记录：
  - 各规模 total / build / lvs 耗时 + verdict（consistent 必须 ACCEPT）
  - 翻倍斜率（near-linear 应 ~2-4×；治理前 ~6× O(n^1.65)）
  - 128k cProfile 热点，确认 _collect_cross_shorts 主导且近线性
纯 stdlib；判决语义零变化（由 verify_lvs_cross_equiv.py 铁证）。
"""
import cProfile
import pstats
import sys
import time

sys.path.insert(0, "D:/agent_LDA/lda")
sys.path.insert(0, "D:/agent_LDA/lda/lda_harness")
import scale_anchor as SA

SCALES = [4000, 8000, 16000, 32000, 64000, 128000, 256000]


def _profile_128k():
    """128k cProfile：确认热点在 _collect_cross_shorts 且近线性。"""
    pr = cProfile.Profile()
    pr.enable()
    rep = SA.run_scale_pipeline(128000, case="consistent")
    pr.disable()
    st = pstats.Stats(pr)
    print(f"\n=== 128k cProfile（verdict={rep['verdict']} "
          f"lvs={rep['time_lvs_s']}s total={rep['time_total_s']}s）===")
    rows = []
    for func, val in st.stats.items():
        fname = func[0]
        if "lda_l2/lvs.py" in fname or "lda_layout" in fname:
            # (cc, nc, tt, ct, callers)
            cc, nc, tt, ct = val[0], val[1], val[2], val[3]
            rows.append((ct, fname, cc, nc))
    rows.sort(reverse=True)
    for ct, fname, cc, nc in rows[:12]:
        print(f"  {ct*1000:9.2f}ms  {cc:7d}x  {fname}")


def main():
    print(f"{'N':>8} {'build_s':>9} {'lvs_s':>9} {'total_s':>9} "
          f"{'verdict':>8} {'x/2x_total':>11}")
    prev = None
    for n in SCALES:
        t0 = time.perf_counter()
        rep = SA.run_scale_pipeline(n, case="consistent")
        _ = time.perf_counter()
        if rep["verdict"] != "ACCEPT":
            print(f"  !! {n}: verdict={rep['verdict']} "
                  f"viol={rep.get('n_violations')} — 语义回归！")
        x = "" if prev is None else f"{rep['time_total_s']/prev:6.2f}x"
        print(f"{n:>8} {rep['time_build_s']:>9.3f} {rep['time_lvs_s']:>9.3f} "
              f"{rep['time_total_s']:>9.3f} {rep['verdict']:>8} {x:>11}")
        prev = rep["time_total_s"]
    _profile_128k()
    print("\nDONE")


if __name__ == "__main__":
    sys.exit(main())
