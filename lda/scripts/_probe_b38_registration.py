"""Probe: B469-B472 登记链路在闭式解释器（无 scipy）下是否加载干净 + 三分类计数是否符合预期。

不检查文档（文档同步在 Task #49），只验证：
  1. BENCHMARK_DEFS 含 B469-B472
  2. B469/B470/B471 含 "candidate" 键 ⇒ strict_independent；**B472 无 candidate 键 ⇒ 自证桩**（诚实降级）
  3. total = len(DEFS)，strict = 含 candidate 键数
  4. 预期 total=490、strict=468、deg=3、stub=19（v0.9.208 的 486/465/3/18 净增 3 严格锚 + 1 自证桩）
  5. import 不触发 scipy（闭式门禁安全）
"""
import sys
import importlib

# 确认 scipy 未导入
def _scipy_loaded():
    return "scipy" in sys.modules

ok = True
try:
    from lda_harness.benchmark_defs import BENCHMARK_DEFS
    from lda_harness.benchmarks import BENCHMARK_ORDER
except Exception as exc:
    print("IMPORT_FAIL", repr(exc))
    sys.exit(2)

print("scipy_loaded_after_defs_import =", _scipy_loaded())

need = {"B469", "B470", "B471", "B472"}
present = need.issubset(set(BENCHMARK_DEFS.keys()))
print("B469-B472 in DEFS =", present)
for bid in sorted(need):
    d = BENCHMARK_DEFS.get(bid, {})
    cand = d.get("candidate")
    print(f"  {bid}: candidate={cand!r} strict={'YES' if cand else 'NO'}")

total = len(BENCHMARK_DEFS)
# 与 run_p0_count_guard_sync_smoke._derive_true_tiers 同源判序（degraded 优先）
strict = deg = stub = 0
for _d in BENCHMARK_DEFS.values():
    if _d.get("candidate_status") == "degraded_ordinal":
        deg += 1
    elif "candidate" in _d:
        strict += 1
    else:
        stub += 1
print(f"total={total} strict={strict} degraded={deg} stub={stub}")
print("order_len=", len(BENCHMARK_ORDER), "order_has_all=", need.issubset(set(BENCHMARK_ORDER)))
print("three_class_sum_check (strict+deg+stub==total):", strict + deg + stub == total)

exp_total, exp_strict, exp_deg, exp_stub = 490, 468, 3, 19
if not present:
    ok = False; print("FAIL: B469-B472 未全部登记")
if total != exp_total:
    ok = False; print(f"FAIL: total={total} 期望 {exp_total}")
if strict != exp_strict:
    ok = False; print(f"FAIL: strict={strict} 期望 {exp_strict}")
if deg != exp_deg:
    ok = False; print(f"FAIL: degraded={deg} 期望 {exp_deg}")
if stub != exp_stub:
    ok = False; print(f"FAIL: stub={stub} 期望 {exp_stub}")

print("PROBE_RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
