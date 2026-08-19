#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""L2 PDK 驱动逆设计 · smoke test（真跑，非演示）。

验证：PDKRegistry.derive_problem → DesignAgent.run 在真实工艺窗口内收敛，
含单参数与 N 维逆设计；l3_ai 缺陷内核在双/多规格被法官独立抓出（双判据分离）。
"""
import os
import sys

LDA_ROOT = os.path.dirname(os.path.abspath(__file__))
if LDA_ROOT not in sys.path:
    sys.path.insert(0, LDA_ROOT)

from lda_l2.pdk import get_default_registry
from lda_l1.protocol import KernelGateway
from lda_agent.design_loop import DesignAgent

OUT = os.path.join(LDA_ROOT, "reports_pdk")


def main():
    reg = get_default_registry()
    print("已登记 PDK:", reg.list_pdks())

    gw = KernelGateway(out_dir=OUT)
    agent = DesignAgent(gw, out_dir=OUT)
    key0 = reg.list_pdks()[0]

    # 1) 每个模板用真内核逆设计，应全部收敛（含多参数 / 谱形 / 多晶圆厂模板）
    for key in reg.list_pdks():
        for tpl in reg.get(key).templates.values():
            prob = reg.derive_problem(key, tpl.name, solver="truth")
            res = agent.run(prob, max_iter=80)
            nd = "ND" if len(prob.tunables) > 1 else "1D"
            print(f"[{nd}][{tpl.name}] truth: "
                  f"converged={res.converged} iters={res.iterations} "
                  f"final={res.final_param} metric={res.final_metric} "
                  f"passed_all={res.final_passed_all}")
            assert res.converged, f"真内核未收敛: {tpl.name}"
            assert res.final_passed_all, f"真内核未过验证: {tpl.name}"

    # 2) 双判据分离（单参数双规格，l3_ai）
    prob = reg.derive_problem(key0, "环形谐振器 FSR+波导", solver="l3_ai")
    res = agent.run(prob, max_iter=30)
    print(f"[双判据分离·1D] l3_ai dual: converged={res.converged} "
          f"passed_all={res.final_passed_all}")
    assert res.converged
    assert not res.final_passed_all

    # 3) 多参数逆设计专项 + 双判据分离（ND）
    prob = reg.derive_problem(key0, "环形双参数逆设计(B4+B2)", solver="truth")
    res = agent.run(prob, max_iter=80)
    print(f"[多参数逆设计·truth] final={res.final_param} "
          f"metric={res.final_metric} passed_all={res.final_passed_all}")
    assert set(res.final_param.keys()) == {"R", "w_core"}, \
        "多参数落点须含 R 与 w_core"
    assert res.converged and res.final_passed_all, \
        "多参数真内核应双判据全绿"

    prob = reg.derive_problem(key0, "环形双参数逆设计(B4+B2)", solver="l3_ai")
    res = agent.run(prob, max_iter=80)
    print(f"[多参数逆设计·l3_ai] converged={res.converged} "
          f"passed_all={res.final_passed_all} note={res.note}")
    assert res.converged, "设计目标 B4 仍应收敛（双判据·收敛 ≠ 验真）"
    assert not res.final_passed_all, \
        "多参数下法官仍应抓出 l3_ai 的 B2 缺陷（双判据分离：收敛但被判 FAIL）"

    # 4) 加权多目标逆设计（template5：B4 FSR + B2 n_eff 同时达标）
    prob = reg.derive_problem(key0, "环形双目标加权(B4+B2)", solver="truth")
    res = agent.run(prob, max_iter=80)
    print(f"[加权多目标·truth] final={res.final_param} metric={res.final_metric} "
          f"passed_all={res.final_passed_all} objectives={res.objectives}")
    assert res.objectives and len(res.objectives) > 1, "应暴露加权多目标"
    assert res.converged and res.final_passed_all, \
        "加权多目标真内核应双判据全绿（两目标同时达标）"

    # 5) 量子子集 B9/B10（确定性物理锚：transmon 频率 + 门保真度）
    qkey = [k for k in reg.list_pdks() if "量子" in k][0]
    prob = reg.derive_problem(qkey, "transmon 频率逆设计(B9)", solver="truth")
    res = agent.run(prob, max_iter=60)
    print(f"[量子·B9 truth] final={res.final_param} f01={res.final_metric} "
          f"passed_all={res.final_passed_all}")
    assert res.converged and res.final_passed_all, "量子 B9 真内核应收敛且通过验证"
    prob = reg.derive_problem(qkey, "transmon 频率逆设计(B9)", solver="l3_ai")
    res = agent.run(prob, max_iter=60)
    print(f"[量子·B9 l3_ai] converged={res.converged} "
          f"passed_all={res.final_passed_all}")
    assert not res.final_passed_all, "量子 B9 l3_ai 内核缺陷应被法官抓 FAIL"

    prob = reg.derive_problem(qkey, "量子门保真度+transmon约束(B10+B9)", solver="truth")
    res = agent.run(prob, max_iter=60)
    print(f"[量子·B10+B9 truth] final={res.final_param} F={res.final_metric} "
          f"passed_all={res.final_passed_all}")
    assert res.converged and res.final_passed_all, "量子 B10+B9 真内核应双判据全绿"
    prob = reg.derive_problem(qkey, "量子门保真度+transmon约束(B10+B9)", solver="l3_ai")
    res = agent.run(prob, max_iter=60)
    print(f"[量子·B10+B9 l3_ai] converged={res.converged} "
          f"passed_all={res.final_passed_all} note={res.note}")
    assert res.converged, "设计目标 B10 仍应收敛（双判据·收敛 ≠ 验真）"
    assert not res.final_passed_all, \
        "量子 l3_ai 的 B9 约束缺陷应被法官抓 FAIL（双判据分离：收敛但被判 FAIL）"

    # 6) B6 Tidy3D 门控（主权安全默认：无 key → 外部 ORACLE 返回 None，回退设计守则锚）
    from lda_harness.oracle_tidy3d import resolve_tidy3d_grating
    from lda_harness.golden import b6_grating_coupling_eff
    ora = resolve_tidy3d_grating({"wl": 1.55, "n_si": 3.48, "n_clad": 1.44,
                                   "period": 0.63, "ff": 0.5, "theta_deg": 8.0})
    assert ora is None, "本环境未配 TIDY3D_API_KEY，应返回 None（主权安全默认）"
    eff = b6_grating_coupling_eff(wl=1.55, n_si=3.48, n_clad=1.44,
                                  period=0.63, ff=0.5, theta_deg=8.0)
    assert abs(eff - 0.5) < 1e-9, "B6 无 ORACLE 时应回退设计守则锚 0.5"
    print(f"[B6 Tidy3D 门控] oracle=None(无key) eff回退={eff} ✓ 严守 GPL 仅外部 ORACLE")

    # 7) 多晶圆厂 PDK 共建校验
    n_pdk = len(reg.list_pdks())
    print(f"[多晶圆厂] 已登记 PDK 数={n_pdk}：{reg.list_pdks()}")
    assert n_pdk >= 4, "应已登记 ≥4 个 foundry（NOEIC/CUMEC/SITRI/量子）"

    # 8) 目标谱形逆设计（B11，有限差分梯度下降 / 数值伴随）
    prob = reg.derive_problem(key0, "环形谱形匹配(B11)", solver="truth")
    res = agent.run(prob, max_iter=80)
    print(f"[目标谱形·B11 truth] R={res.final_param} 谱形误差={res.final_metric} "
          f"converged={res.converged} passed_all={res.final_passed_all}")
    assert res.converged and res.final_passed_all, \
        "目标谱形逆设计应收敛且过 B4 物理定律约束（双判据分离在谱形域成立）"

    print("\nL2 PDK smoke OK —— PDK 驱动逆设计（含 N 维 / 加权多目标 / 量子子集 / "
          "目标谱形 / 多晶圆厂）链路通，双判据分离 + GPL 仅外部 ORACLE 纪律生效。")


if __name__ == "__main__":
    main()
