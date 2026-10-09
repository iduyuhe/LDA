# -*- coding: utf-8 -*-
"""LDA · 光子计算 SoC 征程 G6 收官 — foundry NDA deck 替换机制 CI 门禁。

复用 S5 全链路拿到主权 GDS，验证「真实 foundry NDA deck 替换闭集」机制：
  - 基线：闭集默认 signoff（public 近似）仍全 PASS（不破坏既有能力）。
  - 替换（文件加载）：foundry 授权方按 schema 注入的 deck 被真加载、signoff 走该 deck。
  - 反向探针：合成一条更严规则（min_width=2.0µm）的 deck，判定**必须翻转**为
    not-ready，证明替换是「真走替换 deck」而非退回默认值（死测试自证护栏）。
  - env 注入：LDA_FOUNDRY_DECK 指向 deck 文件时 auto_env 自动加载。
  - 加载器护栏：provenance 非 NDA:/public: 开头的 deck 必须被拒绝。

🔴 诚实边界：本门禁**不持有任何 NDA 数值**；模板/合成 deck 均为 public 近似或
反向测试用途。真实 NDA deck 由 foundry 授权方提供，零改动经同一 schema 生效。
"""
from __future__ import annotations

import os
import sys
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import run_soc_s5_smoke as s5mod  # noqa: E402
from lda_l2 import soc_tapeout_signoff as ts  # noqa: E402

TEMPLATE_PATH = os.path.join(
    _ROOT, "examples", "sovereign_evidence", "foundry_deck_TEMPLATE.json")


def run_soc_tapeout_signoff_deck_smoke(N: int = 16, dac_bits: int = 16,
                                       seed: int = 20261009) -> dict:
    """返回 {all_pass, ...}。失败即抛 AssertionError（门禁红色）。"""
    # 复用 S5 全链路（一次构建 mesh，拿主权 GDS 路径）
    s5 = s5mod.run_soc_s5_smoke(N=N, dac_bits=dac_bits, seed=seed)
    assert s5["all_pass"], "NDA deck 替换前置失败：S5 全链路未全 PASS"
    gds_path = s5["gds_path"]

    # ① 基线：闭集默认（public 近似）signoff 仍全 PASS
    base = ts.tapeout_signoff_report(gds_path=gds_path)
    assert base["signoff_ready"] is True, "基线闭集 signoff 应 PASS"
    assert base["deck_source"] == "closed-set-public-approx", "基线 deck 来源应为闭集"
    assert base["n_rules_pass"] == base["n_rules_total"], "基线规则应全 PASS"

    # ② 替换（文件加载）：模板 deck 被真加载、signoff 走该 deck 且仍 PASS
    tmpl = ts.load_foundry_deck(TEMPLATE_PATH)
    assert tmpl.provenance.startswith("public:template-placeholder"), "模板 provenance 须 public:"
    swapped = ts.tapeout_signoff_report(gds_path=gds_path, deck=tmpl)
    assert swapped["signoff_ready"] is True, "模板 deck 替换后应 PASS（阈值与闭集等价）"
    assert swapped["deck_source"] == tmpl.name, "替换后 deck 来源应=模板名"
    assert all(r["prov"].startswith("public:") for r in swapped["per_rule"]), \
        "替换 deck 逐条 prov 须 public: 开头"

    # ③ 反向探针：合成更严 deck（SI min_width=2.0µm）→ 判定必须翻转 not-ready
    synth_rules = []
    for r in tmpl.rules:
        if r.rid == "FDRC-W-SI-MINWIDTH":
            r = ts.FoundryDRCRule(r.rid, r.foundry_layer, r.layer_name,
                                  r.kind, 2.0, r.prov)
        synth_rules.append(r)
    synth = ts.FoundryDeck("reverse-test-synthetic", tmpl.node,
                           "public:reverse-test-synthetic", synth_rules,
                           tmpl.spec_anchors)
    rev = ts.tapeout_signoff_report(gds_path=gds_path, deck=synth)
    si_rule = next(r for r in rev["per_rule"] if r["rid"] == "FDRC-W-SI-MINWIDTH")
    assert rev["signoff_ready"] is False, "反向探针：更严 deck 必须 flipping 为 not-ready"
    assert si_rule["pass"] is False, "反向探针：合成更严的 SI-MINWIDTH 规则必须判违规"
    assert rev["deck_source"] == "reverse-test-synthetic", "反向探针 deck 来源须=合成名"

    # ④ env 注入：LDA_FOUNDRY_DECK 指向模板 → auto_env 自动加载
    old_env = os.environ.get(ts.ENV_DECK_VAR)
    os.environ[ts.ENV_DECK_VAR] = TEMPLATE_PATH
    try:
        env_run = ts.tapeout_signoff_report(gds_path=gds_path, auto_env=True)
        assert env_run["deck_source"] == tmpl.name, "env 注入须自动加载模板 deck"
        assert env_run["signoff_ready"] is True, "env 注入模板后须 PASS"
    finally:
        if old_env is None:
            os.environ.pop(ts.ENV_DECK_VAR, None)
        else:
            os.environ[ts.ENV_DECK_VAR] = old_env

    # ⑤ 加载器护栏：provenance 非 NDA:/public: 开头 → 拒绝
    bad = {"name": "fake", "node": "x", "provenance": "fake-deck",
           "rules": [{"rid": "X", "foundry_layer": 1, "layer_name": "SI",
                      "kind": "min_width", "thr_um": 0.12, "prov": "fake"}]}
    raised = False
    try:
        ts.load_foundry_deck(bad)
    except ValueError:
        raised = True
    assert raised, "加载器护栏：provenance 非 NDA:/public: 必须拒绝"

    all_pass = True
    return {
        "all_pass": all_pass,
        "s5_all_pass": s5["all_pass"],
        "gds_path": gds_path,
        "baseline_signoff_ready": base["signoff_ready"],
        "swapped_signoff_ready": swapped["signoff_ready"],
        "swapped_deck_source": swapped["deck_source"],
        "reverse_test_signoff_ready": rev["signoff_ready"],
        "reverse_test_si_minwidth_pass": si_rule["pass"],
        "env_inject_deck_source": env_run["deck_source"],
        "loader_guardrail_rejected": raised,
        "honest_boundary": (
            "本门禁不持有 NDA 数值；模板/合成 deck 均为 public 近似或反向测试。"
            "真实 NDA deck 由 foundry 授权方按 FoundryDeck schema 提供，零改动生效。"
        ),
    }


def _main():
    ap = argparse.ArgumentParser(description="SoC G6 收官 · foundry NDA deck 替换机制门禁")
    ap.add_argument("--N", type=int, default=int(os.environ.get("LDA_G6D_N", "16")))
    ap.add_argument("--dac-bits", type=int, default=16)
    ap.add_argument("--seed", type=int, default=20261009)
    args = ap.parse_args()
    rep = run_soc_tapeout_signoff_deck_smoke(N=args.N, dac_bits=args.dac_bits, seed=args.seed)
    print("=== SoC G6 收官 · foundry NDA deck 替换机制门禁 ===")
    for k, v in rep.items():
        if k != "honest_boundary":
            print(f"  {k}: {v}")
    print(f"  honest_boundary: {rep['honest_boundary']}")
    print(f"ALL_PASS = {rep['all_pass']}")
    return 0 if rep["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(_main())
