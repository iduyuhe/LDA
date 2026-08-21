"""LDA L0 · IR 静态校验器（技术复利地基）。

把"验证闭环"前置到 IR 层——这恰好是"技术复利"的具象：上层每一次设计（单
foundry / 多 foundry / 加权 / 谱形）都先过这道门，IR 不合法就根本不会进
agent 闭环，省下大量"跑完才发现意图自相矛盾"的浪费。这是护城河地基的一部分，
必须自己做好、不取巧。

校验项：
  1. component id 唯一；
  2. net.connects 引用的 "comp.port" 必须在 components 中存在；
  3. objective / constraint 引用的 bid 必须非空且符合 "B<数字>" 形式
     （宽松校验，避免耦合 harness 的题号集合，但挡住明显非法）；
  4. spectrum 规格合法（kind 已知、target_fsr_nm>0、primary_param 在主器件
     param_bounds 或 params 内）；
  5. params 当前值若带 param_bounds，必须落在区间内；
  6. foundry_plan 合法（mode∈{all,list}，list 模式 foundries 非空）；
  7. 必须至少指定一个设计意图（spectrum 或 objectives 至少其一），否则桥接
     层会抛错——提前在 IR 层拦截，给 agent 一次性修复清单。

返回错误字符串列表；空列表 = 通过。设计哲学：不抛异常、收集全部问题，
便于 agent 一次性拿到修复清单（而不是改一个错再跑一次）。
"""
from __future__ import annotations

from typing import List

from .core import IRModel

_KNOWN_SPECTRUM_KINDS = {"ring_fsr", "lorentz_comb"}
_KNOWN_SCHEMA_VERSIONS = {"0.2", "0.3"}     # D-40 受控升级：0.2 遗留兼容
_KNOWN_PHYSICS_BIDS = {"B9", "B12", "B13"}  # 量子物理锚（B9 transmon-f01 /
                                            # B12 resonator-f0 / B13 coupler-J）


def validate(m: IRModel) -> List[str]:
    """校验 IRModel，返回错误列表（空=合法）。"""
    errs: List[str] = []

    # 0. schema 版本受控（D-40：0.3 现行，0.2 遗留兼容；未知版本拒绝）
    if m.schema_version not in _KNOWN_SCHEMA_VERSIONS:
        errs.append(f"schema_version 未知：'{m.schema_version}'"
                    f"（须 {sorted(_KNOWN_SCHEMA_VERSIONS)}）")

    # 1. component id 唯一
    ids = [c.id for c in m.components]
    if len(ids) != len(set(ids)):
        errs.append("component id 重复：" + ", ".join(sorted({i for i in ids if ids.count(i) > 1})))

    # 建立 comp.port 索引
    port_index = set()
    for c in m.components:
        for p in c.ports:
            port_index.add(f"{c.id}.{p.name}")

    # 2. net 连接闭合
    for n in m.nets:
        for ref in n.connects:
            if ref not in port_index:
                errs.append(f"net '{n.id}' 引用未定义端口 '{ref}'")

    # 3. objective / constraint bid 合法
    for o in m.objectives:
        if not o.bid or not (o.bid[0] == "B" and o.bid[1:].isdigit()):
            errs.append(f"objective/constraint bid 非法：'{o.bid}'（须形如 B11）")

    # 3b. physics 物理锚合法（D-40：bid 已知 + spec_params 非空）
    for c in m.components:
        if c.physics is not None:
            ph = c.physics
            if ph.bid not in _KNOWN_PHYSICS_BIDS:
                errs.append(f"component '{c.id}' physics.bid 未知：'{ph.bid}'")
            if not ph.spec_params:
                errs.append(f"component '{c.id}' physics.spec_params 为空"
                            f"（物理锚须带规范参数）")

    # 4. spectrum 规格合法
    if m.spectrum:
        s = m.spectrum
        if s.kind not in _KNOWN_SPECTRUM_KINDS:
            errs.append(f"spectrum.kind 未知：'{s.kind}'")
        if s.target_fsr_nm <= 0:
            errs.append("spectrum.target_fsr_nm 必须 > 0")
        prim = m.primary_component
        if prim is not None:
            if s.primary_param not in prim.params and s.primary_param not in prim.param_bounds:
                errs.append(f"spectrum.primary_param '{s.primary_param}' 不在主器件 "
                            f"'{prim.id}' 的 params/param_bounds 内")

    # 5. params 落在 param_bounds 内
    for c in m.components:
        for name, (lo, hi) in c.param_bounds.items():
            if name in c.params:
                v = c.params[name]
                if not (lo <= v <= hi):
                    errs.append(f"component '{c.id}' 参数 '{name}'={v} 超出区间 [{lo},{hi}]")

    # 6. foundry_plan 合法
    if m.foundry_plan:
        fp = m.foundry_plan
        if fp.mode not in ("all", "list"):
            errs.append(f"foundry_plan.mode 非法：'{fp.mode}'（须 all/list）")
        if fp.mode == "list" and not fp.foundries:
            errs.append("foundry_plan.mode=list 但 foundries 为空")

    # 7. 必须至少指定一个设计意图（目标谱形 或 显式 objectives）
    #    —— 否则桥接层会抛 ValueError；这里提前在 IR 层拦截，给 agent 一次性
    #       修复清单（技术复利：上层设计都先过此门）。
    if m.spectrum is None and not m.objectives:
        errs.append("IR 未指定任何设计意图（spectrum 或 objectives 至少其一）")

    return errs
