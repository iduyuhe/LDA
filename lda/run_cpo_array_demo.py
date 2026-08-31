"""CPO 共封装光引擎阵列 · 十万级真实器件样例演示（v0.8.47 · 阶段2）。

把 v0.8.45/v0.8.46 打通的十万器件级全链能力落到**真实器件样例**：
CPO（Co-Packaged Optics）光引擎阵列 —— 层次化（阵列→光引擎→波长通道→
波长 lane）、器件类型多样（微环调制器 / WDM 解复用环 / 功率监测抽头 /
光栅耦合器 / 互连波导段）、参数由物理谐振条件反解。

闭环：构建 → 放置 → 布线 → GDS 导出 → DRC 可制造性 → LVS 签核 → 报告。

死标量验收（LLM 不进判决路径）：
  ① 器件数 = 配置推导值（不差分毫）；
  ② 光路数 = 2 × 通道数（每通道 1 发 1 收）；
  ③ GDS round-trip 可解析；
  ④ DRC 全过（器件级可制造性）；
  ⑤ LVS ACCEPT（版图-原理图一致，0 违规、网表全匹配）；
  ⑥ 反例：注入断路 → LVS REJECT（证明判决抓得住，非"永远 ACCEPT"）。

运行：python run_cpo_array_demo.py [--oe 32] [--ch 34] [--lane 8]
                                   [--ch-per-row 4] [--out reports_cpo_array]
      小规模试跑：python run_cpo_array_demo.py --oe 1 --ch 2 --out /tmp/cpo_s
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_PASS = 0
_FAIL = 0
_FATAL: list = []


def check(name: str, cond: bool, detail: str = "") -> bool:
    global _PASS, _FAIL
    mark = "PASS" if cond else "FAIL"
    if cond:
        _PASS += 1
    else:
        _FAIL += 1
        _FATAL.append(name)
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))
    return cond


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="CPO 光引擎阵列演示（v0.8.47）")
    ap.add_argument("--oe", type=int, default=32, help="光引擎数（默认 32）")
    ap.add_argument("--ch", type=int, default=34, help="每引擎通道数（默认 34）")
    ap.add_argument("--lane", type=int, default=8, help="每通道波长数（≤8）")
    ap.add_argument("--ch-per-row", type=int, default=4,
                    help="每行通道数（须整除 oe×ch）")
    ap.add_argument("--out", default="reports_cpo_array",
                    help="报告输出目录（相对 lda/）")
    ap.add_argument("--no-gds", action="store_true",
                    help="跳过 GDS 导出（仅 DRC/LVS，调试用）")
    args = ap.parse_args(argv)

    from lda_harness.cpo_array import (CPOArrayConfig, build_cpo_array_case,
                                       inject_fault)
    from lda_l2.chip_layout_export import export_chip_gds, chip_drc_report
    from lda_l2.lvs import run_lvs

    cfg = CPOArrayConfig(n_oe=args.oe, n_ch=args.ch, n_lane=args.lane,
                         ch_per_row=args.ch_per_row)
    cfg.validate()
    out_dir = Path(_HERE) / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    t_start = time.perf_counter()
    print("CPO 共封装光引擎阵列（阶段2 · 十万级真实器件样例）")
    print("=" * 68)
    print(f"配置：{cfg.n_oe} 引擎 × {cfg.n_ch} 通道 × {cfg.n_lane} 波长 "
          f"→ 推导 {cfg.n_devices} 器件 / {2 * cfg.n_channels} 条光路")
    print(f"网格：{cfg.cols} 列/行 × "
          f"{cfg.n_devices // cfg.cols + (1 if cfg.n_devices % cfg.cols else 0)} 行")

    # ① 构建 + 放置 + 布线
    link, placement, routes, meta = build_cpo_array_case(cfg)
    t_build = time.perf_counter() - t_start
    print(f"[1/5] 构建+放置+布线: {t_build:.2f}s "
          f"(建链 {meta['time_build_link_s']}s / 布线 {meta['time_route_s']}s)")
    check("器件数 = 配置推导值（死标量）",
          len(link.ir.components) == cfg.n_devices == meta["n_devices"],
          f"{len(link.ir.components)} == {cfg.n_devices}")
    check("光路数 = 2 × 通道数（每通道 1 发 1 收）",
          meta["n_chains"] == 2 * cfg.n_channels,
          f"{meta['n_chains']} == {2 * cfg.n_channels}")
    n_route = len(routes)
    check("布线网数 = 器件数 − 光路数（链内串行）",
          n_route == cfg.n_devices - meta["n_chains"],
          f"{n_route} == {cfg.n_devices} - {meta['n_chains']}")
    check("总网数 = 布线网 + 2 × 光路（首尾各 1 个外部 IO）",
          meta["n_nets"] == n_route + 2 * meta["n_chains"],
          f"{meta['n_nets']} == {n_route} + {2 * meta['n_chains']}")

    # ② 几何自检：端口线对齐（行内连接全为水平段 → 零回折）
    bad = 0
    for net_id, rr in routes.items():
        pts = rr.points_um
        if len(pts) >= 2 and abs(pts[0][1] - pts[-1][1]) > 1e-6:
            bad += 1
    check("几何：全部行内连接为水平段（端口线对齐，零回折）",
          bad == 0, f"非水平 {bad}/{len(routes)}")

    # ③ DRC
    t0 = time.perf_counter()
    drc = chip_drc_report(link, placement)
    t_drc = time.perf_counter() - t0
    print(f"[2/5] DRC 可制造性: {drc['n_pass']}/{drc['n_checked']} "
          f"({t_drc:.2f}s)")
    check("DRC：全部器件通过（死标量）",
          drc["all_pass"] and drc["n_pass"] == cfg.n_devices,
          f"{drc['n_pass']}/{drc['n_checked']}")

    # ④ LVS 正例
    t0 = time.perf_counter()
    lvs = run_lvs(link, placement, routes)
    t_lvs = time.perf_counter() - t0
    print(f"[3/5] LVS 签核（正例）: {lvs['verdict']} ({t_lvs:.2f}s)")
    check("LVS：正例 ACCEPT（0 违规）",
          lvs["verdict"] == "ACCEPT" and lvs["n_violations"] == 0,
          f"viol={lvs['n_violations']}")
    nm = lvs["match"]
    check("LVS：网表全匹配（含布线网全覆盖）",
          nm["n_nets_match"] == nm["n_nets_total"] == n_route,
          f"{nm['n_nets_match']}/{nm['n_nets_total']} (routes={n_route})")

    # ⑤ GDS 导出
    gds_stats = {}
    if not args.no_gds:
        t0 = time.perf_counter()
        r = export_chip_gds(link, placement, routes)
        t_gds = time.perf_counter() - t0
        st = r["gds_stats"]
        print(f"[4/5] GDS 导出: {st['gds_bytes'] / 1e6:.2f} MB / "
              f"{st['n_elements']} 元素 ({t_gds:.2f}s)")
        check("GDS round-trip 可解析",
              isinstance(r["gds_parse"], dict)
              and r["gds_parse"].get("n_structures", 0) >= 1
              and st["n_elements"] >= cfg.n_devices,
              f"struct={st.get('n_structures')} elem={st['n_elements']}")
        check("芯片面积/bbox 合理（非退化）",
              st["area_um2"] > 0 and st["width_um"] > 0
              and st["height_um"] > 0,
              f"{st['width_um']}×{st['height_um']} µm = "
              f"{st['area_um2'] / 1e6:.2f} mm²")
        gds_stats = {k: st[k] for k in ("gds_bytes", "n_elements", "bbox_um",
                                        "area_um2", "width_um", "height_um",
                                        "n_io") if k in st}
        gds_stats["time_export_s"] = round(t_gds, 3)

    # ⑥ 反例：注入断路 → 必须 REJECT（证明判决非"永远 ACCEPT"）
    routes_bad = dict(routes)
    killed = inject_fault(routes_bad, "disconnect")
    lvs_bad = run_lvs(link, placement, routes_bad)
    print(f"[5/5] LVS 签核（反例 · 断路 {killed[:28]}…）: {lvs_bad['verdict']}")
    check("LVS：注入断路 → REJECT（判决抓得住）",
          lvs_bad["verdict"] == "REJECT",
          f"verdict={lvs_bad['verdict']} viol={lvs_bad['n_violations']}")

    t_total = time.perf_counter() - t_start
    print("=" * 68)
    print(f"CPO 阵列演示：{_PASS} PASS / {_FAIL} FAIL · 全链 {t_total:.2f}s")

    # 报告落盘
    report = {
        "title": "CPO 共封装光引擎阵列（v0.9.2 · 阶段2 十万级真实器件样例）",
        "config": meta["config"],
        "n_devices": meta["n_devices"],
        "n_chains": meta["n_chains"],
        "n_nets": meta["n_nets"],
        "pitch_um": meta["pitch_um"],
        "wavelengths_nm": meta["wavelengths_nm"],
        "ring_radii_um": meta["ring_radii_um"],
        "n_eff": meta["n_eff"],
        "ring_order_m": meta["ring_order_m"],
        "device_mix": meta["device_mix"],
        "role_mix": meta["role_mix"],
        "drc": {"n_pass": drc["n_pass"], "n_checked": drc["n_checked"],
                "all_pass": drc["all_pass"]},
        "lvs": {"verdict": lvs["verdict"], "n_violations": lvs["n_violations"],
                "match": lvs["match"]},
        "lvs_fault_injection": {"net": killed,
                                "verdict": lvs_bad["verdict"],
                                "n_violations": lvs_bad["n_violations"]},
        "gds": gds_stats,
        "time_s": {"build_route": round(t_build, 2), "drc": round(t_drc, 2),
                   "lvs": round(t_lvs, 2), "total": round(t_total, 2)},
        "pass": _PASS, "fail": _FAIL,
        "accepted": bool(drc["all_pass"]
                         and lvs["verdict"] == "ACCEPT"
                         and lvs_bad["verdict"] == "REJECT"),
    }
    with open(out_dir / "cpo_array_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    mix = " · ".join(f"{k}×{v}" for k, v in meta["device_mix"].items())
    L = [
        "# CPO 共封装光引擎阵列报告（v0.9.2 · 阶段2）",
        "",
        f"- 架构：**{cfg.n_oe} 光引擎 × {cfg.n_ch} 波长通道 × {cfg.n_lane} 波长**"
        f" → **{meta['n_devices']:,} 器件 / {meta['n_chains']:,} 条独立光路**",
        f"- 器件构成：{mix}",
        f"- 波长栅格：LAN-WDM {cfg.n_lane} 波 "
        f"`{'` `'.join(str(w) for w in meta['wavelengths_nm'])}` nm",
        f"- 微环半径：n_eff={meta['n_eff']} · m={meta['ring_order_m']} → "
        f"`{'` `'.join(str(r) for r in meta['ring_radii_um'])}` µm"
        "（由谐振条件 m·λ = 2π·n_eff·R 反解）",
        f"- 网格 pitch：{meta['pitch_um'][0]} × {meta['pitch_um'][1]} µm",
    ]
    if gds_stats:
        L.append(f"- 芯片：{gds_stats['width_um']} × {gds_stats['height_um']} µm "
                 f"= {gds_stats['area_um2'] / 1e6:.2f} mm² · "
                 f"GDS {gds_stats['gds_bytes'] / 1e6:.2f} MB / "
                 f"{gds_stats['n_elements']:,} 元素 · IO {gds_stats['n_io']}")
    L += [
        f"- DRC：**{drc['n_pass']}/{drc['n_checked']} 通过**",
        f"- LVS：**{lvs['verdict']}**（{nm['n_nets_match']}/"
        f"{nm['n_nets_total']} 网一致 · 违规 {lvs['n_violations']}）",
        f"- 反例（注入断路）：**{lvs_bad['verdict']}**（违规 "
        f"{lvs_bad['n_violations']}）",
        f"- 全链耗时：**{t_total:.2f}s**（构建+放置+布线+DRC+LVS+GDS）",
        f"- 验收：**{'✅ ACCEPT' if report['accepted'] else '❌ REJECT'}**",
        "",
        "*诚实边界：仅建模无源光子层（有源器件激光器/探测器/驱动按黑箱，属"
        "负面清单）；工艺为公开文献近似非真实 PDK；本样例只做版图闭环，"
        "未做光学仿真验证；未流片、无实测回流。*",
    ]
    md_path = out_dir / "cpo_array_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"报告：{md_path}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
