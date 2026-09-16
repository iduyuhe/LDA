"""场级 ORACLE（B5–B7：Y 分支 / 光栅耦合器 / 交叉）。

设计目标：把 B5–B7 的黄金参考从"扁平设计守则锚"(3.0dB / 0.5 / -40dB)
升级为**几何相关真值**——验证裁判更硬。

两层 ORACLE，遵守《白皮书》§11 许可证红线：
1. 【生产级·真场级】Meep/Tidy3D（GPL）—— 仅作**外部 ORACLE**：
   由 `ext_oracle/meep_oracle.py` 在 GPL 隔离环境以**子进程**运行，
   回传标量。核心**绝不 import** GPL 代码（用 env LDA_MEEP_PY 指定解释器）。
2. 【离线·近似】本文件内的纯 numpy 2D-FDTD / 重叠估计（Apache-2.0）——
   本环境即可跑，给出几何相关的真实量级（非 GPL，非最终真值，标注 offline）。
   ⚠️ B7 的 2D 离线核自 v0.9.82 起**不再作为 golden**（模型-器件不匹配，
      见 `_fdtd2d_crossing`），仅作机理诊断量；B7 golden 走 Meep → 设计守则锚。

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
# 1. 离线 numpy 2D-FDTD（B7 交叉 — ⚠️ 机理诊断量，**不再作 golden**）
# --------------------------------------------------------------------------
# v0.9.82 修复（三处缺陷，全部有收敛性证据；见 P1-1_B7_golden_fix_report.md）：
#   · 吸收层：σ_max = target_exp·3·n_clad²/(dt·pml)，pml 按**物理厚度**取
#     1.2 µm；衰减算子用 exp(−σdt)。原实现 σ 固定 0.06 且用 (1−σdt) —— 后者
#     在 σ_max≈76 时变负会发散，**这才是原实现只能用弱 σ 的真实原因**，而非
#     「弱吸收够用」。修复后 pml 厚度 1.2 vs 1.5 µm 仅差 0.16 dB。
#   · 源：全程 CW + ramp = 10 光周期 + 基模匹配横向形状（取自参考直波导运行）。
#     原实现 n≥460 停源，而测量窗自 600 步起 ⇒ 累加的是**衰减暂态**。
#     修复后步数 3000/6000/12000 给 −19.042/−19.030/−19.028（0.015 dB）。
#   · 度量：**净功率流**（Poynting）S_x = −Ez·Hy、S_y = +Ez·Hx，锁相检波后
#     P = Re(Σ A_Ez·conj(A_H))。行波给净流、驻波给零净流 ⇒ 对干涉免疫。
#     原实现的单点 Σ|E|² 含交叉区辐射近场，随监视距离漂 9.4 dB；修复后
#     1.5/2.0/2.5/3.0 µm 给 −10.89/−10.86/−11.05/−11.27（0.4 dB）。
#   · 十字结构在 x 方向对称 ⇒ 垂直波导两侧各得一半，故对 ±x 两端求和。
#
# ⚠️ 但第三层缺陷**不可在 2D 内修复**，故本函数**不再作为 B7 golden**：
#   本体几何（w=0.5/h=0.22/n_si=3.48/n_clad=1.44/wl=1.55）与实证语料
#   E-SOI-CROSS-XT **完全相同**（Zhang 2013 PTL 25(13):1225，
#   DOI 10.1109/LPT.2013.2241049；同篇还给出 E4 的 IL=0.18 dB），实测
#   **−41±2 dB**；而 2D 降维模型给出 −11 ~ −20 dB（差 20~30 dB）。加 taper
#   展宽（W_max 0.5→1.5 µm）仅改善 3.6 dB；源位置深扫 1.5~4.0 µm 在 ±3 dB
#   内乱跳无收敛趋势（2D 线源的辐射不匹配真实 3D 波导激励，直接污染垂直
#   波导）。⇒ 复现该器件需 **3D 全波 + 真实 taper 版图**（T2 级缺口）。
_B7_DIAG = dict(dl=0.05, N=240, pml_um=1.2, target_exp=12.0, nsteps=8000,
                ramp_cycles=10.0, off_um=2.0, src_off_um=3.5, meas_frac=0.5)


def _b7_crossing_core(w_core, n_si, n_clad, wl, vertical, phi_shape=None,
                      dl=0.05, N=240, pml_um=1.2, target_exp=12.0, nsteps=8000,
                      ramp_cycles=10.0, off_um=2.0, src_off_um=3.5,
                      meas_frac=0.5):
    """2D TE-FDTD 十字交叉核（Yee 网格 + 梯度吸收层 + 净功率流度量）。

    `vertical=False` 为参考直波导运行（供提取基模横向剖面 φ）。
    返回 {"crosstalk_dB", "one_side_dB", "seg_drift", "phi"}（参考运行只返回 phi）。
    """
    pml = max(6, int(round(pml_um / dl)))
    ramp = max(60, int(round(ramp_cycles * (wl / dl))))
    w_cells = max(4, int(round(w_core / dl)))
    center = N // 2
    half = w_cells // 2
    band = slice(center - half, center + half + 1)
    nb = 2 * half + 1

    eps = np.full((N, N), n_clad ** 2)
    eps[band, :] = n_si ** 2
    if vertical:
        eps[:, band] = n_si ** 2

    dt = dl / math.sqrt(2.0) * 0.95
    sig_max = target_exp * 3.0 * (n_clad ** 2) / (dt * pml)
    prof = np.zeros(N)
    for i in range(pml):
        f = ((pml - i) / pml) ** 2
        prof[i] = f
        prof[N - 1 - i] = f
    sig2 = np.minimum(prof[:, None] + prof[None, :], sig_max)
    damp = np.exp(-sig2 * dt)
    dampHx = np.exp(-sig2[:, :-1] * dt)
    dampHy = np.exp(-sig2[:-1, :] * dt)

    omega = 2.0 * math.pi / (wl / dl) * (dl / dt)

    Ez = np.zeros((N, N))
    Hx = np.zeros((N, N - 1))
    Hy = np.zeros((N - 1, N))

    src_x = center - int(round(src_off_um / dl))
    off = int(round(off_um / dl))
    y_thr, x_p, x_m = center + off, center + off, center - off

    if phi_shape is None:
        shape = np.ones(nb)
    else:
        shape = np.abs(np.asarray(phi_shape, dtype=complex))
        shape = shape / max(float(np.max(shape)), 1e-30)

    meas_start = int(nsteps * (1.0 - meas_frac))
    half_pt = meas_start + (nsteps - meas_start) // 2

    def _z():
        return np.zeros(nb, dtype=float)

    tEz_c, tEz_s, tHx_c, tHx_s = _z(), _z(), _z(), _z()
    pEz_c, pEz_s, pHy_c, pHy_s = _z(), _z(), _z(), _z()
    mEz_c, mEz_s, mHy_c, mHy_s = _z(), _z(), _z(), _z()
    bEz_c, bEz_s = _z(), _z()
    prof_c, prof_s = _z(), _z()

    for n in range(nsteps):
        Hx -= dt / dl * (Ez[:, 1:] - Ez[:, :-1])
        Hy += dt / dl * (Ez[1:, :] - Ez[:-1, :])
        dHy_dx = (Hy[1:N - 1, 1:N - 1] - Hy[0:N - 2, 1:N - 1]) / dl
        dHx_dy = (Hx[1:N - 1, 1:N - 1] - Hx[1:N - 1, 0:N - 2]) / dl
        Ez[1:N - 1, 1:N - 1] += dt / eps[1:N - 1, 1:N - 1] * (dHy_dx - dHx_dy)

        env = (0.5 * (1 - math.cos(math.pi * min(n, ramp) / ramp))
               if n < ramp else 1.0)
        Ez[band, src_x] += 0.5 * env * math.sin(omega * n) * shape

        Ez *= damp
        Hx *= dampHx
        Hy *= dampHy

        if n >= meas_start:
            cs, sn = math.cos(omega * n), math.sin(omega * n)
            eT = Ez[band, y_thr]
            hT = Hx[band, y_thr]
            eP = Ez[x_p, band]
            hP = Hy[x_p, band]
            eM = Ez[x_m, band]
            hM = Hy[x_m, band]
            if n >= half_pt:
                tEz_c += eT * cs; tEz_s += eT * sn
                tHx_c += hT * cs; tHx_s += hT * sn
                pEz_c += eP * cs; pEz_s += eP * sn
                pHy_c += hP * cs; pHy_s += hP * sn
                mEz_c += eM * cs; mEz_s += eM * sn
                mHy_c += hM * cs; mHy_s += hM * sn
            else:
                bEz_c += eT * cs; bEz_s += eT * sn
                prof_c += eT * cs; prof_s += eT * sn

    def _pw(ec, es, hc, hs):
        return float(np.real(np.sum((ec + 1j * es) * np.conj(hc + 1j * hs))))

    amp = prof_c + 1j * prof_s
    amp = amp / max(float(np.max(np.abs(amp))), 1e-30)
    out = {"phi": amp}
    if not vertical:
        return out

    p_thr = _pw(tEz_c, tEz_s, tHx_c, tHx_s)      # S_y = +Ez·Hx
    p_xp = -_pw(pEz_c, pEz_s, pHy_c, pHy_s)      # S_x = −Ez·Hy
    p_xm = _pw(mEz_c, mEz_s, mHy_c, mHy_s)       # −x 向外流
    p_ct = max(p_xp, 0.0) + max(p_xm, 0.0)
    a_a = float(np.sqrt(np.sum(np.abs(tEz_c + 1j * tEz_s) ** 2)))
    a_b = float(np.sqrt(np.sum(np.abs(bEz_c + 1j * bEz_s) ** 2)))
    out["crosstalk_dB"] = 10.0 * math.log10(max(p_ct / max(p_thr, 1e-30), 1e-30))
    out["one_side_dB"] = 10.0 * math.log10(
        max(max(p_xp, 0.0) / max(p_thr, 1e-30), 1e-30))
    out["seg_drift"] = abs(a_b - a_a) / max(a_a, 1e-30)
    return out


def _fdtd2d_crossing(params):
    """波导交叉串扰(dB) —— 2D TE-FDTD **机理诊断量**（⚠️ 不作为 B7 golden）。

    两条等宽波导在中心 90° 交叉；西端口全程 CW 注入（基模匹配），在交叉点
    两侧的垂直波导截面上取**净功率流**，串扰 = 10·log10(Σ两侧 P⊥ / P_through)。

    默认参数（w=0.5/h=0.22/n=3.48/1.55µm）给 **−14.1 dB**（≈ 裸十字），
    而其**锚定器件**（同几何的 taper 优化交叉，E-SOI-CROSS-XT）实测
    **−41±2 dB** ⇒ 本函数输出与锚定器件相差 20~30 dB，**不得作为 golden**
    （否则把「模型-器件不匹配」伪装成锚真值）。B7 golden 只经 Meep 真场级
    （未启用）→ 设计守则锚 −40 dB。本函数保留为设计侧机理诊断（裸十字 vs
    优化交叉的对比基线），证据链见 `P1-1_B7_golden_fix_report.md`。
    """
    w_core = float(params.get("w_core", 0.5))
    n_si = float(params.get("n_si", 3.48))
    n_clad = float(params.get("n_clad", 1.44))
    wl = float(params.get("wl", 1.55))
    cfg = dict(_B7_DIAG)
    ref = _b7_crossing_core(w_core, n_si, n_clad, wl, vertical=False, **cfg)
    res = _b7_crossing_core(w_core, n_si, n_clad, wl, vertical=True,
                            phi_shape=ref["phi"], **cfg)
    val = float(res["crosstalk_dB"])
    return {"value": val, "source": "numpy-fdtd-offline",
            "note": (f"2D FDTD 离线**机理诊断量（非 golden）**; 裸十字 XT={val:.3f} dB "
                     f"(单侧 {res['one_side_dB']:.3f}); seg_drift={res['seg_drift']:.1e}; "
                     f"与锚定器件实证 −41±2 dB 相差 {abs(val + 41.0):.1f} dB")}


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
      'numpy-overlap-offline' — numpy 重叠估计离线近似（B5）
      None                    — 无 ORACLE（golden 回退设计守则锚）
                                B7 自 v0.9.82 起即走此路（离线 2D 已撤出，
                                见 `_fdtd2d_crossing` 的 ⚠️ 说明）
    """
    dispatch_offline = {
        "B5": _ybranch_overlap,
        "B6": _b6_oracle,  # 3D：优先 Tidy3D 外部 ORACLE，否则 None→设计守则锚
        # B7 已于 v0.9.82 撤出 golden 调度：2D 降维（裸十字）与其锚定器件
        # （500×220 SOI taper 优化交叉，实证 −41±2 dB）相差 20~30 dB，
        # 作 golden 会把「模型-器件不匹配」伪装成锚真值。B7 golden 现只经
        # Meep 真场级（未启用）→ 设计守则锚 −40 dB（有 E7 实证背书）；
        # `_fdtd2d_crossing` 降级为独立机理诊断量，不参与判决。
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
