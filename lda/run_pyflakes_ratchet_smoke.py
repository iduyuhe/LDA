# -*- coding: utf-8 -*-
"""静态卫生棘轮护栏（v0.9.112 · 波次 1 · 源自 2026-09-19 全面代码审计 F-11/F-12/F-13/F-15）。

防什么
------
**"清理过" ≠ "保持干净"**。2026-09-19 全面代码审计实测受跟踪 507 个 .py 有
pyflakes 告警 F401×244 / F841×71 / F541×25 / F811×4（共 344 条）。v0.9.112 波次 1
完成清理后，若没有任何守卫，下一批新代码可以**悄悄**重新引入死导入 / 死变量 /
空占位 f-string，而全绿依旧——审计成果随时间蒸发。本 smoke 把清理后的基线钉成
**棘轮**：只许降，不许升。

口径（死标量，LLM 不进判决路径）
--------------------------------
  ① 受跟踪 + 未跟踪(非 ignore) 的 .py（`git ls-files --cached --others`，排除三方
     隔离区）→ pyflakes 全量扫描
  ② 逐类型计数 ≤ 棘轮基线（见 `_RATCHET`）
  ③ pyflakes 解析错误 == 0（语法全部可编译）
  ④ pyflakes 缺失 ⇒ FAIL（与 scipy/jsonschema 同范式：核心门禁依赖缺失=红，**不**静默跳过）
  ⑤ 🔴 反向测试（两条）：把基线调低 1 / 合成超限计数 ⇒ 违规检测器**必报**
     （铁律：没被验证过的护栏不算护栏——证明棘轮真会响，非假绿）

为何 F401 基线不是 0
-------------------
244 处中大量是**合法的 re-export / 契约探针**，已实证三条通道：
① `lda_webui.app` 的 `shelf_status` 被 `run_shelf_*_smoke` 外部 from-import；
② `lda_harness.golden` 的 `s7/s8` 统计锚被 `benchmarks.py` 相对导入取走；
③ 🔴 **`lda_webui/routes.py` 的 `_app.<name>` 属性取用**——routes.py 不做
from-import，而是 `sys.modules.get("__main__")` 反查 app 模块后按属性取业务函数
（避开循环导入 + 避免脚本/包双实例）。故 app.py 里那 12 个 `lda_pdk` 名字
（`submit_device` / `review_proposal` / `land_measurement` …）**看着未用、实为契约**。
**血案（v0.9.112 波次 1 实测）**：按 F401 清掉它们 ⇒ 请求期
`AttributeError: module '__main__' has no attribute 'submit_device'` ⇒
`run_webui_api_smoke` 9 条路由 500（178P/1F）。修法 = 在 app.py 用显式元组
`_ROUTES_APP_CONTRACT` 标记为「已使用」，并由 `run_webui_api_smoke` 的静态前置断言
`_check_app_attr_contract` 守契约（启服前按名报缺）。此外 `device_library` 三处
`# noqa: F401` 是双模式契约自检的可导入性探针。
⇒ 盲删会破坏调用方 ⇒ 按审计裁决**只清两个热点**
（`lda_webui/app.py` + `lda_harness/golden.py` 及其传递链），余量作存量基线。

基线来源：v0.9.112 波次 1 清理后**实测值**（见 `LDA_fix_workplan_2026-09-19.md`）。
运行：python run_pyflakes_ratchet_smoke.py
"""
from __future__ import annotations

import json
import os
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)  # D:/agent_LDA

# 三方隔离区：不属本仓库受跟踪源码（独立 venv / node_modules / vendored 镜像 / 缓存）
_EXCLUDE_PARTS = ("lda_cuda_venv", "node_modules", "vendor", ".cache", "site-packages")

# 🔴 棘轮基线（v0.9.112 波次 1 清理后实测）——**只许降，不许升**。
# 改动本表必须付理由：若某类型确实需要上调（如新增合法 re-export），须在 PR
# 描述说明"为何不是死代码"，并在本合同步留注（防止静默放宽）。
_RATCHET = {
    "F401": 201,   # 未用导入（余量=合法 re-export/契约探针存量，见文件头）
    "F841": 12,    # 未用局部变量（12 处"算而未用·疑似漏用"，登记不删）
    "F541": 0,     # 无占位符 f-string
    "F811": 0,     # 重复定义未用（三处契约探针已改 importlib 消解）
    "F821": 0,     # 未定义名（v0.9.111 已清零）
    "OTHER": 0,    # 其它 pyflakes 类型（显式计零；新类型报出即红，需评估后登记）
}

# pyflakes 消息类名 → 类型码
_MSG_TO_CODE = {
    "UnusedImport": "F401",
    "UnusedVariable": "F841",
    "FStringMissingPlaceholders": "F541",
    "RedefinedWhileUnused": "F811",
    "UndefinedName": "F821",
}

_CHECKS = []


def check(name, ok, detail=""):
    _CHECKS.append({"name": name, "ok": bool(ok)})
    tag = "PASS" if ok else "FAIL"
    line = "  [%s] %s" % (tag, name)
    if (not ok) and detail:
        line += "  —— " + str(detail)
    print(line)
    return bool(ok)


def _tracked_py():
    """受跟踪 + 未跟踪(非 ignore) 的 .py 相对路径，排除三方隔离区。"""
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.py"],
        cwd=_ROOT, capture_output=True, text=True)
    files = [f for f in out.stdout.splitlines() if f.strip()]
    return [f for f in files if not any(p in f for p in _EXCLUDE_PARTS)]


class _Collector:
    """pyflakes reporter：收集 flake / syntaxError / unexpectedError。"""

    def __init__(self):
        self.msgs = []

    def unexpectedError(self, filename, msg):  # noqa: N802 (pyflakes 接口名)
        self.msgs.append(("__ERR__", filename, 0, str(msg)))

    def syntaxError(self, filename, msg, lineno, offset, text):  # noqa: N802
        self.msgs.append(("__SYN__", filename, lineno or 0, str(msg)))

    def flake(self, message):
        self.msgs.append((type(message).__name__, message.filename,
                          message.lineno, str(message)))


def _scan(files):
    """pyflakes 全量扫描；pyflakes 缺失时抛 ImportError 交由调用方处理。"""
    from pyflakes.api import check as pf_check
    c = _Collector()
    for rel in files:
        abspath = os.path.join(_ROOT, rel.replace("/", os.sep))
        try:
            with open(abspath, "r", encoding="utf-8", errors="replace") as fh:
                src = fh.read()
        except OSError as exc:
            c.msgs.append(("__ERR__", rel, 0, str(exc)))
            continue
        pf_check(src, rel, c)
    return c.msgs


def _ratchet_violations(counts, baseline):
    """纯函数：返回超出基线的 (code, actual, limit) 列表。正向/反向共用。"""
    out = []
    for code, limit in baseline.items():
        actual = counts.get(code, 0)
        if actual > limit:
            out.append((code, actual, limit))
    return out


def main() -> int:
    print("== 静态卫生棘轮（pyflakes · 只降不升）==")
    files = _tracked_py()
    try:
        msgs = _scan(files)
    except ImportError:
        check("pyflakes 可用（核心门禁依赖）", False,
              "未安装 ⇒ 请 `pip install pyflakes`（requirements.txt 必装项）")
        print("-" * 74)
        print("FAIL — 缺 pyflakes，棘轮无法运行（门禁依赖缺失=红，不静默跳过）")
        return 1

    counts = {code: 0 for code in _RATCHET}
    parse_errs = []
    for type_name, fname, lineno, text in msgs:
        if type_name in ("__ERR__", "__SYN__"):
            parse_errs.append((fname, lineno, text))
            continue
        code = _MSG_TO_CODE.get(type_name, "OTHER")
        counts[code] = counts.get(code, 0) + 1

    print("  受跟踪 .py（含未跟踪、排除隔离区）：%d" % len(files))
    print("  实测：%s" % json.dumps({k: counts[k] for k in _RATCHET}, ensure_ascii=False))
    print("  基线：%s" % json.dumps(_RATCHET, ensure_ascii=False))

    other_detail = [m[3] for m in msgs if _MSG_TO_CODE.get(m[0]) is None
                    and m[0] not in ("__ERR__", "__SYN__")]

    rc = 0
    rc |= not check("① pyflakes 解析错误 == 0（受跟踪语法全部可编译）",
                    len(parse_errs) == 0,
                    "解析错误 %d 处：%s" % (len(parse_errs), parse_errs[:5]))

    viol = _ratchet_violations(counts, _RATCHET)
    rc |= not check("② 逐类型计数 ≤ 棘轮基线（只许降不许升）", len(viol) == 0,
                    "超限：" + str(["%s %d>%d" % (c, a, l) for c, a, l in viol]))

    rc |= not check("③ 其它 pyflakes 类型 == 0（新类型报出即红，需评估登记）",
                    counts.get("OTHER", 0) == 0,
                    "未映射类型：%s" % other_detail[:5])

    # 🔴 反向测试 A：把 F401 基线调低 1 ⇒ 检测器必须报违规（真会响）
    probe_baseline = dict(_RATCHET)
    probe_baseline["F401"] = max(0, _RATCHET["F401"] - 1)
    probe_counts = dict(counts)
    if probe_counts.get("F401", 0) <= probe_baseline["F401"]:
        probe_counts["F401"] = probe_baseline["F401"] + 1
    rc |= not check("④ 反向 A：基线调低 1 ⇒ 违规检测器必报（非假绿）",
                    len(_ratchet_violations(probe_counts, probe_baseline)) > 0,
                    "检测器未响应")

    # 🔴 反向测试 B：合成超限计数 ⇒ 必报
    synth = {"F401": _RATCHET["F401"] + 5}
    rc |= not check("⑤ 反向 B：合成超限计数 ⇒ 必报",
                    len(_ratchet_violations(synth, _RATCHET)) > 0)

    n_pass = sum(1 for c in _CHECKS if c["ok"])
    print("-" * 74)
    print("汇总：%d PASS / %d FAIL / 共 %d 项" % (n_pass, len(_CHECKS) - n_pass, len(_CHECKS)))
    if rc == 0:
        print("ALL PASS — 静态卫生只降不升，棘轮在位（" +
              " / ".join("%s≤%d" % (k, v) for k, v in _RATCHET.items()) + "）")
    else:
        print("FAIL — 静态卫生劣化或棘轮失效，请按上方 FAIL 项修复")
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
