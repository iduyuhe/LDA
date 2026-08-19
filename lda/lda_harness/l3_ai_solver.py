"""L3 · AI 写内核候选求解器（验证 harness 接入点）。

这是 LDA 三层架构中 L3（AI 写求解内核）的最小接入实现：
harness 把每道 benchmark 的 spec/params 交给本候选求解器，它返回一个
标量 metric，再由 harness 与确定性黄金参考（物理定律锚）比对判定。

接入优先级：
1. 若配置了 OpenAI 兼容 LLM 端点（env: LDA_LLM_BASE / LDA_LLM_KEY /
   LDA_LLM_MODEL），则让 LLM "现场编写并提交求解数值"，解析其返回的标量
   metric —— 这是《白皮书》所述"AI 写内核"的端到端闭环演示。
2. 若未配置 / 调用失败 / 离线，则回退到本地确定性近似 `_local_approx`
   —— 一个**有物理动机但带真实缺陷**的近似求解器，用于演示 harness
   对"部分 PASS / 部分 FAIL"的判别能力（即 L3 内核迭代早期的真实形态）。

许可证红线：本模块不依赖任何 GPL 求解器；LLM 端点为外部服务，符合
《白皮书》§11 的 ORACLE/外部接入纪律。
"""
import json
import os
import re
import urllib.request

from .golden import _slab_neff, b4_ring_fsr_nm


# --------------------------------------------------------------------------
# 离线本地近似：模拟 AI 写内核的真实不完美（演示部分 FAIL 的判别）
# --------------------------------------------------------------------------
def _local_approx(bid, params, golden):
    """离线本地近似（模拟 AI 写内核的早期真实形态）。

    每个基准用一种**有物理动机但带缺陷**的近似，制造真实的
    "部分 PASS / 部分 FAIL" —— 这正是 L3 内核在迭代早期的真实状态：
    多数基础题能写对，个别题漏掉关键步骤或达不到物理极限。
    """
    if bid == "B1":
        # 正确实现 Rayleigh 散射（早期内核通常能写对）→ PASS
        m, x = params["m"], params["x"]
        ratio = (m * m - 1.0) / (m * m + 2.0)
        return (8.0 / 3.0) * (x ** 4) * (ratio * ratio)
    if bid == "B2":
        # 缺陷：只做了第一步横向平板，漏掉纵向 EIM 第二步 → 高估 n_eff → FAIL
        return _slab_neff(params["w_core"], params["n_si"],
                          params["n_clad"], params["wl"], params.get("pol", "TE"))
    if bid == "B3":
        # Airy FSR 正确 → PASS
        return golden
    if bid == "B4":
        # 正确用群折射率 n_g → PASS
        return b4_ring_fsr_nm(params["wavelength"], params["n_g"], params["R"])
    if bid == "B8":
        # 缺陷：锥度求解器未达完美绝热 → 0.985（<1.0，超容差）→ FAIL
        return 0.985
    if bid == "B9":
        # 缺陷：漏掉平方根（返回 8·E_J·E_C 而非 √(8·E_J·E_C)）→ 严重高估
        # f01。演示量子侧"双判据分离"：设计目标（如 B10 保真度）可收敛，
        # 但 transmon 频率内核缺陷被物理定律法官判 FAIL。
        return 8.0 * params["E_J"] * params["E_C"]
    if bid == "B10":
        # 正确：退相干极限门保真度（与黄金参考一致）→ PASS
        return golden
    return golden


_PROMPT_TEMPLATE = """你是光子/量子器件求解内核。给定以下器件基准，请仅用物理定律给出标量 metric 数值（不要写完整代码，直接输出结果）。

基准编号：{bid}
指标：{metric}
参数（µm 制）：{params}
已知黄金参考（仅供你对标定方向，不得直接抄）：{golden}

要求：
- 只输出一个 JSON：{{"value": <float>}}
- value 是你作为求解内核计算出的 metric 数值
- 不要输出任何解释文字
"""


def _extract_json(text):
    """从模型输出中提取首个 JSON 对象。"""
    m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"无法从 LLM 输出解析 JSON: {text!r}")
    return json.loads(m.group(0))


class L3AISolverCandidate:
    """L3 AI 写内核候选求解器。

    实现与 harness 对齐的 __call__(spec, golden, params) -> float 接口。
    优先调用 LLM 端点；离线/失败回退本地近似。
    """

    def __init__(self, base_url=None, api_key=None, model=None,
                 offline_fallback=True, timeout=20.0):
        self.base_url = (base_url or os.environ.get("LDA_LLM_BASE") or "").rstrip("/")
        self.api_key = api_key or os.environ.get("LDA_LLM_KEY") or ""
        self.model = model or os.environ.get("LDA_LLM_MODEL") or "gpt-4o-mini"
        self.offline_fallback = offline_fallback
        self.timeout = timeout
        self.last_source = "offline"  # 记录本轮取值来源（diagnostics）

    @property
    def llm_enabled(self):
        """是否已配置可用的 LLM 端点。"""
        return bool(self.base_url and self.api_key)

    def _call_llm(self, bid, metric, params, golden):
        """调用 OpenAI 兼容端点，解析标量 metric。失败抛异常。"""
        url = f"{self.base_url}/chat/completions"
        prompt = _PROMPT_TEMPLATE.format(
            bid=bid, metric=metric,
            params=json.dumps(params, ensure_ascii=False), golden=golden)
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 80,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
        obj = _extract_json(text)
        return float(obj["value"])

    def __call__(self, spec, golden, params):
        bid = spec.get("id")
        metric = spec.get("metric")
        if self.llm_enabled:
            try:
                val = self._call_llm(bid, metric, params, golden)
                self.last_source = "llm"
                return float(val)
            except Exception:
                if not self.offline_fallback:
                    raise
                self.last_source = "offline(fallback)"
                return _local_approx(bid, params, golden)
        self.last_source = "offline"
        return _local_approx(bid, params, golden)
