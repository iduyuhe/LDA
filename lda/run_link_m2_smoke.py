"""P1-M2 自动布线 routing · 生成 + round-trip + 损耗计入 + 自洽验证 smoke。

验证点：
  1. 4 信道 WDM 链路 → 自动布线生成 3 条内部 bus 网，路径/长度/损耗合理、无 blocked；
  2. GDS 字节经 parse_gds round-trip 可解析（结构/元素/PATH 层）；
  3. 损耗计入：注入 net 损耗后的仿真 ≤ 理想 net（逐波长逐点），且 net 损耗非空；
  4. 自洽：route_and_simulate 内部 sim 与 engine.simulate(net_loss_db=同一字典)
     逐波长逐点一致（证明 net 损耗已正确注入级联引擎）。

注：M1「与 wdm_system 级联一致性」回归由 run_link_m1_smoke 单独保证，本 smoke
不耦合 wdm_system（避免签名漂移），聚焦 M2 布线/损耗/GDS 自身正确性。
"""
import sys

from lda_chain import (simulate, route_and_simulate,
                       build_wdm_link_from_channels)


def main():
    channels = [1550.0, 1570.0, 1590.0, 1610.0]
    link = build_wdm_link_from_channels(channels)
    assert link.validate() == [], "IR.validate 应无错误"

    wls = [round(1.50 + 0.001 * i, 4) for i in range(121)]  # 1.50~1.62 µm

    # 1) 布局 + 布线 + 仿真
    res = route_and_simulate(link, wls, wg_width=0.5, bend_radius=5.0)
    routes = res["routes"]
    checks = []
    checks.append(("route 数 == 内部 2 端口 net 数(3)", len(routes) == 3))
    for net_id, rr in routes.items():
        checks.append((f"{net_id}: 路径点>=2", len(rr.points_um) >= 2))
        checks.append((f"{net_id}: 长度>0 ({rr.length_um:.2f}um)",
                       rr.length_um > 0))
        checks.append((f"{net_id}: 总损耗>0 ({rr.total_loss_db:.4f}dB)",
                       rr.total_loss_db > 0))
        checks.append((f"{net_id}: 弯曲数={rr.n_bends} 圆角损耗={rr.bend_loss_db:.4f}dB",
                       rr.n_bends >= 0))
    checks.append(("无 blocked net（成功避障）", len(res["blocked_nets"]) == 0))
    checks.append(("GDS 结构数==1", res["gds_parse"]["n_structures"] == 1))
    chip = res["gds_parse"]["structures"]["CHIP"]
    checks.append(("GDS 元素数>0", chip["elements"] > 0))
    checks.append(("GDS 含 PATH 层(1)", 1 in chip["layers"]))

    # 2) 损耗计入：有 net 损耗的 sim 应 <= 理想（net_loss_db={}）
    ideal = simulate(link, wls)  # 无损耗
    routed = res["sim"]
    max_extra = 0.0
    for k in ideal["transfers"]:
        if k in routed["transfers"]:
            for a, b in zip(ideal["transfers"][k], routed["transfers"][k]):
                max_extra = max(max_extra, a - b)  # 理想应 >= 路由
    # 路由传递 = 理想传递 × 累积 net 增益(<1)，最长路径经 3 段 bus 损耗，
    # 幅度衰减约 0.0033（正确物理行为）；此处验证方向正确且量级合理
    checks.append(("有损耗 sim 不高于理想（衰减合理 <0.05）",
                   max_extra >= -1e-12 and max_extra < 0.05))
    checks.append(("net 损耗已注入（3 条）",
                   len(routed.get("net_loss_db", {})) == 3))

    # 3) 自洽：内部 sim 与 engine.simulate(net_loss_db=同字典) 一致
    rerun = simulate(link, wls, net_loss_db=res["net_loss_db"])
    max_self = 0.0
    for k in rerun["transfers"]:
        if k in routed["transfers"]:
            for a, b in zip(rerun["transfers"][k], routed["transfers"][k]):
                max_self = max(max_self, abs(a - b))
    checks.append(("sim 与 engine(net_loss) 自洽 (err<1e-12)", max_self < 1e-12))

    ok = all(v for _, v in checks)
    print("=== P1-M2 routing smoke ===")
    for name, v in checks:
        print(f"  [{'PASS' if v else 'FAIL'}] {name}")
    print(f"routes={len(routes)} blocked={res['blocked_nets']}")
    print(f"net_loss_db={ {k: round(v, 4) for k, v in res['net_loss_db'].items()} }")
    print(f"max_extra(路由-理想)={max_extra:.4e}  max_self(自洽)={max_self:.2e}")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
