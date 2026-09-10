# -*- coding: utf-8 -*-
"""生产红队锚面 fuzz 周期化看门狗（cron 触发，建议每 30 分钟一次）。

与 scripts/redteam_cron.py 同范式，但面向「52 锚 fuzz + 死标量裁决」闭环：
  1. 运行 run_redteam_anchor_fuzz_smoke.py（规则式 ±30% 扰动攻击 52 锚）
  2. 运行 run_redteam_adjudication.py（死标量重判，分类发散点）
  3. 按 in_domain_suspect 数定级：
       CRITICAL : 域内疑点 > 0  → 出现「域内发散」= 真实可疑（非极值预期分叉），须人工/锚复核
       OK       : 全部分歧为预期极值分叉，无域内疑点
  4. 写趋势日志 redteam_anchor_fuzz_trend.jsonl + 带冷却的本地告警

纪律（五共识 ② / 多智能体红蓝队分工）：红队只出题攻击、判决在锚。
本脚本是看门狗，不改动管线，只把裁决死标量趋势化并告警。
依赖：仅 Python 标准库。可用 /opt/lda_env/bin/python 直接跑。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

LDA_ROOT = os.environ.get("LDA_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = os.environ.get("LDA_CRON_PY", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "..", ".workbuddy", "binaries", "python", "envs", "default", "Scripts", "python.exe"))
if not os.path.exists(PY):
    PY = sys.executable  # 回退当前解释器

TREND_LOG = os.environ.get("REDTEAM_FUZZ_TREND",
                           os.path.join(LDA_ROOT, "logs", "redteam_anchor_fuzz_trend.jsonl"))
ALERT_LOG = os.environ.get("REDTEAM_FUZZ_ALERT",
                          os.path.join(LDA_ROOT, "logs", "redteam_anchor_fuzz_alerts.log"))
STATE_FILE = os.environ.get("REDTEAM_FUZZ_STATE",
                           os.path.join(LDA_ROOT, "logs", "redteam_anchor_fuzz_state.json"))
COOLDOWN_SEC = int(os.environ.get("REDTEAM_FUZZ_COOLDOWN_SEC", "3600") or 3600)
REPORT_JSON = os.path.join(LDA_ROOT, "lda", "redteam_adjudication_report.json")


def _run(script: str) -> int:
    """运行一个 lda/ 下的 smoke 脚本，返回退出码。"""
    path = os.path.join(LDA_ROOT, "lda", script)
    if not os.path.exists(path):
        print("[WARN] 脚本缺失: %s" % path)
        return 1
    try:
        r = subprocess.run([PY, path], cwd=LDA_ROOT,
                           capture_output=True, text=True, timeout=600)
        return r.returncode
    except Exception as e:  # noqa: BLE001
        print("[WARN] 运行 %s 异常: %s" % (script, e))
        return 2


def classify(rep: dict) -> tuple:
    total = rep.get("total", 0)
    suspect = rep.get("in_domain_suspect", 0)
    expected = rep.get("expected_extreme", 0)
    if suspect > 0:
        return "CRITICAL", ("域内疑点 %d 个（非极值预期分叉），须人工/锚复核" % suspect)
    return "OK", ("无域内疑点；%d 发散点均为预期极值分叉（非缺陷）" % expected)


def _load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(st: dict):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(st, f)
    except Exception:
        pass


def _emit(level: str, message: str, rep: dict):
    now = time.time()
    st = _load_state()
    sig = "%s|%s" % (level, message)
    if level != "CRITICAL" and sig == st.get("last_sig", "") \
            and (now - st.get("last_alert_ts", 0)) < COOLDOWN_SEC:
        return
    st["last_alert_ts"] = now
    st["last_sig"] = sig
    st["last_level"] = level
    _save_state(st)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
           "level": level, "message": message, "report": rep}
    try:
        os.makedirs(os.path.dirname(ALERT_LOG), exist_ok=True)
        with open(ALERT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass
    print("[ALERT %s] %s" % (level, message))


def main():
    print("=== 红队锚面 fuzz 周期看门狗 ===")
    rc1 = _run("run_redteam_anchor_fuzz_smoke.py")
    rc2 = _run("run_redteam_adjudication_smoke.py")
    if not os.path.exists(REPORT_JSON):
        print("[WARN] 裁决报告缺失（fuzz/adjudication 可能失败 rc1=%s rc2=%s），跳过定级" % (rc1, rc2))
        _emit("WARN", "裁决报告缺失 rc1=%s rc2=%s" % (rc1, rc2), {})
        return
    with open(REPORT_JSON, "r", encoding="utf-8") as f:
        rep = json.load(f)

    level, message = classify(rep)
    trend = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
             "fuzz_rc": rc1, "adjudication_rc": rc2,
             "total": rep.get("total"), "expected_extreme": rep.get("expected_extreme"),
             "in_domain_suspect": rep.get("in_domain_suspect"), "level": level}
    try:
        os.makedirs(os.path.dirname(TREND_LOG), exist_ok=True)
        with open(TREND_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(trend, ensure_ascii=False) + "\n")
    except Exception:
        pass

    print("[%s] total=%s expected=%s suspect=%s fuzz_rc=%s adj_rc=%s"
          % (level, rep.get("total"), rep.get("expected_extreme"),
             rep.get("in_domain_suspect"), rc1, rc2))
    if level != "OK":
        _emit(level, message, rep)
    else:
        st = _load_state()
        st["last_level"] = "OK"
        st["last_sig"] = "OK|"
        st["last_alert_ts"] = time.time()
        _save_state(st)


if __name__ == "__main__":
    main()
