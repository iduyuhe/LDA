"""LDA 实证语料「可公开溯源」分级与门禁（D-63 · 实证锚来源边界）。

来源边界（用户 2026-09-01 拍板）：
    仅限 ①公开论文 ②公开 datasheet ③公开测量数据集；且必须可公开溯源。

「可公开溯源」在本模块中被定义为**机器可判**的硬标准，而非主观描述——
因为主观描述（如 "published data"、"文献量级"）无法被第三方复验，
一旦进入判决路径就会把「实证锚」稀释成「自证桩」，直接违反验证红线。

三级分类：
    A 级 · 可公开溯源 —— citation 含可解析定位符（DOI / arXiv / 公开 URL）。
        第三方可凭该定位符独立取回原始出处 → **可作 golden 进判决路径**。
    B 级 · 量级参考   —— 有 citation 文本但无定位符，无法独立复验。
        **禁止作 golden 进判决**（只能作参考/展示），须补溯源后升级。
    X 级 · 无来源     —— citation 缺失 → 直接拒收（既有门禁已在做）。

红线守住：本模块只做**确定性字符串解析**，不涉及任何语义判断，
LLM / AI 永不参与溯源分级。

许可边界：仅定位与分级，不抓取、不下载任何外部内容（无网络 I/O）。
"""
import re

__all__ = [
    "TIER_A", "TIER_B", "TIER_X",
    "SOURCE_CLASSES",
    "extract_locators",
    "classify_citation",
    "is_traceable",
    "audit_items",
]

TIER_A = "A"   # 可公开溯源（DOI / arXiv / 公开 URL）→ 可进判决
TIER_B = "B"   # 量级参考（无定位符）→ 禁止进判决
TIER_X = "X"   # 无来源 → 拒收

SOURCE_CLASSES = ("paper", "datasheet", "dataset", "pdk_public", "other")

# DOI：10.<注册商前缀>/<后缀>，后缀允许常见标点与字母数字
_RE_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>,;)\]]+)", re.I)
# arXiv：arXiv:2601.01234[vN] 或 arxiv.org/abs/2601.01234
_RE_ARXIV = re.compile(r"(?:arxiv\s*:\s*)?(\d{4}\.\d{4,5})(?:v(\d+))?", re.I)
_RE_ARXIV_URL = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", re.I)
_RE_URL = re.compile(r"https?://[^\s\"'<>,;)\]]+", re.I)

# 非公开主机：内网 / 回环 / 私有地址段 —— 即便形似 URL 也不构成「公开」
_PRIVATE_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "::1", "10.", "192.168.", "172.16.")


def _is_public_url(url: str) -> bool:
    """URL 是否指向公开可达位置（排除内网/回环/私有段）。"""
    u = (url or "").strip().lower()
    if not u:
        return False
    # 剥离协议后检查主机前缀
    host = u.split("//", 1)[-1].split("/", 1)[0].split("@")[-1].split(":")[0]
    return not any(host.startswith(p) for p in _PRIVATE_HOSTS)


def extract_locators(citation: str, source_url: str = "") -> dict:
    """从 citation（可选 source_url）中抽取可解析溯源定位符。

    返回 {"doi": ..., "arxiv": ..., "url": ..., "public_url": ...}，
    未命中项为 None。纯字符串解析、无网络 I/O。
    """
    text = f"{citation or ''} {source_url or ''}"
    dois = [d.rstrip(".,;") for d in _RE_DOI.findall(text)]
    arxiv = _RE_ARXIV_URL.findall(text) or [
        m.group(1) for m in _RE_ARXIV.finditer(text)
        if not _RE_ARXIV_URL.search(text)
    ]
    urls = [u.rstrip(".,;)") for u in _RE_URL.findall(text)]

    # arXiv 优先走显式 URL 命中，其次裸编号（需形如 NNNN.NNNNN 且不在纯数字上下文中）
    ax = arxiv[0] if arxiv else None
    pub_urls = [u for u in urls if _is_public_url(u)]

    return {
        "doi": dois[0] if dois else None,
        "arxiv": ax,
        "url": urls[0] if urls else None,
        "public_url": pub_urls[0] if pub_urls else None,
    }


def classify_citation(citation: str, source_url: str = "") -> dict:
    """给一条语料的来源定级（A/B/X）+ 来源类别 + 定位符。

    判定优先级：DOI > arXiv > 公开 URL > 有文本但无定位符(B) > 空(X)。
    """
    cit = (citation or "").strip()
    loc = extract_locators(cit, source_url)

    if loc["doi"]:
        tier, locator, kind = TIER_A, loc["doi"], "doi"
        cls = "paper"
    elif loc["arxiv"]:
        tier, locator, kind = TIER_A, loc["arxiv"], "arxiv"
        cls = "paper"
    elif loc["public_url"]:
        tier, locator, kind = TIER_A, loc["public_url"], "url"
        u = loc["public_url"].lower()
        # 仅凭主机特征粗分来源类别（不做内容抓取）
        if any(k in u for k in ("doi.org", "arxiv.org", "opg.optica",
                                "ieeexplore", "nature.com", "spie.org",
                                "researchgate", "pubmed")):
            cls = "paper"
        elif any(k in u for k in (".pdf", "datasheet", "documentation")):
            cls = "datasheet"
        else:
            cls = "other"
    elif cit:
        tier, locator, kind, cls = TIER_B, None, "none", "other"
    else:
        tier, locator, kind, cls = TIER_X, None, "none", "other"

    return {
        "tier": tier,
        "source_class": cls,
        "locator_kind": kind,
        "locator": locator,
        "traceable": tier == TIER_A,
    }


def is_traceable(citation: str, source_url: str = "") -> bool:
    """是否达到「可公开溯源」（A 级）——可作 golden 进判决路径。"""
    return classify_citation(citation, source_url)["tier"] == TIER_A


def audit_items(items) -> dict:
    """对一批语料做溯源审计，返回分级统计与不合格清单。

    items: 可迭代，元素需有 .citation（可选 .source_url / .id / .metric）。
    """
    by_tier = {TIER_A: 0, TIER_B: 0, TIER_X: 0}
    untraceable, traceable = [], []
    for m in items:
        cit = getattr(m, "citation", "")
        surl = getattr(m, "source_url", "") or ""
        info = classify_citation(cit, surl)
        by_tier[info["tier"]] = by_tier.get(info["tier"], 0) + 1
        rec = {
            "id": getattr(m, "id", "?"),
            "metric": getattr(m, "metric", ""),
            "device": getattr(m, "device", ""),
            "citation": cit,
            "tier": info["tier"],
            "source_class": info["source_class"],
            "locator_kind": info["locator_kind"],
            "locator": info["locator"],
        }
        (traceable if info["traceable"] else untraceable).append(rec)
    total = sum(by_tier.values())
    return {
        "total": total,
        "by_tier": by_tier,
        "traceable_ratio": (by_tier[TIER_A] / total) if total else 0.0,
        "traceable": traceable,
        "untraceable": untraceable,
    }
