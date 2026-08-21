"""LDA · D-45 WDM 纵深 smoke（XT 反解 / 插损预算 / 单 FSR 信道上限）。

验证：
  1. xt_to_gap：给定 XT 指标 → 反解 gap（4 信道 2.5nm 间隔，XT≥20dB → gap≈0.32µm）
  2. insertion_loss_budget：每信道总插损 = drop IL + 前序环 thru 残差，≤ 阈值
  3. design_wdm_advanced：XT 指标驱动统一入口 → 反解 gap + 系统设计 PASS
  4. channel_capacity：单 FSR + XT 约束下信道上限（合理数值）
  5. 负例：XT 指标超出 gap 上限可达范围 → 正确报不可达
LLM 不进判决路径。
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lda_agent.wdm_system import (channel_capacity,  # noqa: E402
                                  design_wdm_advanced, insertion_loss_budget,
                                  xt_to_gap)

CH = [1550.0, 1552.5, 1555.0, 1557.5]


def main() -> int:
    ok = True
    print("=" * 70)
    print("D-45 WDM 纵深：XT 反解 gap / 插损预算 / 信道上限")
    print("=" * 70)

    # 1) XT 反解
    for xt in (15.0, 20.0, 25.0, 30.0):
        g = xt_to_gap(CH, xt)
        good = g["achievable"] and g["xt_db"] >= xt - 0.5
        ok &= good
        print(f"[{'OK  ' if good else 'FAIL'}] XT≥{xt}dB → gap={g['gap']}µm "
              f"（实际 XT={g['xt_db']}dB）")

    # 2) 插损预算
    from lda_agent.wdm_system import inverse_ring_for_channel
    Rs = [inverse_ring_for_channel(c * 1e-3) for c in CH]
    ilb = insertion_loss_budget(CH, Rs, 0.3)
    ok &= bool(ilb["max_total_il_db"] <= 3.0)
    print(f"[{'OK  ' if ok else 'FAIL'}] 插损预算: max 总插损="
          f"{ilb['max_total_il_db']}dB")
    for r in ilb["rows"]:
        print(f"     信道 {r['channel_nm']}nm: drop IL={r['drop_il_db']}dB + "
              f"thru 残差 {r['thru_residue_db']}dB = {r['total_il_db']}dB")

    # 3) design_wdm_advanced（XT 指标驱动）
    adv = design_wdm_advanced(channels_nm=CH, xt_target_db=20.0)
    acc = adv.get("acceptance", {})
    ok &= bool(acc.get("passed"))
    print(f"[{'OK  ' if acc.get('passed') else 'FAIL'}] design_wdm_advanced "
          f"XT≥20dB: gap={adv.get('xt_solve', {}).get('gap')}µm → "
          f"verdict={adv['verdict'][:70]}")
    print(f"     容量: {adv.get('channel_capacity')}")

    # 4) 容量
    cap = channel_capacity(20.0, 2.5)
    ok &= bool(cap["achievable"]) and 2 <= cap["n_max_single_fsr"] <= 6
    print(f"[{'OK  ' if ok else 'FAIL'}] 信道上限: gap={cap.get('required_gap_um')}"
          f"µm, 单 FSR {cap.get('min_fsr_nm')}nm → 最多 {cap.get('n_max_single_fsr')} 信道")

    # 5) 负例：XT 指标不可达
    bad = xt_to_gap(CH, 90.0)
    ok &= (not bad["achievable"]) and bad["gap"] is None
    print(f"[{'OK  ' if ok else 'FAIL'}] 负例 XT≥90dB: achievable={bad['achievable']}"
          f"（应 False，gap 上限不可达）")

    print("=" * 70)
    print("D-45 smoke 全绿:", ok)
    with open(os.path.join(_HERE, "reports", "wdm_depth_d45.json"), "w",
              encoding="utf-8") as f:
        json.dump({"all_passed": ok,
                   "xt_to_gap": {str(x): xt_to_gap(CH, x) for x in (15, 20, 25, 30)},
                   "insertion_loss_budget": ilb,
                   "channel_capacity_20db_2p5nm": cap,
                   "advanced_4ch": {k: adv[k] for k in
                                    ("channels_nm", "gap_um", "xt_solve",
                                     "insertion_loss_budget", "channel_capacity",
                                     "acceptance", "verdict")}},
                  f, ensure_ascii=False, indent=2)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
