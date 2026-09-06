"""Phase 1 系统类型 smoke（v0.8.33 · 提案编译器系统类型注册表）。

覆盖：
  ① SYSTEM_TYPES 注册表含三类基线 + 后续扩展类型（sensor_frontend / qkd_link /
     cpo_optical_io），且**每个类型都自带死标量锚**（禁止"无锚假类型"）
  ② link 默认路径零回归（design_pipeline 不传 system_type 仍走 link 闭环）
  ③ wdm_demux 复用 design_wdm_advanced 已验证闭环（B4 锚：drop IL≤3 / XT≥15）
  ④ quantum_fidelity 复用 design_multiqubit_fidelity 已验证闭环（D-46×D-47）
  ⑤ 向后兼容：design_pipeline({...}) 无 system_type 参数 = link，n_accepted≥1
  ⑥ 🔴 红线：每个类型 honest_note 声明 LLM 不进判决路径

🔴 v0.9.41 修复（潜伏断裂）：① 原断言 `types == [link, wdm_demux, quantum_fidelity]`
  是**等值比较**，M2 加 sensor_frontend、v0.9.40 加 qkd_link 后即已 FAIL，
  而本脚本在 CORE_SMOKES 内 ⇒ **core 门禁实际是破的**（铁律：CORE 覆盖不到 = 没门禁）。
  改为「基线三类必须含 + 每个类型必须自带锚 + 声明 LLM 不进判决」，新增类型不再打穿。

运行：python run_system_types_smoke.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.proposal_compiler import (
    design_pipeline, supported_system_types, SYSTEM_TYPES,
)

_PASS = 0
_FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    mark = "PASS" if cond else "FAIL"
    if cond:
        _PASS += 1
    else:
        _FAIL += 1
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))


def main() -> int:
    print("Phase 1 系统类型 smoke（提案编译器 SYSTEM_TYPES 注册表）")

    # ① 注册表：基线三类必须含（等值比较会随扩展打穿 ⇒ 改包含式）
    types = supported_system_types()
    baseline = ["link", "wdm_demux", "quantum_fidelity"]
    check("SYSTEM_TYPES 含基线三类 link/wdm_demux/quantum_fidelity",
          all(t in types for t in baseline), f"{types}")
    # ①-b 后续扩展类型（M2 / v0.9.40 / v0.9.41）—— 缺任一说明回归丢失
    extended = ["sensor_frontend", "qkd_link", "cpo_optical_io"]
    check("SYSTEM_TYPES 含扩展类型 sensor_frontend/qkd_link/cpo_optical_io",
          all(t in types for t in extended), f"{types}")
    # ①-c 🔴 每个类型必须自带死标量锚 + 完整字段（禁止"无锚假类型"）
    _required = ("domain", "title", "engine", "anchors", "honest_tier")
    _bad_meta = [t for t, m in SYSTEM_TYPES.items()
                 if any(k not in m for k in _required)]
    _no_anchor = [t for t, m in SYSTEM_TYPES.items() if not m.get("anchors")]
    check("每个系统类型字段完整（domain/title/engine/anchors/honest_tier）",
          not _bad_meta, f"缺字段: {_bad_meta}")
    check("每个系统类型自带死标量锚（禁止无锚假类型）",
          not _no_anchor, f"无锚类型: {_no_anchor}")

    # ② link 默认路径（零回归）
    link = design_pipeline({"n_channels": 4, "channel_spacing_ghz": 100,
                            "link_budget_db": 3.0})
    check("link 默认路径：过锚提案≥1（零回归）",
          link["n_accepted"] >= 1 and link["feasible_domain"]["feasible"],
          f"过锚 {link['n_accepted']}")

    # ③ wdm_demux（复用 design_wdm_advanced）
    wdm = design_pipeline({"n_channels": 4, "spacing_nm": 2.5},
                          system_type="wdm_demux")
    wdm_acc = wdm["ranked"][0]["screening"]["accepted"]
    check("wdm_demux：B4 锚判决 ACCEPT（复用已验证闭环）",
          wdm["n_accepted"] == 1 and wdm_acc,
          wdm["ranked"][0]["screening_summary"])
    check("wdm_demux：honest_note 声明 LLM 不进判决",
          "不进判决路径" in wdm["honest_note"], "")

    # ④ quantum_fidelity（复用 design_multiqubit_fidelity）
    q = design_pipeline({"f01s": [4.8, 5.0, 5.2]},
                        system_type="quantum_fidelity")
    q_acc = q["ranked"][0]["screening"]["accepted"]
    check("quantum_fidelity：D-46×D-47 判决 ACCEPT（复用已验证闭环）",
          q["n_accepted"] == 1 and q_acc,
          q["ranked"][0]["screening_summary"])
    check("quantum_fidelity：honest_note 声明 LLM 不进判决",
          "不进判决路径" in q["honest_note"], "")

    # ①-d 每个类型的 engine 必须指向真实设计函数（不静默退化）
    import lda_harness.proposal_compiler as _pc
    _unresolved = [t for t, m in SYSTEM_TYPES.items()
                   if str(m.get("engine", "")).startswith("proposal_compiler.")
                   and not callable(getattr(
                       _pc, str(m["engine"]).split(".", 1)[1], None))]
    check("每个系统类型的 engine 指向真实设计函数（不静默退化）",
          not _unresolved, f"未解析: {_unresolved}")

    # ④-b cpo_optical_io（D 赛道 · v0.9.41 新类：三死标量锚 + P-CPO×D-67 双向护栏）
    cpo = design_pipeline({"n_channels": 8, "lane_rate_gbps": 200.0,
                           "pitch_um": 250.0}, system_type="cpo_optical_io")
    cpo_acc = cpo["ranked"][0]["screening"]["accepted"]
    check("cpo_optical_io：S-CPO-IL/DENSITY/BUDGET 三锚判决 ACCEPT",
          cpo["n_accepted"] == 1 and cpo_acc,
          cpo["ranked"][0]["screening_summary"])
    check("cpo_optical_io：honest_note 声明 LLM 不进判决 + 显式不判决能效 pJ/bit",
          "不进判决路径" in cpo["honest_note"]
          and "不判决能效" in cpo["honest_note"], "")
    # ④-c 🔴 新护栏必须反向测试会响：间距低于物理下界必须抛错（否则密度可静默虚报）
    from lda_design import cpo_engines as _ce
    _p_hits = 0
    for _cm, _p in (("fau", 20.0), ("grating_array", 5.0)):
        try:
            _ce.cpo_optical_io_metrics({"couple_mode": _cm, "pitch_um": _p})
        except AssertionError:
            _p_hits += 1
    check("P-CPO 间距几何下界护栏会响（虚报密度必被拦）", _p_hits == 2,
          f"命中 {_p_hits}/2")

    # ⑤ 向后兼容：无 system_type = link
    legacy = design_pipeline({"n_channels": 4, "channel_spacing_ghz": 100})
    check("向后兼容：design_pipeline 无 system_type 仍走 link",
          legacy.get("system_type", "link") == "link"
          and legacy["n_accepted"] >= 1,
          f"过锚 {legacy['n_accepted']}")

    # ⑥ 未知类型报错（不静默退化）
    try:
        design_pipeline({}, system_type="nope")
        check("未知 system_type 抛错（不静默退化）", False, "未抛错")
    except ValueError:
        check("未知 system_type 抛错（不静默退化）", True, "")

    print(f"\n系统类型 smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
