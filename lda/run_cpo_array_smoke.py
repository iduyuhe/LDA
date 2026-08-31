"""v0.8.47 CPO 共封装光引擎阵列 smoke（阶段2 · 十万级真实器件样例）。

验证 `lda_harness/cpo_array`：
  ① 层次推导死标量：器件数 = (4 + 11·n_lane) × n_oe × n_ch（不差分毫）
  ② 光路数 = 2 × 通道数；布线网 = 器件 − 光路；总网 = 布线网 + 2×光路
  ③ 几何：端口线对齐（行内连接全为水平段，零回折 —— 零短路的几何基石）
  ④ 物理自洽：**独立重算** R = m·λ/(2π·n_eff)，与生成器输出逐位比对
  ⑤ 光栅布拉格条件：λ_c = Λ·(n_eff,gr − sin θ) 落在 LAN-WDM 波段内
  ⑥ DRC 全过（器件级可制造性，死标量）
  ⑦ LVS 正例 ACCEPT（0 违规 · 网表全匹配）
  ⑧ LVS 反例：断路 → REJECT；错连 → REJECT（证明判决非"永远 ACCEPT"）
  ⑨ GDS round-trip 可解析
  ⑩ 十万配置推导：默认配置 = 100,096 器件（只推导不实跑，CI 快）
  ⑪ 红线：cpo_array.py 源码零 LLM 引用

小规模实跑（2 引擎 × 4 通道 × 4 波长 = 384 器件），CI 秒级；
十万级实跑由 `run_cpo_array_demo.py` 覆盖（工业回归，非 core）。
运行：python run_cpo_array_smoke.py
"""
from __future__ import annotations

import inspect
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.cpo_array import (CPOArrayConfig, GC_COUPLING_ANGLE_DEG,
                                   GC_DUTY, GC_LAMBDA_UM, GC_N_EFF_GRATING,
                                   LAN_WDM_CHANNELS_NM, N_EFF_SOI,
                                   RING_ORDER_M, build_cpo_array_case,
                                   inject_fault, lane_wavelengths,
                                   ring_radius_um)
from lda_l2.chip_layout_export import chip_drc_report, export_chip_gds
from lda_l2.lvs import run_lvs

_PASS = 0
_FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> bool:
    global _PASS, _FAIL
    mark = "PASS" if cond else "FAIL"
    if cond:
        _PASS += 1
    else:
        _FAIL += 1
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))
    return cond


def main() -> int:
    cfg = CPOArrayConfig(n_oe=2, n_ch=4, n_lane=4, ch_per_row=4)
    expect_dev = (4 + 11 * cfg.n_lane) * cfg.n_oe * cfg.n_ch
    print(f"CPO 阵列 smoke（{cfg.n_oe} 引擎 × {cfg.n_ch} 通道 × "
          f"{cfg.n_lane} 波长 = {expect_dev} 器件）")

    link, placement, routes, meta = build_cpo_array_case(cfg)

    # ① 层次推导死标量
    check("① 器件数 = (4 + 11·n_lane) × n_oe × n_ch（层次推导死标量）",
          len(link.ir.components) == expect_dev == meta["n_devices"],
          f"{len(link.ir.components)} == {expect_dev}")
    check("① 器件数 = 配置推导值（两条独立路径一致）",
          cfg.n_devices == expect_dev, f"{cfg.n_devices} == {expect_dev}")

    # ② 光路 / 网数
    n_route = len(routes)
    check("② 光路数 = 2 × 通道数（每通道 1 发 1 收）",
          meta["n_chains"] == 2 * cfg.n_channels,
          f"{meta['n_chains']} == {2 * cfg.n_channels}")
    check("② 布线网 = 器件 − 光路（链内串行）",
          n_route == expect_dev - meta["n_chains"],
          f"{n_route} == {expect_dev} - {meta['n_chains']}")
    check("② 总网 = 布线网 + 2 × 光路（首尾各 1 个外部 IO）",
          meta["n_nets"] == n_route + 2 * meta["n_chains"],
          f"{meta['n_nets']} == {n_route} + {2 * meta['n_chains']}")

    # ③ 几何：端口线对齐（零回折）
    non_h = sum(1 for rr in routes.values()
                if abs(rr.points_um[0][1] - rr.points_um[-1][1]) > 1e-6)
    check("③ 几何：行内连接全为水平段（端口线对齐 · 零回折 · 零跨行跳线）",
          non_h == 0, f"非水平 {non_h}/{n_route}")

    # ④ 物理自洽：独立重算 R = m·λ/(2π·n_eff)
    lam_list = lane_wavelengths(cfg.n_lane)
    expect_R = [RING_ORDER_M * (l / 1000.0) / (2.0 * math.pi * N_EFF_SOI)
                for l in lam_list]
    got_R = meta["ring_radii_um"]
    check("④ 物理自洽：R = m·λ/(2π·n_eff)（独立重算逐项比对）",
          all(abs(a - round(b, 4)) < 1e-9 for a, b in zip(got_R, expect_R)),
          f"m={RING_ORDER_M} n_eff={N_EFF_SOI} R={got_R[:3]}…")
    check("④ 微环半径全部 ≥ DRC min_bend_R 5.0 µm",
          min(got_R) >= 5.0, f"min R={min(got_R)} µm")
    check("④ 谐振级数 m 为整数（物理约束，非拟合常数）",
          isinstance(RING_ORDER_M, int), f"m={RING_ORDER_M}")

    # ⑤ 光栅布拉格条件
    lam_c = GC_LAMBDA_UM * (GC_N_EFF_GRATING
                            - math.sin(math.radians(GC_COUPLING_ANGLE_DEG)))
    check("⑤ 光栅耦合中心波长落在 LAN-WDM 波段内（布拉格条件反解）",
          min(LAN_WDM_CHANNELS_NM) / 1000.0 - 0.02
          <= lam_c <= max(LAN_WDM_CHANNELS_NM) / 1000.0 + 0.02,
          f"λ_c={lam_c:.4f} µm ∈ "
          f"[{min(LAN_WDM_CHANNELS_NM) / 1000:.4f}, "
          f"{max(LAN_WDM_CHANNELS_NM) / 1000:.4f}]")
    tooth = GC_LAMBDA_UM * GC_DUTY
    gap = GC_LAMBDA_UM * (1.0 - GC_DUTY)
    check("⑤ 光栅齿形满足 DRC 线宽/间距双约束（齿宽≥0.35 · 齿隙≥0.20）",
          tooth >= 0.35 and gap >= 0.20,
          f"齿宽 {tooth:.3f} / 齿隙 {gap:.3f} µm")

    # ⑥ DRC
    drc = chip_drc_report(link, placement)
    check("⑥ DRC：全部器件通过（死标量）",
          drc["all_pass"] and drc["n_pass"] == expect_dev,
          f"{drc['n_pass']}/{drc['n_checked']}")

    # ⑦ LVS 正例
    lvs = run_lvs(link, placement, routes)
    check("⑦ LVS：正例 ACCEPT（0 违规）",
          lvs["verdict"] == "ACCEPT" and lvs["n_violations"] == 0,
          f"{lvs['verdict']} viol={lvs['n_violations']}")
    nm = lvs["match"]
    check("⑦ LVS：网表全匹配",
          nm["n_nets_match"] == nm["n_nets_total"] == n_route,
          f"{nm['n_nets_match']}/{nm['n_nets_total']}")

    # ⑧ LVS 反例
    r_dis = dict(routes)
    inject_fault(r_dis, "disconnect")
    lvs_dis = run_lvs(link, placement, r_dis)
    check("⑧ 反例-断路：REJECT（判决抓得住）",
          lvs_dis["verdict"] == "REJECT", f"{lvs_dis['verdict']}")
    r_mis = dict(routes)
    inject_fault(r_mis, "misroute")
    lvs_mis = run_lvs(link, placement, r_mis)
    check("⑧ 反例-错连：REJECT（判决抓得住）",
          lvs_mis["verdict"] == "REJECT", f"{lvs_mis['verdict']}")

    # ⑨ GDS round-trip
    g = export_chip_gds(link, placement, routes)
    st = g["gds_stats"]
    check("⑨ GDS round-trip 可解析",
          isinstance(g["gds_parse"], dict)
          and g["gds_parse"].get("n_structures", 0) >= 1
          and st["n_elements"] >= expect_dev,
          f"struct={st.get('n_structures')} elem={st['n_elements']}")

    # ⑩ 十万配置推导（不实跑，CI 快）
    big = CPOArrayConfig()
    check("⑩ 十万配置推导：32 引擎 × 34 通道 × 8 波长 = 100,096 器件",
          big.n_devices == 100096, f"{big.n_devices}")
    check("⑩ 十万配置：光路 2,176 条 · 通道宽度 92 器件/通道",
          big.n_channels == 1088 and big.channel_width() == 92,
          f"ch={big.n_channels} width={big.channel_width()}")
    try:
        CPOArrayConfig(n_oe=1, n_ch=3, ch_per_row=4).validate()
        ok = False
    except ValueError:
        ok = True
    check("⑩ 配置护栏：ch_per_row 不整除 n_oe×n_ch 时拒绝（否则通道跨行）",
          ok, "3 % 4 != 0 → ValueError")

    # ⑪ 红线
    from lda_harness import cpo_array as ca_mod
    src = inspect.getsource(ca_mod)
    hits = [k for k in ("openai", "anthropic", "ollama", "transformers",
                        "requests.post", "torch") if k in src]
    check("⑪ 红线：cpo_array.py 源码零 LLM 引用（判决路径不含模型）",
          not hits, f"hits={hits}")

    print(f"\nCPO 阵列 smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
