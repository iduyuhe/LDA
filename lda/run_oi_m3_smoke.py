# -*- coding: utf-8 -*-
"""M3（3.2T / CPO · G-OI6）门禁：400G/lane 带宽墙 · CPO 电通道 · die↔die 热 + 闭环热调 ·
同口径功耗账 · 2.5D 版图签核。

🔴 本门禁的判据纪律（本项目反复血的）：
  · **golden = 闭式物理律**（TWMZM 解析积分 / 电报闭式 / 二维对数热场 / 代数闭环稳态）。
    第二通道（ABCD 矩阵链 / 1D FDTD / M2b 有限差分热网络）**只互验，不是 golden**。
  · 判据必须**咬语义不咬字面**；「同源相等」单独用是**假判据** ⇒ 每条 golden 都配
    第二独立通道（矩阵链递推 / 时域 FDTD）或**退化/边界**判据。
  · **探针先证「能变红」再信判据**；探针落点必须打在**被门禁真正消费的那份引用**上
    （模块级函数 → patch `lda_l2.oi_m3` 的属性，不能只改调用方）。
  · 还原后基线门禁**必须重新全绿**（探针不得污染真判据）。

判据（共 51 项，来自 `oi_m3.oi_m3_self_check`）：
  C01–C04  规格锚 / 3.2T 常量互锁（**由 200G 档派生**，不重抄）
  C05–C15  ① TWMZM 带宽墙（闭式解析 + ABCD 链第二通道 + 速度失配 + f_RC ∝ 1/L²）
  C16–C24  ② CPO 电通道（√f 窗口 / 长度衰减 / NEXT / PDN 地弹 / FDTD ⟷ 闭式）
  C25–C34  ③ 跨 die 热 + **闭环热调**（收敛路径返回 / 代数⟷不动点 / **双计必发散** /
           ∝1/R_h（求解器输出）/ 单向执行器 / 残余失谐）+ **单一真源可达 / 无旁路热阻键**（F6/F7）
  C35–C39  ④ 功耗同口径账（对拍 / CPO 热代价 / 独有项 / 红线 / 同参）
  C40–C46  ⑤ 2.5D 版图（电层 DRC / fiber 不落版图 / LVS **独立解码 4 条** / 光引擎复用）
  C47–C51  复用底座在 400G 速率级仍成立 + 诚实边界

探针（**先证能变红**）：
  P1  TWMZM 把光相位基准从 γ 里**减掉**（相位算重 ⇒ q 相位变 2β_mw−β_opt）
      ⇒ C05「带宽墙」必红
  P2  f_RC 漏一个 L（∝1/L）⇒ C13「∝ 1/L²」必红
  P3  ABCD 链末端**开路**（丢掉特性阻抗匹配端接）⇒ C07/C08 必红
  P4  NEXT 耦合比清零时**钳位成 −3000 dB**（不是 −∞）⇒ C19 必红
  P5  FDTD 步长**越 CFL**（Δt = 1.5·Δx/v_p）⇒ C22/C23 必红
  P6  闭环热调**退回「一次性」**（稳态功率与残余失谐恒 0）⇒ C26/C27 必红
  P7  🔴 热调**双计**（把「加热器→温升→波长」通路算两遍 ⇒ 环路增益 A≈28 ≫ 1）
      ⇒ 走**真实现** fixed_point ⇒ 「稳态解收敛」判据必红（首版真踩过的坑：1e88 K）
  P8  功耗账**漏掉 CPO 独有项** interposer_pdn ⇒ C29 对拍必红
  P9  **片外 fiber 落进版图** ⇒ C35 必红
  P10 衰减把 √f 律写成 f 律 ⇒ C16 必红
  P11 焊盘⟷走线**错位**（走线起点移出焊盘 1 µm）⇒「无悬空」判据必红
  P12 **删一条走线**（末焊盘悬空）⇒「无悬空」判据必红
  P13 **对照组**：同一坏几何喂「旧式计数 LVS」仍**假绿** ⇒ 证明新判据有判别力
  P14 🔴 复活死配置 `OI_M3_PROCESS["r_th_thermal_k_per_w"] = 8.0`（旁路热阻键）⇒「无旁路热阻键」必红
  P15 🔴 令单一真源 `lda_design.active_models` **不可达**（sys.modules 置 None）⇒「单一真源可达」必红
      （首版回退 `return 1.0` 恰等真值 ⇒ 静默降级看不见；回退已删 · F7）
  R   探针还原后基线门禁**必须重新全绿**（探针不污染真判据）
"""
from __future__ import annotations

import cmath
import importlib
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LDA = os.path.dirname(_HERE)
if _LDA not in sys.path:
    sys.path.insert(0, _LDA)

from lda_harness.smoke_kit import make_check  # noqa: E402
check = make_check(globals(), ok_key="PASS", bad_key="FAIL",
                   indent="", detail_fmt=' —— {d}')


def section(title: str) -> None:
    print("-" * 74)
    print("  " + title)


def report() -> int:
    n_pass = globals().get("PASS", 0)
    n_fail = globals().get("FAIL", 0)
    print("-" * 74)
    print(f"汇总：{n_pass} PASS / {n_fail} FAIL / 共 {n_pass + n_fail} 项")
    return 0 if (n_pass and not n_fail) else 1


_M3 = "lda_l2.oi_m3"


def _mod(name: str = _M3):
    return importlib.import_module(name)


def base_checks() -> dict:
    """跑全量判据，返回 `{判据名: bool}`。"""
    M = _mod()
    return {name: bool(ok) for name, ok in M.oi_m3_self_check(verbose=False)["checks"]}


def _red(chk: dict, key: str) -> bool:
    """探针断言：名字**含** `key` 的判据（们）**必须全为 False**（先证能变红）。"""
    hits = [v for k, v in chk.items() if key in k]
    return bool(hits) and not any(hits)


# ═════════════════════════════════════════════════════════════════════════════
# 突变探针
# ═════════════════════════════════════════════════════════════════════════════
def run_probes() -> dict:
    M = _mod()
    orig = {k: getattr(M, k) for k in (
        "twmzm_response_closed", "rc_pole_hz", "twmzm_response_ladder",
        "xtalk_next_db", "fdtd_telegraph", "closed_loop_thermal_steady",
        "tuning_slope_nm_per_k", "power_breakdown", "cpo_2p5d_geometry",
        "echannel_att_db", "_pdn_lvs")}
    res: dict = {}

    def restore() -> None:
        for k, v in orig.items():
            try:
                setattr(M, k, v)
            except Exception:
                pass

    # ── P1：TWMZM 相位算重（把 −ω·n_g,opt/c 的减法丢掉）───────────────────────
    #    探针只改**相位基准**这一处，其余（primers/γ/积分形式）与生产实现逐行同构
    def _dup_phase(f_hz, l_mm=None, dn_g_resid=None):
        r_pm, l_pm, c_pm, L = M._electrode_primers(l_mm, dn_g_resid)
        g = M.propagation_gamma(f_hz, r_pm, l_pm, c_pm)
        q = complex(g.real, g.imag)            # 🔴 少了 −ω·n_g,opt/c ⇒ 相位重了一遍
        if abs(q) * L < 1e-9:
            return 1.0 + 0j
        return (1.0 - cmath.exp(-q * L)) / (L * q)

    M.twmzm_response_closed = _dup_phase
    res["P1"] = _red(base_checks(), "带宽墙：TWMZM")
    restore()

    # ── P2：f_RC 漏一个 L（∝1/L 而不是 ∝1/L²）──────────────────────────────────
    p = M.OI_M3_PROCESS
    _r = float(p["r_elect_ohm_per_mm"]) * 1e3
    _c = float(p["c_elect_fF_per_mm"]) * 1e-15 / 1e-3

    def _bad_rc(l_mm=None):
        l = 1.0 if l_mm is None else float(l_mm)
        return 1.0 / (2.0 * math.pi * _r * _c * l)      # 🔴 只乘一个 L ⇒ ∝1/L

    M.rc_pole_hz = _bad_rc
    res["P2"] = _red(base_checks(), "∝ 1/L²")
    restore()

    # ── P3：ABCD 链末端开路（丢掉 Z0 = √(z/y) 匹配端接）─────────────────────────
    def _bad_ladder(f_hz, n_seg=200, l_mm=None, dn_g_resid=None):
        r_pm, l_pm, c_pm, L = M._electrode_primers(l_mm, dn_g_resid)
        n = max(2, int(n_seg)); seg = L / n; w = 2.0 * math.pi * f_hz
        z = (r_pm + 1j * w * l_pm) * seg
        y = 1j * w * c_pm * seg
        m11, m12, m21, m22 = (1.0 + z * y), z, y, 1.0 + 0j
        t11, t12, t21, t22 = m11, m12, m21, m22
        for _ in range(n - 1):
            s11 = t11 * m11 + t12 * m21
            s12 = t11 * m12 + t12 * m22
            s21 = t21 * m11 + t22 * m21
            s22 = t21 * m12 + t22 * m22
            t11, t12, t21, t22 = s11, s12, s21, s22
        if abs(t11) < 1e-300:
            return 0.0 + 0j
        v_l = 1.0 / t11                      # 🔴 末端开路 ⇒ 无匹配端接（Z0=∞）
        v, i = 1.0 + 0j, t21 * v_l
        k_opt = 2.0 * math.pi * f_hz * float(M.OI_M3_PROCESS["n_g_opt"]) / M.C_M_S
        acc = 0.0 + 0j
        for k in range(n):
            acc += v * cmath.exp(1j * k_opt * (k + 0.5) * seg)
            v, i = v - z * i, -y * v + (1.0 + z * y) * i
        return acc / n

    M.twmzm_response_ladder = _bad_ladder
    res["P3"] = _red(base_checks(), "ABCD 链相对误差")
    restore()

    # ── P4：NEXT 零耦合钳位成 −3000 dB（不是 −∞）──────────────────────────────
    o4 = orig["xtalk_next_db"]

    def _bad_xt(f_hz=None, k=None):
        r = o4(f_hz, k)
        if k == 0.0:
            r = dict(r); r["xtalk_at_zero_coupling_db"] = -3000.0   # 🔴 假 clamp
        return r

    M.xtalk_next_db = _bad_xt
    res["P4"] = _red(base_checks(), "耦合比清零")
    restore()

    # ── P5：FDTD 越 CFL（Δt = 1.5·Δx/v_p ⇒ a·b = 2.25 > 1）────────────────────
    def _bad_fdtd(pulse_s=1.5e-12, l_mm=None, n_cells=400, tail_ps=120.0, r_on=False):
        #    🔴 本探针刻意走**无损**电报方程（只破 CFL，不引入 R 项）⇒ 不取 r_bus
        pp = M.OI_M3_PROCESS
        l_mm = float(pp["bus_len_mm"] if l_mm is None else l_mm)
        lc = float(pp["l_bus_nH_per_mm"]) * 1e-9 / 1e-3
        c = float(pp["c_bus_fF_per_mm"]) * 1e-15 / 1e-3
        L = l_mm * 1e-3
        n = max(8, int(n_cells)); dx = L / n
        v_p = 1.0 / math.sqrt(lc * c)
        dt = 1.5 * dx / v_p                                  # 🔴 越过蛙跳稳定界
        n_step = max(8, int(math.ceil(max(tail_ps * 1e-12, 3.0 * L / v_p) / dt)))
        i_out = n
        v = [0.0] * (n + 1); i_arr = [0.0] * n
        t_axis = [k * dt for k in range(n_step)]
        src = [math.exp(-((t / pulse_s) ** 2)) for t in t_axis]
        v_hist = [0.0] * n_step
        c1, c2 = dt / (lc * dx), dt / (c * dx)
        for s in range(n_step):
            for kk in range(n):
                i_arr[kk] = i_arr[kk] - c1 * (v[kk + 1] - v[kk])
            i_right = i_arr[1:] + [0.0]
            for kk in range(1, n + 1):
                v[kk] = v[kk] - c2 * (i_right[kk - 1] - i_arr[kk - 1])
            v[0] = src[s]; v_hist[s] = v[i_out]
        k_out = max(range(n_step), key=lambda z: v_hist[z])
        y1, y2, y3 = v_hist[k_out - 1], v_hist[k_out], v_hist[k_out + 1]
        den = y1 - 2.0 * y2 + y3
        shift = 0.5 * (y1 - y3) / den if den != 0.0 else 0.0
        t_peak = (k_out + shift) * dt
        tau = L / v_p
        return {"tau_fdtd_s": t_peak, "tau_closed_s": tau,
                "rel_err": abs(t_peak - tau) / tau, "peak_out_v": float(v_hist[k_out]),
                "phase_ok": bool(abs(t_peak - tau) / tau < 0.05)}

    M.fdtd_telegraph = _bad_fdtd
    res["P5"] = _red(base_checks(), "FDTD 时域相速") or _red(base_checks(), "FDTD 输出幅度")
    restore()

    # ── P6/P7：闭环热调退回「一次性」 / 🔴 双计 ────────────────────────────────
    def _one_shot(n_lanes=None, setpoint_over_ambient_c=None,
                  r_h_override_k_per_mw=None, **kw):
        # 🔴 退回「一次性」：稳态执行器功率与残余失谐**恒 0**（闭环形同虚设）
        r = dict(orig["closed_loop_thermal_steady"](
            n_lanes, setpoint_over_ambient_c, r_h_override_k_per_mw, **kw))
        r.update(p_actuator_required_mw_per_lane=0.0, residual_nm=0.0,
                 closed_loop=False, solution="one_shot", converged=True)
        return r

    M.closed_loop_thermal_steady = _one_shot
    res["P6"] = _red(base_checks(), "稳态执行器功率 ∝ 1/R_h") \
        or _red(base_checks(), "残余失谐落在")
    restore()

    def _double_count(*a, **kw):
        #   🔴 复刻首版真 bug 形态：把「加热器→温升→波长」通路**算两遍**
        #      （灵敏度算错 ⇒ 环路增益 A≈28 ≫ 1）⇒ 走**真实现**的 fixed_point 路径
        #      ⇒ 迭代必发散（**不是**直接改输出字段 —— 那只是自证探针）。
        kw2 = {k: v for k, v in kw.items() if k not in ("solve_mode", "loop_gain")}
        return orig["closed_loop_thermal_steady"](
            *a, solve_mode="fixed_point", loop_gain=28.0, **kw2)

    M.closed_loop_thermal_steady = _double_count
    res["P7"] = _red(base_checks(), "稳态解**收敛**")
    restore()

    # ── P8：功耗账漏掉 CPO 独有项 interposer_pdn ──────────────────────────────
    o8 = orig["power_breakdown"]

    def _bad_pw(form="cpo", n_lanes=None):
        # 🔴 复刻真实 bug：CPO 独有项 interposer_pdn **挂在 sum 之后** ⇒
        #    items 加总里含它，per_lane_total 里不含 ⇒ 对拍必红。
        #    （首版探针改成「置 0 后重算 sum」⇒ 两边仍一致 ⇒ 假绿！必须造真分歧。）
        r = o8(form, n_lanes)
        it = dict(r["items_mw_per_lane"])                    # 🔴 该项**非零保留**在 items 里
        it_nopdn = {k: v for k, v in it.items() if k != "interposer_pdn_mw"}
        r["items_mw_per_lane"] = it
        r["per_lane_total_mw"] = sum(it_nopdn.values())      # 🔴 但 per_lane_total 漏掉它 ⇒ 必红
        r["module_total_w"] = r["per_lane_total_mw"] * r["n_lanes"] / 1000.0
        return r

    M.power_breakdown = _bad_pw
    res["P8"] = _red(base_checks(), "对拍：逐项加总")
    restore()

    # ── P9：片外 fiber 落进版图 ────────────────────────────────────────────────
    o9 = orig["cpo_2p5d_geometry"]

    def _bad_geo(oe_structures=None):
        r = o9(oe_structures)
        r = dict(r); r["structures"] = dict(r.get("structures", {}))
        r["structures"]["FIBER"] = ["fiber-body"]            # 🔴 片外 fiber 落版图
        r["fiber_in_layout"] = True
        r["oe_structures_inherited"] = bool(oe_structures)
        return r

    M.cpo_2p5d_geometry = _bad_geo
    res["P9"] = _red(base_checks(), "片外 fiber 不落版图")
    restore()

    # ── P10：把 √f 律写成 f 律（每倍频多乘 √2）────────────────────────────────
    o10 = orig["echannel_att_db"]

    def _bad_att(f_hz, l_mm=None):
        return o10(f_hz, l_mm) * math.sqrt(max(f_hz, 1e-12) / 1e9)

    M.echannel_att_db = _bad_att
    res["P10"] = _red(base_checks(), "R 主导子带")
    restore()

    # ── P11：焊盘 ⟷ 走线**错位**（把一条走线起点移出焊盘右边界 1 µm）────────────
    #     🔴 真灌 bug：改**生成端几何**（重编码 M1 PATH），经**独立解码器** → 真 LVS
    #     ⇒「无悬空」判据必红。**不是**直接改输出字段（那只是自证探针）。
    from lda_l2 import gds_export as _gx11
    o11 = orig["cpo_2p5d_geometry"]

    def _bad_geo_mismatch(oe_structures=None):
        r = dict(o11(oe_structures))
        st = dict(r["structures"])
        p = M.OI_M3_PROCESS
        w = float(p["m1_width_um"])
        pad = float(p["interposer_pad_um"])
        ax = float(p["asic_die_x_um"])
        n_pitch = max(1, int(ax // (2.0 * float(p["diff_pitch_um"]))))
        x = -ax / 2 + 0.5 * (ax / n_pitch) + pad / 2 + 1.0      # 🔴 移出焊盘右边界 1 µm
        m1s = list(st["M1_ROUTING"])
        m1s[0] = _gx11.path(M._LAYER_M1, w, [(x, 0.0), (x, ax * 0.5 + pad)])
        st["M1_ROUTING"] = m1s
        r["structures"] = st
        return r

    M.cpo_2p5d_geometry = _bad_geo_mismatch
    base_bad = base_checks()
    res["P11"] = _red(base_bad, "无悬空")

    # ── P13：**对照组** —— 同一坏几何喂「旧式计数 LVS」必须仍**假绿**
    #     证明新判据确实有判别力（而不是「怎么改都红」的粗糙判据）。
    def _count_only_lvs(structs):
        #    🔴 复刻首版真 bug 形态：只统计元素计数，端点是否落在焊盘上**根本不检查**
        n = sum(len(v) for v in structs.values() if isinstance(v, (list, tuple)))
        return {"n_nets": n, "nets": [{"net": "BUS_LANE_1", "endpoints_on_pads": True}],
                "n_pads": n, "n_paths": n, "n_dangling_paths": 0, "n_uncovered_pads": 0,
                "n_offdie_touch_points": 0, "pass": bool(n > 0),
                "decoder": "old_count_only（首版形态）", "kind": "geometry_topology_lvs"}

    M._pdn_lvs = _count_only_lvs
    legacy = [v for k, v in base_checks().items() if "无悬空" in k]
    res["P13"] = bool(legacy) and all(legacy)      # 旧式对同一坏几何**仍绿** ⇒ 对照组成立
    restore()

    # ── P12：删一条走线 ⇒ **悬空焊盘**（反向完备必红）──────────────────────────
    def _bad_geo_drop(oe_structures=None):
        r = dict(o11(oe_structures))
        st = dict(r["structures"])
        st["M1_ROUTING"] = list(st["M1_ROUTING"])[:-1]          # 🔴 删末条 ⇒ 末焊盘悬空
        r["structures"] = st
        return r

    M.cpo_2p5d_geometry = _bad_geo_drop
    res["P12"] = _red(base_checks(), "无悬空")
    restore()

    # ── P14：🔴 复活死配置「旁路热阻键」（8.0 K/W）⇒ F6 守卫必红 ──────────────────
    M.OI_M3_PROCESS["r_th_thermal_k_per_w"] = 8.0
    res["P14"] = _red(base_checks(), "无旁路热阻键")
    M.OI_M3_PROCESS.pop("r_th_thermal_k_per_w", None)
    restore()

    # ── P15：🔴 单一真源不可达 ⇒ F7 可达性判据必红（回退已删，不能再静默降级）────────
    #     🔴 真灌故障：把 `lda_design` 从 `sys.modules` 里置 None ⇒ `from lda_design import
    #     active_models` 真抛 ImportError（不是直接改判据返回值 = 自证探针）。
    import sys as _sys
    _keep = _sys.modules.get("lda_design", "__MISSING__")
    _sys.modules["lda_design"] = None
    try:
        res["P15"] = (M.single_source_reachable_m3() is False)
    finally:
        if _keep == "__MISSING__":
            _sys.modules.pop("lda_design", None)
        else:
            _sys.modules["lda_design"] = _keep
    restore()

    return res


def main() -> int:
    base = base_checks()
    section("M3（G-OI6）门禁 · 基线判据（51 项）")
    for k in sorted(base):
        check("  %s" % k, base[k])
    # 判据数自行锁住：门禁只管看得见的集合 ⇒ 新判据静默进盲区
    check("R0 判据集合规模 == 51（新增判据必须同步本门禁与定稿索引）", len(base) == 51)
    section("M3 突变探针（先证能变红）")
    probes = run_probes()
    for k in sorted(probes):
        check("  %s" % k, bool(probes[k]))
    section("M3 探针还原后基线复检")
    after = base_checks()
    same = after == base
    check("R1 探针还原后判据集合与原基线逐项一致（探针不污染真判据）", same)
    check('R2 探针还原后基线仍**全部 PASS**（不是「全变绿/全变红」的假还原）',
          bool(after) and all(after.values()))
    return report()


if __name__ == "__main__":
    raise SystemExit(main())
