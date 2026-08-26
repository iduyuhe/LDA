"""LDA LLM 提案生成器（发动期 · Phase 4 生成侧 LLM 接入）。

红线（生成与判决分离——五共识 ② 的工程边界）：
  本模块【只生成候选参数】，不含任何 PASS/FAIL 判决逻辑——
  LLM 输出经结构校验后送 proposal_compiler 的同一条四锚判决管线
  （S1/S5/S2/S7 死标量），LLM 无法跳过锚。LLM 可替换（网格/启发式/
  任何模型），判决不可触碰。

配置（OpenAI 兼容端点，与 L3AISolverCandidate 同一 env 约定）：
  LDA_LLM_BASE   如 http://localhost:11434/v1（ollama）或 https://api.xxx/v1
  LDA_LLM_KEY    API key（本地 ollama 可为任意非空串）
  LDA_LLM_MODEL  模型名（默认 gpt-4o-mini）

降级语义：未配置 / 调用失败 / 输出全垃圾 → 返回空列表，
调用方（proposal_compiler）降级纯网格——核心零依赖优雅降级铁律。
"""
from __future__ import annotations

import json
import math
import os
import urllib.request
from typing import Any, Dict, List

# ---- 提案参数合法域（结构校验边界——LLM 输出钳制，越界丢弃） ----
_PARAM_BOUNDS = {
    "p_tx_dbm": (-10.0, 20.0),        # 激光器功率 dBm
    "channel_spacing_ghz": (12.5, 400.0),  # 信道间隔（DWDM grid 下界 12.5GHz）
    "filter_bw_ghz": (5.0, 200.0),     # 滤波带宽 GHz
    "wg_length_cm": (0.1, 10.0),       # 波导长 cm
    "n_channels": (1, 64),             # 信道数
    "link_budget_db": (0.0, 20.0),     # 余量要求 dB
}

_PROMPT_TEMPLATE = """你是光子芯片系统架构提案器。给定 WDM 链路功能需求，提出 {n} 个不同的候选设计参数组合。

需求：信道数={n_channels}，信道间隔={channel_spacing_ghz}GHz，滤波带宽={filter_bw_ghz}GHz，链路余量要求={link_budget_db}dB，激光功率={p_tx_dbm}dBm，波导长={wg_length_cm}cm。

每个候选给出 4 个参数：p_tx_dbm（-10 到 20 dBm）、channel_spacing_ghz（12.5 到 400）、filter_bw_ghz（5 到 200，须小于间隔）、wg_length_cm（0.1 到 10）。

候选应多样化（不同功率档/间隔/带宽组合），物理合理（光栅耦合 -3dB×2、波导 3dB/cm、环形 -0.5dB、探测器 -20dBm 灵敏度）。
只输出 JSON 数组，格式：[{{"p_tx_dbm": 0.0, "channel_spacing_ghz": 100.0, "filter_bw_ghz": 50.0, "wg_length_cm": 1.0}}, ...]"""


def _extract_json_array(text: str) -> List[Any]:
    """从 LLM 回复中提取 JSON 数组（容忍 markdown 代码块包裹）。"""
    t = text.strip()
    if "```" in t:
        # 取代码块内容
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


class LLMProposer:
    """LLM 提案生成器——只出参数，不判对错（判决在锚管线）。"""

    def __init__(self, base_url=None, api_key=None, model=None,
                 timeout=30.0):
        self.base_url = (base_url or os.environ.get("LDA_LLM_BASE") or "").rstrip("/")
        self.api_key = api_key or os.environ.get("LDA_LLM_KEY") or ""
        self.model = model or os.environ.get("LDA_LLM_MODEL") or "gpt-4o-mini"
        self.timeout = timeout
        self.last_source = "unconfigured"  # diagnostics：llm / unconfigured / error

    @property
    def enabled(self) -> bool:
        """是否已配置 LLM 端点。"""
        return bool(self.base_url and self.api_key)

    def validate_params(self, cand: Dict[str, Any]) -> bool:
        """结构校验：4 参数全为有限数且在合法域内（垃圾丢弃，不重试）。

        红线注：这是【输入合法性检查】，不是设计判决——判决在四锚。
        """
        if not isinstance(cand, dict):
            return False
        try:
            for k, (lo, hi) in _PARAM_BOUNDS.items():
                if k in cand:
                    v = float(cand[k])
                    if not math.isfinite(v) or not (lo <= v <= hi):
                        return False
            # 滤波带宽必须小于间隔（结构约束，物理常识）
            bw = float(cand.get("filter_bw_ghz", 50.0))
            sp = float(cand.get("channel_spacing_ghz", 100.0))
            return bw < sp
        except (TypeError, ValueError, KeyError):
            return False

    def propose(self, req: Dict[str, Any], n: int = 3) -> List[Dict[str, Any]]:
        """生成 n 个候选参数组合；失败/未配置返回空列表（调用方降级网格）。"""
        if not self.enabled:
            self.last_source = "unconfigured"
            return []
        try:
            prompt = _PROMPT_TEMPLATE.format(
                n=n,
                n_channels=req.get("n_channels", 4),
                channel_spacing_ghz=req.get("channel_spacing_ghz", 100.0),
                filter_bw_ghz=req.get("filter_bw_ghz", 50.0),
                link_budget_db=req.get("link_budget_db", 3.0),
                p_tx_dbm=req.get("p_tx_dbm", 0.0),
                wg_length_cm=req.get("wg_length_cm", 1.0))
            body = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,   # 提案要多样性（判决交给锚）
                "max_tokens": 500,
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
            # 结构校验过滤（垃圾丢弃不重试）
            valid = []
            for c in raw:
                if isinstance(c, dict) and self.validate_params(c):
                    valid.append({k: float(c[k]) for k in
                                  ("p_tx_dbm", "channel_spacing_ghz",
                                   "filter_bw_ghz", "wg_length_cm")
                                  if k in c})
            self.last_source = "llm"
            return valid
        except Exception:  # noqa: BLE001 —— 网络超时/格式错全降级
            self.last_source = "error(degraded)"
            return []
