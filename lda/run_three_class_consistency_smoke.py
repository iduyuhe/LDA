# -*- coding: utf-8 -*-
"""N-4 三分类对外一致性护栏（v0.9.48）。

🔴 根因（同类「标签≠行为 / 计数一致性」血案）：三分类（严格独立 / 降级量级参考 /
   自证桩）是 LDA 诚实边界的核心陈述，对外有三个面——README 账本、本机 harness 推导、
   `/api/verification_ledger` 端点。端点已动态推导（无硬编码），harness 是权威源，但
   README 是**静态手写陈述**，历史上曾因写死数字与代码脱节（ci_core=82 同类漂移）。
   本护栏把「三者必须逐项相等」固化进 CI，杜绝 README 悄悄失真。

护栏：
  C1 harness 推导三分类（严格/降级/自证桩）结构正确、和 = 题数。
  C2 README 账本陈述的三分类 ≡ harness 推导（防静态陈述失真）。
  C3 /api/verification_ledger 端点三分类 ≡ harness 推导（真跑端点，非同式复算）。
  C4 反向：篡改 README 数字 ⇒ C2 必 FAIL（护栏会响，非假绿）。
"""
import os
import re
import sys
import json
import time
import socket
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APP = os.path.join(ROOT, "lda", "lda_webui", "app.py")
README = os.path.join(ROOT, "README.md")


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _harness_three_class():
    sys.path.insert(0, ROOT)
    from lda_harness.benchmarks import BENCHMARK_DEFS
    from lda_harness.verification_adapters import BENCHMARK_CANDIDATES
    strict = deg = stub = 0
    for bid in BENCHMARK_DEFS:
        d = BENCHMARK_DEFS[bid]
        k = d.get("candidate")
        if d.get("candidate_status") == "degraded_ordinal":
            deg += 1
        elif k and k in BENCHMARK_CANDIDATES:
            strict += 1
        else:
            stub += 1
    return strict, deg, stub


def _readme_three_class():
    txt = open(README, encoding="utf-8").read()
    m = re.search(
        r"严格独立\s*(\d+)\s*道.*?降级量级参考\s*(\d+)\s*道.*?自证桩\s*(\d+)\s*道",
        txt, re.S)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _http(method, url, timeout=10, headers=None):
    try:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(url, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return -1, str(e)


def _run():
    results = []
    h_strict, h_deg, h_stub = _harness_three_class()
    h_total = h_strict + h_deg + h_stub

    # C1 harness 结构正确
    ok = h_total > 0 and h_strict >= 0 and h_deg >= 0 and h_stub >= 0
    results.append(("C1 harness 三分类推导有效（和=%d=题数）" % h_total,
                    ok, f"strict={h_strict} deg={h_deg} stub={h_stub}"))

    # C2 README ≡ harness
    r_tc = _readme_three_class()
    ok = r_tc == (h_strict, h_deg, h_stub)
    results.append(("C2 README 账本三分类 ≡ harness（%d/%d/%d）" % (h_strict, h_deg, h_stub),
                    ok, f"readme={r_tc} harness=({h_strict},{h_deg},{h_stub})"))

    # C3 真跑端点 ≡ harness
    port = _free_port()
    env = dict(os.environ, LDA_WEBUI_PORT=str(port), LDA_ADMIN_TOKEN="tc-smoke-tok")
    proc = subprocess.Popen([sys.executable, APP], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        base = f"http://127.0.0.1:{port}"
        ready = False
        for _ in range(40):
            code, _ = _http("GET", f"{base}/api/status", timeout=5)
            if code == 200:
                ready = True
                break
            time.sleep(0.5)
        if not ready:
            results.append(("C3 WebUI 服务就绪", False, "app.py 未起"))
        else:
            code, body = _http("GET", f"{base}/api/verification_ledger", timeout=10)
            try:
                d = json.loads(body)
                tot = d["judgment_paths"]["derived"]["totals"]
                e_s, e_d, e_st = (tot["strict_independent"],
                                   tot["degraded_ordinal"],
                                   tot["self_consistent_stub"])
                ok = (e_s, e_d, e_st) == (h_strict, h_deg, h_stub)
                results.append(("C3 端点 /api/verification_ledger 三分类 ≡ harness",
                                ok, f"endpoint=({e_s},{e_d},{e_st}) harness=({h_strict},{h_deg},{h_stub})"))
            except Exception as e:
                results.append(("C3 端点 JSON 解析", False, str(e)[:160]))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    # C4 反向：篡改 README 数字 ⇒ C2 必须 FAIL
    txt = open(README, encoding="utf-8").read()
    polluted = txt.replace("严格独立 25 道", "严格独立 99 道")
    tmp = README + ".pollute_tmp"
    try:
        open(tmp, "w", encoding="utf-8").write(polluted)
        # 用污染副本重算 README 三分类（绕过真实 README 路径，直接测正则判定）
        m = re.search(
            r"严格独立\s*(\d+)\s*道.*?降级量级参考\s*(\d+)\s*道.*?自证桩\s*(\d+)\s*道",
            polluted, re.S)
        pol_tc = tuple(int(m.group(i)) for i in range(1, 4)) if m else None
        ok = pol_tc != (h_strict, h_deg, h_stub)
        results.append(("C4 反向·README 数字篡改 ⇒ 判据必须 FAIL（非假绿）",
                        ok, "" if ok else "护栏未对篡改响应（假绿）"))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    return results


def _report(results):
    npass = sum(1 for _, ok, _ in results if ok)
    for name, ok, why in results:
        print(("[PASS  ]" if ok else "[FAIL  ]") + " " + name +
              ("" if ok else "  ← " + why))
    print(f"\n三分类对外一致性护栏：{npass}/{len(results)} PASS")
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    sys.exit(_report(_run()))
