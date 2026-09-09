"""LDA LLM 红队（出题攻击生成器 · 发动期 Phase 4 生成侧红队）。

与 LLMProposer（蓝队/生成器）对称：本模块【只出对抗候选】，不判 PASS/FAIL——
红队出题由锚管线判卷（feasible_domain + 四锚死标量），红队不进判决路径。

纪律（五共识 ② 红蓝分工 · 见 MEMORY「多智能体红蓝队分工纪律」）：
- 红队模型必须 ≠ 生成器模型（防同源假独立）→ 由 run_redteam_llm_smoke 强制。
- 红队自身也必须被证伪：命中率 = 被锚确认的真实缺陷数 ÷ 出题数（死标量）。
  健康管线缺陷=0 ⇒ 命中率=0/N（好）；一旦回归引入漏洞，漏过数>0 ⇒ 命中率
  飙升即告警。红队的价值=覆盖面（出题数 + 命中锚的多样性），非判决。

配置（OpenAI 兼容端点，与 LLMProposer 同一约定，仅前缀不同）：
  LDA_REDTEAM_BASE   如 https://api.xxx/v1（缺省同 LDA_LLM_BASE）
  LDA_REDTEAM_KEY    API key
  LDA_REDTEAM_MODEL  模型名（默认 gpt-4o-mini）

降级语义：未配置 / 调用失败 / 输出全垃圾 → 返回空列表，
调用方（run_redteam_llm_smoke）回退规则式红队——核心零依赖优雅降级铁律。
"""
from __future__ import annotations

import json
import math
import os
import urllib.request
from typing import Any, Dict, List, Optional

_REDTEAM_PROMPT = """你是光子芯片验证管线的对抗红队测试员。你的任务不是设计好方案，而是专门构造【应当被验证锚拦下】的恶意/临界候选——参数在工程界内，但物理上违规，用来测试锚是否真能抓住它们。

具体攻击配方（参数在界内、但应触发对应锚 FAIL）：
- 攻 S1（功率预算）：极低 p_tx（-8~-10 dBm）+ 长波导（8~10 cm），使余量 < 要求
- 攻 S5（最坏情况）：长波导使最坏余量 < 0
- 攻 S7（统计最坏 p5）：把余量压到临界（p_tx 取使 margin 接近 0 的值），使统计 p5 < 0
- 攻 S2（频率碰撞）：filter_bw 设到非常接近 spacing（如 spacing=50, bw=47~49），制造临界——纯 WDM 下界内难真碰撞，标注 target=S2 作覆盖即可

不要给越界值（那会被结构校验钳掉，无测试价值）。每个候选必须带 target 字段（S1/S2/S5/S7 之一），说明你想击穿的锚。

只输出 JSON 数组，格式：
[{{"target": "S1", "p_tx_dbm": -9.0, "channel_spacing_ghz": 100.0, "filter_bw_ghz": 30.0, "wg_length_cm": 9.0}}, ...]"""


def _extract_json_array(text: str) -> List[Any]:
    """从 LLM 回复中提取 JSON 数组（容忍 markdown 代码块包裹）。"""
    t = text.strip()
    if "```" in t:
        parts = t.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("["):
                t = p
                break
    start = t.find("[")
    end = t.rfind("]")
    if start < 0 or end <= start:
        raise ValueError("回复中无 JSON 数组")
    return json.loads(t[start:end + 1])


class RedTeamProposer:
    """LLM 红队出题器——只出对抗候选，不判对错（判卷在锚管线）。"""

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None,
                 model: Optional[str] = None, timeout: float = 30.0):
        self.base_url = (base_url or os.environ.get("LDA_REDTEAM_BASE")
                         or os.environ.get("LDA_LLM_BASE") or "").rstrip("/")
        self.api_key = api_key or os.environ.get("LDA_REDTEAM_KEY") or ""
        self.model = model or os.environ.get("LDA_REDTEAM_MODEL") or "gpt-4o-mini"
        self.timeout = timeout
        self.last_source = "unconfigured"  # diagnostics：llm / unconfigured / error

    @property
    def enabled(self) -> bool:
        """是否已配置红队端点。"""
        return bool(self.base_url and self.api_key)

    def propose_attacks(self, req: Dict[str, Any],
                        blue_candidates: Optional[List[Dict[str, Any]]] = None,
                        n: int = 4) -> List[Dict[str, Any]]:
        """生成 n 个对抗候选参数组合；失败/未配置返回空列表（调用方降级规则式）。

        返回 dict 列表，每项为 4 参数浮点（仅保留含 4 键且为有限数的项）。
        不做结构钳制——红队允许边界/临界值，钳制由评卷方（validate_params）执行。
        """
        if not self.enabled:
            self.last_source = "unconfigured"
            return []
        try:
            blue_summary = ""
            if blue_candidates:
                items = []
                for c in blue_candidates[:4]:
                    rs = c.get("req_source", {})
                    ls = c.get("link_spec", {})
                    items.append(
                        f"(p_tx={rs.get('p_tx_dbm', ls.get('p_tx_dbm'))}, "
                        f"spacing={rs.get('channel_spacing_ghz')}, "
                        f"bw={rs.get('filter_bw_ghz')}, "
                        f"wg={ls.get('wg_length_cm')})")
                blue_summary = "蓝队已提候选：" + "; ".join(items) + "。"

            prompt = _REDTEAM_PROMPT.format(n=n)
            if blue_summary:
                prompt += "\n" + blue_summary
            body = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.9,   # 红队要多样性/对抗性（判卷交给锚）
                "max_tokens": 600,
            }
            url = f"{self.base_url}/chat/completions"
            rq = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {self.api_key}"},
                method="POST")
            with urllib.request.urlopen(rq, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = data["choices"][0]["message"]["content"]
            raw = _extract_json_array(text)
            valid = []
            for c in raw:
                if not isinstance(c, dict):
                    continue
                try:
                    item = {k: float(c[k]) for k in
                            ("p_tx_dbm", "channel_spacing_ghz",
                             "filter_bw_ghz", "wg_length_cm") if k in c}
                except (TypeError, ValueError):
                    continue
                if len(item) != 4 or not all(math.isfinite(v) for v in item.values()):
                    continue
                tgt = c.get("target")
                if isinstance(tgt, str) and tgt.upper() in ("S1", "S2", "S5", "S7"):
                    item["target"] = tgt.upper()
                valid.append(item)
            self.last_source = "llm"
            return valid
        except Exception:  # noqa: BLE001 —— 网络超时/格式错全降级
            self.last_source = "error(degraded)"
            return []
