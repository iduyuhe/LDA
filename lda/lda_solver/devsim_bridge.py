"""T1-B-W1 · DEVSIM (Apache-2.0, B 级) subprocess 隔离桥（主权冷备调用层）。

纪律（对齐 `lda/lda_pdk/sovereign_deps.py` + `lda/lda_harness/oracle_tidy3d.py` 的 B 级处理）：
  - DEVSIM 为 B 级（Apache-2.0，可 fork 主权副本，借今踢后）。**绝不 import 进
    LDA Apache-2.0 核心**；只通过 subprocess 调起外部 DEVSIM 进程，回传**标量**。
  - DEVSIM 解出的 N(x)/P(x) 仅作**候选交叉校验**，与自研 C 级候选
    (`drift_diffusion_1d.solve_pn_junction_1d`) 互证；**永不**作为 ORACLE 真值
    （T1 输出不作 ORACLE 纪律）。死标量判决由 Sze 教科书闭式 golden 定。
  - 本环境未安装 DEVSIM（仅镜像冷备在 vendor/devsim_mirror），故跨校验函数
    默认返回 None，由调用方回退到自研 C 级候选。这是刻意主权安全默认。
  - EAR 744.23：DEVSIM 仅用于成熟节点/非先进用途（见 docs/lda_t1b_ear74423_compliance.md）。

subprocess 隔离契约：
  - 仅回标量（dict of float / None），不回传任何 DEVSIM 内部对象/数组引用。
  - DEVSIM 进程崩溃 → 捕获异常 → 返回 None（不污染核心，不静默假绿）。
"""
from __future__ import annotations

import shutil
import subprocess
import sys

# 本地镜像冷备路径（gitignored，详见 docs/lda_t1b_devsim_cold_backup.md）
DEVSM_MIRROR = "vendor/devsim_mirror"
# 锁定提交（r2.11.0 = 2.11.0，与 PyPI wheel 对齐）
PINNED_COMMIT = "43b41ca845184c47e22b72d144db7e7db8509377"

# T1 输出不作 ORACLE：DEVSIM 结果只是候选，golden 是 Sze 闭式
IS_ORACLE = False


def devsim_available() -> bool:
    """DEVSIM 是否可在外部调用（绝不进核心 venv）。

    仅当系统 PATH 有 `devsim` 可执行，或独立 venv 可 import 时返回 True。
    CI 核心 venv 不装 DEVSIM → 返回 False（链路走自研 C 级候选）。
    """
    if shutil.which("devsim"):
        return True
    try:
        import devsim  # 可能缺失（核心 venv 不装）
        return True
    except Exception:
        return False


def devsim_pn_junction_scalar_crosscheck(
    N_A: float, N_D: float, L: float, probe_x_um: float,
    devsim_script: str | None = None,
) -> dict | None:
    """DEVSIM 1D p-n 结**标量**交叉校验（候选，非真值）。

    参数：
      N_A, N_D, L    掺杂/长度（与 drift_diffusion_1d 同量纲，µm/cm⁻³）
      probe_x_um     探测点（µm），取该处载流子浓度标量
      devsim_script  外部 DEVSIM tcl/python 脚本路径（离线/空气间隙环境提供）

    返回：
      None                        → DEVSIM 不可用（回退自研 C 级候选）
      {"N_at_probe": float,       → 仅标量，DEVSIM 内部对象不逃逸
       "source": "devsim-subprocess",
       "note": "候选交叉校验，非 ORACLE"} 否则

    🔴 纪律：返回 dict of float（标量），绝不返回 DEVSIM 数组/对象引用。
       DEVSIM 崩溃 → 捕获 → 返回 None（不静默假绿）。
    """
    if not devsim_available() or devsim_script is None:
        return None
    try:
        # subprocess 外部进程：devsim -p <script>，脚本内把 N(probe_x) 打印为标量
        out = subprocess.run(
            [sys.executable, devsim_script,
             str(N_A), str(N_D), str(L), str(probe_x_um)],
            capture_output=True, text=True, timeout=120,
        )
        if out.returncode != 0:
            return None
        # 仅解析最后一个浮点标量（N_at_probe），其余输出丢弃
        last = out.stdout.strip().splitlines()[-1]
        n_at_probe = float(last.split()[-1])
        return {
            "N_at_probe": n_at_probe,
            "source": "devsim-subprocess",
            "note": "候选交叉校验，非 ORACLE（T1 输出不作真值）",
        }
    except Exception:
        # 任何异常（进程崩/超时/解析失败）→ 回退，不污染核心
        return None
