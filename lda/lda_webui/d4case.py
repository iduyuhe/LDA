# -*- coding: utf-8 -*-
"""LDA · D4 交付扩面案例卡（W5-1 · ecore / 量子侧 · 只读案例卡）。

============================================================================
案例卡体例（与 qchip/schip/pchip/ecore/accel 同族）：
  `*_case.py` 事实源 → 只读 GET 路由（不进 HEAVY_POST_PATHS）→ 前端 sec-* 面板
  → API 参考（gen_api_reference 单一真源）→ 案例卡门禁（run_*_case_smoke.py）。

本卡守的是「**用户拿得走东西**」：W2 已把光子侧「设计→GDS→签核→下载」实测贯通，
本卡把电子（ecore 交叉阵列）、超导量子（transmon 阵列）与光量子 LOQC（可编程 MZI
网格）三条**既有真产线**一并对外开放——它们此前各有 GDS/DRC/LVS，但**没有对外
交付通路**（残缺口 G-U 已随本轮收口）。

🔴 诚实边界（逐条登记，不粉饰）：
  - 层规为**公开工艺近似**设计规则（非 Foundry PDK 标定值）；
  - DRC 为 bbox 级几何近似（非多边形布尔运算）；
  - verdict 属**设计期签核**，**非实测签核 · 非流片结果**；
  - 不报 TOPS / TOPS-W / fJ/op（红线）· LLM 不进判决路径。
"""
from __future__ import annotations

from typing import Any, Dict

from lda_l2.ecore.layout import LAYOUT_DISCLOSURE

CASE_ID = "D4-DOMAIN-EXPANSION-v1"

_CARD_CACHE: Dict[tuple, Dict[str, Any]] = {}

CLAIM = ("电子侧、超导量子侧与光量子 LOQC 侧都能出**真 GDS** 并通过 DRC/LVS 双闸签核——"
         "且同一份交付物的 sha256 可确定性重建（设计→签核→下载 全链一致）")
IDENTITY = {
    "ecore": "电子计算核：NMOS 1T 交叉点单元阵列（DIFF/POLY/CONT/M1/VIA1/M2 层栈）"
             "→ 几何 DRC（bbox 级）+ 几何 LVS（并查集连通分量）→ GDSII",
    "quantum_sc": "超导 transmon 量子阵列（S3）：Al 膜层 + JJ + 地平面 + 读出/控制几何"
                  "→ DRC + LVS 签核 → GDSII",
    "loqc": "光量子 LOQC 可编程 MZI 网格（`lda_layout/mesh_pnr`）：Clements 矩形分解 → "
            "摆位 → 布线 → 输出相移 → 物理级联网表真算该酉 → GDS → 主权 DRC/LVS"
            "（n=2..16 实测双闸全 ACCEPT）",
    "photon": "光子侧（W2 已闭合，本卡仅作对照基线）：单器件设计包 → 芯片级 GDS + 双闸 → 下载",
    "route_note": "本卡只读消费 `lda_l2/d4_domains.py`（编排）+ `ecore/layout` + "
                  "`lda_qeda/sc_array` + `lda_layout/mesh_pnr`（几何/DRC/LVS 真实现），"
                  "**不重造任何一环**",
}
HONEST_NOTE = (
    "诚实边界：层规为公开工艺近似设计规则（非 Foundry PDK 标定值）；DRC 为 bbox 级几何近似；"
    "verdict 属设计期签核、非实测签核、非流片结果；不报 TOPS / TOPS-W / fJ/op；"
    "LLM 不进判决路径；零商业 EDA 依赖。"
)
MILESTONES = [
    {"id": "D1", "label": "光子侧 D4 先闭合（W2）",
     "detail": "/api/design_tapeout → /api/design_gds：芯片级 GDS + 双闸 ACCEPT + "
               "下载 sha256 与本地确定性重建逐位 MATCH（12/12 进程内 E2E）"},
    {"id": "D2", "label": "发现两条产线仍是断的",
     "detail": "ecore（E6）与超导量子（S3）早就有真 GDS + DRC/LVS，但**无对外交付通路**——"
               "用户拿不走 ⇒ 能力停在 D3"},
    {"id": "D3", "label": "统一编排收编既有链路",
     "detail": "`lda_l2/d4_domains.py`：build_domain(domain) 一次跑完「几何 → GDS → 双闸签核 → "
               "确定性 sha256」，只读消费既有模块，不重造几何/DRC/LVS"},
    {"id": "D4", "label": "双向确定性判据",
     "detail": "同参数两次 sha256 逐位一致；换参数（ecore n·m）sha256 必须不同——"
               "防「常数假确定性」"},
    {"id": "D5", "label": "布局：域完备反向判据 + 探针（逐域递增）",
     "detail": "注册域 ≡ 门禁显式表（新域必须进门禁）；探针覆盖：空 GDS / DRC 伪造 REJECT / "
               "塞入未接门禁的 ghost 域 / 字节面被换成另一份真字节 / 下载与报告取到不同 raw，"
               "逐域递增至 8 道，皆必红"},
    {"id": "D6", "label": "下载端点扩面（G-D 收口）",
     "detail": "`/api/d4_gds?domain=<域>` 出 `.gds`：octet-stream + attachment 附件名 + "
               "`X-LDA-GDS-Sha256` 响应头；**下载字节 sha256 与本卡登记的逐位 MATCH**——"
               "「设计→签核→下载」在新两域同样闭合。免登录 ⇒ 参数面带硬限幅"},
    {"id": "D7", "label": "光量子 LOQC 入编排（G-U 收口）",
     "detail": "第三域 `loqc`：Clements 矩形分解可编程 MZI 网格（n=2..16 实测全 ACCEPT）。"
               "编排层把 `mesh_pnr` 的扁报告（drc_pass 布尔 / lvs_full 嵌套）**归一化**成与"
               "另两域同形 ⇒ `_report_of`（双闸咬合唯一口）只认一种形状，不新增分支"},
    {"id": "D8", "label": "枚举型参数白名单（新类型限幅）",
     "detail": "`loqc.layout_mode ∈ {serpentine, grid2d}` 是**枚举**不是数值：白名单外/非字符串"
               "一律 400 + JSON，且报文点名『不在白名单』而非『不是数』——判据 ④c 咬住"
               "「枚举被静默丢弃」（吞了参数仍交 ACCEPT 真 GDS，属最难看的一类假绿）"},
]
FINDINGS = [
    {"title": "两条新产线都能出真 GDS 且双闸 ACCEPT",
     "detail": "ecore 交叉阵列与超导 transmon 阵列各产出字节级 GDS（HEADER 记录 "
               "`00 06 00 02`），DRC 零违规 + LVS ACCEPT"},
    {"title": "确定性不是口号，是双向断言",
     "detail": "只测「同参数同 sha」会被恒定 sha 骗过；本卡同时断言「换参数必变」"},
    {"title": "编排层必须是薄薄的一层",
     "detail": "编排只做去重/归一/确定性哈希，几何与签核仍各自真实现——"
               "否则编排一改，两条产线的物理结论跟着漂移"},
    {"title": "对外只给标量",
     "detail": "deliver_report 不含 GDS 字节面（前端/案例卡只消费标量），字节面仅由"
               "签名端点交付"},
    {"title": "交付闭环以 sha256 互证，而非口头承诺",
     "detail": "案例卡报告 sha256 与 `/api/d4_gds` 实际字节 sha256 逐位 MATCH —— "
               "两处由同一份字节面算出（响应头不重算、双闸咬合不拼两份），"
               "改任一侧都会红"},
    {"title": "免登录端点必须有参数硬限幅",
     "detail": "下载端点无鉴权 ⇒ `?domain=ecore&n=100000` 一个请求就能 OOM；"
               "DOMAIN_PARAM_LIMITS 逐键设上下限，越界/非数值/非登记键一律 400 + JSON，"
               "不静默丢弃、不返回空文件"},
    {"title": "第三条产线（光量子 LOQC）同口径收编，编排未长胖",
     "detail": "`mesh_pnr` 的回报形状与另两域不同（布尔 `drc_pass` / 嵌套 `lvs_full`）⇒ "
               "在**构建器里**做归一化，不在 `_report_of` 里开分支——"
               "双闸咬合仍只有一处实现，改逻辑不会漏改第二处"},
]
GAPS = [
    {"id": "G-U", "label": "光量子（LOQC）侧已纳入统一编排（本轮闭合）",
     "closed": True,
     "note": "`loqc` 域（Clements 可编程 MZI 网格）与另两域同口径：真 GDS + 双闸 ACCEPT + "
             "下载 sha256 互证；余下：LOQC 仅覆盖 Clements 网格，时间复用/2D 压实以外的"
             "LOQC 拓扑未纳入"},
    {"id": "G-D", "label": "下载端点已扩面到新两域（本轮闭合）",
     "closed": True,
     "note": "`/api/d4_gds?domain=<域>` 与光子侧同口径出 .gds，下载 sha256 ≡ 本卡登记值；"
             "余下：光子侧 kind 参数面仍各自一套（未走统一编排）"},
    {"id": "G-P", "label": "层规仍是公开工艺近似（不可闭合 · 已机器化锁死）",
     "closed": False,
     "note": "层规为**公开工艺近似**设计规则（非 Foundry PDK 标定值）：Foundry PDK 层规"
             "属外部依赖（D5），平台不沾 ⇒ 签核结论不可当流片放行依据。"
             "此条**物理不可闭合**：任何「已符合 Foundry 层规 / 已 PDK 标定 / 可流片放行」"
             "的表述都属假宣传 ⇒ 判据 ⑬ 锁死层规短口径单一真源，案例卡门禁 ③o 以肯定式"
             "禁词拦住对外物料（否定式『非 Foundry PDK』豁免）"},
    {"id": "G-B", "label": "DRC 为 bbox 级近似（保守方向 · 已实证锁死）",
     "closed": False,
     "note": "bbox 相交偏保守（宁可多报、零漏报）——真实多边形布尔运算不在本层。"
             "判据 ⑭ 以真实 `run_edrc` 算例实证两条性质：①真重叠必报（零漏报）"
             "②外接 bbox 重叠而本体不相交的 L 形布局仍报（多报 ⇒ 安全侧）"},
]


def _domain_facts() -> Dict[str, Any]:
    """逐域取交付报告（只读标量面）。"""
    from lda_l2 import d4_domains as dm

    facts = {}
    for d in dm.D4_DOMAINS:
        r = dm.deliver_report(d)
        facts[d] = {
            "label": r.get("label"),
            "verdict": r.get("verdict"),
            "n_bytes": r.get("gds", {}).get("n_bytes"),
            "sha256": r.get("gds", {}).get("sha256"),
            "n_elements": r.get("n_elements"),
            # 下载通路：与光子侧 `/api/design_tapeout` 报告的 gds.download_url 同口径，
            # 逐域唯一。门禁断言「下载字节 sha256 ≡ 本值」⇒ 交付闭环可证。
            "download_url": "/api/d4_gds?domain=%s" % d,
            "drc": r.get("drc"),
            "lvs": r.get("lvs"),
        }
    return facts


def case_card(use_cache: bool = True) -> Dict[str, Any]:
    """组装 D4 扩面案例卡（确定性现算 + 模块级缓存）。"""
    if use_cache and CASE_ID in _CARD_CACHE:
        return _CARD_CACHE[CASE_ID]

    facts = _domain_facts()
    card = {
        "endpoint": "/api/d4_demo",
        "case_id": CASE_ID,
        "claim": CLAIM,
        "identity": IDENTITY,
        "verdict": "DESIGN_BUDGET",
        "verdict_label": "设计期签核口径（几何 + DRC/LVS 双闸 · 确定性哈希 · 非流片实测）",
        "honest_note": HONEST_NOTE,
        "domains": facts,
        "domain_list": list(facts),
        # 🔴 派生自单一真源：LAYOUT_DISCLOSURE 的机器可读短口径键。
        #   此前三字段是**第二份手写副本**，且全仓无人消费 ⇒ 改坏也全绿（血案 #10 极端形态）。
        #   现结构上不可能与层规声明漂移；跨源一致由编排门禁判据 ⑬ 咬住。
        "disclosure": {
            "layer_rules": LAYOUT_DISCLOSURE["layer_rules_short"],
            "drc_precision": LAYOUT_DISCLOSURE["geom_short"],
            "signoff_class": LAYOUT_DISCLOSURE["signoff_short"],
            "redline": "不报 TOPS / TOPS-W / fJ/op",
        },
        "milestones": MILESTONES,
        "findings": FINDINGS,
        "gaps": GAPS,
        "gaps_total": len(GAPS),
    }
    if use_cache:
        _CARD_CACHE[CASE_ID] = card
    return card


def run_selfchecks(verbose: bool = False) -> bool:
    card = case_card()
    facts_ok = bool(card["domains"]) and all(
        v["verdict"] == "ACCEPT" and v["n_bytes"] > 0 for v in card["domains"].values())
    if verbose:
        print("[%s] 案例卡 %s · 域=%s · 全 ACCEPT=%s"
              % ("PASS" if facts_ok else "FAIL", CASE_ID,
                 ",".join(card["domain_list"]), facts_ok))
    return bool(facts_ok)


if __name__ == "__main__":
    print("D4 case self-check:", "PASS" if run_selfchecks(verbose=True) else "FAIL")
