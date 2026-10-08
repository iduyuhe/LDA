"""L2 开放 PDK / 器件本体 Registry（D-93）。

社区共建的器件本体注册。每条 DeviceEntry 含：
  - id / name / tech / foundry / sovereign_class（A/B/C）
  - layers / params / tags / note

Registry 支持 add / get / query（tech/foundry/class/tag 过滤）/ stats /
to_json / load。与 empirical_bank.EmpiricalCorpus 同构（注册 + 查询 +
溯源），区别在本模块承载「器件本体元数据」而非「实测语料」。

红线：本模块只做「注册 + 查询 + 溯源」，不实际对接晶圆厂 NDA-PDK
（属发动期事项，D-62 联动，暂缓）。真实 PDK 数据经 community/foundry
提交入口（empirical_submit 同源）流入。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class DeviceEntry:
    """一条器件本体注册记录。"""
    id: str
    name: str
    tech: str                     # 工艺：SOI / SiN / InP / Transmon / ...
    foundry: str                  # 来源：NOEIC / CUMEC / SITRI / community / self
    sovereign_class: str          # 主权分级：A / B / C
    layers: List[str] = field(default_factory=list)
    params: Dict = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    note: str = ""

    def validate(self) -> bool:
        if not self.id or not self.name:
            raise ValueError("id/name 必填")
        if self.sovereign_class not in ("A", "B", "C"):
            raise ValueError("sovereign_class 须为 A/B/C")
        return True


class PDKRegistry:
    """开放 PDK / 器件本体 Registry（社区共建地基接口）。"""

    def __init__(self, entries=None):
        self._items: Dict[str, DeviceEntry] = {}
        for e in (entries or []):
            self.add(e)

    def add(self, e: DeviceEntry, overwrite: bool = False) -> str:
        """返回 'added'（新增）/ 'conflict'（id 已存在且未覆盖）。"""
        e.validate()
        if e.id in self._items and not overwrite:
            return "conflict"
        self._items[e.id] = e
        return "added"

    def get(self, did: str) -> Optional[DeviceEntry]:
        return self._items.get(did)

    def query(self, tech=None, foundry=None, sovereign_class=None, tag=None):
        out = []
        for e in self._items.values():
            if tech and e.tech != tech:
                continue
            if foundry and e.foundry.lower() != foundry.lower():
                continue
            if sovereign_class and e.sovereign_class != sovereign_class:
                continue
            if tag and tag not in e.tags:
                continue
            out.append(e)
        return out

    def stats(self) -> dict:
        by_class: Dict[str, int] = {}
        by_tech: Dict[str, int] = {}
        for e in self._items.values():
            by_class[e.sovereign_class] = by_class.get(e.sovereign_class, 0) + 1
            by_tech[e.tech] = by_tech.get(e.tech, 0) + 1
        return {
            "total": len(self._items),
            "by_sovereign_class": by_class,
            "by_tech": by_tech,
        }

    def to_json(self, path: str) -> None:
        records = [e.__dict__ for e in self._items.values()]
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"registry": records}, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "PDKRegistry":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("registry", data) if isinstance(data, dict) else data
        reg = cls()
        for it in items:
            reg.add(DeviceEntry(**it))
        return reg


#: 本仓**内置器件本体条目**（生态地基里「我们自己的第一批」）。
#: 🔴 只存**元数据**（id/name/tech/foundry/layers/params/tags/note）；几何与工艺
#:    参数的**单一真源**在 `lda_l2.primitives` / `lda_l2.drc` —— 此处 `params`
#:    一律留空，note 里给出真源指针，**不复制一份数值**（防第二份副本漂移）。
BUILTIN_DEVICE_ENTRIES: List["DeviceEntry"] = [
    DeviceEntry(
        id="lda.SensingRing",
        name="传感环（局部开窗）",
        tech="SOI",
        foundry="self",
        sovereign_class="C",
        layers=["SI", "WINDOW"],
        params={},
        tags=["photonics", "sensor", "sensing-window", "ps-m1"],
        note=("PS 征程 M1/G4：局部去上包层的开窗传感环。几何真源 = "
              "`lda_l2.primitives.sensing_window_geometry('SensingRing', …)`；"
              "工艺例外真源 = `lda_l2.drc.WINDOW_EXCEPTIONS`；"
              "DRC 规则键 = min_window_um / min_window_margin_um / min_window_end_um。"),
    ),
    DeviceEntry(
        id="lda.SensingMZI",
        name="传感 MZI（双臂开窗）",
        tech="SOI",
        foundry="self",
        sovereign_class="C",
        layers=["SI", "WINDOW"],
        params={},
        tags=["photonics", "sensor", "sensing-window", "ps-m1"],
        note=("PS 征程 M1/G4：双臂均开窗的传感 MZI。几何真源 = "
              "`lda_l2.primitives.sensing_window_geometry('SensingMZI', …)`；"
              "工艺例外真源 = `lda_l2.drc.WINDOW_EXCEPTIONS`。"),
    ),
]


def builtin_registry() -> "PDKRegistry":
    """返回预置了**本仓内置器件本体**的 Registry（PS-M1/G4 起）。"""
    return PDKRegistry(BUILTIN_DEVICE_ENTRIES)
