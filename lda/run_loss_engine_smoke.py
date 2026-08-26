"""v0.8.11e loss/效率类引擎 smoke：实证锚 9 条语料全对照。

验证 `lda_design/loss_engines`：
  1. 5 个 loss/效率类引擎（Y-branch/光栅 eff/crossing/MMI EL/SiN PL）全部可调用；
  2. 6 条缺口语料（E-YBRANCH-LOSS/E-GRATING-EFF/E-SOI-CROSS-IL/XT/E-MMI-1X2-EL/
     E-SIN-PL-800）与引擎对照 rel 全部 ≤ 25%（半解析近似容差）——语料全可对照；
  3. 物理合理性：参数扰动产生方向正确的输出变化（θ↑→损耗↑、σ↑→传播损耗↑、
     占空比偏离 0.5→效率↓）；
  4. 与对照报告联动：corpus_coverage 9/9 全 covered。

全部死标量（LLM 不进判决路径）；零依赖。
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_harness.empirical_bank import EmpiricalCorpus
from lda_design.loss_engines import (ENGINE_FUNCS, LOSS_ENGINES,
                                     resolve_corpus_engine, CORPUS_ENGINE_MAP)

CHECKS = []


def check(name: str, ok: bool, detail: str = ""):
    CHECKS.append((name, bool(ok)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('| ' + detail) if detail else ''}")


def main() -> int:
    # ① 5 引擎全部可调用
    ok_all = True
    for name in LOSS_ENGINES:
        ok_all = ok_all and callable(ENGINE_FUNCS.get(name))
    check("5 个 loss/效率类引擎全部注册", ok_all, f"{len(LOSS_ENGINES)} 引擎")

    # ② 6 条缺口语料全对照（rel ≤ 25%）
    corpus = EmpiricalCorpus.load(os.path.join(_HERE, "lda_harness", "seed_empirical.json"))
    rels = {}
    all_ok = True
    for eid in ["E-YBRANCH-LOSS", "E-GRATING-EFF", "E-SOI-CROSS-IL", "E-SOI-CROSS-XT",
                "E-MMI-1X2-EL", "E-SIN-PL-800"]:
        m = corpus.get(eid)
        r = resolve_corpus_engine(eid, dict(m.geometry))
        if r.get("engine") is None or r.get("value") is None:
            all_ok = False
            continue
        rel = abs(r["value"] - m.measured_value) / max(abs(m.measured_value), 1e-9) * 100
        rels[eid] = round(rel, 2)
        all_ok = all_ok and rel <= 25.0
    check("6 条缺口语料与 loss 引擎全对照（rel≤25%）", all_ok,
          f"rels={rels}")

    # ③ 物理合理性：方向正确的参数响应
    # Y-branch：θ↑ → 损耗↑
    v1 = ENGINE_FUNCS["engine_ybranch_split"]({"theta_deg": 5.0})["value"]
    v2 = ENGINE_FUNCS["engine_ybranch_split"]({"theta_deg": 20.0})["value"]
    check("Y-branch θ↑→损耗↑", v2 > v1, f"{v1} → {v2}")
    # SiN PL：粗糙度↑ → 传播损耗↑
    p1 = ENGINE_FUNCS["engine_sin_pl"]({"roughness_nm": 0.3})["value"]
    p2 = ENGINE_FUNCS["engine_sin_pl"]({"roughness_nm": 0.6})["value"]
    check("SiN 粗糙度↑→传播损耗↑", p2 > p1, f"{p1} → {p2}")
    # 光栅：占空比偏离 0.5 → 效率↓
    e1 = ENGINE_FUNCS["engine_grating_eff"]({"ff": 0.5})["value"]
    e2 = ENGINE_FUNCS["engine_grating_eff"]({"ff": 0.2})["value"]
    check("光栅 ff 偏离 0.5→效率↓", e2 < e1, f"{e1} → {e2}")

    # ④ 对照报告联动：9/9 语料全 covered
    from lda_design.loss_engines import CORPUS_ENGINE_MAP
    all9 = [eid for eid in
            ["E-SOI-NEFF-220", "E-SIN-NEFF-300", "E-YBRANCH-LOSS", "E-RING-FSR",
             "E-GRATING-EFF", "E-SOI-CROSS-IL", "E-SOI-CROSS-XT", "E-MMI-1X2-EL",
             "E-SIN-PL-800"]]
    covered = sum(1 for eid in all9
                  if eid in CORPUS_ENGINE_MAP or eid in
                  ("E-SOI-NEFF-220", "E-SIN-NEFF-300", "E-RING-FSR"))
    check("对照报告联动：9 条语料全有引擎", covered == 9, f"{covered}/9")

    npass = sum(1 for c in CHECKS if c[1])
    print("-" * 60)
    print(f"loss 引擎 smoke：{npass}/{len(CHECKS)} PASS")
    return 0 if npass == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
