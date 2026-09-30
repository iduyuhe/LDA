"""LDA · GPU/CUDA 预置隔离 venv 可用性自检（v0.9.145 · P1 GPU wheel 预置）。

背景（审计 R7 缺口）
-------------------
`torch` 仅为 pyproject 的 **optional extra**（`[torch]`）；本机/开发者机可预置一个
**隔离** CUDA venv（`lda_cuda_venv/`，已在 `.gitignore` 排除 ⇒ 不污染用户/仓库环境、
不进任何 git 追踪）。该 venv 预装 `torch` CUDA wheel（如 `2.11.0+cu128`），供
`lda/lda_solver/fdtd3d_torch.py` 在 GPU 上大规模并行 FDTD（自动选 cuda/cpu）。

本门禁是**软 / Advisory**护栏，登记「预置预期 + 可用性自检」两件事：

  ① 预期（EXPECT，机器可判）：预置 venv 应含 ``torch>=2.0`` 且为 **CUDA build**
     （``torch.version.cuda`` 非空）。
  ② 可用性自检：
       · 若 ``lda_cuda_venv/Scripts/python.exe`` 不存在 ⇒ **SKIP**（advisory）：
         CI 沙箱因 R7 缺口无法下载 CUDA wheel、属合法缺席；GPU 后端自动回退
         numpy/cpu，不影响任何正确性门禁。
       · 若 venv 存在 ⇒ 实跑其 python 校验 torch 可 import、为 CUDA build、版本
         达标；健康 ⇒ PASS；损坏（导入失败 / 非 CUDA build / 版本过低）⇒ FAIL
         （抓出「预置了却坏掉」的真问题，区别于「没预置」）。

硬依赖纪律（与 ``run_optional_import_guard_smoke`` 互补）：本门禁**绝不** import
torch、绝不安装任何东西，只探测已存在的 venv，故不污染用户环境、不会在缺 torch
的 CI 上裸崩。

反向测试（铁律：护栏必须会响）
------------------------------
  [R1] 把 venv 探测路径指到不存在的目录 ⇒ 必须走 SKIP 分支（非 PASS 也非 FAIL）。
  [R2] 版本解析器喂「非 CUDA build / 版本过低 / 导入失败」坏样本 ⇒ 必须判
       unhealthy（FAIL 路径）；喂健康样本 ⇒ 必须判 healthy（PASS 路径）。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

PASS = 0
FAIL = 0
SKIP = 0

ROOT = Path(__file__).resolve().parent.parent            # D:\agent_LDA
VENV_DIR = ROOT / "lda_cuda_venv"
VENV_PY = VENV_DIR / "Scripts" / "python.exe"            # Windows；gitignored

# 预置预期（登记，机器可判）。改这里即改"什么叫预置好了"。
EXPECT = {
    "venv_dir": "lda_cuda_venv",
    "torch_min": "2.0",
    "cuda_build_required": True,       # 必须是 CUDA build（torch.version.cuda 非空）
    "index_url": "https://download.pytorch.org/whl/cu128",
}

# 🔴 check 单一定义在 lda_harness/smoke_kit（v0.9.113 · 波次 2 · F-07）。
from lda_harness.smoke_kit import make_check  # noqa: E402
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="  ", detail_fmt='  ({d})')


def soft_skip(name: str, detail: str = "") -> None:
    """SKIP 一行（advisory：不计入 FAIL，rc 不受影响）。"""
    global SKIP
    SKIP += 1
    print("  [SKIP] " + name + (f"  ({detail})" if detail else ""))


_PROBE = (
    "import sys, torch\n"
    "print('TORCH', torch.__version__)\n"
    "print('CUDA_BUILD', torch.version.cuda or '')\n"
    "print('CUDA_AVAIL', torch.cuda.is_available())\n"
)


def discover_venv_py() -> Path | None:
    """返回 venv 的 python 路径；不存在则返回 None。"""
    return VENV_PY if VENV_PY.is_file() else None


def decide(venv_py: Path | None) -> str:
    """返回 'skip'（venv 不存在，advisory）或 'probe'（venv 存在，需校验）。"""
    if venv_py is None or not Path(venv_py).is_file():
        return "skip"
    return "probe"


def run_torch_probe(venv_py: Path) -> tuple[int, str]:
    """在 venv 内实跑 torch 探针，返回 (退出码, 合并输出)。超时/异常 ⇒ rc=-1。"""
    try:
        proc = subprocess.run(
            [str(venv_py), "-c", _PROBE],
            capture_output=True, text=True, timeout=60,
        )
    except Exception as exc:  # noqa: BLE001
        return -1, f"spawn-failed: {exc}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def parse_probe(rc: int, out: str) -> dict:
    """解析探针输出 ⇒ {healthy, version, cuda_build, cuda_avail, reason}。

    判定顺序（任一步不满足 ⇒ unhealthy + reason）：
      · rc == 0 且能解析出 TORCH 行；
      · CUDA build 非空（torch.version.cuda）；
      · 主版本 >= 2（EXPECT["torch_min"]）。
    CUDA_AVAIL 仅作信息项，不计入 healthy（硬件缺失不致命，build 正确即可）。
    """
    res = {"healthy": False, "version": None, "cuda_build": None,
           "cuda_avail": None, "reason": ""}
    if rc != 0:
        res["reason"] = f"probe rc={rc}"
        return res
    for line in out.splitlines():
        if line.startswith("TORCH "):
            res["version"] = line.split(" ", 1)[1].strip()
        elif line.startswith("CUDA_BUILD "):
            cb = line.split(" ", 1)[1].strip()
            res["cuda_build"] = cb or None
        elif line.startswith("CUDA_AVAIL "):
            res["cuda_avail"] = (line.split(" ", 1)[1].strip() == "True")
    if res["version"] is None:
        res["reason"] = "no TORCH line (torch import failed?)"
        return res
    if not res["cuda_build"]:
        res["reason"] = "not a CUDA build (torch.version.cuda empty)"
        return res
    try:
        major = int(res["version"].split("+")[0].split(".")[0])
    except Exception:
        res["reason"] = f"unparseable version {res['version']!r}"
        return res
    if major < int(EXPECT["torch_min"].split(".")[0]):
        res["reason"] = f"torch {res['version']} < {EXPECT['torch_min']}"
        return res
    res["healthy"] = True
    return res


def main() -> int:
    print("=" * 70)
    print(">> LDA GPU/CUDA 预置隔离 venv 可用性自检（软 / Advisory）")
    print("=" * 70)
    print(f"   venv = {VENV_DIR}  (gitignore 排除，不污染用户/仓库环境)")

    # ---- R2：解析器双向标定（先证明解析器本身会响） ----
    print("\n[R2] 探针解析器双向标定")
    bad_nocuda = parse_probe(0, "TORCH 2.11.0+cpu\nCUDA_BUILD \nCUDA_AVAIL False\n")
    check("R2-a 非 CUDA build 必须判 unhealthy", not bad_nocuda["healthy"], bad_nocuda["reason"])
    bad_rc = parse_probe(1, "ImportError: No module named torch\n")
    check("R2-b 导入失败(rc!=0) 必须判 unhealthy", not bad_rc["healthy"], bad_rc["reason"])
    bad_old = parse_probe(0, "TORCH 1.13.1+cu117\nCUDA_BUILD 11.7\nCUDA_AVAIL True\n")
    check("R2-c 版本 <2.0 必须判 unhealthy", not bad_old["healthy"], bad_old["reason"])
    good = parse_probe(0, "TORCH 2.11.0+cu128\nCUDA_BUILD 12.8\nCUDA_AVAIL True\n")
    check("R2-d 健康 CUDA build 必须判 healthy", good["healthy"], good["reason"])

    # ---- ① 预期登记可见（机器可判，禁止"只写在文档里"） ----
    print("\n[1] 预置预期登记")
    check("1-a 预期已登记：torch>=2.0 且要求 CUDA build",
          EXPECT["torch_min"] >= "2.0" and EXPECT["cuda_build_required"],
          json.dumps(EXPECT, ensure_ascii=False))

    # ---- ② 可用性自检 ----
    print("\n[2] 可用性自检")
    venv_py = discover_venv_py()
    decision = decide(venv_py)
    if decision == "skip":
        soft_skip(
            "2-a CUDA venv 未预置（advisory）：GPU 后端自动回退 numpy/cpu；"
            "CI 沙箱因审计 R7 缺口无法下载 CUDA wheel，属合法缺席，不阻断任何门禁",
            f"expected={VENV_DIR}",
        )
        check("2-b 缺席环境不得误判 FAIL（只走 SKIP）", True, "venv absent => SKIP")
    else:
        rc, out = run_torch_probe(venv_py)
        res = parse_probe(rc, out)
        check("2-b venv 存在时 torch 探针健康（import + CUDA build + 版本达标）",
              res["healthy"],
              f"torch={res['version']} cuda_build={res['cuda_build']} "
              f"avail={res['cuda_avail']} :: {res['reason']}")
        if res["healthy"]:
            check("2-c CUDA 实际可用（torch.cuda.is_available）",
                  res["cuda_avail"] is True,
                  f"cuda_avail={res['cuda_avail']}（硬件缺失仅告警，build 正确即达标）")

    # ---- R1：反向测试 —— 不存在路径必须走 SKIP（非 PASS/非 FAIL） ----
    print("\n[R1] 缺席路径反向测试")
    fake = ROOT / "lda_cuda_venv_DOES_NOT_EXIST" / "Scripts" / "python.exe"
    check("R1 不存在的 venv 路径必须判定 skip（advisory，不进 FAIL）",
          decide(fake) == "skip", f"fake={fake}")

    print("\n" + "=" * 70)
    print(f">> 结果：{PASS} PASS / {FAIL} FAIL / {SKIP} SKIP"
          f"（SKIP = 本环境未预置 CUDA venv，属 advisory，rc=0）")
    print("=" * 70)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
