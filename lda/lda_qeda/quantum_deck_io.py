# -*- coding: utf-8 -*-
"""D-225 · 量子 deck **导入链**（净增 0 锚 · 能力层）。

════════════ 为什么单独一个模块，而不是塞进 `quantum_deck.py` ════════════
D-215 的 `quantum_deck.py` 刻意保持**零文件 IO**（门禁 F3 直接断言其源码无 `open(`）——
契约层只回答「这份 deck 合法吗」，不回答「它从哪来」。本模块只做后者：

    路径 / dict / 环境变量  ──▶  已校验 deck + **可追溯的加载器元信息**

把两件事塞一起会同时破坏 F3 与职责边界（IO 可被 mock，契约不该被 mock）。

════════════ 三条硬设计（都是护栏，不是装饰）════════════
① **加载器元信息只回带、不进判决**（与 D-215 ③ 同一条红线）：
   `loader` 段带 source / basename / sha256 / env_var，但用 `drc_with_deck` 跑出的
   判决必须与「程序内构造的同限值 deck」**逐字相同**（门禁 G7 机器核验）。
   改文件路径不改判决，改限值才改判决。
② **sha256 记账、不写时间戳**：同一份文件 ⇒ 同一个 sha（跨机器可对拍）；
   写 `loaded_at` 会让 `run_report_determinism_smoke`（相同输入 ⇒ 字节一致）红 ——
   这是**确定性优先于"看起来完整"**的一次取舍。
③ **env 通道独立**：`LDA_QUANTUM_DECK`，**不与光子侧 `LDA_FOUNDRY_DECK` 混用**。
   两域限值键集不同（10 键 vs 3 键），混用必然错配；门禁 G6 对此设正反两向。

════════════ 边界（诚实披露）════════════
- 本层**不校验 NDA 凭据真伪**（与 D-215 同口径）：只保证 `attestation` 字段存在且非空白。
  `FOUNDRY_SIGNOFF` 的成立仍依赖人工作业与真实 NDA 文件。
- **不解析任何商业 deck 格式**：只吃本平台的 `lda_quantum_foundry_deck_v1` JSON。
  商业 deck（DRC 厂商私有格式）本平台不沾，属外部依赖。
- `loader` 段与 D-215 的 meta 段同属"元数据"，**同样不进判决路径**。
- 红线照旧：纯 stdlib · 零第三方 · 零网络 · 零 LLM · 不新增锚。
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "ENV_DECK_VAR",
    "LOADER_SCHEMA",
    "load_quantum_deck",
    "load_quantum_deck_from_env",
    "loader_provenance",
    "run_selfchecks",
]

#: 环境变量名（**独立于光子侧 `LDA_FOUNDRY_DECK`**，两域键集不同不可混用）
ENV_DECK_VAR = "LDA_QUANTUM_DECK"

#: 加载器元信息的 schema 标识（用于区分"文件加载"与"程序内构造"）
LOADER_SCHEMA = "lda_quantum_deck_loader_v1"

#: 认作"路径"的入参类型（bytes 也接受，便于跨平台调用）
_PATHLIKE: Tuple[type, ...] = (str, bytes, os.PathLike)


# ═══════════════════════════ 加载 ═══════════════════════════
def load_quantum_deck(path_or_dict: Any,
                      *,
                      expected_domain: Optional[str] = None) -> Dict[str, Any]:
    """加载并校验一份量子 foundry deck（JSON 文件路径 或 已解析 dict）。

    处理顺序（每一步失败都抛具名错误，不静默回退）：
      1. 路径 ⇒ 文件不存在 `FileNotFoundError`；非 UTF-8 / 非法 JSON ⇒ `ValueError`（带行列）
      2. 结构 ⇒ 交给 `quantum_deck.validate_deck`（schema / 键集守恒 / 有限非负 / NDA 凭据）
      3. `expected_domain` ⇒ 域不符即拒（防"拿超导 deck 跑光子 DRC"）
      4. 拒绝后**不留半成品**：返回体是校验后的副本，附加 `loader` 段

    返回：
      `{schema, domain, foundry, process, version, provenance, attestation, note, limits,
        loader: {schema, source, basename, sha256, env_var, domain_checked}}`

    🔴 `loader` 段**不进判决**：`deck_limits()` / `drc_with_deck()` 会先过
    `validate_deck`，而它只取白名单字段 ⇒ `loader` 被自然剥离。这是刻意的：
    契约层不认识"加载器"，所以任何判决都不可能依赖它。
    """
    from lda_qeda import quantum_deck as QD   # 单一真源（契约层）

    raw = path_or_dict
    source, basename, sha = "dict", None, None

    if isinstance(raw, _PATHLIKE):
        p = os.fspath(raw)
        if isinstance(p, bytes):
            p = p.decode("utf-8", "replace")
        if not os.path.isfile(p):
            raise FileNotFoundError("量子 deck 文件未找到：%s" % p)
        with open(p, "rb") as fh:
            data = fh.read()
        sha = hashlib.sha256(data).hexdigest()
        basename = os.path.basename(p)
        try:
            raw = json.loads(data.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise ValueError("deck 文件非 UTF-8 编码：%s" % exc)
        except json.JSONDecodeError as exc:
            raise ValueError("deck 文件非合法 JSON：%s（第 %d 行第 %d 列）"
                             % (exc.msg, exc.lineno, exc.colno))
        source = "file"

    if not isinstance(raw, dict):
        raise TypeError("deck 必须是 dict 或 JSON 文件路径，实际 %s"
                        % type(raw).__name__)

    deck = QD.validate_deck(raw)             # 不合规 ⇒ 此处抛，不留半成品

    if expected_domain is not None and deck["domain"] != expected_domain:
        raise ValueError("deck.domain=%r 与期望 %r 不符 ⇒ 拒绝（防错配域）"
                         % (deck["domain"], expected_domain))

    out = dict(deck)
    out["loader"] = {
        "schema": LOADER_SCHEMA,
        "source": source,
        "basename": basename,
        "sha256": sha,
        "env_var": None,
        "domain_checked": expected_domain is not None,
    }
    return out


def load_quantum_deck_from_env(*,
                               required: bool = False,
                               expected_domain: Optional[str] = None
                               ) -> Optional[Dict[str, Any]]:
    """从环境变量 `LDA_QUANTUM_DECK` 指定的路径加载 deck。

    - 变量未设置 / 空白 ⇒ `required=False` 返 `None`（调用方回落自建 deck）；
      `required=True` ⇒ `FileNotFoundError`（**不给"看起来有 deck"的假象**）。
    - 加载成功 ⇒ `loader.env_var` 记下实际生效的变量名，便于审计"这份判决是用哪条通道喂的"。
    """
    p = os.environ.get(ENV_DECK_VAR)
    if p is None or not str(p).strip():
        if required:
            raise FileNotFoundError(
                "环境变量 %s 未设置或为空（required=True）" % ENV_DECK_VAR)
        return None
    deck = load_quantum_deck(str(p).strip(), expected_domain=expected_domain)
    deck["loader"]["env_var"] = ENV_DECK_VAR
    return deck


def loader_provenance(deck: Dict[str, Any]) -> Dict[str, Any]:
    """取出加载器元信息；**程序内构造的 deck 没有它** ⇒ `ValueError`。

    这条"有/没有"的区分本身是判据基础：对外材料里若声称"来自 NDA deck 文件"，
    必须能拿出 `loader.sha256` 与真实文件对得上（门禁 G2 核验），光写 provenance 字段不算。
    """
    lp = (deck or {}).get("loader") if isinstance(deck, dict) else None
    if not isinstance(lp, dict) or lp.get("schema") != LOADER_SCHEMA:
        raise ValueError("该 deck 不带加载器元信息"
                         "（程序内构造而非 load_quantum_deck 加载）")
    return dict(lp)


# ═══════════════════════════ 自检（门禁同源调用）═══════════════════════════
def run_selfchecks(verbose: bool = False) -> bool:
    """模块自检。全部为契约/错误路径断言；**不写任何文件**（文件路径类由门禁用 tmpdir 验）。"""
    from lda_qeda import quantum_deck as QD

    res: List[Tuple[str, bool]] = []

    def chk(name: str, cond: bool) -> None:
        res.append((name, bool(cond)))

    # ① dict 加载：source=dict 且 sha 为 None（不假装来自文件）
    sb = QD.self_built_deck("photonic")
    d1 = load_quantum_deck(sb)
    lp1 = loader_provenance(d1)
    chk("① dict 加载 ⇒ source=dict ∧ sha256=None ∧ 限值逐键相同",
        lp1["source"] == "dict" and lp1["sha256"] is None
        and d1["limits"] == sb["limits"])

    # ② loader 段可被 loader_provenance 读出，但不进 validate 的返回体
    chk("② loader 段只回带：validate_deck(loaded) 不含 loader（契约层不认识它）",
        "loader" not in QD.validate_deck(d1)
        and "loader" in d1)

    # ③ 程序内构造的 deck ⇒ loader_provenance 必抛
    try:
        loader_provenance(sb)
        chk("③ 程序内构造的 deck ⇒ loader_provenance 必抛", False)
    except ValueError:
        chk("③ 程序内构造的 deck ⇒ loader_provenance 必抛", True)

    # ④ 非法 schema ⇒ 透传契约层的 ValueError（不静默补默认）
    try:
        bad = dict(sb, schema="bogus_schema")
        load_quantum_deck(bad)
        chk("④ 非法 schema ⇒ ValueError（不静默兜底）", False)
    except ValueError:
        chk("④ 非法 schema ⇒ ValueError（不静默兜底）", True)

    # ⑤ 缺键 ⇒ 透传（键集守恒在加载链上仍然生效）
    try:
        bad = json.loads(json.dumps(sb))
        bad["limits"].pop(sorted(bad["limits"])[0])
        load_quantum_deck(bad)
        chk("⑤ 缺键 ⇒ ValueError（键集守恒不被加载绕开）", False)
    except ValueError:
        chk("⑤ 缺键 ⇒ ValueError（键集守恒不被加载绕开）", True)

    # ⑥ expected_domain 不符 ⇒ 拒
    try:
        load_quantum_deck(sb, expected_domain="superconducting")
        chk("⑥ expected_domain 不符 ⇒ 拒", False)
    except ValueError:
        chk("⑥ expected_domain 不符 ⇒ 拒", True)

    # ⑦ env 未设 ⇒ 非 required 返 None；required ⇒ 抛
    _old = os.environ.pop(ENV_DECK_VAR, None)
    try:
        none_ok = load_quantum_deck_from_env() is None
        try:
            load_quantum_deck_from_env(required=True)
            req_ok = False
        except FileNotFoundError:
            req_ok = True
    finally:
        if _old is not None:
            os.environ[ENV_DECK_VAR] = _old
    chk("⑦ env 未设 ⇒ 非 required 返 None ∧ required=True 抛 FileNotFoundError",
        none_ok and req_ok)

    # ⑧ 确定性：同一 dict 加载两次，除 loader 外逐键相同（无时间戳/随机量）
    a = load_quantum_deck(sb)
    b = load_quantum_deck(sb)
    a.pop("loader"), b.pop("loader")
    chk("⑧ 确定性：同 dict 两次加载除 loader 外逐键相同（无时间戳）",
        json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
        and "loaded_at" not in json.dumps(load_quantum_deck(sb), sort_keys=True))

    ok = all(v for _, v in res)
    if verbose:
        for n, v in res:
            print(("  [PASS] " if v else "  [FAIL] ") + n)
    return ok


if __name__ == "__main__":
    print("quantum_deck_io 自检：",
          "ALL PASS" if run_selfchecks(verbose=True) else "FAIL")
