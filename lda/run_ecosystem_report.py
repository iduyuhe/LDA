"""D-93 生态共建框架 · 验收报告生成。

汇总：harness 题库 B1-B18 全量 PASS + 新题 B14-B18 物理值/tol +
PDK 主权分级 A/B/C 落地 + Registry 接口自洽。输出 reports/ecosystem_d93.json。

运行：python run_ecosystem_report.py（managed python，零外部依赖）
"""
import sys
import json
sys.path.insert(0, ".")

from lda_harness.golden import (b14_dc_coupling_length, b15_bragg_wavelength,
    b16_mmi_length, b17_jj_critical_current, b18_purcell_factor)
from lda_harness.verification_adapters import build_harness_specs
from lda_harness.verification_spec import run_verification
from lda_pdk import PDKRegistry, DeviceEntry, SOVEREIGN_DEPS, by_class


def main():
    # ---- 新题物理值 + tol ----
    new_defs = {
        "B14": {"fn": b14_dc_coupling_length,
                "params": {"n_e": 2.45, "n_o": 2.40, "wl": 1.55},
                "tol": 0.5, "metric": "L_3dB_um",
                "note": "拍波长法 L=λ0/(2|n_e−n_o|)"},
        "B15": {"fn": b15_bragg_wavelength,
                "params": {"n_eff": 2.4, "period": 0.323},
                "tol": 0.01, "metric": "lambda_B_um",
                "note": "一阶 Bragg 条件 λ_B=2·n_eff·Λ"},
        "B16": {"fn": b16_mmi_length,
                "params": {"W_e": 2.0, "n_eff": 2.4, "wl": 1.55},
                "tol": 3.0, "metric": "L_mmi_um",
                "note": "L=3·L_π，L_π=n_eff·W_e²/λ0（设计守则锚）"},
        "B17": {"fn": b17_jj_critical_current,
                "params": {"E_J_ghz": 20.0},
                "tol": 1e-9, "metric": "I_c_A",
                "note": "I_c=2e·E_J/ℏ=E_J·1e9·4π·e（约瑟夫森关系）"},
        "B18": {"fn": b18_purcell_factor,
                "params": {"g_ghz": 0.1, "kappa_ghz": 0.005, "gamma_ghz": 0.001},
                "tol": 1.0, "metric": "F_purcell",
                "note": "F_P=4g²/(κ·γ_1)（腔 QED 增强因子）"},
    }
    new_values = {}
    for bid, d in new_defs.items():
        val = d["fn"](**d["params"])
        new_values[bid] = {
            "metric": d["metric"], "value": val, "tol": d["tol"],
            "params": d["params"], "note": d["note"],
            "oracle": "analytical(physical-law)",
        }

    # ---- harness 全量 ----
    specs, cand = build_harness_specs()
    n_pass = sum(1 for s in specs if run_verification(s, cand[s.spec_id]).passed)
    harness = {
        "total": len(specs),
        "passed": n_pass,
        "new_benchmarks": ["B14", "B15", "B16", "B17", "B18"],
        "all_pass": n_pass == len(specs),
    }

    # ---- PDK 主权分级 ----
    pdk = {
        "sovereign_deps_total": len(SOVEREIGN_DEPS),
        "by_class": {
            "A": len(by_class("A")),
            "B": len(by_class("B")),
            "C": len(by_class("C")),
        },
        "class_A_names": [d.name for d in by_class("A")],
        "class_B_names": [d.name for d in by_class("B")],
        "class_C_names": [d.name for d in by_class("C")],
    }
    # Registry 接口自洽（注册/查询/冲突）
    reg = PDKRegistry()
    reg.add(DeviceEntry(id="seed_soi_dc", name="种子 SOI 定向耦合器",
                        tech="SOI", foundry="self", sovereign_class="B",
                        tags=["coupler"]))
    conflict = reg.add(DeviceEntry(id="seed_soi_dc", name="重复",
                                   tech="SOI", foundry="self",
                                   sovereign_class="B"))
    reg_stats = reg.stats()
    registry_ok = (conflict == "conflict" and reg_stats["total"] == 1)

    acceptance = {
        "passed": bool(harness["all_pass"]
                       and pdk["by_class"]["A"] >= 4
                       and pdk["by_class"]["B"] >= 6
                       and pdk["by_class"]["C"] >= 4
                       and registry_ok),
        "checks": {
            "harness_B1_B18_all_pass": harness["all_pass"],
            "pdk_class_A_ge_4": pdk["by_class"]["A"] >= 4,
            "pdk_class_B_ge_6": pdk["by_class"]["B"] >= 6,
            "pdk_class_C_ge_4": pdk["by_class"]["C"] >= 4,
            "registry_add_conflict_self_consistent": registry_ok,
        },
    }

    report = {
        "d93": "生态共建框架（harness 题库扩充 B14-B18 + PDK Registry/L2 开放标准接口）",
        "date": "2026-08-24",
        "honest_boundary": (
            "harness 题库 B14-B18 为确定性物理定律锚（能力圈内，立即落地）；"
            "PDK Registry 为 L2 开放标准接口框架 + 主权依赖分级 A/B/C 代码化"
            "（系统开发可做）；真实晶圆厂 PDK 对接/实测语料采集属发动期事项"
            "（D-62 联动），暂缓，不在此硬编码。"),
        "harness": harness,
        "new_benchmark_values": new_values,
        "pdk_sovereign": pdk,
        "pdk_registry_interface": {
            "ok": registry_ok,
            "stats": reg_stats,
            "note": "Registry 仅承载器件本体元数据（几何/工艺/来源），"
                    "真实 PDK 数据经 empirical_submit 同源入口流入。",
        },
        "acceptance": acceptance,
    }

    out = "lda/reports/ecosystem_d93.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("PASS:", acceptance["passed"])
    print("harness: %d/%d | 新题: %s" % (n_pass, len(specs), list(new_values)))
    print("PDK A/B/C: %d/%d/%d (总 %d)" % (
        pdk["by_class"]["A"], pdk["by_class"]["B"], pdk["by_class"]["C"],
        pdk["sovereign_deps_total"]))
    print("[written] %s" % out)
    return 0 if acceptance["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
