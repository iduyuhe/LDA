"""D-辅助 · GitHub 社区信号补验探针。

用途：在战略审计中客观补验"社区 traction"——避免用本地/生产假数据推断社区活跃度。
抓取指标：stars / forks / watchers / subscribers / open issues(不含PR) / open PRs /
总 issue 数 / 总 PR 数 / 贡献者数 / 最近提交时间 / license / 主语言 / 创建&推送时间。

用法：
  GITHUB_TOKEN=xxx python scripts/probe_github_signals.py [owner/repo] [out.json]
若不传 owner/repo 默认 iduyuhe/LDA；不传 out.json 默认 docs/community_signals_<date>.json。
LLM 不进判决路径——本脚本只搬运 GitHub REST 事实，不做任何推断。
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys
import urllib.request
import urllib.error

API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

_REPO = sys.argv[1] if len(sys.argv) > 1 else "iduyuhe/LDA"
_OUT = sys.argv[2] if len(sys.argv) > 2 else (
    "docs/community_signals_" + _dt.date.today().isoformat() + ".json")


def _get(path: str) -> dict:
    url = API + path
    req = urllib.request.Request(url)
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "lda-audit-probe")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _search_count(q: str) -> int:
    d = _get("/search/issues?q=" + urllib.parse.quote(q) + "&per_page=1")
    return int(d.get("total_count", -1))


def _safe(fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


import urllib.parse  # noqa: E402  (placed after defs to keep header clean)

repo = _safe(lambda: _get("/repos/" + _REPO))
contributors = _safe(
    lambda: _get("/repos/" + _REPO + "/contributors?per_page=100"))
latest = _safe(lambda: _get("/repos/" + _REPO + "/commits?per_page=1"))

result = {
    "repo": _REPO,
    "fetched_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    "rate_limit_status": _safe(
        lambda: {k: v for k, v in _get("/rate_limit")["resources"].items()
                 if k in ("core", "search")}),
}

if isinstance(repo, dict) and "error" not in repo:
    result["stars"] = repo.get("stargazers_count")
    result["forks"] = repo.get("forks_count")
    result["watchers"] = repo.get("watchers_count")
    result["subscribers"] = repo.get("subscribers_count")
    result["open_issues_incl_pr"] = repo.get("open_issues_count")
    result["network_count"] = repo.get("network_count")
    result["license"] = (repo.get("license") or {}).get("spdx_id")
    result["language"] = repo.get("language")
    result["created_at"] = repo.get("created_at")
    result["pushed_at"] = repo.get("pushed_at")
    result["updated_at"] = repo.get("updated_at")
    result["default_branch"] = repo.get("default_branch")
    result["size_kb"] = repo.get("size")

if isinstance(contributors, list):
    result["contributors_visible"] = len(contributors)
elif isinstance(contributors, dict) and "error" in contributors:
    result["contributors_visible"] = contributors
else:
    result["contributors_visible"] = None

if isinstance(latest, list) and latest:
    c0 = latest[0].get("commit", {})
    result["last_commit_sha"] = latest[0].get("sha")
    result["last_commit_date"] = c0.get("committer", {}).get("date")
    result["last_commit_message"] = c0.get("message", "")[:120]

# 搜索 API 计数（issues / PRs 分开，避免 GitHub open_issues_count 把 PR 算进去）
result["issues_total"] = _safe(
    lambda: _search_count("repo:" + _REPO + " type:issue"))
result["issues_open"] = _safe(
    lambda: _search_count("repo:" + _REPO + " type:issue state:open"))
result["prs_total"] = _safe(
    lambda: _search_count("repo:" + _REPO + " type:pr"))
result["prs_open"] = _safe(
    lambda: _search_count("repo:" + _REPO + " type:pr state:open"))

with open(_OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(json.dumps(result, ensure_ascii=False, indent=2))
