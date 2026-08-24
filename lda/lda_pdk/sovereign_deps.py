"""主权依赖分级清单（A/B/C，来自战略审计 LDA-ST-001，D-93 落地为代码）。

分级依据（中美对抗背景下的技术主权判断）：
  - A 级 永不借：美系商业工具 + 美属托管平台（收入靠可信授权，agent
    长出的开放内核成功=击穿收费地基，结构性不能做开放内核）。
  - B 级 借今踢后（MIT/BSD）：可 fork 到 Gitee/GitCode 主权副本 +
    PyPI/NPM 镜像 hash 冷备；后期 AI 重写替换；Meep 先当 ORACLE 后被
    自写 FDTD 取代。
  - C 级 第一天自主：L0 IR/DSL、L1 agent 协议、L3 AI 求解核、物理定律锚。

EAR 734.7b：公开可得源码（MIT/BSD）默认不受出口管制，可合法 fork——
B 级策略的技术法律基础。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class Dependency:
    name: str
    cls: str                 # A / B / C
    license: str
    note: str
    fork_to: str = ""        # B 级主权副本目标（Gitee/GitCode/LDA）


# 战略审计（LDA-ST-001）三级分类代码化
SOVEREIGN_DEPS: List[Dependency] = [
    # ---------- A 级：永不借（美系商业工具 + 美属托管平台） ----------
    Dependency("Lumerical (Ansys)", "A", "商用闭源", "FDTD 求解器，商业闭源"),
    Dependency("Synopsys", "A", "商用闭源", "光学/TCAD 套件，商业闭源"),
    Dependency("Cadence", "A", "商用闭源", "Virtuoso 等 IC 设计，商业闭源"),
    Dependency("Siemens (Calibre)", "A", "商用闭源", "物理验证/DRC/LVS，商业闭源"),
    Dependency("GDSFactory+商业 NDA-PDK", "A", "NDA 专有", "晶圆厂私有 PDK，永不借"),

    # ---------- B 级：借今踢后（MIT/BSD，fork 主权副本） ----------
    Dependency("gdsfactory 内核", "B", "MIT", "fork 到 Gitee/GitCode 主权副本", "Gitee"),
    Dependency("Meep", "B", "GPL", "仅当 ORACLE 校验、零硬编码；后期被自写 FDTD 取代", "Gitee"),
    Dependency("KLayout", "B", "GPL", "版图查看/DRC，fork 主权副本", "Gitee"),
    Dependency("SAX", "B", "MIT", "电路级 ORACLE（sax 库）", "Gitee"),
    Dependency("MPB", "B", "GPL", "光子能带 ORACLE", "Gitee"),
    Dependency("Nazca", "B", "MIT", "版图框架", "Gitee"),
    Dependency("Tidy3D", "B", "前端 GPL/云美属",
               "仅外部 ORACLE 校验、零硬编码、无 Key 自动回退", "Gitee"),

    # ---------- C 级：第一天自主（LDA 自有） ----------
    Dependency("L0 IR/DSL", "C", "LDA 自有", "光子+量子统一中间表示，主权自主", "LDA"),
    Dependency("L1 agent 协议层", "C", "LDA 自有", "把旧内核翻译为 agent 操作接口", "LDA"),
    Dependency("L3 AI 求解核", "C", "LDA 自有", "AI 自举的求解器后端", "LDA"),
    Dependency("物理定律锚", "C", "LDA 自有", "解析解/麦克斯韦确定性计算", "LDA"),
]


def classify_dependency(name: str) -> str:
    """返回依赖的主权分级 A/B/C，未收录则返回 '?'。"""
    for d in SOVEREIGN_DEPS:
        if d.name.lower() == name.lower():
            return d.cls
    return "?"


def by_class(cls: str) -> List[Dependency]:
    """返回某主权分级下的全部依赖。"""
    return [d for d in SOVEREIGN_DEPS if d.cls == cls]
