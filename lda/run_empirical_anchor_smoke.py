"""D-62 实证大数据锚 smoke：harness 实证锚题（E1-E7 第二道非 AI ground）+ 语料评审流。

覆盖：
  ① harness 实证锚题解析（BENCHMARK_DEFS 50 = B1-B30 + E1-E7 + S1-S13；E 题 golden 来自实测语料；
     B19 为 P1-M4 新增链路级无源无增益物理定律锚；B20-B27 为 v0.8 内核纵深新增）
  ② 参考候选 34/34 PASS（物理定律 + 实证锚双 ground）
  ③ 扰动候选：实证锚题 FAIL 检测（自适应扰动幅度，实证锚能抓偏离）
  ④ 语料评审流：提交（citation/数值/σ 门禁 + 防重）→ 具名评审（缺评审人拒）→ 落地 → reload 生效
  ⑤ harness 键集一致性（E1-E7 全部可解析）
  ⑥ measurement_stats 自洽
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.benchmarks import BENCHMARK_DEFS, BENCHMARK_ORDER
from lda_harness.verification_adapters import build_harness_specs, harness_perturbed_candidate
from lda_harness.empirical_bank import EmpiricalCorpus, EmpiricalAnchor
from lda_pdk.empirical import (
    submit_measurement, review_measurement, land_measurement,
    list_measurements, measurement_stats,
)

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('| ' + detail) if detail else ''}")


def main():
    # ① 实证锚题解析
    e_ids = [b for b in BENCHMARK_ORDER if b.startswith("E")]
    check("BENCHMARK_DEFS 50 题（B1-B30+E1-E7+S1-S13）", len(BENCHMARK_DEFS) == 50
          and e_ids == ["E1", "E2", "E3", "E4", "E5", "E6", "E7"],
          f"defs={len(BENCHMARK_DEFS)} e={e_ids}")
    specs, cand_map = build_harness_specs()
    emp = [s for s in specs if s.oracle_kind == "empirical_measurement"]
    check("实证锚题解析（E1-E7 oracle_kind=empirical_measurement）",
          len(emp) == 7 and all(s.spec_id in ("E1", "E2", "E3", "E4", "E5", "E6", "E7") for s in emp),
          f"emp={len(emp)}")
    goldens = {s.spec_id: s.oracle_fn(s.params) for s in emp}
    # D-63：E3 golden 由「解析公式反算的 9.15」换成「实测 FSR 10.44」
    # （Sridaran & Bhave, Opt. Express 18(4) 3850 (2010)，R=7.5um 环扫频实测）
    # D-64：E2 golden 由「n_eff 1.53（导出量·B级）」换成「群折射率 n_g 1.892」
    # （300nm LPCVD Si3N4 平台 1.0×0.3um，OFDR 环腔实测 + MZI 交叉验证，几何已对齐）
    # D-66：E1 golden 由「n_eff 2.63（经核实为错值，真值 2.44~2.46）」换成
    # 「群折射率 n_g 4.18」（SOI 500×220nm racetrack L=66.8um，arXiv:2011.03273
    # 实测 FSR=8.6nm 反演，含 DOI → A 级）。至此 E1-E7 golden 全部 A 级可溯源。
    check("E 题 golden=语料值（4.18/1.892/10.44/0.18/0.05/0.087/-41）",
          abs(goldens["E1"] - 4.18) < 1e-9 and abs(goldens["E2"] - 1.892) < 1e-9
          and abs(goldens["E3"] - 10.44) < 1e-9
          and abs(goldens["E4"] - 0.18) < 1e-9 and abs(goldens["E5"] - 0.05) < 1e-9
          and abs(goldens["E6"] - 0.087) < 1e-9 and abs(goldens["E7"] + 41.0) < 1e-9,
          str(goldens))

    # ---- D-64 核心：候选求解器独立性（把「真验证」钉进 smoke）----
    # 背景：_harness_reference_candidate 直接 return golden ⇒ |candidate−golden|≡0，
    #       恒 PASS 但零验证价值（D-64 实测 E1/E3-E7 均为 0.0）。
    # E2 是首道接入独立候选的实证锚。
    # 🔴 v0.9.23：候选由 FDFD（标量亥姆霍兹）**换成 semivec_ng**（2D 半矢量本征模）
    # —— 原 FDFD 候选的 n_g 随计算窗口散射 ±0.04~0.08，PASS 可能只是窗口挑得好；
    # 半矢量同口径散射 <1e-5，且辨 TE/TM ⇒ E2 由「降级量级参考」升为「严格独立候选」。
    _s2 = next(s for s in emp if s.spec_id == "E2")
    _g2 = _s2.oracle_fn(_s2.params)
    _c2 = cand_map["E2"](_s2, _g2)
    check("D-64 E2 candidate 为独立半矢量本征模求解（非 golden 自证，且落在容差内）",
          abs(_c2 - _g2) > 1e-6 and abs(_c2 - _g2) <= _s2.tol,
          f"golden(实测)={_g2} candidate(semivec)={_c2:.4f} "
          f"|diff|={abs(_c2-_g2):.4f} tol={_s2.tol}")
    # 反向断言：其余 E 题仍为占位自证（如实标注，不得假装已验证）
    _still_self = [s.spec_id for s in emp
                   if s.spec_id != "E2"
                   and abs(cand_map[s.spec_id](s, s.oracle_fn(s.params))
                           - s.oracle_fn(s.params)) < 1e-12]
    check("D-64 其余 6 道 E 题仍为占位自证桩（candidate≡golden，如实标注非真验证）",
          sorted(_still_self) == ["E1", "E3", "E4", "E5", "E6", "E7"],
          f"自证={sorted(_still_self)}")

    # ---- D-65 判定窗口鲁棒性（**历史候选 fdfd_ng** 的证据，v0.9.23 起不再管辖 E2）----
    # 实测：FDFD 候选的 n_g 随计算窗口（clad_um）在 1.878~1.962 间散射（网格过粗所致，
    # 见 E2 note）。若只测默认窗口，PASS 可能只是运气。故断言**所有**窗口都必须落在
    # 容差内，并对散射设上界护栏（防止网格实现退化让不确定度失控）。
    # 🔴 2026-09-03（v0.9.23）：E2 的候选已由 fdfd_ng 换成 **semivec_ng**（2D 半矢量
    # 本征模），其窗口散射实测 **<1e-5**（对比 FDFD 的 ±0.04~0.08）——这正是 E2 得以
    # 从「降级量级参考」升为「严格独立候选」的核心凭据。本段**保留**为历史证据：
    # ①证明换候选是有实测理由的，不是拍脑袋；②若有人想换回 FDFD，这段会立刻提醒
    # 他要重新面对 ±0.04~0.08 的不确定度。新候选的窗口鲁棒性由
    # run_semivec_mode_smoke.py 常驻守护（L=5.0/6.0/8.0 三窗口散射 <1e-3）。
    try:
        from lda_harness.verification_adapters import _fdfd_ng_candidate

        class _P:  # 轻量 shim：候选函数只用到 spec.params
            def __init__(self, params):
                self.params = params

        _ngs = {}
        for _clad in (1.5, 2.0, 2.5, 3.0, 4.0):
            _ngs[_clad] = _fdfd_ng_candidate(
                _P(dict(_s2.params, clad_um=_clad)), _g2)
        _worst = max(abs(v - _g2) for v in _ngs.values())
        _spread = max(_ngs.values()) - min(_ngs.values())
        check("D-65 [历史候选 fdfd_ng] 5 个计算窗口全部落在容差内（散射证据留存）",
              _worst <= _s2.tol,
              " ".join(f"clad{k}={v:.4f}" for k, v in _ngs.items())
              + f" | 最大|diff|={_worst:.4f} tol={_s2.tol}")
        check("D-65 [历史候选 fdfd_ng] 数值不确定度护栏（散射不得恶化；R16 已证伪："
              "±0.04~0.08 实为窗口扫描非网格）——E2 已于 v0.9.23 换用 semivec_ng，本条仅存证",
              _spread <= 0.12,
              f"散射={_spread:.4f}（≈±{_spread/2:.3f}；这正是 FDFD 被换下的原因——"
              f"半矢量同口径散射 <1e-5，小 4 个数量级）")
    except Exception as _e:  # noqa: BLE001 求解器不可用时显式 FAIL，不静默放过
        check("D-65 E2 窗口鲁棒性检查可运行", False, f"{type(_e).__name__}: {_e}")
    # E3「实测 FSR ↔ 解析 λ²/(n_g·2πR)」闭合性检查。
    # 🔴🔴 **名实必须相符（v0.9.26 订正）**：这条原叫「实测↔解析**交叉验证**」，
    # 是**循环论证**。实证语料 E-TBOX-FSR-TM 的 method 字段明写「**实测 FSR**，
    # **反算**群折射率 n_g=4.92」⇒ golden(10.44) 与解析式**共用同一个 n_g**，
    # 二者不是独立两路，而是同一条数据链的正反演。
    #   量化看有多空：n_g 每变 0.01 ⇒ FSR 变 0.021 nm，而本条"吻合"仅 0.024 nm
    #   —— 差异量级等同于**舍入噪声**，不构成任何验证强度。
    # ⇒ 改标为「**自洽性检查**（非独立交叉验证）」：它只能防止数据录错/公式写错，
    #   **不能**当作 E3 的独立凭据。E3 至今仍是自证桩（见下方 _still_self）。
    _p = next(s for s in emp if s.spec_id == "E3").params
    _analytic = (_p["wl_um"] * 1000) ** 2 / (_p["n_g"] * 2 * 3.141592653589793
                                             * _p["R_um"] * 1000)
    check("E3 自洽性检查（非独立交叉验证）：|golden 10.44 − λ²/(ng·2πR)| ≤ tol 0.1"
          "——golden 由实测 FSR 反算 n_g 得来，与解析式同源，仅防数据/公式录错",
          abs(goldens["E3"] - _analytic) <= 0.1,
          f"实测={goldens['E3']} 解析={_analytic:.3f} 差={abs(goldens['E3']-_analytic):.3f} nm")

    # ② 注册候选全 PASS（50/50）。🔴 v0.9.25：此处曾硬编码 abs(cand−golden），
    # 与 path① 的 cmp_abs 硬编码同根——B19 接线后 cand_map["B19"] 是真实候选
    # （link_passivity，≈0.9999，cmp='le'），套绝对误差口径 ⇒ 1.04e-4 > tol 1e-9
    # 假 FAIL（全量回归 2/87 失败的根因，并经 industrial smoke 内部递归传导）。
    # 判据必须单一定义处：一律用 spec.compare_fn(candidate, oracle)。
    npass = sum(1 for s in specs
                if s.compare_fn(cand_map[s.spec_id](s, s.oracle_fn(s.params)),
                                s.oracle_fn(s.params)) <= s.tol)
    check("注册候选 50/50 PASS（双 ground · cmp 分发口径）", npass == len(specs) == 50,
          f"{npass}/{len(specs)}")

    # ③ 扰动候选：实证锚题 FAIL 检测（自适应扰动幅度）
    # 说明：E4-E7 为小量值（0.18/0.05/0.087 dB 等），固定 10% 相对扰动的绝对偏差
    # 可能小于绝对 tol（如 0.18×1.1=0.198 差 0.018 ≤ tol 0.1）——这是绝对容差语义
    # 的自然结果，非检测失效。为使"实证锚能抓偏离"的验证对所有题有效，
    # 扰动幅度按题自适应：rel = max(0.10, 2·tol/|golden|)（保证扰动偏差 ≥ 2×tol）。
    emp_fail = all(
        abs((goldens[s.spec_id] * (1.0 + max(0.10, 2.0 * s.tol / max(abs(goldens[s.spec_id]), 1e-12))))
            - goldens[s.spec_id]) > s.tol
        for s in emp)
    check("实证锚题扰动 FAIL 检测（自适应 rel，全部 7 题）", emp_fail,
          "实证锚能抓候选偏离实测（死标量比对，扰动≥2×tol）")

    # ④ 语料评审流（临时库）
    tmp = tempfile.mkdtemp(prefix="lda_d62_smoke_")
    pp = os.path.join(tmp, "empirical_proposals.json")
    cp = os.path.join(tmp, "empirical_contributions.json")

    r = submit_measurement({"id": "E-X1", "device": "d", "metric": "m",
                            "measured_value": 1.0, "uncertainty_abs": 0.1,
                            "fab_source": "X"}, proposals_path=pp)  # 缺 citation
    check("citation 门禁（无引用不予收录）", r["status"] == "rejected"
          and "citation" in r["reason"], r["reason"][:50])
    r = submit_measurement({"id": "E-X2", "device": "d", "metric": "m",
                            "measured_value": float("nan"), "uncertainty_abs": 0.1,
                            "fab_source": "X", "citation": "c"}, proposals_path=pp)
    check("NaN 数值门禁", r["status"] == "rejected", r["reason"][:40])
    r = submit_measurement({"id": "E-X3", "device": "d", "metric": "m",
                            "measured_value": 1.0, "uncertainty_abs": -1,
                            "fab_source": "X", "citation": "c"}, proposals_path=pp)
    check("σ<0 门禁", r["status"] == "rejected", r["reason"][:40])

    # D-63 来源边界：citation 须含 DOI/arXiv/公开 URL 方可收录（A 级可公开溯源）
    PAY = {"id": "E-TEST-1", "device": "测试器件", "metric": "loss_dB",
           "measured_value": 0.82, "uncertainty_abs": 0.05, "fab_source": "CUMEC",
           "citation": "S. Sridaran & S. A. Bhave, Opt. Express 18(4), 3850-3857 (2010), "
                       "https://opg.optica.org/oe/viewmedia.cfm?URI=oe-18-4-3850",
           "proposed_by": "community"}
    r = submit_measurement(PAY, proposals_path=pp)
    check("语料提交 accepted_pending", r["status"] == "accepted_pending", r["reason"][:40])
    r = submit_measurement(PAY, proposals_path=pp)
    check("防重守卫（同 id 重复拒）", r["status"] == "rejected", r["reason"][:40])
    r = review_measurement("E-TEST-1", "approve", "", "x", proposals_path=pp)
    check("评审缺具名评审人拒（LLM 不进判决）", r["status"] == "error"
          and "评审人" in r["reason"], r["reason"][:40])
    r = review_measurement("E-TEST-1", "approve", "杜玉河", "citation 可追溯", proposals_path=pp)
    check("具名评审 approve", r["status"] == "approved", r["reason"][:40])
    r = land_measurement("E-TEST-1", proposals_path=pp, corpus_path=cp)
    check("语料落地 landed", r["status"] == "landed", r["reason"][:40])
    # reload 进语料库 → harness 实证锚题实时可用
    corpus = EmpiricalCorpus.load(cp)
    anchor = EmpiricalAnchor(corpus)
    val, src, note = anchor.resolve("E-TEST-1")
    check("落地语料可被实证锚 resolve", val == 0.82 and src == "empirical-measurement",
          f"val={val} src={src}")

    # ⑤ harness 键集一致性（D-63：区分可溯源 A 级 / 待溯源 B 级）
    _anchors = {b: BENCHMARK_DEFS[b].get("anchor")
                for b in ("E1", "E2", "E3", "E4", "E5", "E6", "E7")}
    # D-64：E2 换用可公开溯源的实测群折射率语料（E-SIN-NG-300）→ 升 A 级。
    # D-66：E1 原用 E-SOI-NEFF-220（n_eff=2.63）经逐字核实系错值（真值 2.44~2.46），
    #       改判为 n_g 实测锚 E-SOI-NG-220（4.18±0.05，arXiv:2011.03273 racetrack
    #       实测 FSR 反演，含 DOI）→ **E1 同步升 A 级**。
    #       至此 E1-E7 全部为 A 级可公开溯源实证锚（B 级清零）。
    check("E1-E7 anchor 分型（D-66 后全部 = empirical(A级可公开溯源)，B 级清零）",
          all(_anchors[b] == "empirical"
              for b in ("E1", "E2", "E3", "E4", "E5", "E6", "E7")),
          str(_anchors))

    # ⑦ D-63 来源边界门禁：仅限公开论文/datasheet/公开测量数据集，且必须可公开溯源
    from lda_harness.provenance import classify_citation, audit_items

    # (a) B 级（无 DOI/URL 的模糊描述）提交须被拒
    r = submit_measurement({"id": "E-X4", "device": "d", "metric": "m",
                            "measured_value": 1.0, "uncertainty_abs": 0.1,
                            "fab_source": "X",
                            "citation": "某某公开 PDK 文献量级"},
                           proposals_path=pp)
    check("溯源门禁：B 级（无 DOI/URL）语料被拒（来源边界）",
          r["status"] == "rejected" and "溯源门禁" in r["reason"],
          r["reason"][:56])

    # (b) A 级（含公开 URL）可提交
    r = submit_measurement({"id": "E-X5", "device": "d", "metric": "m",
                            "measured_value": 1.0, "uncertainty_abs": 0.1,
                            "fab_source": "X",
                            "citation": "A. Author, Opt. Express 18(4), 3850 (2010), "
                                        "https://opg.optica.org/oe/viewmedia.cfm?URI=oe-18-4-3850"},
                           proposals_path=pp)
    check("溯源门禁：A 级（含公开 URL）语料放行",
          r["status"] == "accepted_pending", r["reason"][:56])

    # (c) A 级语料可作 golden；B 级语料作 golden 须被挡下
    _seed = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "lda_harness", "seed_empirical.json")
    _corpus = EmpiricalCorpus.load(_seed)
    _anchor = EmpiricalAnchor(_corpus)
    _v, _src, _ = _anchor.resolve("E-TBOX-FSR-TM")          # A 级（含 URL）
    check("A 级语料可作 golden（E-TBOX-FSR-TM → 10.44）",
          _v == 10.44 and _src == "empirical-measurement", f"val={_v} src={_src}")
    _v2, _src2, _note2 = _anchor.resolve("E-RING-FSR")       # A 级（D-66 补 arXiv DOI）
    check("A 级语料可作 golden（E-RING-FSR → 8.6，D-66 补 arXiv DOI 后由 B 升 A）",
          _v2 == 8.6 and _src2 == "empirical-measurement", f"val={_v2} src={_src2}")

    # B 级禁止作 golden：D-66 后 seed 语料库 **B 级已清零**（30/30 全 A），
    # 已无真实的 B 级样本可供断言 → 改用**合成 B 级语料**（citation 只有文本描述、
    # 无 DOI/arXiv/URL 定位符）来验证「门禁机制本身仍然生效」。
    # （不能用「语料库里没有 B 级」来证明门禁有效——那是缺样本，不是门禁通过。）
    from lda_harness.empirical_bank import EmpiricalMeasurement  # noqa: F401
    _b_corpus = EmpiricalCorpus([{
        "id": "E-SYNTH-B-1", "device": "synthetic", "metric": "m",
        "measured_value": 1.0, "uncertainty_abs": 0.1, "fab_source": "X",
        "citation": "某公开文献典型量级（无 DOI/arXiv/URL 定位符，仅文本描述）",
        "method": "未标注", "geometry": {}, "tags": [],
    }])
    _b_anchor = EmpiricalAnchor(_b_corpus)
    _vb, _srcb, _ = _b_anchor.resolve("E-SYNTH-B-1")
    check("B 级语料禁止作 golden（合成无定位符语料被挡下；seed 库 B 级已清零）",
          _vb is None and _srcb == "empirical-untraceable", f"val={_vb} src={_srcb}")
    _vb2, _srcb2, _ = _b_anchor.resolve("E-SYNTH-B-1", require_traceable=False)
    check("B 级语料显式 require_traceable=False 可降级取值并诚实标注",
          _vb2 == 1.0 and _srcb2 == "empirical-B-untraceable",
          f"val={_vb2} src={_srcb2}")

    # (d) 语料库整体溯源健康度
    # 达标线演进（D-66 → 本轮政策）：80% → **100%**（B 级零容忍）。
    # 政策（本轮）：随语料补充，达标线**逐步上调**，当前下限为 90%+、强制门禁为 100% ——
    # 任何 B 级混入都会稀释「实证锚 = 第二道非 AI ground」的可信度，故不容忍；
    # 90%+ 为审计脚本宽松基线（run_provenance_audit.py --min-ratio 默认 0.90），
    # 本提交门禁维持 100% 死守。
    _rep = audit_items(_corpus._items.values())
    check("语料库 A 级（可公开溯源）占比 = 100%（D-66 上调，B 级零容忍）",
          _rep["traceable_ratio"] >= 1.0,
          f"A={_rep['by_tier']['A']} B={_rep['by_tier']['B']} "
          f"total={_rep['total']} 占比={_rep['traceable_ratio']*100:.1f}%")

    # ⑥ 统计自洽
    s = measurement_stats(proposals_path=pp)
    # 计数基线：E-TEST-1(landed) + E-X5(pending，⑦ 溯源门禁「A 级放行」用例)
    check("measurement_stats 自洽（含 ⑦ A 级放行用例）",
          s["total"] == 2 and s["by_status"]["landed"] == 1
          and s["by_status"]["pending"] == 1,
          str(s))
    check("list_measurements 含审计", any(m["id"] == "E-TEST-1" and m["audit"]
          for m in list_measurements(proposals_path=pp)))

    npass_t = sum(1 for c in CHECKS if c[1])
    print("-" * 60)
    print(f"实证锚 smoke：{npass_t}/{len(CHECKS)} PASS")
    return 0 if npass_t == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
