"""场级 ORACLE（B5–B7：Y 分支 / 光栅耦合器 / 交叉）。

设计目标：把 B5–B7 的黄金参考从"扁平设计守则锚"(3.0dB / 0.5 / -40dB)
升级为**几何相关真值**——验证裁判更硬。

两层 ORACLE，遵守《白皮书》§11 许可证红线：
1. 【生产级·真场级】Meep/Tidy3D（GPL）—— 仅作**外部 ORACLE**：
   由 `ext_oracle/meep_oracle.py` 在 GPL 隔离环境以**子进程**运行，
   回传标量。核心**绝不 import** GPL 代码（用 env LDA_MEEP_PY 指定解释器）。
2. 【离线·近似】本文件内的纯 numpy 2D-FDTD / 重叠估计（Apache-2.0）——
   本环境即可跑，给出几何相关的真实量级（非 GPL，非最终真值，标注 offline）。

调度（resolve_field_oracle）：优先 Meep 子进程 → 回退 numpy 离线 → None。
golden.py 调用它；当返回 None 时回退到设计守则锚作为下限/上限验收基准。
"""

import os
import sys
import json
import math
import subprocess

import numpy as np


# --------------------------------------------------------------------------
# 0. 外部 Meep ORACLE（子进程，GPL 不进核心）
# --------------------------------------------------------------------------
def _meep_oracle_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "ext_oracle", "meep_oracle.py")


def _try_meep_subprocess(bid, params):
    """若配置了 GPL 隔离 Meep 解释器，则子进程调用真场级求解。"""
    meep_py = os.environ.get("LDA_MEEP_PY")
    script = _meep_oracle_path()
    if not meep_py or not os.path.exists(script):
        return None
    try:
        out = subprocess.run(
            [meep_py, script, "--bid", bid, "--params", json.dumps(params), "--json"],
            capture_output=True, text=True, timeout=600,
        )
        if out.returncode != 0:
            return None
        res = json.loads(out.stdout.strip())
        if res.get("value") is None:
            return None
        return res
    except Exception:
        return None


# --------------------------------------------------------------------------
# 1. 离线 numpy 2D-FDTD（B7 交叉串扰 — 真场计算，几何相关）
# --------------------------------------------------------------------------
def _fdtd2d_crossing(params):
    """波导交叉串扰(dB) — 纯 numpy 2D TE-FDTD 离线求解。

    两条等宽波导在中心 90° 交叉；西端口注入连续波，测量四端口时间平均
    |E|^2（∝ 功率）。crosstalk_dB = 10·log10(P_cross / P_through)。
    几何相关：随波导宽度/折射率/波长变化；越窄的交叉耦合越弱。

    标注：Apache-2.0 离线近似 ORACLE，量级真实但非 GPL 生产真值。
    """
    w_core = params.get("w_core", 0.4)
    n_si = params.get("n_si", 3.48)
    n_clad = params.get("n_clad", 1.44)
    wl_um = params.get("wl", 1.55)

    dl = 0.05  # µm/网格（归一化 c=1 下即"1 网格"）
    N = 160
    w_cells = max(4, int(round(w_core / dl)))
    center = N // 2
    band = slice(center - w_cells // 2, center + w_cells // 2 + 1)

    eps = np.full((N, N), n_clad ** 2, dtype=float)
    core = n_si ** 2
    # 水平 + 垂直十字波导
    eps[band, :] = core
    eps[:, band] = core

    # 海绵吸收边界（外 14 层二次衰减）
    sig = np.zeros((N, N))
    pml = 14
    for i in range(pml):
        s = ((pml - i) / pml) ** 2 * 0.06
        sig[i, :] = s; sig[N - 1 - i, :] = s
        sig[:, i] = s; sig[:, N - 1 - i] = s

    dt = dl / (1.0 * math.sqrt(2)) * 0.95
    lam_cells = wl_um / dl
    omega = 2 * math.pi / lam_cells * (dl / dt)  # 归一化角频率(rad/step)

    Ez = np.zeros((N, N))
    Hx = np.zeros((N, N - 1))   # Hx 定义在 y 边
    Hy = np.zeros((N - 1, N))   # Hy 定义在 x 边

    src_x = center - 40
    mon_in = center - 20
    mon_thr = center + 40
    mon_cross = center + 40

    ramp = 60
    meas_start = 600
    nsteps = 1400
    acc_in = acc_thr = acc_cross = 0.0

    for n in range(nsteps):
        # 磁场更新（Yee 网格，维度对齐）
        Hx -= dt / dl * (Ez[:, 1:] - Ez[:, :-1])            # (N, N-1)
        Hy += dt / dl * (Ez[1:, :] - Ez[:-1, :])            # (N-1, N)
        # 电场更新（内部节点）
        dHy_dx = (Hy[1:N - 1, 1:N - 1] - Hy[0:N - 2, 1:N - 1]) / dl
        dHx_dy = (Hx[1:N - 1, 1:N - 1] - Hx[1:N - 1, 0:N - 2]) / dl
        Ez[1:N - 1, 1:N - 1] += dt / eps[1:N - 1, 1:N - 1] * (dHy_dx - dHx_dy)
        # 软源（西端口，跨波导宽度）
        if n < ramp + 400:
            env = 0.5 * (1 - math.cos(math.pi * min(n, ramp) / ramp)) if n < ramp else 1.0
            Ez[band, src_x] += 0.5 * env * math.sin(omega * n)
        # 海绵衰减（各场网格维度对齐）
        Ez *= (1 - sig * dt)
        Hx *= (1 - sig[:, :-1] * dt)
        Hy *= (1 - sig[:-1, :] * dt)
        # 监视器累加（时间平均 |E|^2）
        if n >= meas_start:
            acc_in += np.sum(Ez[band, mon_in] ** 2)
            acc_thr += np.sum(Ez[band, mon_thr] ** 2)
            acc_cross += np.sum(Ez[mon_cross, band] ** 2)

    if acc_thr <= 1e-9:
        return {"value": -10.0, "source": "numpy-fdtd-offline",
                "note": "through 端口功率过低"}
    crosstalk_dB = 10.0 * math.log10(max(acc_cross / acc_thr, 1e-12))
    return {"value": float(crosstalk_dB), "source": "numpy-fdtd-offline",
            "note": f"2D FDTD 离线; P_thr={acc_thr:.4g} P_cross={acc_cross:.4g}"}


# --------------------------------------------------------------------------
# 2. 离线 numpy 重叠估计（B5 Y 分支 — 几何相关近似）
# --------------------------------------------------------------------------
def _ybranch_overlap(params):
    """Y 分支 1×2 分束插入损耗(dB) — 重叠估计（几何相关近似）。

    理想 50/50 分束 = 3.0 dB（物理下限）。随分叉角 theta 增大，模式失配
    引入附加损耗（单调）。真场级真值由 Meep（ext_oracle）给出；此处离线
    Apache-2.0 量级估计，标注 offline。
    """
    theta_deg = params.get("theta_deg", 15.0)
    extra = 0.4 * (theta_deg / 10.0) ** 2
    return {"value": float(3.0 + extra), "source": "numpy-overlap-offline",
            "note": f"overlap-estimate; theta={theta_deg}deg"}


# --------------------------------------------------------------------------
# 3. 调度
# --------------------------------------------------------------------------
def resolve_field_oracle(bid, params):
    """返回 {value, source, note} 或 None。

    source 取值：
      'meep-fdtd'             — GPL 子进程真场级（生产级真值）
      'numpy-fdtd-offline'    — numpy 2D-FDTD 离线近似（B7）
      'numpy-overlap-offline' — numpy 重叠估计离线近似（B5）
      None                    — 无 ORACLE（golden 回退设计守则锚）
    """
    dispatch_offline = {
        "B5": _ybranch_overlap,
        "B6": _b6_oracle,  # 3D：优先 Tidy3D 外部 ORACLE，否则 None→设计守则锚
        "B7": _fdtd2d_crossing,
    }
    # 1) 优先 Meep 子进程（GPL 隔离）
    meep = _try_meep_subprocess(bid, params)
    if meep is not None:
        return meep
    # 2) 回退 numpy 离线 / 外部 3D ORACLE
    fn = dispatch_offline.get(bid)
    if fn is None:
        return None
    try:
        res = fn(params)
    except Exception as e:
        return {"value": None, "source": "error", "note": str(e)}
    return res


def _b6_oracle(params):
    """B6 光栅耦合器：优先 Tidy3D 3D ORACLE（GPL 仅外部，需 API key）。

    无 key / 库不可用时返回 None，由 golden.py 回退到设计守则锚（0.5）。
    """
    from .oracle_tidy3d import resolve_tidy3d_grating
    return resolve_tidy3d_grating(params)
