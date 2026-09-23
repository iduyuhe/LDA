"""v0.9.132 P3-T3.3 · 对抗题自动判分 smoke（迈向 VMM Tier-4）。

## 现状（改造前）

开放对抗性题库 `lda/lda_harness/seed_empirical.json` 的 `adversarial` 段有 **4 道**
入库对抗题（征集「让 AI 求解器翻车」的物理陷阱题）。此前 `run_empirical_bank.py`
只把它们**打印出来**（`for b in bank._items.values(): print(...)`）—— 即「有题、无判分」，
离 VMM Tier-4（可自动判分）还差一整步。

## 本 smoke 做什么

把 4 道题逐题**绑定 in-tree 求解器**并**自动判分**，且每道题的判分都必须过
**反向测试**（错答必不通过）。判分链全死标量、零 LLM、零网络。

判分的判据**不**来自任何拟合式或 golden 常数，而来自**物理必然性**：

  · A-TAPER-FAST ：有限长度锥度 ⇒ `T < 1` **严格**（非绝热极限）；且渐变不劣于
    突变结 ⇒ `T ≥ abrupt_overlap`。陷阱题本意就是「求解器按绝热极限高估到 T=1」。
  · A-HETERO-MODE：两端芯宽差 3 倍 ⇒ 模场失配 ⇒ `η < 1` **严格**。陷阱是
    「忽略失配直接报 η=1」。

## 🔴 关键交付：**2 道可判分 + 2 道如实标注不可判分**

逐题勘查后的诚实结论（不虚报「4/4 已判分」）：

| 题 | 判分 | 依据 |
|---|---|---|
| A-TAPER-FAST | ✅ 可判分 | `eme_taper.taper_transmission`（EME）+ `abrupt_overlap`（独立下界） |
| A-HETERO-MODE | ✅ 可判分 | `eme_taper.abrupt_overlap`（模场重叠积分）+ 物理界 |
| A-BEND-R2 | ❌ 不可判分 | 本仓**无**「弯曲辐射损耗 vs R」物理求解器：`bend_mode` 只给群折射率 n_g（metric 不符）、`route_net.bend_loss_db` 是**布线模型**非器件物理 |
| A-CROSS-TIGHT | ❌ 不可判分 | `loss_engines.engine_crossing` 是唯象拟合式（XT=−(28+4L/w)）且**不读 gap**，无法响应本题核心变量 gap=0.1µm |

「不可判分」也**必须**带回溯理由与「缺什么」——这本身就是对抗题库的价值输出
（它暴露了求解器的覆盖边界）。disposition 三态完备、**禁静默跳过**。

运行：python run_adversarial_scoring_smoke.py
"""
from __future__ import annotations

import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "lda_solver"))

from lda_harness.smoke_kit import make_check                    # noqa: E402

_PASS = 0
_FAIL = 0

check = make_check(globals(), ok_key="_PASS", bad_key="_FAIL",
                   indent="  ", detail_fmt='  ({d})', return_ok=True)

_SEED = os.path.join(_HERE, "lda_harness", "seed_empirical.json")

#: 每道题的处置三态（完备枚举，禁「未处理」）
DISPOSITIONS = ("scored", "unscorable")


# ---------------------------------------------------------------------------
# 判分器：从**题目 geometry** 驱动求解器（改题 ⇒ 判分跟着变，不硬编码结果）
# ---------------------------------------------------------------------------
def _score_taper_fast(geom: dict, tol: float) -> dict:
    """A-TAPER-FAST：极短锥度（L=5µm）传输率 T。

    求解器：EME（`taper_transmission`）；独立参照：突变结下界（`abrupt_overlap`）。
    """
    from lda_solver.eme_taper import taper_transmission, abrupt_overlap
    w1, w2 = float(geom["w1_um"]), float(geom["w2_um"])
    L, wl = float(geom["L_um"]), float(geom["wl_um"])
    n_eff, n_clad = float(geom["n_eff"]), float(geom["n_clad"])
    T = float(taper_transmission(w1, w2, L, wl, n_eff, n_clad))
    T_lower = float(abrupt_overlap(w1, w2, wl, n_eff, n_clad))
    return {
        "value": T, "independent_ref": T_lower,
        "solver": "eme_taper.taper_transmission（EME 本征模展开）",
        "ref_name": "eme_taper.abrupt_overlap（突变结极限，独立下界）",
        # ① 渐变不劣于突变（物理下界）② 有限长度必有损耗 ⇒ T<1 严格 ③ 与下界在 tol 内
        "criteria": {
            "T_ge_lower_bound": T >= T_lower - 1e-12,
            "T_strictly_below_one": (1.0 - T) > 1e-4,
            "T_within_tol_of_lower": abs(T - T_lower) <= tol,
        },
    }


def _score_hetero_mode(geom: dict, tol: float) -> dict:
    """A-HETERO-MODE：异质集成模场失配耦合效率 η。

    求解器：两端 TE0 模场（`te0_neff_analytic`）+ 重叠积分（`abrupt_overlap`）；
    独立参照：换更细横向网格重算（`dx` 收敛，判断结果不依赖离散档位）。
    """
    from lda_solver.eme_taper import abrupt_overlap, te0_neff_analytic
    w1, w2 = float(geom["w1_um"]), float(geom["w2_um"])
    wl, n_clad = float(geom["wl_um"]), 1.44
    n2 = float(geom["n2"])
    ne2 = float(te0_neff_analytic(w2, wl, n2, n_clad))
    eta = float(abrupt_overlap(w1, w2, wl, ne2, n_clad, dx=0.02))
    eta_fine = float(abrupt_overlap(w1, w2, wl, ne2, n_clad, dx=0.01))
    return {
        "value": eta, "independent_ref": eta_fine,
        "solver": "eme_taper.te0_neff_analytic + abrupt_overlap(dx=0.02)",
        "ref_name": "abrupt_overlap(dx=0.01)（同链更细网格，判离散档位无关性）",
        "criteria": {
            "eta_in_physical_range": 0.0 < eta < 1.0,
            "eta_strictly_below_one": (1.0 - eta) > 1e-3,
            "dx_independent_within_tol": abs(eta - eta_fine) <= tol,
        },
    }


#: 题目 id → 判分器（无 ⇒ unscorable，必须附理由）
SCORERS = {
    "A-TAPER-FAST": {
        "fn": _score_taper_fast,
        "traps": [
            ("绝热极限高估：T=1.0（忽略非绝热损耗）", lambda g, t: 1.0),
            ("严重低估：T=0.5（跌破突变结下界）", lambda g, t: 0.5),
        ],
    },
    "A-HETERO-MODE": {
        "fn": _score_hetero_mode,
        "traps": [
            ("忽略模场失配：η=1.0", lambda g, t: 1.0),
            ("非物理越界：η=1.5", lambda g, t: 1.5),
        ],
    },
}

#: 不可判分题的理由（必须指出「缺什么」，不得只写「不做」）
UNSCORABLE_REASONS = {
    "A-BEND-R2": ("本仓**无**「弯曲辐射损耗 vs 半径 R」的物理求解器：`bend_mode.py` 只"
                  "输出群折射率 n_g（metric 不匹配，题要 bend_loss_dB）；`lda_l1.protocol."
                  "route_net` 的 `bend_loss_db` 是**布线几何模型**（按拐角计数×固定系数），"
                  "非器件辐射物理。缺项：**共形变换/辐射边界下的弯曲模损耗求解器**。"),
    "A-CROSS-TIGHT": ("`lda_design.loss_engines.engine_crossing` 是**唯象拟合式**"
                      "（XT=−(28+4·L_taper/w)，标定自「公开优化 crossing 典型量级」），"
                      "且签名只读 `w_core_um`/`L_taper_um`、**完全不读 `gap_um`** ⇒ "
                      "无法响应本题核心变量 gap=0.1µm（紧间隙串扰的唯一驱动量）。"
                      "缺项：**读 gap 的全波 crossing 求解器**（或 gap 参数化的实测语料锚）。"),
}


def _judge(criteria: dict) -> tuple:
    """判分：全部判据通过 ⇒ PASS。返回 (passed, 失败判据名列表)。"""
    bad = [k for k, v in criteria.items() if not v]
    return (not bad), bad


def _run_one(bid: str, geom: dict, tol: float) -> dict:
    """判分单题（含反向测试）。"""
    spec = SCORERS[bid]
    res = spec["fn"](geom, tol)
    passed, bad = _judge(res["criteria"])

    # 反向测试：把「值」换成陷阱答案，判据必须至少有一条翻红
    trap_rows = []
    for label, mk in spec["traps"]:
        fake = dict(res["criteria"])
        v = mk(geom, tol)
        # 用陷阱值重算三条判据（保持与正向同构）
        if bid == "A-TAPER-FAST":
            lower = res["independent_ref"]
            fake = {
                "T_ge_lower_bound": v >= lower - 1e-12,
                "T_strictly_below_one": (1.0 - v) > 1e-4,
                "T_within_tol_of_lower": abs(v - lower) <= tol,
            }
        else:
            fine = res["independent_ref"]
            fake = {
                "eta_in_physical_range": 0.0 < v < 1.0,
                "eta_strictly_below_one": (1.0 - v) > 1e-3,
                "dx_independent_within_tol": abs(v - fine) <= tol,
            }
        ok_fake, bad_fake = _judge(fake)
        trap_rows.append({"trap": label, "injected": v,
                          "passed": ok_fake, "failed_criteria": bad_fake})
    return {
        "id": bid, "disposition": "scored", "tol": tol,
        "solver": res["solver"], "ref_name": res["ref_name"],
        "value": res["value"], "independent_ref": res["independent_ref"],
        "criteria": res["criteria"], "passed": passed, "failed_criteria": bad,
        "traps": trap_rows,
        "traps_all_rejected": all(not t["passed"] for t in trap_rows),
    }


def main() -> int:
    t0 = time.time()
    raw = json.load(open(_SEED, encoding="utf-8"))
    problems = raw.get("adversarial", [])
    print("=== 对抗题自动判分（VMM Tier-4 方向）===")
    print("  入库对抗题 %d 道" % len(problems))

    results = []
    for b in problems:
        bid = b["id"]
        tol = float(b.get("tol"))
        geom = b.get("geometry", {})
        if bid in SCORERS:
            results.append(_run_one(bid, geom, tol))
        elif bid in UNSCORABLE_REASONS:
            results.append({"id": bid, "disposition": "unscorable", "tol": tol,
                            "metric": b.get("target_metric"),
                            "reason": UNSCORABLE_REASONS[bid]})
        else:
            # 🔴 禁静默跳过：新入库的题必须显式落到三态之一
            results.append({"id": bid, "disposition": "UNHANDLED", "tol": tol,
                            "reason": "新题未登记 disposition"})

    # ① 题数一致
    check("① 全部入库对抗题都已读取（%d 道）" % len(problems),
          len(results) == len(problems) and len(problems) > 0,
          "读取 %d / 题数 %d" % (len(results), len(problems)))

    # ② disposition 三态完备、无 UNHANDLED（禁静默跳过）
    unhandled = [r["id"] for r in results if r["disposition"] not in DISPOSITIONS]
    check("② 每题 disposition 都已判定（无静默跳过）", not unhandled,
          "未处理 %s" % unhandled)

    # ③ 可判分题：真跑求解器 + 判据齐全 + 判分 PASS
    scored = [r for r in results if r["disposition"] == "scored"]
    check("③ 可判分题 ≥1 且**真跑求解器**得出值（非占位）", len(scored) >= 1,
          "可判分 %d 道" % len(scored))
    for r in scored:
        check("③ %s 判分 PASS（%s）" % (r["id"], r["solver"].split("（")[0]),
              r["passed"] and len(r["criteria"]) >= 3,
              "value=%.6f ref=%.6f 失败判据=%s"
              % (r["value"], r["independent_ref"], r["failed_criteria"]))

    # ④ 🔴 反向自证：错答（陷阱答案）**必不通过**
    for r in scored:
        check("④ %s 反向：%d 个陷阱答案**全部**被拒（错答必不通过）"
              % (r["id"], len(r["traps"])),
              r["traps_all_rejected"] and len(r["traps"]) >= 2,
              "; ".join("%s→%s" % (t["trap"][:18], t["failed_criteria"])
                        for t in r["traps"]))

    # ⑤ 不可判分题必须带回溯理由 + 「缺什么」
    unscored = [r for r in results if r["disposition"] == "unscorable"]
    for r in unscored:
        check("⑤ %s 不可判分理由含「缺项」指认" % r["id"],
              "缺项" in r["reason"], r["reason"][:60] + "…")

    # ⑥ 判分链零 LLM / 零网络（扫登记文本，防判据扫到自己）
    payload = json.dumps(results, ensure_ascii=False).lower()
    hit = [t for t in ("openai", "anthropic", "chatgpt", "requests.", "http://")
           if t in payload]
    check("⑥ 判分链零 LLM / 零网络引用", not hit, "命中 %s" % hit)

    elapsed = time.time() - t0
    report = {
        "p3_t33": "adversarial auto-scoring",
        "problems_total": len(problems),
        "scored": len(scored), "unscorable": len(unscored),
        "results": results, "elapsed_s": round(elapsed, 2),
    }
    out_dir = os.path.join(_HERE, "reports")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "adversarial_scoring_report.json")
    from lda_harness import deterministic as _det
    _det.write_json(out_path, report)
    print("\n报告：%s" % out_path)

    print("\n=== 判分一览（可判分 %d / 不可判分 %d / 共 %d）==="
          % (len(scored), len(unscored), len(results)))
    for r in results:
        if r["disposition"] == "scored":
            print("  ✅ %-16s %-10s value=%.6f  ref=%.6f  traps=%d/%d 拒绝"
                  % (r["id"], "scored", r["value"], r["independent_ref"],
                     sum(1 for t in r["traps"] if not t["passed"]), len(r["traps"])))
        else:
            print("  ⛔ %-16s %-10s %s" % (r["id"], r["disposition"],
                                          r["reason"][:56] + "…"))
    print("\nP3-T3.3 对抗题自动判分 smoke：%s  (%.2fs)"
          % ("ALL GREEN" if _FAIL == 0 else "HAS FAILURE", elapsed))
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
