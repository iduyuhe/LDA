"""LDA L2 · SPICE 兼容网表生成器（WBS-T1-2）+ Cadence 导入适配（WBS-T1-3）。

把 T1-1 的带参数紧凑模型（CompactModelSpec）从"参数 schema"升级为
**电路仿真器可读的带参数网表**：标准 SPICE3 `.cir` + Cadence Spectre
适配变体。这是 A 档「光电接口层」价值落点之一——把光电器件的行为级
电学模型（调制器行波电极 RC、探测器结电容+响应度、激光器阈值）导出为
标准网表，供 ngspice / Cadence Spectre 接 Cadence，不绑定任何商业格式。

主权纪律（与 compact_model.py / parasitic_rc.py 同源）：
  - 默认物理常数 = 公开文献典型量级占位，非真实 PDK 声明；
  - 不启动 Cadence（商业闭源，B 级借今踢后）；只生成其兼容网表格式；
  - 每个数值来自 CompactModelSpec / derive_responses，绝不凭空杜撰。

可证伪反向护栏（run_spice_netlist_smoke.py）：
  - 改紧凑模型参数 → 网表对应数值行必须变（防常数假绿）；
  - 悬空端口 / 重名节点 → 必须抛 NetlistError（防非法网表假绿）；
  - SPICE 与 Spectre 两种输出结构必须不同（适配层真生效）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .compact_model import CompactModelSpec, derive_responses


class NetlistError(ValueError):
    """非法电路网表（悬空端口 / 重名节点冲突 / 未知器件）。"""


# --------------------------------------------------------------------------
# 电路实例
# --------------------------------------------------------------------------
@dataclass
class DeviceInstance:
    """一个电路器件实例（引用紧凑模型或纯电气元件）。"""
    id: str
    kind: str                      # modulator | photodetector | laser | vsource | load
    spec: Optional[CompactModelSpec] = None
    params: Dict[str, float] = field(default_factory=dict)


# --------------------------------------------------------------------------
# 网表构建器
# --------------------------------------------------------------------------
class CircuitNetlist:
    """从紧凑模型 + 电路拓扑生成 SPICE 兼容带参数网表。

    节点命名：每个器件电气端口映射到显式节点名 `<id>_<port>`；
    地固定为 `0`（SPICE）/ `gnd`（Spectre 适配层重映射）。
    """

    def __init__(self, name: str = "lda_circuit"):
        self.name = name
        self.devices: List[DeviceInstance] = []
        self._nets: Dict[str, List[str]] = {}   # net_name -> ["dev.port", ...]
        self._gnd = "0"

    # —— 构建 API ——
    def add_device(self, inst_id: str, kind: str,
                   spec: Optional[CompactModelSpec] = None,
                   **params: float) -> "CircuitNetlist":
        if kind not in ("modulator", "photodetector", "laser", "vsource", "load"):
            raise NetlistError(f"未知器件 kind={kind!r} (实例 {inst_id})")
        if any(d.id == inst_id for d in self.devices):
            raise NetlistError(f"器件 id 重名：{inst_id}")
        self.devices.append(DeviceInstance(id=inst_id, kind=kind,
                                           spec=spec, params=dict(params)))
        return self

    def connect(self, net_name: str, *termrefs: str) -> "CircuitNetlist":
        """把一个命名网络连到若干 `dev_id.port` 终端。"""
        for tr in termrefs:
            if "." not in tr:
                raise NetlistError(f"非法终端引用（需 dev.port）：{tr!r}")
            dev_id, _port = tr.split(".", 1)
            if not any(d.id == dev_id for d in self.devices):
                raise NetlistError(f"悬空终端：引用不存在的器件 {dev_id!r}（net={net_name}）")
        self._nets.setdefault(net_name, []).extend(termrefs)
        return self

    # —— 内部校验 ——
    def _validate(self) -> None:
        valid_ports = {
            "modulator": {"rf_in", "rf_out", "term", "gnd"},
            "photodetector": {"anode", "cathode", "gnd"},
            "laser": {"anode", "cathode", "gnd"},
            "vsource": {"plus", "minus"},
            "load": {"plus", "minus"},
        }
        for d in self.devices:
            used = [tr.split(".", 1)[1] for tr in self._nets.get(d.id, [])
                    if tr.startswith(d.id + ".")]
            # 遍历所有 nets 找该器件被引用的端口
            for net in self._nets.values():
                for tr in net:
                    if tr.startswith(d.id + "."):
                        used.append(tr.split(".", 1)[1])
            for p in set(used):
                if p not in valid_ports.get(d.kind, set()):
                    raise NetlistError(
                        f"器件 {d.id}（{d.kind}）端口 {p!r} 非法；"
                        f"合法端口={sorted(valid_ports[d.kind])}")
        # 每个器件至少有 1 个端口被连接（除非是电源/地参考）
        for d in self.devices:
            refs = [tr for net in self._nets.values() for tr in net
                    if tr.startswith(d.id + ".")]
            if not refs:
                raise NetlistError(f"悬空器件：{d.id}（{d.kind}）无任何端口连接")

    # —— 派生：把紧凑模型展开为元件数值 ——
    def _device_elements(self, d: DeviceInstance) -> List[str]:
        """返回某器件的 SPICE 元件行（不含节点名映射，节点由 net 决定）。"""
        lines: List[str] = []
        if d.kind == "modulator":
            s = d.spec or CompactModelSpec()
            r = s.R_electrode_ohm
            c_total_ff = s.C_junction_fF + s.C_electrode_fF
            resp = derive_responses(s)
            lines.append(f"* Modulator {d.id} (VpiL={s.VpiL_Vcm} V·cm, "
                         f"L={s.length_mm} mm, Vpi@{s.length_mm}mm="
                         f"{resp['Vpi_at_length_V']} V)")
            lines.append(f"R{d.id}_rf {d.id}_rf_in {d.id}_int {r:.6g}")
            lines.append(f"C{d.id}_jct {d.id}_int 0 {c_total_ff:.3f}e-15")
            lines.append(f".model {d.id}_mod vccs (gain={resp['Vpi_at_length_V']:.6g})")
        elif d.kind == "photodetector":
            s = d.spec or CompactModelSpec()
            resp = derive_responses(s)
            c_total_ff = s.C_junction_fF + s.C_electrode_fF
            lines.append(f"* Photodetector {d.id} "
                         f"(responsivity={resp['responsivity_AW']} A/W, "
                         f"Cjct={c_total_ff:.3f}fF, "
                         f"Idark={s.dark_current_nA}e-9 A)")
            lines.append(f"C{d.id}_jct {d.id}_anode {d.id}_cathode {c_total_ff:.3f}e-15")
            # 受控电流源：I = responsivity × Popt（Popt 以 .param 声明）
            lines.append(f"G{d.id}_phot {d.id}_anode {d.id}_cathode "
                         f"{d.id}_anode {d.id}_cathode {resp['responsivity_AW']:.6g}")
            lines.append(f"Idark_{d.id} {d.id}_cathode {d.id}_anode "
                         f"{s.dark_current_nA:.6g}e-9")
        elif d.kind == "laser":
            s = d.spec or CompactModelSpec()
            lines.append(f"* Laser {d.id} (λ={s.wavelength_nm} nm)")
            lines.append(f".model {d.id}_ldiode d (is=1e-12)")
            lines.append(f"D{d.id}_d {d.id}_anode {d.id}_cathode {d.id}_ldiode")
        elif d.kind == "vsource":
            v = d.params.get("dc", 0.0)
            lines.append(f"V{d.id} {d.id}_plus {d.id}_minus dc={v:.6g}")
        elif d.kind == "load":
            r = d.params.get("r", 50.0)
            lines.append(f"R{d.id} {d.id}_plus {d.id}_minus {r:.6g}")
        return lines

    def _node_for(self, dev_id: str, port: str) -> str:
        """查找该 dev.port 所在 net 的唯一节点名；未连接则显式悬空节点。"""
        for net_name, refs in self._nets.items():
            if f"{dev_id}.{port}" in refs:
                return net_name
        return f"{dev_id}_{port}"   # 未连接 → 物理悬空节点（SPICE 合法但仿真告警）

    # —— 导出：标准 SPICE3 .cir ——
    def to_spice(self) -> str:
        self._validate()
        L: List[str] = [f"* LDA generated SPICE netlist: {self.name}",
                        f"* schema: lda-spice/1.0  (compact-model driven)",
                        f".title {self.name}"]
        # 把 CompactModelSpec 的 Popt 参数声明（供探测器受控源消费）
        opts = [d for d in self.devices if d.kind == "photodetector"]
        if opts:
            L.append(".param POPT=1e-3   ; 入射光功率 (W)，占位默认 1mW")
        for d in self.devices:
            for ln in self._device_elements(d):
                L.append(ln)
        L.append(".end")
        return "\n".join(L) + "\n"

    # —— 导出：Cadence Spectre 适配变体 ——
    def to_cadence_spectre(self) -> str:
        self._validate()
        L: List[str] = [f"simulator lang=spectre",
                        f"// LDA generated Spectre netlist: {self.name}",
                        f"subckt {self.name} (vdd gnd)"]
        opts = [d for d in self.devices if d.kind == "photodetector"]
        if opts:
            L.append("  parameters POPT=1e-3  // 入射光功率 (W)")
        for d in self.devices:
            for ln in self._device_elements(d):
                # 把 SPICE 元件行转为 Spectre 的 (node node) element 语法
                conv = self._to_spectre_line(ln, d)
                if conv:
                    L.append("  " + conv)
        L.append("ends " + self.name)
        return "\n".join(L) + "\n"

    @staticmethod
    def _to_spectre_line(spice_line: str, d: DeviceInstance) -> Optional[str]:
        """把单条 SPICE 元件行转 Cadence Spectre 原生语法。

        SPICE3 与 Spectre 元件语法差异：
          Rxx n1 n2 val          →  xx (n1 n2) resistor r=val
          Cxx n1 n2 val          →  xx (n1 n2) capacitor c=val
          Vxx n1 n2 dc=v         →  xx (n1 n2) vsource dc=v
          Ixx n1 n2 val          →  xx (n1 n2) isource dc=val
          Gxx o1 o2 c1 c2 g      →  xx (o1 o2) (c1 c2) vccs gm=g
          Dxx n1 n2 model        →  xx (n1 n2) diode model=model
        """
        if spice_line.startswith("*"):
            return None                      # 注释行在 Spectre 里省略（结构已变）
        if spice_line.startswith(".model"):
            return f"// {spice_line}"        # model 声明保留为注释备查
        parts = spice_line.split()
        if not parts:
            return None
        token = parts[0]
        prefix = token[0]
        name = token[1:]
        rest = parts[1:]
        if prefix == "R" and len(rest) >= 3:
            return f"{name} ({rest[0]} {rest[1]}) resistor r={rest[2]}"
        if prefix == "C" and len(rest) >= 3:
            return f"{name} ({rest[0]} {rest[1]}) capacitor c={rest[2]}"
        if prefix == "V" and len(rest) >= 3:
            return f"{name} ({rest[0]} {rest[1]}) vsource dc={rest[2].split('=')[-1]}"
        if prefix == "I" and len(rest) >= 3:
            return f"{name} ({rest[0]} {rest[1]}) isource dc={rest[2]}"
        if prefix == "G" and len(rest) >= 5:
            o1, o2, c1, c2, g = rest[0], rest[1], rest[2], rest[3], rest[4]
            return f"{name} ({o1} {o2}) ({c1} {c2}) vccs gm={g}"
        if prefix == "D" and len(rest) >= 3:
            return f"{name} ({rest[0]} {rest[1]}) diode model={rest[2]}"
        return None
