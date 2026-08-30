"""创新超市 smoke（v0.8.34 · 创新超市 · 前瞻预研货架红线下护栏）。

三守护（与全局红线一致）：
  ① 每条组合可分解到已锚定基元（composition 全部 ∈ GOLDEN_IDS）——禁止含未锚定基元；
  ② 每条结构可行 + 系统预算不破（design_pipeline 复用 system_type 已验证闭环）；
  ③ honest_tier 必填且 = "前瞻预研"——CI 绝不输出"已流片验证"字样。

运行：python run_innovation_market_smoke.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lda_l2.innovation_market import (
    evaluate_all, to_markdown, save_library_json, DEFAULT_SHELF,
    HONEST_TIER, HONEST_BANNER,
)
from lda_l2.golden_product_benchmarks import DEFAULT_BENCHMARKS
from lda_l2.ship_package import OPEN_SHELVES

# 仅 GP-*（器件级基元）构成锚集；GC-*（整芯片级）为级联聚合条目，不参与基元锚集。
GOLDEN_IDS = {b.product_id for b in DEFAULT_BENCHMARKS if hasattr(b, "product_id")}
SHELF_IDS = {s.id for s in DEFAULT_SHELF}

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
    print("Phase 2 创新超市 smoke（前瞻预研货架 · 红线下护栏）")
    print(HONEST_BANNER)
    results = evaluate_all()
    n_total = len(results)

    # 回归护栏：白名单 ⊆ 货架集（防 v0.8.49 漏将新货架加入 OPEN_SHELVES 致 open=False/403）
    missing = sorted(s for s in OPEN_SHELVES if s not in SHELF_IDS)
    check("白名单 OPEN_SHELVES ⊆ DEFAULT_SHELF（无孤儿 id）",
          not missing,
          "" if not missing else f"孤儿 {missing}")
    n_ok = sum(1 for r in results if r.get("feasible") and not r.get("error"))

    for r in results:
        sid = r["id"]
        err = r.get("error")
        # 守护①：composition 全部已锚定
        comp = r.get("composition", [])
        unanchored = [c for c in comp if c not in GOLDEN_IDS]
        check(f"{sid}：组合可分解到已锚定基元（{', '.join(comp)}）",
              not unanchored,
              "" if not unanchored else f"未锚定 {unanchored}")
        # 守护②：结构可行 + 预算不破（无 error 且 feasible）
        check(f"{sid}：结构可行 + 系统预算不破（可上架）",
              (err is None) and bool(r.get("feasible")),
              r.get("summary", err or ""))
        # 守护③：honest_tier 必填 = 前瞻预研
        check(f"{sid}：honest_tier = 前瞻预研（CI 不宣称流片验证）",
              r.get("honest_tier") == HONEST_TIER,
              r.get("honest_tier", ""))

    # 库落盘 + 目录生成（B 生态播种素材）
    lib = save_library_json()
    report = to_markdown(results)
    out_md = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                          "docs", "innovation_market.md")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n库已落盘: {lib}")
    print(f"目录已写: {out_md}")
    print(f"汇总: {n_ok}/{n_total} 货架通过结构可行检查")

    # ⑥ 三档定价护栏（v0.9.1 · D2）：新增货架必须归档价档，且不得出现野价
    try:
        from lda_webui.shelf_pricing import (PRICE_TIERS, TIER_BASIC,
                                             TIER_CONSULT, TIER_PREMIUM,
                                             TIER_STANDARD, build_price_map)
        pm = build_price_map()
        tiered = set(TIER_BASIC) | set(TIER_STANDARD) | set(TIER_PREMIUM) | set(TIER_CONSULT)
        check("定价覆盖：全部 58 货架均已归档价档（无漏定价）",
              set(pm) == SHELF_IDS,
              f"已定价={len(pm)} 货架={len(SHELF_IDS)} 差={sorted(SHELF_IDS ^ set(pm))[:5]}")
        check("定价无孤儿 id（定价表不含不存在的货架）",
              not (set(pm) - SHELF_IDS),
              f"多余={sorted(set(pm) - SHELF_IDS)[:5]}")
        allowed = set(PRICE_TIERS.values())
        bad_price = {k: v for k, v in pm.items() if v not in allowed}
        check("价格只能取三档（599 / 1999 / 4999）",
              not bad_price, f"野价={list(bad_price.items())[:3]}")
        check("档位分组无重叠（一个货架只归一档）",
              len(tiered) == len(TIER_BASIC) + len(TIER_STANDARD)
              + len(TIER_PREMIUM) + len(TIER_CONSULT),
              f"并集={len(tiered)} 分项和={len(TIER_BASIC) + len(TIER_STANDARD) + len(TIER_PREMIUM) + len(TIER_CONSULT)}")
        # 出口管制红线：量子咨询制货架不得进开放下载白名单
        leaked = sorted(set(TIER_CONSULT) & set(OPEN_SHELVES))
        check("出口管制红线：量子咨询制货架不在开放下载白名单",
              not leaked, f"越界={leaked}")
        # 定价生效性：store.price_of 走分档表（非 DEFAULT 兜底）
        from lda_webui import store
        p_basic = store.price_of(TIER_BASIC[0], None)
        p_prem = store.price_of(TIER_PREMIUM[0], None)
        check("定价生效：基础档 599 / 高端档 4999（经 store.price_of）",
              p_basic == PRICE_TIERS["basic"] and p_prem == PRICE_TIERS["premium"],
              f"{TIER_BASIC[0]}={p_basic} {TIER_PREMIUM[0]}={p_prem}")
        p_aca = store.price_of(TIER_PREMIUM[0], "academic")
        check("身份折扣叠加正确（学术 6 折 = 2999.40）",
              abs(p_aca - PRICE_TIERS["premium"] * 0.6) < 0.01, f"{p_aca}")
    except ImportError as e:  # 定价模块缺失 → 明确 FAIL（不允许静默跳过）
        check("三档定价模块可导入", False, f"ImportError: {e}")

    if n_ok < n_total or _FAIL:
        print("FAIL: 存在未达标货架或护栏破")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
