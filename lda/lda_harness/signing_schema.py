# -*- coding: utf-8 -*-
"""N3 · 四域签核 schema（**单一真源** · v0.9.283 · D-231）。

═══ 为什么存在（四域审计 v3 §10 N3）═══
四个域的「签核」各写各的：案例卡的 `verdict` 有 6 种值（ACCEPT / DESIGN_BUDGET /
DESIGN_SIGNOFF / DESIGN_VERIFIED / FEASIBLE / NOT_ANCHORABLE）、诚实边界有 **6 种
不同名字**（`HONEST_NOTE` / `PM_HONEST_NOTE` / `QCHIP_HONEST_NOTE` / …）、
deck 可信等级**只有量子侧有**（光子侧无）。⇒ 外部读者无法回答一句话：

    「这一张卡，到底是什么级别的签核？」

本模块把「签核」拆成**三个正交维度**（这是本版最重要的判断）：

  ┌─ grade    工程链深度：预算 < 验证 < 签核 < 工艺厂签核
  ├─ evidence 证据强度  ：无锚 < 有锚 < 有实测语料锚 < 有 strict 独立锚
  └─ deck     deck 可信等级：无 / 自建 / 公开近似 / NDA

🔴 **为什么必须拆开**：`ecore` 的 `DESIGN_VERIFIED` 与 `schip` 的 `DESIGN_SIGNOFF`
**不是同一个维度上的强弱** —— 前者说的是"我这条工程链走到了后仿/DRC"，后者说的是
"我走完了版图+DRC/LVS 签核链"。而"我有没有可复核的锚"是**另一件事**：
`ecore` 工程链到 VERIFIED，但电子域 **0 锚**（见四域审计 v3 §6.1）。
把三者压进一个 `verdict` 字符串，就会得出"ecore 比 13 张预算卡更可信"这种**错误结论**。

═══ 四条硬规则（可证伪 · 都有反向探针）═══
R1 **对外口径**（**v0.9.283 N3-b 重定义**）：
    `grade` = 工程链深度**事实**，不被任何 deck 压制。
    `claimable_grade = min_claim(declared, claim_ceiling(deck))` —— 独立维度，只答
    "对外最高能说成什么"。claim_ceiling：none → DESIGN_VERIFIED ·
    self_built → DESIGN_SIGNOFF · `foundry_public` → **AUDIT_ONLY** ·
    foundry_nda → FOUNDRY_SIGNOFF（后三档复用量子侧 `quantum_deck.py` 既有语义）。
    🔴 **改前的写法是 `effective_grade = min(declared_grade, ceiling(deck))`，那是错的**：
    它把"用途限制"写成"工程深度变浅"。`AUDIT_ONLY` 在旧序数序列里 rank 1，
    低于 `DESIGN_BUDGET` rank 2 ⇒ soc（工程链走完 DRC/LVS）被判成"比 13 张设计
    预算卡还浅"。这正是本模块立项理由「概念被压扁」的**第二次复发**，N3-b 修掉。
R2 **防自封**：`grade == FOUNDRY_SIGNOFF` ⇒ deck 必须 `foundry_nda` **且** attestation 非空
R3 **容量口径**：`capacity_basis == fabricated_devices` ⇒ evidence 必须 ≥ EMPIRICAL
    （没有实测锚就说"已制备器件数" ⇒ 直接把"版图容量"当"实测规模"卖）
R4 **claim 不得手改**：`claimable_grade` 必须等于按 (declared, deck) 现算的值
    （只换 deck 不重算 ⇒ 红。这条让 R1 的重定义**不可被绕过**）

═══ 两处登记（**不掩盖**）═══
V1 **`soc` 对外口径受限** —— ✅ **v0.9.283 N3-b 已处置（拆维度）**：
   deck 的 note 原文写「闭集规则数值 = **公开近似** + 逐条规格锚，**非 foundry NDA 真值**；
   signoff_ready 仅代表主权自洽可制造性就绪，非真实 tape-out 授权」，
   且 `foundry_pdk.py` 用的是 **AIM Photonics 官方公开页面 PDK** ⇒ deck = `foundry_public`。
   ⇒ **`grade` 仍 `DESIGN_SIGNOFF`（事实）· `claimable_grade` = `AUDIT_ONLY`（限制）**。
   棘轮 `CEILING_VIOLATIONS` **1 → 0**（不再是"违规"）；新增
   `CLAIM_DOWNGRADED_CASES = 1`（登记"口径被压制"的卡，**只降不升**）。
   🔴 **没有降 soc 的对外 verdict** —— 那是口径变更，需人决策（N3-b 的选择是拆维度）。
V2 **签核卡未登记锚** —— ✅ **v0.9.283 N3-a 已闭合**：
   原 4 张 `DESIGN_SIGNOFF` 卡（pchip/pm/soc/schip）卡上**都没有 `anchors` 字段**。
   N3-a 给全部 **18 张卡**补了 `anchors` / `anchors_source` / `anchors_note` 三字段，
   棘轮 `ANCHOR_UNREGISTERED_CASES` **14 → 0**。
   🔴 关键是 `anchors_source` 的**三档证据等级**（这是 N3-a 最重要的判断）：
      `runtime` 卡内代码/字段**真的跑**这条锚 —— 全项目只有 1 张（`oi` → B19）
      `segment` 依据账本**号段归属**登记，卡内无运行时引用 —— 16 张
      `none`    本卡确实不依赖账本锚 —— 2 张（`accel` 基准是全精度数字参考；
                `ecore` 电子域专属锚 0 条）
   把 `segment` 读成 `runtime`，就是"把号段归属当已验证" —— 本项目头号复发错。

🔴 **本模块不做的事**：不改任何卡的对外 `verdict`（那是口径变更，需人决策）、
不改任何锚、不进判决路径。它只提供「同一套话 + 可机器核的规则」。

🔴 **`anchors_on_card` 不再手填**（v0.9.283）：它由 `audit()` **运行时读卡计算**
（`read_card()` → `case_card()["anchors"]`），并与本表 `anchors` **双向对拍**。
手填 bool = 自证，是本项目已判死的形态（同 `self_certified` 锚）。

确定性：纯 stdlib、无时间戳、无随机；`audit()` 返回按键排序的确定性结构。
"""
from __future__ import annotations

from typing import Dict, List, Tuple

SCHEMA = "lda_signing_schema_v1"

# ── 维度一：工程链深度（有序，越右越深）────────────────────────────────
# 🔴 N3-b（v0.9.283）：`AUDIT_ONLY` **已从本序列移除**。理由见模块 docstring §N3-b：
#    它是「对外可宣称口径」的取值，不是「工程链深度」的档位。混在同一序数序列里
#    会让「工程链走到签核、但 deck 是公开近似」的卡被判成"比设计预算还浅"。
GRADES: Tuple[str, ...] = (
    "NONE",             # 无任何工程链
    "DESIGN_BUDGET",    # 设计预算／建模值（闭式 + 示例参数）
    "DESIGN_VERIFIED",  # 设计期验证（含电路/版图/后仿/DRC 链）
    "DESIGN_SIGNOFF",   # 设计期签核（版图 + DRC/LVS 链闭合）
    "FOUNDRY_SIGNOFF",  # 工艺厂签核（唯一可对外，须 NDA attestation）
)
GRADE_RANK: Dict[str, int] = {g: i for i, g in enumerate(GRADES)}

# ── 维度一（b）：对外可宣称口径（**独立序列**）──────────────────────────
# 🔴 这是 N3-b 的核心改动：**不再用 `min(grade, ceiling)` 把两件事压成一个数**。
#    · `GRADES`    回答「工程链走到哪一步」—— 是**事实**
#    · `CLAIMABLE` 回答「对外最高能说成什么」—— 是**限制**
#    本序列内部仍有序（`AUDIT_ONLY` 最弱：只能被审计，连"设计预算"都不宜对外宣称），
#    但它**不与 GRADES 交叉比大小** —— 两者各说各的事，互不压制。
#    反例（改前）：soc 工程链走完 DRC/LVS，却因 deck 是公开近似被判成 `AUDIT_ONLY`，
#    读起来像"比 13 张设计预算卡还浅" —— 那是把限制误读成深度。
CLAIMABLE: Tuple[str, ...] = (
    "NONE",             # 不可对外
    "AUDIT_ONLY",       # 只能对外说"可审计"（公开近似 deck 的上限）
    "DESIGN_BUDGET",
    "DESIGN_VERIFIED",
    "DESIGN_SIGNOFF",
    "FOUNDRY_SIGNOFF",
)
CLAIM_RANK: Dict[str, int] = {c: i for i, c in enumerate(CLAIMABLE)}

# ── 维度二：证据强度（有序；与"有没有可复核的锚"挂钩）──────────────────
EVIDENCES: Tuple[str, ...] = (
    "NONE",       # 该域/该卡 0 条专属锚
    "BUDGET",     # 有锚但只有自证桩/建模量
    "EMPIRICAL",  # 有公开实测语料锚
    "STRICT",     # 有 strict 独立候选锚
)
EVIDENCE_RANK: Dict[str, int] = {e: i for i, e in enumerate(EVIDENCES)}

# ── 维度三：deck 可信等级（与 `lda_qeda/quantum_deck.py` 同义）─────────
DECKS: Tuple[str, ...] = ("none", "self_built", "foundry_public", "foundry_nda")

#: deck ⇒ **可对外宣称**的最高口径（不是"降 grade"，见 CLAIMABLE 注释）
DECK_CLAIM_CEILING: Dict[str, str] = {
    "none": "DESIGN_VERIFIED",   # 无 deck ⇒ 可验证，但不得对外称"签核"
    "self_built": "DESIGN_SIGNOFF",  # 自建规则 ⇒ 只可内部设计签核（allow_external=False）
    "foundry_public": "AUDIT_ONLY",  # 公开近似层 ⇒ 只可审计（量子侧既有语义）
    "foundry_nda": "FOUNDRY_SIGNOFF",  # 唯一可对外
}

#: deck ⇒ 是否允许进对外材料（复用量子侧 `SIGNOFF_CEILING[*]["allow_external"]`）
DECK_ALLOW_EXTERNAL: Dict[str, bool] = {
    "none": False,
    "self_built": False,
    "foundry_public": False,
    "foundry_nda": True,
}

CAPACITY_BASES: Tuple[str, ...] = ("none", "layout_capacity", "fabricated_devices")

#: 棘轮（**只降不升**）
CEILING_VIOLATIONS = 0        # N3-b 后：天花板不再产生"违规"，改为登记 claim 压制
ANCHOR_UNREGISTERED_CASES = 0  # N3-a 后：18/18 卡都有 anchors 字段（原 14）

#: claim 被 deck 压制的卡数（**只降不升**；soc 是唯一一条，且属正常限制而非缺陷）
CLAIM_DOWNGRADED_CASES = 1


class SigningRecord(dict):
    """一条签核记录（dict 子类，便于 JSON 化）。"""


def claim_ceiling_of(deck: str) -> str:
    """deck → **可对外宣称**的最高口径（R1）。未知 deck 一律按最严处理。"""
    return DECK_CLAIM_CEILING.get(deck, "AUDIT_ONLY")


def claimable_grade(declared: str, deck: str) -> str:
    """对外可宣称口径（R1 · **N3-b 重定义**）。

    🔴 与改前的 `effective_grade` 的本质区别：
      · 改前：`min(declared, ceiling)` 覆盖了 declared ⇒ 把「限制」写成「深度变浅」
      · 改后：`declared` 原样保留（事实），本函数**只回答"能对外说成什么"**

    返回值的取值域是 `CLAIMABLE`（可能是 `AUDIT_ONLY`，它不在 `GRADES` 里）。
    """
    c = claim_ceiling_of(deck)
    if declared not in CLAIM_RANK or c not in CLAIM_RANK:
        return "NONE"
    return declared if CLAIM_RANK[declared] <= CLAIM_RANK[c] else c


def make_record(*, case: str, declared: str, evidence: str, deck: str,
                capacity: str = "layout_capacity", anchors: Tuple[str, ...] = (),
                attestation: str = "") -> SigningRecord:
    """构造一条签核记录（**只做结构校验，不算 claim**）。

    `anchors` = 该卡所属征程**确实存在**的账本锚（依据：账本号段 + 四域审计 v3）。

    🔴 **没有 `on_card` 参数**（v0.9.283 N3-a 删除）：卡上是否真写了 anchors
    由 `audit()` **运行时读卡**判定（`read_card()`），不接受登记表自述。
    手填 bool 就是自证 —— 本项目已判死形态。
    """
    return SigningRecord({
        "case": case,
        # `grade` = 工程链深度**事实**（不再被 deck 压制，N3-b）
        "grade": declared,
        "declared_grade": declared,
        "evidence": evidence,
        "deck": deck,
        "capacity_basis": capacity,
        "anchors": tuple(anchors),
        "attestation": attestation,
        # 对外口径（独立维度，N3-b）
        "claimable_grade": claimable_grade(declared, deck),
        "claim_ceiling": claim_ceiling_of(deck),
        "allow_external": DECK_ALLOW_EXTERNAL.get(deck, False),
        "claim_downgraded": claim_rank_lt(claimable_grade(declared, deck), declared),
    })


def claim_rank_lt(a: str, b: str) -> bool:
    """对外口径 a 是否弱于工程深度 b（用于登记"被压制"，不是"违规"）。"""
    if a not in CLAIM_RANK or b not in CLAIM_RANK:
        return False
    return CLAIM_RANK[a] < CLAIM_RANK[b]


def validate(rec: dict) -> List[str]:
    """返回违规项（空列表 = 合规）。每条都能被反向探针触发。"""
    bad: List[str] = []
    g = rec.get("declared_grade")
    ev = rec.get("evidence")
    dk = rec.get("deck")
    cap = rec.get("capacity_basis")
    anc = tuple(rec.get("anchors") or ())

    if g not in GRADE_RANK:
        bad.append("unknown_grade:%r" % (g,))
    if ev not in EVIDENCE_RANK:
        bad.append("unknown_evidence:%r" % (ev,))
    if dk not in DECKS:
        bad.append("unknown_deck:%r" % (dk,))
    if cap not in CAPACITY_BASES:
        bad.append("unknown_capacity:%r" % (cap,))

    # R1 对外口径（**N3-b 重定义：不再是 violation**）
    # 🔴 改前是 `ceiling_violation`（把 deck 限制当违规 ⇒ 逼着人"降 verdict"）。
    #    改后：deck 限制只决定 `claimable_grade`，**不动 grade**。
    #    ⇒ 这里只校验"claimable 是否真的等于按 deck 算出来的值"（防手改），
    #      而不再把"declared 高于 ceiling"本身当错误。
    if g in GRADE_RANK and dk in DECKS:
        expect = claimable_grade(g, dk)
        got = rec.get("claimable_grade")
        if got is not None and got != expect:
            bad.append("claimable_mismatch:%s!=%s(declared=%s,deck=%s)"
                       % (got, expect, g, dk))

    # R2 防自封
    if g == "FOUNDRY_SIGNOFF":
        if dk != "foundry_nda":
            bad.append("self_sealed:foundry_signoff_with_deck=%s" % dk)
        if not str(rec.get("attestation") or "").strip():
            bad.append("self_sealed:foundry_signoff_without_attestation")

    # R3 容量口径
    if cap == "fabricated_devices":
        if EVIDENCE_RANK.get(ev, -1) < EVIDENCE_RANK["EMPIRICAL"]:
            bad.append("capacity_unbacked:fabricated_devices_with_evidence=%s" % ev)

    # R4 证据自洽：声称 STRICT/EMPIRICAL 就必须有锚
    if ev in ("STRICT", "EMPIRICAL") and not anc:
        bad.append("evidence_without_anchors:%s" % ev)

    return bad


# ═══════════════════════════════════════════════════════════════════════════
# 18 张案例卡的签核登记表（**单一真源**）
# ---------------------------------------------------------------------------
# 🔴 登记纪律：
#   · `declared` 不是"再声明一遍" —— 门禁会拿它与**卡上实际 `verdict`** 逐条对拍
#     （`run_webui_json_hard_smoke` 的 S1b），漂移即红。
#   · `anchors` 记的是「该卡所属征程**确实存在**的账本锚」（依据：账本号段 +
#     四域审计 v3 §2.1/§4.2），**不是**"卡自己声明要签的锚"。后者见 V2 缺口：
#     18 张里只有 d1/d2/j1/j5 四张在卡上写了 `anchors` 字段。
#   · `deck` 依据：光子 pchip/pm 与超导 schip 用**自建 DRC/LVS 规则**（四域审计
#     §8.4 缺口 2 原文「自建规则，非 foundry deck」）⇒ self_built；
#     soc 的闭集规则 note 自述「公开近似，非 foundry NDA 真值」⇒ foundry_public。
# ═══════════════════════════════════════════════════════════════════════════
_HELPER_10 = ("B9", "B10", "B12", "B13", "B18", "B22", "B24", "B25", "B26", "B30")
_QS_24 = tuple("B%d" % n for n in range(473, 497))
_J1_9 = tuple("B%d" % n for n in range(497, 506))
_J2_4 = tuple("B%d" % n for n in range(506, 510))
_J3_5 = tuple("B%d" % n for n in range(510, 515))
_J4_4 = ("B515", "B518")          # B516/B517 是 reserved_null 空位
_J5_4 = tuple("B%d" % n for n in range(519, 523))
_LOQC_5 = ("B453", "B454", "B455", "B456", "B457")
_V2_3 = ("B523", "B524", "B525")

CASES: Dict[str, SigningRecord] = {
    # ── 光子域 ────────────────────────────────────────────────────────
    # 🔴 N3-a 对拍修正：原登记 B1/B2/B20/B21，但 **B1（米氏散射）与 B21（光子晶体腔）
    #    与 MZI 张量核无关**，卡上亦无依据 ⇒ 只留 B2（SOI n_eff）与 B20（MZI FSR）。
    "pchip": make_record(case="pchip", declared="DESIGN_SIGNOFF", evidence="BUDGET",
                         deck="self_built", anchors=("B2", "B20")),
    "pm": make_record(case="pm", declared="DESIGN_SIGNOFF", evidence="BUDGET",
                      deck="self_built", anchors=("B28", "B29")),
    "soc": make_record(case="soc", declared="DESIGN_SIGNOFF", evidence="BUDGET",
                       deck="foundry_public",
                       # 🔴 N3-a 修正：原登记 S1–S13 全 13 条，但 **S4 是量子门保真预算**
                       #    （量子域），光 SoC 不应认领 ⇒ 排除，实为 12 条。
                       anchors=tuple("S%d" % n for n in range(1, 14) if n != 4)),
    # 🔴 N3-a 对拍修正：原登记为空，但卡内 `b19_passivity` **实测 True**
    #    ⇒ B19（无源无增益）是唯一有 runtime 证据的锚，必须登。
    "oi": make_record(case="oi", declared="DESIGN_BUDGET", evidence="BUDGET",
                      deck="none", anchors=("B19",)),
    "accel": make_record(case="accel", declared="DESIGN_BUDGET", evidence="BUDGET",
                         deck="none", anchors=()),
    "sensor": make_record(case="sensor", declared="DESIGN_BUDGET", evidence="EMPIRICAL",
                          deck="none",
                          anchors=tuple("B%d" % n for n in range(459, 473))),
    # ── 量子域（LOQC / 传感 / 六层 / 蓝图 v2）─────────────────────────
    # 🔴 N3-a 对拍修正：LOQC 5 条之外还有 **S4 量子门保真度预算**（光学量子门必经）。
    "qchip": make_record(case="qchip", declared="DESIGN_BUDGET", evidence="STRICT",
                         deck="none", anchors=_LOQC_5 + ("S4",)),
    "qs": make_record(case="qs", declared="DESIGN_BUDGET", evidence="STRICT",
                      deck="none", anchors=_QS_24),
    "j1": make_record(case="j1", declared="DESIGN_BUDGET", evidence="STRICT",
                      deck="none", anchors=_J1_9),
    "j2": make_record(case="j2", declared="DESIGN_BUDGET", evidence="STRICT",
                      deck="none", anchors=_J2_4),
    "j3": make_record(case="j3", declared="DESIGN_BUDGET", evidence="STRICT",
                      deck="none", anchors=_J3_5),
    "j4": make_record(case="j4", declared="DESIGN_BUDGET", evidence="STRICT",
                      deck="none", anchors=_J4_4),
    "j5": make_record(case="j5", declared="DESIGN_BUDGET", evidence="STRICT",
                      deck="none", anchors=_J5_4),
    "d1": make_record(case="d1", declared="DESIGN_BUDGET", evidence="STRICT",
                      deck="none", anchors=("B523", "B524")),
    "d2": make_record(case="d2", declared="DESIGN_BUDGET", evidence="STRICT",
                      deck="none", anchors=("B525",)),
    "d4": make_record(case="d4", declared="DESIGN_BUDGET", evidence="BUDGET",
                      deck="none", anchors=_V2_3),
    # ── 超导量子域 ────────────────────────────────────────────────────
    # 🔴 N3-a 修正：原只登超导器件物理 10 条，**漏了签核卡必须的系统级 6 条** ——
    #    S4 门保真预算 · S9/S10 LVS 版图一致性 · S11 千器件规模 · S12 阵列分布 · S13 良率。
    #    超导芯片的 DESIGN_SIGNOFF 恰恰是 S9/S10 定义的，漏登等于"签核没签在锚上"。
    "schip": make_record(case="schip", declared="DESIGN_SIGNOFF", evidence="STRICT",
                         deck="self_built",
                         anchors=_HELPER_10 + ("S4", "S9", "S10", "S11", "S12", "S13")),
    # ── 电子域 ────────────────────────────────────────────────────────
    # 🔴 `evidence="STRICT"`（v0.9.341 · A1）：电子域专属锚 **5 条（B526–B530）**，
    #    均为确定性闭式物理律（教科书）golden ⇄ 独立数值法 candidate（R4 规则：STRICT 须配非空 anchors）。
    #    `DESIGN_VERIFIED` 仍指工程链走到后仿/DRC，与锚证据正交。
    "ecore": make_record(case="ecore", declared="DESIGN_VERIFIED", evidence="STRICT",
                         deck="none", anchors=("B526", "B527", "B528", "B529", "B530")),
}


#: case key → 案例卡模块（`lda_webui.<module>`）。`d4` 的模块名不规整，单列。
_CARD_MODULE: Dict[str, str] = {
    "pchip": "pchip_case", "pm": "pm_case", "soc": "soc_case", "oi": "oi_case",
    "accel": "accel_case", "sensor": "sensor_case", "qchip": "qchip_case",
    "qs": "qs_case", "j1": "j1_case", "j2": "j2_case", "j3": "j3_case",
    "j4": "j4_case", "j5": "j5_case", "d1": "d1_case", "d2": "d2_case",
    "d4": "d4case", "schip": "schip_case", "ecore": "ecore_case",
}


#: 公开别名（门禁/端点在需要"case → 模块名"时用它，不必碰私有名）
CARD_MODULE: Dict[str, str] = _CARD_MODULE


def read_card(case: str) -> dict:
    """运行时读一张案例卡（懒导入 `lda_webui.*`，避免本模块加载期依赖 webui）。

    🔴 为什么不放在模块顶层 import：`signing_schema` 会被多个门禁 import，
    而 `lda_webui` 包较重（案例卡现算）。懒导入 + 只读一次最省。
    """
    import importlib

    mod = _CARD_MODULE[case]
    return importlib.import_module("lda_webui." + mod).case_card()


def anchors_diff(registered, on_card) -> List[str]:
    """本表登记 anchors ⇄ 卡上 anchors 的差异（空列表 = 一致）。

    抽成纯函数是为了**可反向探针**：门禁构造一组故意不一致的输入，验它必非空。
    """
    reg = {str(x) for x in (registered or ())}
    act = {str(x) for x in (on_card or ())}
    out: List[str] = []
    if reg - act:
        out.append("only_in_schema:" + ",".join(sorted(reg - act)))
    if act - reg:
        out.append("only_on_card:" + ",".join(sorted(act - reg)))
    return out


def honest_note_of(case: str) -> str:
    """该卡的诚实边界文本（**统一读取入口** · N3-d）。

    🔴 **为什么不统一 Python 变量名**（这是 N3-d 最重要的判断）：
      1. 18 个模块的实际形态是 **4 张 `HONEST_NOTE` + 12 张 `XXX_HONEST_NOTE` + 2 张内联字符串**
         （`oi` / `accel` 根本没有模块级常量）。
      2. 更硬的理由：**7 个门禁用「改模块级变量 ⇒ `case_card()` 必红」做突变探针**
         （`EC.ECORE_HONEST_NOTE = …` 后验红）。改名会连带改这些探针；
         而加**别名**（`HONEST_NOTE = ECORE_HONEST_NOTE`）是**快照** ——
         突变改了原变量、别名仍指向旧对象 ⇒ **统一入口会给过期值**，比不统一更危险。
      3. 所以收敛点放在**对外契约**而不是变量名：`case_card()["honest_note"]` 本来就是
         18 张卡统一有的字段。本函数**每次现读卡**，永远拿最新值（突变可传播）。
    """
    return str(read_card(case).get("honest_note") or "")


#: 各卡**模块级常量名**登记（N3-d · 仅供可发现性与机核，**不是读取路径**）。
#: `None` = 该模块没有常量，honest_note 直接内联在 `case_card()` 里。
#: 🔴 门禁 S7 会逐条 `hasattr(module, name)` 核对 —— 表过期（改名/删除）即红。
NOTE_ATTR: Dict[str, object] = {
    "accel": None,                 # 内联字符串
    "d1": "HONEST_NOTE",
    "d2": "HONEST_NOTE",
    "d4": "HONEST_NOTE",
    "ecore": "ECORE_HONEST_NOTE",
    "j1": "J1_HONEST_NOTE",
    "j2": "J2_HONEST_NOTE",
    "j3": "J3_HONEST_NOTE",
    "j4": "J4_HONEST_NOTE",
    "j5": "J5_HONEST_NOTE",
    "oi": None,                    # 内联字符串
    "pchip": "PCHIP_HONEST_NOTE",
    "pm": "PM_HONEST_NOTE",
    "qchip": "QCHIP_HONEST_NOTE",
    "qs": "QS_HONEST_NOTE",
    "schip": "SCHIP_HONEST_NOTE",
    "sensor": "HONEST_NOTE",
    "soc": "SOC_HONEST_NOTE",
}


def audit() -> Dict[str, object]:
    """全表审计（确定性输出）。门禁消费此结果。

    🔴 **`anchors_on_card` 与 `anchors_drift` 都是运行时读卡算出来的**
    （`read_card()`），不是登记表自述 —— 这是 v0.9.283 N3-a 的核心改动。
    """
    rows: Dict[str, List[str]] = {}
    violations = 0
    for key in sorted(CASES):
        bad = validate(CASES[key])
        rows[key] = bad
        if bad:
            violations += 1
    # 🔴 N3-b：不再有"capped"（grade 不被压），改为登记**对外口径被压制**的卡
    downgraded = sorted(k for k in CASES if CASES[k]["claim_downgraded"])
    dist_grade: Dict[str, int] = {}
    dist_claim: Dict[str, int] = {}
    dist_ev: Dict[str, int] = {}
    dist_src: Dict[str, int] = {}
    on_card: List[str] = []
    unregistered: List[str] = []
    drift: Dict[str, List[str]] = {}
    sources: Dict[str, str] = {}
    notes: Dict[str, str] = {}
    labels: Dict[str, str] = {}
    for k in sorted(CASES):
        g = CASES[k]["grade"]                    # 工程链深度（事实）
        c = CASES[k]["claimable_grade"]          # 对外口径（限制）
        e = CASES[k]["evidence"]
        dist_grade[g] = dist_grade.get(g, 0) + 1
        dist_claim[c] = dist_claim.get(c, 0) + 1
        dist_ev[e] = dist_ev.get(e, 0) + 1
        # ── 运行时读卡（本表的 anchors 必须与卡上逐条相等）──
        card = read_card(k)
        src = str(card.get("anchors_source") or "")
        dist_src[src] = dist_src.get(src, 0) + 1
        sources[k] = src
        notes[k] = str(card.get("honest_note") or "")   # N3-d：统一从卡上取
        labels[k] = str(card.get("verdict_label") or "")  # N5：对外标签（卡片字段）
        if "anchors" not in card:
            unregistered.append(k)
            continue
        on_card.append(k)
        bad_diff = anchors_diff(CASES[k]["anchors"], card["anchors"])
        if bad_diff:
            drift[k] = bad_diff
    return {
        "schema": SCHEMA,
        "cases_total": len(CASES),
        "by_grade": dist_grade,                  # 工程链深度分布（N3-b）
        "by_claimable_grade": dist_claim,        # 对外口径分布（N3-b）
        "by_evidence": dist_ev,
        "by_anchors_source": dist_src,
        "violations": violations,
        "violation_detail": {k: v for k, v in rows.items() if v},
        # 🔴 N3-b：`ceiling_capped`（grade 被压）已废除 —— grade 是事实，不压。
        #    改为登记"对外口径弱于工程深度"的卡（正常限制，不是缺陷）。
        "claim_downgraded": downgraded,
        "allow_external_cases": sorted(k for k in CASES if CASES[k]["allow_external"]),
        "anchors_on_card": on_card,           # 运行时读卡：卡上确有 anchors 字段
        "anchors_unregistered": unregistered,  # 运行时读卡：卡上无 anchors 字段
        "anchors_drift": drift,               # 🔴 本表 anchors ≠ 卡上 anchors
        "anchors_source_by_case": sources,    # 逐卡证据等级（runtime/segment/none）
        "honest_note_by_case": notes,         # N3-d：逐卡诚实边界（统一从卡上取）
        "verdict_label_by_case": labels,      # N5：逐卡对外标签（卡片字段，6 张原为 None）
        "note_attr": dict(sorted(NOTE_ATTR.items())),   # 模块级常量名登记（可发现性）
        "ceiling_violations_ratchet": CEILING_VIOLATIONS,
        "anchor_unregistered_cases_ratchet": ANCHOR_UNREGISTERED_CASES,
        "claim_downgraded_cases_ratchet": CLAIM_DOWNGRADED_CASES,
    }
