"""LDA · L3 自研 1D FDTD 求解核（agent-native，C 级自主）。

从第一性原理实现一维麦克斯韦方程组（Ez / Hz 交错 Yee 网格 + 梯度海绵吸收层），
求解标量 1D 波方程，输出垂直入射多层结构的透射谱。

设计哲学（刻意区别于 Meep 等"为人类操作"系统）：
- **机器优先接口**：喂入结构化 spec（分层折射率剖面 + 波长列表），一步返回
  透射谱 dict（JSON 可序列化）—— agent 直接消费出结果，人不需逐步点击/调参。
  这正是 LDA 人机协作总纲：agent 出结果，人做判断。
- **零外部依赖**：仅 numpy；离线可跑，不 import 任何 GPL/商业求解器。
- **可验证**：谱形必须经 tmm.py 物理定律锚（多层膜传输矩阵解析解）交叉校验
  —— 自写核不能自证（沿用全局验证锚纪律）。

数值方案要点：
- 单位归一化 c = μ = 1；空间步 dl(µm)、时间步 dt = dl·courant（courant<1 保稳定）。
- 网格策略（关键）：
  整个谱用**同一固定 dl**（由最短波长按目标"每波长网格数"推导），并对结构中最薄
  层厚度取整吸附 —— 使各层厚度落在整数格点上，几何与波长无关。否则 dl 随 λ 变
  会导致薄膜光学程、布拉格周期随波长漂移 → 法布里-珀罗条纹错位、禁带整体平移。
- 吸收边界：梯度海绵损耗层（二次 σ 剖面），介质 ε 不变——物理吸收，
  无 Mur-ABC 随波速 1/n 退化、无 CPML 卷积系数易错的坑。
- 透射测量（参考跑归一化法，绝对定标，物理严谨）：
  对每个波长跑两次：
    (1) 真实结构：末层出射区（折射率 nL）监视点复 DFT → E_real；
    (2) 参考跑：几何完全相同，但所有层折射率替换为 n0（无结构），同位置监视
        为纯入射场 → E_ref。
  两者同几何同软源，共模误差（源渐入、网格色散、海绵吸收、DFT 泄漏）在比值中
  自动抵消 → 绝对标度正确：T = (nL/n0)·|E_real / E_ref|²（标准平面波功率透射）。
- **源必须全程开启（已根除早期反复假失败的根因）**：
  软源在 ramp 步内余弦渐入后保持恒定 1.0 到 nsteps 结束，绝对不可在 DFT 测量
  窗口（meas0 之后）前关闭——否则测得的是源关断后衰减中的场，标度整体崩塌，
  表现为"场幅 1e-7""假驻波"等伪差。现已固定为全程开启。
"""
from __future__ import annotations

import math

import numpy as np


def _choose_dl(layers, wls, cpw):
    """选定固定网格步 dl（µm）：由最短波长按 cpw 推导，并吸附到最薄层整数格点。

    保证几何与波长无关、且最薄特征层厚度精确落在整数格上（消光学程/周期漂移）。
    """
    wl_min = min(wls)
    base_dl = wl_min / cpw                       # 最短波长目标每波长 cpw 格
    finite = [th for th, n in layers if not math.isinf(th)]
    if not finite:
        # 全半无限包层（纯均匀介质）：无特征层可吸附，直接用 base_dl
        return base_dl
    th_min = min(finite)                         # 最薄有限层（吸附目标）
    k = max(2, round(th_min / base_dl))          # 该层取整数格数
    dl = th_min / k                              # 吸附后 dl（使 th_min 恰好 k 格）
    return dl


def _build_profile(layers, dl):
    """由分层定义构建离散折射率剖面 n(z)（每层厚度吸附到整数格点）。"""
    segs = []
    for thick, n in layers:
        ncells = 80 if math.isinf(thick) else max(2, int(round(thick / dl)))
        segs.append((ncells, float(n)))
    total = sum(s[0] for s in segs)
    nz = np.empty(total, dtype=float)
    i = 0
    for ncells, n in segs:
        nz[i:i + ncells] = n
        i += ncells
    return nz


def _ref_layers(layers):
    """参考跑剖面：几何不变，所有层折射率替换为入射介质 n0（构造无结构均匀介质）。"""
    n0 = float(layers[0][1])
    return [(th, n0) for th, n in layers]


def _run_monochromatic(layers, wl, dl, courant, ramp, sponge, target_exp):
    """单次单色稳态 FDTD（梯度海绵吸收）：返回出射区监视点平均复 DFT（1 complex）。

    标准 Yee 更新（单位 c=μ=ε0=1，介质 ε=n²），海绵区附加导电损耗 σ：
      E: Ez[i] = (Ez[i] + dt/ε·dH) / (1 + dt·σ/ε)
      H: Hz[i] = (Hz[i] + dt·dE) / (1 + dt·σ_m)，  σ_m = σ/ε（保阻抗连续）
    σ 二次剖面：自海绵/无损交界(=0)平滑升至外边界(=σ_max)。σ_max 按目标总衰减
    常数标定，使 exp(-Σ dt·σ/ε) = exp(-target_exp)，与 dl/n 无关。

    软源：在左缓冲（n0）注入；ramp 步内余弦渐入，之后恒定 1.0 直到 nsteps 结束
    （全程开启，绝不在测量窗口前关闭）。
    """
    dt = dl * courant
    n0 = float(layers[0][1])
    nz = _build_profile(layers, dl)
    buf = 60                               # 左侧均匀缓冲（源所在，均为 n0）
    nz = np.concatenate([np.full(buf, n0), nz])
    interior = len(nz)
    N = interior + 2 * sponge
    nL_b = float(layers[-1][1])
    eps = np.ones(N)
    eps[:sponge] = n0 ** 2                  # 左海绵基底（接 n0）
    eps[sponge:sponge + interior] = nz ** 2  # 内部 = n²
    eps[sponge + interior:] = nL_b ** 2     # 右海绵基底（接 nL）

    # 导电损耗 σ 剖面（二次），按目标衰减标定 σ_max
    sig = np.zeros(N)
    for i in range(sponge):
        x = (sponge - 1 - i) / (sponge - 1)          # 外边界=1，交界=0
        sig[i] = x ** 2
    for i in range(N - sponge, N):
        x = (i - (N - sponge)) / (sponge - 1)
        sig[i] = x ** 2
    # Σ sig ≈ sponge/3（连续二次剖面）；令 dt·σ_max/eps·(sponge/3) = target_exp
    sig_max_left = target_exp * 3.0 * (n0 ** 2) / (dt * sponge)
    sig_max_right = target_exp * 3.0 * (nL_b ** 2) / (dt * sponge)
    sig[:sponge] *= sig_max_left
    sig[N - sponge:] *= sig_max_right
    sig_m = sig / eps                                 # 磁损耗 σ_m = σ/ε

    # 阻尼因子（更新时直接相乘）
    damp_E = 1.0 / (1.0 + dt * sig / eps)
    # Hz 边位于 E 节点 i 与 i+1 之间：取相邻 σ_m 平均（交界附近平滑过渡）
    damp_H = 1.0 / (1.0 + dt * 0.5 * (sig_m[:-1] + sig_m[1:]))

    # 几何布点
    src = sponge + 40                                   # 软源（左缓冲内，n0）
    out_c, out_d = N - sponge - 60, N - sponge - 59     # 出射监视器（末层 nL 包层内）

    omega = 2.0 * math.pi / wl                 # 真空角频（c=1）

    # 自适应步数：瞬态沉降 + 整数周期 DFT（消除频谱泄漏）
    period_steps = wl / (dl * courant)
    transient = max(ramp + int(5.0 * period_steps), 4000)
    M = max(2000, int(140.0 * period_steps))
    nsteps = transient + M
    meas0 = transient

    Ez = np.zeros(N)
    En = np.zeros(N)
    Hz = np.zeros(N - 1)
    oc_s = oc_c = od_s = od_c = 0.0

    for n in range(nsteps):
        # 磁场更新（全边）+ 海绵阻尼
        dE = (Ez[1:] - Ez[:-1]) / dl
        Hz = (Hz + dt * dE) * damp_H
        # 电场更新（内部节点 1..N-2）+ 海绵阻尼
        dH = (Hz[1:] - Hz[:-1]) / dl          # 在 E 节点 1..N-2（N-1 长）
        En[1:N - 1] = (Ez[1:N - 1] + dt / eps[1:N - 1] * dH) * damp_E[1:N - 1]
        # 两端边界节点（始终位于海绵内，阻尼已含）
        En[0] = (Ez[0] + dt / eps[0] * Hz[0]) * damp_E[0]                 # 左端 dH = Hz[0]
        En[N - 1] = (Ez[N - 1] + dt / eps[N - 1] * (-Hz[N - 2])) * damp_E[N - 1]

        # 软源：ramp 内余弦渐入 → 恒定 1.0 全程开启（绝不中途关闭）
        if n < ramp:
            env = 0.5 * (1.0 - math.cos(math.pi * n / ramp))
        else:
            env = 1.0
        En[src] += 0.5 * env * math.sin(omega * n * dt)

        Ez, En = En, Ez

        # 稳态后复 DFT 累加（e^{+iωt} 约定，幅度符号在比值中抵消）
        if n >= meas0:
            ph = omega * n * dt
            sp, cp = math.sin(ph), math.cos(ph)
            oc_s += Ez[out_c] * sp; oc_c += Ez[out_c] * cp
            od_s += Ez[out_d] * sp; od_c += Ez[out_d] * cp

    cnt = nsteps - meas0
    ec = complex(oc_s, oc_c) / cnt
    ed = complex(od_s, od_c) / cnt
    return 0.5 * (ec + ed)    # 两点平均，抑制网格色散噪声


def solve_spectrum(spec, dl_factor=60.0, courant=0.99, ramp=400,
                   sponge=120, target_exp=12.0):
    """一步求解透射谱，返回机器优先结构化 dict（参考跑归一化绝对标度）。

    spec = {
      "layers":         [(thickness_um, n), ...],   # 首尾 inf = 半无限包层
      "wavelengths_um": [...],
    }
    返回 {wavelengths_um, transmission, source, note}

    dl_factor 语义：最短波长目标"每波长网格数"（cpw）。实际 dl 由最短波长推导，
    并吸附到最薄层整数格点，保证几何与波长无关且特征层精确。
    """
    layers = spec["layers"]
    wls = spec["wavelengths_um"]
    n0 = float(layers[0][1])
    nL = float(layers[-1][1])
    ref = _ref_layers(layers)

    dl = _choose_dl(layers, wls, dl_factor)

    transmission = []
    for wl in wls:
        e_real = _run_monochromatic(layers, wl, dl, courant, ramp, sponge, target_exp)
        e_ref = _run_monochromatic(ref, wl, dl, courant, ramp, sponge, target_exp)
        if abs(e_ref) <= 1e-12:
            T = 0.0
        else:
            T = (nL / n0) * abs(e_real / e_ref) ** 2
        transmission.append(T)

    return {
        "wavelengths_um": list(wls),
        "transmission": transmission,
        "source": "lda-fdtd1d",
        "note": f"1D FDTD (gradient-sponge ABC + reference-run normalization); "
                f"dl={dl:.5f}um (cpw={dl_factor:.0f}@minwl), "
                f"courant={courant}, sponge={sponge}",
    }
