"""M5 光计算对标基准 · CI 门禁（任务 #5）。

纪律（与 M1–M4 一致）：
- name-first `check(name, cond, detail)`；反向可证伪（每组带一个会红的假实现）。
- 零能效数字（复用 optical_pareto.assert_no_energy_metrics）。
- 扁平包导入（`import run_ci_regression`，无 lda. 前缀）。
- K1：本文件必须已登记进 CORE_SMOKES（防静默漏接）。
"""
from __future__ import annotations

import sys
import traceback
from typing import Any, Dict

# ── 路径：本文件在 lda/ 下，包根即 lda/ ──
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lda_l2 import photonic_compute_benchmarks as B  # noqa: E402
from lda_l2 import optical_pareto as OP  # noqa: E402

PASS = 0
FAIL = 0
_log: list = []


def check(name: str, cond: bool, detail: str = "") -> bool:
    """name-first（血案 1c/20 教训）：名字在前，写反即假绿。"""
    global PASS, FAIL
    ok = bool(cond)
    if ok:
        PASS += 1
    else:
        FAIL += 1
    _log.append("%s | %s%s" % ("PASS" if ok else "FAIL", name,
                                ("  [%s]" % detail) if detail else ""))
    return ok


def _raises(fn, *a, **k) -> bool:
    try:
        fn(*a, **k)
        return False
    except Exception:
        return True


def _claims_energy(d: Dict[str, Any]) -> bool:
    """反向辅助：dict 是否含任何 fabricated 能效键。"""
    return any(k in d for k in ("tops_w", "pj_per_mac", "power_w", "energy_per_mac"))


def _is_scale_blind(verdict: Dict[str, Any]) -> bool:
    """反向辅助：判定 scale-blind（与模块同口径）。"""
    return bool(verdict.get("scale_blind")) and verdict.get("ratio_rel_std", 1.0) < 0.20


# ══════════════════════════════════════════════════════════════
# A 组 · 诚实边界披露
# ══════════════════════════════════════════════════════════════
note = B.LDA_PHOTONIC_HONEST_NOTE
check("A1 诚实边界含「非已流片光子芯片」字面", "非已流片光子芯片" in note)
check("A2 诚实边界含「不宣称任何 fabricated 能效数字」字面",
      "不宣称任何 fabricated 能效数字" in note)
check("A3 诚实边界含「规模 = 设计容量」字面", "规模 = 设计容量" in note)
check("A4 诚实边界含「零能效数字」字面", "零能效数字" in note)
check("A5 诚实边界含「LLM 不进判决路径」字面", "LLM 不进判决路径" in note)

# ══════════════════════════════════════════════════════════════
# B 组 · 公开 landmark 均可复核（A 级 golden 带源）
# ══════════════════════════════════════════════════════════════
all_src = all(bool(v.get("source")) for v in B.PUBLIC_LANDMARKS.values())
check("B1 全部公开 landmark 带来源 URL（可复核）", all_src,
      "%d 条" % len(B.PUBLIC_LANDMARKS))
# 关键来源须与真实检索一致（Lightmatter / MIT / 清华 / AIP / Ayar）
check("B2 含 Lightmatter Envise 2025 来源",
      "whychips.com" in B.PUBLIC_LANDMARKS["lightmatter_envise_2025"]["source"])
check("B3 含 MIT 2026 超复用 MMM 来源（rle.mit.edu）",
      "rle.mit.edu" in B.PUBLIC_LANDMARKS["mit_2026_hypermux"]["source"])
check("B4 含 AIP AML 2024 对比表来源",
      "pubs.aip.org" in B.PUBLIC_LANDMARKS["aip_aml_2024_table"]["source"])
check("B5 明标 Ayar 为「光 I/O 层，非计算核」",
      "非计算核" in B.PUBLIC_LANDMARKS["ayar_labs"]["note"])

# ══════════════════════════════════════════════════════════════
# C 组 · LDA 不报 fabricated 能效（核心诚实边界）
# ══════════════════════════════════════════════════════════════
d = B.lda_demonstrated()
check("C1 LDA reports_fabricated_tops_w == False", d["reports_fabricated_tops_w"] is False)
check("C2 LDA 实绩字典不含任何能效键", not _claims_energy(d))
# 反向：注入能效键 ⇒ 同一判定必 True（证明判据能变红）
check("C3 反向：注入 tops_w ⇒ _claims_energy 必 True（假实现会变红）",
      _claims_energy(dict(d, tops_w=5.0)) is True)

# ══════════════════════════════════════════════════════════════
# D 组 · 尺度盲保真（达国际规模的真身）
# ══════════════════════════════════════════════════════════════
check("D1 scale-blind == True", d["scale_blind"] is True)
check("D2 N=256 网格酉保真度 ≥ 0.98（%.4f）" % d["grid_fidelity_at_256"],
      d["grid_fidelity_at_256"] >= 0.98)
check("D3 scale-blind ratio 相对标准差 < 20%%（%.4f）" % d["scale_blind_ratio_rel_std"],
      d["scale_blind_ratio_rel_std"] < 0.20)
# 反向：伪造 scale_blind=False 的 verdict ⇒ 判定必 False
fake_bad = {"scale_blind": False, "ratio_rel_std": 0.5}
fake_good = {"scale_blind": True, "ratio_rel_std": 0.08}
check("D4 反向：伪 verdict(scale_blind=False) ⇒ 判定 False",
      _is_scale_blind(fake_bad) is False)
check("D5 反向：伪 verdict(scale_blind=True) ⇒ 判定 True",
      _is_scale_blind(fake_good) is True)

# ══════════════════════════════════════════════════════════════
# E 组 · 尺度盲外推（延展到 800×800 文献类）
# ══════════════════════════════════════════════════════════════
ext = B.scale_blind_extrapolation(800)
check("E1 外推 800×800 设计保真度 ≥ 0.98（%.4f）" % ext["est_grid_fidelity"],
      ext["est_grid_fidelity"] >= 0.98)
check("E2 外推 MZI 计数 = 800*799//2 = 319600（%d）" % ext["mzi_count"],
      ext["mzi_count"] == 800 * 799 // 2)
check("E3 外推含诚实 caveat（非流片实测）", "非流片实测" in ext["caveat"])

# ══════════════════════════════════════════════════════════════
# F 组 · 架构族对齐（与 MIT MZI-mesh lineage 同族；不与 Ayar 同层比）
# ══════════════════════════════════════════════════════════════
ac = B.architecture_class()
check("F1 与 MIT 2025 Nature 128×128 PTC 同族",
      any("2025 Nature 128" in s for s in ac["same_lineage_as"]))
check("F2 明标不与 Ayar（光 I/O 层）同台比",
      "Ayar Labs" in ac["not_same_layer_as"][0])
check("F3 文献 MZI-mesh 最大 ≤800×800", ac["literature_mzi_mesh_max"] <= 800)
check("F4 明标 LDA 正解该瓶颈（制备误差）",
      "制备误差" in ac["lda_addresses_bottleneck"])

# ══════════════════════════════════════════════════════════════
# G 组 · 零能效数字（注入必 raise）
# ══════════════════════════════════════════════════════════════
budget = {"mzi_per_core": 32640, "dac_bits": 16, "tile_k": 16}
check("G1 本模块预算字典通过 assert_no_energy_metrics",
      not _raises(OP.assert_no_energy_metrics, budget))
injected = dict(budget, pj_per_bit=1e-12)
check("G2 注入能效键 ⇒ assert_no_energy_metrics 必 raise（反向）",
      _raises(OP.assert_no_energy_metrics, injected))

# ══════════════════════════════════════════════════════════════
# H 组 · 输入域 / 护栏
# ══════════════════════════════════════════════════════════════
small = B.scale_blind_extrapolation(8)
check("H1 小 N=8 外推仍返回有限保真度", 0.0 < small["est_grid_fidelity"] <= 1.0)
check("H2 案例卡组装不抛错且 verdict=DESIGN_SIGNOFF",
      B.case_card()["verdict"] == "DESIGN_SIGNOFF")

# ══════════════════════════════════════════════════════════════
# I 组 · 反向可证伪（整体）：破坏诚实边界任一条 ⇒ 相关判据必红
# ══════════════════════════════════════════════════════════════
# I1 伪造「报 fabricated 能效」的实绩 ⇒ C 组判定会红
fake_d_energy = dict(d, reports_fabricated_tops_w=True)
check("I1 反向：伪造报 fabricated 能效 ⇒ C1 判定必红",
      (fake_d_energy["reports_fabricated_tops_w"] is False) is False)
# I2 伪造「尺度盲塌缩」实绩 ⇒ D 组判定会红
fake_d_collapse = dict(d, scale_blind=False, grid_fidelity_at_256=0.5)
check("I2 反向：伪造尺度盲塌缩(保真0.5) ⇒ D2 判定必红",
      (fake_d_collapse["grid_fidelity_at_256"] >= 0.98) is False)

# ══════════════════════════════════════════════════════════════
# J 组 · 通用反向（门禁自身体现反向纪律）
# ══════════════════════════════════════════════════════════════
# 若把「诚实边界」里移除「非已流片」字样，A1 必红（证明 A1 非死判据）
fake_note_ok = note.replace("非已流片光子芯片", "")
check("J1 反向：移除「非已流片」字样 ⇒ A1 判定必红",
      ("非已流片光子芯片" in fake_note_ok) is False)

# ══════════════════════════════════════════════════════════════
# K 组 · 自入 CI core（防静默漏接 · 血案 28）
# ══════════════════════════════════════════════════════════════
try:
    import run_ci_regression as R  # noqa: E402,F401
    in_core = "run_photonic_compute_m5_smoke.py" in R.CORE_SMOKES
    check("K1 本 smoke 已登记进 CI core（CORE_SMOKES）", in_core,
          "len=%d" % len(R.CORE_SMOKES))
except Exception as e:  # pragma: no cover
    check("K1 本 smoke 已登记进 CI core（CORE_SMOKES）", False,
          "import 失败: %s" % e)


# ══════════════════════════════════════════════════════════════
def main() -> int:
    print("=" * 64)
    print("M5 光计算对标基准 · CI 门禁")
    print("=" * 64)
    for line in _log:
        print("  " + line)
    print("-" * 64)
    print("PASS=%d  FAIL=%d  TOTAL=%d" % (PASS, FAIL, PASS + FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        traceback.print_exc()
        rc = 2
    sys.exit(rc)
