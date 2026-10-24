"""D-220 · 超导微波**介电口径单一真源**门禁（caliber SSOT）· 能力层 · 净增 0 锚。

## 这道门禁守什么

`eps_eff` 这个符号在量子侧曾有 4 个互不相同、互相零引用的取值（6.0 / 6.0 / 6.5 / 6.25），
而几何反提的真值是 **6.224562**；6.0 ↔ 6.5 互差 **8.333%** ⇒ λ/4 腔长互差
**240.080 µm（3.996%）** ⇒ 频率峰峰 **199.8 MHz**（FDM 音间隔典型 10–50 MHz）。

但那四处 ε **不是同一个物理量**（全截面填充 vs 线间 fringe 场填充），所以**不能统一成一个数**。
本门禁守的是「**来源唯一 + 偏离可见**」：

  A 组  TL 口径必须来自**反提**（不许写字面量）
  X 组  三处消费点必须**接真源**；且**改 ε 不得动几何**（爆炸半径 = 报告值）
  G 组  两口径**允许不等但差值必须量化**；fringe 口径必须证明「不是判决瓶颈」
  H 组  登记表完整性 + 不统一的理由机器化
  Z 组  零增量（不新增锚）

判据标签避开 B/E/S 前缀（那些是锚号前缀，会被 K4 文本代理误判成覆盖）。

纯 stdlib · 零子进程 · 零落盘 · 实测 **~2.0 s**（19 判据；耗时主要在 3 次阵列几何构建
与 5 点敏感度扫描 —— 后者每次要跑 `solve_coupler`。相对 120 s 预算留 61× 余量）。
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

from lda_qeda import substrate_caliber as CAL
from lda_qeda import sc_readout as S4
from lda_qeda import sc_readout_mux as MX
from lda_harness.smoke_kit import make_check

_CNT = {"PASS": 0, "FAIL": 0}
# 🔴 v0.9.275：本文件的 `check` 改用 `smoke_kit` 单一实现（`run_helper_dup_ratchet_smoke`
#   J3/J4 要求「不得再添本地 `def check`」—— 本版把 .271~.275 新增的 5 道门禁全部归一）。
check = make_check(_CNT, ok_key="PASS", bad_key="FAIL", indent="  ",
                   detail_fmt="  |  {d}", detail_on="both", return_ok=True)
# 本文件在 <root>/lda/ 下 ⇒ 兄弟目录 lda_qeda 就是同级的 "lda_qeda"
_QEDA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lda_qeda")

#: 允许出现的「非标定量」字面量 —— 只有真空基准 1.0（物理恒等，不是标定）
_VACUUM_EXEMPT = {1.0}




def _geom_sig(descs) -> str:
    h = hashlib.sha1()
    for d in descs:
        h.update(str(d.get("kind")).encode())
        h.update(str(d.get("net")).encode())
        h.update(str(d.get("rings_um") or d.get("points_um")).encode())
        h.update(str(d.get("width_um")).encode())
    return h.hexdigest()[:16]


def _scan_literals():
    """扫 lda_qeda 里的 eps_eff **默认值/字面量赋值**（不扫表达式）。"""
    pats = (
        re.compile(r'\.get\(\s*"eps_eff"\s*,\s*([0-9]+(?:\.[0-9]+)?)'),
        re.compile(r'"eps_eff"\s*:\s*([0-9]+(?:\.[0-9]+)?)'),
        re.compile(r'eps_eff\s*:\s*float\s*=\s*([0-9]+(?:\.[0-9]+)?)'),
        re.compile(r'eps_eff\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*[,)]'),
    )
    hits = []
    for f in sorted(os.listdir(_QEDA_DIR)):
        if not f.endswith(".py"):
            continue
        p = os.path.join(_QEDA_DIR, f)
        for ln, line in enumerate(open(p, encoding="utf-8", errors="replace"), 1):
            for pat in pats:
                for m in pat.finditer(line):
                    hits.append((f, ln, float(m.group(1)), line.strip()))
    return hits


def main() -> int:
    _CNT["PASS"] = _CNT["FAIL"] = 0
    print("超导微波介电口径单一真源 门禁 smoke（D-220）")

    # ---------------- A 组：TL 口径必须来自反提 ----------------
    tl = CAL.TL_EPS_EFF_REF
    check("A1 TL 口径 ≡ cpw_quasi_static 反提（同值再算一次，rel<1e-15）",
          abs(CAL.tl_eps_eff() - tl) <= 1e-15 * tl, "TL=%.6f" % tl)
    check("A2 n_eff = √ε_eff（与既有 CPW 锚同口径）",
          abs(CAL.TL_N_EFF_REF ** 2 - tl) <= 1e-12 * tl,
          "n_eff=%.6f" % CAL.TL_N_EFF_REF)
    check("A3 参考几何反提值落在开区间 (6.0, 6.5) —— 证明原两个值都是拍的，真值在中间",
          6.0 < tl < 6.5, "TL=%.6f" % tl)
    check("A4 真空极限：εr=1 ⇒ ε_eff = 1.0（保角映射退化正确，非拼凑）",
          abs(CAL.tl_eps_eff({"eps_r": 1.0}) - 1.0) <= 1e-12)
    check("A5 ε_eff 随 εr 单调增（3 点：4.0 / 11.45 / 12.9）",
          CAL.tl_eps_eff({"eps_r": 4.0}) < CAL.tl_eps_eff({"eps_r": 11.45})
          < CAL.tl_eps_eff({"eps_r": 12.9}))

    # ---------------- X 组：消费点必须接真源 + 爆炸半径 ----------------
    lits = _scan_literals()
    bad = [x for x in lits if x[2] not in _VACUUM_EXEMPT]
    check("X1 全 lda_qeda 无「裸 eps_eff 数值默认值」（唯一例外 = 真空基准 1.0）",
          not bad,
          "违规 %d 处：%s" % (len(bad), [(b[0], b[1], b[2]) for b in bad[:4]]) if bad else
          "字面量 %d 处（全为 1.0 真空基准）" % len(lits))

    check("X2 sc_readout_mux.DEFAULT_MUX_PLAN['eps_eff'] ≡ TL 真源（rel<1e-15）",
          abs(float(MX.DEFAULT_MUX_PLAN["eps_eff"]) - tl) <= 1e-15 * tl,
          "DEFAULT=%.6f" % MX.DEFAULT_MUX_PLAN["eps_eff"])

    check("X3 两个 λ/4 闭式的默认 ε ≡ TL 真源（签名默认值，rel<1e-15）",
          abs(MX.resonator_length_um.__defaults__[0] - tl) <= 1e-15 * tl
          and abs(MX.resonator_freq_ghz.__defaults__[0] - tl) <= 1e-15 * tl,
          "len_default=%.6f freq_default=%.6f"
          % (MX.resonator_length_um.__defaults__[0], MX.resonator_freq_ghz.__defaults__[0]))

    plan = MX.mux_plan({"rows": 2, "cols": 2})
    check("X4 mux_plan()['eps_eff'] ≡ TL 真源（规划层不再自带口径）",
          abs(float(plan["eps_eff"]) - tl) <= 1e-15 * tl,
          "plan eps=%.6f" % plan["eps_eff"])

    # X5 fringe 两处的**默认值**必须是登记值（显式传入 <登记值> 与不传等价）
    a_default = S4._control_xtalk({"rows": 2, "cols": 2}, {0: (0.0, 0.0), 1: (22.0, 0.0)})
    a_explicit = S4._control_xtalk({"rows": 2, "cols": 2, "eps_eff": CAL.FRINGE_EPS_DESIGN},
                                   {0: (0.0, 0.0), 1: (22.0, 0.0)})
    from lda_qeda import sc_control as CT
    f_default = CT._fringe_x(1.0, 4.0, {})
    f_explicit = CT._fringe_x(1.0, 4.0, {"eps_eff": CAL.FRINGE_EPS_DESIGN})
    check("X5 fringe 两处默认值 ≡ 登记值（不传 与 显式传登记值 逐位相同）",
          a_default == a_explicit and f_default == f_explicit,
          "S4 %.6e / SC %.6e" % (a_default[0]["X"] if a_default else 0.0, f_default))

    # X6 爆炸半径：改 ε 不得动几何（几何与 ε 解耦 ⇒ 本版只改报告值）
    g_lo = _geom_sig(MX.mux_array_cell({"rows": 2, "cols": 2, "eps_eff": 6.0}))
    g_hi = _geom_sig(MX.mux_array_cell({"rows": 2, "cols": 2, "eps_eff": 6.5}))
    g_tl = _geom_sig(MX.mux_array_cell({"rows": 2, "cols": 2}))
    check("X6 几何与 ε 解耦：ε=6.0 / 6.5 / 真值 三者的阵列几何指纹逐位相同",
          g_lo == g_hi == g_tl, "sig=%s" % g_tl)

    # ---------------- G 组：允许不等 + 偏离可见 + 余量 ----------------
    fr = CAL.FRINGE_EPS_DESIGN
    dev = (fr - tl) / tl * 100.0
    check("G1 两口径【允许不等】且确实不等（防有人悄悄把它们统一成一个数）",
          abs(fr - tl) > 1e-6, "TL=%.6f FRINGE=%.6f Δ=%.4f" % (tl, fr, fr - tl))
    check("G2 偏离被量化且与登记表一致（deviation_vs_tl_pct）",
          abs(CAL.FRINGE_DISCLOSURE["deviation_vs_tl_pct"] - dev) <= 1e-12,
          "%+.4f%%" % dev)

    sm = CAL.sensitivity_margin()
    check("G3 fringe 口径余量 ≥ 10×（实测 %.1f×）⇒ 标为设计参数是诚实的，不是偷懒"
          % sm["margin_x"],
          sm["margin_x"] >= 10.0 and sm["all_ok"],
          "X=%.3e vs 限值 %.3e" % (sm["base_max_control_xtalk"], sm["limit"]))

    check("G4 反例在场：若把 mux 的真源换回 6.5，腔长会偏离 2.19%（即 X2 会红）",
          abs(MX.resonator_length_um(5.0, eps_eff=6.5)
              / MX.resonator_length_um(5.0) - 1.0) > 0.02,
          "偏差 %.4f%%" % ((MX.resonator_length_um(5.0, eps_eff=6.5)
                            / MX.resonator_length_um(5.0) - 1.0) * 100.0))

    # ---------------- H 组：登记完整性与不统一的理由 ----------------
    reg = CAL.caliber_register()
    check("H1 登记表覆盖两口径且 derivable 标注正确（TL=True / FRINGE=False）",
          {r["id"] for r in reg} == {"TL", "FRINGE"}
          and all(r["derivable"] == (r["id"] == "TL") for r in reg),
          "ids=%s" % sorted(r["id"] for r in reg))

    check("H2 每个口径都声明了 used_by（防「有值无主」的孤儿口径）",
          all(r.get("used_by") for r in reg)
          and all(r.get("source") for r in reg))

    wnu = CAL.why_not_unified()
    check("H3 不统一的理由机器化（双向：统一到 TL 错在哪 / 统一到 FRINGE 错在哪 + 差值）",
          (not wnu["unified"]) and wnu["reason_if_unified_to_TL"]
          and wnu["reason_if_unified_to_FRINGE"]
          and abs(wnu["deviation_pct"] - dev) <= 1e-12)

    # ---------------- Z 组：零增量 ----------------
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from lda_harness.benchmarks import BENCHMARK_DEFS as D
        n = len(D)
        check("Z1 零增量：账本锚数 = %d（本门禁只统一来源，不加锚）" % n, n == 541)
    except Exception as e:                                   # noqa: BLE001
        check("Z1 零增量：账本锚数不变", False, "不可读：%s" % e)

    n_pass = _CNT["PASS"]
    print("\n门禁 smoke：%d PASS / %d FAIL（共 %d 项）"
          % (n_pass, _CNT["FAIL"], n_pass + _CNT["FAIL"]))
    return 0 if _CNT["FAIL"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
