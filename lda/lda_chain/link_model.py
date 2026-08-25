"""LDA L0/L1 · 通用链路模型（LinkModel）—— IR 在链路/系统级场景的便捷门面。

P1-M1（芯片级补强）引入。LDA 原有 IRModel 已支持 `components` + `nets`
（net 为多端口星型连接），但各子系统（wdm_system 等）把它当专用脚本用，
缺少「任意器件实例 + 任意互连」的通用链路抽象与级联仿真引擎。

LinkModel 是 IRModel 的轻量门面（facade）：
  - 不重复造 IR（复用 IRModel / Component / Port / Net / validate）；
  - 提供链路场景的便捷 API（add_device / connect / mark_source）；
  - 内部持有 IRModel，to_ir() 输出标准 IR，落库 / 经 L1 MCP 传输 / 复用
    validate 零成本；
  - 拓扑分析（内部连接 vs 外部 IO 端口），供 lda_chain.engine 级联仿真消费。

主权策略：C 级自写零依赖（仅标准库 + lda_ir）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from lda_ir import IRModel
from lda_ir.core import Component, Port


# 常见光子器件默认端口（与 lda_ir.photon 工厂约定一致，便于零样板构造）
_DEFAULT_PORTS = {
    "RingResonator": ["in", "out", "drop"],
    "Waveguide": ["in", "out"],
    "GratingCoupler": ["fib", "wg"],
    "Splitter": ["in", "out1", "out2"],
    "DirectionalCoupler": ["in1", "in2", "out1", "out2"],
    "SymmetricYBranch": ["in", "out1", "out2"],
}


class LinkModel:
    """通用链路/系统级 IR 门面（facade over IRModel）。

    一个 LinkModel 描述：若干器件实例（instances）+ 它们之间的互连（nets）
    + 外部 IO 端口（source/sink）+ 可选 link 级共享参数（如 bus gap）。
    """

    def __init__(self, domain: str = "photon", name: str = "",
                 notes: str = "") -> None:
        self.ir = IRModel(domain=domain, name=name, notes=notes)
        self._sources: List[Tuple[str, str]] = []
        self.link_params: Dict[str, Any] = {}

    # —— 便捷构造 ——
    def add_device(self, id: str, kind: str,
                   params: Optional[Dict[str, float]] = None,
                   ports: Optional[List[str]] = None) -> "LinkModel":
        """加入一个器件实例；ports 省略时按 kind 取默认端口。"""
        if ports is None:
            ports = list(_DEFAULT_PORTS.get(kind, ["in", "out"]))
        comp = Component(id=id, kind=kind,
                         params=dict(params or {}),
                         ports=[Port(p) for p in ports])
        self.ir.add(comp)
        return self

    def connect(self, net_id: str, src_inst: str, src_port: str,
                dst_inst: str, dst_port: str) -> "LinkModel":
        """声明一条内部互连（点对点 bus/波导）。"""
        self.ir.connect(net_id, f"{src_inst}.{src_port}",
                        f"{dst_inst}.{dst_port}")
        return self

    def external_io(self, net_id: str, inst: str, port: str) -> "LinkModel":
        """声明一个外部 IO 端口（单端口 net，悬挂，不连内部器件）。"""
        self.ir.connect(net_id, f"{inst}.{port}")
        return self

    def mark_source(self, inst: str, port: str, net_id: str = None) -> "LinkModel":
        """声明链路输入源（同时也是 external IO 端口）。"""
        nid = net_id or f"src_{inst}_{port}"
        self.external_io(nid, inst, port)
        if (inst, port) not in self._sources:
            self._sources.append((inst, port))
        return self

    def set_link_param(self, key: str, value: Any) -> "LinkModel":
        """设置 link 级共享参数（如 bus gap），供器件传递模型消费。"""
        self.link_params[key] = value
        return self

    # —— 标准 IR 出口 ——
    def to_ir(self) -> IRModel:
        return self.ir

    def validate(self) -> List[str]:
        from lda_ir import validate
        return validate(self.ir)

    # —— 拓扑分析（供 engine 消费）——
    def topology(self) -> Dict[str, Any]:
        """返回内部连接（多端口 net 的端口组）与外部 IO 端口（单端口 net）。

        内部连接：net.connects 含 ≥2 个 "inst.port" → 这些端口理想互连（透射 1）。
        外部 IO：net.connects 仅含 1 个 "inst.port" → 悬挂端口，链路对外接口。
        """
        internal: List[List[Tuple[str, str]]] = []
        external: List[Tuple[str, str, str]] = []
        for net in self.ir.nets:
            ports = [tuple(c.split(".", 1)) for c in net.connects if "." in c]
            if len(ports) >= 2:
                internal.append(ports)
            elif len(ports) == 1:
                external.append((ports[0][0], ports[0][1], net.id))
        return {"internal": internal, "external": external}

    @property
    def sources(self) -> List[Tuple[str, str]]:
        return list(self._sources)
