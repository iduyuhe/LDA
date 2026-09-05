"""LDA · 四套裁判到统一验证契约的适配器（D-04）。

把项目内四套裁判（harness B1-B11 / waveguide_loop / coupler_loop / solver_writer）
各自的目标描述、ORACLE 接入、容差语义、候选求解器统一到 VerificationSpec，
使全量回归可经统一入口（run_all_specs.py）执行并输出统一报告。

每个 build_*_specs 返回 (specs, cand_map)：
  specs     : List[VerificationSpec]（统一契约，含 oracle_fn/compare_fn/tol/source）
  cand_map  : Dict[spec_id, candidate_fn(spec, oracle_value) -> 候选值]
"""
from __future__ import annotations

import math
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from .verification_spec import (
    VerificationSpec, cmp_abs, cmp_rel, cmp_abs_balance, compare_fn_for,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_SOLVER_DIR = os.path.join(os.path.dirname(_HERE), "lda_solver")
_AGENT_DIR = os.path.join(os.path.dirname(_HERE), "lda_agent")


def _ensure_paths():
    for p in (_SOLVER_DIR, _AGENT_DIR):
        if p not in sys.path:
            sys.path.insert(0, p)


# ---------------------------------------------------------------------------
# 1. harness（B1-B18 物理定律 + E1-E7 实证语料锚 · D-62 双 ground）
# ---------------------------------------------------------------------------
def build_harness_specs(defs: Optional[Dict] = None
                        ) -> Tuple[List[VerificationSpec], Dict[str, Callable]]:
    from .benchmarks import BENCHMARK_DEFS
    from .golden import golden_with_source
    from .empirical_bank import EmpiricalCorpus, EmpiricalAnchor

    defs = defs or BENCHMARK_DEFS
    specs: List[VerificationSpec] = []
    cand_map: Dict[str, Callable] = {}
    # D-62 实证锚：加载实测语料（seed + 社区落库增量），供 E1-E7 实证锚题取 golden
    anchor = None
    for bid in sorted(defs.keys()):
        d = defs[bid]
        params = dict(d["default_params"])

        # D-63 溯源分级：empirical=A 级可公开溯源（计入实证锚）；
        #   empirical_unverified=B 级待溯源（同走死标量判决，但单独标注、不计入可溯源计数）
        if d.get("anchor") in ("empirical", "empirical_unverified"):
            if anchor is None:
                anchor = _load_empirical_anchor()
            eid = d.get("empirical_id")
            unverified = (d.get("anchor") == "empirical_unverified")

            # A 级（empirical）：强制要求可公开溯源，B 级语料一律挡在判决之外；
            # B 级（empirical_unverified）：显式放行取值但标注，且不计入可溯源计数
            _req_trace = (not unverified)

            def _emp_oracle(p, eid=eid, anchor=anchor, _req=_req_trace):
                val, _src, _note = anchor.resolve(eid, require_traceable=_req)
                if val is None:
                    raise ValueError(
                        f"实证语料不可用: {eid} —— {_note}"
                        f"（B 级语料无公开溯源定位符，禁止作 golden；"
                        f"须补 DOI/URL 后升级 A 级）")
                return val

            specs.append(VerificationSpec(
                spec_id=bid,
                metric=d["metric"],
                oracle_kind="empirical_measurement",
                oracle_fn=_emp_oracle,
                compare_fn=cmp_abs,
                tol=d["tol"],
                tol_mode="abs",
                target_desc=d.get("title", ""),
                params=params,
                source=(d.get("oracle", "empirical-measurement")
                        + (" ⚠️B级·待溯源（无 DOI/URL，不计入可溯源实证锚）"
                           if unverified else "")),
                candidate_desc=_emp_candidate_desc(d)))
            # v0.9.23：实证锚的候选分发改为**查登记表**（与 B 类物理定律锚同构）。
            # 此前此处硬编码 `== "fdfd_ng"` ⇒ 每接一种新候选就要改一遍分支，
            # 且「登记表里登记了却没被任何锚引用」这类失配无法被发现。
            cand_map[bid] = (BENCHMARK_CANDIDATES.get(d.get("candidate"))
                             or _harness_reference_candidate)
            continue

        def _oracle(p, bid=bid):
            val, _src, _note = golden_with_source(bid, p)
            return val

        # v0.9.14（P0-1 · 战略审计 R1）：B 类物理定律锚**首次接入独立候选**。
        # 此前 build_harness_specs 对所有非实证锚一律落 _harness_reference_candidate
        # （candidate≡golden，恒 PASS、零验证价值）→ 48 锚中 47 道为自证桩。
        # 现按 benchmarks.py 的 `candidate` 字段查表分发；未登记者仍是自证桩
        # （诚实保留，不假装已独立）。
        cand_key = d.get("candidate")
        cand_fn = BENCHMARK_CANDIDATES.get(cand_key) if cand_key else None
        independent = cand_fn is not None

        specs.append(VerificationSpec(
            spec_id=bid,
            metric=d["metric"],
            oracle_kind="physical_law",
            oracle_fn=_oracle,
            compare_fn=compare_fn_for(d.get("cmp", "abs")),
            tol=d["tol"],
            tol_mode="abs",
            target_desc=d.get("title", ""),
            params=params,
            source=d.get("oracle", "physical_law"),
            candidate_desc=(d.get("candidate_desc")
                            if independent
                            else "harness 参考候选（占位自证："
                                 "candidate≡golden，恒 PASS，无验证价值）"),
        ))
        cand_map[bid] = cand_fn or _harness_reference_candidate
    return specs, cand_map


# ---------------------------------------------------------------------------
# 1b. B 类物理定律锚 · 独立候选登记表（v0.9.14 · P0-1）
# ---------------------------------------------------------------------------
# key   = benchmarks.py 中 BENCHMARK_DEFS[x]["candidate"] 的取值
# value = candidate_fn(spec, oracle_value) -> float
#
# 「独立」的判据：候选必须走与 golden **方法学不同源**的求解路径
#   golden = 解析闭式（Koch 色散近似 / Blais 微扰闭式 / 定义式）
#   cand   = 严格数值（电荷基对角化 / 多能级+Fock 联合对角化）
# 二者物理同源、方法独立 ⇒ |cand−golden| 反映**近似式的固有误差**，
# 这才是真可证伪的验证（自证桩的 |diff|≡0 不携带任何信息）。
BENCHMARK_CANDIDATES: Dict[str, Callable] = {}


def _register_candidate(key: str, desc: str):
    """登记一个 B 类独立候选（装饰器：同时写入 desc 供报告显示）。"""
    def _wrap(fn: Callable) -> Callable:
        fn.candidate_desc = desc
        BENCHMARK_CANDIDATES[key] = fn
        return fn
    return _wrap


@_register_candidate(
    "transmon_exact",
    "电荷基严格对角化 f01（N=20，41 维实对称矩阵 eigh）"
    "—— 与 golden 的 Koch 色散近似方法学独立")
def _transmon_exact_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B9 / B25 独立候选：transmon 哈密顿量电荷基严格对角化求 f01。

    golden = Koch2007 解析色散近似 f01=√(8·E_J·E_C)−E_C（E_J≫E_C 渐近解）
    cand   = H=4E_C(n−n_g)² − (E_J/2)Σ(|n+1><n|+h.c.) 电荷基截断严格对角化

    两条路径**方法学独立**：解析渐近 vs 数值本征值。实测偏差（transmon
    工作区 E_J/E_C≈67）rel≈0.22%（B9 默认参数），即近似式的固有误差。
    纯 numpy（41 维 eigh），零外部依赖、零 GPU，LLM 不进判决路径。
    """
    _ensure_paths()
    from transmon_solver import solve_transmon

    p = spec.params
    if "phi_frac" in p:      # B25：SQUID 磁通调谐，E_J(Φ)=E_JΣ·|cos(πΦ/Φ0)|
        ej = float(p["e_j_sum_ghz"]) * abs(math.cos(math.pi * float(p["phi_frac"])))
        ec = float(p["e_c_ghz"])
    else:                    # B9：固定频率 transmon
        ej, ec = float(p["E_J"]), float(p["E_C"])
    return solve_transmon(ej, ec, N=20)["f01"]


@_register_candidate(
    "chi_exact",
    "L=6 能级 transmon + Fock 谐振器联合严格对角化（162 维 eigh）"
    "—— 与 golden 的 Blais 微扰闭式方法学独立")
def _chi_exact_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B26 独立候选：多能级 + Fock 联合严格对角化提取色散位移 χ。

    golden = Blais 修正微扰闭式 χ = g²α/(Δ(Δ+α))（|Δ|≫g 微扰展开）
    cand   = H = Σ_s E_s|s><s| + f_r·a†a + g·(a†+a)·Σ_s√(s+1)|s+1><s|
             严格对角化后按最近能量匹配提取 χ = ½[(E_e1−E_e0)−(E_g1−E_g0)]

    取 L=6（χ(L) 在 L=5→6 已收敛，变化 <1e-6 相对量），M=25 Fock 截断。
    实测偏差 rel≈1.98% —— 这是**微扰闭式在 g/Δ=0.1 下的固有误差**，
    非数值噪声（L 收敛扫描已证：L=5 与 L=6 差 <1e-8）。
    """
    _ensure_paths()
    from qeda_depth_solver import tls_spectrum_L, _chi_from_spectrum

    p = spec.params
    f_q = float(p["f_q_ghz"])
    alpha = float(p["alpha_ghz"])
    f_r = float(p["f_r_ghz"])
    g = float(p["g_ghz"])
    E = tls_spectrum_L(f_q, alpha, f_r, g, L=6, M=25)
    return _chi_from_spectrum(E, f_q, f_r)


@_register_candidate(
    "cz_exact",
    "t_CZ=π/(2|χ_严格对角化|)，χ 由 L=6 多能级+Fock 联合对角化给出"
    "—— 与 golden 的闭式 χ 方法学独立")
def _cz_exact_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B27 独立候选：CZ 门时间由严格对角化的 χ 反推。

    golden = t_CZ = π/(2|χ_Blais闭式|)
    cand   = t_CZ = π/(2|χ_严格对角化|)（χ 取自 _chi_exact_candidate）

    严格说 B27 与 B26 共用同一数值 χ ⇒ 二者**非完全独立**（一荣俱荣）。
    诚实标注：B27 验证的是「χ→t_CZ 的换算链路」+「χ 数值侧的自洽」，
    其独立性弱于 B26。保留它是因为它能抓住换算错误（如漏掉因子 2）。
    """
    chi = _chi_exact_candidate(spec, oracle_value)
    return math.pi / (2.0 * abs(chi))


@_register_candidate(
    "lindblad_gate_f",
    "Lindblad 主方程 4×4 超算子 RK4 数值积分 → 完整 PTM → 平均门保真度"
    "（不套衰减率闭式、不假设 PTM 对角）—— 与 golden 的解析闭式方法学独立")
def _lindblad_gate_f_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B10 独立候选：数值积分 Lindblad 主方程求平均门保真度。

    golden = 闭式 (3 + 2e^(−t/T2) + e^(−t/T1))/6（golden.py 内 math.exp 实现）
    cand   = 构造 4×4 Liouvillian（γ₁·D[σ₋] + γ_φ·D[σ_z]）→ 对 4 个 Pauli 基
             各 RK4 积分一次 ⇒ 完整 PTM 矩阵 → F_avg = ½ + (Λ_xx+Λ_yy+Λ_zz)/6

    **方法学独立**：候选不套任何衰减率公式、不假设 PTM 对角结构，是从
    超算子积分出来的。PTM 实际**非对角**（振幅阻尼的 Λ_Z,I = −(1−e^(−t/T1))
    ≈ −2.5e-4，布居转移特征），候选会真实遇到这些非对角元。

    🔴 **v0.9.24 诚实边界 —— 生产档位残差落在机器精度**：
    默认参数 t_gate=0.02 µs、T1/T2 ~ 60-80 µs ⇒ 无量纲演化量 |L|·t ≈ 2.5e-4，
    RK4 从 N=5 到 N=400 残差恒为 **1.11e-16**，与步数无关 ⇒ 该残差**不可标定**
    （与自证桩的 |Δ|≡0 在数值上无法区分）。因此「候选真在工作」不是靠生产
    档位的残差证明的，而是靠三条**可标定**的自校锚（见
    `lda_solver/lindblad_gate_fidelity.py`）：
      · PTM 非对角元 Λ_Z,I ≈ −2.5e-4 逐元素比对（不是机器精度）
      · 敏感 regime（t=200 µs，|L|t≈2.5）残差 5.6e-9，N 加倍降 16.3×（O(h⁴)）
      · t→∞ 稳态极限 F → 0.5（完全退相干通道的平均保真度）
    外加 harness 的反向扰动测试（自证桩扰动后 |Δ|≡0 会 FAIL）。

    ⚠️ 已知边界：①T=0 热库（未含 n_th 热激发）②H=0 idle 门口径（未含脉冲
    形状误差/泄漏/串扰）③T2 > 2·T1 属非物理输入，抛 ValueError 而非 clamp。
    """
    try:
        from lda.lda_solver import lindblad_gate_fidelity as lg
    except ImportError:  # 包内相对导入兜底（与 semivec_ng 同构）
        _ensure_paths()
        import lindblad_gate_fidelity as lg

    p = spec.params
    # 🔴 float() 双重包裹（v0.9.24 全量回归实测）：候选若返回 np.float64，
    # 下游 `passed = abs(cand-golden) <= tol` 会变成 np.bool_，进而在
    # report.format_json 抛 TypeError（与 v0.9.17 B24 同类）。模块内部已包
    # 一层，这里再包一层作双保险——**判决链上不许出现 numpy 标量**。
    return float(lg.average_gate_fidelity(float(p["T1"]), float(p["T2"]),
                                          float(p["t_gate"]),
                                          n_steps=lg.N_STEPS))


def _load_empirical_anchor():
    """加载实证语料锚（seed_empirical.json + 社区落库增量 empirical_contributions.json）。

    语料=真实测量事实（文献/PDK 公开量级 + 社区经「具名人工评审→落地」流入），
    构成验证的第二道非 AI ground；LLM 永不进判决路径。
    """
    from .empirical_bank import EmpiricalCorpus, EmpiricalAnchor
    _here = os.path.dirname(os.path.abspath(__file__))
    corpus = EmpiricalCorpus()
    seed = os.path.join(_here, "seed_empirical.json")
    if os.path.exists(seed):
        for m in EmpiricalCorpus.load(seed)._items.values():
            corpus.add(m, contributor="seed", source_file=seed, overwrite=True)
    contrib = os.path.join(os.path.dirname(_here), "lda_pdk", "empirical_contributions.json")
    if os.path.exists(contrib):
        try:
            for m in EmpiricalCorpus.load(contrib)._items.values():
                corpus.add(m, contributor="community", source_file=contrib,
                           overwrite=True)
        except Exception:  # 增量文件损坏时优雅降级（诚实：以 seed 为准）
            pass
    return EmpiricalAnchor(corpus)


def _emp_candidate_desc(d: dict) -> str:
    """实证锚（E 族）的候选描述串（v0.9.23 · 查登记表，不再硬编码 fdfd_ng）。

    🔴 与 B 类锚走**同一张** BENCHMARK_CANDIDATES 登记表：
    此前 E 族分支硬编码 `== "fdfd_ng"`，接新候选要改分支，且「登记了却无人引用」
    的失配不可见。现在两边同构，`run_benchmark_falsifiability_smoke` 的
    「已登记候选类型与实测独立锚一致」护栏即可同时覆盖 E 族。
    """
    fn = BENCHMARK_CANDIDATES.get(d.get("candidate")) if d.get("candidate") else None
    if fn is None:
        return ("harness 参考候选（占位自证：candidate≡golden，"
                "恒 PASS，无验证价值）")
    desc = getattr(fn, "candidate_desc", "独立候选求解器")
    if d.get("candidate_status") == "degraded_ordinal":
        desc += (" ⚠️降级：候选与 golden **几何不同源/精度不足**，"
                 "仅作量级参考，不进死标量判决（诚实边界 C · R16 已证伪）")
    return desc


def _harness_reference_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """参考候选：返回 ORACLE 真值本身（正确求解器语义，同 ReferenceCandidate）。

    ⚠️ 占位语义：|candidate − golden| ≡ 0 ⇒ 恒 PASS，**不产生验证价值**
    （D-64 实测：E1-E7 七道 |diff| 全为 0.0）。任何宣称「锚题 PASS」的结论，
    若走的是本候选，都只能算「自洽」而不能算「验证」。
    需要真验证的锚题须在 benchmarks.py 里显式指定 `candidate` 字段
    （如 semivec_ng / fdfd_ng）。
    """
    return oracle_value


# 🔴 v0.9.23：`fdfd_ng` **取消登记**（不再 @_register_candidate），仅保留函数。
# 原因：E2 改用半矢量候选后，全库再无锚题引用 fdfd_ng；而
# run_benchmark_falsifiability_smoke 护栏②断言
#   set(BENCHMARK_CANDIDATES) ⊆ {BENCHMARK_DEFS[*].candidate}
# （「已登记候选类型与实测独立锚一致（无登记未接线）」）
# ⇒ 继续登记会直接判 FAIL。这是**故意的**：登记了却无人用 = 接口失配，
#   护栏本来就该响。函数本身保留，供 run_empirical_anchor_smoke.py 直接调用
#   复现 D-65（窗口散射 ±0.04~0.08）与 R16 证伪证据。
def _fdfd_ng_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """独立候选：标量亥姆霍兹 FDFD 本征模算 n_eff(λ) → 中心差分得 n_g。

    ⚠️ **已退出判决路径**（v0.9.23）：E2 改用 semivec_ng 后本函数不再被任何
    锚题引用，仅作历史候选保留（D-64/D-65/R16 证据复现）。
    其已知缺陷（**保留在此，不得遗忘**）：
      · 标量近似不辨 TE/TM（实测 TE 1.892 / TM 1.717，标量解偏高）
      · **窗口散射 ±0.04~0.08**（仅改计算窗口 clad=1.5→4.0 µm，n_g 在
        1.878~1.962 间散射）—— 与半矢量的 <1e-5 形成鲜明对比，
        这正是它被换下的**首要原因**（D-65）
      · R16（亚网格 ε 平均 + dl=24→64 细化）实测**无效**（n_g 纹丝不动）

    ⚠️ 网格 dl 必须由**中心波长**固定：若 dl 随扫描波长变化，差分测到的是
    网格伪变化而非物理色散（实测曾致 n_g 乱跳 5.93 / 1.85 / 1.61）。
    """
    _ensure_paths()
    from fdtd3d_waveguide import build_waveguide_field_3d
    from .oracle_mode import fdfd_mode_field   # oracle_mode 在 lda_harness 包内（非 lda_solver）

    p = spec.params
    wl = float(p["wl_um"])
    dl = wl / float(p.get("dl_factor", 24.0))    # 固定网格（关键）
    clad = float(p.get("clad_um", 3.0))
    Lz = float(p.get("Lz_um", 8.0))
    d = float(p.get("d_wl_um", 0.02))            # 差分半步长（默认 ±20nm）

    def _neff(w):
        eps3, meta = build_waveguide_field_3d(
            float(p["w_um"]), float(p["h_um"]),
            float(p["n_core"]), float(p["n_clad"]),
            w, dl=dl, clad_um=clad, Lz_um=Lz)
        return fdfd_mode_field(eps3, meta["dl"], w)[0]

    n1 = _neff(wl - d)
    n2 = _neff(wl + d)
    # n_g = n_eff − λ·dn_eff/dλ（中心差分）
    return (n1 + n2) / 2.0 - wl * (n2 - n1) / (2.0 * d)


@_register_candidate(
    "semivec_ng",
    "2D 半矢量本征模（准 TE，界面调和通量 + Dirichlet ghost-point）"
    "n_eff(λ) → 中心差分 n_g —— 与实测 golden 完全独立，"
    "低对比度段已由 A 级实证对照校准到 1e-4")
def _semivec_ng_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """E2 独立候选：2D 半矢量本征模 n_eff(λ) → 中心差分得 n_g（v0.9.23）。

    ═══ 为什么它能从「降级量级参考」升为「严格独立候选」═══
    被换下的 fdfd_ng 有两条致命缺陷，半矢量逐个解决：

      ① **窗口散射**（D-65，最致命）：FDFD 仅改计算窗口（clad 1.5→4.0 µm）
         n_g 在 1.878~1.962 间散射 **±0.04~0.08**，几乎吃掉 tol=0.10 的全部
         预算 ⇒ 「PASS」可能只是窗口挑得好，判决不可信。
         半矢量实测（E2 几何，h=0.015）L=6.0/7.5/9.0 → 1.957177 / 1.957174 /
         1.957174，**窗口散射 < 1e-5**（比 FDFD 小 4 个数量级）。
      ② **不辨 TE/TM**：标量亥姆霍兹只有一个解，无法对上实测的 TE 1.892。
         半矢量按偏振求解（准 TE / 准 TM 分离），与实测口径对齐。

    ═══ 独立性的凭据（不读任何测量数据）═══
      实测侧：OFDR 环腔群延迟 / MZI 传输谱（实验）
      计算侧：2D 半矢量本征值问题 + Sellmeier 材料色散 + λ 中心差分
      两条路径方法学不同源，|cand−golden| 是真残差。

    ═══ 精度凭据（A 级实证对照，唯一凭据，缺此不可宣称）═══
      semivec_mode_solver 自校锚③：Si₃N₄ 1.2×0.3 纯净对照组（无 SiOC，
      全 silica 包层，R=100 µm 无弯曲，λ²/(FSR·L)=1.9666 自洽），
      实测 n_g=1.9666 vs 计算 1.966684 ⇒ **Δ=+8.4e-5**。
      该对照与本锚同材料体系（Si₃N₄/SiO₂）、同尺寸量级（1.2×0.3 vs 1.0×0.3），
      故它端到端校准了「算子 + 色散 + 数值微分」整条链路。

    ═══ 🔴 已知边界（必须与结论一起读）═══
      · **残差 +0.0652 不等于精度已验证**：残差的主成分是「ring golden vs
        直波导候选」的对象不对齐 + 制造公差（h_um ±10% 就移动 n_g ∓0.046，
        300 nm LPCVD 膜厚公差轻松达 ±5%）。tol=0.10 里**没有多少物理裕度**。
      · **不得用于 SOI 高对比度**：半矢量是约束变分问题 ⇒ β² 系统性偏高，
        SOI（3.478/1.444）实测偏差 +0.0276。E1 仍保持自证桩即因于此。
      · 材料色散：采用 Sellmeier（Si₃N₄ / SiO₂）。若关掉色散 n_g=1.9218
        （Δ=+0.0298，反而更近）——**不据此择优**，色散是物理事实。
    """
    # 双路兜底（项目铁律：包内模块导入不得只依赖单一路径）
    try:  # 优先按包路径（仓库根在 sys.path 时）
        from lda.lda_solver import semivec_mode_solver as sv   # noqa: F401
    except ImportError:  # 回退：把 lda_solver 目录塞进 sys.path 后裸导入
        _ensure_paths()
        import semivec_mode_solver as sv                        # noqa: F401

    p = spec.params
    # 🔴 h_grid / L 取模块生产档位且**不随参数变化**：三个 λ 上网格与窗口必须
    # 完全相同，否则差分测到的是网格伪变化而非物理色散（实测曾致 n_g 乱跳
    # 5.93 / 1.85 / 1.61）。参数扰动只改几何/折射率，不改网格。
    return sv.group_index(
        float(p["w_um"]), float(p["h_um"]), float(p["wl_um"]),
        n_core=float(p["n_core"]), n_clad=float(p["n_clad"]),
        core_material="Si3N4", clad_material="SiO2",
        h_grid=sv.H_GRID, L=sv.L_WIN)


# ---------------------------------------------------------------------------
# 1c. 光子侧 FSR 族：数值响应谱**频域峰周期**拟合（v0.9.16 · P0 续）
# ---------------------------------------------------------------------------
# 方法学 independence 的依据（B3/B4/B20 通用）：
#   谐振/干涉峰满足（光程）= m·λ ⇒ **1/λ_m = m/(光程) 严格等距**；
#   教科书闭式 FSR_λ = λ²/(光程) 只是该频域等距性在 λ0 处的**一阶连续化**。
#   候选全程**不调用**该闭式：数值扫描响应谱 → 定峰 → 对 1/λ 做等距最小二乘
#   → 单位换算。故 |cand−golden| 反映的是「闭式一阶近似 + 数值定峰」的真实
#   残差，可证伪（改错公式/少个 2π/用错折射率，残差立刻爆炸到 tol 外）。
#
# ⚠️ 网格规模是**刻意标定**的（实测扫描，n_grid=50001）：
#   - 太粗 ⇒ 残差超过 tol（B20 的 tol=1e-6 最紧）⇒ 假红
#   - 太精 ⇒ 残差掉到 1e-12 以下，与「自证桩」按值不可区分 ⇒ 护栏会误报假独立
#   实测三道残差 1.7e-8 / 1.9e-8 / 4.7e-10，离 1e-12 判据有 ≥467× 余量。
_FSR_GRID_N = 50001          # 数值谱网格点数（标定值，勿随意改）
_FSR_MIN_PEAKS = 5           # 最少峰数（不足则自适应加倍开窗）
_FSR_HALF_REL = 0.05         # 初始开窗半宽（相对 λ0）


def _peaks_parabolic(lam, T):
    """局部极大 + 三点抛物线亚网格细化，返回按 λ **降序**排列的峰位。

    只做抛物线细化、**不做**牛顿/二分精化：候选值相对 golden 的残差正来自
    这份数值误差。若把候选打磨到机器精度，|diff| 会掉到 1e-12 以下，自动
    护栏将无法把它和「直接 return golden 的自证桩」区分开（宁可粗糙可辨）。
    """
    lam = np.asarray(lam, dtype=float)
    T = np.asarray(T, dtype=float)
    idx = np.flatnonzero((T[1:-1] > T[:-2]) & (T[1:-1] >= T[2:])) + 1
    if idx.size < 3:
        return np.array([])
    y1, y2, y3 = T[idx - 1], T[idx], T[idx + 1]
    den = y1 - 2.0 * y2 + y3
    safe = np.where(np.abs(den) > 0, den, 1.0)
    shift = np.where(np.abs(den) > 0, 0.5 * (y1 - y3) / safe, 0.0)
    h = lam[1] - lam[0]
    pk = lam[idx] + shift * h
    return pk[np.argsort(pk)[::-1]]


def _fit_fsr_peak_periodicity(response_fn, wl0_um, n_grid=_FSR_GRID_N,
                              min_peaks=_FSR_MIN_PEAKS,
                              half_rel=_FSR_HALF_REL) -> float:
    """从数值响应谱 T(λ) 的**频域峰周期**反推波长域 FSR（nm）。

    步骤（全程闭式无关）：
      ① 自适应开窗（初始 ±5%·λ0，峰数不足则加倍，最多 6 次）
      ② 等距网格扫描响应谱、三点抛物线定峰
      ③ 对 u=1/λ 关于级次序号做**最小二乘等距拟合**，slope = Δu
      ④ FSR_λ(λ0) = λ0² · Δu · 1000（频域周期 → 波长域的一阶换算，单位 nm）

    开窗宽度**不依赖**任何闭式 FSR 估计（否则循环论证）—— 只按「峰数够不够」
    自适应加宽，故该候选与 golden 的方法学 independence 成立。
    """
    half = wl0_um * half_rel
    pk = np.array([])
    for _ in range(6):
        lam = np.linspace(wl0_um - half, wl0_um + half, int(n_grid))
        pk = _peaks_parabolic(lam, np.asarray(response_fn(lam), dtype=float))
        if pk.size >= min_peaks:
            break
        half *= 2.0
    if pk.size < min_peaks:
        raise RuntimeError(
            f"数值响应谱峰数不足（{pk.size}<{min_peaks}）：无法独立定 FSR"
            f"（λ0={wl0_um}，开窗已扩至 ±{half:.4g} um）")
    u = 1.0 / pk                       # λ 降序 ⇒ u=1/λ 升序
    slope, _ = np.polyfit(np.arange(u.size, dtype=float), u, 1)
    return float(wl0_um ** 2 * slope * 1000.0)


@_register_candidate(
    "fp_fsr_peakfit",
    "数值 Airy 响应谱峰周期拟合 FSR（自适应开窗 + 抛物线定峰 + 1/λ 等距最小二乘）"
    "—— 与 golden 的 Airy 闭式 FSR=λ²/(2nL) 方法学独立")
def _fp_fsr_peakfit_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B3 独立候选：FP 标准具 FSR（数值峰周期 ↔ 解析闭式 λ²/(2nL)）。

    golden = Airy 解析闭式 FSR = λ²/(2nL)（一阶连续化，误差 O(1/m)）
    cand   = 数值扫 Airy 透射谱 T=1/(1+F·sin²(δ/2))，δ=4πnL/λ，
             定峰后对 1/λ 做等距拟合得 Δu=1/(2nL)，换算 FSR_λ=λ0²·Δu

    反射率 R（⇒ 精细度系数 F=4R/(1−R)²）**只影响峰宽、不影响峰位**
    （Airy 分母在 sin²(δ/2)=0 处恒取极大，与 F 无关），故取 R=0.5
    （F=8，精细度≈4.4，峰可分辨）不影响被测物理量。
    """
    p = spec.params
    wl0 = float(p["wavelength"])
    n = float(p["n"])
    L = float(p["L"])
    R = float(p.get("R_mirror", 0.5))          # 镜面反射率（仅定峰宽）
    coef = 4.0 * R / (1.0 - R) ** 2            # Airy 精细度系数 F

    def _T(lam):
        delta = 4.0 * math.pi * n * L / lam    # 往返相位
        return 1.0 / (1.0 + coef * np.sin(delta / 2.0) ** 2)

    return _fit_fsr_peak_periodicity(_T, wl0)


@_register_candidate(
    "ring_fsr_peakfit",
    "数值 add-drop 环传递函数（drop 口）峰周期拟合 FSR"
    "—— 与 golden 的环形闭式 FSR=λ²/(n_g·2πR) 方法学独立")
def _ring_fsr_peakfit_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B4 独立候选：add-drop 环形谐振器 FSR（数值峰周期 ↔ 解析闭式）。

    golden = 解析传递函数闭式 FSR = λ²/(n_g·2πR)
    cand   = 数值扫 drop 口传递 D ∝ 1/|1 − a·t·e^{−iφ}|²，φ=2π·n_g·L/λ，
             L=2πR；定峰后对 1/λ 等距拟合得 Δu=1/(n_g·L)，换算 FSR_λ=λ0²·Δu

    drop 口极大恒在 φ=2πm（分母 |1−a·t·e^{−iφ}|² = 1+(at)²−2at·cosφ 最小），
    **与耦合系数 κ、往返损耗 a 无关** ⇒ 二者取 κ=0.3 / a=0.99 只影响峰宽，
    不改变被测的峰位周期性。
    """
    p = spec.params
    wl0 = float(p["wavelength"])
    ng = float(p["n_g"])
    L = 2.0 * math.pi * float(p["R"])
    kappa = float(p.get("kappa", 0.3))         # 耦合系数（仅定峰宽）
    a_rt = float(p.get("a_rt", 0.99))          # 往返振幅损耗（仅定峰宽）
    t_rt = math.sqrt(max(0.0, 1.0 - kappa ** 2))

    def _drop(lam):
        phi = 2.0 * math.pi * ng * L / lam
        return (kappa ** 4 * a_rt) / (1.0 + (a_rt * t_rt) ** 2
                                      - 2.0 * a_rt * t_rt * np.cos(phi))

    return _fit_fsr_peak_periodicity(_drop, wl0)


@_register_candidate(
    "mzi_fsr_peakfit",
    "数值 MZI 干涉谱 T=½(1+cos φ) 峰周期拟合 FSR"
    "—— 与 golden 的闭式 FSR=λ²/(n_eff·ΔL) 方法学独立")
def _mzi_fsr_peakfit_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B20 独立候选：MZI 干涉 FSR（数值峰周期 ↔ 解析闭式 λ²/(n_eff·ΔL)）。

    golden = 闭式（干涉解的一阶连续化）FSR = λ²/(n_eff·ΔL)
    cand   = 数值扫 T=½(1+cos(2π·n_eff·ΔL/λ))，定峰后对 1/λ 等距拟合得
             Δu=1/(n_eff·ΔL)，换算 FSR_λ=λ0²·Δu

    本锚**无自由参数**（无需 κ/R/a 之类仅定峰宽的量），是三道里最干净的一道。
    ⚠️ B20 的 tol=1e-6 是「自证桩容差」量级（相对量 5e-8），实测残差 4.7e-10
    （d/tol≈4.7e-4，余量 2000×）—— 正说明真独立候选能满足它，且该容差事实上
    能抓住 5e-8 相对量以上的任何公式错误（三道里最灵敏的一道）。
    """
    p = spec.params
    wl0 = float(p["wl0_um"])
    n_eff = float(p["n_core"])                 # 与 golden 同一物理输入（n_eff≡n_core）
    dL = float(p["deltaL_um"])

    def _T(lam):
        return 0.5 * (1.0 + np.cos(2.0 * math.pi * n_eff * dL / lam))

    return _fit_fsr_peak_periodicity(_T, wl0)


# ---------------------------------------------------------------------------
# 1d. 量子侧严格数值候选（v0.9.17 · P0 续）：B12 / B22 / B23 / B24 / B13
# ---------------------------------------------------------------------------
# 这五道的 note 早就写着「严格侧 = 离散 TL 三对角特征值 / 441 维电荷基对角化 /
# 双基对拍 / 三模 Fock 截断」，但 harness **从未真的接过** —— 一直落
# `_harness_reference_candidate`（|diff|≡0 恒 PASS）。v0.9.17 把宣称接成事实。
#
# 🔴 传输线离散化必须用**二阶 ghost-point 边界**（实测教训）：
#   `lda_solver/resonator_solver._discrete_f0` 在开路端写 `A[N-1,N-1] = -1`，
#   等价于单边一阶差分 ⇒ 整体收敛只有 O(1/N)，N=200 残差 2.7e-2（B12 tol=0.02
#   都过不去，B22 tol=1e-6 更无望）。改用 ghost point：
#       短路端（Dirichlet, V=0）：V_{-1} = −V_0  ⇒ d[0]  = −3
#       开路端（Neumann, V'=0）：V_N    =  V_{N-1} ⇒ d[-1] = −1
#   收敛恢复 O(1/N²)，实测 B12 N=400 残差 6.9e-6、B22 N=4000 残差 5.0e-8。
#
# 🔴 **TL-FDTD 路线不可用**（实测证伪）：`device_library._qres_tlfdtd_core` 的
#   FFT 记录长度 ∝ dt ∝ 1/N，网格细化反而**缩短时窗**、降低频率分辨率 ⇒
#   残差随 N **恶化**（N=200: 8.4e-2 → N=1600: 3.6e-2），全部远超 tol。
#   故 B22 走本征值路线而非时域路线。
_TL_N_B12 = 400        # B12 网格（标定值：残差 6.9e-6，d/tol=3.5e-4，余量 2894×）
_TL_N_B22 = 4000       # B22 网格（标定值：残差 5.0e-8，d/tol=5.0e-2，余量 20×）


def _tl_eigen_f0_2nd(v: float, length: float, n_grid: int) -> float:
    """二阶 ghost-point 边界的离散传输线 λ/4 基模频率（短路端 ↔ 开路端）。

    对无损 TL 波动方程 ∂²V/∂x² = (1/v²)∂²V/∂t² 做等距二阶中心差分，
    得三对角矩阵 A（对角 −2、次对角 +1），两端按 ghost point 修正；
    最低模对应 A 的**最大（最接近 0）本征值** λ_max < 0：
        ω = √(−λ_max)·v/dx,  f0 = ω/(2π)

    ⚠️ 网格是**双向标定**的（与光子侧 `_FSR_GRID_N` 同一纪律）：
      - 太粗 ⇒ 残差超 tol ⇒ 假红
      - 太细 ⇒ ①残差掉到 1e-12 以下、与自证桩按值不可区分（护栏误报假独立）
              ②越过 LAPACK 数值地板后残差**反升**（B22 实测 N=8000 起 2.6e-8、
                N=16000 恶化到 1.0e-7，已非离散误差主导）
    量纲由调用方保证：v/length 同量纲 ⇒ 返回值量纲 = v/length。
    """
    from scipy.linalg import eigh_tridiagonal

    n = int(n_grid)
    dx = float(length) / n
    diag = np.full(n, -2.0)
    diag[0] = -3.0          # Dirichlet ghost（短路端）
    diag[-1] = -1.0         # Neumann ghost（开路端）
    off = np.ones(n - 1)
    lam = eigh_tridiagonal(diag, off, select="i", select_range=(n - 1, n - 1))[0]
    omega = math.sqrt(-float(lam[0])) * float(v) / dx
    return omega / (2.0 * math.pi)


@_register_candidate(
    "tl_eigen_f0",
    "二阶 ghost-point 边界离散传输线三对角本征值 f0（N=400，scipy eigh_tridiagonal）"
    "—— 与 golden 的 λ/4 连续极限闭式方法学独立")
def _tl_eigen_f0_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B12 独立候选：超导谐振器 λ/4 基模 f0（离散 TL 本征 ↔ 连续闭式）。

    golden = f0 = 1/(4l·√(L′C′))（**连续极限**闭式，无离散误差项）
    cand   = 离散化 TL 波动方程的三对角矩阵最低本征模（二阶 ghost 边界）

    参数量纲：Lp [H/m]、Cp [F/m]、l [m] ⇒ v=1/√(LpCp) [m/s]、f [Hz] → /1e9 GHz。
    实测 N=400 残差 6.913e-6 GHz（rel 6.4e-5 = 0.0064%），tol=0.02 **未放宽**
    （d/tol=3.5e-4，余量 2894×）；离 1e-12 自证桩判据有 6.9e6× 余量。
    反向 10% 扰动实测 Lp/Cp/l 三键残差 0.50/0.50/0.98 GHz，全部远超 tol ⇒ 可证伪。
    """
    p = spec.params
    v = 1.0 / math.sqrt(float(p["Lp"]) * float(p["Cp"]))     # m/s
    return _tl_eigen_f0_2nd(v, float(p["l"]), _TL_N_B12) / 1e9


@_register_candidate(
    "tl_eigen_qres",
    "二阶 ghost-point 边界离散传输线三对角本征值 f0（N=4000）"
    "—— 与 golden 的 CPW λ/4 闭式 c0/(4·L·n_eff) 方法学独立")
def _tl_eigen_qres_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B22 独立候选：CPW λ/4 读出谐振器基模（离散 TL 本征 ↔ 连续闭式）。

    golden = f0 = c0/(4·L·n_eff)（连续极限闭式）
    cand   = 同一 TL 波动方程离散本征（相速 v = c0/n_eff，与 golden 同物理输入）

    ⚠️ B22 的 tol=1e-6 是「自证桩容差」量级（相对量 1.3e-7）—— 接线前担心真
    独立候选满足不了。实测 N=4000 残差 4.982e-8（d/tol=4.98e-2，余量 20×）
    ⇒ **tol 未放宽**（放宽 tol 等于取消验证，是 P0 纪律红线）。
    N 不能再加大：N=8000 残差 2.6e-8、N=16000 反升到 1.0e-7（越过数值地板）。
    反向 10% 扰动 L_um/n_eff 残差均 0.68 GHz（是 tol 的 6.8e5 倍）⇒ 可证伪。
    """
    p = spec.params
    c0_um_ghz = 299792.458                                  # c0 = 299792.458 um·GHz
    v = c0_um_ghz / float(p["n_eff"])                       # um·GHz
    return _tl_eigen_f0_2nd(v, float(p["L_um"]), _TL_N_B22)  # 直接得 GHz


@_register_candidate(
    "fluxonium_ho_exact",
    "Fluxonium 谐振子基矩阵严格对角化 f01（ncut=24，cosφ 泰勒矩阵幂级数）"
    "—— 与 golden 的 LC 极限闭式 √(8·Ec·El) 方法学独立")
def _fluxonium_ho_exact_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B23 独立候选：Fluxonium 在 Ej→0 极限的 f01（数值对角化 ↔ LC 闭式）。

    golden = √(8·Ec·El)（H = 4Ec·n² + ½El·φ² 的 LC 谐振子解析解）
    cand   = 同一 H 在**谐振子基**（φ_zpf=(8Ec/El)^¼、n_zpf=½(El/8Ec)^¼）
             展开成 ncut 维矩阵后 numpy eigh 求 E1−E0，取 Ej=0（严格极限）

    ⚠️ ncut 是**双向标定**的：
      ncut=20 ⇒ 4.889e-7（d/tol=0.49，余量不足 2×）
      ncut=24 ⇒ 7.752e-9（d/tol=7.8e-3，余量 129×，离 1e-12 有 7.8e3×）✅ 选定
      ncut=28 ⇒ 1.188e-10 · ncut=32 ⇒ 1.733e-12 —— **已贴到 1e-12 判据**，
      再精就与自证桩按值不可区分，自动护栏会误报「标非自证桩却 |diff|≡0」。
    tol=1e-6 **未放宽**。反向 10% 扰动 ec/el 残差均 0.138 GHz ⇒ 可证伪。
    """
    _ensure_paths()
    # 双路兜底：本模块既可能作顶层包 `lda_harness`（sys.path 含 lda/）导入，
    # 也可能作 `lda.lda_harness`（sys.path 含仓库根）导入 —— 两种都要能拿到求解核。
    try:
        from lda_l2.device_library import _fluxonium_ho_core
    except ImportError:                                  # pragma: no cover
        from lda.lda_l2.device_library import _fluxonium_ho_core

    p = spec.params
    return float(_fluxonium_ho_core(e_j=0.0, e_c=float(p["ec_ghz"]),
                                    e_l=float(p["el_ghz"]), ncut=24))


@_register_candidate(
    "tcoup_fock_exact",
    "三模 Fock 截断严格对角化激发带劈裂/2（ncut=3），符号由本征矢宇称独立判定"
    "—— 与 golden 的二阶微扰/SW 闭式方法学独立")
def _tcoup_fock_exact_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B24 独立候选：可调耦合器二阶有效耦合 g_eff（三模严格对角化 ↔ SW 闭式）。

    golden = g_eff = (g1·g2/2)·(1/Δ1 + 1/Δ2)（二阶微扰 / Schrieffer-Wolff）
    cand   = H = Σ ω_i a_i†a_i + g1(a_q1†a_c+h.c.) + g2(a_q2†a_c+h.c.)
             在 q1⊗q2⊗c 三模 Fock 截断下 eigh，取两个 qubit-like 态的
             劈裂 (E_hi−E_lo)/2，**符号由本征矢宇称独立判定**

    🔴 符号不能取绝对值：golden 在 Δ<0（qubit 低于耦合器）时为**负**
    （默认参数 Δ1=Δ2=−2.5 ⇒ golden=−0.004）。判定规则：两个 qubit-like 态
    ≈(|100⟩±|010⟩)/√2，若较低态的 |100⟩ 与 |010⟩ 振幅**同号**（对称态更低）
    则 g_eff<0。⚠️ 张量序是 q1⊗q2⊗c、q1 为最高位 ⇒ qubit2 激发的索引是
    `i010 = 1*ncut`（**不是** `1`，那是耦合器激发）。首版误用后端索引导致宇称
    判反、候选出正值、残差 7.99e-3（超 tol 7987×）—— 索引与构造序必须一致。

    ⚠️ tol 由 1e-6 **按实测重定为 3e-5**：1e-6 是「自证桩容差」（只容得下
    candidate≡golden），而闭式与严格解的**固有模型差**实测 1.272e-5
    （rel 0.32%，ncut=2/3/4/5 完全一致 ⇒ 已收敛，非截断噪声）。
    定 tol=3e-5 = 实测差 × 2.36 余量；判据窗口 (1.272e-5, 4.045e-4) = 31.8×，
    3e-5 落在窗内 ⇒ 正向 PASS 与「反向 10% 扰动必 FAIL」同时成立
    （实测 g1/g2 4.045e-4 · wc 9.289e-4 · wq 9.752e-4，四键全被抓）。
    """
    p = spec.params
    wq, wc = float(p["wq_ghz"]), float(p["wc_ghz"])
    g1, g2 = float(p["g1_ghz"]), float(p["g2_ghz"])
    ncut = 3
    n = np.arange(ncut, dtype=float)
    a = np.diag(np.sqrt(n[1:]), 1)
    eye = np.eye(ncut)
    h = (np.kron(np.kron(np.diag(wq * n), eye), eye)
         + np.kron(np.kron(eye, np.diag(wq * n)), eye)
         + np.kron(np.kron(eye, eye), np.diag(wc * n)))
    j1 = np.kron(np.kron(a.T, eye), a) + np.kron(np.kron(a, eye), a.T)
    j2 = np.kron(np.kron(eye, a.T), a) + np.kron(np.kron(eye, a), a.T)
    evals, evecs = np.linalg.eigh(h + g1 * j1 + g2 * j2)
    if evals[1] <= evals[2]:
        v_lo, e_lo, e_hi = evecs[:, 1], evals[1], evals[2]
    else:
        v_lo, e_lo, e_hi = evecs[:, 2], evals[2], evals[1]
    i100 = 1 * ncut * ncut          # |1,0,0>：qubit1 激发
    i010 = 1 * ncut                 # |0,1,0>：qubit2 激发（最高位是 q1！）
    mag = 0.5 * (e_hi - e_lo)
    return float(-mag if (v_lo[i100] * v_lo[i010]) > 0 else mag)


@_register_candidate(
    "yield_analytic",
    "S13 设计良率解析闭式（高斯积分 Φ 精确解，保留 1/L 非线性）↔ 蒙特卡洛双算法互证，"
    "与 golden 的 MC 仿真方法学独立（同一物理定律两种算法 = 非 AI ground）")
def _s13_yield_analytic_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """S13 独立候选：环形 FSR 命中规格窗口的设计良率（解析高斯积分）。

    golden = 蒙特卡洛仿真良率（固定种子 1313，采样 20000 点）
    cand   = 解析闭式 Y = Φ((L_hi−L0)/σ_L) − Φ((L_lo−L0)/σ_L)
             （FSR=c/L 单调 ⇒ 规格窗口逆变换为 L 区间 ⇒ 误差函数精确积分，
              非 δ/σ 一阶线性化，1/L 非线性完整保留）

    ⚠️ 实测（v0.9.18）：golden=0.954750、candidate=0.954413、baseline|diff|=3.37e-4
    （rel 0.035%，tol=0.01 余量 29.7×）。反向扰动信号谱：
    delta×1.1 → |cand−golden0|=1.73e-2（51×）✅ · sigma_rel×1.1 → 2.39e-2（71×）✅
    · fsr_nom×1.1 → 3.37e-4（=baseline，漏抓：yield 对 fsr_nom 免疫，因 σ 按比例缩放）
    ⇒ 盲区 fsr_nom_nm 已诚实披露，PERTURB 固定扰 delta（最强键）。
    """
    try:
        from lda_harness.yield_anchor import yield_analytic
    except ImportError:
        from lda.lda_harness.yield_anchor import yield_analytic
    p = spec.params
    return float(yield_analytic(
        fsr_nom_nm=float(p["fsr_nom_nm"]),
        delta=float(p["delta"]),
        sigma_rel=float(p["sigma_rel"]),
    ))


@_register_candidate(
    "bragg_bloch_exact",
    "反周期 Bloch 广义本征值问题 A ψ=β²B ψ（N=240，scipy eigvalsh）—— "
    "与 golden 的一阶相位匹配闭式方法学独立")
def _b15_bragg_bloch_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B15 独立候选：Bragg 光栅中心波长（Bloch 本征 ↔ 相位匹配闭式）。

    golden = 一阶 Bragg 条件 λ_B = 2·n_eff·Λ（运动学：k 演化只计基波）
    cand   = E(z)=n_eff²(1+m·cos(2πz/Λ)) 的广义本征值问题
             A ψ = β² B ψ（反周期边界 ψ(z+Λ)=−ψ(z) 锁定 k=±π/Λ，
             谱最低简并对即第一带隙边沿，中心 → λ_B=2π/β_c）
             —— 动力学全波本征谱，调制深度 m 进入算子。

    ⚠️ v0.9.18 曾判 B15「不可接」：当时唯一在库求解器 tmm.py 是垂直入射
    多层膜堆（折射率沿 z 分层、平面波正入射透射谱），与波导光栅（折射率
    沿传播方向周期调制、Bragg 反射带隙）物理对象不同 ⇒ 接它必成伪独立。
    v0.9.19 新写 bragg_solver.py（正确的物理对象 + 正确的本征值方法）。

    实测标定（n_eff=2.4 / Λ=0.323 / m=0.004 / N=240）：
    baseline |diff| = 8.356e-6（rel 5.4e-6，tol=0.01 未动，余量 1196×）。
    反向扰动信号谱：n_eff×1.1 → 1.55e-1（15.5×）✅ · period×1.1 → 1.55e-1
    （与 n_eff 一阶等价，λ_B∝n_eff·Λ）⇒ PERTURB 固定扰 n_eff（最强键）。
    网格双向标定：N=480 diff=5.4e-8 为偶然抵消点、N=960 起越过 LAPACK
    地板反升（2.0e-6）⇒ 取 N=240 收敛段稳定点（详 bragg_solver.py docstring）。
    """
    _ensure_paths()
    from bragg_solver import lambda_B_bloch

    p = spec.params
    return float(lambda_B_bloch(
        n_eff=float(p["n_eff"]),
        period=float(p["period"]),
        mod_depth=float(p.get("mod_depth", 0.004)),
        N=int(p.get("bloch_N", 240)),
    ))


@_register_candidate(
    "dc_cmt_fft",
    "数值传播 + FFT 拍频谱峰提取 L_3dB（增量 2×2 复传播矩阵 + Hann 窗 rFFT"
    " + 三点抛物线细化）—— 与 golden 的耦合模解析闭式反解方法学独立")
def _b14_dc_cmt_fft_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B14 独立候选：定向耦合器 3dB 耦合长度（FFT 拍频 ↔ 解析闭式）。

    golden = 耦合模解析闭式 L_3dB = λ/(4|Δn|)（由 P2=sin²(κz) 反解 P2=0.5）
    cand   = 数值传播 [A1,A2] 序列 → P2(z) 的 FFT 拍频谱峰 → L_P=1/f_peak
             → L_3dB = L_P/4（B3/B4/B20 同款「数值序列提取频域周期」方法学）

    ⚠️ v0.9.20 语义修正（D-66「怀疑 golden 本身」第 4 例）：golden 原式
    λ/(2|Δn|) 是**完全转移长度**（P2=sin²(π/2)=1.0，RK4 实证），被错标
    为 3dB 点；真 3dB 点 = λ/(4|Δn|)（P2=sin²(π/4)=0.5）。修正后
    tol 从 0.5（旧值 3.2%）按同比重定 0.25（3.2%，余量不变）。

    实测标定（n_e=2.45/n_o=2.40/λ=1.55，golden=7.75）：
    baseline |diff| = 1.56e-4（rel 2.0e-5，tol=0.25 余量 1560×；
    残差由谱分辨率+抛物线近似控制，远离 1e-12 自证桩判据）。
    反向扰动信号谱：n_e×1.1 → 6.44（25.8×）✅ · n_o×1.1 → 5.71（22.9×）✅
    · wl×1.1 → 0.775（3.1×）✅ ⇒ PERTURB 固定扰 n_e（最强键）。
    """
    _ensure_paths()
    from dc_cmt_solver import dc_3dB_fft

    p = spec.params
    return float(dc_3dB_fft(
        n_e=float(p["n_e"]),
        n_o=float(p["n_o"]),
        wl=float(p["wl"]),
        dz=float(p.get("fft_dz", 0.01)),
        n_periods=int(p.get("fft_n_periods", 8)),
    ))


@_register_candidate(
    "mie_exact",
    "完整 Mie 级数 Q_scat（B&H 4.53 维度形式，Wiscombe 截断 nmax=x+4x^⅓+2，"
    "纯 numpy 递推）—— 与 golden 的 Rayleigh 一阶极限方法学独立")
def _b1_mie_exact_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B1 独立候选：米氏散射效率（完整级数 ↔ Rayleigh 一阶极限）。

    golden = Rayleigh（偶极子）极限 Q=(8/3)·x⁴·r²（x≪1 只保留 a₁ 首项）
    cand   = 完整 Mie 级数（所有多极子 a_n/b_n 求和到 nmax）

    二者物理同源（麦克斯韦方程）、方法独立（一阶展开 vs 全阶求和）⇒
    |cand−golden| = Rayleigh 固有截断误差（x⁶ 首项），随 x 单调增长
    （-0.001%@x=0.01 → 1.388%@x=0.4）——「x≪1 精确一致」的定量边界。

    ⚠️ 环境确定性：golden 的 b1_mie_qscat(use_miepython=True) 在装有
    miepython 的环境会切换到完整 Mie（ORACLE）⇒ golden 环境相关。
    接线后 default_params 钉死 use_miepython=False（golden 固定走
    Rayleigh，任何环境一致），Mie ORACLE 路径保留给显式外部验货。

    实测标定（m=1.33/x=0.4，golden=2.8413e-3）：
    baseline |diff| = 3.945e-5（rel 1.388%，tol=2e-4 未动，余量 5.1×）。
    反向扰动信号谱：m×1.1 → 2.357e-3（11.9×）✅ · x×1.1 → 1.246e-3
    （6.2×）✅ ⇒ PERTURB 固定扰 m（最强键）。
    递推已用 scipy.special.spherical_jn/yn 交叉验证（max|Δ|≤3e-8）。
    """
    _ensure_paths()
    from mie_solver import mie_q_scat

    p = spec.params
    return float(mie_q_scat(m=float(p["m"]), x=float(p["x"])))


@_register_candidate(
    "coupler_charge_exact",
    "双 transmon 441 维电荷基严格对角化 J（Nq=10，一般失谐提取 √((Δ/2)²−(δ/2)²)）"
    "—— 与 golden 的电荷矩阵元渐近闭式方法学独立")
def _coupler_charge_exact_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B13 独立候选：双 transmon 电容耦合 J（电荷基严格对角化 ↔ 渐近闭式）。

    golden = J = Jc·⟨0|n̂|1⟩₁·⟨0|n̂|1⟩₂，其中 n01≈(E_J/2E_C)^{1/4}/2（渐近式）
    cand   = 双比特电荷基（每比特 2Nq+1=21 维，联合 441 维）严格对角化，
             由单激发双重态劈裂按一般失谐提取 J=√((Δ/2)²−(δ/2)²)

    ⚠️ tol 由 0.10 **收紧 50× 到 2.0e-3**（是加严不是放宽）：0.10 相当于
    golden 的 316%，等于什么都抓不住。实测基线残差 1.3131e-3（rel 4.15%，
    与本锚 note 原就写着的「rel~4%」一致，Nq=8 起已收敛、Nq 增大不变）
    ⇒ 该 4.15% 是**渐近闭式的固有截断误差**，非数值噪声。

    🔴 **诚实披露：本锚的判据窗口很窄，有已知反向盲区。**
    10% 扰动逐键实测残差（golden 固定）：
        C1/C2   4.0686e-3（3.10× 基线）✅ 被抓
        E_C1/E_C2 2.0599e-3（1.57×）   ✅ 被抓
        Cc      1.7179e-3（1.31×）     ❌ 漏抓（< tol）
        E_J1/E_J2 5.5027e-4（0.42×）   ❌ 漏抓（**比基线还小**）
    E_J 扰动使严格解**朝渐近值靠近**（扰动与近似误差偶然抵消，同 B26 现象）
    ⇒ 任何 tol > 基线的取值都不可能抓住 E_J 键。取 tol=2.0e-3（基线 ×1.52）
    是「正向 PASS」与「尽量多抓反向键」的最优折中：4/7 键可抓。
    反向测试固定扰 C1（信号最强）。**盲区不掩盖，写进 note 与本 docstring。**
    """
    _ensure_paths()
    from coupler_solver import solve_coupler

    p = spec.params
    return float(solve_coupler(
        E_J1=float(p["E_J1"]), E_C1=float(p["E_C1"]),
        E_J2=float(p["E_J2"]), E_C2=float(p["E_C2"]),
        Cc=float(p["Cc"]), C1=float(p["C1"]), C2=float(p["C2"]),
        Nq=10)["J_num"])


# ---------------------------------------------------------------------------
# B19 链路无源上界候选的网格常数（🔴 **单一定义处**，v0.9.25）
#   窗口 = [min(λ)−100nm, max(λ)+100nm]，步长 0.01 nm。
#   步长由实测标定（收敛自校锚见下方 step 扫描数值）：
#     step 0.6 / 0.3 / 0.15 / 0.075 / 0.0375 / **0.02 / 0.01 / 0.005** / 0.0025
#     → 0.9998905 / 0.9997835 / 0.9995947 / 0.9998871 / 0.9998970 /
#       **0.9998962 / 0.9998962 / 0.9998962** / 0.9998978
#   ⚠️ **非单调**：max|T| 是「采样是否命中窄共振峰尖」的问题，不是光滑收敛。
#      step ≤ 0.01 后稳定到 1e-12（N≈26001，实测 0.034s）⇒ 取 0.01。
#   不要为省时间调粗 —— 粗网格会**低估** max|T|（0.99959 vs 0.99990），
#   让本锚的判据余量看起来比实际大 3 倍。
_LINK_PASSIVITY_WL_MARGIN_NM = 100.0
_LINK_PASSIVITY_WL_STEP_NM = 0.01


@_register_candidate(
    "link_passivity",
    "lda_chain 链路引擎端到端级联（构建→布局→自动布线→带布线损耗→传递谱）"
    "在**全部传递路径 × 全部采样波长**上的 max|T| —— 与 golden 无源上界 1.0 "
    "死标量比对（cmp='le'）")
def _link_passivity_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B19 独立候选：无源链路无增益上界（max|T| ≤ 1）。

    golden = 常量 **1.0**（无源线性网络无外部泵浦 ⇒ 所有传递增益 |T(λ)| ≤ 1；
             能量守恒是其无损特例）。cmp='le'。
    cand   = `lda_chain` 引擎真跑一遍完整链路：
             `build_wdm_link` 建 N 环 WDM 级联 → `route_and_simulate` 布局 +
             自动布线（产出逐 net 的 `net_loss_db`）→ `engine.simulate` 级联
             → 取所有路径 × 所有波长上的 max|T|。

    **方法学独立性（最强一档）**：golden 是一个**不依赖任何模型的物理硬约束**
    （无源性/能量守恒），候选是一整套工程师序（耦合模谱 × 布线损耗 × 级联）。
    候选不可能"复述" golden —— 它甚至不知道 golden 是多少。

    🔴 **v0.9.25 诚实边界（三条，均已实测）：**
    1. **判据余量仅 ~1.04e-4**。max|T| 的真值 ≈ 0.9998962，缺口几乎全部来自
       环的弯曲损耗。若某天把损耗模型关掉，max|T| → 1.0，本锚会**顶到边界**
       （cmp='le' 下 1.0 恰好 PASS，但任何数值噪声都可能顶穿）。
    2. **网格非单调 + 覆盖盲区**。max|T| 随网格密度**非单调**（采样是否命中窄
       共振峰尖），粗网格会**低估** max ⇒ 步长固定 0.01 nm（已标定稳定）。
       即便如此，若存在 >1 的尖峰恰好落在采样点之间，仍会漏检 —— **加细网格
       只能缓解，不能根除**。这是本锚的结构性盲区，不掩盖。
    3. **`alpha_cm` 对本锚的指标无影响**。它确实被消费（bus0/1/2 的
       `net_loss_db` 随 alpha 增长，实测 alpha=2.5/25/250 时 ring3.out 的
       max|T| 0.9801→0.9594→0.7752），但**全局 max 落在 `ring0.in->ring0.drop`
       这条不经过任何 bus 的路径上**（三档 alpha 下恒为 0.9995947013）。
       ⇒ 候选对 alpha_cm 零响应；判据靠 gap_um / n_g 两键成立（Δ ~1e-4）。
    4. **只判合法性，不判精度**。本锚只回答"链路有没有产生增益"，不回答
       "级联算得准不准"。后者由 `link_harness.link_cascade_check` 负责，但
       它用**引擎同源**模型重建期望 ⇒ **不是独立验证，不得当独立凭据**。

    ⚠️ 布线被阻塞（`blocked_nets` 非空）时**抛异常上浮**，绝不静默回退 ——
    否则又变成自证桩（IndependentCandidateRouter 的既定设计原则）。
    """
    try:
        from lda_chain import build_wdm_link
        from lda_chain import route_sim
        from lda_chain.link_harness import max_transfer_of
    except ImportError:
        # 🔴 `lda_chain` 内部用**绝对**导入（`from lda_ir import ObjectiveSpec`），
        #    所以 `from lda.lda_chain import ...` 必然 ModuleNotFoundError；
        #    必须把 lda/ 根目录放进 sys.path，再按顶层包名导入。
        _root = os.path.dirname(_HERE)
        if _root not in sys.path:
            sys.path.insert(0, _root)
        from lda_chain import build_wdm_link
        from lda_chain import route_sim
        from lda_chain.link_harness import max_transfer_of

    p = spec.params
    if str(p.get("type", "wdm")) != "wdm":
        raise ValueError(f"B19 候选仅支持 type='wdm'，收到 {p.get('type')!r}")
    channels_nm = [float(c) for c in p["channels_nm"]]
    Rs_um = [float(r) for r in p["Rs_um"]]
    if not channels_nm or len(channels_nm) != len(Rs_um):
        raise ValueError(
            f"B19 候选 channels_nm({len(channels_nm)}) 与 "
            f"Rs_um({len(Rs_um)}) 必须非空且等长")

    lo = min(channels_nm) - _LINK_PASSIVITY_WL_MARGIN_NM
    hi = max(channels_nm) + _LINK_PASSIVITY_WL_MARGIN_NM
    n = int(round((hi - lo) / _LINK_PASSIVITY_WL_STEP_NM)) + 1
    wls = [(lo + (hi - lo) * i / (n - 1)) / 1000.0 for i in range(n)]

    link = build_wdm_link(channels_nm, Rs_um,
                          gap=float(p["gap_um"]), n_g=float(p["n_g"]))
    res = route_sim.route_and_simulate(
        link, wls, straight_loss_db_cm=float(p["alpha_cm"]))
    blocked = res.get("blocked_nets") or []
    if blocked:
        raise RuntimeError(f"B19 链路布线不完整 blocked_nets={blocked}"
                           f" —— 级联结果不可信，拒绝出数")
    # 🔴 float() 包裹：判决链上不许出现 numpy 标量（v0.9.24 B10 同类坑）
    return float(max_transfer_of(res["sim"]))


@_register_candidate(
    "taper_eme",
    "本征模展开（EME）逐切片解完整 Helmholtz + 模式重叠矩阵级联 —— 每片解的是"
    "**无旁轴假设的精确横向本征问题**，与 golden 的「绝热极限 T→1」死标量比对")
def _taper_eme_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B8 独立候选：绝热锥度传输效率 T（EME 本征模展开）。

    golden = 常量 **1.0**（绝热极限：锥度足够缓变时局部基模绝热跟随 ⇒ T→1，
             这是**能量守恒给出的物理上界**，不是任何引擎的输出）。
    cand   = `lda_solver.eme_taper` 真解一遍：把锥度切成 N 片，每片解
             一维横向 Helmholtz 本征问题（scipy `eigh_tridiagonal`），片内
             精确模态传播 exp(−iβ·dz)，片间用模式重叠矩阵投影级联，
             T = |c_out,0|²（末片基模功率占比）。

    **方法学独立性**：候选全程不知道 golden 是多少，也不调用任何闭式传输公式；
    它只解亥姆霍兹方程。golden 的「1.0」是上界，候选的 0.999953 是从
    Maxwell 方程算出来的**实测缺口**。

    🔴 **v0.9.26 四条诚实边界（均已实测）：**
    1. **判据余量只有 4.65e-5（占 tol 1e-2 的 0.47%）**。深度绝热区 T 离 1
       极近，本锚实际只回答「是否进入绝热极限」，**不回答精度**。
       ⚠️ 这与 B19（余量 1.04e-4）同型：两个"上界型"锚的余量都极小。
    2. **0.2→0.5 µm 这个几何的损耗上限仅 ~1.5%**（突变结模式重叠 0.9853）。
       ⇒ **单独扰动 L 无法击穿 tol**：L 缩到 0.2 µm 也只到 0.993。反向测试
       必须改成 w2=3.0/L=1.0 µm（T≈0.435）。这是几何本身的性质，非缺陷。
    3. **短锥度区（L≲2 µm）未收敛**：箱模谱在 Δβ·L≪1 时欠采样，窗口 8/16/32
       的 T 相差达 4e-3，且 EME 给出的 T（0.993）**高于**突变结重叠下界
       （0.9853）。已收敛区（L≥5 µm）窗口 16→32 只差 1.4e-5。
       单调性自校锚因此**只取 L≥5**。
    4. **EIM 降维 + 单向近似**：垂向压成常数 n_eff ⇒ 不含垂向辐射与极化耦合；
       只算前向模式不算背向反射。反射只会**降低** T ⇒ 对上界 golden 不会虚高。

    ⚠️ 失败即抛异常上浮，绝不静默回退（IndependentCandidateRouter 既定原则）。
    """
    try:
        from lda.lda_solver import eme_taper
    except ImportError:
        _ensure_paths()
        import eme_taper

    p = spec.params
    # 🔴 float() 包裹：判决链上不许出现 numpy 标量（v0.9.24 B10 同类坑）
    return float(eme_taper.taper_transmission(
        w1=float(p["w1"]), w2=float(p["w2"]), L=float(p["L"]),
        wl=float(p["wl"]), n_eff=float(p["n_eff"]),
        n_clad=float(p["n_clad"]),
        # 🔴 数值档位取**求解器生产档位常量**，不随 spec 参数变化：
        #    参数扰动只改几何/波长，不改网格（同 semivec 的网格纪律）。
        dz=eme_taper.DEFAULT_DZ, m_modes=eme_taper.DEFAULT_MMODES,
        dx=eme_taper.DEFAULT_DX, window=eme_taper.DEFAULT_WINDOW_UM))


def harness_perturbed_candidate(rel_err: float):
    """扰动候选：golden·(1+rel_err)——用于演示 fail 检测（同 PerturbedCandidate）。"""
    def _cand(spec: VerificationSpec, oracle_value: Any) -> float:
        return oracle_value * (1.0 + rel_err)
    return _cand


# ---------------------------------------------------------------------------
# 2. waveguide_loop（真 2D 波导 neff · FDFD 本征 ORACLE）
# ---------------------------------------------------------------------------
def build_waveguide_specs(cases: Optional[List] = None,
                          backend: str = "numpy"
                          ) -> Tuple[List[VerificationSpec], Dict[str, Callable]]:
    """WG neff 契约构造。

    backend（v0.9.38 T-8）：
      "numpy" —— 原生产 numpy 实现（默认，**行为与新增前完全一致**）；
      "numba" —— 强制 numba-CPU 后端（缺 numba 直接抛错，不静默降级）；
      "auto"  —— numba 可用则用 numba，否则回退 numpy（DeviceLibrary live 用）。
    三种后端**同一物理、同一默认测量窗**（M=80 周期 / transient≥3000），
    差异只在计算内核，见 fdtd3d_waveguide_numba.py 的交叉验证判据。
    """
    _ensure_paths()
    from waveguide_loop import WaveguideTarget, _default_cases
    from fdtd3d_waveguide import build_waveguide_field_3d, solve_waveguide_neff_3d
    from oracle_mode import fdfd_mode_field

    if backend not in ("numpy", "numba", "auto"):
        raise ValueError(f"backend 必须是 numpy/numba/auto，收到 {backend!r}")

    _backend_used = {"name": "numpy"}
    if backend in ("numba", "auto"):
        try:
            from fdtd3d_waveguide_numba import (solve_waveguide_neff_3d_numba,
                                                backend_info)
            if backend_info()["have_numba"]:
                _backend_used["name"] = "numba"
            elif backend == "numba":
                raise RuntimeError("backend='numba' 但 numba 不可用："
                                   + backend_info()["import_error"])
        except ImportError:
            if backend == "numba":
                raise

    cases = cases if cases is not None else _default_cases()
    specs: List[VerificationSpec] = []
    cand_map: Dict[str, Callable] = {}
    for i, t in enumerate(cases):
        sid = f"WG-{t.label[:14]}"
        params = {
            "w_um": t.w_um, "h_um": t.h_um, "n_core": t.n_core,
            "n_clad": t.n_clad, "wl_um": t.wl_um,
            "dl": t.wl_um / t.dl_factor, "clad_um": t.clad_um,
            "Lz_um": t.Lz_um, "label": t.label, "tol": t.tolerance_abs,
        }

        def _oracle(p):
            eps3, meta = build_waveguide_field_3d(
                p["w_um"], p["h_um"], p["n_core"], p["n_clad"], p["wl_um"],
                dl=p["dl"], clad_um=p["clad_um"], Lz_um=p["Lz_um"])
            ne, _mode = fdfd_mode_field(eps3, meta["dl"], p["wl_um"])
            return ne

        def _cand(spec, oracle_value):
            p = spec.params
            eps3, meta = build_waveguide_field_3d(
                p["w_um"], p["h_um"], p["n_core"], p["n_clad"], p["wl_um"],
                dl=p["dl"], clad_um=p["clad_um"], Lz_um=p["Lz_um"])
            ne_oracle, mode2d = fdfd_mode_field(eps3, meta["dl"], p["wl_um"])
            solver = (solve_waveguide_neff_3d_numba
                      if _backend_used["name"] == "numba"
                      else solve_waveguide_neff_3d)
            return solver(
                eps3, meta["dl"], p["wl_um"], n_clad=p["n_clad"],
                n_core=p["n_core"], mode_source=mode2d)

        # 诚实披露：候选实际走哪个后端（供 DeviceLibrary / CI 报告）
        _cand.backend_used = lambda: _backend_used["name"]  # type: ignore[attr-defined]
        specs.append(VerificationSpec(
            spec_id=sid, metric="neff", oracle_kind="fdfd_eigen",
            oracle_fn=_oracle, compare_fn=cmp_abs,
            tol=params["tol"], tol_mode="abs",
            target_desc=t.label, params=params,
            source="fdfd 标量亥姆霍兹本征值（独立频域）",
            candidate_desc="标量 3D FDTD（独立时域）"))
        cand_map[sid] = _cand
    return specs, cand_map


# ---------------------------------------------------------------------------
# 3. coupler_loop（方向耦合器 κ / 对称分束器平衡度）
# ---------------------------------------------------------------------------
def build_coupler_specs(cases: Optional[List] = None
                        ) -> Tuple[List[VerificationSpec], Dict[str, Callable]]:
    _ensure_paths()
    from coupler_loop import CouplerTarget, _default_cases
    from fdtd3d_coupler import (
        build_coupler_field_3d, build_ybranch_field_3d,
        solve_supermode_projection_3d_torch, solve_port_powers_3d_torch,
    )
    from oracle_coupler import fdfd_coupler_supermodes, ybranch_oracle
    from oracle_mode import fdfd_mode_field

    cases = cases if cases is not None else _default_cases()
    specs: List[VerificationSpec] = []
    cand_map: Dict[str, Callable] = {}

    for i, t in enumerate(cases):
        dl = t.wl_um / t.dl_factor
        if t.kind == "dc":
            sid = f"DC-gap{t.gap_um}"
            params = {
                "kind": "dc", "w_um": t.w_um, "h_um": t.h_um,
                "gap_um": t.gap_um, "n_core": t.n_core, "n_clad": t.n_clad,
                "wl_um": t.wl_um, "dl": dl, "clad_um": t.clad_um,
                "Lz_um": t.dc_Lz_um, "label": t.label,
            }

            def _oracle(p):
                eps3, meta = build_coupler_field_3d(
                    p["w_um"], p["h_um"], p["gap_um"], p["n_core"], p["n_clad"],
                    p["wl_um"], dl=p["dl"], clad_um=p["clad_um"], Lz_um=p["Lz_um"])
                o = fdfd_coupler_supermodes(eps3[:, :, 0], meta["dl"], p["wl_um"],
                                            mask_a=meta["mask_a"], mask_b=meta["mask_b"])
                return o["kappa"]

            def _cand(spec, oracle_value):
                p = spec.params
                from coupler_loop import _beta_from_recurrence
                eps3, meta = build_coupler_field_3d(
                    p["w_um"], p["h_um"], p["gap_um"], p["n_core"], p["n_clad"],
                    p["wl_um"], dl=p["dl"], clad_um=p["clad_um"], Lz_um=p["Lz_um"])
                o = fdfd_coupler_supermodes(eps3[:, :, 0], meta["dl"], p["wl_um"],
                                            mask_a=meta["mask_a"], mask_b=meta["mask_b"])
                # 波导 A 单波导基模作源
                Nx, Ny = meta["Nx"], meta["Ny"]
                xs = (np.arange(Nx) - Nx / 2.0) * meta["dl"]
                ys = (np.arange(Ny) - Ny / 2.0) * meta["dl"]
                X, Y = np.meshgrid(xs, ys, indexing="ij")
                core_a = (np.abs(X - meta["xa_um"]) <= p["w_um"] / 2.0) & \
                         (np.abs(Y) <= p["h_um"] / 2.0)
                eps2_a = np.full((Nx, Ny), p["n_clad"] ** 2)
                eps2_a[core_a] = p["n_core"] ** 2
                _, src = fdfd_mode_field(eps2_a, meta["dl"], p["wl_um"])
                # 瞬态测量窗（与 coupler_loop 相同参数）
                sponge_z = max(8, min(60, meta["Nz"] // 4))
                src_um = meta["dl"] * (sponge_z + max(8, int(0.12 * (meta["Nz"] - 2 * sponge_z))))
                z_samp = src_um + 2.0 + 0.25 * np.arange(12)
                k0 = 2.0 * math.pi / p["wl_um"]
                dt_f = meta["dl"] * 0.95 / math.sqrt(3.0)
                period = int(round(2.0 * math.pi / (o["neff_s"] * k0 * dt_f)))
                prop = int(round((z_samp[0] - src_um) * o["neff_s"] / dt_f))
                transient = 400 + prop + 5 * period
                Os, Oa, zu = solve_supermode_projection_3d_torch(
                    eps3, meta["dl"], p["wl_um"], p["n_clad"], p["n_core"], src,
                    o["mode_s"], o["mode_a"], src_um=src_um, z_sample_um=z_samp,
                    M_cycles=20, transient=transient)
                bs = _beta_from_recurrence(Os, zu)
                ba = _beta_from_recurrence(Oa, zu)
                if bs is None or ba is None:
                    return float("nan")
                return (bs - ba) / 2.0

            specs.append(VerificationSpec(
                spec_id=sid, metric="kappa", oracle_kind="fdfd_supermode",
                oracle_fn=_oracle, compare_fn=cmp_rel,
                tol=t.tol_kappa, tol_mode="rel",
                target_desc=t.label, params=params,
                source="FDFD 超模法（对称/反对称超模 → κ）",
                candidate_desc="标量 3D FDTD 超模投影递推（独立时域）"))
            cand_map[sid] = _cand
        else:  # ybranch
            sid = "YB-1x2"
            params = {
                "kind": "ybranch", "w_um": t.w_um, "h_um": t.h_um,
                "n_core": t.n_core, "n_clad": t.n_clad, "wl_um": t.wl_um,
                "dl": dl, "clad_um": t.clad_um, "sep_um": t.sep_um,
                "l_in_um": t.l_in_um, "l_trans_um": t.l_trans_um,
                "l_out_um": t.l_out_um, "label": t.label,
                "tol_balance": t.tol_balance,
            }

            def _oracle(p):
                return ybranch_oracle()["target_frac"]

            def _cand(spec, oracle_value):
                p = spec.params
                eps3, meta = build_ybranch_field_3d(
                    p["w_um"], p["h_um"], p["n_core"], p["n_clad"], p["wl_um"],
                    sep_um=p["sep_um"], l_in_um=p["l_in_um"],
                    l_trans_um=p["l_trans_um"], l_out_um=p["l_out_um"],
                    dl=p["dl"], clad_um=p["clad_um"])
                Nx, Ny = meta["Nx"], meta["Ny"]
                xs = (np.arange(Nx) - Nx / 2.0) * p["dl"]
                ys = (np.arange(Ny) - Ny / 2.0) * p["dl"]
                X, Y = np.meshgrid(xs, ys, indexing="ij")
                inp_core = (np.abs(X) <= p["w_um"] / 2.0) & (np.abs(Y) <= p["h_um"] / 2.0)
                eps2_in = np.full((Nx, Ny), p["n_clad"] ** 2)
                eps2_in[inp_core] = p["n_core"] ** 2
                _, mode_in = fdfd_mode_field(eps2_in, p["dl"], p["wl_um"])
                src_um = p["l_in_um"] * 0.7
                z_out = meta["l_out_start_um"] + np.linspace(0.6, 4.2, 7)
                neff_avg = 0.5 * (p["n_core"] + p["n_clad"])
                dt_f = p["dl"] * 0.95 / math.sqrt(3.0)
                period = int(round(2.0 * math.pi / (neff_avg * 2.0 * math.pi / p["wl_um"] * dt_f)))
                prop = int(round((z_out[0] - src_um) * neff_avg / dt_f))
                transient = 400 + prop + 5 * period
                fa, fb, _zu, _pa, _pb, _srcz = solve_port_powers_3d_torch(
                    eps3, meta["dl"], p["wl_um"], p["n_clad"], p["n_core"], mode_in,
                    meta["mask_a"], meta["mask_b"], src_um=src_um,
                    z_sample_um=z_out, M_cycles=20, transient=transient, debug=True)
                n_avg = max(2, len(fa) // 2)
                return float(np.mean(fa[-n_avg:]))

            specs.append(VerificationSpec(
                spec_id=sid, metric="power_frac", oracle_kind="symmetry_theorem",
                oracle_fn=_oracle, compare_fn=cmp_abs_balance,
                tol=params["tol_balance"], tol_mode="abs_balance",
                target_desc=t.label, params=params,
                source="对称性定理（几何完全对称 ⇒ P1=P2=0.5·P_in）",
                candidate_desc="标量 3D FDTD 能流功率测量（独立时域）"))
            cand_map[sid] = _cand
    return specs, cand_map


# ---------------------------------------------------------------------------
# 4. solver_writer（AI-dev 自举写核 · tmm 解析 ORACLE）
# ---------------------------------------------------------------------------
def cmp_max_abs_err(candidate, oracle) -> float:
    """逐用例最大绝对误差（oracle/candidate 为 list[list[float]]，每用例多波长）。"""
    if not isinstance(candidate, list) or len(candidate) != len(oracle):
        return float("inf")
    errs = []
    for c, o in zip(candidate, oracle):
        if isinstance(o, (list, tuple)):
            if not isinstance(c, (list, tuple)) or len(c) != len(o):
                return float("inf")
            errs.append(max(abs(float(g) - float(oo)) for g, oo in zip(c, o)))
        else:
            errs.append(abs(float(c) - float(o)))
    return max(errs)


def build_solver_writer_specs(spec, candidate_code: str
                              ) -> Tuple[List[VerificationSpec], Dict[str, Callable]]:
    """把 solver_writer 的一个 SolverSpec + 候选代码适配成统一契约（单 spec）。

    oracle = 各测试用例 ORACLE 真值列表；candidate = 沙箱执行候选代码后的逐用例输出；
    compare = cmp_max_abs_err（同 solver_writer.Verifier 语义，max_abs_err ≤ tol）。
    """
    from .verification_spec import VerificationSpec

    # 序列化 test_cases（oracle 真值 + 输入）到 params
    cases_data = [{
        "name": c.name, "inputs": c.inputs,
        "oracle": list(c.oracle_value) if isinstance(c.oracle_value, (list, tuple))
                  else c.oracle_value,
        "tol": c.tol,
    } for c in spec.test_cases]

    def _oracle(p):
        return [c["oracle"] for c in p["cases"]]

    def _cand(spec_obj, oracle_value):
        p = spec_obj.params
        from solver_writer import SandboxExecutor
        # 构造临时 SolverSpec 以复用沙箱执行（只取 test_cases 的输入）
        from solver_writer import SolverSpec, TestCase
        tmp_cases = [TestCase(name=c["name"], inputs=c["inputs"],
                              oracle_value=c["oracle"], tol=c["tol"])
                     for c in p["cases"]]
        tmp_spec = SolverSpec(spec_id=spec.spec_id,
                              problem_statement=spec.problem_statement,
                              entrypoint=spec.entrypoint,
                              io_contract=spec.io_contract,
                              test_cases=tmp_cases,
                              oracle_kind=spec.oracle_kind)
        res = SandboxExecutor(timeout=120.0).run(p["code"], tmp_spec)
        if not res.get("ok"):
            return None
        out = []
        by_name = {r["name"]: r for r in res.get("results", [])}
        for c in p["cases"]:
            r = by_name.get(c["name"])
            out.append(r["value"] if r and r.get("ok") else None)
        return out

    specs = [VerificationSpec(
        spec_id=spec.spec_id, metric="transmission", oracle_kind="tmm_analytic",
        oracle_fn=_oracle, compare_fn=cmp_max_abs_err,
        tol=0.05, tol_mode="abs",
        target_desc=f"AI-dev 写核：{spec.entrypoint}（{len(spec.test_cases)} 用例）",
        params={"cases": cases_data, "code": candidate_code},
        source="tmm.py 解析透射谱（外部物理定律锚）",
        candidate_desc="AI-dev 候选求解核（沙箱执行）")]
    return specs, {spec.spec_id: _cand}


# ============================================================================
# B28 独立候选：数值零点拟合 Vπ（v0.9.28 · T-2）
# ============================================================================
@_register_candidate(
    "mzm_vpi_nullfit",
    "推挽 MZM 传输谱 T(V)=cos²(Δφ_arm(V)) 数值采样 + 首个传输零点三点抛物线"
    "定顶 —— 与 golden 的解析反解闭式 Vπ=λ₀d/(2n³rΓL) 方法学独立"
    "（数值观测谱零点测量 vs 解析求根，与 B3/B4/B20 峰拟合同族）")
def _mzm_vpi_nullfit_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """B28 独立候选：数值零点拟合半波电压 Vπ。

    golden = 解析闭式（对 T(V)=0 条件解析反解）
    cand   = 按 Pockels 相位链算传输谱 T(V)，采样 → 找首个局部极小 →
             三点抛物线定顶（= 实验 Measure Vπ 标准流程的数值化）。
             **从不求值闭式**，也不含任何剖分守恒结构。

    🔴 判据 D 实测（2026-09-03，判据 D 单一定义处复算）：
    n_voltage 2→512 残差 1.91e-3 → 2.34e-8，粗端（n≤8，零点两侧采样对称
    抵消）后 N 加倍误差降 ~8-87×（cos² 四次修正项），**真数值离散化**。
    对照：同锚的沿程积分候选（mzm_vpi_integral）残差恒 4.44e-16 = 代数恒等
    （判据 D 反例，T-1 已证）——**同锚两候选恰成判据 D 的教学对照**。

    基线（生产档位 n_voltage=400）：残差 7.6e-9 V（tol=1e-3 的 0.0008%，
    ≫1e-12 噪声地板，双向可标定）。

    ⚠️ 诚实边界：①同一 1D Pockels 模型，独立性在「解法」不在「模型」（与
    B20 同档）；②扫描上界由相位链 Δφ=π 反解（=2·Vπ），仅括住零点不影响
    定位（上界取 3π 反解结果不变）；③均匀 Γ 假设（求解器支持任意 Γ(z)）。

    ⚠️ 失败即抛异常上浮，绝不静默回退（IndependentCandidateRouter 既定原则）。
    """
    try:
        from lda.lda_solver import mzm_vpi_nullfit as mv
    except ImportError:
        _ensure_paths()
        import mzm_vpi_nullfit as mv

    p = spec.params
    return float(mv.mzm_vpi_nullfit(
        lambda_vac_um=float(p["lambda_vac_um"]),
        n_eff=float(p["n_eff"]),
        r_eff=float(p["r_eff"]),
        gamma=float(p["gamma"]),
        L_um=float(p["L_um"]),
        d_um=float(p["d_um"]),
        n_voltage=mv.DEFAULT_N_VOLTAGE))


# ---------------------------------------------------------------------------
# S7 / S8 统计锚独立候选（v0.9.29 · T-3）：闭式高斯 p5（μ − 1.645σ）
# ---------------------------------------------------------------------------
# golden = 蒙特卡洛经验 5% 分位（随机采样、固定种子）；
# cand   = 闭式高斯 5% 分位（组件容差解析叠加得 μ/σ，p5 = μ − z·σ）。
# 方法学独立性：两题分布都是**精确高斯**（S7 独立正态损耗之和；S8 的
# 10log10(F)=nf+δ 恰为高斯 ⇒ OSNR 严格高斯）⇒ p5=μ−1.645σ 是闭式精确值，
# 与「抽样 + 经验分位」是两种不同算法。若分布非高斯，两者偏离 tol ⇒ 能抓错。
# 与 S13 的 `yield_analytic`（闭式 Φ ↔ MC 双算法互证）同型：闭式候选不进
# 判据 D（无离散参数），但基线残差 >1e-12 + 反向扰动必 FAIL ⇒ 真独立。
@_register_candidate(
    "gauss_p5_margin",
    "闭式高斯 p5 = μ−1.645σ（组件容差解析叠加 μ/σ）—— 与 MC 经验 5% 分位方法学独立")
def _s7_gauss_p5_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """S7 独立候选：闭式高斯最坏情况 p5（margin_p5_dB）。

    golden = 蒙特卡洛 margin 分布经验 5% 分位（固定种子 42）；
    cand   = μ − 1.645σ，μ/σ 由组件工艺容差解析叠加。

    实测（默认参数）：μ=10.5、σ=√(2·0.3²+(0.5·1)²+0.1²)=0.6633、
    p5=10.5−1.6449·0.6633=9.409；golden(MC p5)≈9.41，
    |Δ|≈0.001<tol 0.15（基线属抽样噪声，非恒等）。

    反向 10% 扰动信号谱（candidate 对参数真实响应、golden 取原值）：
    detector_sens_dbm −20→−22 ⇒ μ+2.0 ⇒ |Δ|≈2.0（13×tol）✅
    wg_loss_db_cm 3.0→3.3 ⇒ μ−0.3 ⇒ |Δ|≈0.30（2×）✅
    ⇒ PERTURB 固定扰 detector_sens_dbm（最强键，1% 即抓、min_detect=0.01）。

    ⚠️ 已知边界：候选假设分布为高斯（由独立正态之和的闭式保证），不做
    分布形态检验；「高斯性是否成立」由 s7 distribution_report 方向性断言 +
    实测语料背书，不在本题死标量判决内。
    """
    from .statistical_anchor import s7_gaussian_moments
    p = spec.params
    mu, sigma = s7_gaussian_moments(
        p_tx_dbm=float(p.get("p_tx_dbm", 0.0)),
        n_gratings=int(p.get("n_gratings", 2)),
        grating_db=float(p.get("grating_db", -3.0)),
        wg_length_cm=float(p.get("wg_length_cm", 1.0)),
        wg_loss_db_cm=float(p.get("wg_loss_db_cm", 3.0)),
        ring_il_db=float(p.get("ring_il_db", -0.5)),
        detector_sens_dbm=float(p.get("detector_sens_dbm", -20.0)))
    from .statistical_anchor import GAUSS_Z05
    return float(mu - GAUSS_Z05 * sigma)


@_register_candidate(
    "gauss_p5_osnr",
    "闭式高斯 p5 = μ−1.645σ（σ=√(σ_laser²+σ_nf²)）—— 与 MC 经验 5% 分位方法学独立")
def _s8_gauss_p5_candidate(spec: VerificationSpec, oracle_value: Any) -> float:
    """S8 独立候选：闭式高斯最坏情况 p5（OSNR_p5_dB）。

    golden = 蒙特卡洛 OSNR 分布经验 5% 分位（固定种子 7）；
    cand   = μ − 1.645σ，其中 10log10(F)=nf+δ 恰为高斯 ⇒ OSNR 严格高斯，
            μ = p_sig − 30 − 10log10(hνbwN) − nf，σ=√(σ_laser²+σ_nf²)。

    实测（默认参数）：μ=46.930、σ=√(0.5²+0.3²)=0.5831、
    p5=46.930−1.6449·0.5831=45.971；golden(MC p5)≈45.93，
    |Δ|≈0.04<tol 0.20（基线属抽样噪声，非恒等）。

    反向 10% 扰动信号谱：
    nf_db 5.0→5.5 ⇒ μ−0.5 ⇒ |Δ|≈0.5（2.5×tol）✅（min_detect=0.05）
    bw_ghz 50→55 ⇒ μ−0.414 ⇒ |Δ|≈0.41（2.1×）✅
    ⇒ PERTURB 固定扰 nf_db（最强键）。

    ⚠️ 已知边界：同 S7，候选假设 OSNR 为高斯（10log10(F)=nf+δ 闭式保证），
    不做形态检验；高斯性由 s8 osnr_distribution_report 方向性断言背书。
    """
    from .statistical_anchor import s8_gaussian_moments, GAUSS_Z05
    p = spec.params
    mu, sigma = s8_gaussian_moments(
        p_sig_dbm=float(p.get("p_sig_dbm", 0.0)),
        n_amp=int(p.get("n_amp", 1)),
        nf_db=float(p.get("nf_db", 5.0)),
        bw_ghz=float(p.get("bw_ghz", 50.0)))
    return float(mu - GAUSS_Z05 * sigma)
