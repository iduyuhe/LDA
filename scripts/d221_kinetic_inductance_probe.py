"""D-221 突变探针（scratch · 不入 CI）：证明 run_kinetic_inductance_smoke.py 能变红。

惯例：`scripts/*_probe.py` 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块对象（**不碰源文件**）。

人工记录（改动 → 应红判据）：
  · M1 λ_L(T) 漏掉 (T/Tc)^4 的物理形式（写成 λ0/(T/Tc)）      ⇒ A1/A2 应红
  · M2 coth(t/λ) 换成 1（忽略薄膜因子）                        ⇒ A5 应红
  · M3 L_k 与 w 成正比（而非反比）                              ⇒ A7 应红
  · M4 n_eff' 用 √α 而非 √(1+α)                                ⇒ X1 应红
  · M5 cpw_kinetic_report 自带一个 ε_eff（绕过 SSOT）           ⇒ X2 应红
  · M6 L_mag 写成 μ0/C_air（漏 ε0）                             ⇒ X3 应红
  · M7 材料库全同参（假装材料不敏感）                            ⇒ G4 应红
  · M8 谎称可锚（anchorable=True）                              ⇒ H3 应红
🔴 教训：patch 打在**门禁实际调用的模块对象**（`lda_qeda.kinetic_inductance`）；
   M5/M4 这类要 patch `cpw_kinetic_report` 本身，patch 常量会被消费方一起跟着变 ⇒ 假绿。
"""
from __future__ import annotations

import contextlib
import io
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_kinetic_inductance_smoke as S     # noqa: E402
from lda_qeda import kinetic_inductance as KI  # noqa: E402


def run_smoke():
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = S.main()
    except Exception as e:                                   # noqa: BLE001
        rc = 99
        buf.write("[FAIL] 门禁异常：%s: %s" % (type(e).__name__, e))
    out = buf.getvalue()
    return rc, out.count("[FAIL]"), out


def main() -> int:
    rows = []

    rc, nf, _ = run_smoke()
    rows.append(("baseline 无突变（须全绿）", rc, nf))

    _lam = KI.lambda_l
    _lk = KI.l_kin_per_length
    _lm = KI.l_mag_per_length
    _rep = KI.cpw_kinetic_report
    _mats = dict(KI.MATERIALS)
    _why = KI.why_not_anchored

    # M1 λ_L(T) 漏掉 (T/Tc)^4 物理形式
    KI.lambda_l = lambda lam0_nm, tc_k, t_k: (
        float(lam0_nm) * 1e-9 if t_k <= 0 else float(lam0_nm) * 1e-9 / (t_k / tc_k))
    rows.append(("M1 λ_L(T) 写成 λ0/(T/Tc)", *run_smoke()[:2]))
    KI.lambda_l = _lam

    # M2 coth(t/λ) → 1（忽略薄膜因子）
    KI.l_kin_per_length = lambda lam_m, t_m, w_m: KI.MU0 * lam_m / w_m
    rows.append(("M2 忽略薄膜因子（coth→1）", *run_smoke()[:2]))
    KI.l_kin_per_length = _lk

    # M3 L_k ∝ w（而非 1/w）
    KI.l_kin_per_length = lambda lam_m, t_m, w_m: (
        KI.MU0 * lam_m * (1.0 / math.tanh(t_m / lam_m)) * w_m)
    rows.append(("M3 L_k 与 w 成正比", *run_smoke()[:2]))
    KI.l_kin_per_length = _lk

    # M4 n_eff' 用 √α 而非 √(1+α)
    def _rep_wrong_n(rep_material="Al", *a, **kw):
        r = dict(_rep(rep_material, *a, **kw))
        r["n_eff_with_kin"] = r["n_eff_geom"] * math.sqrt(r["alpha_kin"])
        return r
    KI.cpw_kinetic_report = _rep_wrong_n
    rows.append(("M4 n_eff' 用 √α（漏 1+）", *run_smoke()[:2]))
    KI.cpw_kinetic_report = _rep

    # M5 自带 ε_eff（绕过 SSOT 单一真源）
    def _rep_own_eps(rep_material="Al", *a, **kw):
        r = dict(_rep(rep_material, *a, **kw))
        r["eps_eff_geom"] = 6.5
        return r
    KI.cpw_kinetic_report = _rep_own_eps
    rows.append(("M5 ε_eff 绕过 SSOT（硬编码 6.5）", *run_smoke()[:2]))
    KI.cpw_kinetic_report = _rep

    # M6 L_mag 漏 ε0
    KI.l_mag_per_length = lambda c_air: KI.MU0 / c_air
    rows.append(("M6 L_mag 漏 ε0（μ0/C_air）", *run_smoke()[:2]))
    KI.l_mag_per_length = _lm

    # M7 材料库全同参（假装材料不敏感）
    KI.MATERIALS = {k: {"tc_k": 1.20, "lambda0_nm": 50.0} for k in _mats}
    rows.append(("M7 材料库全同参（假称不敏感）", *run_smoke()[:2]))
    KI.MATERIALS = _mats

    # M8 谎称可锚
    def _why_anchorable():
        r = dict(_why())
        r["anchorable"] = True
        return r
    KI.why_not_anchored = _why_anchorable
    rows.append(("M8 谎称可锚（anchorable=True）", *run_smoke()[:2]))
    KI.why_not_anchored = _why

    KI.lambda_l, KI.l_kin_per_length = _lam, _lk
    KI.l_mag_per_length, KI.cpw_kinetic_report = _lm, _rep
    KI.MATERIALS, KI.why_not_anchored = _mats, _why

    print("\n%-40s %4s %6s  %s" % ("突变", "rc", "FAIL", "结论"))
    ok = True
    for name, rc, nf in rows:
        if name.startswith("baseline"):
            good = (rc == 0 and nf == 0)
            verdict = "OK（全绿）" if good else "!! 基线应全绿"
        else:
            good = (rc != 0 and nf > 0)
            verdict = "咬住（%d 条红）" % nf if good else "!! 未咬住（假绿）"
        ok = ok and good
        print("%-40s %4s %6s  %s" % (name, rc, nf, verdict))
    print("\n探针结论：%s（%d/%d 突变被咬住）"
          % ("ALL_CAUGHT" if ok else "HAS_UNCAUGHT",
             sum(1 for n, r, f in rows if not n.startswith("baseline") and r != 0 and f > 0),
             len(rows) - 1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
