"""LDA L2 · 编译器 / AI 框架前端 —— 网络矩阵 → 酉分解 → 驱动清单 + 保真度报告。

============================================================================
红线自检标注（本模块守的纪律，详见 IRONLAWS.md / 愿景战略 §5）
----------------------------------------------------------------------------
- C 级自主：纯 numpy，**零外部依赖**；不 import torch / onnx / tensorflow / jax。
- LLM 不进判决路径：全部死标量 / numpy 运算，无任何模型推理调用。
- Layer-2 编译映射：目标酉经 Clements 矩形分解（数学定理）精确实现；
  复用 `lda_layout.mesh_pnr` 的已证分解 + 列分配 + 驱动清单生成链**作底座**
  （复用数学函数 ≠ 与版图链路耦合：本模块**不**跑 DRC / LVS / GDS）。
- 🔴 **前端边界（本模块的核心纪律）**：外部 AI 框架（PyTorch / ONNX / JAX …）
  只允许作**只读输入** —— 必须先转成 numpy 数组才可进入编译链路；判决路径
  有机器守卫 `guard_no_framework_in_judgment()`（检测到框架对象即 raise）。
============================================================================

## 它解决什么问题

光子 MZI 网格**只能**实现酉变换（无增益时还须是**被动**的）。而真实 DNN /
数值计算的算子（权重矩阵）几乎都**不是酉**。前端要做的三件事：

1. **酉性体检** —— 输入矩阵离酉有多远（SVD 谱 / 条件数 / 酉性偏差）。
2. **最近酉投影** —— 非酉时取 Frobenius 意义下的**最近酉算子**（Procrustes /
   极分解闭式解 `U_near = U·V†`，`A = U·Σ·V†`）。
3. **诚实标注** —— 实现的是 `U_near`，**不是** `A`。两者偏差有闭式解，
   必须原样报出（`residual_fro` / `residual_relative` / 最优缩放 `beta_opt`）。

## 🔴 诚实边界（防纸糊楼 / 不虚报）

1. **只做线性（酉）映射**。非线性（ReLU / softmax / 归一化 …）**不在**本编译器
   范围内 —— 光子网格对经典光**不做**非线性。声称「整个 DNN 都能编译」是错的。
2. **非酉残余不可为零**。`A` 非酉时，`min ‖A − U‖_F`（U 酉）> 0（除非 A 恰是酉）；
   本模块**只报**该下界与实现残差，**绝不**宣称「精确实现原算子」。
3. **奇异值夹持 = 有损**。若 `σ_max(A) > 1`，说明算子含**增益**；被动光子网格
   无法实现 ⇒ 必须先按 `β = 1/σ_max` 衰减（β<1 可实现，但损失动态范围），
   代价是**保真度下降**。夹持量与原谱一并报出。
4. **只做逻辑编译**。产出 = 合法酉目标 + 驱动电压清单；**不含**物理版图 /
   DRC / LVS / GDS（那是后端 `build_mesh_pnr` 的职责），**不含** L3 校准闭环。
5. **实数输入经复酉映射**（`real_mapped_to_complex`）。DNN 权重多为实矩阵，
   而光子场天然复相位 ⇒ 复酉近似**合法且更优**（实正交是复酉的子集），
   但该事实必须显式标注，不得默认读者已知。
6. **驱动电压是映射量级**。`V = φ·Vπ·L/(π·L_arm)`（Soref-Bennett），
   绝对电压为**闭环标定常量**，此处给映射关系与 V_max，**非**实测标定值。

## 接缝（复用既有已证资产，不重复实现）

| 复用对象 | 来源 | 用途 |
|---|---|---|
| `clements_rect_decompose` | `lda_layout.mesh_pnr` | 酉 → 压实 BS 序列 + 对角 D |
| `_rect_column_assignment` | `lda_layout.mesh_pnr` | BS 序列 → 2D 网格列号（同列端口不冲突） |
| `mesh_rect_decomp_fidelity` / `mesh_rect_fidelity` | `lda_layout.mesh_pnr` | 分解级 / 版级保真度 |
| `mesh_drive_manifest` | `lda_layout.mesh_pnr` | φ/D → 驱动电压清单（Vπ·L 定律） |

> `_rect_column_assignment` 虽为私有名，但本仓既有跨模块复用私有助手的惯例
> （见 `wdm_mesh_pnr.py` 导入 `_mzi_arm_polyline`）——**改名须穷举 git grep**。
"""
from __future__ import annotations

import csv
import json
import os
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

from lda_layout.mesh_pnr import (
    _rect_column_assignment,
    clements_rect_decompose,
    mesh_drive_manifest,
    mesh_rect_decomp_fidelity,
    mesh_rect_fidelity,
)

__all__ = [
    "FrontendBoundaryError",
    "COMPILER_DISCLOSURE",
    "UNITARY_TOL",
    "MAX_DIM",
    "matrix_spectrum",
    "nearest_isometry",
    "nearest_unitary",
    "complete_to_unitary",
    "clamp_singular_values",
    "guard_no_framework_in_judgment",
    "to_numpy_readonly",
    "compile_layer",
    "compile_network",
    "write_drive_manifest_csv",
    "write_network_drive_manifest_csv",
    "load_layers_from_json",
    "demo_network",
    "demo_nonunitary_network",
]

# 酉性判据阈：‖A·A† − I‖_max ≤ UNITARY_TOL ⇒ 视为酉（机器精度量级）。
UNITARY_TOL = 1e-9
# 单层维度上限：与 D3 实测主权 P&R 上限（N=512）一致；防误用超大矩阵拖垮 CI。
MAX_DIM = 512

# 判决路径**禁止**出现的外部框架模块前缀（零依赖检测：只看 type(...).__module__）。
_BANNED_FRAMEWORK_MODULES = (
    "torch", "tensorflow", "jax", "jaxlib", "onnx", "onnxruntime",
    "paddle", "mindspore", "tvm", "keras",
)

COMPILER_DISCLOSURE: Dict[str, Any] = {
    "scope": "仅线性（酉）映射的**逻辑编译**：网络矩阵 → 最近酉 → Clements 分解 "
             "→ 驱动电压清单 + 保真度报告。不含物理版图 / DRC / LVS / GDS，"
             "不含 L3 校准闭环。",
    "nonlinearity": "🔴 非线性（ReLU / softmax / 归一化 …）**不在**本编译器范围。"
                    "光子 MZI 网格对经典光不做非线性；本模块**不声称**能编译整个 DNN。",
    "nonunitary": "🔴 输入非酉时，光子网格**只能**实现其**最近酉算子** U_near "
                  "（Procrustes 闭式解）。残余 ‖A − U_near‖_F > 0 恒成立（除非 A 恰酉），"
                  "本模块原样报出并与解析预测交叉验证。",
    "clamping": "🔴 σ_max > 1 ⇒ 算子含增益 ⇒ 被动网格须先按 β = 1/σ_max 衰减；"
                "夹持（σ ← min(σ, 1)）是**有损**的，夹持量与原谱一并报出。",
    "real_input": "实矩阵经**复酉**映射（real_mapped_to_complex）——复酉是实正交的超集，"
                  "该近似合法且更优，但必须显式标注。",
    "drive_voltage": "V = φ·Vπ·L/(π·L_arm)（Soref-Bennett 硅热光）；绝对电压是"
                     "**闭环标定常量**，此处给映射关系与 V_max，非实测标定值。",
    "framework_boundary": "外部 AI 框架（PyTorch / ONNX / JAX …）只作**只读输入**："
                          "须经 to_numpy_readonly() 转 numpy 后才可进入编译链路；"
                          "判决路径有 guard_no_framework_in_judgment() 机器守卫。",
    "decomposition": "Clements 矩形分解为**数学定理**（非验证锚）：重构保真度 = 机器精度。",
    "sovereignty": "C 级自主（纯 numpy，零外部求解器）；LLM 不进判决路径。",
}


class FrontendBoundaryError(Exception):
    """前端边界违规（外部框架进入判决路径 / 非法输入 / 超维）。

    继承自 Exception 而非 ValueError：本类代表**红线边界**被触碰，
    CI 应据此报红，语义上区别于普通的数值输入错误。
    """


# ---------------------------------------------------------------------------
# 0) 前端边界守卫（🔴 红线机器化）
# ---------------------------------------------------------------------------
def _module_of(obj: Any) -> str:
    return type(obj).__module__.split(".")[0]


def guard_no_framework_in_judgment(obj: Any, where: str = "judgment") -> None:
    """🔴 红线守卫：判决路径只吃 numpy / 内建数值容器。

    若检测到 torch / onnx / tensorflow / jax / paddle / mindspore / tvm / keras
    等外部框架对象 ⇒ raise FrontendBoundaryError。

    零依赖实现：按 `type(obj).__module__` 前缀判定，**不 import** 那些包。
    递归检查 list / tuple / dict 元素，以及 dtype=object 的 numpy 数组。
    """
    mod = _module_of(obj)
    if mod in _BANNED_FRAMEWORK_MODULES:
        raise FrontendBoundaryError(
            f"前端边界违规（{where}）：判决路径不接受外部框架对象 {type(obj).__name__!r}"
            f"（模块 {mod!r}）。外部框架只作**只读输入** —— 请先经 "
            f"to_numpy_readonly() 或 np.asarray(x.detach().cpu().numpy()) 转 numpy。")
    if isinstance(obj, (list, tuple)):
        for x in obj:
            guard_no_framework_in_judgment(x, where)
    elif isinstance(obj, dict):
        for x in obj.values():
            guard_no_framework_in_judgment(x, where)
    elif isinstance(obj, np.ndarray) and obj.dtype == object:
        for x in obj.ravel().tolist():
            guard_no_framework_in_judgment(x, where)


def to_numpy_readonly(obj: Any, where: str = "adapter") -> np.ndarray:
    """把外部框架张量转为 numpy（**只读输入适配器**，位于边界外）。

    零依赖路径：numpy 数组 / 嵌套 list / 标量直接 `np.asarray`。
    框架对象：仅调用 `.detach()` → `.cpu()` → `.numpy()`（纯读取，**不**建立
    计算图依赖、**不**引入梯度），转换后立即过边界守卫。

    🔴 本函数**不 import** 任何框架包；它只调对象自身的转换方法。
    若对象无法转 numpy ⇒ raise（**不静默失败**）。
    """
    mod = _module_of(obj)
    if mod in _BANNED_FRAMEWORK_MODULES:
        for attr in ("detach", "cpu"):
            fn = getattr(obj, attr, None)
            if callable(fn):
                obj = fn()
        npv = getattr(obj, "numpy", None)
        if not callable(npv):
            raise FrontendBoundaryError(
                f"无法把 {type(obj).__name__!r} 转为 numpy（{where}）；"
                f"请先显式转 numpy 再进入编译链路。")
        obj = npv()
    arr = np.asarray(obj, dtype=complex)
    guard_no_framework_in_judgment(arr, where)
    return arr


# ---------------------------------------------------------------------------
# 1) 酉性体检
# ---------------------------------------------------------------------------
def matrix_spectrum(A: Any) -> Dict[str, Any]:
    """矩阵的 SVD 谱与酉性体检（纯死标量）。

    返回：shape / square / sigma（降序奇异值）/ sigma_max / sigma_min / cond /
    rank / n_sigma_gt_1（>1 的奇异值个数 ⇒ 是否含增益）/ unitarity_err_max /
    is_unitary。
    """
    M = np.asarray(A, dtype=complex)
    if M.ndim != 2 or M.size == 0:
        raise FrontendBoundaryError(f"matrix_spectrum 需要非空二维矩阵，得到 shape={M.shape}")
    s = np.linalg.svd(M, compute_uv=False)
    m, n = int(M.shape[0]), int(M.shape[1])
    square = (m == n)
    if square:
        un_err = float(np.max(np.abs(M @ M.conj().T - np.eye(m))))
    else:
        un_err = float("inf")   # 非方阵不可能酉（MZI 网格口径）
    smax = float(s.max()) if s.size else 0.0
    smin = float(s.min()) if s.size else 0.0
    return {
        "shape": [m, n],
        "square": bool(square),
        "sigma": [float(x) for x in s],
        "sigma_max": smax,
        "sigma_min": smin,
        "cond": (float(smax / smin) if smin > 0.0 else float("inf")),
        "rank": int(np.sum(s > 1e-12 * (smax if smax > 0.0 else 1.0))),
        "n_sigma_gt_1": int(np.sum(s > 1.0 + 1e-12)),
        "unitarity_err_max": un_err,
        "is_unitary": bool(un_err <= UNITARY_TOL),
    }


# ---------------------------------------------------------------------------
# 2) 最近酉投影（Procrustes / 极分解 · 闭式解）
# ---------------------------------------------------------------------------
def nearest_isometry(A: Any) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Frobenius 意义下的最近**部分等距**（闭式解 `U_p = U[:, :k]·V†[:k, :]`）。

    数学（Procrustes）：`argmin_{U†U = I_k} ‖A − U‖_F`（U 为 m×n 部分等距、
    k = min(m,n)）的解即 SVD 截断积 `U[:, :k] @ Vh[:k, :]`。
    最优标量缩放（允许整体衰减 β，物理上 = 可调衰减器）：
        β* = Σσ_i / k              （‖U_p‖_F² = k）
        residual² = Σσ_i² − (Σσ_i)²/k     （Frobenius 平方，闭式）
    两者**解析可预测** ⇒ 可作判据（实测 numpy == 闭式预测，机器精度）。

    🔴 关键：**对原 m×n 矩阵直接求**（**不**先 padding）—— 否则补零行会被
    最近酉填成非零，残余被结构污染（本模块 v1 曾踩此坑，实测 4×16 层相对
    残余虚高到 4.64）。此处的残余是**真正的逼近损失**，尺度正确。

    返回 (U_p (m×n), info)。
    """
    M = np.asarray(A, dtype=complex)
    if M.ndim != 2 or M.size == 0:
        raise FrontendBoundaryError(f"nearest_isometry 需要非空二维矩阵，得到 shape={M.shape}")
    m, n = int(M.shape[0]), int(M.shape[1])
    k = min(m, n)
    U, s, Vh = np.linalg.svd(M, full_matrices=True)
    U_p = U[:, :k] @ Vh[:k, :]
    sum_s = float(np.sum(s))
    fro2 = float(np.sum(s ** 2))
    beta_opt = float(sum_s / k)
    res_opt2 = max(0.0, fro2 - (sum_s ** 2) / k)
    res_fro = float(np.linalg.norm(M - U_p))
    res_opt = float(np.sqrt(res_opt2))
    norm_M = float(np.linalg.norm(M))
    return U_p, {
        "mode": "procrustes-nearest-isometry",
        "k": int(k),
        "shape": [m, n],
        "beta_opt": beta_opt,
        "residual_fro": res_fro,
        "residual_relative": (float(res_fro / norm_M) if norm_M > 0.0 else 0.0),
        "residual_rms": float(res_fro / float(np.sqrt(m * n))),
        "residual_at_opt_fro": res_opt,
        "residual_at_opt_relative": (float(res_opt / norm_M) if norm_M > 0.0 else 0.0),
        "sum_sigma": sum_s,
        "frobenius_sq": fro2,
        "note": "逼近目标是**最近部分等距** U_p = U[:,:k]·V†[:k,:]，**不是**输入 A；"
                "residual_fro = ‖A − U_p‖_F > 0 恒成立（除非 A 恰为部分等距）。",
    }


def nearest_unitary(A: Any) -> Tuple[np.ndarray, Dict[str, Any]]:
    """**方阵**的最近酉（`U_near = U·V†`）；非方阵 ⇒ raise（须走 isometry 路径）。

    方阵时 `nearest_isometry` 的结果即最近酉（k = N）。
    """
    M = np.asarray(A, dtype=complex)
    if M.ndim != 2 or M.shape[0] != M.shape[1]:
        raise FrontendBoundaryError(
            f"nearest_unitary 只接受方阵；得到 shape={getattr(M, 'shape', None)}。"
            f"非方阵请用 nearest_isometry()（残余才不受 padding 污染）。")
    return nearest_isometry(M)


def complete_to_unitary(U_p: Any) -> Tuple[np.ndarray, Dict[str, Any]]:
    """把 m×n **部分等距**扩展为 N×N 酉（N = max(m,n)）—— 物理可实现性构造。

    定理：任意部分等距均可扩展为酉。构造（零依赖，纯 numpy）：
      - m ≤ n（N=n，行正交 ⇒ 补 n−m **行**）：令 P = I_n − U_p†·U_p（投影到正交补，
        rank = n−m），`eigh(P)` 取特征值 ≈0 的特征向量即补空间的正交基 ⇒
        `U_full = [U_p ; W]` 酉。
      - m > n（N=m，列正交 ⇒ 补 m−n **列**）：令 P = I_m − U_p·U_p†，取零空间基 ⇒
        `U_full = [U_p , W]` 酉。

    🔴 **硬性质（可断言）**：`U_full[:m, :n] == U_p`（机器精度）—— 即「有效端口
    传输恰等于逼近结果」，这就是「部分等距可被 MZI 网格精确实现」的证明。
    返回 (U_full (N×N), info)；info 含补充方向 / 补充量 / 残差（应为 ~1e-15）。
    """
    Up = np.asarray(U_p, dtype=complex)
    if Up.ndim != 2 or Up.size == 0:
        raise FrontendBoundaryError(f"complete_to_unitary 需要非空二维矩阵，得到 shape={Up.shape}")
    m, n = int(Up.shape[0]), int(Up.shape[1])
    N = max(m, n)
    k = min(m, n)
    # 部分等距体检（诚实护栏：非部分等距则补全无意义）
    eye_k = np.eye(k)
    if m <= n:
        gram = Up @ Up.conj().T
        err = float(np.max(np.abs(gram - eye_k)))
    else:
        gram = Up.conj().T @ Up
        err = float(np.max(np.abs(gram - eye_k)))
    if err > 1e-8:
        raise FrontendBoundaryError(
            f"complete_to_unitary 输入非部分等距（体检残差 {err:.3e}）："
            f"须先经 nearest_isometry() 投影。")

    if m == n:
        return Up.copy(), {
            "N": N, "mode": "already-square", "added": 0,
            "direction": "none", "embedding_residual_max": 0.0,
            "note": "方阵部分等距即酉，无需补全。",
        }

    if m <= n:
        P = np.eye(n, dtype=complex) - Up.conj().T @ Up     # 投影到行空间正交补
        w, V = np.linalg.eigh(P)
        pick = n - m
        idx = np.argsort(w)[-pick:]                         # 特征值 ≈ 1 的张成补空间
        if pick and float(np.min(w[idx])) < 0.5:
            raise FrontendBoundaryError(
                f"正交补全失败：期望 {pick} 个特征值≈1，实得最小 {float(np.min(w[idx])):.3e}")
        W = V[:, idx].conj().T                              # (n−m)×n，补空间正交基
        U_full = np.vstack([Up, W])
        direction = "rows"
    else:
        P = np.eye(m, dtype=complex) - Up @ Up.conj().T
        w, V = np.linalg.eigh(P)
        pick = m - n
        idx = np.argsort(w)[-pick:]
        if pick and float(np.min(w[idx])) < 0.5:
            raise FrontendBoundaryError(
                f"正交补全失败：期望 {pick} 个特征值≈1，实得最小 {float(np.min(w[idx])):.3e}")
        W = V[:, idx]                                       # m×(m−n)
        U_full = np.hstack([Up, W])
        direction = "cols"

    un_err = float(np.max(np.abs(U_full @ U_full.conj().T - np.eye(N))))
    emb_err = float(np.max(np.abs(U_full[:m, :n] - Up)))
    return U_full, {
        "N": N, "mode": "orthogonal-completion", "added": int(N - k),
        "direction": direction,
        "unitarity_err_max": un_err,
        "embedding_residual_max": emb_err,
        "note": ("部分等距按正交补扩展为 N×N 酉；有效端口块 U_full[:m,:n] == U_p "
                 "（机器精度）⇒ 逼近结果可被 MZI 网格精确实现。"),
    }


def clamp_singular_values(A: Any, cap: float = 1.0) -> Tuple[np.ndarray, Dict[str, Any]]:
    """奇异值夹持：`σ_i ← min(σ_i, cap)`（默认 cap=1.0）。

    用途：把「含增益」（σ > 1）的算子压进**被动**酉可实现域。
    🔴 这是**有损**操作：夹持后算子 ≠ 原算子；偏差 = ‖A − A_clamped‖_F。
    物理上等价于先按 β = 1/σ_max 整体衰减（β<1 可实现，但损失动态范围），
    而**增益介质锁死**（T2 禁区）⇒ 放大无路径。

    返回 (A_clamped, info)。
    """
    M = np.asarray(A, dtype=complex)
    if M.ndim != 2 or M.size == 0:
        raise FrontendBoundaryError(f"clamp_singular_values 需要非空二维矩阵，得到 shape={M.shape}")
    cap = float(cap)
    if not (cap > 0.0):
        raise FrontendBoundaryError(f"cap 必须为正，得到 {cap}")
    U, s, Vh = np.linalg.svd(M, full_matrices=False)
    s_cl = np.minimum(s, cap)
    A_cl = (U * s_cl) @ Vh
    smax = float(s.max()) if s.size else 0.0
    n_trunc = int(np.sum(s > cap + 1e-12))
    return A_cl, {
        "sigma_cap": cap,
        "sigma_before": [float(x) for x in s],
        "sigma_after": [float(x) for x in s_cl],
        "n_truncated": n_trunc,
        "max_sigma": smax,
        "clamp_residual_fro": float(np.linalg.norm(M - A_cl)),
        "requires_attenuation": bool(n_trunc > 0),
        "attenuation_beta": (float(1.0 / smax) if smax > 0.0 else 1.0),
        "note": ("含增益（σ_max=%.6f > %g）：被动网格须先按 β=%.6f 衰减，"
                 "夹持有损，残余 %.3e。" % (smax, cap, (1.0 / smax if smax > 0.0 else 1.0),
                                          float(np.linalg.norm(M - A_cl))))
        if n_trunc > 0 else "无奇异值超过 cap ⇒ 无夹持损失（但不代表 A 酉）。",
    }


# ---------------------------------------------------------------------------
# 3) 单层编译
# ---------------------------------------------------------------------------
def compile_layer(A: Any, name: str = "layer",
                  sigma_cap: float = 1.0, ps_arm_um: float = 1000.0,
                  vpi_l_v_mm: float = 7.5) -> Dict[str, Any]:
    """编译单层矩阵 A → 合法酉目标 + 驱动清单 + 保真度报告。

    流程：
      ① 边界守卫 → ② 形状检查 → ③ 酉性体检
      → ④ **酉**（必方阵）：目标即 A，N = m = n，残余 0
         **非酉**：对原 m×n 求最近部分等距 U_p（**不 pad**）→ 正交补全为 N×N 酉
      → ⑤ Clements 压实分解 → ⑥ 列分配 → ⑦ 驱动清单（Vπ·L）
      → ⑧ 分解级 + 版级保真度。

    🔴 报告里三个量**不可混用**：
      - `fidelity_vs_target`     ：对**酉目标**的实现保真度（应 = 1.0，机器精度）
      - `nearest_unitary_info.residual_relative` ：**离原算子的逼近损失**（非酉 ⇒ > 0）
      - `clamp`                   ：含增益（σ>1）⇒ 被动网格须衰减的代价
      ⚠️ `residual_relative` 以 ‖A‖_F 归一且**未**计入整体缩放自由度 ⇒ 对「整体
      幅值偏小」的 A 可能 > 1（部分等距的范数固定为 √k，不可小）。**有解释力的
      指标是 `residual_at_opt_relative`** —— 允许整体衰减 β* = Σσ/k 后的相对残余
      （≤ 1，0 表示 A 恰为某部分等距的缩放）。
    端口语义：`active_in_ports = n`、`active_out_ports = m`；酉网格其余端口
    为补全旁路（不驱动 / 不采样）。
    """
    guard_no_framework_in_judgment(A, f"compile_layer[{name}]:input")
    M0 = np.asarray(A, dtype=complex)
    if M0.ndim != 2 or M0.size == 0:
        raise FrontendBoundaryError(f"层 {name!r} 需要非空二维矩阵，得到 shape={M0.shape}")
    m, n = int(M0.shape[0]), int(M0.shape[1])
    if max(m, n) > MAX_DIM:
        raise FrontendBoundaryError(
            f"层 {name!r} 维度 max({m},{n}) 超过前端上限 {MAX_DIM}")

    spec = matrix_spectrum(M0)
    is_real = bool(np.allclose(M0.imag, 0.0))

    if spec["is_unitary"]:
        N = m
        U_target = M0
        exact = True
        embedding: Dict[str, Any] = {
            "N": N, "mode": "already-square", "added": 0, "direction": "none",
            "embedding_residual_max": 0.0,
            "note": "输入即酉 ⇒ 无需补全，精确实现。",
        }
        unify: Dict[str, Any] = {
            "mode": "exact-unitary",
            "k": N, "shape": [m, n], "beta_opt": 1.0,
            "residual_fro": 0.0, "residual_relative": 0.0, "residual_rms": 0.0,
            "residual_at_opt_fro": 0.0, "residual_at_opt_relative": 0.0,
            "sum_sigma": float(np.sum(spec["sigma"])),
            "frobenius_sq": float(np.sum(np.square(spec["sigma"]))),
            "note": "输入即酉 ⇒ 精确实现，残余为零（机器精度）。",
        }
        clamp: Dict[str, Any] = {
            "sigma_cap": float(sigma_cap),
            "sigma_before": spec["sigma"], "sigma_after": spec["sigma"],
            "n_truncated": 0, "max_sigma": spec["sigma_max"],
            "clamp_residual_fro": 0.0, "requires_attenuation": False,
            "attenuation_beta": 1.0,
            "note": "输入酉 ⇒ 奇异值全为 1，无夹持。",
        }
    else:
        U_p, unify = nearest_isometry(M0)            # 对原 m×n（不 pad）
        U_target, embedding = complete_to_unitary(U_p)
        N = int(embedding["N"])
        _, clamp = clamp_singular_values(M0, cap=sigma_cap)
        exact = False

    bs_list, D = clements_rect_decompose(U_target)
    cols = _rect_column_assignment(bs_list)
    ops = [(int(j), float(th), float(ph), int(c))
           for (j, th, ph), c in zip(bs_list, cols)]
    drive = mesh_drive_manifest(ops, D, ps_arm_um=ps_arm_um, vpi_l_v_mm=vpi_l_v_mm)
    fid_decomp = float(mesh_rect_decomp_fidelity(bs_list, D, U_target))
    fid_layout = float(mesh_rect_fidelity(bs_list, D, U_target))

    return {
        "name": str(name),
        "shape_in": [m, n],
        "N": N,
        "active_in_ports": n,
        "active_out_ports": m,
        "embedding": embedding,
        "is_real_input": is_real,
        "real_mapped_to_complex": bool(is_real and not exact),
        "unitarity": spec,
        "exact_unitary": bool(exact),
        "implemented_operator": ("input" if exact else "nearest_isometry(A) ⊕ 正交补全"),
        "nearest_unitary_info": unify,
        "clamp": clamp,
        "n_mzi": int(len(ops)),
        "n_ps": int(D.shape[0]),
        "ops": ops,
        "D_diag": [complex(D[k, k]) for k in range(int(D.shape[0]))],
        "drive": drive,
        "fidelity_vs_target": fid_decomp,
        "layout_fidelity_vs_target": fid_layout,
    }


# ---------------------------------------------------------------------------
# 4) 网络编译
# ---------------------------------------------------------------------------
def _normalize_layers(layers: Sequence[Any]) -> List[Tuple[str, Any]]:
    out: List[Tuple[str, Any]] = []
    for idx, it in enumerate(layers):
        if isinstance(it, dict):
            nm = str(it.get("name", f"L{idx}"))
            if "matrix" not in it:
                raise FrontendBoundaryError(f"层定义缺 'matrix' 键：{it!r}")
            mx = it["matrix"]
        elif isinstance(it, (list, tuple)) and len(it) == 2:
            nm, mx = str(it[0]), it[1]
        else:
            raise FrontendBoundaryError(
                f"层定义须为 {{'name','matrix'}} 或 (name, matrix)：得到 {type(it).__name__}")
        out.append((nm, mx))
    return out


def compile_network(layers: Sequence[Any], name: str = "network", **kwargs: Any) -> Dict[str, Any]:
    """编译整张网络（层序列）→ 逐层报告 + 汇总。

    `layers`：`[(name, matrix), ...]` 或 `[{"name","matrix"}, ...]`。
    逐层调用 compile_layer（kwargs 透传，如 sigma_cap / ps_arm_um / vpi_l_v_mm）。

    🔴 汇总里 `min_fidelity_vs_target` 是**对酉目标**的保真度（应为 1.0）；
    真正的「离原算子的偏差」在 `max_relative_residual`（非酉损失）。
    两者**不可混用**，报告与 CSV 均分列。
    """
    norm = _normalize_layers(layers)
    reps = [compile_layer(mx, name=nm, **kwargs) for (nm, mx) in norm]
    n_mzi = int(sum(r["n_mzi"] for r in reps))
    n_drv = int(sum(r["n_mzi"] + r["n_ps"] for r in reps))
    worst_fid = float(min((r["fidelity_vs_target"] for r in reps), default=1.0))
    worst_layout = float(min((r["layout_fidelity_vs_target"] for r in reps), default=1.0))
    nonuni = int(sum(0 if r["exact_unitary"] else 1 for r in reps))
    n_clamp = int(sum(r["clamp"]["n_truncated"] for r in reps))
    max_res = float(max((r["nearest_unitary_info"]["residual_relative"] for r in reps),
                        default=0.0))
    return {
        "name": str(name),
        "layers": reps,
        "n_layers": int(len(reps)),
        "n_mzi_total": n_mzi,
        "n_driver_total": n_drv,
        "min_fidelity_vs_target": worst_fid,
        "min_layout_fidelity_vs_target": worst_layout,
        "n_nonunitary_layers": nonuni,
        "n_truncated_singular_values": n_clamp,
        "max_relative_residual": max_res,
        "all_exact_unitary": bool(nonuni == 0),
        "disclosure": COMPILER_DISCLOSURE,
    }


# ---------------------------------------------------------------------------
# 5) 驱动清单 CSV 落盘（格式与 examples/scale_up_p1b.py 同源）
# ---------------------------------------------------------------------------
def write_drive_manifest_csv(layer_report: Dict[str, Any], path: str,
                             tag: str = "LDA-U5") -> str:
    """单层驱动清单 CSV 落盘（表头与既有 `scale_up_p1b.py` 格式同源 + 加 layer 列）。

    列：kind, idx, col_c_or_rail, phi_rad, V
      - kind='mzi'：idx = 下轨 j，col_c_or_rail = 网格列 c
      - kind='out'：idx = 输出轨道，col_c_or_rail = '-'
    """
    dm = layer_report["drive"]
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([f"# {tag} 驱动电压清单", layer_report["N"], "x", layer_report["N"],
                    "layer", layer_report["name"],
                    "Vpi_L_mm", dm["vpi_l_v_mm"], "arm_um", dm["ps_arm_um"],
                    "Vpi_volts", round(dm["vpi_volts"], 3), "Vmax", round(dm["v_max"], 3)])
        w.writerow(["kind", "idx", "col_c_or_rail", "phi_rad", "V"])
        for d in dm["mzi"]:
            w.writerow(["mzi", d["j"], d["col_c"], round(d["phi_rad"], 6), round(d["V"], 4)])
        for d in dm["out"]:
            w.writerow(["out", d["rail"], "-", round(d["phi_rad"], 6), round(d["V"], 4)])
    return os.path.abspath(path)


def write_network_drive_manifest_csv(net_report: Dict[str, Any], path: str,
                                     tag: str = "LDA-U5") -> str:
    """网络驱动清单 CSV 落盘（多层 ⇒ 首列加 layer）。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([f"# {tag} 网络驱动电压清单", net_report["name"],
                    "layers", net_report["n_layers"],
                    "n_mzi_total", net_report["n_mzi_total"],
                    "n_driver_total", net_report["n_driver_total"]])
        w.writerow(["layer", "kind", "idx", "col_c_or_rail", "phi_rad", "V"])
        for lr in net_report["layers"]:
            dm = lr["drive"]
            for d in dm["mzi"]:
                w.writerow([lr["name"], "mzi", d["j"], d["col_c"],
                            round(d["phi_rad"], 6), round(d["V"], 4)])
            for d in dm["out"]:
                w.writerow([lr["name"], "out", d["rail"], "-",
                            round(d["phi_rad"], 6), round(d["V"], 4)])
    return os.path.abspath(path)


# ---------------------------------------------------------------------------
# 6) 边界外只读输入：JSON 层定义读取（零依赖）
# ---------------------------------------------------------------------------
def _decode_matrix(raw: Any) -> np.ndarray:
    """把 JSON 嵌套 list 解成复矩阵：元素为 number（实数）或 [re, im]（复数）。"""
    rows = list(raw)
    if not rows:
        raise FrontendBoundaryError("JSON 矩阵为空")
    out: List[List[complex]] = []
    width = None
    for r in rows:
        cells = list(r)
        if width is None:
            width = len(cells)
        elif len(cells) != width:
            raise FrontendBoundaryError("JSON 矩阵行宽不一致（非矩形）")
        row: List[complex] = []
        for c in cells:
            if isinstance(c, (list, tuple)):
                if len(c) == 2:
                    row.append(complex(float(c[0]), float(c[1])))
                elif len(c) == 1:
                    row.append(complex(float(c[0]), 0.0))
                else:
                    raise FrontendBoundaryError(f"复数须为 [re, im]，得到 {c!r}")
            else:
                row.append(complex(float(c), 0.0))
        out.append(row)
    return np.array(out, dtype=complex)


def load_layers_from_json(path: str) -> Tuple[str, List[Tuple[str, np.ndarray]]]:
    """从 JSON 读层定义（**边界外只读输入**，零外部依赖）。

    支持：
      {"name": "...", "layers": [{"name": "L0", "matrix": [[...]]}, ...]}
      或 [{"name": ..., "matrix": [...]}, ...]
    复数以 `[re, im]` 表示。返回 (network_name, [(layer_name, matrix), ...])。
    """
    with open(path, encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, dict):
        nname = str(obj.get("name", "network"))
        raw = obj.get("layers", [])
    else:
        nname, raw = "network", obj
    layers: List[Tuple[str, np.ndarray]] = []
    for idx, it in enumerate(raw):
        if not isinstance(it, dict) or "matrix" not in it:
            raise FrontendBoundaryError(f"第 {idx} 层定义须为 {{'name','matrix'}}：{it!r}")
        layers.append((str(it.get("name", f"L{idx}")), _decode_matrix(it["matrix"])))
    return nname, layers


# ---------------------------------------------------------------------------
# 7) demo 网络（确定性，无随机）
# ---------------------------------------------------------------------------
def _dft(N: int) -> np.ndarray:
    """N 点 DFT 酉矩阵（确定性复酉基准）。"""
    k = np.arange(N)
    return np.exp(-2j * np.pi * np.outer(k, k) / N) / float(np.sqrt(N))


def _spread_real(m: int, n: int, scale: float = 0.5) -> np.ndarray:
    """确定性实矩阵（非酉，常用于演示「离酉有多远」）：A[i,j] = scale/(1+i+j)。"""
    i = np.arange(m).reshape(-1, 1)
    j = np.arange(n).reshape(1, -1)
    return (scale / (1.0 + i + j)).astype(complex)


def _near_unitary(N: int, eps: float = 0.05) -> np.ndarray:
    """近酉矩阵 A = DFT(N) + P，‖P‖_F = eps（确定性小扰动）。

    模拟真实 DNN 层「几乎酉但非酉」的情形 ⇒ 逼近残余应 ≈ eps/‖A‖_F（小且可预测）。
    """
    U = _dft(N)
    d = np.arange(N, dtype=float)
    P = np.cos(d)[None, :] * np.sin(d)[:, None]
    nrm = float(np.linalg.norm(P))
    P = P * (eps / nrm) if nrm > 0.0 else P
    return U + P


def demo_network() -> Tuple[str, List[Tuple[str, Any]]]:
    """示例网络（**确定性**，验收用）：4×4 酉 → 4×16 非方阵实层 → 16×16 酉。

    覆盖三条路径：
      - 'dft4'    ：4×4 复酉 ⇒ 精确实现（残差 0）
      - 'real4x16'：4×16 实非方阵 ⇒ 最近部分等距 + 正交补全（N=16，有效端口 4×16）
      - 'dft16'   ：16×16 复酉 ⇒ 精确实现
    """
    return "demo_net_4_to_16", [
        ("dft4", _dft(4)),
        ("real4x16", _spread_real(4, 16, scale=0.5)),
        ("dft16", _dft(16)),
    ]


def demo_nonunitary_network() -> Tuple[str, List[Tuple[str, Any]]]:
    """含「近酉」与「增益」的示例网络（**确定性**）⇒ 触发两条非酉分支。

    层 'near_unitary16'：A = DFT16 + P（‖P‖_F=0.05）⇒ 近酉，残余小且可预测。
    层 'gain16'        ：A[i,j] = 2/(1+i+j)（实）⇒ σ_max > 1 ⇒ 被动网格须先
    衰减 β = 1/σ_max ⇒ 夹持损失被量化报出。
    """
    return "demo_net_nonunitary", [
        ("dft4", _dft(4)),
        ("near_unitary16", _near_unitary(16, eps=0.05)),
        ("gain16", _spread_real(16, 16, scale=2.0)),
    ]


if __name__ == "__main__":  # pragma: no cover
    import tempfile

    nname, layers = demo_network()
    rep = compile_network(layers, name=nname)
    print("=" * 72)
    print(f"U5 编译器前端 demo · {rep['name']} · {rep['n_layers']} 层")
    print("=" * 72)
    for lr in rep["layers"]:
        emb = lr["embedding"]
        print(f"  [{lr['name']:>9}] N={lr['N']:>3}  补全={emb['added']:>2}({emb['direction']})  "
              f"酉={lr['exact_unitary']}  n_mzi={lr['n_mzi']:>4}  "
              f"fid_target={lr['fidelity_vs_target']:.12f}  "
              f"rel_resid={lr['nearest_unitary_info']['residual_relative']:.6e}  "
              f"端口块误差={emb['embedding_residual_max']:.2e}")
    print(f"  合计：MZI {rep['n_mzi_total']} · 驱动器 {rep['n_driver_total']} · "
          f"非酉层 {rep['n_nonunitary_layers']} · "
          f"最小目标保真度 {rep['min_fidelity_vs_target']:.12f} · "
          f"最大相对残余 {rep['max_relative_residual']:.6e}")

    nname2, layers2 = demo_nonunitary_network()
    rep2 = compile_network(layers2, name=nname2)
    print("-" * 72)
    for lr in rep2["layers"]:
        cl = lr["clamp"]
        ui = lr["nearest_unitary_info"]
        print(f"  [{lr['name']:>14}] σ_max={lr['unitarity']['sigma_max']:.6f}  "
              f"夹持={cl['n_truncated']}  β_atten={cl['attenuation_beta']:.6f}  "
              f"β_opt={ui['beta_opt']:.6f}  rel_resid={ui['residual_relative']:.4e}  "
              f"res@opt={ui['residual_at_opt_relative']:.4e}")

    with tempfile.TemporaryDirectory() as td:
        p1 = write_drive_manifest_csv(rep["layers"][0], os.path.join(td, "L0.csv"))
        p2 = write_network_drive_manifest_csv(rep, os.path.join(td, "net.csv"))
        print("-" * 72)
        print("CSV 落盘：", os.path.basename(p1), os.path.basename(p2))
        with open(p2, encoding="utf-8") as f:
            head = [next(f).rstrip("\n") for _ in range(3)]
        for h in head:
            print("  " + h)
