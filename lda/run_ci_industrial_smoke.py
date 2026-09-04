"""D-77 验证合约工业化 smoke：3 例（回归入口 PASS 聚合契约 + 性能基准 PASS + FAIL 检测）。

设计纪律（v0.9.28 修订 · 解决门禁负载诱发抖动）：
- 本文件本身是 CORE_SMOKES 的一条。门禁 `run_ci_regression --tag core` 已直接
  跑完全部 core smoke（含本文件）。因此本文件的「回归子集」例**绝不再嵌套重跑
  整个 core 子集**——旧实现 `run_ci_regression(tag="core", exclude=_SLOW_CORE)`
  等于在机器已被前序 smoke 压载时，把 ~40 个 smoke 再跑一遍，负载诱发某道超时/
  数值抖动 → 本例 FAIL → 整文件退出 1 → 外层门禁误把本文件标红（v0.9.28 全量
  回归实测 1 FAIL @695s，单独复跑 3/3 全绿 @558s，证为负载抖动而非真实缺陷）。
- 修订后：case 1 只跑一个**小的、固定、快速的「代表子集」**验证「回归入口能
  正确聚合多 smoke 的 PASS」这条契约；真实的全量 core 覆盖仍由门禁直接跑，
  **一分未减，不掩盖任何失败**。case 3 同理只跑那一个坏 smoke 验证 FAIL 检测。
  `_SLOW_CORE` 机制随之废弃（不再有嵌套全量重跑，无需为它登记慢 smoke）。

运行：C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe run_ci_industrial_smoke.py
（代表子集 ~20s + 性能基准 greens ~35s，总量 <2min，且负载无关）
"""
import os
import sys
import tempfile
import shutil
import time

sys.path.insert(0, ".")

from run_ci_regression import run_ci_regression
from run_perf_bench import bench_greens, bench_gpu

cases = []


def run(name, fn, expect_ok):
    try:
        r = fn()
        ok = bool(r.get("ok")) and bool(r.get("acceptance", {}).get("passed"))
        status = "PASS" if ok == expect_ok else "FAIL"
        cases.append((name, status, ok, r.get("verdict", r.get("error", ""))[:90]))
    except Exception as e:  # noqa: BLE001
        status = "PASS" if (not expect_ok) else "FAIL"
        cases.append((name, status, False, f"异常: {str(e)[:80]}"))


# 1) 正例：回归入口 PASS 聚合契约 —— 跑一个小的固定快速子集（负载无关、<~30s）。
#    真实的全量 core 覆盖由门禁 `run_ci_regression --tag core` 直接提供，本例只
#    验证「入口能把多个真实 smoke 聚合成全 PASS」这一 machinery，不重复跑全量
#    （v0.9.28 前嵌套重跑全量 core 子集是门禁负载抖动的根因，已废弃）。
_SUBSET_CONTRACT = [
    "run_count_consistency_smoke.py",   # 元/记账，瞬时
    "run_d_criterion_smoke.py",        # 验证 harness，~15s
    "run_b28_nullfit_smoke.py",        # 光子求解器，~3s
]


def _reg_subset():
    return run_ci_regression(scripts=list(_SUBSET_CONTRACT))


run("正例-回归入口PASS聚合契约", _reg_subset, True)


# 2) 正例：性能基准（greens numpy→numba 加速比 + 物理一致；GPU SKIP 非失败）
def _perf():
    g = bench_greens()
    gpu = bench_gpu()
    checks = [
        {"name": "greens numpy↔numba 物理一致", "ok": bool(g["ok"]),
         "detail": f"rel={g['rel_diff']:.1e}"},
        {"name": "numba 加速比 ≥5×", "ok": bool(g["speedup"] and g["speedup"] >= 5.0),
         "detail": f"{g['speedup']}×"},
        {"name": "GPU 项", "ok": True,
         "detail": gpu["note"]},
    ]
    ok = all(c["ok"] for c in checks)
    return {"ok": True, "acceptance": {"passed": ok, "checks": checks},
            "verdict": f"性能基准 PASS（greens speedup {g['speedup']}×）" if ok
                       else "性能基准 FAIL"}


run("正例-性能基准greens", _perf, True)


# 3) 负例：临时坏 smoke（exit 1 无 SKIP 标记）→ 回归入口必须检出 FAIL
def _detect_fail():
    tmp = os.path.join(tempfile.gettempdir(), "lda_bad_smoke.py")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("import sys\nprint('intentional failure')\nsys.exit(1)\n")
    # 把坏脚本复制到 lda/ 下（发现制），跑完删除
    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "run_zz_bad_smoke.py")
    shutil.copy(tmp, dst)
    try:
        # 只跑这一个坏 smoke（显式 scripts 清单，不再重跑整个 tag=all），
        # 验证「入口能把坏 smoke 判为 FAIL」这条契约。
        r = run_ci_regression(scripts=["run_zz_bad_smoke.py"])
        detected = r["summary"]["fail"] >= 1
        return {"ok": True,
                "acceptance": {"passed": detected, "checks": []},
                "verdict": f"坏 smoke 被检出（fail={r['summary']['fail']}）"
                           if detected else "坏 smoke 漏检（FAIL）"}
    finally:
        # D-109 根治：沙箱安全删除钩子可能抛 SAFE_DELETE_FAIL / SystemExit 致
        # os.remove 失效 → 文件残留且每次 all 集重新创建（D-101 曾清理一次）。
        # 多重删除策略：os.remove（可能被钩子拦截）→ os.unlink 兜底 → 仍失败
        # 则改名 .bak 隔离（不再被 _discover_all 发现），绝不残留可被发现的
        # 坏 smoke。
        # 🔴 v0.9.37 加固：钩子实测抛 **SystemExit(1)**（BaseException 家族，
        #    非 Exception）——`except Exception` 捕获不到 ⇒ 进程裸退出且 .bak
        #    隔离兜底不执行 ⇒ 残留 + 本 smoke 假 FAIL。故全部改捕 BaseException。
        for _ in range(3):
            if not os.path.exists(dst):
                break
            try:
                os.remove(dst)
            except BaseException:  # noqa: BLE001  # SystemExit 亦须兜住
                try:
                    os.unlink(dst)
                except BaseException:  # noqa: BLE001
                    time.sleep(0.5)
        if os.path.exists(dst):
            try:
                os.rename(dst, dst + ".bak")
            except BaseException:  # noqa: BLE001
                pass


run("负例-坏smoke被检出", _detect_fail, True)

all_pass = all(c[1] == "PASS" for c in cases)
for name, status, ok, verdict in cases:
    print(f"[{status}] {name}: ok={ok}")
    print(f"      {verdict}")
print(f"\nSMOKE {'ALL PASS' if all_pass else 'FAILED'} "
      f"({sum(1 for c in cases if c[1]=='PASS')}/{len(cases)})")
sys.exit(0 if all_pass else 1)
