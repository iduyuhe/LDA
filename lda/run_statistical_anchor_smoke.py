"""Phase 3 统计锚 smoke：S7 蒙特卡洛分布锚（红线 + 防自证）。

覆盖：
  ① 蒙特卡洛均值收敛于解析 10.5（|mean−10.5|<0.15，采样噪声界）
  ② 分布方向正确（p5 < 解析 < p95——损耗随机增大 margin 变差）
  ③ 种子可复现（同种子两次运行逐样本一致——统计锚判决前提）
  ④ 🔴 红线断言：判决路径零 LLM（statistical_anchor 模块不引用任何
     agent/llm 模块；harness S7 的 oracle_kind 为确定性统计量）
  ⑤ S7 harness reference PASS（golden 自洽）
  ⑥ 扰动负例：损耗整体 +1dB → 分布下移 → candidate 偏离 golden > tol 被 FAIL 抓
  ⑦ 题库计数 469 题（B1-B451 = 446 + E1-E10 = 10 + S1-S13 = 13）
  ⑧ S8 OSNR 统计锚（模板复用：Jensen 方向 + golden 收敛）
  ⑨ 蒙特卡洛收敛性（N 扫描收敛带）

运行：python run_statistical_anchor_smoke.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_harness.benchmarks import BENCHMARK_DEFS, BENCHMARK_ORDER
from lda_harness.golden import golden_value
from lda_harness.harness import VerificationHarness
from lda_harness.statistical_anchor import (
    distribution_report, margin_stats, monte_carlo_margins,
    s7_statistical_margin_anchor, s8_statistical_osnr_anchor,
    monte_carlo_osnr, osnr_distribution_report, convergence_scan,
)
from lda_harness.verification_adapters import build_harness_specs

_PASS = 0
_FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    mark = "PASS" if cond else "FAIL"
    if cond:
        _PASS += 1
    else:
        _FAIL += 1
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))


def main() -> int:
    print("Phase 3 统计锚 smoke（S7 蒙特卡洛分布 · 红线 + 防自证）")

    # ① 均值收敛于解析值（独立手算参照，非调用被测）
    r = distribution_report()
    analytic = 10.5  # S1 解析 margin：0 − 6 − 3 − 0.5 + 20
    check("均值收敛于解析 10.5（N=2000 采样噪声 <0.15）",
          abs(r["stats"]["mean"] - analytic) < 0.15,
          f"mean={r['stats']['mean']}")

    # ② 分布方向：p5 < 解析 < p95（最坏情况维度）
    check("分布方向正确（p5 < 解析 < p95）",
          r["direction_ok"], f"p5={r['stats']['p5']} p95={r['stats']['p95']}")
    check("p5 显著低于 mean（损耗增大方向 margin 变差）",
          (r["stats"]["mean"] - r["stats"]["p5"]) > 0.5,
          f"Δ={r['stats']['mean'] - r['stats']['p5']:.3f}")

    # ③ 种子可复现（判决前提）
    m1 = monte_carlo_margins(seed=42)
    m2 = monte_carlo_margins(seed=42)
    check("种子 42 可复现（逐样本一致）", m1 == m2)
    m3 = monte_carlo_margins(seed=7)
    check("不同种子分布不同（随机性真实存在）", m1 != m3)

    # ④ 红线断言：判决路径零 LLM（只检查 import 语句——docstring/注释
    #    提及 LLM 属说明文字非引用；真正引用必然出现在 import 行）
    src_lines = open(os.path.join(os.path.dirname(__file__),
                                  "lda_harness", "statistical_anchor.py"),
                     encoding="utf-8").read().splitlines()
    imports = [ln for ln in src_lines
               if ln.strip().startswith(("import ", "from "))]
    banned = [w for w in ("llm", "agent", "openai", "anthropic", "gpt")
              if any(w.lower() in ln.lower() for ln in imports)]
    check("红线：statistical_anchor import 零 LLM/agent", not banned,
          f"banned={banned}" if banned else "仅标准库 import")
    specs, _ = build_harness_specs()
    s7s = [x for x in specs if x.spec_id == "S7"]
    check("S7 oracle 为确定性统计量（非 LLM oracle）",
          len(s7s) == 1 and s7s[0].oracle_kind != "llm_judge",
          f"oracle_kind={s7s[0].oracle_kind if s7s else '?'}")

    # ⑤ S7 harness reference PASS（golden 自洽）
    harness = VerificationHarness(BENCHMARK_DEFS)
    s7_specs = [s for s in harness.resolve_specs(None) if s.get("id") == "S7"]
    from lda_harness.harness import ReferenceCandidate
    cand = ReferenceCandidate()
    res = harness.run(s7_specs, cand)
    check("S7 reference PASS（golden 自洽）",
          res[0].passed, f"{res[0].candidate} vs {res[0].golden}")

    # ⑥ 扰动负例：损耗整体 +1dB → 分布下移 → FAIL 被抓
    margins_bad = monte_carlo_margins(
        grating_db=-4.0, wg_loss_db_cm=4.0, ring_il_db=-1.5)  # 各损耗 +1dB
    bad_mean = margin_stats(margins_bad)["mean"]
    golden = s7_statistical_margin_anchor()
    # 手算：total=−4×2−4×1−1.5=−13.5 → margin=0−13.5+20=6.5
    check("扰动负例：损耗+1dB 分布下移（mean≈6.5）",
          abs(bad_mean - 6.5) < 0.3, f"mean={bad_mean}")
    check("扰动负例：偏离 golden > tol 被 FAIL 抓（防自证门禁）",
          abs(bad_mean - golden) > 0.15,
          f"Δ={abs(bad_mean - golden):.3f} > 0.15")

    # ⑦ 题库计数（B+E+S 动态，v0.9.51 起不再硬编码 50/7；
    #    v0.9.67 新增 B33；v0.9.69/v0.9.70 启用 B31/B32 → B 类连续 B1-B33、
    #    v0.9.79 路径 B 扩基新增 B34/B36/B37/B40/B41（末位跳至 B41，B35 复用、
    #    B38/B39 预留缺口）→ 总数 61；v0.9.84 路径 B-4 扩基新增 B65-B68/B70-B71/
    #    B73-B88（缺口 B69 相移/B72 线宽预留）→ 总数 83；v0.9.85 路径 B-5 扩基新增
    #    B89-B104（氢原子径向/3D-HO/圆波导/矩形波导族）→ 总数 99；v0.9.86 路径 B-6 扩基
    #    新增 B105-B120（刚性转子/2D 方势阱/三角势阱/球形势阱族，稀释 terminal）→ 总数 115；
    #    v0.9.87 路径 B-7 扩基新增 B121-B136（Morse 势/2D 各向异性谐振子/3D 长方体势阱/
    #    类氢激发态族）→ 总数 131，此守卫须精确跟账本）
    b_ids = [b for b in BENCHMARK_ORDER if b.startswith("B")]
    e_ids = [b for b in BENCHMARK_ORDER if b.startswith("E")]
    s_ids = [b for b in BENCHMARK_ORDER if b.startswith("S")]
    expected_b = ([f"B{i}" for i in range(1, 35)]          # B1-B34
                  + ["B36", "B37", "B40", "B41"]            # 缺口 B35 预留
                  + [f"B{i}" for i in range(42, 52)]        # B42-B51 = Batch B-2 十锚
                  + [f"B{i}" for i in range(52, 65)]        # B52-B64 = Batch B-3 十三锚
                  + [f"B{i}" for i in range(65, 69)]        # B65-B68 = Batch B-4 四锚
                  + ["B70", "B71"]                          # 缺口 B69 相移预留
                  + [f"B{i}" for i in range(73, 89)]        # B73-B88 = Batch B-4 十六锚（缺口 B72 线宽预留）
                  + [f"B{i}" for i in range(89, 105)]       # B89-B104 = Batch B-5 十六锚（氢原子径向/3D-HO/圆波导/矩形波导）
                  + [f"B{i}" for i in range(105, 121)]      # B105-B120 = Batch B-6 十六锚（刚性转子/2D 方势阱/三角势阱/球形势阱）
                  + [f"B{i}" for i in range(121, 137)]      # B121-B136 = Batch B-7 十六锚（Morse 势/2D 各向异性谐振子/3D 长方体势阱/类氢激发态）
                  + [f"B{i}" for i in range(137, 153)]      # B137-B152 = Batch B-8 十六锚（2D 类氢/2D 圆环+AB 通量/3D 有限深球形阱/各向异性 3D 谐振子）
                  + [f"B{i}" for i in range(153, 169)]     # B153-B168 = Batch B-9 十六锚（4阶 Euler-Bernoulli 梁/Hulthen 势/Fock-Darwin 量子点/Rosen-Morse II 势）
                  + [f"B{i}" for i in range(169, 185)]     # B169-B184 = Batch B-10 十六锚（Mathieu 周期系数 ODE/椭圆积分与椭球静电/Fresnel 积分/线性扩散热核时间推进）
                  + [f"B{i}" for i in range(185, 201)]     # B185-B200 = Batch B-11 十六锚（量子统计积分 Γ·ζ/经典二体 Kepler 轨道/辐射传热角系数/Voigt 谱线轮廓）
                  + [f"B{i}" for i in range(201, 217)]     # B201-B216 = Batch B-12 十六锚（正交多项式高斯求积/连分数有理逼近/Durand–Kerner 求根/₂F₁ 超几何 Euler 积分）
                  + [f"B{i}" for i in range(217, 233)]     # B217-B232 = Batch B-13 十六锚（Grünwald–Letnikov 分数阶导数/矩阵指数 scaling–squaring/固定步长梯度下降/第二类 Volterra 分块梯形）
                  + [f"B{i}" for i in range(233, 249)]     # B233-B248 = Batch B-14 十六锚（定常对流–扩散中心差分/第二类 Fredholm 可分核 Nyström/自然三次样条逼近/非线性两点边值打靶法）
                  + [f"B{i}" for i in range(249, 265)]    # B249-B264 = Batch B-15 十六锚（延迟泛函微分方程分步法/Kirchhoff 薄板双调和 13 点差分/一维输运半拉格朗日特征线/聚焦 NLSE 孤子分裂步 Fourier）
                  + [f"B{i}" for i in range(265, 281)]    # B265-B280 = Batch B-16 十六锚（Burgers tanh 行波 RK4+中心差分/广义指数积分 E_n 截断复合 Simpson/Haar 小波多分辨投影逐层低通）
                  + [f"B{i}" for i in range(281, 297)]    # B281-B296 = Batch B-17 十六锚（线性受迫阻尼 ODE 指数时间差分 ETD2/Zernike 圆域模态 RMS 极坐标中点求积/Duffing 硬化振子四阶组合辛积分 Yoshida）
                  + [f"B{i}" for i in range(297, 313)]    # B297-B312 = Batch B-18 十六锚（振荡积分 Filon 型分段二次求积/Gauss–Legendre 2 级隐式 RK 四阶 A-稳定/Adams–Bashforth 4 阶线性多步）
                  + [f"B{i}" for i in range(313, 329)]     # B313-B328 = Batch B-19 十六锚（广义 Lane–Emden 奇异 IVP Taylor+RK4/二维 Laplace 间接单层位势 BEM/Eikonal 制造解 FMM）
                  + [f"B{i}" for i in range(329, 345)]     # B329-B344 = Batch B-20 十六锚（修正 Bessel I_ν/球谐 Y_l^m 自投影/一维 MQ-RBF 插值）
                  + [f"B{i}" for i in range(345, 361)]      # B345-B360 = Batch B-21 十六锚（Hermite/Laguerre 多项式 + Bernstein 多项式逼近）
                  + [f"B{i}" for i in range(361, 374)]    # B361-B373 = Batch B-22 十三锚（阶跃/渐变光纤物理定律族）
                  + [f"B{i}" for i in range(374, 387)]     # B374-B386 = Batch B-23 十三锚（高斯光束旁轴光学族）
                  + [f"B{i}" for i in range(387, 400)]      # B387-B399 = Batch B-24 十三锚（标量衍射族 Fraunhofer/Fresnel Simpson 求积）
                  + [f"B{i}" for i in range(400, 452)])    # B400-B412 = Batch B-25 十三锚（静电/静磁有限源族 库仑/Biot-Savart Simpson 求积） + Batch B-26 十三锚（单界面 Fresnel/Snell 光学族 1D FD Helmholtz） + Batch B-27 十三锚（色散与群速度族 中心差分数值微分） + Batch B-28 十三锚（不完全 Beta 族 复合 Simpson 双重数值积分 / 积分正余弦族 RK4 积分定义 ODE）
    check("题库（B1-B451 含 Batch B-1 五锚 + Batch B-2 十锚 + Batch B-3 十三锚 + Batch B-4 二十二锚 + Batch B-5 十六锚 + Batch B-6 十六锚 + Batch B-7 十六锚 + Batch B-8 十六锚 + Batch B-9 十六锚 + Batch B-10 十六锚 + Batch B-11 十六锚 + Batch B-12 十六锚 + Batch B-13 十六锚 + Batch B-14 十六锚 + Batch B-15 十六锚 + Batch B-16 十六锚 + Batch B-17 十六锚 + Batch B-18 十六锚 + Batch B-19 十六锚 + Batch B-20 十六锚 + Batch B-21 十六锚 + Batch B-22 十三锚 + Batch B-23 十三锚 + Batch B-24 十三锚 + Batch B-25 十三锚 + Batch B-26 十三锚 + Batch B-27 十三锚 + E1-E10 + S1-S13 动态计数）",
          b_ids == expected_b
          and s_ids == [f"S{i}" for i in range(1, 14)]
          and e_ids == [f"E{i}" for i in range(1, len(e_ids) + 1)],
          f"总={len(BENCHMARK_ORDER)} B={len(b_ids)} E={len(e_ids)} S={len(s_ids)}")

    # ⑧ S8 OSNR 统计锚（模板复用验证）
    r8 = osnr_distribution_report()
    check("S8 golden 收敛于解析 46.93（P_sig 线性保持）",
          abs(r8["stats"]["mean"] - r8["analytic_osnr_dB"]) < 0.15,
          f"mean={r8['stats']['mean']} analytic={r8['analytic_osnr_dB']}")
    check("S8 Jensen 方向（NF 非线性：均值≤解析，物理真实）",
          r8["jensen_ok"],
          f"mean={r8['stats']['mean']} ≤ {r8['analytic_osnr_dB']}")
    check("S8 p5 携带最坏情况（Δ>0.5dB）",
          (r8["stats"]["mean"] - r8["stats"]["p5"]) > 0.5,
          f"Δ={r8['stats']['mean'] - r8['stats']['p5']:.3f}")
    g8 = s8_statistical_osnr_anchor()
    check("S8 种子 7 可复现", g8 == s8_statistical_osnr_anchor())

    # ⑨ 蒙特卡洛收敛性（N 扫描收敛带——采样充分性死标量）
    c = convergence_scan()
    check("收敛性 N 扫描（500→4000 收敛带 <0.05）",
          c["converged"], f"spread={c['spread']} means={c['means']}")

    # ⑩ v0.8.42 S12 阵列分布锚（锚+统计混合 · 抓单点锚盲区）
    from lda_harness.array_distribution_anchor import (
        array_insertion_loss_anchor, array_fidelity_anchor,
        array_distribution_verdict,
        s12_array_distribution_report, s12_array_distribution_verdict)
    m_il, vals_il = array_insertion_loss_anchor(8, seed=42)
    r12 = s12_array_distribution_report(kind="insertion_loss", seed=42)
    check("S12 正例：8 通道插损分布 ACCEPT（均值/下界/离群三锚 AND）",
          s12_array_distribution_verdict(kind="insertion_loss", seed=42) == 1.0
          and r12["verdict"] == "ACCEPT",
          f"mean={r12['stats']['mean']} checks={[c['ok'] for c in r12['checks']]}")
    r12b = s12_array_distribution_report(kind="insertion_loss", seed=42)
    # 反例：注入单通道离群（14dB，均值仍≈9——单点锚盲区）
    bad_vals = list(vals_il)
    bad_vals[3] = 14.0
    r12b = array_distribution_verdict(
        bad_vals, golden_mean=9.0, tol_mean=0.3,
        golden_min=6.0, tol_min=0.5, outlier_margin=2.0)
    check("S12 反例：单通道离群 REJECT（单点锚盲区被离群锚抓住）",
          r12b["verdict"] == "REJECT"
          and not [c for c in r12b["checks"] if c["name"] == "离群锚"][0]["ok"],
          f"max={r12b['stats']['max']}")
    m_f, vals_f = array_fidelity_anchor(8, seed=7)
    r12f = s12_array_distribution_report(kind="fidelity", seed=7)
    check("S12 保真度 kind：8 比特读出分布 ACCEPT",
          s12_array_distribution_verdict(kind="fidelity", seed=7) == 1.0,
          f"mean={r12f['stats']['mean']}")

    # ⑪ v0.8.44 B3 相关簇锚（系统级簇漂移——单点锚/离群锚的最后一类盲区）
    from lda_harness.array_distribution_anchor import (
        array_distribution_verdict, cluster_drift)
    # 纯盲区：16 通道，通道 5-7 连续 3 通道 +1.0~1.2dB——均值/下界/离群三锚全过
    vals_c = [9.0] * 16
    for i, off in ((5, 1.0), (6, 1.1), (7, 1.2)):
        vals_c[i] = 9.0 + off
    r_old3 = array_distribution_verdict(
        vals_c, golden_mean=9.0, tol_mean=0.3,
        golden_min=6.0, tol_min=0.5, outlier_margin=2.0)
    r_new4 = array_distribution_verdict(
        vals_c, golden_mean=9.0, tol_mean=0.3,
        golden_min=6.0, tol_min=0.5, outlier_margin=2.0,
        cluster_dev=0.8, min_cluster=3)
    check("B3 盲区确认：旧三锚 ACCEPT（均值/下界/离群全过）",
          r_old3["verdict"] == "ACCEPT", f"{r_old3['verdict']}")
    check("B3 相关簇锚唯一捕获：四锚 REJECT（簇锚 False 其他 True）",
          r_new4["verdict"] == "REJECT"
          and all(c["ok"] for c in r_new4["checks"]
                  if c["name"] != "相关簇锚")
          and not [c for c in r_new4["checks"]
                   if c["name"] == "相关簇锚"][0]["ok"],
          f"checks={[(c['name'], c['ok']) for c in r_new4['checks']]}")
    cd = cluster_drift(vals_c, 0.8, 3)
    check("B3 簇检测原语：3 通道连续同向（均值偏离 1.1）",
          cd["drift"] and cd["max_cluster_len"] == 3,
          f"{cd}")
    # 正例不误伤（既有 S12 配置含簇锚）
    r12_ok = s12_array_distribution_report("insertion_loss", seed=42)
    check("B3 正例不误伤：配置簇锚后插损正例仍 ACCEPT",
          r12_ok["verdict"] == "ACCEPT"
          and [c for c in r12_ok["checks"]
               if c["name"] == "相关簇锚"][0]["ok"],
          f"{r12_ok['verdict']}")

    # ⑫ v0.9.1 S13 设计良率锚（DFY · 解析闭式 ↔ 蒙特卡洛双算法互证）
    from lda_harness.yield_anchor import (
        monte_carlo_yield, nominal_ring_length, s13_design_yield_anchor,
        yield_analytic, yield_report, yield_vs_tolerance_scan)

    rep = yield_report()
    y_an, y_mc = rep["yield_analytic"], rep["yield_monte_carlo"]
    # ① 核心判决：两种独立算法（解析积分 / 数值采样）偏差 ≤ 1 个百分点
    check("S13 解析↔蒙特卡洛互证（|Δ| ≤ 0.01）",
          rep["cross_check_ok"],
          f"解析={y_an} MC={y_mc} Δ={rep['cross_delta']:.6f}")
    # ② 判别力：良率不得恒等于 1（否则锚无分辨率，正态容差下应约 95%）
    check("S13 良率落在有判别力区间（0.8 < Y < 0.999）",
          0.8 < y_an < 0.999, f"Y_analytic={y_an}")
    # ③ DFY 物理正确性：工艺容差放大 → 良率单调下降
    scan = yield_vs_tolerance_scan()
    check("S13 良率随工艺容差单调下降（DFY 判别力）",
          scan["monotone_decreasing"],
          " > ".join(f"{r['sigma_rel']*100:g}%:{r['yield_analytic']:.3f}"
                     for r in scan["rows"]))
    # ④ 逐点互证：扫描的每个 σ 上解析与 MC 都要吻合（不只默认点）
    worst = max(r["cross_delta"] for r in scan["rows"])
    check("S13 全扫描点互证一致（max Δ ≤ 0.01）", worst <= 0.01,
          f"maxΔ={worst:.6f}")
    # ⑤ 规格窗口放宽 → 良率上升（客户可理解的 trade-off 方向）
    y_tight = yield_analytic(delta=0.01)
    y_loose = yield_analytic(delta=0.03)
    check("S13 规格窗口放宽 → 良率上升", y_loose > y_tight,
          f"δ=1%:{y_tight:.4f} < δ=3%:{y_loose:.4f}")
    # ⑥ 种子可复现（统计锚判决前提）
    y1 = s13_design_yield_anchor()
    y2 = s13_design_yield_anchor()
    check("S13 固定种子可复现（两次调用逐位一致）", y1 == y2, f"{y1} == {y2}")
    # ⑦ 物理合理性：环长 µm 量级、样本 FSR 均值逼近名义 17.5nm
    l0 = nominal_ring_length()
    check("S13 物理合理性（L0 为 µm 量级、FSR 样本均值≈17.5nm）",
          1e3 < l0 < 1e6 and abs(rep["diagnostics"]["fsr_mean_nm"] - 17.5) < 0.05,
          f"L0={l0/1e3:.2f}µm FSR_mean={rep['diagnostics']['fsr_mean_nm']}nm")
    # ⑧ 极端容差：收紧到 0.2% → 高良率；放大到 4% → 显著劣化
    y_hi = yield_analytic(sigma_rel=0.002)
    y_lo = yield_analytic(sigma_rel=0.04)
    check("S13 容差收紧/放大两端行为正确", y_hi > 0.999 and y_lo < 0.7,
          f"σ=0.2%:{y_hi:.4f}  σ=4%:{y_lo:.4f}")
    # ⑨ harness S13 reference PASS（golden 自洽，复用 S7 同款构造）
    from lda_harness.harness import ReferenceCandidate
    h13 = VerificationHarness(BENCHMARK_DEFS)
    spec_s13 = [s for s in h13.resolve_specs(None) if s.get("id") == "S13"]
    check("S13 已注册进 harness 题库", len(spec_s13) == 1,
          f"specs={len(spec_s13)}")
    if spec_s13:
        res13 = h13.run(spec_s13, ReferenceCandidate())[0]
        check("S13 harness reference PASS（golden 自洽）",
              res13.passed, f"{res13.candidate} vs {res13.golden}")
    # ⑩ 红线：判决路径零 LLM（用 AST 查真实 import 依赖，不受注释文本干扰——
    #    注：docstring 里出现的"LLM 不进判决路径"是声明而非依赖，文本匹配会误伤）
    import ast
    import inspect
    from lda_harness import yield_anchor as _ya_mod
    _tree = ast.parse(inspect.getsource(_ya_mod))
    _imported: list = []
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.Import):
            _imported += [a.name for a in _n.names]
        elif isinstance(_n, ast.ImportFrom):
            _imported.append(_n.module or "")
    _bad = [m for m in _imported
            if any(k in m.lower() for k in ("llm", "openai", "agent", "torch"))]
    check("S13 红线：yield_anchor 零 LLM/agent 依赖（AST 查 import）",
          not _bad, f"imports={_imported}")

    print(f"\n统计锚 smoke：{_PASS} PASS / {_FAIL} FAIL")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
