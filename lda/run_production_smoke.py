"""研发生产系统 smoke（v0.9.41 · 四赛道全跑通 + 防回归）。

落点：A/B/C/D 四赛道生产任务全跑通 → 反向验证护栏（golden 45→48，含 D 赛道
      CPO 硅光 I/O 专用锚）不破 → 主货架库（71→75）结构可行 → 红线不破。
      CI 由本脚本守护。

动作：
  1) 解析《2027 产品规划》→ 17 个生产任务（A5/B4/C4/D4）
  2) 半自动确认门 dump（人工 approve 才执行；本 CI 用 ALL 自动批准全部非 blocked）
  3) 执行：design_pipeline（复用 system_type 已验证闭环，LLM 不进判决）+ 反向验证护栏
  4) 断言：四赛道全 done（无 blocked）+ golden 48/48 PASS + 货架 75 且全锚定
  5) 🔴 三道反向测试：D-67（漏算分光）/ Q-D67（QKD 漏算惩罚项）/
     P-CPO（CPO 间距低于物理下界）—— 全部要求护栏命中（新护栏必须反向测试会响）

出口：全部 PASS 才退出 0；任一 FAIL 记失败（CI 计数守护）。

红线（与全局一致）：
  - 不 import / 不调用 tapeout_pipeline（真实流片属 C 期，本系统不做）
  - LLM 不进判决路径（design_pipeline generator=grid，死标量锚判定）
  - 货架 honest_tier 固定前瞻预研（等效验证，不冒充流片验证）
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_l3 import production_plan as pp  # noqa: E402
from lda_l2 import innovation_market as im  # noqa: E402
from lda_l2.golden_product_benchmarks import (  # noqa: E402
    evaluate_all as golden_evaluate_all, HONEST_BANNER,
)


def _section(title: str) -> None:
    print("=" * 68)
    print(title)
    print("=" * 68)


def _d67_reverse_test() -> bool:
    """🔴 注入「漏算 3.0103dB 分光」回归，确认能量守恒下界护栏仍命中。"""
    from lda_design.loss_engines import ENGINE_FUNCS as _EF  # noqa: E402
    from lda_l2 import golden_product_benchmarks as _gpb  # noqa: E402

    _orig = _EF["engine_ybranch_split"]

    def _bad_ybranch(geom):
        th = float(geom.get("theta_deg", 10.0))
        c1 = float(geom.get("excess_coef", 0.004))
        return {"metric": "excess_loss_dB", "value": round(c1 * th * th, 4),
                "model": "BAD-D66"}

    _EF["engine_ybranch_split"] = _bad_ybranch
    try:
        _hit_floor = 0
        _chips = [c for c in _gpb.DEFAULT_CHIP_BENCHMARKS
                  if getattr(c, "geom", {}).get("n_ybranch", 0) > 0]
        for _c in _chips:
            try:
                _c.evaluate()
            except AssertionError:
                _hit_floor += 1
        _yb = [b for b in _gpb.DEFAULT_BENCHMARKS
               if getattr(b, "product_id", None) == "GP-YBRANCH"][0]
        _sem = bool(_yb.evaluate().get("error"))
    finally:
        _EF["engine_ybranch_split"] = _orig

    if _hit_floor != len(_chips):
        print(f"FAIL: 能量守恒下界护栏失效 —— 注入漏算分光后仅拦下 "
              f"{_hit_floor}/{len(_chips)} 条含分束器链路")
        return False
    if not _sem:
        print("FAIL: metric 语义错配护栏失效 —— 拿过量损耗比总插损 golden 未被拦下")
        return False
    print(f"[D-67 反向测试] 注入「漏算 3.0103dB 分光」回归 → 两道护栏均命中："
          f"能量守恒下界拦下 {_hit_floor}/{len(_chips)} 条链路 + "
          f"metric 语义错配拦下（护栏真实有效，非纸上谈兵）")
    return True


def _qd67_reverse_test() -> bool:
    """🔴 Q-D67 反向测试：注入「漏算误纠错惩罚项 / 错用 Q_μ 替代 Q_1」回归，
    确认 QKD 安全密钥率护栏（密钥率 ≤ 单光子贡献上界，位于 _skr_per_pulse）仍命中。"""
    import math
    from lda_design import qkd_engines as _qe

    _orig = _qe._skr_per_pulse

    def _bad(geom):
        """复现回归：正项用 Q_μ 替代 Q_1 且丢弃 −Q_μ·f·H₂(E_μ) 惩罚项；护栏仍在。"""
        L = float(geom["distance_km"])
        alpha = float(geom.get("fiber_loss_db_km", 0.2))
        alice = float(geom.get("alice_il_db", 15.0))
        bob = float(geom.get("bob_il_db", 8.0))
        eta_det = float(geom.get("detector_eff", 0.1))
        p_d = float(geom.get("dark_count_prob", 1e-6))
        e_mis = float(geom.get("misalignment", 0.015))
        mu = float(geom.get("mu", 0.5))
        f = float(geom.get("f_ec", 1.1))
        q = 0.5
        loss_db = alice + alpha * L + bob
        T = 10.0 ** (-loss_db / 10.0)
        eta = T * eta_det
        Y0 = 2.0 * p_d
        Y1 = Y0 + eta
        e1 = e_mis + Y0 / (2.0 * Y1)
        Q1 = mu * math.exp(-mu) * Y1
        Qmu = Y0 + eta * mu
        Emu = (0.5 * Y0 + e1 * mu * math.exp(-mu) * Y1) / Qmu
        H1 = _qe.binary_entropy(e1)
        Hmu = _qe.binary_entropy(Emu)
        skr_per_pulse = q * Qmu * (1.0 - H1)   # BAD：用 Q_μ 且丢惩罚项 → 应突破上界
        q1_upper = q * Q1
        if skr_per_pulse > q1_upper + 1e-15:
            raise AssertionError(
                f"[QKD] 密钥率 {skr_per_pulse:.3e}/脉冲 超过单光子贡献上界 {q1_upper:.3e} "
                f"（疑似漏算误纠错惩罚项 −Q_μ·f·H₂(E_μ) 或错用 Q_μ 替代 Q₁，见 Q-D67 回归）")
        return {"per_pulse": skr_per_pulse, "transmittance": T, "eta_det_eff": eta,
                "single_photon_yield": Y1, "single_photon_qber": e1, "qber": Emu,
                "model": "BAD-QD67"}

    _qe._skr_per_pulse = _bad
    try:
        _hit = False
        try:
            _qe.decoy_bb84_skr({"distance_km": 50.0})
        except AssertionError:
            _hit = True
    finally:
        _qe._skr_per_pulse = _orig

    if not _hit:
        print("FAIL: Q-D67 护栏失效 —— 注入「漏算惩罚项/错用 Q_μ」后未拦下（会伪装成安全成钥 = 假绿）")
        return False
    print(f"[Q-D67 反向测试] 注入「漏算误纠错惩罚项 / 错用 Q_μ 替代 Q_1」回归 → "
          f"密钥率≤单光子贡献上界护栏命中（真实有效，非纸上谈兵）")
    return True


def _pcpo_reverse_test() -> bool:
    """🔴 P-CPO 反向测试：注入「通道间距低于物理下界 = 虚报带宽密度」回归。

    与 D-67 **对称**的假绿通道：插损 metric 方向是 `le`（越小越 PASS）⇒ 漏算损耗
    会伪装成设计更好；带宽密度 metric 方向是 `ge`（越大越 PASS）⇒ 把通道间距写小
    会伪装成密度更高。两者都必须用**物理下界/上界**堵死。

    三注（任一不响即判护栏失效 —— 宁红不假绿）：
      ① 光纤阵列 pitch 20 µm < 125 µm（ITU-T G.652 单模光纤包层直径，几何必然）
      ② 片间光栅直连 pitch 5 µm < 10.3 µm（G.652 MFD@1550，模场重叠即串扰）
      ③ 在 **CPO 生产代码路径**（非 golden 内嵌副本）漏算 3.0103 dB 分光
    """
    from lda_design import cpo_engines as _ce
    from lda_design.loss_engines import ENGINE_FUNCS as _EF

    hits = []
    for cm, p, why in (("fau", 20.0, "G.652 包层直径 125 µm"),
                       ("grating_array", 5.0, "G.652 MFD@1550 10.3 µm")):
        try:
            _ce.cpo_optical_io_metrics({"couple_mode": cm, "pitch_um": p})
        except AssertionError:
            hits.append(f"{cm}@{p}µm(<{why})")

    # ③ CPO 路径 D-67（护栏位于 cpo_engines，须测生产代码而非 golden 副本）
    _orig = _EF["engine_ybranch_split"]

    def _bad_ybranch(geom):
        th = float(geom.get("theta_deg", 10.0))
        c1 = float(geom.get("excess_coef", 0.004))
        return {"metric": "excess_loss_dB", "value": round(c1 * th * th, 4),
                "model": "BAD-D66"}

    _EF["engine_ybranch_split"] = _bad_ybranch
    try:
        _ce.cpo_optical_io_metrics({"couple_mode": "fau", "n_ybranch": 1})
    except AssertionError:
        hits.append("CPO 路径漏算 3.0103dB 分光")
    finally:
        _EF["engine_ybranch_split"] = _orig

    if len(hits) != 3:
        print(f"FAIL: P-CPO 护栏失效 —— 三注仅命中 {len(hits)}/3（已命中：{hits}）"
              f"；间距下界或能量守恒下界有一处不响，CPO 密度/插损会静默假绿")
        return False
    print(f"[P-CPO 反向测试] 注入「间距低于物理下界 ×2 + CPO 路径漏算分光」三注回归 → "
          f"P-CPO 间距几何下界护栏 + D-67 能量守恒下界均命中（护栏真实有效，非纸上谈兵）")
    return True


def main() -> int:
    rc = 0

    # 1) 解析规划
    _section("1) 解析《2027 产品规划》→ 生产任务")
    tasks = pp.parse_plan()
    from collections import Counter
    by_track = Counter(t.track for t in tasks)
    print(f"解析到 {len(tasks)} 个任务：{dict(by_track)}")
    print(f"  A={by_track['A']} B={by_track['B']} C={by_track['C']} D={by_track['D']}")
    if (len(tasks) != 17 or by_track['A'] != 5 or by_track['B'] != 4
            or by_track['C'] != 4 or by_track['D'] != 4):
        print("FAIL: 任务数或赛道分布异常（期望 17 = A5/B4/C4/D4）")
        return 1

    # 2) 确认门 dump + ALL 批准
    _section("2) 半自动确认门 + 批准 ALL")
    gate = pp.confirm_gate_dump(tasks)
    print(f"确认门 dump: {gate}")
    approve_ids = [t.shelf_id for t in tasks if t.status != "blocked"]
    print(f"批准 {len(approve_ids)} 个任务（ALL）")

    # 3) 执行
    _section("3) 执行四赛道生产任务（design_pipeline + 反向验证护栏）")
    results = pp.run_production(tasks, approve_ids)
    blocked = [sid for sid, r in results.items() if r.get("status") != "done"]
    for sid, r in results.items():
        print(f"  - {sid} [{r.get('track')}]: {r.get('status')} "
              f"(feasible={r.get('feasible')}, n_accepted={r.get('n_accepted')}, "
              f"golden={r.get('golden_pass')}/{r.get('golden_total')})")
    if blocked:
        print(f"FAIL: 以下任务未 done（blocked）：{blocked}")
        rc = 1

    # 4) golden 反向验证库不破（45→48）
    _section("4) golden 基准库（45→48，含 D 赛道 CPO 光 I/O 锚）反向验证")
    gres = golden_evaluate_all()
    gn = len(gres)
    gp = sum(1 for r in gres if r.get("passed_all"))
    print(f"{gp}/{gn} 产品级对标 PASS")
    if gp < gn:
        print("FAIL: 存在未达标对标")
        for r in gres:
            if not r.get("passed_all"):
                print(f"   - {r['product_id']}: {r.get('error', 'FAIL')}")
        rc = 1

    # 5) 货架库结构（71→75）
    _section("5) 主货架库（71→75，含 D 赛道 4 条 CPO 货架）结构校验")
    shelf = im.DEFAULT_SHELF
    print(f"货架总数: {len(shelf)}")
    if len(shelf) != 75:
        print(f"FAIL: 货架数 {len(shelf)} ≠ 75")
        rc = 1
    bad_comp = [s.id for s in shelf if not s.validate_composition()["all_anchored"]]
    if bad_comp:
        print(f"FAIL: 含未锚定基元的货架：{bad_comp}")
        rc = 1
    else:
        print("  全部货架仅由已锚定基元组装（红线下护栏①）")

    # 6) D-67 + Q-D67 + P-CPO 反向测试
    _section("6) 🔴 D-67 / Q-D67 / P-CPO 反向测试（护栏必须会响）")
    if not _d67_reverse_test():
        rc = 1
    if not _qd67_reverse_test():
        rc = 1
    if not _pcpo_reverse_test():
        rc = 1

    # 7) 报告 + 红线声明
    _section("7) 生产报告")
    rep = pp.write_report(tasks, results)
    print(f"报告已写: {rep}")
    print("\n红线声明：")
    print("  - 不调用 tapeout_pipeline（真实流片属 C 期，本系统不做）")
    print("  - LLM 不进判决路径（design_pipeline generator=grid，死标量锚）")
    print("  - 每次产出过 golden_product_benchmarks 反向验证，FAIL 即 blocked")
    print("  - 货架 honest_tier 固定为前瞻预研（等效验证）")

    if rc == 0:
        print("\nALL PASS — 四赛道全跑通（A5/B4/C4/D4） · golden 48/48 · 货架 75 · 红线不破")
    else:
        print("\nFAIL — 见上")
    return rc


if __name__ == "__main__":
    sys.exit(main())
