# -*- coding: utf-8 -*-
"""N-5 验证成熟度模型（VMM）底线护栏（v0.9.62）。

🔴 背景：B16 假绿事件证明「想多报一个数」的诱惑真实存在，且自证桩里 golden 本身可能
   算错（B16 因子 3 错 33%）。VMM（docs/verification_maturity_model.md）把「自证」定为
   合法第一阶段，但要求每锚**诚实标注来源 + 带升级路径 + 守底线**。本护栏把底线 6 条中
   可机器化的一条固化进 CI：每锚必须有 maturity_tier / provenance，且 Tier-1 必含
   upgrade_path；声明层级须与 harness 权威分类一致（防越级谎报）；self_authored_closed_form
   （纯未验自写闭式）自动进「低置信·待再审计」名单（防 B16 型安静翻车）；design_rule_anchor
   与 self_authored_closed_form_with_check 不进低置信名单（前者为外部来源、后者已内验）。

护栏：
  M1 每锚含 maturity_tier + provenance 字段。
  M2 Tier-1（自证）必含非空 upgrade_path（否则=无路线，违反底线 6）。
  M3 声明 maturity_tier ≡ harness 权威三分类（strict/degraded/self_certified），
     越级谎报即 FAIL（同 C2 防标签≠行为）。
  M4 provenance=self_authored_closed_form（纯未验自写闭式）的锚落入「低置信·待再审计」名单并显式披露
     （信息项，不 FAIL——已内验的 self_authored_closed_form_with_check 与行业 design_rule_anchor 不进此名单）。
  M5 三分类计数与 README/C2 口径一致（26/1/25，和=52）。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from lda_harness.benchmarks import BENCHMARK_DEFS


def _harness_classify():
    """复刻 IndependentCandidateRouter.candidate_class 的权威分类。"""
    from lda_harness.verification_adapters import BENCHMARK_CANDIDATES
    strict = deg = stub = 0
    for bid in BENCHMARK_DEFS:
        d = BENCHMARK_DEFS[bid]
        k = d.get("candidate")
        if d.get("candidate_status") == "degraded_ordinal":
            deg += 1
        elif k and k in BENCHMARK_CANDIDATES:
            strict += 1
        else:
            stub += 1
    return strict, deg, stub


def main():
    fails = []
    infos = []

    # M1 + M2 + M4 逐锚检查
    low_conf = []
    with_check = []
    for bid, d in BENCHMARK_DEFS.items():
        if "maturity_tier" not in d:
            fails.append(f"M1 {bid}: 缺 maturity_tier")
        if "provenance" not in d:
            fails.append(f"M1 {bid}: 缺 provenance")
        if d.get("maturity_tier") == "self_certified":
            if not d.get("upgrade_path"):
                fails.append(f"M2 {bid}: Tier-1 缺 upgrade_path")
        pv = d.get("provenance")
        if pv == "self_authored_closed_form":
            low_conf.append(bid)
        elif pv == "self_authored_closed_form_with_check":
            with_check.append(bid)

    # M3 声明层级 ≡ harness 权威分类
    h_strict, h_deg, h_stub = _harness_classify()
    decl = {"strict_independent": 0, "degraded": 0, "self_certified": 0}
    for d in BENCHMARK_DEFS.values():
        t = d.get("maturity_tier")
        if t in decl:
            decl[t] += 1
        else:
            fails.append(f"M3 非法 maturity_tier={t}")
    if decl["strict_independent"] != h_strict:
        fails.append(f"M3 strict 声明{h_strict}≠harness{h_strict}")
    if decl["degraded"] != h_deg:
        fails.append(f"M3 degraded 声明{decl['degraded']}≠harness{h_deg}")
    if decl["self_certified"] != h_stub:
        fails.append(f"M3 self_certified 声明{decl['self_certified']}≠harness{h_stub}")

    # M5 计数一致性
    total = len(BENCHMARK_DEFS)
    if h_strict + h_deg + h_stub != total:
        fails.append(f"M5 三分类和 {h_strict+h_deg+h_stub}≠题数 {total}")
    if (h_strict, h_deg, h_stub) != (26, 1, 25):
        infos.append(f"M5 三分类口径=({h_strict},{h_deg},{h_stub})（期望 (26,1,25)）")

    # 输出
    print("=" * 64)
    print("N-5 验证成熟度模型（VMM）底线护栏")
    print("=" * 64)
    print(f"[M1] 每锚字段完整性：{'PASS' if not any('M1' in f for f in fails) else 'FAIL'}")
    print(f"[M2] Tier-1 必含 upgrade_path：{'PASS' if not any('M2' in f for f in fails) else 'FAIL'}")
    print(f"[M3] 声明层级 ≡ harness 权威分类：{'PASS' if not any('M3' in f for f in fails) else 'FAIL'}")
    print(f"[M4] 低置信未验自写闭式锚（待再审计，不含 design_rule_anchor/with_check）：{len(low_conf)} 道 -> {','.join(sorted(low_conf))}")
    print(f"[M4+] 已内验自写闭式锚（中置信·非低）：{len(with_check)} 道 -> {','.join(sorted(with_check))}")
    print(f"[M5] 三分类口径：strict={h_strict} degraded={h_deg} self_certified={h_stub} 和={total}")
    if infos:
        for i in infos:
            print(f"  [INFO] {i}")

    if fails:
        print("\n[FAIL] 底线护栏未通过：")
        for f in fails:
            print("  -", f)
        return 1
    print("\n[PASS] VMM 底线护栏全部通过（maturity_tier/provenance/upgrade_path 齐备、层级不谎报、低置信可见）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
