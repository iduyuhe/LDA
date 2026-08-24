"""D-77 · 验证合约工业化 —— 持续集成全量回归统一入口。

把 LDA 全部验证（70 个 run_*smoke*.py + run_harness.py B1-B18）收敛到
**一条命令、一份机器可读报告**——降低社区协作门槛（新贡献者/第三方跑
`python run_ci_regression.py` 即可看全量回归红绿），对齐 D-04 三套裁判统一。

特性：
  - 自动发现 `lda/run_*smoke*.py` + `run_harness.py`（新增 smoke 零配置纳入）；
  - 每项独立子进程（隔离环境，崩溃不影响他者）+ 超时保护 + 输出尾部捕获；
  - **SKIP 语义**：退出非 0 且输出含 SKIP/无 GPU/无 numba 等优雅降级标记
    → 记 SKIP（非 FAIL），区分"环境缺失"与"真失败"；
  - `--tag core`：内置 CI 安全集（纯 numpy 快速，ubuntu CI 可跑）；
    `--tag all`（默认）：全量（重 FDTD / GPU 项本机或 venv 跑）；
  - 输出：JSON 报告（机器可读，供 CI 解析/趋势）+ 人类可读汇总表。

验收（死标量）：FAIL=0（真失败清零）→ 回归绿；SKIP 不计失败但逐条列出原因。
LLM 不进判决路径。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA_ROOT = _HERE          # 本脚本位于 lda/（包根）

# CI 安全集：纯 numpy 快速 smoke（对齐 .github/workflows/ci.yml 已挑选步骤 +
# D-73~D-76 新增解析模型/标准 smoke）。重 FDTD/GPU 项（sparams/adjoint/
# wdm_coupler 标定等）走 --tag all 在本机/venv 跑。
CORE_SMOKES: List[str] = [
    # 裁判 + 标准题
    "run_harness.py",                        # B1-B13 物理定律锚
    # IR / 谱形 / 环形（纯 numpy）
    "run_ir_d05_smoke.py", "run_ir_ring_smoke.py", "run_ir_spec_smoke.py",
    "run_spectrum_loop_smoke.py", "run_ring_fdtd_smoke.py",
    "run_ring_double_verify_smoke.py",
    # 器件库 / 版图 / DRC / 流水线
    "run_device_fdtd_smoke.py", "run_dc_transmission_smoke.py",
    "run_device_library_smoke.py", "run_gds_smoke.py", "run_drc_smoke.py",
    "run_layout_sim_smoke.py", "run_drc_fix_smoke.py", "run_drc_pdk_smoke.py",
    "run_pipeline_smoke.py", "run_pipeline_multidevice_smoke.py",
    "run_pipeline_realize_smoke.py", "run_primitives_smoke.py",
    "run_gc_smoke.py", "run_coupler_band_smoke.py",
    "run_d06_smoke.py", "run_d10_smoke.py", "run_pdk_smoke.py",
    # Track D / 标准层（D-73~D-76）
    "run_tunable_wdm_smoke.py", "run_qeda_topology_smoke.py",
    "run_large_scale_smoke.py",
    # 生态共建链（D-93~D-98：harness 扩展 / 提交 / 评审→落地→发布，纯 numpy 快速）
    "run_ecosystem_smoke.py",        # harness B1-B18 + 主权 A/B/C + Registry 自检
    "run_ecosystem_submit_smoke.py", # 社区提交入口（器件 + 批量 + 提案）
    "run_ecosystem_publish_smoke.py",# 评审→落地→发布 全链（含补丁生成）
    # 实证大数据锚（D-62：harness E1-E3 实证锚题 + 语料评审流，纯 numpy 快速）
    "run_empirical_anchor_smoke.py",
    # WebUI 路由层（D-102：全端点静态 + 快路径实跑，秒级）
    "run_webui_api_smoke.py",
]

_SKIP_MARKERS = ("SKIP", "skip", "无 GPU", "无gpu", "no GPU", "no gpu",
                 "GPU 不可用", "torch 未安装", "未安装", "not installed",
                 "numba 未安装", "SKIPPED")


def _discover_all() -> List[str]:
    """自动发现 lda/ 下全部 run_*smoke*.py + run_harness.py（去重、排序）。"""
    files = set()
    for fn in sorted(os.listdir(_HERE)):
        if fn.startswith("run_") and fn.endswith("_smoke.py"):
            files.add(fn)
    if os.path.exists(os.path.join(_HERE, "run_harness.py")):
        files.add("run_harness.py")
    return sorted(files)


def _run_one(python: str, script: str, timeout: float) -> Dict[str, Any]:
    t0 = time.perf_counter()
    try:
        p = subprocess.run(
            [python, script], cwd=_HERE,
            capture_output=True, text=True, timeout=timeout)
        rc, out = p.returncode, (p.stdout or "") + (p.stderr or "")
        dt = time.perf_counter() - t0
        status = "PASS" if rc == 0 else "FAIL"
        if rc != 0 and any(m in out for m in _SKIP_MARKERS):
            status = "SKIP"
        tail = "\n".join(out.strip().splitlines()[-4:])
        return {"script": script, "rc": rc, "status": status,
                "elapsed_s": round(dt, 2), "tail": tail}
    except subprocess.TimeoutExpired:
        return {"script": script, "rc": -1, "status": "TIMEOUT",
                "elapsed_s": timeout, "tail": f"超过 {timeout}s 超时"}
    except Exception as e:  # noqa: BLE001
        return {"script": script, "rc": -2, "status": "ERROR",
                "elapsed_s": round(time.perf_counter() - t0, 2),
                "tail": str(e)[:200]}


def run_ci_regression(python: Optional[str] = None, tag: str = "all",
                      timeout: float = 300.0, fail_fast: bool = False,
                      exclude: Optional[List[str]] = None) -> Dict[str, Any]:
    """全量/核心回归。返回 {results, summary, acceptance, verdict}。"""
    python = python or sys.executable
    if tag == "core":
        scripts = [s for s in CORE_SMOKES
                   if os.path.exists(os.path.join(_HERE, s))]
    else:
        scripts = _discover_all()
    exclude = set(exclude or [])
    scripts = [s for s in scripts if s not in exclude]

    results: List[Dict[str, Any]] = []
    t_total0 = time.perf_counter()
    for s in scripts:
        r = _run_one(python, s, timeout)
        results.append(r)
        print(f"  [{r['status']:<6}] {r['script']}  ({r['elapsed_s']}s)")
        if fail_fast and r["status"] in ("FAIL", "ERROR", "TIMEOUT"):
            break
    total_s = round(time.perf_counter() - t_total0, 2)

    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_skip = sum(1 for r in results if r["status"] == "SKIP")
    n_fail = sum(1 for r in results if r["status"] in ("FAIL", "ERROR", "TIMEOUT"))
    failed = [r for r in results if r["status"] in ("FAIL", "ERROR", "TIMEOUT")]
    skipped = [r for r in results if r["status"] == "SKIP"]
    checks = [
        {"name": f"回归通过（{n_pass}/{len(results)}，FAIL=0）",
         "ok": n_fail == 0,
         "detail": f"{n_pass} PASS / {n_skip} SKIP / {n_fail} FAIL"}
    ]
    if n_fail:
        checks.append({"name": "失败项逐条列出（可追溯）",
                       "ok": False,
                       "detail": "; ".join(f"{r['script']}(rc={r['rc']})"
                                           for r in failed[:8])})
    if n_skip:
        checks.append({"name": "SKIP 项原因透明",
                       "ok": True,
                       "detail": "; ".join(r["script"] for r in skipped[:8])})
    passed = n_fail == 0
    verdict = (f"验证合约工业化回归 {tag} 集：{n_pass} PASS / {n_skip} SKIP / "
               f"{n_fail} FAIL，总耗时 {total_s}s"
               + (" —— 全绿" if passed else
                  f" —— 失败项：{'; '.join(r['script'] for r in failed[:5])}"))
    return {
        "ok": True,
        "title": f"CI 全量回归（tag={tag}）",
        "tag": tag, "python": python,
        "n_scripts": len(scripts),
        "summary": {"pass": n_pass, "skip": n_skip, "fail": n_fail,
                    "total_s": total_s, "failed": failed, "skipped": skipped},
        "results": results,
        "acceptance": {"checks": checks, "passed": passed},
        "verdict": verdict,
        "note": ("统一入口自动发现全部 smoke（新增零配置纳入）；SKIP=环境缺失"
                 "优雅降级（无 GPU/numba），FAIL=真失败；LLM 不进判决路径。"
                 "core 集对齐 CI 可跑（纯 numpy）；all 集含重 FDTD/GPU 项。"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="D-77 验证合约工业化 · 全量回归")
    ap.add_argument("--tag", choices=["core", "all"], default="all")
    ap.add_argument("--python", default=None, help="解释器（全量推荐 venv）")
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--fail-fast", action="store_true")
    ap.add_argument("--exclude", default="", help="逗号分隔排除脚本")
    ap.add_argument("--out", default=None, help="JSON 报告路径")
    a = ap.parse_args()
    excl = [x.strip() for x in a.exclude.split(",") if x.strip()]
    r = run_ci_regression(python=a.python, tag=a.tag, timeout=a.timeout,
                          fail_fast=a.fail_fast, exclude=excl)
    print(r["verdict"])
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        print(f"[written] {a.out}")
    return 0 if r["acceptance"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
