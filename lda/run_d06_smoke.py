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
    seed_prov = corpus.get("E-SOI-NEFF-220").provenance
    assert seed_prov.get("contributor") == "seed", seed_prov
    assert seed_prov.get("source_file", "").endswith("seed_empirical.json"), seed_prov

    # ---- 构造临时 CSV：1 条新增 + 1 条重复 id（去重）+ 1 条坏数据 ----
    csv_text = (
        "id,device,metric,measured_value,uncertainty_abs,fab_source,citation,method,geometry,tags\n"
        "E-NEW-TEST,test waveguide,fsr,12.3,0.1,test fab,test cite,cutback,\"{}\",test\n"
        "E-SOI-NEFF-220,duplicate attempt,fsr,99.9,0.1,evil,evil cite,cutback,\"{}\",dup\n"  # 重复 id → conflict
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
        assert r.conflicts and r.conflicts[0][0] == "E-SOI-NEFF-220", r
        assert r.errors and r.errors[0][0] == "E-BAD-ROW", r
        # 去重生效：原 seed 值未被覆盖
        assert corpus.get("E-SOI-NEFF-220").measured_value == 2.63, "去重未生效"
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
    anchor = EmpiricalAnchor(corpus)
    v, src, note = anchor.resolve("E-SOI-NEFF-220")
    assert v == 2.63 and src == "empirical-measurement", (v, src)

    print("D-06 smoke ALL GREEN: corpus=%d, bank=%d, provenance OK"
          % (corpus.stats()["total"], bank.stats()["total"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
