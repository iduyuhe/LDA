# -*- coding: utf-8 -*-
"""蓝图 v2 · **D2 QEC 码族 · M0 数值核**（`_batch_v2d2_numeric`）。

锚 **B525**：退极化信道的 **hashing（coherent-information）界** `I_c(p)`（bit / 信道使用）。

- **golden（闭式）**：`I_c(p) = 1 − H₂(p) − p·log₂3`，`H₂(p) = −p·log₂p − (1−p)·log₂(1−p)`。
  这是信息论的**精确闭式**（非截断近似）。本模块**独立实现**一次（不 import 能力层），
  以便门禁做「golden ≡ 能力层」的跨源对拍。
- **candidate（数值）**：用 `−log₂x = (1/ln2)·∫ₓ¹ dt/t` 把熵改写成两个积分

      H₂(p) = (1/ln2)·[ p·∫_p^1 dt/t + (1−p)·∫_{1−p}^1 dt/t ]

  再对两个积分做**复合 Simpson**（被积函数 `1/t` 光滑、解析）⇒ 残差是**真截断 O(h⁴)**，
  实测相邻比趋近 **16 = 2⁴**（n: 64→1024）。
  🔴 这不是「同式异写」：candidate 完全不调用 `log`，只做 `1/t` 的加权重求和。

🔴 **为什么必须换路子**：若 candidate 也直接算 `log`，两条路径都落在同一批 libm 调用上，
  残差只会在 0~几个 ulp 间摆动（`ulp(|g|)=8.3e-17`，而 BL-M2c 要求 `resid ≥ 1e4·ulp`）
  ⇒ 平台间不可复现。改积分表示后 `resid/ulp = 3.5e5`（n=1024）⇒ 非脆弱。

🔴 **端点语义**：`I_c(0)=1`；`I_c` 在 `p* ≈ 0.1893` 穿零；`I_c(3/4) = −1`（完全退极化）。
  **3/4 处不是 0** —— 本档自检当场纠正过这处误述。

🔴 零商业依赖（纯 `math`；零 RNG）。确定性：纯函数，无时钟/随机/文件 IO。
"""

from __future__ import annotations

import math

__all__ = [
    "B525_DEFAULT_PARAMS",
    "hashing_bound_golden",
    "golden_b525",
    "cand_b525",
    "_M_BY_BID",
    "_N_CHAIN",
    "_TOL_BY_BID",
]

_LN2 = math.log(2.0)
_LOG2_3 = math.log2(3.0)

#: B525 默认参数（退极化错误率；设计示例，非实验标定）
B525_DEFAULT_PARAMS = {"p": 0.10}

#: 默认候选段数（偶数 · 收敛链见 `_N_CHAIN`）
_M_BY_BID = {"B525": 1024}
#: 收敛链（残差随 n 严格单调降、比趋近 16 = 2⁴）
_N_CHAIN = {"B525": [64, 128, 256, 512, 1024]}
#: 默认 tol（按 BL-M5b 口径 `|golden|/12`；p=0.10 ⇒ |g|/12 = 0.03104）
_TOL_BY_BID = {"B525": 0.031}


def _bin_entropy_golden(p: float) -> float:
    """闭式 `H₂(p)`（端点按极限取 0）。**独立实现**，供跨源对拍。"""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -p * math.log2(p) - (1.0 - p) * math.log2(1.0 - p)


def hashing_bound_golden(p: float = B525_DEFAULT_PARAMS["p"]) -> float:
    """闭式 hashing 界 `I_c(p) = 1 − H₂(p) − p·log₂3`（bit / 信道使用）。"""
    if p < 0.0 or p > 0.75:
        raise ValueError("hashing_bound_golden: p 须在 [0, 0.75]，得到 %r" % (p,))
    return 1.0 - _bin_entropy_golden(p) - p * _LOG2_3


def golden_b525(p: float = B525_DEFAULT_PARAMS["p"]) -> float:
    """B525 golden（闭式）。"""
    return float(hashing_bound_golden(p))


def _simpson(f, lo: float, hi: float, n: int) -> float:
    """复合 Simpson（n 强制偶数）。"""
    n = int(n)
    n += n % 2
    h = (hi - lo) / n
    s = f(lo) + f(hi)
    for k in range(1, n):
        s += (4.0 if k % 2 else 2.0) * f(lo + k * h)
    return s * h / 3.0


def cand_b525(p: float = B525_DEFAULT_PARAMS["p"],
              n: int = _M_BY_BID["B525"]) -> float:
    """B525 候选：对数积分表示 + 复合 Simpson（残差 = 求积截断 O(h⁴)）。

    `H₂(p) = (1/ln2)·[ p·∫_p^1 dt/t + (1−p)·∫_{1−p}^1 dt/t ]`，两积分分别用 Simpson 现算
    （**不调用 log**）。`I_c = 1 − H₂ − p·log₂3`（最后一项是常数 `p·log₂3`，不是残差来源）。
    """
    if p < 0.0 or p > 0.75:
        raise ValueError("cand_b525: p 须在 [0, 0.75]，得到 %r" % (p,))
    if p == 0.0:
        return 1.0
    i1 = _simpson(lambda t: 1.0 / t, p, 1.0, n)
    i2 = _simpson(lambda t: 1.0 / t, 1.0 - p, 1.0, n)
    h2 = (p * i1 + (1.0 - p) * i2) / _LN2
    return float(1.0 - h2 - p * _LOG2_3)


if __name__ == "__main__":
    g = golden_b525()
    print("B525 golden = %.15f  (p=%.2f)" % (g, B525_DEFAULT_PARAMS["p"]))
    prev = None
    for n in _N_CHAIN["B525"]:
        v = cand_b525(n=n)
        r = abs(v - g)
        ratio = ("%.2f" % (prev / r)) if prev else "-"
        print("  n=%5d cand=%.15f resid=%.3e 比=%s" % (n, v, r, ratio))
        prev = r
    d = _M_BY_BID["B525"]
    print("默认 n=%d resid=%.3e tol=%.4f 余量=%.2e× resid/ulp=%.1e"
          % (d, abs(cand_b525(n=d) - g), _TOL_BY_BID["B525"],
             _TOL_BY_BID["B525"] / abs(cand_b525(n=d) - g),
             abs(cand_b525(n=d) - g) / (2 ** -52 * abs(g))))
