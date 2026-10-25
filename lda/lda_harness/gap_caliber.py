"""跨卡缺口口径注册表（v0.9.300 · B 类跨卡口径冲突的统一裁决）。

## 为什么需要这个模块

同一个事实在不同案例卡里被记成了**不同状态**：

| 事实 | 记成边界声明的卡 | 记成未闭合（欠债）的卡 |
|---|---|---|
| 无流片 / 无低温实测 | `ecore G-A` · `pchip G-A` · `sensor G_no_tapeout` | `j2 J2-G-A` · `schip G-A` |
| 无 foundry PDK | `ecore G-B` · `ecore G-F` · `accel G-A4` · `oi G-OI4` | `j2 J2-G-B` · `schip G-B` |
| 须实验台的标定 | —（无对照） | `j2 J2-G-B` · `schip G-D` |
| 纠错码层不在本卡范围 | —（无对照） | `schip G-C` |

这不是「某个卡写错了」，而是**没有一条成文规则**，于是每张卡各自判。

## 判定规则（唯一依据，来自 `MEMORY.md` 的判定问句）

> 明天派一个工程师来做，**能做的**才是欠债；**本卡不做 / 项目不做**的是边界声明。

按此问句，上表四类**全都是边界声明**，因为它们要求的不是建模，而是
**流片预算 / 产线 / foundry deck（NDA）/ 低温实验台** —— 这些**任何案例卡都无法在本仓内完成**，
项目级红线本来就是「设计期签核 · 非流片实测」。

🔴 **这条规则不是为降数字而发明的**：v0.9.289–v0.9.299 十一次「闭合」全都是**建模活**
（IL 精度模型 / CMR 来源 / Werner 组合律 / 中继吞吐 / 源不可分辨性 / 热噪声 / 温漂预算 /
两个解码器 / 封装三项），**没有一条**依赖硬件。所以「须硬件的活 = 边界」与既有实践一致。

## 防「洗白」的三道机核（本模块的全部价值）

1. **同类必须同状态**：同一口径命中的所有缺口，状态必须等于该口径期望值。
   ⇒ 今天这样改完，明天任何卡再把「无流片」记成未闭合，`audit()` 立刻判红。
2. **`RECLASSIFIED` 逐条留痕**：这次因口径统一而从「未闭合」转出的每一条，
   必须登记 `(card, gap_id) → (口径, 理由)`，且**理由必须写出判定依据**（非流片纪律 /
   须 NDA / 须实验台 / 专卡承载），不许写「口径统一」四个字糊过去。
3. **角色分工也要机核**：`role_delegated` 类（纠错码层由专卡承载）必须能在承载卡里
   找到**真实的欠债条目**，否则「分工」只是嘴上说的 —— 以分工为名推掉欠债，同样是洗白。

## 词表纪律

🔴 **只匹配 `title`，不匹配 `detail`**。`detail` 里出现「未实测」的条目（如 `oi G-OI7`
封装热-机械真值、`pm PM-G9` 外设实测锚）**确实是能做活**，若按 detail 匹配会被误判成边界。
写词表前已把全部 116 条的 title 逐条 dump 过（见 v0.9.300 提交记录）。
"""

from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

#: 四值口径的字符串（与 `scripts/gen_gap_settlement.py` 同字面量）
GAP_CLOSED = "已闭合"
GAP_SETTLED = "已结算"
GAP_OPEN = "未闭合"
GAP_BOUNDARY = "边界声明"

#: 口径族定义。
#:   `kind`:
#:     - `permanent_boundary`：命中者**必须全是边界声明**，且**必须覆盖 ≥2 张卡**（防空集合）
#:     - `role_delegated`：命中者必须全是边界声明，且**承载卡里必须有真实欠债**（机核分工）
#:   `title_any`：`title` 子串词表（**大小写敏感度为原文**，中文不受影响）
CALIBERS: Dict[str, Dict[str, Any]] = {
    "tapeout": {
        "kind": "permanent_boundary",
        "label": "非流片 / 无低温实测（项目级非流片纪律）",
        "title_any": ("无流片", "非流片", "无低温实测"),
        "rationale": (
            "流片与低温实测须流片预算、产线与 4 K 实验台，**任何案例卡都无法在本仓内完成**；"
            "项目对外口径本就是「设计期签核 · 非流片实测」⇒ 永久边界，不是欠债。"
        ),
    },
    "foundry_pdk": {
        "kind": "permanent_boundary",
        "label": "无 foundry PDK（器件 / DRC deck）",
        "title_any": ("无 foundry PDK", "无foundry PDK", "无 PDK deck"),
        "rationale": (
            "PDK 与 DRC deck 须 **NDA + 工艺厂交付**，属 D5 外部依赖；"
            "本仓只有「公开近似 + 自建设计规则」⇒ 永久边界。"
        ),
    },
    "bench_calib": {
        "kind": "permanent_boundary",
        "label": "脉冲级 / 门级标定（须实验台）",
        "title_any": ("脉冲级标定", "门标定", "脉冲级 Rabi", "Rabi/Ramsey"),
        "rationale": (
            "Rabi/Ramsey 等脉冲级标定须**真实器件 + 微波/激光实验台**，"
            "没有器件就无从标定 ⇒ 永久边界；而**线路编译与噪声仿真**是纯模型活，"
            "必须**单独拆出**为欠债（见 `schip G-Db`），不得被这句边界一起带走。"
        ),
    },
    "qec_out_of_scope": {
        "kind": "role_delegated",
        "label": "纠错码层不在本案例卡范围（由专卡承载）",
        "title_any": ("无纠错码层",),
        "rationale": (
            "纠错码层由 **j1（`G-QEC*` 容错）与 d2（LDPC / 色码解码器）专卡承载**；"
            "同一项目级缺口不得在案例卡里**重复计债**，否则一处欠债被数两次。"
        ),
        #: 承载卡 → 该卡里必须存在的欠债 id 子串（机核「分工」不是嘴上说的）
        "delegated_to": {"j1": "QEC", "d2": "G-V2-D2"},
    },
}

#: 🔴 **口径更正痕迹账本**（本仓唯一允许「未闭合下降但不做新活」的通道）。
#: 键 = `"<card>/<gap_id>"`，值 = `(口径 id, 理由)`。
#: **理由必须写出判定依据**（`KEYWORDS` 之一），否则 `audit()` 判红。
RECLASSIFIED: Dict[str, Tuple[str, str]] = {
    "j2/J2-G-A": (
        "tapeout",
        "非流片纪律：T1/T2、门保真度、读出保真度均须低温实测台，本仓无法完成"
        " ⇒ 与 ecore G-A / pchip G-A 统一为边界声明；**能力事实不变**（仍全部为设计预算）。",
    ),
    "j2/J2-G-B": (
        "foundry_pdk",
        "须 NDA + 工艺厂 deck（D5 外部依赖）；脉冲级 Rabi/Ramsey 标定须实验台"
        " ⇒ 与 ecore G-B 统一为边界声明；**能力事实不变**（参数仍为设计示例量级）。",
    ),
    "schip/G-A": (
        "tapeout",
        "非流片纪律：与 j2 J2-G-A 逐字同型、与 ecore G-A 同型 ⇒ 统一为边界声明；"
        "**能力事实不变**（仍为设计期签核、未实测）。",
    ),
    "schip/G-B": (
        "foundry_pdk",
        "须 NDA + 工艺厂 deck：DRC 限值为自建设计规则，未对接任何 deck"
        " ⇒ 与 ecore G-B / ecore G-F 统一为边界声明。",
    ),
    "schip/G-C": (
        "qec_out_of_scope",
        "专卡承载：纠错码层由 j1（G-QEC* 容错）与 d2（LDPC / 色码解码器）承载，"
        "本卡不重复计债 ⇒ 边界声明；**不是**「纠错这件事不欠了」，而是「不在这张卡里欠」。",
    ),
    "schip/G-D": (
        "bench_calib",
        "须实验台：脉冲级 Rabi/Ramsey 与门标定无法在无器件条件下进行 ⇒ 该半部分为边界声明；"
        "另一半**线路编译与噪声仿真**是纯模型活，已**拆出**为 `G-Db`（未闭合）。",
    ),
}

#: 理由必须含其一（判定依据），防「口径统一」四个字糊过去
KEYWORDS = ("非流片", "须 NDA", "实验台", "专卡", "不重复计债")


_FOUR = (GAP_CLOSED, GAP_SETTLED, GAP_OPEN, GAP_BOUNDARY)


def prefix4(text: Optional[str]) -> Optional[str]:
    """把卡上的状态原文归一到四值（**只认前缀**），无法识别返回 `None`。

    🔴 为什么口径判据只需要前缀、不需要生成器那套完整词表：
       生成器要兼容历史形态（`CLOSED（…）` / `state` 键 / `gaps_closed` 汇总），
       而口径判据只关心「这一条落在四值哪一档」⇒ **前缀足够且更稳**。
       两处职责不同，故各自实现、**各有自测**，而不是复制同一套词表（复制必漂）。
    """
    t = (text or "").strip()
    for v in _FOUR:
        if t.startswith(v):
            return v
    return None


def rows_from_card(card: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """把**一张卡**的 `gaps` 抽成 `[{"id","title","status_text"}]`（**不归一**）。

    🔴 **这是全仓唯一的「从卡片抽缺口行」实现**：生成器与审计共用它，
    避免「生成器一份、门禁一份」两套抽取各自漂移（v0.9.298 的
    `d2_case.gate_checks` 写 13 / 实跑 19 就是同型，陈腐多版无人发现）。

    三处状态源分支（优先级即顺序，与生成器 `_classify` 同构）：
      ① 并行 `gaps_status` 列表（字符串型 gaps 的卡用）
      ② 元素自带 `status` / `state` 键
      ③ 元素自带 `closed` 布尔（旧口径，只区分闭/未闭）
    都取不到 ⇒ `status_text = ""`（调用方按「未标」处理，**本函数不猜**）。
    """
    gaps = card.get("gaps") or []
    if not gaps:
        return []
    gs = card.get("gaps_status")
    has_par = isinstance(gs, (list, tuple)) and len(gs) == len(gaps)
    out: List[Dict[str, Any]] = []
    for i, g in enumerate(gaps):
        if isinstance(g, dict):
            gid = g.get("id", "-")
            title = g.get("title", "")
        else:
            gid, title = "-", str(g)
        if has_par:
            txt = gs[i]
        elif isinstance(g, dict) and ("status" in g or "state" in g):
            txt = g.get("status") or g.get("state")
        elif isinstance(g, dict) and "closed" in g:
            txt = GAP_CLOSED if g.get("closed") is True else GAP_OPEN
        else:
            txt = ""
        out.append({"id": str(gid), "title": title or "", "status_text": txt})
    return out


def classify_title(title: Optional[str]) -> Tuple[str, ...]:
    """按 `title` 归类口径（**不看 detail**，见模块 docstring 的词表纪律）。"""
    t = title or ""
    hits: List[str] = []
    for cid, spec in CALIBERS.items():
        if any(w in t for w in spec["title_any"]):
            hits.append(cid)
    return tuple(sorted(hits))


def expected_status(caliber_id: str) -> str:
    """该口径下所有缺口必须处于的状态（当前四类统一为边界声明）。"""
    if caliber_id not in CALIBERS:
        raise KeyError("未知口径: %r" % (caliber_id,))
    return GAP_BOUNDARY


def audit(cards: Mapping[str, Iterable[Mapping[str, Any]]]) -> List[str]:
    """跨卡口径审计。

    参数
    ----
    cards : `{card_key: [ {"id":..., "title":..., "status":...}, ... ]}`
        `status` 必须是**已归一的四值字符串**（调用方用生成器同一套分类器归一）。

    返回
    ----
    违反项列表（空 = 通过）。每条都是**人类可读的判决**，不是「失败」二字。
    """
    bad: List[str] = []

    # ① 逐条：命中口径的缺口，状态必须等于该口径期望值
    per_caliber: Dict[str, List[Tuple[str, str]]] = {cid: [] for cid in CALIBERS}
    for ckey in sorted(cards):
        for g in cards[ckey]:
            gid = str(g.get("id") or "-")
            title = g.get("title") or ""
            raw_status = g.get("status") or ""
            status = prefix4(raw_status)
            hits = classify_title(title)
            if hits and status is None:
                # 🔴 口径判据依赖状态可归一：命中了口径却读不出四值 ⇒ 必须判红，
                #    否则「无流片」那类条目随便写个自由文本就能绕过一致性检查。
                bad.append("状态不可归一：%s/%s 属「%s」，但状态「%s」不以四值开头"
                           % (ckey, gid, ",".join(hits), str(raw_status)[:30]))
            for cid in hits:
                per_caliber[cid].append((ckey, gid))
                want = expected_status(cid)
                if status != want:
                    bad.append(
                        "口径不一致：%s/%s 标题属「%s」，应为「%s」，实为「%s」"
                        "（标题：%s）" % (ckey, gid, cid, want, status or "<空>", title[:40])
                    )

    # ② 防空集合：permanent_boundary 必须跨 ≥2 张卡（否则「统一」只在单卡内自说自话）
    for cid, spec in CALIBERS.items():
        hits = per_caliber[cid]
        n_cards = len({c for c, _ in hits})
        if spec["kind"] == "permanent_boundary" and n_cards < 2:
            bad.append(
                "口径「%s」只命中 %d 张卡（%s）⇒ 覆盖不足，无法证明跨卡一致"
                "（防空集合探针）" % (cid, n_cards, sorted({c for c, _ in hits}))
            )
        if not hits:
            bad.append("口径「%s」零命中 ⇒ 词表已失效（必须能被真实数据命中）" % cid)

    # ③ 角色分工机核：`role_delegated` 的承载卡里必须有**真实欠债**
    for cid, spec in CALIBERS.items():
        if spec["kind"] != "role_delegated":
            continue
        for carrier, needle in (spec.get("delegated_to") or {}).items():
            rows = list(cards.get(carrier) or [])
            # 🔴 匹配 **id 或标题**：`j1`/`d2` 的 gaps 是**纯字符串型**（无 id，id 恒为 "-"），
            #    只按 id 匹配会永远失败 ⇒ 把「分工」判成「推掉欠债」（第一版就这样误判了）。
            has = any((needle in (str(g.get("id") or "-") + " " + str(g.get("title") or "")))
                      and (prefix4(g.get("status")) == GAP_OPEN) for g in rows)
            if not has:
                bad.append(
                    "口径「%s」声称由 %s 承载（含 `%s` 的欠债），但该卡里找不到这样的未闭合条目"
                    " ⇒ 以分工为名推掉欠债" % (cid, carrier, needle)
                )
    return bad


def audit_reclassify(cards: Mapping[str, Iterable[Mapping[str, Any]]]) -> List[str]:
    """核验 `RECLASSIFIED` 痕迹账本本身（防「改了状态但痕迹对不上」）。"""
    bad: List[str] = []
    idx: Dict[str, Dict[str, Any]] = {}
    for ckey in cards:
        for g in cards[ckey]:
            idx["%s/%s" % (ckey, str(g.get("id") or "-"))] = g

    if not RECLASSIFIED:
        bad.append("RECLASSIFIED 为空：口径更正必须有痕迹（否则无法与「真做了活」区分）")

    for key, val in sorted(RECLASSIFIED.items()):
        if key not in idx:
            bad.append("RECLASSIFIED 指向不存在的缺口：%s" % key)
            continue
        cid, reason = val
        if cid not in CALIBERS:
            bad.append("RECLASSIFIED[%s] 口径未知：%s" % (key, cid))
            continue
        g = idx[key]
        # ① 当前状态必须与口径期望一致（防「登记了理由、状态又改回去」）
        if prefix4(g.get("status")) != expected_status(cid):
            bad.append("RECLASSIFIED[%s] 当前状态「%s」≠ 期望「%s」（痕迹与现状不符）"
                       % (key, str(g.get("status"))[:20], expected_status(cid)))
        # ② 该条 title 必须真的命中登记的口径（防「借一个口径蒙过另一条」）
        if cid not in classify_title(g.get("title") or ""):
            bad.append("RECLASSIFIED[%s] 标题并不属于口径「%s」（标题：%s）"
                       % (key, cid, (g.get("title") or "")[:40]))
        # ③ 理由必须写出判定依据，不许「口径统一」四字糊过去
        if not any(k in reason for k in KEYWORDS):
            bad.append("RECLASSIFIED[%s] 理由未给出判定依据（须含 %s 之一）"
                       % (key, "/".join(KEYWORDS)))
        if len(reason) < 30:
            bad.append("RECLASSIFIED[%s] 理由过短（%d 字）⇒ 无法复核" % (key, len(reason)))
    return bad


def selfcheck() -> Dict[str, bool]:
    """双向自测：词表**正例命中 / 反例不命中**，且两条审计路径各有反向探针。"""
    c: Dict[str, bool] = {}

    # ① 正例：真实写法的 title 必须被正确归类（四种口径各一，含混写）
    c["pos_tapeout_cn"] = classify_title("无流片 / 无低温实测") == ("tapeout",)
    c["pos_tapeout_slash"] = classify_title("非流片 / 非实测芯片") == ("tapeout",)
    c["pos_foundry"] = classify_title("无 foundry PDK") == ("foundry_pdk",)
    c["pos_mixed"] = classify_title("无 foundry PDK / 无脉冲级标定") == ("bench_calib", "foundry_pdk")
    c["pos_qec"] = classify_title("无纠错码层") == ("qec_out_of_scope",)

    # ② 反例：**detail 里的措辞**与**真活**不得被误判成边界（词表只认 title）
    c["neg_measured_anchor"] = classify_title("外设参数缺本项目实测锚") == ()
    c["neg_thermal_truth"] = classify_title("封装级热-机械-光真值缺失") == ()
    c["neg_simulation"] = classify_title("不含线路级量子态仿真与解码器实测") == ()
    c["neg_empty"] = classify_title(None) == () and classify_title("") == ()
    c["neg_decoder"] = classify_title("LDPC 解码（BP+OSD）") == ()

    # ②b 前缀归一的**正反例**（带后缀必须能认、自由文本必须拒）
    c["prefix4_plain"] = prefix4("未闭合") == GAP_OPEN
    c["prefix4_suffixed"] = prefix4("边界声明（v0.9.300 口径统一：…）") == GAP_BOUNDARY
    c["prefix4_closed_suffix"] = prefix4("已闭合（证据链可查）") == GAP_CLOSED
    c["prefix4_rejects_free"] = prefix4("待定") is None and prefix4("") is None
    c["prefix4_rejects_none"] = prefix4(None) is None
    # 前缀判定**不许**把「已结算」误读成「已闭」（同 S9b 的压扁血案）
    c["prefix4_settled_not_closed"] = prefix4("已结算（裁决）") == GAP_SETTLED

    # ③ 审计正例：构造一份**完全一致**的假数据 ⇒ 必须无违反
    good = {
        "c1": [{"id": "A", "title": "无流片 / 无低温实测", "status": GAP_BOUNDARY}],
        "c2": [{"id": "B", "title": "非流片 / 非实测芯片", "status": GAP_BOUNDARY}],
        "c3": [{"id": "B", "title": "无 foundry PDK", "status": GAP_BOUNDARY}],
        "c4": [{"id": "C", "title": "无 foundry PDK", "status": GAP_BOUNDARY}],
        "c5": [{"id": "D", "title": "无脉冲级标定", "status": GAP_BOUNDARY}],
        # `bench_calib` 在真实数据里命中 j2 与 schip 两张卡 ⇒ 正例也必须给两张，
        # 否则「跨 ≥2 卡」这条防空集合判据会（正确地）判红 —— 我第一次就少了这张。
        "c7": [{"id": "D", "title": "无量子线路级仿真与门标定", "status": GAP_BOUNDARY}],
        "c6": [{"id": "E", "title": "无纠错码层", "status": GAP_BOUNDARY}],
        "j1": [{"id": "G-QEC-1", "title": "容错", "status": GAP_OPEN}],
        "d2": [{"id": "G-V2-D2-5", "title": "阈值", "status": GAP_OPEN}],
    }
    c["audit_clean_passes"] = audit(good) == []

    # ④ 🔴 反向探针 1：把一条改成未闭合 ⇒ 必须指名判红
    bad1 = {k: [dict(g) for g in v] for k, v in good.items()}
    bad1["c2"][0]["status"] = GAP_OPEN
    msg1 = audit(bad1)
    c["probe_open_caught"] = (len(msg1) == 1 and "c2/B" in msg1[0]
                              and "边界声明" in msg1[0])

    # ⑤ 🔴 反向探针 2：只留一张卡 ⇒ 「跨卡一致」这条必须判红（防单卡自说自话）
    solo = {"c1": good["c1"]}
    c["probe_single_card_caught"] = any("覆盖不足" in m for m in audit(solo))

    # ⑥ 🔴 反向探针 3：把承载卡的欠债删掉 ⇒ 必须判「以分工为名推掉欠债」
    bad3 = {k: [dict(g) for g in v] for k, v in good.items()}
    bad3["j1"] = [{"id": "G-QEC-1", "title": "容错", "status": GAP_CLOSED}]
    c["probe_delegation_caught"] = any("以分工为名" in m for m in audit(bad3))

    # ⑦ 痕迹账本自测：构造一条**故意偷懒**的理由 ⇒ 必须判「理由过短 / 无判定依据」
    #    🔴 这一项**只该测「审计器能不能抓到」**，不该顺手校验真实数据 ——
    #       否则真实数据一坏，报错会变成「审计器本身坏了」，把读者引向错误方向
    #       （v0.9.300 第一版就写混了，探针 C 报的是 rc=5 而非 rc=4）。
    probe = {"x": [{"id": "Y", "title": "无流片", "status": GAP_BOUNDARY}]}
    fake_key = "x/Y"
    saved = dict(RECLASSIFIED)
    try:
        RECLASSIFIED[fake_key] = ("tapeout", "口径统一")
        c["reclassify_probe_short_reason"] = any(
            "理由过短" in m or "判定依据" in m for m in audit_reclassify(probe))
    finally:
        RECLASSIFIED.clear()
        RECLASSIFIED.update(saved)
    c["reclassify_restored"] = RECLASSIFIED == saved
    return c


if __name__ == "__main__":       # pragma: no cover
    sc = selfcheck()
    bad = [k for k, v in sc.items() if not v]
    print("gap_caliber 自检 %d/%d" % (len(sc) - len(bad), len(sc)))
    if bad:
        print("FAIL:", bad)
        raise SystemExit(1)
    print("口径族:", ", ".join(sorted(CALIBERS)))
    print("口径更正痕迹:", len(RECLASSIFIED), "条")
    for k, (cid, _) in sorted(RECLASSIFIED.items()):
        print("  %-14s -> %s" % (k, cid))
