"""锚题可证伪性 smoke（v0.9.14 立项 · P0-1；v0.9.15 补 ⑦⑧ 对外口径护栏 · P0-2；
v0.9.16 补 P0-3 三分类双向复核 · P0 续光子侧 B3/B4/B20 接线）。

背景（2026-09-02 战略审计实测）：48 锚实跑 48 PASS，其中 **47 道是自证桩**
——candidate 走 `_harness_reference_candidate`（直接返回 golden），
|cand−golden| ≡ 0 恒 PASS、零验证价值。全绿不等于可证伪。

本 smoke 是**反自证桩的常驻护栏**，判八件事：

  ① 独立性普查：48 锚中有多少道真走独立候选（|cand−golden| > 0）
  ② 正向：独立候选锚必须在各自 tol 内 PASS（证明求解器没坏）
  ③ 反向（关键）：注入参数扰动 ⇒ **必须 FAIL**
     —— 证明 tol 没有放水到"什么都抓不住"，护栏真能抓错
  ④ 灵敏度：登记「最小可检出扰动」上界，把验证强度显式化
  ⑤ 无回归：独立化不得弄坏其余任何一道（全 48 锚仍全绿）
  ⑥ 诚实披露剩余自证桩（不构成失败，但必须可见）
  ⑦ 对外口径：/api/verification_ledger 的三分类必须**逐项等于**本机实测
     —— 外部验货面曾把独立候选硬编码成 ["E2"]（而 E2 恰是已降级那道），
     新接的 4 道一道没出现；改为动态推导后仍须钉死，防"动态"悄悄失效
  ⑧ 路径②一致：CLI 对外主报告（VerificationHarness + IndependentCandidateRouter）
     的 verified 口径必须等于路径①，且 48 题**全部按题标注**独立性
     —— ci.yml 直跑 run_harness.py，但本地 `--tag core` 不跑它，存在覆盖盲区

为什么③比②重要：②只能证明"没坏"，③才能证明"坏了能发现"。
只做②不做③，等于把「放宽容差」变成「取消验证」——这正是自证桩的翻版。

🔴 ⑧ 的**双向**复核（v0.9.16 · P0-3 加强，仍守「标签 ≠ 行为」教训）：
   · 非自证桩（strict / degraded）⇒ |cand−golden| 必须 **非零**
     （若恒为零 = 静默回落 golden，verified 虚报）
   · 自证桩 ⇒ |cand−golden| 必须 **为零**
     （若非零 = 分类表与实现脱节，该道实际已接线却被算进自证桩，verified 少算）
  只做前半条时，v0.9.15 曾放过「路由已改坏、标签仍为真」的假绿；
  只做前半条也放得过「新接线被误分类成自证桩」的漏算 —— 故必须双向。

⚠️ 诚实边界（实测发现，2026-09-02）：
  B26 在 g 扰动 +1% 处 diff=1.68e-6，反而**小于**未扰动时的 4.57e-5
  ——参数扰动与（闭式↔数值）近似误差发生**偶然抵消**。这是物理上的正常
  现象，但意味着**小幅系统误差存在检测盲点**。故反向测试采用 10% 扰动
  （该档位 4 道全 FAIL，稳健），并额外登记「最小可检出扰动」作为灵敏度
  指标，把验证强度显式化，而不是藏在一句"PASS"后面。

运行：python run_benchmark_falsifiability_smoke.py
出口：全部 PASS 退 0；任一 FAIL 退 1。LLM 不进判决路径。
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
# ⑦ 需按包路径导入 WebUI 端点（lda.lda_webui.routes）⇒ 仓库根也要在路径里。
# 用 append 而非 insert，避免抢占 lda_harness 等顶层模块名。
sys.path.append(os.path.dirname(_HERE))

from lda_harness.benchmarks import BENCHMARK_DEFS, BENCHMARK_ORDER
from lda_harness.verification_adapters import (
    build_harness_specs, BENCHMARK_CANDIDATES,
)
from lda_harness.verification_spec import VerificationSpec, run_verification

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {('| ' + detail) if detail else ''}")


# 独立候选锚题的**反向测试配置**：(锚题, 扰动参数, 扰动方式)
# 扰动幅度：10%（实测该档位 4 道全部 FAIL，稳健；更小幅度存在抵消盲点）
PERTURB_SPEC = [
    ("B9", "E_J", "mul"),
    ("B25", "phi_frac", "add"),
    ("B26", "g_ghz", "mul"),
    ("B27", "g_ghz", "mul"),
    # v0.9.16（P0 续）：光子侧 FSR 三兄弟（FSR ∝ 1/光程 ⇒ 光程 +10% ⇒ FSR −9%）
    ("B3", "L", "mul"),
    ("B4", "R", "mul"),
    ("B20", "deltaL_um", "mul"),
    # v0.9.17（P0 续）：量子侧五道（离散 TL 本征 / 电荷基 / HO 基 / 三模 Fock）
    ("B12", "l", "mul"),            # λ/4 谐振器长度 ⇒ f0 ∝ 1/l
    ("B22", "L_um", "mul"),         # 同上（CPW 读出腔）
    ("B23", "el_ghz", "mul"),       # f01=√(8EcEl) ⇒ El +10% ⇒ f01 +4.9%
    ("B24", "wq_ghz", "mul"),       # Δ=wq−wc ⇒ g_eff 随失谐变化（实测信号最强键）
    # v0.9.18（P0 续）：S13 设计良率（解析 Φ ↔ 蒙特卡洛双算法互证）。
    # 🔴 必须扰 delta（规格窗口 ±x%，信号 1.73e-2，51× 最强键）。
    #   实测逐键信号：delta 1.73e-2 ✅ · sigma_rel 2.39e-2 ✅ · fsr_nom 3.37e-4 ❌
    #   （yield 对 fsr_nom 免疫，σ 按比例缩放 ⇒ 盲区已写入 note，不掩盖）。
    ("S13", "delta", "mul"),
    # 🔴 B13 必须扰 C1（信号 4.07e-3，唯一稳超 tol=2.0e-3 的强键）。
    #   实测逐键信号：C1/C2 4.07e-3 ✅ · E_C1/E_C2 2.06e-3 ✅ · Cc 1.72e-3 ❌
    #   · E_J1/E_J2 5.50e-4 ❌（比基线 1.31e-3 还小 —— 扰动与近似误差偶然抵消，
    #   同 B26 现象）。盲区已写入 benchmarks.py 的 note，不掩盖。
    ("B13", "C1", "mul"),
    # v0.9.19（P0 续）：B15 Bragg 光栅（Bloch 本征值 ↔ 相位匹配闭式）。
    # 扰 n_eff（信号 1.55e-1，15.5×）；period 与 n_eff 一阶等价（λ_B∝n_eff·Λ）
    #   ⇒ 同信号，固定扰 n_eff。
    ("B15", "n_eff", "mul"),
    # v0.9.20（P0 续）：B14 定向耦合器 3dB（FFT 拍频谱峰 ↔ 解析闭式）。
    # 🔴 本道伴随 golden 语义修正（15.5→7.75，完全转移长度错标 3dB 点）。
    # 扰 n_e（信号 6.44，25.8× 最强键）；n_o×1.1→5.71 · wl×1.1→0.775。
    ("B14", "n_e", "mul"),
    # v0.9.21（P0 续）：B1 米氏散射（完整 Mie 级数 ↔ Rayleigh 一阶极限）。
    # 扰 m（信号 2.357e-3，11.9× 最强键）；x×1.1→1.246e-3（6.2×）。
    ("B1", "m", "mul"),
    # v0.9.23（P0 续）：E2 由「降级量级参考」**升为严格独立候选**
    # （候选 fdfd_ng → semivec_ng，2D 半矢量本征模；FDFD 的 ±0.04~0.08 窗口
    #  散射缺陷被解决，半矢量散射 <1e-5）。
    # 🔴 必须扰 n_core（信号 0.3600，3.6× tol）。实测逐键信号（|Δ| vs golden）：
    #   n_core×1.1 0.3600 ✅ · n_clad×0.9 0.1212 ✅ · h_um×1.1 0.1032 ✅(仅 1.03×，不用)
    #   w_um×1.1 0.0764 ❌ · w_um×0.9 0.0511 ❌ · h_um×0.9 0.0191 ❌ · n_clad×1.1 0.0173 ❌
    #   ⇒ 四个弱键**抓不住**，已如实登记在此，不掩盖、不改用弱键充数。
    ("E2", "n_core", "mul"),
    # v0.9.24（P0 续）：B10 门保真度（Lindblad 数值积分 ↔ 解析闭式）
    #   + **golden 语义修正（D-66 第 8 例）**：旧式 exp(−t(1/T1+1/(2T2))) 被证否
    #     （一阶系数是严格解的 2.727×，比值 30/11 无物理来源），改 Lindblad 严格
    #     平均门保真度闭式 (3+2e^(−t/T2)+e^(−t/T1))/6。
    #   + **tol 收紧 1e6 倍**（0.01 → 1e-8）：旧 tol 下六路 10% 扰动信号
    #     （1.5e-5~4.2e-5）比 tol 小 240~660 倍，一根都抓不住 ⇒ 该锚零判别力。
    # 🔴 收紧后**三键六路全部可抓**（与 E2 的四个弱键形成对照）：
    #   t_gate±10% 1.527e-5（1527×）· T2±10% 1.010e-5/1.234e-5（1010×/1234×）
    #   T1±10% 3.787e-6/4.628e-6（379×/463×）
    #   ⇒ 这里登记全部三键（都稳超 tol），不做"挑强键"的取舍。
    ("B10", "t_gate", "mul"),
    ("B10", "T1", "mul"),
    ("B10", "T2", "mul"),
]
PERTURB_REL = 0.10          # 反向测试扰动幅度（10%）
SENSITIVITY_GRID = (0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.10, 0.20)
SENSITIVITY_MAX = 0.10      # 灵敏度上界断言：10% 扰动必须可检出

# 独立候选数下限（随 P0 推进递增：v0.9.14 起步 4 → v0.9.16 光子侧 7
# → v0.9.17 量子侧接 B12/B13/B22/B23/B24 后 12
# → v0.9.18 接 S13（解析 Φ ↔ 蒙特卡洛双算法互证，S7/S8 伪独立陷阱已证否）后 13
# → v0.9.19 接 B15（Bloch 本征值 ↔ 相位匹配闭式，tmm 物理对象错配已绕开）后 14
# → v0.9.20 接 B14（FFT 拍频谱峰 ↔ 解析闭式；golden 语义修正 15.5→7.75）后 15
# → v0.9.21 接 B1（完整 Mie 级数 ↔ Rayleigh 一阶极限；golden 钉死环境无关）后 16
# → v0.9.23 接 E2（2D 半矢量本征模 ↔ Si3N4 实测 n_g；由降级锚升为 strict）后 17
#   注意：E2 是**升级**不是新增 —— 它原本就在 independent 里，只是被算进
#   degraded。故本轮 strict +1、degraded −1、stub 不变（48 守恒）。
# → v0.9.24 接 B10（Lindblad 4×4 超算子 RK4 积分 ↔ 解析闭式；伴 golden 语义
#   修正 D-66 第 8 例 + tol 由 0.01 收紧 1e6 倍至 1e-8）后 18。
#   本轮是**真新增**（B10 此前为自证桩）⇒ strict +1、stub −1（48 守恒）。）
MIN_INDEPENDENT = 18


def _clone_with(sp: VerificationSpec, key: str, value: float) -> VerificationSpec:
    """克隆 spec 并替换单个参数（oracle 仍取原 golden，模拟「求解器算错」）。"""
    p2 = dict(sp.params)
    p2[key] = value
    return VerificationSpec(
        spec_id=sp.spec_id, metric=sp.metric, oracle_kind=sp.oracle_kind,
        oracle_fn=sp.oracle_fn, compare_fn=sp.compare_fn, tol=sp.tol,
        tol_mode=sp.tol_mode, target_desc=sp.target_desc, params=p2,
        source=sp.source, candidate_desc=sp.candidate_desc,
    )


def _perturb(base: float, rel: float, mode: str) -> float:
    """扰动取值：非零参数按比例（mul），零值参数用加法（add，避免乘 0 无效）。"""
    return base * (1.0 + rel) if mode == "mul" else base + rel


def _candidate_responds(sp, cand_fn, oracle_value) -> bool:
    """候选是否对参数扰动有**物理响应** —— 真候选 vs 自证桩的行为判据。

    🔴🔴 铁律「标签 ≠ 行为」的升级版（v0.9.24 · 由 B10 触发）

    原判据 `|cand − golden| < 1e-12 ⇒ 自证桩` 在 B10 上**误判**：B10 的候选是
    真的 4×4 Liouvillian 超算子 RK4 积分（三条**可标定**自校锚 + 六路反向扰动
    全部抓住，信号 1.5e-5），但生产档位 t_gate=0.02 µs、T1/T2~60-80 µs ⇒
    无量纲演化量 |L|·t ≈ 2.5e-4 ⇒ RK4 从 N=5 到 N=400 残差**恒为 1.11e-16**，
    与步数无关。即该锚的残差**物理上不可标定**，必然落在 1e-12 以内。

    自证桩的**充要特征**其实不是「残差小」，而是「**跟着 golden 走**」：
    `_harness_reference_candidate(spec, oracle_value)` 直接 `return oracle_value`，
    **完全不看 spec.params** ⇒ 扰动参数后候选值纹丝不动，|cand − golden(原)| ≡ 0。
    真候选扰动后会给出真实物理响应。

    ⇒ 判据改为（仍是**值上**判定，不查标签）：
        残差 ≡ 0 **且** 对全部数值参数做 ±10% 扰动都无响应 ⇒ 自证桩
    这比原来的单点启发式**更严**：原判据会被「残差恰好小」的真候选误伤，
    也会被「残差恰好大」（如浮点抖动）的自证桩漏过；新判据两者都不会。

    🔴 **本函数只做薄委托**：权威实现在 `lda_harness.harness.candidate_responds`。
    v0.9.24 实测教训——smoke 里写一份、`run_harness.py` 里再写一份，只升级
    前者 ⇒ smoke 8/8 全绿而 CLI 断言 `假独立=['B10']` 崩掉。**判据必须单一
    定义处**，这里保留签名兼容（VerificationSpec 与 _SpecShim 都吃）。
    """
    from lda_harness.harness import candidate_responds
    return candidate_responds(sp, cand_fn, oracle_value)


def main() -> int:
    print("=" * 70)
    print("LDA 锚题可证伪性 smoke（反自证桩护栏）")
    print("=" * 70)

    specs, cand_map = build_harness_specs()
    by_id = {s.spec_id: s for s in specs}

    # ① 独立性普查：区分「真独立求解」与「自证桩」
    # 🔴 v0.9.24：判据不再只看 |cand−golden|<1e-12（该启发式对 B10 误判，
    # 见 _candidate_responds 的 docstring），加**行为**条件：残差 ≡0 且扰动
    # 无响应才算自证桩。
    independent, stub = [], []
    for sp in specs:
        try:
            ov = sp.oracle_fn(sp.params)
            cv = cand_map[sp.spec_id](sp, ov)
            is_stub = (isinstance(cv, (int, float))
                       and isinstance(ov, (int, float))
                       and abs(cv - ov) < 1e-12
                       and not _candidate_responds(sp, cand_map[sp.spec_id], ov))
        except Exception:
            is_stub = True
        (stub if is_stub else independent).append(sp.spec_id)

    # 独立候选中，**进死标量判决**的才算数：candidate_status="degraded_ordinal"
    # 的锚（如 E2，FDFD 直波导候选 vs 环器件 golden 几何不同源）仅作量级参考，
    # 不计入独立强度——避免用一个已降级的锚充数（诚实边界 C，R16 证伪）。
    degraded = [b for b in independent
                if BENCHMARK_DEFS.get(b, {}).get("candidate_status")
                == "degraded_ordinal"]
    strict = [b for b in independent if b not in degraded]
    n_ind = len(strict)

    check(f"进判决的独立候选锚题数 ≥ {MIN_INDEPENDENT}（脱离自证桩）",
          n_ind >= MIN_INDEPENDENT,
          f"严格独立={n_ind} {sorted(strict)} · 降级量级参考={degraded} "
          f"· 自证桩={len(stub)}/{len(specs)}")

    check("已登记候选类型与实测独立锚一致（无登记未接线）",
          set(BENCHMARK_CANDIDATES) <= {
              d.get("candidate") for d in BENCHMARK_DEFS.values()
              if d.get("candidate")},
          f"登记表={sorted(BENCHMARK_CANDIDATES)}")

    # ② 正向：独立候选锚必须在各自 tol 内 PASS（只查进判决的严格独立锚）
    ok_pos, detail_pos = [], []
    for bid in strict:
        sp, ov = by_id[bid], None
        try:
            ov = sp.oracle_fn(sp.params)
            cv = cand_map[bid](sp, ov)
            out = run_verification(sp, cand_map[bid], oracle_value=ov)
            rel = abs(cv - ov) / abs(ov) * 100 if ov else 0.0
            # 一并披露 |diff|/tol：残差相对容差越小，说明该道验证**越灵敏**
            # （容差放水到残差的 1e6 倍时，等于几乎抓不到任何东西）
            ratio = abs(cv - ov) / sp.tol if sp.tol else float("inf")
            ok_pos.append(out.passed)
            detail_pos.append(f"{bid}:{rel:.3e}%(d/tol={ratio:.1e})")
        except Exception as e:
            ok_pos.append(False)
            detail_pos.append(f"{bid}:ERR {str(e)[:30]}")
    check("独立候选锚正向全部 PASS（求解器未坏）",
          all(ok_pos) and len(ok_pos) > 0, " ".join(detail_pos))

    # ③ 反向（核心）：10% 参数扰动 ⇒ 必须 FAIL
    ok_neg, detail_neg = [], []
    for bid, key, mode in PERTURB_SPEC:
        if bid not in by_id:
            ok_neg.append(False)
            detail_neg.append(f"{bid}:缺失")
            continue
        sp = by_id[bid]
        try:
            ov = sp.oracle_fn(sp.params)
            base = float(sp.params[key])
            sp2 = _clone_with(sp, key, _perturb(base, PERTURB_REL, mode))
            cv = cand_map[bid](sp2, ov)
            out = run_verification(sp2, cand_map[bid], oracle_value=ov)
            caught = (not out.passed)
            ok_neg.append(caught)
            detail_neg.append(f"{bid}@{key}{PERTURB_REL:+.0%}:"
                              f"{'FAIL✅' if caught else 'PASS❌'}"
                              f"(d={abs(cv - ov):.3e}/tol={sp.tol:.3g})")
        except Exception as e:
            ok_neg.append(False)
            detail_neg.append(f"{bid}:ERR {str(e)[:30]}")
    check(f"反向测试：{PERTURB_REL:.0%} 参数扰动必被抓（tol 未放水）",
          all(ok_neg) and len(ok_neg) > 0, " ".join(detail_neg))

    # ④ 灵敏度登记：最小可检出扰动（把验证强度显式化）
    sens_rows = []
    for bid, key, mode in PERTURB_SPEC:
        if bid not in by_id:
            continue
        sp = by_id[bid]
        min_detectable = None
        for rel in SENSITIVITY_GRID:
            try:
                ov = sp.oracle_fn(sp.params)
                sp2 = _clone_with(sp, key, _perturb(float(sp.params[key]), rel, mode))
                out = run_verification(sp2, cand_map[bid], oracle_value=ov)
                if not out.passed:
                    min_detectable = rel
                    break
            except Exception:
                continue
        sens_rows.append((bid, key, min_detectable))
        print(f"      灵敏度 {bid}（扰动 {key}）："
              f"{'≤%.1f%%' % (min_detectable * 100) if min_detectable else '>20% 未检出'}")

    worst = max((r[2] for r in sens_rows if r[2] is not None), default=None)
    check(f"灵敏度上界：最小可检出扰动 ≤ {SENSITIVITY_MAX:.0%}",
          worst is not None and worst <= SENSITIVITY_MAX,
          f"最差={worst:.1%}" if worst else "无锚题可测")

    # ⑤ 无回归：全 48 锚仍全绿（独立化不得弄坏任何一道）
    n_pass = 0
    for sp in specs:
        try:
            ov = sp.oracle_fn(sp.params)
            if run_verification(sp, cand_map[sp.spec_id], oracle_value=ov).passed:
                n_pass += 1
        except Exception:
            pass
    check(f"全量 {len(specs)} 锚无回归（{BENCHMARK_ORDER[0]}–{BENCHMARK_ORDER[-1]}）",
          n_pass == len(specs) == len(BENCHMARK_DEFS),
          f"PASS={n_pass}/{len(specs)}")

    # ⑦ 对外账本口径一致性（v0.9.15/P0-2 新增）：
    # /api/verification_ledger 是**外部验货面**，此前把独立候选硬编码成
    # ["E2"]——而 E2 恰是已降级那道，新接的 B9/B25/B26/B27 一道都没出现，
    # 对外宣称与代码实际状态脱节。已改为动态推导，但"动态"本身也可能失效
    # （登记表漏登记 / 候选跑挂回落 golden / 分类条件被改坏）。
    # 与 ci_core 计数漂移是同一类缺陷（写死 vs 实际），故用常驻护栏钉死：
    # 端点三分类必须**逐项等于**本机实测分类，且 CLI 报告 verified 同步。
    try:
        from lda.lda_webui.routes import h_verification_ledger
        _code, _ledger = h_verification_ledger(None, None, None,
                                               "/api/verification_ledger")
        _jp = (_ledger or {}).get("judgment_paths", {})
        _d = _jp.get("derived", {}) or {}
        _e_ind = set(_d.get("strict_independent") or [])
        _e_deg = set(_d.get("degraded_ordinal") or [])
        _e_stub = set(_d.get("self_consistent_placeholder") or [])
        _tot = _d.get("totals") or {}
        _cli = _jp.get("harness_cli", {}) or {}
        _diff = []
        if _e_ind != set(strict):
            _diff.append(f"独立集合差={sorted(set(strict) ^ _e_ind)}")
        if _e_deg != set(degraded):
            _diff.append(f"降级集合差={sorted(set(degraded) ^ _e_deg)}")
        if _e_stub != set(stub):
            _diff.append(f"自证集合差={sorted(set(stub) ^ _e_stub)}")
        if _tot.get("anchors") != len(specs):
            _diff.append(f"总数={_tot.get('anchors')}≠{len(specs)}")
        if _cli.get("verified") != len(strict):
            _diff.append(f"CLI verified={_cli.get('verified')}≠{len(strict)}")
        # P0-3（v0.9.16）闭合后路径② 也走三分类 ⇒ CLI stub 应**恰好等于**
        # 三分类 stub（E2 在两条路径都是 degraded，不再被塞进自证桩）。
        # v0.9.15 时此处是 stub+degraded（43+1=44），是分类能力缺失的补丁，
        # 不是真实口径；现在按真实口径断言，混淆会被立刻抓住。
        _expect_stub = len(stub)
        if _cli.get("self_consistent_stub_count") != _expect_stub:
            _diff.append(f"CLI stub={_cli.get('self_consistent_stub_count')}≠{_expect_stub}")
        _tri = _cli.get("trichotomy_totals") or {}
        if (_tri.get("strict_independent"), _tri.get("degraded_ordinal"),
                _tri.get("self_consistent_stub")) != (len(strict), len(degraded), len(stub)):
            _diff.append(f"CLI 三分类={_tri}≠({len(strict)},{len(degraded)},{len(stub)})")
        check("对外账本 /api/verification_ledger 三分类与实测口径逐项一致（无硬编码漂移）",
              _code == 200 and not _diff,
              (f"端点 独立{len(_e_ind)}/降级{len(_e_deg)}/自证{len(_e_stub)}"
               f" · 总和{_tot.get('anchors')}/{len(specs)}"
               f" · CLI verified={_cli.get('verified')}/{len(strict)}")
              + (" ⚠ " + "；".join(_diff) if _diff else ""))
    except Exception as e:  # noqa: BLE001 —— 端点推导失败时判 FAIL，不静默跳过
        check("对外账本 /api/verification_ledger 三分类与实测口径逐项一致（无硬编码漂移）",
              False, f"端点不可达/推导异常：{str(e)[:80]}")

    # ⑧ 路径②（CLI 对外主报告）护栏（v0.9.15/P0-2 新增）：
    # ①–⑤ 守护的是**路径①**（内部 smoke 的 build_harness_specs + cand_map），
    # 但对外主报告走**路径②**（VerificationHarness.run + IndependentCandidateRouter）。
    # ci.yml 第 29 行会直跑 run_harness.py，但**本地 `--tag core` 门禁不跑它**
    # ⇒ 本地存在覆盖盲区（与 v0.9.10「脚本在 ci.yml 却不在本地 core」同类）。
    # 这里在进程内复现路径②（**不写报告文件**，避免每次回归污染工作区），
    # 断言其 verified 口径与路径①一致，杜绝「两条路径各说各话」。
    try:
        from lda_harness.harness import VerificationHarness, IndependentCandidateRouter
        from lda_harness import report as rep
        _h = VerificationHarness(BENCHMARK_DEFS)
        _r2 = _h.run(_h.resolve_specs(None), IndependentCandidateRouter())
        _n_ind2 = sum(1 for r in _r2 if getattr(r, "independent", False))
        _verified2 = rep.verified_count(_r2, True)
        _n_marked2 = rep.independence_counts(_r2)[1]
        _n_strict2, _n_deg2, _n_stub2, _n_cls2 = rep.candidate_class_counts(_r2)
        _bad8 = []
        if _n_ind2 != len(strict):
            _bad8.append(f"独立数={_n_ind2}≠路径①{len(strict)}")
        if _verified2 != _n_ind2:
            _bad8.append(f"verified={_verified2}≠独立数{_n_ind2}")
        if _n_cls2 != len(_r2):
            _bad8.append(f"三分类标注{_n_cls2}/{len(_r2)}（有未标注=口径退化）")
        if (_n_strict2, _n_deg2, _n_stub2) != (len(strict), len(degraded), len(stub)):
            _bad8.append(f"路径②三分类=({_n_strict2},{_n_deg2},{_n_stub2})"
                         f"≠路径①({len(strict)},{len(degraded)},{len(stub)})")
        # 🔴 标签 ≠ 行为（v0.9.15 血案）+ 三分类双向复核（v0.9.16 加强）：
        # 只查 independent 标签会被"标签为真、实现已回落 golden"骗过 ⇒ 按值复核。
        #   ① 非自证桩（strict/degraded）⇒ |diff| 必须非零（回落 golden 即穿帮）
        #   ② 自证桩 ⇒ |diff| 必须为零（分类表与实现脱节、新接线被吞即穿帮）
        # 🔴 v0.9.24：① 的判据加**行为**条件（同路径①，见 _candidate_responds）。
        #   B10 的 |diff|=1.11e-16（物理上不可标定，非回落 golden），靠
        #   「扰动 T1/T2/t_gate 有 1.5e-5 响应」证明是真候选。
        _labeled_stub = [r.bid for r in _r2
                         if getattr(r, "candidate_class", None)
                         not in (None, "self_consistent_stub")
                         and isinstance(r.candidate, (int, float))
                         and isinstance(r.golden, (int, float))
                         and abs(r.candidate - r.golden) < 1e-12
                         and not (r.bid in by_id
                                  and _candidate_responds(by_id[r.bid],
                                                          cand_map[r.bid],
                                                          r.golden))]
        if _labeled_stub:
            _bad8.append(f"标非自证桩却 |diff|≡0 的假独立={sorted(_labeled_stub)}")
        _mislabeled_stub = [r.bid for r in _r2
                            if getattr(r, "candidate_class", None) == "self_consistent_stub"
                            and isinstance(r.candidate, (int, float))
                            and isinstance(r.golden, (int, float))
                            and abs(r.candidate - r.golden) >= 1e-12]
        if _mislabeled_stub:
            _bad8.append(f"标自证桩却 |diff|≠0 的漏算={sorted(_mislabeled_stub)}")
        if _n_marked2 != len(_r2):
            _bad8.append(f"按题标注{_n_marked2}/{len(_r2)}（有未标注项=口径退化）")
        if len(_r2) != len(specs):
            _bad8.append(f"题数={len(_r2)}≠{len(specs)}")
        check("路径②（CLI 对外主报告）verified 口径与路径①一致且按题全标注",
              not _bad8,
              (f"独立{_n_ind2} · verified={_verified2} · "
               f"按题标注{_n_marked2}/{len(_r2)}")
              + (" ⚠ " + "；".join(_bad8) if _bad8 else ""))
    except Exception as e:  # noqa: BLE001 —— 路径②复现失败即判 FAIL
        check("路径②（CLI 对外主报告）verified 口径与路径①一致且按题全标注",
              False, f"路径②复现异常：{str(e)[:80]}")

    # ⑨ 报告可序列化护栏（v0.9.24 新增 · **被同一类 bug 咬了两次**）：
    #   v0.9.17 B24：候选返回 numpy 标量 ⇒ run_harness JSON 序列化 TypeError
    #   v0.9.24 B10：候选返回 np.float64 ⇒ `passed` 变 **np.bool_** ⇒ 同一个 TypeError
    # 根因：路径⑧ 在进程内复现路径② 时**刻意不写报告文件**（避免污染工作区）
    #   ⇒ `report.format_json` 从未被执行 ⇒ 全量回归里 run_harness.py 才第一次撞上。
    # 🔴 教训：**进程内复现 ≠ 覆盖真实出口**；省掉的那一步就是盲区。
    # 这里**只在内存里序列化、不落盘**（保留原「不污染工作区」的设计）。
    try:
        from lda_harness import report as rep
        _meta = {"generated_by": "run_benchmark_falsifiability_smoke",
                 "candidate": "IndependentCandidateRouter"}
        try:
            _js = rep.format_json(_r2, _meta)
            _ok9, _err9 = True, ""
        except Exception as _e9:  # noqa: BLE001
            _js, _ok9, _err9 = "", False, f"{type(_e9).__name__}: {_e9}"
        _json_bad = [] if _ok9 else [_err9]
        if _ok9:
            try:
                _parsed = json.loads(_js)
            except Exception as _e9:  # noqa: BLE001
                _parsed, _json_bad = None, [f"JSON 回读失败：{_e9}"]
            if _parsed is not None:
                # 标量类型回归检查：判决链上不许出现 numpy 标量
                _np = [r.get("bid", "?") for r in _parsed.get("results", [])
                       if not isinstance(r.get("passed"), (bool, type(None)))]
                if _np:
                    _json_bad.append(f"passed 非 Python bool 的题={sorted(_np)}（numpy 标量泄漏进判决链）")
        check("路径② 报告可 JSON 序列化（判决链无 numpy 标量泄漏）",
              not _json_bad,
              "；".join(_json_bad) if _json_bad else "48 题 format_json 通过且 passed 均为 Python bool")
    except Exception as e:  # noqa: BLE001
        check("路径② 报告可 JSON 序列化（判决链无 numpy 标量泄漏）",
              False, f"检查自身异常：{str(e)[:80]}")

    # ⑥ 诚实披露剩余自证桩（不构成失败，但必须可见）
    print()
    print(f"  [披露] 剩余自证桩 {len(stub)}/{len(specs)} 道"
          f"（candidate≡golden，恒 PASS、零验证价值）：")
    print(f"         {', '.join(stub)}")

    n_fail = sum(1 for _, ok, _ in CHECKS if not ok)
    print()
    print(f"锚题可证伪性 smoke：{len(CHECKS) - n_fail}/{len(CHECKS)} PASS · "
          f"严格独立 {n_ind} 道 · 降级量级参考 {len(degraded)} 道 · "
          f"自证桩 {len(stub)}/{len(specs)} 道")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
