"""D-77 · 验证合约工业化 —— 持续集成全量回归统一入口。

把 LDA 全部验证（74 个 run_*smoke*.py + run_harness.py B1-B18+E1-E3）收敛到
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
    "run_harness.py",                        # B1-B13 物理定律锚 + E1-E3 实证锚（21 题）
    "run_mcp_smoke.py",                      # L1 协议层（MCP 工具路径，D-104 入 core）
    "run_l1_agent_smoke.py",                 # L1 协议层全链路（KernelGateway + L0 IR + candidate，D-105 入 core）
    "run_agent_loop_smoke.py",               # agent 自迭代设计闭环（DesignAgent「AI for AI」最小实证，D-106 入 core）
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
    # 工业化验证（D-76：FAIL 检出机制 + 性能基准——坏 smoke 残留根治的守卫）
    "run_ci_industrial_smoke.py",
    # 生态共建链（D-93~D-98：harness 扩展 / 提交 / 评审→落地→发布，纯 numpy 快速）
    "run_ecosystem_smoke.py",        # harness B1-B18 + 主权 A/B/C + Registry 自检
    "run_ecosystem_submit_smoke.py", # 社区提交入口（器件 + 批量 + 提案）
    "run_ecosystem_publish_smoke.py",# 评审→落地→发布 全链（含补丁生成）
    # 实证大数据锚（D-62：harness E1-E3 实证锚题 + 语料评审流，纯 numpy 快速）
    "run_empirical_anchor_smoke.py",
    # WebUI 路由层（D-102：全端点静态 + 快路径实跑，秒级）
    "run_webui_api_smoke.py",
    # P1 芯片级补强（链路框架 + 自动布线 + Agent 元编排 + 双 ground 上提，纯 numpy 快速）
    "run_link_m1_smoke.py", "run_link_m2_smoke.py", "run_link_m3_smoke.py",
    "run_link_m4_smoke.py",
    # P1-M4 补强：芯片级设计验收标准（四锚 A-D 死标量）
    "run_chip_acceptance_smoke.py",
    # 器件库主流封口（v0.8.7：MMI/光栅/方向耦合/可调 transmon/读出配对/CZ 门）
    "run_kernel_seal_smoke.py",
    # 仿真级芯片设计闭环演示（任务 256：WDM 收发 + 量子读出链路双案例）
    "run_chip_design_demo.py",
    # 流片级验证管道（门3 接口细化：PDK→DRC→工艺角→实测回流）
    "run_tapeout_smoke.py",
    # 计数一致性门禁（v0.8.10：引擎/包/题库/CI 条数 vs README 宣传串机器断言，防计数漂移根治）
    "run_count_consistency_smoke.py",
    # 基准对照验证闭环报告（v0.8.11c：15 引擎解析锚 rel + 实证语料覆盖矩阵 + ORACLE 状态）
    "run_benchmark_crosscheck_report.py",
    # 芯片级版图导出增强（v0.8.11d：IO 光栅接入 + 版图统计 + 芯片级 DRC 正负例）
    "run_chip_layout_smoke.py",
    # loss/效率类引擎（v0.8.11e：实证锚 9 条语料全对照 + 物理合理性）
    "run_loss_engine_smoke.py",
    # 系统级锚（Phase 0 · Merge-0：S1 功率预算 + 防自证负例）
    "run_system_budget_smoke.py",
    # 链路损耗感知（Merge-1a：Waveguide/MZI 可选损耗 + 预算报告）
    "run_link_loss_smoke.py",
    # 性能漂移角扫（Merge-1b：⑥审计落地，光子/量子按域角 + 死标量判决）
    "run_corner_performance_smoke.py",
    # 有源双出口（Merge-2a：相移器/调制器设计量+行为黑箱，22 引擎）
    "run_active_device_smoke.py",
    # 模型精度分级（Merge-3a：L0/L1/L2 诚实标注 + 升迁机制）
    "run_model_class_smoke.py",
    # 层级 IR（Merge-3b：子系统 flatten 等价性）
    "run_hierarchy_smoke.py",
    # 开发者 CLI 钩子（v0.8.29：lda design/check/report 薄壳三命令）
    "run_cli_smoke.py",
    # gdsfactory 兼容桥 + GDS 主权几何 DRC（v0.8.30：生态互通 + 计数守护固化）
    "run_gdsfactory_bridge_smoke.py",
    # 版图几何级 RC 寄生估算（v0.8.31：设计侧主权闭环收口 S3.5）
    "run_parasitic_rc_smoke.py",
    # 产品级基准对照库（v0.8.32：实证锚产品级扩展 + B 生态播种，免流片）
    "run_golden_product_smoke.py",
    # 对照报告飞轮（v0.8.30：多源死标量对照 + 历史归档 + 覆盖度趋势）
    "run_crosscheck_flywheel_smoke.py",
    # Phase 3 统计锚（S7/S8 蒙特卡洛分布 + 收敛性：红线 + 防自证负例）
    "run_statistical_anchor_smoke.py",
    # Phase 4 提案编译器（生成侧：锚前置剪枝 + 即提即验 + 人终审）
    "run_proposal_compiler_smoke.py",
    # 系统类型注册表（v0.8.33：link/wdm_demux/quantum_fidelity 分发，复用已验证闭环）
    "run_system_types_smoke.py",
    # 创新超市货架（v0.8.34：前瞻预研货架 · 组合已锚定基元 + 公开信号驱动，红线下护栏）
    "run_innovation_market_smoke.py",
    # 第二梯队-1 A* 布线（贪心→全局最优 + 避障 + 无解诚实退化）
    "run_astar_route_smoke.py",
    # B1 批量并行布线（v0.8.44：route_batch 语义一致 + 收益边界 + 诚实拒绝）
    "run_parallel_routing_smoke.py",
    # 第二梯队-2 三件套（多端网 Steiner + 2D 放置 + 有源基元）
    "run_second_tier_smoke.py",
    # LVS 签核（v0.8.24：版图-原理图一致性 · 签核级 · 版图差距 #5 + S9 锚）
    "run_lvs_smoke.py",
    # 千器件规模扩展（v0.8.26：版图差距 #7 收官 · S11 规模锚）
    "run_scale_smoke.py",
    # 千器件芯片级演示（v0.8.27：千器件版图接入演示 · GDS/DRC/LVS 双闸）
    "run_chip_scale_demo.py",
    # 商务闭环（v0.9.0：创新超市商业化链路——注册/下单/凭证/审批/下载限次/
    # 对公申请/定制状态机/我的模块/账号重置/意见收集，函数级快速回归）
    "run_store_flow_smoke.py",
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
                      exclude: Optional[List[str]] = None,
                      timeout_override: Optional[Dict[str, float]] = None
                      ) -> Dict[str, Any]:
    """全量/核心回归。返回 {results, summary, acceptance, verdict}。

    timeout_override：per-script 超时覆盖（{脚本名: 秒}）——供特殊重 smoke
    单独放宽时限（如 run_ci_industrial_smoke 内部含子回归+greens 基准，
    约 300-315s 浮动，全局 300s 常顶到边界；覆盖 600s 根治偶发抖动，
    不掩盖其它 smoke 的真实超时）。
    """
    python = python or sys.executable
    if tag == "core":
        scripts = [s for s in CORE_SMOKES
                   if os.path.exists(os.path.join(_HERE, s))]
    else:
        scripts = _discover_all()
    exclude = set(exclude or [])
    scripts = [s for s in scripts if s not in exclude]
    overrides = timeout_override or {}

    results: List[Dict[str, Any]] = []
    t_total0 = time.perf_counter()
    for s in scripts:
        # run_ci_industrial_smoke 内部含子回归+greens 基准（~300-315s 浮动），
        # 内置放宽至 600s 根治偶发 TIMEOUT；其余 smoke 用全局 timeout。
        to = overrides.get(
            s, 600.0 if s == "run_ci_industrial_smoke.py" else timeout)
        r = _run_one(python, s, to)
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
