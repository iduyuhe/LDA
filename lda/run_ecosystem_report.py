"""D-93 生态共建框架 · 验收报告生成。

汇总：harness 题库全量 PASS + 新题 B14-B18 物理值/tol +
PDK 主权分级 A/B/C 落地 + Registry 接口自洽。输出 reports/ecosystem_d93.json。

运行：python run_ecosystem_report.py（managed python，零外部依赖 · **任意 cwd**）

🔴 v0.9.194：原先 `sys.path.insert(0, ".")` 与 `out = "lda/reports/..."` 都依赖 cwd，
且**两者的正确 cwd 互斥**（导入要 cwd=lda，产物位置要 cwd=仓库根）⇒ 按 docstring
直接跑会写到 `lda/lda/reports/` 这种错误位置。现全部锚定脚本自身位置 / 仓库根。

🔴 v0.9.197（D-93 报告漂移专项）：本报告此前用**裸 `json.dump`**（Windows 还写 CRLF）
且**钉在 `run_report_determinism_smoke._KNOWN_UNREGISTERED` 基线**里（不受 ⑧b 覆盖），
入库快照停在 2026-08-24（harness 18 题 / B14=15.5 / B16=18.58 / 主权 16），与当前
仓库状态漂移。现：
  ① 落盘改走**唯一确定性口径** `deterministic.write_json`（canon 剔 volatile + 浮点 9 位
     有效数字 + LF）；② 登记进 `lint_spec`（从 `_KNOWN_UNREGISTERED` 移除）；
  ③ `run_ecosystem_smoke` 新增「**报告快照 == 仓库现算**」常驻判据 ⇒ 再落后必红。
字段 `date` 更名为 `d93_delivery_date`（语义 = D-93 交付日，不随重生成变化），
并加 `snapshot_note` 显式说明数值为「最近一次生成时的当前状态」。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)

from lda_harness import deterministic as det
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
        "d93_delivery_date": "2026-08-24",
        "snapshot_note": (
            "本报告的数值与计数为「最近一次生成时」的仓库当前状态"
            "（B14-B18 物理值 / 全量 harness 计数与全过标志 / 主权依赖分级），"
            "由 `run_ecosystem_smoke` 的「报告快照 == 仓库现算」判据强制同步 —— "
            "改 golden 或加锚后未重生成本报告 ⇒ CI 必红。"
            "D-93 交付当日（2026-08-24）的历史口径见 CHANGELOG。"),
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

    out = os.path.join(_ROOT, "lda", "reports", "ecosystem_d93.json")
    det.write_json(out, report)
    print("PASS:", acceptance["passed"])
    print("harness: %d/%d | 新题: %s" % (n_pass, len(specs), list(new_values)))
    print("PDK A/B/C: %d/%d/%d (总 %d)" % (
        pdk["by_class"]["A"], pdk["by_class"]["B"], pdk["by_class"]["C"],
        pdk["sovereign_deps_total"]))
    print("[written] %s" % out)
    return 0 if acceptance["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
