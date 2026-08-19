"""LDA · 1D 多层膜传输矩阵法（TMM）解析解 — 物理定律锚。

对逐层均匀、平面波垂直入射的多层膜，精确求解反射/透射（无吸收介质 R + T = 1）。
作为 fdtd1d 自研核的**非 AI 物理定律 ORACLE**：方程的必然，非某人意见。
本文件零依赖（仅 numpy / math）。

特征矩阵（垂直入射，场向量 [E, H]，H 以 nE 归一化）：
    M_j = [[cos δ_j,  i sin δ_j / n_j],
           [i n_j sin δ_j,  cos δ_j]]，  δ_j = 2π n_j d_j / λ
总转移 M = Π M_j；边界 n_0（入射侧）、n_L（出射侧）：
    r = (A - n0 B) / (A + n0 B)，  t = 2 n0 / (A + n0 B)
    A = M11 + M12 n_L，  B = M21 + M22 n_L
    R = |r|^2，  T = |t|^2 * (n_L / n_0)
"""
from __future__ import annotations

import numpy as np


def solve_spectrum(spec):
    """与 fdtd1d.solve_spectrum 同签名的解析透射谱。

    返回 {wavelengths_um, transmission, source, note}
    """
    layers = spec["layers"]
    wls = spec["wavelengths_um"]
    n0 = layers[0][1]
    nL = layers[-1][1]

    Ts = []
    for wl in wls:
        k0 = 2.0 * np.pi / wl
        M = np.eye(2, dtype=complex)
        for thick, n in layers:
            if np.isinf(thick):
                continue  # 半无限层无相位累积
            delta = k0 * n * thick
            cosd, sind = np.cos(delta), np.sin(delta)
            Mj = np.array([[cosd, 1j * sind / n],
                           [1j * n * sind, cosd]], dtype=complex)
            M = M @ Mj
        # 标准 TMM 边界（特征矩阵 [E; H] 约定，H 以 nE 归一化）
        #   入射侧 n0、出射侧 nL；总转移 M = [[M11, M12],[M21, M22]]
        #   r = (nL*M11 + nL*n0*M12 - M21 - n0*M22) / (nL*M11 + nL*n0*M12 + M21 + n0*M22)
        #   t = 2*n0 / (nL*M11 + nL*n0*M12 + M21 + n0*M22)
        denom = nL * M[0, 0] + nL * n0 * M[0, 1] + M[1, 0] + n0 * M[1, 1]
        num_t = 2.0 * n0
        num_r = nL * M[0, 0] + nL * n0 * M[0, 1] - M[1, 0] - n0 * M[1, 1]
        r = num_r / denom
        t = num_t / denom
        T = abs(t) ** 2 * (nL / n0) if (n0 > 0 and denom != 0) else 0.0
        Ts.append(float(T))

    return {
        "wavelengths_um": list(wls),
        "transmission": Ts,
        "source": "tmm-analytical",
        "note": "多层膜传输矩阵法解析解（物理定律锚）",
    }
