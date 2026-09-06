"""N-5 导购二期（D-2=A · 无 LLM 可降级版）。

设计红线（与全项目「LLM 不进判决路径 / 数字可溯源」一致）：
- 锚定导购：推荐结果一律来自对货架 facets 的**实跑匹配**，不凭空生成。
- 数字一律从货架数据渲染：价格来自 price_of 实付价、规格来自 item.specs，
  严禁模板或 LLM 杜撰任何规格数字。
- LLM 角色（未来扩展，当前未启用，见 build_reason 中的扩展点注释）：
  仅做「需求→结构化查询」的解析与「解释文案」的润色；任何 LLM 输出在渲染前
  必须与货架实跑数据核对，且禁止输出规格数字。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from lda_l2.innovation_market import (
    SHELF_TRACKS,
    SHELF_APP_DOMAINS,
    ShelfItem,
)

# —— 赛道 / 应用域 / 价档 关键词别名（中文 + 英文缩写），把自然语言需求映射到结构化查询 ——
_TRACK_KEYWORDS: Dict[str, List[str]] = {
    "datacom": ["数通", "电信", "收发", "光模块", "数据中心", "通信", "相干", "长距",
                "接入", "pon", "roadm", "交换", "路由", "wdm", "波分", "transceiver",
                "coherent", "数据中心互联", "光互连", "互连"],
    "sensing": ["传感", "测量", "传感器", "生化", "激光雷达", "lidar", "微波", "雷达",
                "惯性", "医疗", "成像", "光谱", "气体", "温度", "折射", "陀螺", "加速度"],
    "quantum": ["量子", "quantum", "qkd", "保密", "量子计算", "读出", "比特", "保真", "qubit"],
    "cpo": ["cpo", "共封装", "chiplet", "中介层", "光引擎", "ocs", "光交换", "光计算",
            "互连", "i/o", "io"],
    "component": ["器件", "光源", "频梳", "调制", "开关", "无源", "耦合", "偏振", "光纤",
                  "滤波", "复用", "波导", "分束", "环形器", "探测器", "光电"],
}
_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "transceiver": ["收发引擎", "收发模块", "transceiver"],
    "wdm_roadm": ["wdm", "roadm", "波分", "波分复用", "复用器"],
    "pon": ["pon", "接入网", "无源光网络"],
    "coherent": ["相干", "长距"],
    "switching": ["光交换", "路由", "switch"],
    "biochem": ["生化", "生物", "化学传感"],
    "lidar": ["激光雷达", "lidar", "自动驾驶"],
    "microwave": ["微波光子", "微波雷达"],
    "inertial": ["惯性", "陀螺", "加速度"],
    "medical": ["医疗", "成像", "健康"],
    "spectrum": ["光谱", "spectrometer"],
    "qc_readout": ["量子计算读出", "读出链", "保真度"],
    "qkd": ["量子保密", "量子密钥", "qkd"],
    "cpo_engine": ["cpo光引擎", "共封装光引擎"],
    "chiplet": ["chiplet", "中介层", "小芯片"],
    "optical_switch": ["ocs", "光电路交换"],
    "optical_compute": ["光计算", "光子计算"],
    "light_source": ["光源", "频梳", "激光器", "激光源"],
    "modulation": ["调制", "调制器"],
    "passive": ["无源", "耦合器", "分束器"],
    "polarization": ["偏振"],
    "fiber_io": ["光纤接口", "光纤", "扇出"],
    "filtering": ["滤波", "滤波器"],
    "multiplexing": ["复用", "多维度"],
}
_TIER_KEYWORDS: Dict[str, List[str]] = {
    "basic": ["入门", "基础", "便宜", "低预算", "基础版", "¥599", "599"],
    "standard": ["标准", "通用", "常用", "主流"],
    "premium": ["高端", "高级", "旗舰", "专业", "¥4999", "4999"],
    "consult": ["咨询", "定制", "专属", "人工"],
}

# 应用域标签扁平化（key 全局唯一，与 facets 一致）
_LABELS_DOMAIN: Dict[str, str] = {
    d: lab for doms in SHELF_APP_DOMAINS.values() for d, lab in doms.items()
}

# 停用词（2 字中文功能词 + 价格/否定信号词，避免变成噪声关键词）
_STOP = set(
    "我要 想做 需要 求一个 这款 那个 有什么 推荐 帮选 选个 选一 看看 想做 做用于 针对 应用"
    "于 价格 预算 价位 以下 不非 不要 排除 别无 无需 想要 也和 并与 的了的 在是 到有 及你"
    "我们就 他们 它这 那哪 哪个 哪几 种可以 怎么 如何 什么 哪种 搞个 做个 上中 下大 中小"
    "高高低 内外 部前 后面 做一 一些 这种 那种 相关 之类 等等 方面 一个 用来 应该 能够"
    "希望 打算 准备 想找 找一 适合 合适 比较 比较 想要 帮我 给我 帮我 一下 进行 实现 设计"
    "方案 解决 需求 请问 请问 一个 一种".split()
)
# 价格信号词：已被 price_max 单独解析，禁止再当关键词
_PRICE_WORDS = set("预算 价格 价位 元 块 万 元以下 以内 不超过 低于 便宜 贵 高价 低价".split())


@dataclass
class Query:
    tracks: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)
    tiers: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    price_max: Optional[float] = None
    negations: List[str] = field(default_factory=list)

    def empty(self) -> bool:
        return not (self.tracks or self.domains or self.tiers
                    or self.keywords or self.price_max)


def _extract_keywords(text: str, q: "Query") -> List[str]:
    """从自由文本抽取 2~4 字中文 token / 英文数字词，剔除已识别别名、停用词与价格信号词。"""
    alias_flat = set()
    for d in (_TRACK_KEYWORDS, _DOMAIN_KEYWORDS, _TIER_KEYWORDS):
        for ws in d.values():
            for w in ws:
                alias_flat.add(w.lower())
    tokens = re.findall(r"[a-z0-9]+|[一-龥]{2,4}", (text or "").lower())
    out, seen = [], set()
    for tok in tokens:
        if tok in alias_flat or tok in _STOP or tok in _PRICE_WORDS:
            continue
        if len(tok) < 2:
            continue
        # 以停用词开头的切片（如「我要做一」以「我要」开头）视为句子填充词，跳过
        if any(tok.startswith(s) for s in _STOP if len(s) >= 2):
            continue
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out[:8]


def parse_query(text: str) -> Query:
    """把自然语言需求解析为结构化查询（确定性，零密钥）。"""
    q = Query()
    t = (text or "").lower()

    # 否定词：记下来但不阻断主匹配（v1 仅记录，暂不影响打分）
    neg_markers = ["不", "非", "不要", "排除", "别", "无需", "不想要", "没有"]
    if any(m in text for m in neg_markers):
        q.negations.append("neg")

    for track, kws in _TRACK_KEYWORDS.items():
        if any(k.lower() in t for k in kws):
            if track not in q.tracks:
                q.tracks.append(track)
    for dom, kws in _DOMAIN_KEYWORDS.items():
        if any(k.lower() in t for k in kws):
            if dom not in q.domains:
                q.domains.append(dom)
    for tier, kws in _TIER_KEYWORDS.items():
        if any(k.lower() in t for k in kws):
            if tier not in q.tiers:
                q.tiers.append(tier)

    # 预算上限：必须带价格信号词，避免误把 "800G" 当成 ¥800
    price_signal = re.search(
        r"(?:预算|¥|[\$￥]|万|元|块|cny|rmb|不超过|低于|以内|≤|<=|价格|价位)", t)
    if price_signal:
        m = re.search(r"(\d+(?:\.\d+)?)\s*万", t)
        if m:
            q.price_max = float(m.group(1)) * 10000
        else:
            m = re.search(r"(?:¥|[\$￥]|预算|价格|不超过|低于|以内)\D*?(\d{3,7})\b", t)
            if m:
                q.price_max = float(m.group(1))
            else:
                m = re.search(r"(\d{3,7})\s*(?:元|块|cny|rmb)", t)
                if m:
                    q.price_max = float(m.group(1))

    q.keywords = _extract_keywords(text, q)
    return q


def _fmt_price(v: Optional[float]) -> str:
    if v is None:
        return "—"
    if float(v).is_integer():
        return str(int(v))
    return ("%.2f" % v).rstrip("0").rstrip(".")


def score_shelf(item: ShelfItem, q: Query,
                price_of: Callable[[str], Optional[float]],
                tier_of: Callable[[str], str]) -> Optional[Dict[str, Any]]:
    """对单条货架实跑匹配打分；无命中返回 None。"""
    score = 0
    matched: List[str] = []
    reasons: List[str] = []

    title_l = (item.title or "").lower()
    body_l = " ".join([
        item.target_app or "",
        " ".join(item.features or []),
        " ".join(item.applications or []),
        " ".join("%s %s" % (k, v) for k, v in (item.specs or {}).items()),
        item.signal_ref or "",
        " ".join(item.composition or []),
    ]).lower()

    if q.tracks and item.track in q.tracks:
        score += 4
        matched.append("track")
        reasons.append("匹配赛道【%s】" % SHELF_TRACKS.get(item.track, item.track))
    if q.domains and item.app_domain in q.domains:
        score += 3
        matched.append("domain")
        reasons.append("命中应用域【%s】" % _LABELS_DOMAIN.get(item.app_domain, item.app_domain))

    tier = tier_of(item.id)
    if q.tiers and tier in q.tiers:
        score += 2
        matched.append("tier")
        reasons.append("符合价档【%s】" % tier)

    for kw in q.keywords:
        k = kw.lower()
        if k in title_l:
            score += 2
            matched.append("kw_title")
            reasons.append("标题含「%s」" % kw)
        elif k in body_l:
            score += 1
            matched.append("kw_body")
            reasons.append("用途/特点/规格含「%s」" % kw)

    if not score:
        return None

    price = price_of(item.id)
    if q.price_max is not None and price is not None and price > q.price_max:
        score -= 100
        matched.append("over_budget")
        reasons.append("标准价 ¥%s 超出预算 ¥%s"
                       % (_fmt_price(price), _fmt_price(q.price_max)))

    return {"score": score, "matched": matched, "reasons": reasons,
            "price": price, "tier": tier}


def build_reason(item: ShelfItem, sc: Dict[str, Any], q: Query) -> str:
    """组装中文解释。**数字只来自货架数据**：价格来自 price_of、规格来自 item.specs。

    扩展点（未来接 LLM）：若启用 llm_explain，可在此用 LLM 仅重排/润色 reasons 文案，
    但所有 ¥ 与规格数值必须仍取自下方实跑字段，禁止让 LLM 生成新数字。
    """
    # 正文关键词命中（kw_body）回显具体 4 字碎切片（如「子保密通」）不专业，
    # 改为聚合为一条中性表述，仅标题命中（kw_title）保留具体词条（信号强、可读）。
    kw_body_hits = sum(1 for m in sc["matched"] if m == "kw_body")
    reasons = [r for r in sc["reasons"] if not r.startswith("用途/特点/规格含")]
    if kw_body_hits:
        reasons.append("用途/特点/规格与需求相关")
    parts = list(reasons)
    price = sc.get("price")
    if "over_budget" not in sc["matched"] and price is not None:
        parts.append("标准价 ¥%s" % _fmt_price(price))
    # 真实规格数字来自货架 specs 字段（字符串，已含单位如 ≤3dB）
    if item.specs:
        spec_txt = "、".join("%s %s" % (k, v) for k, v in item.specs.items())
        parts.append("关键规格：" + spec_txt)
    head = "为你匹配到该货架" if sc["score"] >= 4 else "可能相关"
    return head + "：" + "；".join(parts) + "。"


def recommend(text: str, items: List[ShelfItem], *,
              price_of: Optional[Callable[[str], Optional[float]]] = None,
              tier_of: Optional[Callable[[str], str]] = None,
              topn: int = 8) -> Dict[str, Any]:
    """无 LLM 确定性推荐：解析需求 → 逐货架 facets 实跑匹配 → 排序返回。

    返回结构含 query 解析、结果列表（reason 解释 + 来自数据的价格与规格）。
    """
    from lda_webui.shelf_pricing import tier_of as _tier_of

    if tier_of is None:
        tier_of = _tier_of
    if price_of is None:
        # 兜底：无价格函数时用 None（仅影响超预算判断）
        price_of = lambda sid: None  # noqa: E731

    q = parse_query(text)
    results: List[Dict[str, Any]] = []
    for item in items:
        sc = score_shelf(item, q, price_of, tier_of)
        if sc is None:
            continue
        results.append({
            "id": item.id,
            "title": item.title,
            "track": item.track,
            "app_domain": item.app_domain,
            "track_label": SHELF_TRACKS.get(item.track, item.track),
            "app_domain_label": _LABELS_DOMAIN.get(item.app_domain, item.app_domain),
            "score": sc["score"],
            "matched_fields": sc["matched"],
            "reason": build_reason(item, sc, q),
            "price_cny": sc["price"],
            "specs": dict(item.specs or {}),
            "over_budget": "over_budget" in sc["matched"],
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    results = results[:topn]
    return {
        "query": {
            "tracks": q.tracks,
            "domains": q.domains,
            "tiers": q.tiers,
            "keywords": q.keywords,
            "price_max": q.price_max,
        },
        "count": len(results),
        "results": results,
        "used_llm": False,
    }
