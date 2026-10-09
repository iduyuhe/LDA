# -*- coding: utf-8 -*-
"""LDA · 光子计算 SoC 征程 S5-ext — 真实 foundry PDK 对接机制 CI 门禁。

复用 S5 全链路拿到主权 GDS，验证「S5-ext 真实 PDK 对接」机制：
  - ① 默认 PDK（AIM 公开近似）符合性：conformant + all_mapped。
  - ② 多 foundry 注册表覆盖：AIM/Tower/GF/imec 四家公开近似 PDK 均 conformant
        （证明多 foundry 注册表真能跑，非单一家硬编码）。
  - ③ 替换（文件加载）：foundry 授权方按 schema 注入的 PDK（模板 JSON）被真加载、
       符合性走该 PDK 且仍 conformant；逐条 prov 须 public:/NDA: 开头。
  - ④ 反向探针：合成更严 PDK（SI min_width=2.0µm）→ 符合性**必须翻转**为
        not-conformant，证明替换是「真走替换 PDK」而非退回默认值（死测试自证护栏）。
  - ⑤ 加载器护栏：provenance 非 NDA:/public: 开头的 PDK 必须被拒绝。

🔴 诚实边界：本门禁**不持有任何 NDA 数值**；模板/合成 PDK 均为 public 近似或
反向测试用途。真实 NDA PDK 由 foundry 授权方提供，零改动经同一 schema 生效。
"""
from __future__ import annotations

import os
import sys
import argparse
import copy

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import run_soc_s5_smoke as s5mod  # noqa: E402
from lda_l2 import foundry_pdk_registry as reg  # noqa: E402

TEMPLATE_PATH = os.path.join(
    _ROOT, "examples", "sovereign_evidence", "foundry_pdk_TEMPLATE.json")


def run_soc_pdk_integration_smoke(N: int = 16, dac_bits: int = 16,
                                 seed: int = 20261009,
                                 default_pdk: str = "AIM Photonics") -> dict:
    """返回 {all_pass, ...}。失败即抛 AssertionError（门禁红色）。"""
    # 复用 S5 全链路（一次构建 mesh，拿主权 GDS 路径）
    s5 = s5mod.run_soc_s5_smoke(N=N, dac_bits=dac_bits, seed=seed)
    assert s5["all_pass"], "PDK 对接前置失败：S5 全链路未全 PASS"
    gds_path = s5["gds_path"]

    # ① 默认 PDK（AIM 公开近似）符合性
    pdk0 = reg.get_pdk(default_pdk)
    rep0 = reg.pdk_conformance_report(gds_path, pdk0)
    assert rep0["conformant"] is True, "默认 PDK 符合性应 conformant"
    assert rep0["all_mapped"] is True, "默认 PDK 层映射应 all_mapped"
    assert rep0["pdk_provenance"].startswith("public:"), "默认 PDK provenance 须 public:"

    # ② 多 foundry 注册表覆盖（AIM/Tower/GF/imec 均 conformant）
    registry_conformant = {}
    for name in reg.pdk_registry_names():
        r = reg.pdk_conformance_report(gds_path, reg.get_pdk(name))
        registry_conformant[name] = bool(r["conformant"])
        assert r["conformant"] is True, f"注册表 PDK {name} 应 conformant"
        assert r["pdk_provenance"].startswith("public:"), f"{name} provenance 须 public:"

    # ③ 替换（文件加载）：模板 PDK 被真加载、符合性走该 PDK 且仍 conformant
    tmpl = reg.load_foundry_pdk(TEMPLATE_PATH)
    assert tmpl.provenance == "public:template-placeholder", "模板 provenance 须 public:"
    swapped = reg.pdk_conformance_report(gds_path, tmpl)
    assert swapped["conformant"] is True, "模板 PDK 替换后应 conformant（窗口与默认等价）"
    assert swapped["all_mapped"] is True, "模板 PDK 层映射应 all_mapped"
    assert all(L.prov.startswith("public:") for L in tmpl.layers), \
        "替换 PDK 逐层 prov 须 public: 开头"

    # ④ 反向探针：合成更严 PDK（SI min_width=2.0µm）→ 符合性必须翻转 not-conformant
    synth = copy.deepcopy(pdk0)
    for L in synth.layers:
        if L.sovereign_layer == 1:
            L.min_width_um = 2.0
    rev = reg.pdk_conformance_report(gds_path, synth)
    si_layer = next(r for r in rev["per_layer"] if r["sovereign_layer"] == 1)
    assert rev["conformant"] is False, "反向探针：更严 PDK 必须 flipping 为 not-conformant"
    assert si_layer["min_feature_ok"] is False, "反向探针：SI 层最小特征必须判违规"

    # ⑤ 加载器护栏：provenance 非 NDA:/public: 开头 → 拒绝
    bad = {"foundry": "fake", "node": "x", "provenance": "fake-pdk",
           "layers": [{"sovereign_layer": 1, "foundry_layer": 1, "purpose": "Si",
                       "min_width_um": 0.12, "typ_width_um": 0.45,
                       "max_width_um": 20.0, "prov": "fake"}],
           "primitives": []}
    raised = False
    try:
        reg.load_foundry_pdk(bad)
    except ValueError:
        raised = True
    assert raised, "加载器护栏：provenance 非 NDA:/public: 必须拒绝"

    return {
        "all_pass": True,
        "s5_all_pass": s5["all_pass"],
        "gds_path": gds_path,
        "default_pdk": default_pdk,
        "default_conformant": rep0["conformant"],
        "default_all_mapped": rep0["all_mapped"],
        "registry_conformant": registry_conformant,
        "swapped_conformant": swapped["conformant"],
        "swapped_pdk_provenance": swapped["pdk_provenance"],
        "reverse_test_conformant": rev["conformant"],
        "reverse_test_si_min_feature_ok": si_layer["min_feature_ok"],
        "loader_guardrail_rejected": raised,
        "honest_boundary": (
            "本门禁不持有 NDA 数值；模板/合成 PDK 均为 public 近似或反向测试。"
            "真实 NDA PDK 由 foundry 授权方按 FoundryPDK schema 提供，零改动生效。"),
    }


def _main():
    ap = argparse.ArgumentParser(description="SoC S5-ext · 真实 foundry PDK 对接机制门禁")
    ap.add_argument("--N", type=int, default=int(os.environ.get("LDA_PDK_N", "16")))
    ap.add_argument("--dac-bits", type=int, default=16)
    ap.add_argument("--seed", type=int, default=20261009)
    ap.add_argument("--pdk", type=str, default="AIM Photonics")
    args = ap.parse_args()
    rep = run_soc_pdk_integration_smoke(N=args.N, dac_bits=args.dac_bits,
                                        seed=args.seed, default_pdk=args.pdk)
    print("=== SoC S5-ext · 真实 foundry PDK 对接机制门禁 ===")
    for k, v in rep.items():
        if k != "honest_boundary":
            print(f"  {k}: {v}")
    print(f"  honest_boundary: {rep['honest_boundary']}")
    print(f"ALL_PASS = {rep['all_pass']}")
    return 0 if rep["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(_main())
