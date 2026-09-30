# -*- coding: utf-8 -*-
"""LDA · 电子计算征程 E3 · MVM 数据通路（计算架构 + 端到端正确性）（D-152）。

============================================================================
设计定位（吃狗粮：把 E2 的 MVM 阵列接成**完整矩阵运算数据通路**）
----------------------------------------------------------------------------
E2 造出了「N×M 模拟 MVM 交叉阵列」这一块砖；E3 把它接成**可用的模拟计算引擎**：
    x(数字) → DAC(量化) → 交叉阵列(E2 · 参考列法承载带符号权重) → ADC(量化) → y(数字)
并支持两类真实架构要素：
  · **多层级联**：Y = W_L @ act( … W_2 @ act(W_1 @ x) )（如 2 层 MLP + ReLU），带**层间定标**；
  · **分块（tiling）**：大矩阵按输出行切块、各块独立交叉阵列、输出拼接 ⇒ 合成 = 全阵 MVM。

正确性验证：与**全精度数字 golden**（同一权重/激活/定标，纯 numpy）逐元素比对，误差须
落在「量化 + 交叉阵列精度」预算内，且随 ADC/DAC 位数增加而下降。

🔴 带符号权重的物理实现（真实模拟交叉阵列的通行做法）：交叉点电导必须为正，故用
**参考列（offset/reference column）法**——电导 g_ij = g_base + s·W_ij（g_base 抬升保证 >0），
另设一列纯 g_base 参考列；数据列减参考列即得干净的有符号 MVM：y_j = −(V_j − V_ref)/(Rf·s·vfs)。

主权纪律（全平台同源）：C 级自主（纯 numpy）；LLM 不进判决路径；golden=全精度数字参考
（非外部 ORACLE）；**本包主动限定在电路级**（平台红线 = 分层：器件级 T1 已解锁 · T2 永久锁）。
参数为公开典型量级占位，不宣称器件性能。
"""
from __future__ import annotations

import numpy as np

from .crossbar_mvm import CrossbarMVM


# ---------------------------------------------------------------------------
# 量化器（DAC/ADC 统一模型：均匀中平量化 + 饱和）
# ---------------------------------------------------------------------------
def quantize_uniform(v, bits: int, vmin: float, vmax: float) -> np.ndarray:
    """均匀量化 + 钳位：把连续量映射到 2**bits 个电平（bits<=0 视为理想/不量化）。"""
    v = np.asarray(v, dtype=float)
    if bits <= 0:
        return v
    L = (vmax - vmin) / (2 ** bits - 1)
    if L <= 0:
        return v
    return np.clip(np.round((v - vmin) / L) * L + vmin, vmin, vmax)


def relu(v) -> np.ndarray:
    return np.maximum(np.asarray(v, dtype=float), 0.0)


# ---------------------------------------------------------------------------
# 单层模拟 MVM 单元（DAC → 交叉阵列 → ADC）
# ---------------------------------------------------------------------------
class AnalogMvmUnit:
    """一层模拟矩阵-向量乘的数据通路。

    W 形状 (M, N)：数字权重（可正可负）。内部：
      ① 电导映射 g_ij = g_base + s·W_ij（g_base = 1.5·max|W|·s ⇒ 恒 > 0）；
      ② 输入走 DAC（数字 [0,1] → 模拟 [0, vfs]）；
      ③ 交叉阵列（E2 CrossbarMVM ideal）+ 参考列承载 offset；
      ④ 数据列减参考列 ⇒ y = W @ x；输出走 ADC（对 y 量化）。
    """

    def __init__(self, W, s: float = 1e-4, rf: float = 1e4, vfs: float = 0.5,
                 dac_bits: int = 6, adc_bits: int = 6, vout_fs: float = 1.0,
                 out_norm: float = 0.0):
        self.W = np.asarray(W, dtype=float)
        self.M, self.N = self.W.shape
        self.s = float(s)
        self.rf = float(rf)
        self.vfs = float(vfs)
        self.dac_bits = int(dac_bits)
        self.adc_bits = int(adc_bits)
        self.vout_fs = float(vout_fs)
        # 🔴 输出定标（真实架构要素）：y_analog 幅度随 N 增长（MVM 是 N 项求和），
        # 若直接进固定 full-scale 的 ADC 会在规模增大时饱和。故 ADC 在**归一化域**量化：
        #   out_norm（默认 = 权重导出 h = max_r Σ_j|W|）⇒ y/out_norm ∈ [−1,1]（vout_fs=1）。
        #   ⇒ 绝对误差 ≈ out_norm·LSB/2（∝ N），相对误差 ≈ 1/(2^bits−1)（有界，N 无关）。
        wmax = float(np.max(np.abs(self.W)))
        h = float(np.max(np.sum(np.abs(self.W), axis=1))) if self.W.size else 0.0
        self.out_norm = float(out_norm) if out_norm > 0 else (h if h > 0 else 1.0)
        self.g_base = 1.5 * wmax * self.s if wmax > 0 else 1e-4

    def forward_analog(self, x_digital) -> np.ndarray:
        """量化前模拟输出（隔离交叉阵列精度，不含 ADC）。"""
        x = np.asarray(x_digital, dtype=float).reshape(-1)
        if x.shape[0] != self.N:
            raise ValueError("输入维数须等于 W 的列数")
        xq = quantize_uniform(x, self.dac_bits, 0.0, 1.0)
        vin = xq * self.vfs                            # 输入电压向量（长度 N）
        # 交叉点电导矩阵（M+1 行：M 数据列 + 1 参考列），均 > 0
        G = np.zeros((self.M + 1, self.N))
        G[: self.M, :] = self.g_base + self.s * self.W
        G[self.M, :] = self.g_base
        out = CrossbarMVM(G, vin, rf=self.rf, amp="ideal").solve()
        # y_j = −(V_j − V_ref)/(Rf·s·vfs)
        return -(out[: self.M] - out[self.M]) / (self.rf * self.s * self.vfs)

    def forward(self, x_digital):
        """完整数据通路（含 ADC 量化；输出经 out_norm 定标后进 ADC 再还原）。"""
        y_analog = self.forward_analog(x_digital)
        y = quantize_uniform(y_analog / self.out_norm, self.adc_bits,
                             -self.vout_fs, self.vout_fs) * self.out_norm
        return y, y_analog


# ---------------------------------------------------------------------------
# 多层模拟计算通路（层间定标 + 激活）
# ---------------------------------------------------------------------------
class MvmDatapath:
    """多层模拟 MVM 数据通路：Y = W_L @ act( … W_2 @ act(W_1 @ x) )。

    层间定标 h_k = max_r Σ_j |W_k[r,j]|（**仅依赖权重**、数据无关 ⇒ forward 与 golden
    用同一组定标，比对干净）：a_{k+1} = relu(y_k)/h_k ∈ [0,1]（喂下一层 DAC）。
    """

    def __init__(self, weights, **unit_kw):
        self.layers = [AnalogMvmUnit(W, **unit_kw) for W in weights]
        # 权重导出定标 h_k（数据无关，仅由权重决定）：
        #   · 每层 ADC 输出定标 out_norm = h_k（防大规模输出饱和）；
        #   · 层间激活定标 a_{k+1} = relu(y_k)/h_k ∈ [0,1]。
        self.h = [float(np.max(np.sum(np.abs(u.W), axis=1))) for u in self.layers]
        self.h = [h if h > 0 else 1.0 for h in self.h]
        for u, h in zip(self.layers, self.h):
            u.out_norm = h

    def _chain(self, x, layer_fn):
        a = np.asarray(x, dtype=float).reshape(-1)
        for k, u in enumerate(self.layers):
            y = layer_fn(u, a)
            if k < len(self.layers) - 1:
                a = relu(y) / self.h[k]              # 定标到 [0,1] 喂下一层
            else:
                return y
        return a

    def forward(self, x) -> np.ndarray:
        """模拟数据通路（含 DAC/ADC 量化）。"""
        return self._chain(x, lambda u, a: u.forward(a)[0])

    def forward_analog(self, x) -> np.ndarray:
        """模拟通路但**不含 ADC**（各层量化前输出链式），隔离交叉阵列精度。"""
        return self._chain(x, lambda u, a: u.forward_analog(a))

    def golden(self, x) -> np.ndarray:
        """全精度数字 golden（同权重 / 同激活 / 同层间定标，纯 numpy）。"""
        return self._chain(x, lambda u, a: u.W @ a)

    def max_abs_err(self, x) -> float:
        return float(np.max(np.abs(self.forward(x) - self.golden(x))))

    def max_rel_err(self, x) -> float:
        """相对误差（尺度不变）：max|y−gold| / max|gold|。规模对标用它（绝对误差 ∝ N）。"""
        g = self.golden(x)
        denom = float(np.max(np.abs(g)))
        if denom <= 0:
            return float(np.max(np.abs(self.forward(x) - g)))
        return float(np.max(np.abs(self.forward(x) - g)) / denom)


# ---------------------------------------------------------------------------
# 分块（tiling）合成：大矩阵按输出行切块，各块独立交叉阵列，输出拼接
# ---------------------------------------------------------------------------
def tiled_mvm(W, x, tile: int, **unit_kw) -> np.ndarray:
    """把 M×N 权重按输出行切成 ⌈M/tile⌉ 块，逐块走单层数据通路后拼接 ⇒ 合成全阵 MVM。

    🔴 分块必须共享**全阵的输出定标** out_norm = h(W_full)（编译期常数、与物理分块无关），
    否则各块各自定标 ⇒ 量化尺度不一致 ⇒ 合成 ≠ 全阵。
    """
    W = np.asarray(W, dtype=float)
    h = float(np.max(np.sum(np.abs(W), axis=1))) if W.size else 0.0
    out_norm = h if h > 0 else 1.0
    unit_kw = {k: v for k, v in unit_kw.items() if k != "out_norm"}
    chunks = []
    for j0 in range(0, W.shape[0], tile):
        u = AnalogMvmUnit(W[j0: j0 + tile], out_norm=out_norm, **unit_kw)
        chunks.append(u.forward(x)[0])
    return np.concatenate(chunks)


# ---------------------------------------------------------------------------
# 端到端自证桩
# ---------------------------------------------------------------------------
def mvm_datapath_self_check(seed: int = 0) -> dict:
    """端到端自证：单层精度 / 量化趋势 / 2 层 MLP / 分块合成，返回各判据值。"""
    rng = np.random.RandomState(seed)
    x = rng.uniform(0.0, 1.0, 6)
    W = rng.uniform(-1.0, 1.0, (4, 6))
    # 单层（8bit）
    dp1 = MvmDatapath([W], dac_bits=8, adc_bits=8)
    e_single = dp1.max_abs_err(x)
    # 量化趋势（误差应随位数单调下降）
    errs = {}
    for b in (3, 4, 5, 6, 8):
        dpb = MvmDatapath([W], dac_bits=b, adc_bits=b)
        errs[b] = dpb.max_abs_err(x)
    trend_ok = errs[8] <= errs[6] <= errs[4] <= errs[3]
    # 2 层 MLP
    W1 = rng.uniform(-1.0, 1.0, (5, 6))
    W2 = rng.uniform(-1.0, 1.0, (3, 5))
    dp2 = MvmDatapath([W1, W2], dac_bits=6, adc_bits=6)
    e_mlp = dp2.max_abs_err(x)
    # 分块合成（8bit）：应与整体阵列一致（差 ≤ 1 LSB 量级）
    y_full = MvmDatapath([W], dac_bits=8, adc_bits=8).forward(x)
    y_tile = tiled_mvm(W, x, tile=2, dac_bits=8, adc_bits=8)
    e_tile = float(np.max(np.abs(y_full - y_tile)))
    return {
        "single_layer_8bit_max_err": float(e_single),
        "quant_error_by_bits": errs,
        "quant_trend_monotone_decreasing": bool(trend_ok),
        "mlp_2layer_6bit_max_err": float(e_mlp),
        "tiling_vs_full_max_err": e_tile,
    }


MVM_DATAPATH_DISCLOSURE = {
    "route": "电子计算征程 E3 · MVM 数据通路（计算架构 + 端到端正确性）",
    "e3_scope": "数字→DAC→交叉阵列(E2)→ADC→数字 的模拟计算引擎；多层级联(MLP+ReLU) + 分块(tiling)",
    "weight_mapping": "带符号权重经参考列法映射为正电导（g=g_base+s·W，减参考列）",
    "correctness_claim": "端到端输出 vs 全精度数字 golden（同权重/激活/定标）；误差 = 量化 + 交叉阵列精度，随位数下降",
    "redline": "红线 = 分层口径（器件级 T1 内核已解锁 · T2 工艺真值/工艺角/流片永久锁）；"
               "本包主动限定在电路级；C 级自主（纯 numpy）；LLM 不进判决路径",
    "honest_boundary": "理想 TIA 路径（放大器无限增益理想化）；DAC/ADC 为均匀量化模型；"
                       "参数为公开典型量级占位（非 PDK、无实测锚）⇒ 不宣称实际芯片能效/精度",
}
