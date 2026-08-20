#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""L2 PDK 驱动逆设计 · smoke test（真跑，非演示）。

诚实降级说明：DesignProblem 抽象已随 webui 修复移除，DesignAgent 现只消费
intent dict 且仅支持光子真 2D 波导（waveguide_2d）。PDKRegistry.derive_intent
把模板映射为 DesignAgent.run 可消费的 intent：
  - waveguide 模板 → 真跑（FDTD neff ↔ slab ORACLE 验收）；
  - ring_resonator / transmon / gate_fidelity 模板 → agent 逆设计未接入
    （规划 D-09 / BandDesignAgent 通用化），诚实 NotImplementedError，不假装跑通。
另保留 B6 Tidy3D 门控（主权安全默认）与多晶圆厂共建校验。
"""
import os
import sys

LDA_ROOT = os.path.dirname(os.path.abspath(__file__))
if LDA_ROOT not in sys.path:
    sys.path.insert(0, LDA_ROOT)

from lda_l2.pdk import get_default_registry
from lda_agent.design_loop import DesignAgent

OUT = os.path.join(LDA_ROOT, "reports_pdk")


def main():
    reg = get_default_registry()
    print("已登记 PDK:", reg.list_pdks())
    print()

    # 1) waveguide 模板 → derive_intent → DesignAgent 真跑（真 2D 波导验收）
    agent = DesignAgent(backend="numpy", geo_kind="waveguide_2d")
    wg_cases = 0
    for key in reg.list_pdks():
        for tpl in reg.get(key).templates.values():
            if tpl.device_type != "waveguide":
                continue
            intent = reg.derive_intent(key, tpl.name)
            rep = agent.run(intent)
            ok = rep.accepted
            wg_cases += 1
            print(f"[waveguide·{key.split('::')[0]}] {tpl.name}: "
                  f"neff(FDTD)={rep.final_metric:.4f} "
                  f"slab={rep.final_oracle_metric:.4f} accepted={ok}")
            assert ok, f"waveguide 模板未过验收: {tpl.name}"
    assert wg_cases >= 3, "应至少跑通 3 个 waveguide 模板（NOEIC/CUMEC/SITRI）"
    print(f"OK  waveguide 模板 {wg_cases} 例全过验收（FDTD neff ↔ slab ORACLE）")
    print()

    # 2) 其它模板诚实 NotImplementedError（agent 逆设计未接入，规划 D-09）
    for key in reg.list_pdks():
        for tpl in reg.get(key).templates.values():
            if tpl.device_type == "waveguide":
                continue
            try:
                reg.derive_intent(key, tpl.name)
                print(f"FAIL {key} · {tpl.name} 应诚实 NotImplementedError")
                return 1
            except NotImplementedError:
                print(f"[未接入·{key.split('::')[0]}] {tpl.name}"
                      f"（{tpl.device_type}）→ NotImplementedError（规划 D-09 接入）")
    print()

    # 3) B6 Tidy3D 门控（主权安全默认：无 key → 外部 ORACLE 返回 None，回退设计守则锚）
    from lda_harness.oracle_tidy3d import resolve_tidy3d_grating
    from lda_harness.golden import b6_grating_coupling_eff
    ora = resolve_tidy3d_grating({"wl": 1.55, "n_si": 3.48, "n_clad": 1.44,
                                   "period": 0.63, "ff": 0.5, "theta_deg": 8.0})
    assert ora is None, "本环境未配 TIDY3D_API_KEY，应返回 None（主权安全默认）"
    eff = b6_grating_coupling_eff(wl=1.55, n_si=3.48, n_clad=1.44,
                                  period=0.63, ff=0.5, theta_deg=8.0)
    assert abs(eff - 0.5) < 1e-9, "B6 无 ORACLE 时应回退设计守则锚 0.5"
    print(f"[B6 Tidy3D 门控] oracle=None(无key) eff回退={eff} ✓ 严守 GPL 仅外部 ORACLE")
    print()

    # 4) 多晶圆厂 PDK 共建校验
    n_pdk = len(reg.list_pdks())
    print(f"[多晶圆厂] 已登记 PDK 数={n_pdk}：{reg.list_pdks()}")
    assert n_pdk >= 4, "应已登记 ≥4 个 foundry（NOEIC/CUMEC/SITRI/量子）"

    print("\nL2 PDK smoke OK —— waveguide 模板真跑过验收，其余模板诚实声明未接入，"
          "B6 门控 + 多晶圆厂共建纪律生效。")


if __name__ == "__main__":
    main()
