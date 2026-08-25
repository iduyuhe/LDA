"""LDA L1 · 通用光子链路仿真引擎（信号流图级联）。

P1-M1 核心。消费 LinkModel（→ IRModel），对任意「器件实例 + 互连」拓扑做
**通用级联仿真**：

  算法：无源线性网络 → 把每个器件按其端口传递矩阵（来自 registry）作为
  「器件内边」，把 netlist 内部连接作为「理想连接边（透射 1）」，构成信号
  流图；对每个输入源，DFS 累积所有无环路径的 per-wavelength 传递乘积。

  为什么能复刻 wdm_system：WDM 多环级联本质是「前馈链」——信号沿 bus 串，
  每个 ring 在 drop 泄出、thru 续传。信号流图 DFS 对 (ring0.in → ring_i.drop)
  的唯一路径增益 = T_drop(ring_i)·Π_{j<i} T_thru(ring_j)，与 system_metrics
  的级联公式逐波长一致（同一 adddrop_spectrum 模型）。

  诚实边界：
  - 无环假设（前馈链/树）。检测到反馈环时跳过该环路径并标注（MVP 不覆盖
    反馈拓扑，待 M2+ 扩展 Mason 公式全求解）；
  - 未知 kind / 缺模型 → 不参与级联，列于 missing_models；
  - FDTD 钩子预留（关键节点标定），默认解析优先。

输出：{wavelengths_um, transfers{ "src->sink": spectrum }, io_ports, sources,
       sinks, missing_models, note}
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple

from .link_model import LinkModel
from .registry import get_response


def _propagate(src: Tuple[str, str], sinks, wls: List[float],
               internal_map: Dict[Tuple[str, str], list],
               responses: Dict[str, Dict[Tuple[str, str], List[float]]]
               ) -> Dict[Tuple[str, str], List[float]]:
    """从 src 出发 DFS 累积所有路径到各 sink 的 per-wavelength 传递。"""
    n = len(wls)
    collected: Dict[Tuple[str, str], List[List[float]]] = defaultdict(list)

    def dfs(node: Tuple[str, str], gain: List[float], seen: frozenset) -> None:
        if node != src and node in sinks:
            collected[node].append(gain)
        if node in seen:
            return
        seen = seen | {node}
        # 1) 内部连接边（带 net 损耗增益 g，默认透射 1）
        for other, g in internal_map.get(node, []):
            dfs(other, [gain[i] * g for i in range(n)], seen)
        # 2) 器件内边（端口传递）
        inst = node[0]
        resp = responses.get(inst)
        if resp:
            p_in = node[1]
            for (p_out, p_in_key), spec in resp.items():
                if p_in_key == p_in:
                    new_gain = [gain[i] * spec[i] for i in range(n)]
                    dfs((inst, p_out), new_gain, seen)

    dfs(src, [1.0] * n, frozenset())

    out: Dict[Tuple[str, str], List[float]] = {}
    for sink, gains in collected.items():
        vec = [0.0] * n
        for g in gains:
            for i in range(n):
                vec[i] += g[i]
        out[sink] = vec
    return out


def simulate(link: LinkModel, wavelengths_um: List[float],
             kappa_fn: Optional[Callable] = None,
             link_params: Optional[Dict] = None,
             fdtd_hook: Optional[Callable] = None,
             net_loss_db: Optional[Dict[str, float]] = None,
             sources: Optional[List[Tuple[str, str]]] = None
             ) -> Dict[str, Any]:
    """通用链路级联仿真。

    参数：
      link           ：LinkModel（含 instances/nets/IO）
      wavelengths_um ：波长列表（µm）
      kappa_fn       ：可选 gap→κ 覆盖（缺省 registry 内 gap_to_kappa）
      link_params    ：link 级共享参数（缺省用 link.link_params）
      fdtd_hook      ：可选 FDTD 标定钩子（预留，默认解析优先）
      sources        ：输入源列表 [(inst,port)]；缺省用 link.sources，
                       仍空则把所有外部 IO 当源（并标注）

    返回 transfers：{"ring0.in->ring0.drop": [spectrum...], ...}
    """
    lp = link_params if link_params is not None else link.link_params
    topo = link.topology()

    # 内部连接映射：node -> [(互连节点, 增益)]；增益来自 net 损耗（默认透射 1）
    net_loss = net_loss_db or {}
    internal_map: Dict[Tuple[str, str], list] = {}
    for net in link.ir.nets:
        ports = [tuple(c.split(".", 1)) for c in net.connects if "." in c]
        if len(ports) >= 2:
            g = 10.0 ** (-net_loss.get(net.id, 0.0) / 10.0)
            for a in ports:
                internal_map.setdefault(a, [])
                for b in ports:
                    if b != a:
                        internal_map[a].append((b, g))

    ext_nodes = [(i, p) for (i, p, _) in topo["external"]]
    ext_set = set(ext_nodes)

    # 器件响应矩阵
    responses: Dict[str, Dict[Tuple[str, str], List[float]]] = {}
    missing: List[str] = []
    for comp in link.ir.components:
        r = get_response(comp.kind, comp, wavelengths_um, lp, kappa_fn,
                         fdtd_hook)
        if r is None:
            missing.append(comp.id)
        else:
            responses[comp.id] = r

    # 输入源
    if sources is None:
        sources = link.sources if link.sources else ext_nodes
        auto_sources = link.sources == []
    else:
        auto_sources = False

    transfers: Dict[str, List[float]] = {}
    for src in sources:
        if src not in ext_set:
            continue  # 源必须是外部 IO 端口
        res = _propagate(src, ext_set, wavelengths_um, internal_map, responses)
        for sink, vec in res.items():
            if sink == src:
                continue
            key = f"{src[0]}.{src[1]}->{sink[0]}.{sink[1]}"
            transfers[key] = vec

    return {
        "wavelengths_um": list(wavelengths_um),
        "transfers": transfers,
        "io_ports": [f"{i}.{p}" for (i, p) in ext_nodes],
        "sources": [f"{i}.{p}" for (i, p) in sources],
        "sinks": [f"{i}.{p}" for (i, p) in ext_nodes if (i, p) not in set(sources)],
        "missing_models": missing,
        "auto_sources": auto_sources,
        "note": ("通用信号流图级联（无源线性网络，无环假设）；FDTD 钩子预留未启用；"
                 + (f" net 损耗已注入：{net_loss}" if net_loss
                    else " net 损耗未注入（理想互连）。")
                 + (f" 缺模型器件：{missing}" if missing else "")),
    }
