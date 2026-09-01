#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D-06 实证语料库增量导入冒烟：验证 csv/JSON 批量导入、去重、溯源。

纯静态（不跑求解器），CI 友好。覆盖：
  1. 加载 seed_empirical.json 正常（provenance 向后兼容为空）
  2. 新增记录走 csv 导入 → added
  3. 重复 id → conflict（去重生效，保留原值）
  4. 解析错误行 → errors
  5. JSON 批量导入 + 溯源 provenance 被填充
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lda_harness.empirical_bank import (  # noqa: E402
    EmpiricalCorpus, AdversarialBenchmarkBank, EmpiricalAnchor, ImportResult,
)


def main():
    seed = os.path.join(HERE, "lda_harness", "seed_empirical.json")
    assert os.path.exists(seed), f"seed 缺失: {seed}"

    corpus = EmpiricalCorpus.load(seed)
    n = corpus.stats()["total"]
    assert n >= 5, corpus.stats()  # v0.8.11 语料扩充 5→9（动态下限防漂移）
    # 溯源：seed 记录加载后 contributor 标记为 seed，source_file 指向 seed 文件
    # D-66：E-SOI-NEFF-220 已改判为 E-SOI-NG-220（n_eff=2.63 系错值，改判 n_g 实测锚）
    seed_prov = corpus.get("E-SOI-NG-220").provenance
    assert seed_prov.get("contributor") == "seed", seed_prov
    assert seed_prov.get("source_file", "").endswith("seed_empirical.json"), seed_prov

    # ---- 构造临时 CSV：1 条新增 + 1 条重复 id（去重）+ 1 条坏数据 ----
    csv_text = (
        "id,device,metric,measured_value,uncertainty_abs,fab_source,citation,method,geometry,tags\n"
        "E-NEW-TEST,test waveguide,fsr,12.3,0.1,test fab,test cite,cutback,\"{}\",test\n"
        "E-SOI-NG-220,duplicate attempt,fsr,99.9,0.1,evil,evil cite,cutback,\"{}\",dup\n"  # 重复 id → conflict
        "E-BAD-ROW,bad device,fsr,not_a_number,0.1,fab,cite,,,,test\n"  # measured_value 非数值 → error
    )
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False,
                                     encoding="utf-8", newline="") as f:
        f.write(csv_text)
        csv_path = f.name
    try:
        r = corpus.import_csv(csv_path, contributor="smoke")
        print("csv import:", r)
        assert r.added == 1, r
        assert r.conflicts and r.conflicts[0][0] == "E-SOI-NG-220", r
        assert r.errors and r.errors[0][0] == "E-BAD-ROW", r
        # 去重生效：原 seed 值未被覆盖（D-66：E-SOI-NG-220 实测 n_g = 4.18）
        assert corpus.get("E-SOI-NG-220").measured_value == 4.18, "去重未生效"
        # 溯源填充
        new = corpus.get("E-NEW-TEST")
        assert new.provenance.get("contributor") == "smoke", new.provenance
        assert new.provenance.get("source_file", "").endswith(".csv"), new.provenance
        assert "imported_at" in new.provenance, new.provenance
    finally:
        os.unlink(csv_path)

    # ---- JSON 批量导入（含一条新对抗题） ----
    json_text = json.dumps({
        "adversarial": [{
            "id": "A-NEW-SMOKE", "title": "smoke 新对抗题", "desc": "x",
            "target_metric": "T", "oracle_type": "fdtd", "tol": 0.1,
            "submitted_by": "smoke", "tags": ["smoke"],
        }]
    })
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as f:
        f.write(json_text)
        j_path = f.name
    try:
        bank = AdversarialBenchmarkBank.load(seed)
        before = bank.stats()["total"]
        r2 = bank.import_json(j_path, contributor="smoke")
        print("json import:", r2)
        assert r2.added == 1, r2
        assert bank.stats()["total"] == before + 1
        assert bank.get("A-NEW-SMOKE").provenance.get("contributor") == "smoke"
    finally:
        os.unlink(j_path)

    # ---- 锚接入仍可用 ----
    # D-66：E-SOI-NEFF-220（B 级、n_eff=2.63 系错值）已改判为 **A 级** E-SOI-NG-220
    # （n_g=4.18±0.05，arXiv:2011.03273 racetrack 实测 FSR 反演，含 DOI）
    # → 默认红线门禁**放行**作 golden 进判决路径。
    anchor = EmpiricalAnchor(corpus)
    v0, src0, note0 = anchor.resolve("E-SOI-NG-220")
    assert v0 == 4.18 and src0 == "empirical-measurement", (v0, src0)
    assert "tier=A" in note0, note0

    # B 级门禁：seed 语料库 D-66 后 B 级已清零（30/30 全 A），已无真实 B 级样本。
    # 用**合成 B 级语料**（citation 仅文本描述、无 DOI/arXiv/URL 定位符）验证门禁机制：
    # 默认拒作 golden；显式 require_traceable=False 时降级取值并标注 tier=B。
    # （不能用「库里没有 B 级」当作门禁通过——缺样本 ≠ 门禁有效。）
    b_corpus = EmpiricalCorpus([{
        "id": "E-SYNTH-B-1", "device": "synthetic", "metric": "m",
        "measured_value": 1.0, "uncertainty_abs": 0.1, "fab_source": "X",
        "citation": "某公开文献典型量级（无 DOI/arXiv/URL 定位符，仅文本描述）",
        "method": "未标注", "geometry": {}, "tags": [],
    }])
    b_anchor = EmpiricalAnchor(b_corpus)
    vb, srcb, _ = b_anchor.resolve("E-SYNTH-B-1")
    assert vb is None and srcb == "empirical-untraceable", (vb, srcb)
    v, src, note = b_anchor.resolve("E-SYNTH-B-1", require_traceable=False)
    assert v == 1.0 and src == "empirical-B-untraceable", (v, src)
    assert "tier=B" in note, note

    print("D-06 smoke ALL GREEN: corpus=%d, bank=%d, provenance OK"
          "（含 D-63 溯源门禁：A 级 E-SOI-NG-220 放行作 golden；"
          "合成 B 级默认拒、显式降级才可取）"
          % (corpus.stats()["total"], bank.stats()["total"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
