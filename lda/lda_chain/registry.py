"""LDA L1/L2 · 器件传递模型注册表（device response registry）。

P1-M1 通用链路仿真引擎的「物理后端」：**每个器件 kind 提供一个传递模型**
`response(wavelengths_um) -> {(out_port, in_port): spectrum}`，
spectrum 为与 wavelengths 等长的标量 list（场/功率传递，按波长采样）。

  设计原则：
  - 零依赖（标准库 + 现有 lda_agent 解析模型）；C 级自写，不引入外部 EDA；
  - 注册表模式：新器件 kind 只需 register_device_model 即可接入级联引擎；
  - FDTD 钩子优先：若 fdtd_hook 提供且返回非 None，用它替换解析响应
    （M1 预留「关键节点 FDTD 标定」接入点，默认不启用）；
  - 诚实边界：未知 kind / 缺参数 → 返回 None（不参与级联，引擎报 missing）。

对应方案决策：链路仿真「混合（解析 + 关键节点 FDTD）」—— 此处解析模型
为默认后端，FDTD 钩子为后续关键节点标定入口。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

# kind -> response 函数
_RESPONSE_MODELS: Dict[str, Callable] = {}


def register_device_model(kind: str,
                          fn: Callable[[Any, List[float], Optional[Dict],
                                         Optional[Callable]], Optional[Dict]],
                          ) -> None:
    """注册一个器件 kind 的传递模型。

    fn(component, wavelengths_um, link_params, kappa_fn)
        -> {(out_port, in_port): spectrum_list} | None
    """
    _RESPONSE_MODELS[kind] = fn


def get_response(kind: str, component: Any, wavelengths_um: List[float],
                 link_params: Optional[Dict] = None,
                 kappa_fn: Optional[Callable] = None,
                 fdtd_hook: Optional[Callable] = None
                 ) -> Optional[Dict[Tuple[str, str], List[float]]]:
    """取得某器件的端口传递矩阵；FDTD 钩子优先，否则解析注册表。"""
    if fdtd_hook is not None:
        r = fdtd_hook(component, wavelengths_um)
        if r is not None:
            return r
    fn = _RESPONSE_MODELS.get(kind)
    if fn is None:
        return None
    return fn(component, wavelengths_um, link_params, kappa_fn)


# ---------------------------------------------------------------------------
# 内置解析模型（光子子集）
# ---------------------------------------------------------------------------
def _ring_response(component, wls: List[float], link_params, kappa_fn):
    """add-drop 环形：解析耦合模（复用 D-37 ring_adddrop.adddrop_spectrum）。

    端口传递（无源互易）：in→out(=thru)、in→drop，对称。
    gap 取器件 params，缺则取 link_params（WDM bus 共享 gap）。
    """
    from lda_agent.ring_adddrop import (adddrop_spectrum,
                                        bending_loss_db_per_cm, gap_to_kappa)
    R = float(component.params["R"])
    n_g = float(component.params.get("n_g", 4.2))
    gap = (component.params.get("gap")
           if component.params.get("gap") is not None
           else (link_params or {}).get("gap", 0.3))
    kappa = kappa_fn(gap) if kappa_fn else gap_to_kappa(gap)
    alpha_bend = bending_loss_db_per_cm(R)
    sp = adddrop_spectrum(wls, R, n_g, kappa, alpha_bend, 1.55)
    t_thru, t_drop = sp["thru"], sp["drop"]
    return {("out", "in"): t_thru, ("drop", "in"): t_drop}


def _waveguide_response(component, wls: List[float], link_params, kappa_fn):
    """直波导：理想透射 1（损耗可由 L 计入，MVP 理想）。

    仅注册正向边（in→out）：引擎按信号方向单向传播（v0.8.11），
    互易反向边会导致"幽灵反向路径"（信号经器件反向漏入他端口，
    Σ|T|²>1 / C 锚泄漏失真）。互易性由引擎单向 DFS + sink 截断保证。
    """
    ones = [1.0] * len(wls)
    return {("out", "in"): ones}


def _grating_response(component, wls: List[float], link_params, kappa_fn):
    """光栅耦合器：固定耦合效率（缺省 -3dB；可由 params.coupling 覆盖）。"""
    eff = float(component.params.get("coupling", 0.5))
    c = [eff] * len(wls)
    return {("wg", "fib"): c}  # 仅正向 fib→wg（同 v0.8.11 单向传播语义）


def _mzi_response(component, wls: List[float], link_params, kappa_fn):
    """2×2 MZI 交叉开关：理想 50/50 分束 + 两臂相位差 Δφ(λ)=2π·n_eff·ΔL/λ。

    端口传递（无源互易，与 B20 MZI FSR 锚 T=½(1+cosΔφ)=cos²(Δφ/2) 同源）：
        in1→out1（bar）= cos²(Δφ/2)；in1→out2（cross）= sin²(Δφ/2)
        in2 对称；bar+cross = 1（无损，能量守恒诊断理想闭合）。
    参数：n_eff（缺省 2.6）、deltaL_um（缺省 34.5，对应 B20 锚默认 ΔL）。
    """
    import math
    n_eff = float(component.params.get("n_eff", 2.6))
    dL = float(component.params.get("deltaL_um", 34.5))
    bar = []
    cross = []
    for wl in wls:
        dphi = 2.0 * math.pi * n_eff * dL / max(wl, 1e-12)
        c = math.cos(dphi / 2.0)
        s = math.sin(dphi / 2.0)
        bar.append(c * c)
        cross.append(s * s)
    return {
        ("out1", "in1"): bar, ("out2", "in1"): cross,
        ("out2", "in2"): bar, ("out1", "in2"): cross,
    }  # 仅正向边（in→out）；互易反向由引擎单向 DFS 语义保证


register_device_model("RingResonator", _ring_response)
register_device_model("Waveguide", _waveguide_response)
register_device_model("GratingCoupler", _grating_response)
register_device_model("MZI", _mzi_response)
