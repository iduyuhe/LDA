# -*- coding: utf-8 -*-
"""LDA 智能体客服（用户侧 Agent 层）。

定位：生产环境面向访客的「智能体客服」——解答产品问题 + 收集客户线索。
**绝不进入验证判决路径**：LLM 只用于对话生成，求解 / 判决仍由 harness 死标量。

设计纪律（与 WebUI 零依赖哲学一致）：
  - 仅用 Python 标准库（json / re / os / threading / urllib），不引入新依赖。
  - 无 LLM 配置时自动回退内置 FAQ 知识库，离线可跑、立即可用。
  - 配置 LLM：设环境变量 LDA_CS_LLM_BASE_URL（OpenAI 兼容 /chat/completions）、
    LDA_CS_LLM_API_KEY、LDA_CS_LLM_MODEL 即可升级为模型驱动对话。
  - 客户线索落盘到 dist/customer_leads.json（gitignored，与 purchase/opinions 同目录纪律），
    按邮箱去重，绝不入库、不外传。
"""
import json
import os
import re
import threading
import time
import uuid

WEBUI_DIR = os.path.dirname(os.path.abspath(__file__))
LDA_ROOT = os.path.dirname(WEBUI_DIR)
LEADS_PATH = os.path.join(os.path.dirname(LDA_ROOT), "dist", "customer_leads.json")
_LEADS_LOCK = threading.Lock()
_LEADS_CAP = 2000

# --------------------------------------------------------------------------
# 内置 FAQ 知识库（关键词 -> 回答）。无 LLM 时的主应答源；也是 LLM 的
# system prompt 底稿。保持与 README / 验证红线口径一致，不夸大。
# --------------------------------------------------------------------------
FAQ = [
    {
        "keys": ["是什么", "介绍", "你们", "产品", "干嘛", "干什么", "about"],
        "answer": (
            "LDA 是开源、Agent 原生的光子（PDA）与量子（QEDA）芯片设计软件："
            "覆盖设计→仿真→版图→DRC/LVS→工艺角→几何寄生全闭环，并用 50 道验证锚"
            "做死标量可复现验证。核心是「LLM 不进判决路径」——PASS/FAIL 由解析闭式"
            "与麦克斯韦方程的确定性比对决定，可被 curl 活体验货。"
        ),
    },
    {
        "keys": ["验证", "可信", "红线", "为什么", "可靠", "accuracy", "准确"],
        "answer": (
            "可信来自三条：①物理定律锚——判决落非 AI ground（解析解 / 麦克斯韦确定性）；"
            "②死标量比对——PASS/FAIL 由机器算出的标量差决定，不是模型自证；"
            "③LLM 不进判决路径。对外可 curl /api/cpo_array 复现十万级器件的 DRC+LVS"
            "死锚判决。诚实边界：当前 50 锚中严格独立候选约 25 道，其余为自洽占位锚"
            "（仅表示回路闭合，不代表已验证）。"
        ),
    },
    {
        "keys": ["光子", "硅光", "pd", "pda", "波导", "ring", "耦合器", "分束", "光栅"],
        "answer": (
            "光子栈（PDA）覆盖波导 / 环形谐振器 / 布拉格镜 / 方向耦合器 / Y 分支 / "
            "光栅耦合器 / WDM / 热光调谐等，支持参数化逆设计、2D/3D FDTD 端口 S 参数"
            "验收、版图 GDS 导出与 DRC。无 GPU 时诚实退回 ORACLE 真值演示。"
        ),
    },
    {
        "keys": ["量子", "qubit", "transmon", "qeda", "超导", "读出", "保真度"],
        "answer": (
            "量子栈（QEDA）覆盖 Transmon / 谐振器 / 耦合器、色散读出保真度预算、"
            "N-qubit 频率复用读出、量子门 / 纠错拓扑（surface code）。验证用解析闭式"
            "↔ 严格数值对角化双比对，纯 numpy 秒级可跑。"
        ),
    },
    {
        "keys": ["上手", "怎么用", "快速", "demo", "开始", "试用", "3分钟", "三分钟"],
        "answer": (
            "最快上手：打开「验证实力」页看实时自证看板；在控制台选一个器件面板"
            "（如环形 / 布拉格 / 量子读出）点运行，秒级返回带物理洞察的结果。"
            "想跑真·验证：/api/cpo_array 死锚判决可一行 curl 复现。"
        ),
    },
    {
        "keys": ["价格", "收费", "多少钱", "购买", "商用", "授权", "license", "付费", "定价"],
        "answer": (
            "LDA 本身 MIT 开源、免费可自部署。商业侧有「创新超市」设计就绪包分档"
            "（基础 ¥599 / 标准 ¥1999 / 高端 ¥4999）与对公定制。具体需求可留联系方式，"
            "我们按场景报价。"
        ),
    },
    {
        "keys": ["开源", "源码", "github", "仓库", "贡献", "社区"],
        "answer": (
            "LDA 是开源项目（MIT），代码 / 锚清单 / CI 全绿证据全公开："
            "https://github.com/iduyuhe/LDA 。欢迎社区共建 PDK 与器件本体"
            "（生态提交接口内置评审流）。"
        ),
    },
    {
        "keys": ["边界", "不能", "局限", "流片", "tapeout", "量产", "签核", "pdk"],
        "answer": (
            "诚实边界：适合科研 / 教学 / 预研 / 中小设计空间探索 / 方法学验证；"
            "暂不直接交付晶圆厂量产 signoff（需接真实 PDK + 商业签核）。大模型只用于"
            "编排与文档，绝不进求解 / 判决。真实流片属 C 期规划。"
        ),
    },
    {
        "keys": ["agent", "智能体", "ai", "自动化", "agentic"],
        "answer": (
            "LDA 是 Agent 原生：开发侧用 agent 自迭代设计闭环与编排；对外也提供我这个"
            "智能体客服解答问题、收集需求。但验证判决仍由确定性内核与死标量比对完成，"
            "Agent 不替代物理定律——这是与「让 LLM 直接造芯」路线的根本区别。"
        ),
    },
    {
        "keys": ["联系", "商务", "合作", "咨询", "对接", "销售"],
        "answer": (
            "留下您的姓名 / 公司 / 邮箱或微信，我们的团队会尽快与您联系；"
            "也可直接邮件到开源仓库主页。您也可以在这里直接说「留个联系方式」。"
        ),
    },
]

# --------------------------------------------------------------------------
# 引导型对话流（智能体做成引导型）：带用户走 3 分钟上手主线。
# 顺序与 static/guide_widget.js 的 STEPS 一一对应（0 欢迎 / 1 健康 / 2 设计 /
# 3 版图仿真 / 4 验证 / 5 客服 / 6 完成），anchor 选择器保持一致以便联动。
# 注意：引导只是对话/导航辅助，绝不进入验证判决路径。
# --------------------------------------------------------------------------
GUIDE_STEPS = [
    {
        "title": "欢迎 · 3 分钟上手",
        "intro": (
            "我是你的 3 分钟向导 🚀 LDA 是开源、Agent 原生的光子+量子芯片设计软件，"
            "核心红线：LLM 不进判决路径，PASS/FAIL 由物理定律锚的死标量比对决定。\n"
            "我们走一条主线：设计 → 仿真/版图 → 验证。点「下一步」我带你逐站看。"
        ),
        "tip": "途中任何一步卡住，直接在这里问我；也可点「🎯 可视化引导」看聚光灯高亮。",
        "anchor": None,
    },
    {
        "title": "① 一眼看懂系统健康",
        "intro": (
            "顶部四张实时卡是系统真面目：验证 harness 通过数、AI 内核候选、锚覆盖(S1–S12)、"
            "已落地真地基层。它们由后端实时真跑，不是装饰。"
        ),
        "tip": "通过数越高、真地基越多，可验货底子越厚。诚实边界：当前 50 锚中严格独立候选约 25 道。",
        "anchor": "#cards",
    },
    {
        "title": "② 设计：给目标，出统一设计包",
        "intro": (
            "在「旗舰流程·设计闭环端到端」选器件、填目标，点运行设计闭环→出设计包。"
            "LDA 生成候选、物理锚即提即验、确定性排序，给出可下载统一设计包 JSON。"
        ),
        "tip": "关键：AI 生成候选，物理定律当法官——这就是「生成与判决分离」。想看细节问我就行。",
        "anchor": "#runDesignOutcome",
    },
    {
        "title": "③ 版图 → DRC → 仿真 流水线",
        "intro": (
            "「版图→DRC→仿真 流水线」一键贯通：参数→GDS 版图(SVG 预览)→DRC 自查→"
            "FDTD 仿真 neff→物理锚验收。从设计意图到「可制造+已仿真验收」一条命令走完。"
        ),
        "tip": "无 GPU 时诚实退回 ORACLE 真值演示，不谎报算力。",
        "anchor": "#runLp",
    },
    {
        "title": "④ 验证：物理定律当法官",
        "intro": (
            "「验证裁判控制台」选候选求解器、点运行验证：真调 LDA harness，用物理定律锚逐题比对，"
            "给 PASS/FAIL 死标量。这是护城河——判决落非 AI ground，可外部 curl 复现验货。"
        ),
        "tip": "想亲眼验？运行后或访问 /api/cpo_array 一行 curl 复现十万级 DRC+LVS 死锚判决。",
        "anchor": "#runVerify",
    },
    {
        "title": "⑤ 智能体客服：随时提问 + 留资",
        "intro": (
            "就是我啦 😊 我解答产品定位、验证红线、光子/量子能力、上手方式、开源与商用、能力边界；"
            "也能留姓名+公司+邮箱安排专人对接。注意：我只对话，绝不进求解/判决。"
        ),
        "tip": "想对接商务或要白皮书，留个联系方式即可。",
        "anchor": 'div[title="LDA 智能体客服"]',
    },
    {
        "title": "完成 · 你已走完主线",
        "intro": (
            "✅ 设计→仿真/版图→验证 这条闭环你看完了。深入了解：底部「技术白皮书」下载，"
            "或「关于 LDA」看产品说明与验证账本；我随时在。"
        ),
        "tip": "要正式对接或拿源码：留联系方式，或访问 github.com/iduyuhe/LDA。",
        "anchor": None,
    },
]

_FALLBACK = (
    "我是 LDA 智能体客服，可解答产品定位、验证红线、光子/量子能力、上手方式、"
    "开源与商用、边界等问题。您也可以直接留下姓名+公司+邮箱，我们安排专人对接。"
)

_SYSTEM_PROMPT = (
    "你是 LDA（开源 Agent 原生光子/量子芯片设计软件）的智能体客服，语气专业、简洁、诚实。"
    "只回答与 LDA 产品相关的问题；不进入任何工程求解/验证判决路径。"
    "已知事实：LDA 开源 MIT、光子(PDA)+量子(QEDA)双栈、50 道验证锚、LLM 不进判决路径、"
    "可被 curl /api/cpo_array 验货、商业有创新超市分档(¥599/¥1999/¥4999)与对公定制、"
    "边界是不直接交付量产 signoff。用户留下联系方式时，请礼貌确认会安排对接。"
)


# --------------------------------------------------------------------------
# 线索抽取与落盘
# --------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
_WECHAT_RE = re.compile(r"(微信[：: ]?\s*|微信号[：: ]?\s*|wx[：: ]?\s*)([A-Za-z0-9_\-]{5,20})")


def extract_lead(message, structured):
    """从自由文本 + 结构化字段中抽取客户线索。返回 dict 或 None。"""
    lead = {}
    s = structured or {}
    msg = (message or "").strip()
    if s.get("name"):
        lead["name"] = str(s["name"]).strip()[:60]
    if s.get("company") or s.get("organization"):
        lead["company"] = str(s.get("company") or s.get("organization")).strip()[:120]
    if s.get("email"):
        lead["email"] = str(s["email"]).strip()[:120]
    if s.get("phone"):
        lead["phone"] = str(s["phone"]).strip()[:40]
    if s.get("wechat"):
        lead["wechat"] = str(s["wechat"]).strip()[:40]
    if s.get("need") or s.get("interest"):
        lead["need"] = str(s.get("need") or s.get("interest")).strip()[:500]

    if msg:
        m = _EMAIL_RE.search(msg)
        if m and "email" not in lead:
            lead["email"] = m.group(0)
        m = _PHONE_RE.search(msg)
        if m and "phone" not in lead:
            lead["phone"] = m.group(0)
        m = _WECHAT_RE.search(msg)
        if m and "wechat" not in lead:
            lead["wechat"] = m.group(2)
        # 公司/单位关键词
        for kw in ("公司", "单位", "机构", "研究院", "实验室", "大学", "学院", "所", "厂"):
            if kw in msg and "company" not in lead:
                # 取关键词前后一段作为候选单位名（粗抽）
                idx = msg.index(kw)
                seg = msg[max(0, idx - 12): idx + len(kw) + 8]
                lead["company"] = seg.strip()[:120]
                break
        if "name" not in lead:
            # 「我是/我叫 XX」粗抽姓名（2-4 字中文）
            m = re.search(r"(?:我是|我叫|姓名[：: ]?\s*)([\u4e00-\u9fa5]{2,4})", msg)
            if m:
                lead["name"] = m.group(1)

    # 必须有可联系信息才算有效线索
    if not any(k in lead for k in ("email", "phone", "wechat", "company")):
        return None
    if "email" not in lead and "phone" not in lead and "wechat" not in lead \
            and "name" not in lead:
        return None
    lead["source"] = "cs_agent"
    return lead


def collect_lead(lead):
    """落盘客户线索到 dist/customer_leads.json（gitignored）。按邮箱去重。"""
    try:
        os.makedirs(os.path.dirname(LEADS_PATH), exist_ok=True)
        with _LEADS_LOCK:
            data = {"leads": []}
            if os.path.exists(LEADS_PATH):
                try:
                    with open(LEADS_PATH, encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:  # noqa: BLE001
                    data = {"leads": []}
            leads = data.setdefault("leads", [])
            now = datetime_now_iso()
            email = lead.get("email")
            existing = None
            if email:
                for x in leads:
                    if x.get("email") == email:
                        existing = x
                        break
            if existing is not None:
                existing.update({k: v for k, v in lead.items()
                                 if v and k != "source"})
                existing["last_seen"] = now
                existing.setdefault("touchpoints", 0)
                existing["touchpoints"] += 1
            else:
                lead["id"] = "lead-" + uuid.uuid4().hex[:12]
                lead["created_at"] = now
                lead["last_seen"] = now
                lead["touchpoints"] = 1
                leads.append(lead)
                if len(leads) > _LEADS_CAP:
                    leads[:] = leads[-_LEADS_CAP:]
            with open(LEADS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:  # noqa: BLE001
        return False


def datetime_now_iso():
    try:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
    except Exception:  # noqa: BLE001
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# --------------------------------------------------------------------------
# 对话生成
# --------------------------------------------------------------------------
def _rule_reply(message):
    msg = (message or "").lower()
    best, best_score = _FALLBACK, 0
    for item in FAQ:
        score = sum(1 for k in item["keys"] if k.lower() in msg)
        if score > best_score:
            best, best_score = item["answer"], score
    return best


def _llm_reply(message, history):
    base = os.environ.get("LDA_CS_LLM_BASE_URL", "").rstrip("/")
    if not base:
        return None
    key = os.environ.get("LDA_CS_LLM_API_KEY", "")
    model = os.environ.get("LDA_CS_LLM_MODEL", "gpt-3.5-turbo")
    url = base + "/v1/chat/completions"
    msgs = [{"role": "system", "content": _SYSTEM_PROMPT}]
    for h in (history or [])[-6:]:
        role = h.get("role", "user")
        if role not in ("user", "assistant", "system"):
            role = "user"
        msgs.append({"role": role, "content": str(h.get("content", ""))})
    msgs.append({"role": "user", "content": str(message or "")})
    body = json.dumps({"model": model, "messages": msgs,
                       "temperature": 0.3, "max_tokens": 600}).encode("utf-8")
    try:
        import urllib.request
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + key} if key else
                    {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except Exception:  # noqa: BLE001
        return None


def chat(payload):
    """智能体客服主入口。

    payload: {message?, name?, company?, email?, phone?, wechat?, need?, history?}
    返回: {reply, lead_captured, suggestions?}
    """
    payload = payload or {}
    message = str(payload.get("message", "")).strip()
    structured = {k: payload.get(k) for k in
                  ("name", "company", "organization", "email", "phone",
                   "wechat", "need", "interest")}
    history = payload.get("history") or []

    # 1) 线索抽取（自由文本 + 结构化）
    lead = extract_lead(message, {k: v for k, v in structured.items()
                                  if v not in (None, "")})
    lead_captured = False
    if lead:
        lead_captured = collect_lead(lead)

    # 1.5) 引导模式（智能体做成引导型）：带用户走 3 分钟上手主线
    guide_step = payload.get("guide_step")
    guide_cmd = payload.get("guide_cmd")
    if guide_cmd == "start" or isinstance(guide_step, int):
        step = 0 if guide_cmd == "start" else max(0, min(int(guide_step), len(GUIDE_STEPS) - 1))
        s = GUIDE_STEPS[step]
        reply = ""
        if message:
            faq = _rule_reply(message)
            if faq != _FALLBACK:
                reply = faq
            else:
                llm = _llm_reply(message, history)
                if llm:
                    reply = llm
        if lead_captured:
            reply = (reply + "\n已记录您的联系方式，团队会尽快与您联系 🙌").strip()
        return {
            "reply": reply,
            "lead_captured": lead_captured,
            "guide": {"step": step, "total": len(GUIDE_STEPS),
                      "title": s["title"], "intro": s["intro"], "tip": s["tip"],
                      "anchor": s.get("anchor")},
            "suggestions": [],
        }

    # 2) 对话生成（LLM 优先，失败回退 FAQ）
    if not message and not lead:
        reply = ("您好，我是 LDA 智能体客服 👋 可以解答产品定位、验证红线、"
                 "光子/量子能力、上手方式、开源与商用、能力边界等问题；"
                 "也可以直接留姓名+公司+邮箱，我们安排专人对接。")
    else:
        reply = _llm_reply(message, history) or _rule_reply(message)

    # 3) 线索确认话术
    if lead_captured:
        reply = (reply.rstrip("。") + "。已记录您的联系方式，我们的团队会尽快与您联系 🙌")

    return {
        "reply": reply,
        "lead_captured": lead_captured,
        "suggestions": ["产品是什么", "验证为什么可信", "光子能力", "量子能力",
                        "如何快速上手", "价格与商用", "能力边界", "留个联系方式"],
    }
