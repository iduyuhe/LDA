"""D-222 突变探针（scratch · 不入 CI）：证明 run_conductor_surface_smoke.py 能变红。

惯例：`scripts/*_probe.py` 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块对象（**不碰源文件**）。

人工记录（改动 → 应红判据）：
  · M1  coth(k·t) → tanh(k·t)（薄厚颠倒）                        ⇒ A1/A4 应红
  · M2  k = √(jωμ0σ) 漏掉 j（写成 √(ωμ0σ)）                     ⇒ A2/A5 应红
  · M3  有限厚度忽略（Z_s 直接返回 (ρ/δ)(1+j)）                  ⇒ A2/A3/H6 应红
  · M4  薄膜极限不取 1/x（|kt| 判据阈值调到 0 ⇒ 除零/爆）         ⇒ A3/H1 应红
  · M5  α_c 漏掉真空波阻抗 η0                                    ⇒ G1/G4 应红
  · M6  σ1 在深低温改用两流体（假装它没失效）                     ⇒ Z2 应红
  · M7  t=0 不 raise（返回 inf）                                 ⇒ H1 应红
  · M8  谎称可锚（anchorable=True）                              ⇒ Z3 应红
  · M9  材料库全同参（假装材料不敏感）                            ⇒ H6 应红
  · M10 薄膜区 δ_eff 硬编码 t/2（而非真实的 t/3）                 ⇒ H5 应红

🔴 教训（D-219/D-221 同族）：patch 必须打在**门禁实际调用的模块对象**上
   （`lda_qeda.conductor_surface` 的模块级函数）；patch 常量会被消费方跟着变 ⇒ 假绿。
"""
from __future__ import annotations

import contextlib
import io
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_conductor_surface_smoke as S        # noqa: E402
from lda_qeda import conductor_surface as CS   # noqa: E402


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
    rows.append(("baseline（未突变）", rc, nf))

    # 保存原件
    _si = CS.surface_impedance
    _kc = CS.k_complex
    _zn = CS.zs_normal
    _ac = CS.alpha_c_cpw
    _ss = CS.sigma_super
    _wn = CS.why_not_anchored
    _aw = CS.alpha_with_thickness
    _mats = dict(CS.CONDUCTOR_MATERIALS)

    # ---------------- M1 coth → tanh ----------------
    def _si_tanh(sigma, f, t):
        k = _kc(sigma, f)
        zc = 1j * 2.0 * math.pi * f * CS.MU0 / k
        return zc * __import__("cmath").tanh(k * t)
    CS.surface_impedance = _si_tanh
    rows.append(("M1 coth→tanh（薄厚颠倒）", *run_smoke()[:2]))
    CS.surface_impedance = _si

    # ---------------- M2 k 漏 j ----------------
    def _kc_noj(sigma, f):
        return __import__("cmath").sqrt(2.0 * math.pi * f * CS.MU0 * sigma)
    CS.k_complex = _kc_noj
    rows.append(("M2 k 漏掉 j（√(ωμ0σ)）", *run_smoke()[:2]))
    CS.k_complex = _kc

    # ---------------- M3 忽略有限厚度 ----------------
    def _zn_inf(rho, f, t):
        d = CS.skin_depth(rho, f)
        return complex(rho / d, rho / d)
    CS.zs_normal = _zn_inf
    rows.append(("M3 忽略有限厚度（用半无限）", *run_smoke()[:2]))
    CS.zs_normal = _zn

    # ---------------- M4 薄膜极限分支失效 ----------------
    #    🔴 首版把 patch 的触发条件写成 |kt| < 1e-14，而门禁测的是 u=1e-2/1e-3
    #    （|kt| = 1.4e-2 / 1.4e-3）⇒ **从未命中** ⇒ 假绿。
    #    改为：薄膜区（|kt| < 0.1）引入 0.1% 偏差，直击 A2/A3 的解析真值。
    def _si_thin_err(sigma, f, t):
        z = _si(sigma, f, t)
        if abs(_kc(sigma, f) * t) < 0.1:
            return z * 1.001
        return z
    CS.surface_impedance = _si_thin_err
    rows.append(("M4 薄膜区 Re 给错 0.1%", *run_smoke()[:2]))
    CS.surface_impedance = _si

    # ---------------- M5 α_c 漏 η0 ----------------
    def _ac_noeta(zs, f, w, g, h, er, dn_um=None):
        r = _ac(zs, f, w, g, h, er, dn_um)
        r = dict(r)
        r["alpha_c_np_per_m"] = r["alpha_c_np_per_m"] * CS.ETA0
        return r
    CS.alpha_c_cpw = _ac_noeta
    rows.append(("M5 α_c 漏掉 η0", *run_smoke()[:2]))
    CS.alpha_c_cpw = _ac

    # ---------------- M6 σ1 用两流体（假装没失效） ----------------
    def _ss_2f(material, t_k=CS.T_OP_K, f_hz=5e9, npts=4001,
               use_bcs_sigma1=True):
        return _ss(material, t_k, f_hz, npts, use_bcs_sigma1=False)
    CS.sigma_super = _ss_2f
    rows.append(("M6 σ1 改用两流体（假装未失效）", *run_smoke()[:2]))
    CS.sigma_super = _ss

    # ---------------- M7 t=0 不 raise ----------------
    def _si_noraise(sigma, f, t):
        if t <= 0:
            return complex(float("inf"), 0.0)
        return _si(sigma, f, t)
    CS.surface_impedance = _si_noraise
    rows.append(("M7 t=0 返回 inf 而非 raise", *run_smoke()[:2]))
    CS.surface_impedance = _si

    # ---------------- M8 谎称可锚 ----------------
    def _wn_lie():
        d = _wn()
        d["anchorable"] = True
        return d
    CS.why_not_anchored = _wn_lie
    rows.append(("M8 谎称可锚（anchorable=True）", *run_smoke()[:2]))
    CS.why_not_anchored = _wn

    # ---------------- M9 材料库全同参 ----------------
    CS.CONDUCTOR_MATERIALS = {k: {"rho_n": 1e-9, "context": v["context"]}
                              for k, v in _mats.items()}
    rows.append(("M9 材料库全同参（假装不敏感）", *run_smoke()[:2]))
    CS.CONDUCTOR_MATERIALS = _mats

    # ---------------- M10 薄膜区 δ_eff 硬编码 t/2 ----------------
    def _aw_bad(material, t_nm, f_hz=5e9, w_um=10.0, g_um=6.0,
                 h_um=500.0, eps_r=11.45, t_k=CS.T_OP_K, state="super"):
        r = _aw(material, t_nm, f_hz, w_um, g_um, h_um, eps_r, t_k, state)
        r = dict(r)
        r["inset_um"] = (t_nm * 1e-3) / 2.0        # 错的 t/2
        return r
    CS.alpha_with_thickness = _aw_bad
    rows.append(("M10 薄膜区 δ_eff 硬编码 t/2", *run_smoke()[:2]))
    CS.alpha_with_thickness = _aw

    print("\n%-38s %4s %6s  %s" % ("突变", "rc", "FAIL", "结论"))
    ok = True
    for name, rc, nf in rows:
        if name.startswith("baseline"):
            good = (rc == 0 and nf == 0)
            verdict = "OK（全绿）" if good else "!! 基线应全绿"
        else:
            good = (rc != 0 and nf > 0)
            verdict = "咬住（%d 条红）" % nf if good else "!! 未咬住（假绿）"
        ok = ok and good
        print("%-38s %4s %6s  %s" % (name, rc, nf, verdict))
    print("\n探针结论：%s（%d/%d 突变被咬住）"
          % ("ALL_CAUGHT" if ok else "HAS_UNCAUGHT",
             sum(1 for n, r, f in rows if not n.startswith("baseline") and r != 0 and f > 0),
             len(rows) - 1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
