"""LDA ecore · 电子版图层栈与设计规则（E6 · D-156）。

电子计算征程（吃狗粮第三征程）的**几何层栈 + 规则单一真源**——对齐光子侧
`lda_l2/layers.py`（`LayerStack` / `via_map` / `can_cross`）与超导侧
`gds_export` 的 SC 层常量（10–14）。

为什么必须单独有一份（E6 逼出的平台接缝）：
  平台此前只有**光子工艺栈**（SOI：M1 波导 / VIA12 / M2 金属）与**超导栈**
  （Al：M1 / VIA1 / M2）——半导体**前道**（有源区 / 多晶硅栅 / 接触孔）在平台
  里**完全没有表示**。电子芯片的几何签核若借用光子栈，会出现两类错误：
  ①「多晶硅栅」被当成「金属波导」（层语义错，LVS 短路判定失效）；
  ② 接触孔 / 通孔这类**唯一合法跨层桥**没有类型，跨层短路判不出来。

层语义（CMOS 前后道混合工艺的**公开近似**，非 Foundry PDK）：
  - `active` 有源区（DIFF：源/漏/沟道，导电但由栅调制）；
  - `gate`   多晶硅栅（POLY：跨在沟道上，栅极电位 = 权重）；
  - `contact` 接触孔（CONT：**唯一合法桥接 active ↔ M1**）；
  - `signal` 金属布线（M1 行线/权重线 · M2 列线，同层相交 = 短路）；
  - `via`    通孔（VIA1：**唯一合法桥接 M1 ↔ M2**）；
  - `pad`    焊盘 / 钝化开口（对外接入，不参与内部连通性）。

`ELayerStack.can_short(l1, l2)` 是几何 LVS 短路判定的核心谓词：
**同层 signal 相交 = 短路；异层经介质隔离 = 不短路**（跨层投影重叠不算短）。
`ELayerStack.is_bridge(layer)` 判定该层是否为跨层桥（contact / via）。

🔴 诚实边界：层序、层号与规则值均为**公开工艺近似的设计规则**（可覆盖 · 非实测
golden），Foundry PDK 的层规/金属栈属 D5 外部依赖，平台不沾。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from lda_l2 import gds_export as G

# ── 电子层 GDS 层号（单一真源 = gds_export）──────────────────────────────
L_DIFF = G.LIB_LAYER_E_DIFF      # 20
L_POLY = G.LIB_LAYER_E_POLY      # 21
L_CONT = G.LIB_LAYER_E_CONT      # 22
L_M1 = G.LIB_LAYER_E_M1          # 23
L_VIA1 = G.LIB_LAYER_E_VIA1      # 24
L_M2 = G.LIB_LAYER_E_M2          # 25
L_PAD = G.LIB_LAYER_E_PAD        # 26

_LAYER_KIND: Dict[int, str] = {
    L_DIFF: "active",
    L_POLY: "gate",
    L_CONT: "contact",
    L_M1: "signal",
    L_VIA1: "via",
    L_M2: "signal",
    L_PAD: "pad",
}


@dataclass
class ELayer:
    """单个电子版图层。kind ∈ active/gate/contact/signal/via/pad。"""
    name: str
    kind: str
    gds_layer: int
    z_bot_um: float = 0.0
    z_top_um: float = 0.0


@dataclass
class ELayerStack:
    """电子版图层栈：前后道层 + 跨层桥映射。

    `via_map`: 桥层名 -> **允许的 (下层, 上层) 对列表**。真实 CMOS 里 CONT 是同一种
    接触孔层，**同时**桥 active↔M1 与 gate↔M1；VIA1 桥 M1↔M2。故而非单一对，而是集合。
    """
    name: str
    layers: Dict[str, ELayer] = field(default_factory=dict)
    via_map: Dict[str, List[Tuple[str, str]]] = field(default_factory=dict)

    def signal_layers(self) -> List[str]:
        """信号（金属布线）层名，按 z 升序。"""
        sig = [n for n, l in self.layers.items() if l.kind == "signal"]
        return sorted(sig, key=lambda n: self.layers[n].z_top_um)

    def bridge_layers(self) -> List[str]:
        """跨层桥层名（contact / via）。"""
        return [n for n, l in self.layers.items() if l.kind in ("contact", "via")]

    def kind_of(self, name: str) -> str:
        return self.layers[name].kind if name in self.layers else "unknown"

    def order(self) -> List[str]:
        """层名按 z_bot 升序（工艺层序）。"""
        return sorted(self.layers, key=lambda n: self.layers[n].z_bot_um)

    def pos_of(self, name: str) -> int:
        """层在工艺层序中的位置（用于「桥须跨下层→上层」判定）；未知层返回 -1。"""
        return self.order().index(name) if name in self.layers else -1

    def can_short(self, l1: str, l2: str) -> bool:
        """两信号层是否可能短路：**同层 signal 层 True；异层介质隔离 False**。

        跨层投影重叠（M1 与 M2 垂直交叠）**不判短**（介质隔离，物理正确），
        只有经 contact/via 才允许跨层电气连接 —— 这是多层几何 LVS 的核心谓词。
        未知层名按「同名才判短」保守处理。
        """
        if l1 not in self.layers or l2 not in self.layers:
            return l1 == l2
        if l1 == l2:
            return self.layers[l1].kind == "signal"
        return False

    def is_bridge(self, name: str) -> bool:
        """该层是否为跨层桥（contact / via）。"""
        return self.kind_of(name) in ("contact", "via")

    def bridge_connects(self, bridge: str, l1: str, l2: str) -> bool:
        """该桥层是否允许连接 l1 ↔ l2 两层（无序）。"""
        for a, b in self.via_map.get(bridge, []):
            if {a, b} == {l1, l2}:
                return True
        return False

    def to_summary(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "signal_layers": self.signal_layers(),
            "bridge_layers": self.bridge_layers(),
            "via_map": {k: [list(p) for p in v] for k, v in self.via_map.items()},
            "gds_layers": {n: l.gds_layer for n, l in self.layers.items()},
        }


# ---------------------------------------------------------------------------
# 默认电子栈：前后道混合（DIFF / POLY / CONT / M1 / VIA1 / M2）——公开近似
# ---------------------------------------------------------------------------
DEFAULT_CMOS_STACK = ELayerStack(
    name="E-CMOS-6L（公开近似）",
    layers={
        "DIFF": ELayer("DIFF", "active", L_DIFF, z_bot_um=0.00, z_top_um=0.10),
        "POLY": ELayer("POLY", "gate", L_POLY, z_bot_um=0.10, z_top_um=0.25),
        "CONT": ELayer("CONT", "contact", L_CONT, z_bot_um=0.25, z_top_um=0.45),
        "M1": ELayer("M1", "signal", L_M1, z_bot_um=0.45, z_top_um=0.75),
        "VIA1": ELayer("VIA1", "via", L_VIA1, z_bot_um=0.75, z_top_um=0.95),
        "M2": ELayer("M2", "signal", L_M2, z_bot_um=0.95, z_top_um=1.35),
    },
    via_map={"CONT": [("DIFF", "M1"), ("POLY", "M1")], "VIA1": [("M1", "M2")]},
)

ESTACK_REGISTRY: Dict[str, ELayerStack] = {"ecmos": DEFAULT_CMOS_STACK}


def get_estack(name: str = "ecmos") -> ELayerStack:
    """取电子层栈（缺省 E-CMOS-6L）。"""
    return ESTACK_REGISTRY.get(name, DEFAULT_CMOS_STACK)


# ---------------------------------------------------------------------------
# 电子设计规则（公开工艺近似 · 可覆盖 · **非实测 golden**）
# ---------------------------------------------------------------------------
ELEC_DESIGN_RULES: Dict[str, float] = {
    # 有源区
    "diff_min_width_um": 0.30,
    "diff_min_space_um": 0.20,
    "diff_min_area_um2": 0.20,
    "diff_poly_overhang_um": 0.10,     # 栅须在沟道两侧各外延（防边缘漏电）
    # 多晶硅栅
    "poly_min_width_um": 0.18,         # 栅长下限
    "poly_min_space_um": 0.20,
    # 接触孔
    "cont_size_um": 0.20,
    "cont_min_space_um": 0.20,
    "cont_enclosure_um": 0.10,         # CONT 须被 DIFF 与 M1 各包围 ≥ 此值
    # 金属
    "m1_min_width_um": 0.23,
    "m1_min_space_um": 0.23,
    "m2_min_width_um": 0.28,
    "m2_min_space_um": 0.28,
    # 通孔
    "via1_size_um": 0.20,
    "via1_enclosure_um": 0.10,
}

ELEC_DISCLOSURE = {
    "role": "E6 = 电子版图层栈 + 几何签核（DRC/LVS）· 让电子计算芯片能出真 GDS",
    "layers": "DIFF=20 / POLY=21 / CONT=22 / M1=23 / VIA1=24 / M2=25 / PAD=26"
              "（gds_export 定义，**非 Foundry PDK**）",
    "rules": "ELEC_DESIGN_RULES 为**公开工艺近似的设计规则 · 可覆盖 · 非实测 golden**"
             "（Foundry PDK 层规/金属栈属 D5 外部依赖）",
    "lvs": "几何 LVS：对**实际产出几何**做 bbox 重叠网表提取（不重放设计意图）",
    "position": "本栈是电子征程（E6+）的**层栈单一真源**；光子 SOI 栈见 lda_l2/layers.py，"
                "超导 Al 栈见 gds_export 的 SC 层常量",
    "red_line": "纯几何（标准库即可，零 numpy 也够）、LLM 不进判决路径、零商业 EDA 依赖",
}


# ---------------------------------------------------------------------------
# 自检（常驻断言：层序 / 桥映射 / 短路谓词）
# ---------------------------------------------------------------------------
def run_selfcheck(verbose: bool = False) -> bool:
    st = DEFAULT_CMOS_STACK
    msgs: List[Tuple[str, bool]] = []

    def chk(name: str, cond) -> bool:
        msgs.append((name, bool(cond)))
        return bool(cond)

    ok = True
    ok &= chk("① 信号层 = [M1, M2]（按 z 升序）", st.signal_layers() == ["M1", "M2"])
    ok &= chk("② 桥层 = [CONT, VIA1]",
              sorted(st.bridge_layers()) == ["CONT", "VIA1"])
    ok &= chk("③ CONT 桥 DIFF↔M1 与 POLY↔M1（多对）",
              st.bridge_connects("CONT", "DIFF", "M1")
              and st.bridge_connects("CONT", "POLY", "M1"))
    ok &= chk("④ VIA1 桥 M1↔M2", st.bridge_connects("VIA1", "M1", "M2"))
    ok &= chk("⑤ 同层 M1 相交判短", st.can_short("M1", "M1") is True)
    ok &= chk("⑥ 异层 M1/M2 垂直重叠**不**判短（介质隔离）",
              st.can_short("M1", "M2") is False)
    ok &= chk("⑦ POLY 非 signal ⇒ 同层不相交判短",
              st.can_short("POLY", "POLY") is False)
    ok &= chk("⑧ CONT/VIA1 是桥、DIFF/M1 不是",
              st.is_bridge("CONT") and st.is_bridge("VIA1")
              and not st.is_bridge("DIFF") and not st.is_bridge("M1"))
    ok &= chk("⑨ 层号 = 20..25 连续（DIFF..M2）",
              [st.layers[n].gds_layer for n in
               ("DIFF", "POLY", "CONT", "M1", "VIA1", "M2")] == [20, 21, 22, 23, 24, 25])
    ok &= chk("⑩ 设计规则齐备（≥14 项）", len(ELEC_DESIGN_RULES) >= 14)

    if verbose:
        for n, c in msgs:
            print(f"  [{'PASS' if c else 'FAIL'}] {n}")
    return bool(ok)
