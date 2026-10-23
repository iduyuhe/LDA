"""D-220 突变探针（scratch · 不入 CI）：证明 run_substrate_caliber_smoke.py 能变红。

惯例：`scripts/*_probe.py` 记录「改了哪几处、应红哪几条」，供人工复核；**不入 CI**。
做法：in-process monkeypatch 生产模块对象（**不碰源文件**）。

人工记录（改动 → 应红判据）：
  · M1 mux 的 eps_eff 回退成字面量 6.5（口径漂移复发）      ⇒ X2/X4 应红
  · M2 TL 放弃反提、硬编码 6.5（真值被拍脑袋覆盖）          ⇒ A1/A3 应红
  · M3 把 FRINGE 改成等于 TL（**悄悄统一成一个数**）        ⇒ G1/G2 应红
  · M4 TL 用 n_eff 冒充 ε_eff（量纲/物理错）                ⇒ A2 应红
  · M5 让阵列几何依赖 eps（**爆炸半径扩大**）               ⇒ X6 应红
  · M6 抹掉偏离登记（deviation 置 0，即假装两口径相同）      ⇒ G2/H3 应红
  · M7 登记表删掉 FRINGE（孤儿口径：有值无主）              ⇒ H1/H2 应红
  · M8 敏感性余量造假（限值压到 1e-6 ⇒ 假装是瓶颈/或反之）  ⇒ G3 应红
🔴 教训：patch 必须打门禁同一模块对象（`lda_qeda.substrate_caliber` / `sc_readout_mux`）；
   其中 M1 打字典、M5 打函数、M2/M3/M4/M6/M8 打模块常量 —— 都必须在**调用前**打。
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "lda"))

import run_substrate_caliber_smoke as S        # noqa: E402
from lda_qeda import substrate_caliber as CAL  # noqa: E402
from lda_qeda import sc_readout_mux as MX      # noqa: E402


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

    _tl = CAL.TL_EPS_EFF_REF
    _neff = CAL.TL_N_EFF_REF
    _fr = CAL.FRINGE_EPS_DESIGN
    _tl_fn = CAL.tl_eps_eff
    _default_plan = dict(MX.DEFAULT_MUX_PLAN)
    _array_cell = MX.mux_array_cell
    _dev = dict(CAL.FRINGE_DISCLOSURE)
    _reg = dict(CAL.__dict__)

    # M1 mux 的 eps_eff 回退成字面量 6.5（漂移复发）
    MX.DEFAULT_MUX_PLAN = dict(_default_plan, eps_eff=6.5)
    rows.append(("M1 mux eps 回退 6.5（漂移复发）", *run_smoke()[:2]))
    MX.DEFAULT_MUX_PLAN = _default_plan

    # M2 TL 放弃反提、硬编码 6.5
    CAL.TL_EPS_EFF_REF = 6.5
    CAL.tl_eps_eff = lambda geom=None: 6.5
    rows.append(("M2 TL 硬编码 6.5（放弃反提）", *run_smoke()[:2]))
    CAL.TL_EPS_EFF_REF = _tl
    CAL.tl_eps_eff = _tl_fn

    # M3 把 FRINGE 悄悄统一成 TL 值
    CAL.FRINGE_EPS_DESIGN = _tl
    rows.append(("M3 FRINGE 改成等于 TL（悄悄统一）", *run_smoke()[:2]))
    CAL.FRINGE_EPS_DESIGN = _fr

    # M4 TL 用 n_eff 冒充 ε_eff
    CAL.tl_eps_eff = lambda geom=None: _neff
    rows.append(("M4 用 n_eff 冒充 ε_eff", *run_smoke()[:2]))
    CAL.tl_eps_eff = _tl_fn

    # M5 让阵列几何依赖 eps（爆炸半径扩大）
    def _cell_eps_dep(params=None):
        p = dict(params or {})
        base = _array_cell(p)
        e = float(p.get("eps_eff", CAL.TL_EPS_EFF_REF))
        return base + [{"kind": "path", "layer": 10, "net": "leak",
                        "width_um": e * 1e-9, "points_um": [(0.0, 0.0), (e, 0.0)]}]
    MX.mux_array_cell = _cell_eps_dep
    rows.append(("M5 阵列几何依赖 eps（半径扩大）", *run_smoke()[:2]))
    MX.mux_array_cell = _array_cell

    # M6 抹掉偏离登记（假装两口径相同）
    CAL.FRINGE_DISCLOSURE = dict(_dev, deviation_vs_tl_pct=0.0)
    rows.append(("M6 抹掉偏离登记（deviation=0）", *run_smoke()[:2]))
    CAL.FRINGE_DISCLOSURE = _dev

    # M7 登记表删掉 FRINGE（孤儿口径）
    CAL.caliber_register = lambda: [r for r in _reg["caliber_register"]() if r["id"] != "FRINGE"]
    rows.append(("M7 登记表删掉 FRINGE", *run_smoke()[:2]))
    CAL.caliber_register = _reg["caliber_register"]

    # M8 敏感性余量造假（把限值压到 1e-6 ⇒ 假装 fringe 是瓶颈）
    _sens = CAL.sensitivity_margin

    def _sens_fake(params=None):
        r = _sens(params)
        r["margin_x"] = 0.5
        r["all_ok"] = False
        return r
    CAL.sensitivity_margin = _sens_fake
    rows.append(("M8 敏感性余量造假（margin=0.5）", *run_smoke()[:2]))
    CAL.sensitivity_margin = _sens

    MX.DEFAULT_MUX_PLAN = _default_plan
    MX.mux_array_cell = _array_cell
    CAL.TL_EPS_EFF_REF, CAL.FRINGE_EPS_DESIGN = _tl, _fr

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
