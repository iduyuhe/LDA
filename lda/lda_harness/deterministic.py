"""LDA 确定性报告 I/O —— 让「相同输入 ⇒ 相同字节」成为可 CI 校验的性质。

## 为什么要它

本仓库 `reports*/` 下的报告是**受版本控制的验证证据**：拿它们做
`git diff` 应当只反映「证据变了」，而**不是**「又跑了一次」。

历史痛点（v0.9.74 及之前）：每次跑 harness / smoke 都会把受跟踪报告重写成
带 wall-clock 时间戳、耗时、浮点末位抖动的新内容 ⇒ `git status` 常年一片红，
提交时要么误带噪声、要么每次手动 `git checkout --` 掩盖。这不是「文件脏」，
是**生成器非确定性**。

## 唯一口径（三件事）

1. **剔除 volatile 键**：`generated_at` / `elapsed_s` / `total_s` / … 一律不进
   受跟踪产物（任意嵌套层级）。需要留痕时，调用方写进**未跟踪**的
   `<name>.run.json`，不进 git。
2. **浮点归一**：所有 float 取 `SIGNIFICANT_DIGITS`（=9）位有效数字，吸收
   `1.0000000000000002` 这类末位抖动**以及线程预算不同引起的 BLAS 归约漂移**；
   物理量 9 位有效数字远够。
3. **写盘统一**：UTF-8 + `newline="\\n"`（不随平台翻 CRLF）、确定性缩进。

## 红线

- 归一化只发生在**写文件边界**（`dumps` / `write_text` / `write_json`），
  **不得**在内存中改动调用方的对象 —— 免得打断真实计算与断言。
- 归一化必须**可证伪**：改一个真实 golden 值务必让字节变化。护栏
  `run_report_determinism_smoke.py` 正反两面都测。
"""
from __future__ import annotations

import json
import os
import re

# 有效数字位数（v0.9.75b：12 → 9）。
#
# 🔴 血案（2026-09-13 实测）：环境变量线程预算不同 ⇒ BLAS/FFT 归约顺序不同 ⇒
# 浮点末位漂移。全库唯一受影响的是 B15 的 candidate：
#   多线程（默认全核）1.550408355**9**3  vs  受限 10 线程 1.550408355**9**2
# 相对抖动 6.45e-12 —— **恰好等于 12 位有效数字的相邻间距**，故 12 位无法吸收，
# 导致「CI（注入线程预算）跑」与「本地手跑」产物字节不同（`git status` 常红）。
#
# 取 9 位：相邻间距 ~1e-8 相对，对 6.45e-12 抖动余量 ~1500×（抖动跨舍入边界的
# 概率 < 1e-4）⇒ 线程数、CPU 亲和性、BLAS 归约顺序等环境因素全部被吸收。
# 物理上 9 位有效数字仍远超任何工程容差（本库最紧 tol 约 1e-4，相对 ~1e-2），
# 且真实锚变更（模型/方法学改动）量级 ≥1e-6，仍可被 ⑦ 反向判据检出。
SIGNIFICANT_DIGITS = 9

# 不计入受跟踪产物的易变键（任意嵌套层级命中即剔除）。
VOLATILE_KEYS = frozenset({
    "generated_at",
    "elapsed",
    "elapsed_s",
    "total_s",
    "time_total_s",
    "time_build_s",
    "time_lvs_s",
    "duration_s",
    "timestamp",
    "run_at",
    "created_at",
    "updated_at",
    "fetched_at",
    "imported_at",
    "resolved_at",
    "paid_at",
    "approved_at",
    "rejected_at",
    "accepted_at",
})

# 生成物里的「时间痕迹」提示：footnote 用，避免读者以为报告没过期。
DETERMINISM_FOOTNOTE = (
    "*本报告为**确定性生成物**：相同输入 ⇒ 字节一致，不含 wall-clock 时间戳与耗时。"
    "生成时刻以 git 提交时间为准。*"
)


def round_float(v):
    """单个浮点归一（供 markdown 等自排版格式化复用）。非 float 原样返回。"""
    if isinstance(v, float) and v == v and v not in (float("inf"), float("-inf")):
        return float(f"{v:.{SIGNIFICANT_DIGITS}g}")
    return v


def canon(obj):
    """递归归一：剔除 VOLATILE_KEYS（任意层级）+ float 取有效数字。

    🔴 v0.9.102 防御层：numpy 标量（np.float64/np.bool_/np.int64…）非 Python
    float/bool/int 子类 ⇒ json.dumps 抛 TypeError。统一在归一层兜底转原生，
    杜绝「判决链 numpy 标量泄漏进报告」类 bug（falsifiability ⑨ 同因）。
    """
    if isinstance(obj, dict):
        return {k: canon(v) for k, v in obj.items() if k not in VOLATILE_KEYS}
    if isinstance(obj, (list, tuple)):
        return [canon(v) for v in obj]
    # numpy 标量泄漏兜底（不 import numpy，仅按类型归属判定，零额外开销）
    _mod = type(obj).__module__
    if _mod == "numpy" or (_mod is not None and _mod.startswith("numpy.")):
        try:
            obj = obj.item()
        except Exception:
            return obj
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):  # nan/inf 原样
            return obj
        return float(f"{obj:.{SIGNIFICANT_DIGITS}g}")
    if isinstance(obj, int):
        return obj
    return obj


def dumps(obj, indent=2, default=None) -> str:
    """确定性 JSON 文本（UTF-8 安全、无平台相关格式）。

    `default` 透传给 json.dumps（如 `str`），用于兜底不可序列化对象。
    """
    kw = {} if default is None else {"default": default}
    return json.dumps(canon(obj), ensure_ascii=False, indent=indent, **kw)


def write_text(path: str, text: str) -> None:
    """统一写盘：UTF-8 + LF，保证末尾恰好一个换行。"""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def write_json(path: str, obj, indent=2, default=None) -> None:
    """确定性 JSON 落盘（= write_text(path, dumps(obj))）。"""
    write_text(path, dumps(obj, indent, default))


def eol_lf(data: bytes) -> bytes:
    """把字节流行尾归一为 LF（`\\r\\n` → `\\n`）；仅用于**比对**，不用于写盘。

    🔴 存在理由（v0.9.199）：本仓库签出侧 git `core.autocrlf=true`（实测
    `git checkout-index` 产出 CRLF），而 `write_json` 写 LF ⇒ 直接拿「工作树
    快照字节」与「现算字节」裸比会**假红**。行尾是传输属性、非报告内容，
    因此「快照 == 现算」这类判据必须先 `eol_lf` 再比。
    内容真变更（值/字段/判定）经归一后仍必不同 —— 检查强度不减。
    """
    if not data:
        return data
    return data.replace(b"\r\n", b"\n")


# ============================================================
# 「演示流程时刻」清洗（v0.9.199 · D-94~D-98 同族专项）
# ============================================================
# 生态流生成器（D-94~D-98）的报告内嵌两类**非证据**的易变语义：
#   ① wall-clock ISO 时间戳（submitted_at / reviewed_at / landed_at /
#      published_at / ts …），且大量嵌在**字符串内部**（detail 是 dict 的
#      str() 串、patch 是含时间戳的 diff 文本）⇒ canon 的**键**剔除够不着；
#   ② 随机 tmpdir 名（tempfile.mkdtemp(prefix="lda_*_")，patch_path 等）。
# 这些时刻/目录名描述的是「演示流程何时在哪儿跑过一次」，不是交付事实 ——
# 与 d93 的 `date → d93_delivery_date`（交付日固定）同理：**在写边界归一为
# 哨兵**，保留 schema（字段还在、值为 <ts>），字节即确定。
#
# 🔴 红线不变：scrub 只在写边界调用（`det.write_json(p, det.scrub(r))`），
#    返回新对象，不动调用方内存对象。
# 🔴 不得误洗合法文本：`lda_harness/golden.py` 这类普通词不含「随机后缀 +
#    Temp 目录上下文」，两个正则都够不着（run_report_determinism_smoke ⑬
#    有常驻反例判据锁住这一点）。
SCRUB_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
# tmpdir 名只允许出现在「Temp\<dir>\」路径上下文里（前后都有分隔符），
# 防止误伤 `lda_harness` / `lda_webui` 等普通词。
SCRUB_TMP_RE = re.compile(r"(?<=Temp\\)lda_[A-Za-z0-9_]+(?=\\)")
SCRUB_TS_SENTINEL = "<ts>"
SCRUB_TMP_SENTINEL = "<tmpdir>"


def scrub(obj):
    """递归清洗字符串内嵌 wall-clock / 随机 tmpdir（返回新对象）。

    与 `canon` 分工：canon 管键剔除 + 浮点归一 + numpy 兜底（写边界已自动
    应用）；scrub 只管**字符串内部**的易变语义。两者组合 = 完整确定性口径：
    `det.write_json(path, det.scrub(report))`。
    """
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [scrub(v) for v in obj]
    if isinstance(obj, str):
        obj = SCRUB_TS_RE.sub(SCRUB_TS_SENTINEL, obj)
        return SCRUB_TMP_RE.sub(SCRUB_TMP_SENTINEL, obj)
    return obj
