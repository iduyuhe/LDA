"""v0.8.29 开发者 CLI 钩子 smoke（门禁守护：三命令可用 + 设计闭环 + 版图双闸）。

验证 lda_design/cli.py 的薄壳三命令：
  ① lda design <kind> --target  → 设计闭环跑通、最优候选可输出
  ② lda check <spec.json>       → 版图导出 + DRC/LVS 双闸 ACCEPT（示例链路）
  ③ lda report --quick          → 基准对照报告生成（跨源死标量对照）

红线：CLI 不引入新判决逻辑，仅复用 design_engine / chip_layout_export /
run_benchmark_crosscheck_report 的真实计算结果（LLM 不进路径）。
全部纯 numpy 快速，入 CI core 安全集。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

PY = os.environ.get(
    "LDA_PY",
    r"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe",
)
CLI = os.path.join(_HERE, "lda_design", "cli.py")

CHECKS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('| ' + detail) if detail else ''}")


def _run(*cli_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PY, CLI, *cli_args],
        capture_output=True, text=True, cwd=_HERE,
        timeout=120,
    )


def main() -> int:
    # ① lda design
    r = _run("design", "RingResonator", "--target", "9.0", "--top-k", "3")
    ok_design = r.returncode == 0 and "最优候选" in r.stdout and "err=" in r.stdout
    check("lda design：设计闭环跑通 + 最优候选输出",
          ok_design, r.stdout.replace("\n", " ")[:120] if ok_design else r.stderr[:120])

    # ② lda check（示例 spec）
    spec = {
        "domain": "photon", "name": "cli_smoke_link",
        "devices": [
            {"id": "wg1", "kind": "Waveguide", "params": {}},
            {"id": "ring", "kind": "RingResonator", "params": {"R": 10.0, "gap": 0.3}},
            {"id": "wg2", "kind": "Waveguide", "params": {}},
        ],
        "nets": [
            {"net": "n1", "from": ["wg1", "out"], "to": ["ring", "in"]},
            {"net": "n2", "from": ["ring", "out"], "to": ["wg2", "in"]},
        ],
        "io": [
            {"net": "e1", "device": "wg1", "port": "in"},
            {"net": "e2", "device": "wg2", "port": "out"},
        ],
        "sources": [{"device": "wg1", "port": "in"}],
    }
    tmp = os.path.join(tempfile.gettempdir(), "lda_cli_check_spec.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(spec, f)
    out_dir = os.path.join(_HERE, "reports", "cli_smoke")
    r = _run("check", tmp, "--out", out_dir)
    ok_check = r.returncode == 0 and "LVS：**ACCEPT**" in r.stdout and "GDS 已导出" in r.stdout
    check("lda check：版图导出 + DRC/LVS 双闸 ACCEPT + GDS 落盘",
          ok_check, r.stdout.replace("\n", " ")[:120] if ok_check else r.stderr[:120])

    # ③ lda report（quick）
    r = _run("report", "--out", out_dir, "--quick")
    ok_report = r.returncode == 0 and "基准对照验证闭环报告" in r.stdout
    check("lda report：基准对照报告生成（跨源死标量对照）",
          ok_report, r.stdout.replace("\n", " ")[:120] if ok_report else r.stderr[:120])

    # ④ lda check --gds（主权几何 DRC 快查，自造 GDS 测试回路）
    gds_path = os.path.join(_HERE, "reports", "cli_smoke_test.gds")
    _run("check", tmp, "--out", out_dir)  # 先产出一份 LDA 自身 GDS
    # 直接用 cmd_check 内部无法拿路径，这里再生成一份最小 GDS 用于 --gds 回路
    import subprocess as _sp
    gen = _sp.run([PY, "-c",
                   "import sys;sys.path.insert(0,'.');"
                   "from lda_l2 import gds_export;"
                   "b=gds_export.gds_library('T',{'C':[gds_export.path(1,0.5,[(0,0),(20,0)]),"
                   "gds_export.boundary(1,[(0,0),(5,0),(5,5),(0,5),(0,0)])]});"
                   "open(r'" + gds_path.replace("\\", "/") + "','wb').write(b)"],
                  capture_output=True, text=True, cwd=_HERE)
    r = _run("check", "--gds", gds_path, "--out", out_dir)
    ok_gds = r.returncode == 0 and "主权校验" in r.stdout and "几何 DRC 快查" in r.stdout
    check("lda check --gds：导入 GDSII 主权几何 DRC 快查（回路）",
          ok_gds, r.stdout.replace("\n", " ")[:120] if ok_gds else r.stderr[:120])

    # ⑤ lda gf（gdsfactory 未装时优雅降级，不阻断）
    r = _run("gf", tmp, "--out", out_dir)
    ok_gf = r.returncode == 0 and ("gdsfactory 未安装" in r.stdout or "LDA ⇄ gdsfactory" in r.stdout)
    check("lda gf：gdsfactory 兼容桥（未装优雅降级 / 已装转 spec）",
          ok_gf, r.stdout.replace("\n", " ")[:120] if ok_gf else r.stderr[:120])

    npass = sum(1 for c in CHECKS if c[1])
    print("-" * 60)
    print(f"CLI 钩子 smoke：{npass}/{len(CHECKS)} PASS")
    return 0 if npass == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
