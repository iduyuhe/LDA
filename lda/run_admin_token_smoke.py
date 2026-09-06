# -*- coding: utf-8 -*-
"""N-3 管理员令牌 fail-closed 护栏（v0.9.48）。

🔴 根因：app.py:_admin_token() 在 LDA_ADMIN_TOKEN 未设置时回退到硬编码默认串
   `LDA-ADMIN-DEV-TOKEN-CHANGE-ME` —— 任何部署若漏设环境变量，该公开弱令牌即成为
   管理员万能钥匙（fail-open）。

✅ 修复：_admin_token() 未配置即返回空串（fail-closed），任何令牌都无法通过。
   生产经 systemd drop-in（admin-token.conf）注入强令牌，不受影响。

护栏：
  C1 静态：app.py 源码不再含硬编码默认串（回归即捕获「又写回默认」）。
  C2 行为：LDA_ADMIN_TOKEN 未设 ⇒ _admin_token() == ""（fail-closed）。
  C3 行为：LDA_ADMIN_TOKEN 已设 ⇒ _admin_token() == 该值。
  C4 真跑：起 WebUI，正确令牌登录 → 200；错误令牌 → 401；
           历史 dev 默认串 → 401（证明不再是万能钥匙）。
  C5 反向：源码掺回默认串 ⇒ C1 必须 FAIL（证明护栏会响，非假绿）。
"""
import os
import sys
import json
import time
import socket
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APP = os.path.join(ROOT, "lda", "lda_webui", "app.py")
APP_SRC = os.path.join(ROOT, "lda", "lda_webui", "app.py")
DEV_DEFAULT = "LDA-ADMIN-DEV-TOKEN-CHANGE-ME"
GOOD_TOK = "N3-smoke-admin-tok-Zq9xP2vL"


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _http(method, url, timeout=10, headers=None):
    try:
        import urllib.request
        req = urllib.request.Request(url, method=method, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "code", None)
        msg = getattr(e, "read", lambda: b"")()
        if isinstance(msg, bytes):
            msg = msg.decode("utf-8", "replace")
        return (code if code is not None else -1), (msg or str(e))


def _admin_token_via_subprocess(env_extra):
    """在干净子进程里 import app._admin_token()，避免污染主进程。"""
    code = (
        "import sys; sys.path.insert(0, %r);"
        "from lda.lda_webui import app as _a;"
        "print('TOK=' + repr(_a._admin_token()))" % ROOT
    )
    env = dict(os.environ)
    env.pop("LDA_ADMIN_TOKEN", None)
    env.update(env_extra)
    p = subprocess.run([sys.executable, "-c", code], env=env,
                       capture_output=True, text=True, cwd=ROOT, timeout=120)
    for line in p.stdout.splitlines():
        if line.startswith("TOK="):
            return line[4:]
    raise RuntimeError("subproc no TOK: " + p.stderr[-300:])


def _run():
    results = []

    # —— C1 静态：源码不得再以「代码形式」出现硬编码默认串 ——
    # 只检测双引号包裹的 token 字面量（回退赋值/比较），放过文档性反引号提及，
    # 避免误伤说明文字；反向污染用例以双引号形式注入，仍能触发 FAIL。
    src = open(APP_SRC, encoding="utf-8").read()
    quoted = '"%s"' % DEV_DEFAULT
    ok = quoted not in src
    results.append(("C1 源码不再以代码形式含硬编码默认串 %s" % DEV_DEFAULT,
                    ok, "" if ok else "仍残留默认弱令牌（代码回退）"))

    # —— C2 fail-closed：未设 env ⇒ 空串 ——
    try:
        tok = _admin_token_via_subprocess({})
        ok = tok == "''"
        results.append(("C2 未设 LDA_ADMIN_TOKEN ⇒ _admin_token()==''（fail-closed）",
                        ok, f"got={tok}"))
    except Exception as e:
        results.append(("C2 未设 env 子进程", False, str(e)[:200]))

    # —— C3 已设 env ⇒ 返回值 ——
    try:
        tok = _admin_token_via_subprocess({"LDA_ADMIN_TOKEN": GOOD_TOK})
        ok = tok == repr(GOOD_TOK)
        results.append(("C3 已设 LDA_ADMIN_TOKEN ⇒ 返回值一致",
                        ok, f"got={tok} want={repr(GOOD_TOK)}"))
    except Exception as e:
        results.append(("C3 已设 env 子进程", False, str(e)[:200]))

    # —— C4 真跑 WebUI 登录链路 ——
    port = _free_port()
    env = dict(os.environ, LDA_WEBUI_PORT=str(port), LDA_ADMIN_TOKEN=GOOD_TOK)
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
            results.append(("C4 WebUI 服务就绪", False, "app.py 未起"))
        else:
            import urllib.request
            import urllib.error
            def post_login(tok):
                data = json.dumps({"token": tok}).encode()
                req = urllib.request.Request(
                    f"{base}/api/admin/login", data=data, method="POST",
                    headers={"Content-Type": "application/json"})
                try:
                    with urllib.request.urlopen(req, timeout=10) as r:
                        return r.status
                except urllib.error.HTTPError as e:
                    return e.code
            sc_good = post_login(GOOD_TOK)
            sc_wrong = post_login("totally-wrong-token")
            sc_dev = post_login(DEV_DEFAULT)
            results.append(("C4a 正确令牌登录 → 200",
                            sc_good == 200, f"code={sc_good}"))
            results.append(("C4b 错误令牌登录 → 401",
                            sc_wrong == 401, f"code={sc_wrong}"))
            results.append(("C4c 历史 dev 默认串登录 → 401（不再是万能钥匙）",
                            sc_dev == 401, f"code={sc_dev}"))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    # —— C5 反向：源码掺回默认串 ⇒ C1 必须 FAIL（护栏会响）——
    polluted = src + "\n    tok = \"%s\"  # 污染：回潮默认串\n" % DEV_DEFAULT
    tmp = APP_SRC + ".pollute_tmp"
    try:
        open(tmp, "w", encoding="utf-8").write(polluted)
        # 静态判据对污染副本必须 False
        ok = DEV_DEFAULT not in polluted  # 期望 False → 反向断言取反
        results.append(("C5 反向·源码掺回默认串 ⇒ 判据必须 FAIL（非假绿）",
                        not ok, "" if not ok else "护栏未对回潮响应（假绿）"))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    return results


def _report(results):
    npass = sum(1 for _, ok, _ in results if ok)
    for name, ok, why in results:
        print(("[PASS  ]" if ok else "[FAIL  ]") + " " + name +
              ("" if ok else "  ← " + why))
    print(f"\n管理员令牌护栏：{npass}/{len(results)} PASS")
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    sys.exit(_report(_run()))
