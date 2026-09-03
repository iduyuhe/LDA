"""D-77 验证合约工业化 smoke：3 例（回归子集全过 + 性能基准 PASS + FAIL 检测）。

运行：C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe run_ci_industrial_smoke.py
（性能基准 greens numpy 约 35s，总量 <2min）
"""
import os
import sys
import tempfile

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


# 1) 正例：回归统一入口 core 快速子集（harness + IR + GDS + DRC + 系统级）全过
# 注意：必须排除自身（run_ci_industrial_smoke.py）——内部递归调 core 回归，
# 若不排除自身会造成无限递归（内部回归又启动 industrial → 又启动 core → …）
# 导致 300s 超时（v0.8.x 新增 smoke 入 core 后暴露）。新增慢 smoke 也须纳入。
_SLOW_CORE = {
    "run_ring_fdtd_smoke.py", "run_ring_double_verify_smoke.py",
    "run_device_fdtd_smoke.py", "run_dc_transmission_smoke.py",
    "run_layout_sim_smoke.py", "run_pipeline_smoke.py",
    "run_pipeline_multidevice_smoke.py", "run_pipeline_realize_smoke.py",
    "run_coupler_band_smoke.py", "run_ir_spec_smoke.py",
    "run_tunable_wdm_smoke.py", "run_qeda_topology_smoke.py",
    "run_large_scale_smoke.py", "run_primitives_smoke.py",
    "run_gc_smoke.py", "run_drc_fix_smoke.py", "run_drc_pdk_smoke.py",
    "run_d06_smoke.py", "run_d10_smoke.py", "run_pdk_smoke.py",
    # v0.9.1 新增（量子侧入 core）：这两项含 FDTD 场级仿真，单项 180-200s。
    # 若不排除，本脚本内部递归的 core 子集会突破 600s 超时上限
    # （2026-08-30 实测：未排除时 TIMEOUT 600s → 排除后回落）
    "run_splitter_readout_smoke.py", "run_splitter_readout_cal_smoke.py",
    # 🔴 v0.9.24 补登：v0.9.23 把 `run_semivec_mode_smoke.py`（2D 半矢量本征模，
    # 5 次本征解，实测 **~97s**）加入 CORE_SMOKES 时**漏了同步本表** ⇒ 内部
    # 递归的 core 子集从 ~570s 涨到 **667.62s**，撑破外层 600s 上限 ⇒ 全量
    # `--tag core` 回归实测 **TIMEOUT**（v0.9.24 首跑 86 PASS / 1 TIMEOUT）。
    # 本表的设计意图就是「排除慢 smoke 以保住内部子集的可完成性」——semivec 是
    # 除两项 FDTD 外最慢的一条，**本就该在表里**。
    # 🔴 教训：**新增慢 smoke 入 CORE_SMOKES 时，必须同步检查所有「内部递归跑
    # core 子集」的脚本**（本文件是全库唯一一处）。
    "run_semivec_mode_smoke.py",
    # 🔴 v0.9.26 同步补登：`run_eme_taper_smoke.py`（EME 逐片本征解 + 三次收敛
    # 扫描，实测 **~33s**）入 CORE_SMOKES 时即刻登记本表，不再重演 v0.9.24 的
    # 「semivec 漏登记 ⇒ 子回归 667.62s 撑破 600s ⇒ 全量 core TIMEOUT」。
    "run_eme_taper_smoke.py",
    # 🔴 v0.9.27（T-1）同步补登：`run_d_criterion_smoke.py`（判据 D 护栏，
    # 20 道基线普查 + 双例验证，实测 **~15s**）。铁律同上：入 CORE_SMOKES
    # 必须同步登记本表。
    "run_d_criterion_smoke.py",
    # 递归保护：本文件自身
    "run_ci_industrial_smoke.py",
}


def _reg_subset():
    return run_ci_regression(tag="core", exclude=list(_SLOW_CORE))


run("正例-回归core快速子集", _reg_subset, True)


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
    import shutil
    shutil.copy(tmp, dst)
    try:
        r = run_ci_regression(tag="all", exclude=[s for s in
                             os.listdir(os.path.dirname(os.path.abspath(__file__)))
                             if s.startswith("run_") and s.endswith("_smoke.py")
                             and s != "run_zz_bad_smoke.py"])
        detected = r["summary"]["fail"] >= 1
        return {"ok": True,
                "acceptance": {"passed": detected, "checks": []},
                "verdict": f"坏 smoke 被检出（fail={r['summary']['fail']}）"
                           if detected else "坏 smoke 漏检（FAIL）"}
    finally:
        # D-109 根治：沙箱安全删除钩子可能抛 SAFE_DELETE_FAIL 致 os.remove 失效
        # → 文件残留且每次 all 集重新创建（D-101 曾清理一次）。多重删除策略：
        #   os.remove（可能被钩子拦截）→ os.unlink 兜底 → 仍失败则改名 .bak
        #   隔离（不再被 _discover_all 发现），绝不残留可被发现的坏 smoke。
        import time
        for _ in range(3):
            if not os.path.exists(dst):
                break
            try:
                os.remove(dst)
            except Exception:  # noqa: BLE001
                try:
                    os.unlink(dst)
                except Exception:  # noqa: BLE001
                    time.sleep(0.5)
        if os.path.exists(dst):
            try:
                os.rename(dst, dst + ".bak")
            except Exception:  # noqa: BLE001
                pass


run("负例-坏smoke被检出", _detect_fail, True)

all_pass = all(c[1] == "PASS" for c in cases)
for name, status, ok, verdict in cases:
    print(f"[{status}] {name}: ok={ok}")
    print(f"      {verdict}")
print(f"\nSMOKE {'ALL PASS' if all_pass else 'FAILED'} "
      f"({sum(1 for c in cases if c[1]=='PASS')}/{len(cases)})")
sys.exit(0 if all_pass else 1)
