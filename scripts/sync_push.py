# -*- coding: utf-8 -*-
"""三端同步推送（headless-git-sync 复用脚本）。

从 Windows 凭据管理器读取 gitee/github 令牌（仅驻内存，不落盘），
经 git credential-store 写入临时 store，推送两远端后删除 store。
用法: python scripts/sync_push.py REPO_PATH [STORE_PATH]
"""
import os
import sys
import ctypes
import subprocess
import tempfile
from ctypes import wintypes

REPO = sys.argv[1] if len(sys.argv) > 1 else "D:/agent_LDA"
# 🔴 v0.9.169 修复：store 路径必须是**本机真实存在的绝对路径**。
# 旧默认 `/tmp/lda_cred_store_push` 在 Windows 上不是合法路径 ⇒ credential-store
# 写入/读取不一致（写 rc=0，但 push 时读不到 ⇒ `could not read Username`）⇒ 假绿。
# 改用 `tempfile.gettempdir()`（Windows 上 = C:\Users\...\AppData\Local\Temp）·
# 再统一归一化为正斜杠（下方 STORE.replace 已做）。
STORE = sys.argv[2] if len(sys.argv) > 2 else os.path.join(tempfile.gettempdir(), "lda_cred_store_push")

# 🔴 v0.9.118 实测订正：store 路径必须【正斜杠】。
# STORE 被嵌进 `-c credential.helper=store --file={STORE}` ⇒ git 把该 helper 交给
# `sh -c` 执行 ⇒ **Windows 反斜杠会被 sh 吃掉**：`--file=C:\Users\x\_s`
# 实际变成 `--file=C:Usersx_s` ⇒ helper 读一个不存在的文件 ⇒ 返回空 ⇒
# `fatal: could not read Username`（exit=128）。且本脚本自身**仍 rc=0** ⇒ 假绿。
# 2026-09-21 实测 A/B：正斜杠 → rc=0 成功 / 反斜杠 → exit=128 /
# 直接 `git credential-store --file=... get`（不经 shell）→ rc=0
# ⇒ 根因锁定是 `sh -c` 吃反斜杠，与凭据、网络均无关。
# 故此处统一归一化为正斜杠（`os.path.join` 在 Windows 上恰好生成反斜杠，
# 是唯一的触发源；REPO 不受影响 —— 它是 subprocess 的 cwd=，不经 shell）。
STORE = STORE.replace("\\", "/")

CRED_TYPE_GENERIC = 0x1


class CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_char)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def _setup():
    adv = ctypes.windll.advapi32
    adv.CredReadW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(CREDENTIAL)),
    ]
    adv.CredReadW.restype = wintypes.BOOL
    adv.CredFree.argtypes = [ctypes.POINTER(CREDENTIAL)]
    adv.CredFree.restype = wintypes.BOOL
    return adv


def credread(adv, target):
    pcred = ctypes.POINTER(CREDENTIAL)()
    ok = adv.CredReadW(
        ctypes.c_wchar_p(target), CRED_TYPE_GENERIC, 0,
        ctypes.byref(pcred))
    if not ok:
        return None, None
    blob = pcred.contents.CredentialBlob
    size = pcred.contents.CredentialBlobSize
    pwd = ctypes.string_at(blob, size).decode("utf-16-le", "replace").rstrip("\x00")
    user = pcred.contents.UserName or ""
    adv.CredFree(pcred)
    return user, pwd


def _probe(host, user, tok, remote):
    """用该凭据真实做一次 ls-remote，判断能否认证（避免拿到过期/无效 token 仍误报成功）。

    返回 `'direct'` / `'proxy'` / `None` —— 除「能不能用」外，还告诉调用方**这条凭据
    走哪条通路才通**（供 push/verify 段排序，避免每轮白等一次 21 s 直连超时）。
    """
    env0 = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null"}
    try:
        os.remove(STORE)
    except OSError:
        pass
    inp = f"protocol=https\nhost={host}\nusername={user}\npassword={tok}\n"
    subprocess.run(["git", "credential-store", f"--file={STORE}", "store"],
                   input=inp, cwd=REPO, env=env0, capture_output=True, text=True)
    env_p = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null",
             "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_TERMINAL_PROMPT": "0"}
    for k in ("http_proxy", "https_proxy", "all_proxy", "no_proxy",
              "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        env_p.pop(k, None)
    common = ["git", "-c", f"credential.helper=store --file={STORE}",
              "-c", "http.sslBackend=openssl", "-c", "http.version=HTTP/1.1"]
    r = subprocess.run([*common, "ls-remote", remote, "refs/heads/main"],
                       cwd=REPO, env=env_p, capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        return "direct"
    # 🔴 v0.9.180 实测订正：**探活也必须留代理兜底**（与下方 push 段同口径）。
    #   旧版探活只做直连 ⇒ 本机直连 github 不通时（`Recv failure: Connection was reset`
    #   或 `Failed to connect to github.com:443 after 21080 ms`），一条**有效凭据**被判
    #   「不可用」⇒ github 被静默踢出 creds ⇒ 推送段与 VERIFY 段**一起跳过** ⇒ 只推了
    #   gitee 却仍报 `ALL-MATCH`（假绿）。push 段早有直连⟶代理兜底，探活段漏了同款。
    if host == "github.com":
        r2 = subprocess.run(
            [*common, "-c", "http.proxy=socks5h://127.0.0.1:7890",
             "ls-remote", remote, "refs/heads/main"],
            cwd=REPO, env=env_p, capture_output=True, text=True)
        if r2.returncode == 0 and r2.stdout.strip():
            return "proxy"
    return None


def main():
    adv = _setup()
    # 🔴 凭据 target 名在不同托管平台/写入方式下不一致，且某个 token 可能已过期/无效
    #   （如 github 的 `git:https://oauth2@github.com` 曾实测返回 128「Invalid username or
    #   token」）。故每 host 试多个候选 target，并用 `_probe` 真实 ls-remote 认证，
    #   命中第一个能认证成功的即用（不再「非空即采用」）。
    _TARGETS = {
        "gitee.com": ["git:https://gitee.com", "git:https://oauth2@gitee.com"],
        "github.com": ["git:https://x-access-token@github.com",
                       "git:https://oauth2@github.com",
                       "git:https://github.com"],
    }
    creds = {}
    for host, candidates in _TARGETS.items():
        remote = host.split(".")[0]
        got = False
        for target in candidates:
            user, tok = credread(adv, target)
            if not tok:
                continue
            mode = _probe(host, user, tok, remote)
            if mode:
                print(f"[OK] {host} 凭据生效: target={target} user={user} via={mode}")
                creds[host] = (user, tok, mode)
                got = True
                break
            else:
                print(f"[PROBE-FAIL] {host} target={target} 认证失败(过期/无效/直连不通)，试下一个")
        if not got:
            print(f"[WARN] {host} 所有候选凭据均不可用，跳过")
    if not creds:
        print("[FATAL] 无任何凭据，无法推送")
        sys.exit(1)

    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_CONFIG_SYSTEM": "/dev/null"}
    for host, (user, tok, _mode) in creds.items():
        inp = f"protocol=https\nhost={host}\nusername={user}\npassword={tok}\n"
        r = subprocess.run(
            ["git", "credential-store", f"--file={STORE}", "store"],
            input=inp, cwd=REPO, env=env, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"[WARN] 写 store {host} 失败: {r.stderr}")

    base = ["git", "-c", f"credential.helper=store --file={STORE}",
            "-c", "http.sslBackend=openssl", "-c", "http.version=HTTP/1.1"]
    env2 = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_TERMINAL_PROMPT": "0"}
    # 🔴 v0.9.60 实测订正：**必须在环境变量层**清代理，只清 git config 不够。
    # 沙箱会注入 http_proxy/https_proxy=http://127.0.0.1:<随机端口>，且环境变量
    # 优先级高于 `-c http.proxy=`（空值不覆盖已存在的环境变量）⇒ git 仍走那条链路。
    # 该端口未必可达（如刚过一次意外重启），症状是「直连 + 代理两条支路全报
    # Could not connect」，而同一时刻 `env -u http_proxy ... git ls-remote` 却成功
    # ⇒ 是脚本的锅，不是网络的锅。故直连分支用「无代理环境」。
    _PROXY_ENV_KEYS = ("http_proxy", "https_proxy", "all_proxy", "no_proxy",
                       "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")
    env_noproxy = {k: v for k, v in env2.items() if k not in _PROXY_ENV_KEYS}

    push_rc = {}
    if "gitee.com" in creds:
        print("[PUSH] gitee main ...")
        r = subprocess.run([*base, "push", "gitee", "main"], cwd=REPO, env=env2)
        print(f"  gitee exit={r.returncode}")
        push_rc["gitee"] = r.returncode
    if "github.com" in creds:
        # 🔴 v0.9.24 实测订正：github **直连常常就是通的**（故仍保留直连优先，省一次代理往返）。
        # 🔴 v0.9.180 补：**按探活结论排序** —— 探活已实测本机直连不通 / 仅代理通时
        #   （`via=proxy`），就先走代理，避免每轮白等一次 21 s 直连超时；反之直连优先。
        #   两条路都留着（直连可能随时恢复）。直连也走不通时（DNS 污染 / SNI 过滤）的
        #   兜底仍是：paramiko 借生产服务器 115.191.20.92 起 SOCKS5 中继。
        _first = "proxy" if creds["github.com"][2] == "proxy" else "direct"
        _rc = 1
        for _m in (_first, "proxy" if _first == "direct" else "direct"):
            _extra = (["-c", "http.proxy=socks5h://127.0.0.1:7890"]
                      if _m == "proxy" else [])
            print(f"[PUSH] github main ({_m}) ...")
            # 直连/代理两路都必须在**环境变量层**排除注入代理，否则 5xxxx 端口会盖掉配置
            r = subprocess.run([*base, *_extra, "push", "github", "main"],
                               cwd=REPO, env=env_noproxy)
            print(f"  github {_m} exit={r.returncode}")
            _rc = r.returncode
            if _rc == 0:
                break
        push_rc["github"] = _rc

    # 🔴 推送判据（铁律）：ls-remote sha == 本地 HEAD（勿信 rc=0）
    local = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"],
                           capture_output=True, text=True).stdout.strip()
    print(f"[VERIFY] local HEAD = {local}")
    all_match = True
    for remote in ("gitee", "github"):
        if remote + ".com" not in creds:
            # 🔴 v0.9.180 补（反向完备判据）：凭据不可用的远端**必须显式判 FAIL**，
            #   不许 `continue` 静默跳过 —— 旧版只核 gitee 就报 `ALL-MATCH`（假绿），
            #   正是「白名单式门禁缺反向完备判据」的同族（见项目纪律）。
            all_match = False
            print(f"[VERIFY] {remote} main = <NO-CREDENTIAL> -> FAIL"
                  f"（凭据不可用 ⇒ 既未推送也未验证，不算同步成功）")
            continue
        lr = subprocess.run([*base, "ls-remote", remote, "refs/heads/main"],
                            cwd=REPO, env=env2, capture_output=True, text=True)
        sha = lr.stdout.split()[0] if lr.stdout.strip() else ""
        # 🔴 直连 ls-remote 失败（env2 已清代理 ⇒ github 直连不通）⇒ 用代理重试再判。
        #   实测踩到：github 直推 exit=128、走代理 exit=0（推成功了），但本段直连
        #   ls-remote 仍是空 sha ⇒ [VERIFY] 误报 MISMATCH（「推成功却说没推上」，
        #   会让人白重推一轮）。sha 为空只说明「查不到」，不等于「远端不是这个 sha」。
        if not sha and lr.returncode != 0:
            lr2 = subprocess.run([*base, "-c", "http.proxy=socks5h://127.0.0.1:7890",
                                  "ls-remote", remote, "refs/heads/main"],
                                 cwd=REPO, env=env2, capture_output=True, text=True)
            if lr2.stdout.strip():
                print(f"  [{remote}] 直连 ls-remote 失败 ⇒ 代理重试取到 sha（非 MISMATCH）")
                sha = lr2.stdout.split()[0]
        # 🔴 v0.9.180 补（第二处假绿）：**本次 push 是否成功**必须单独作判据。
        #   只因「远端 sha 恰等于本地 HEAD」而报 MATCH 是假绿 —— 上一轮推成功后，
        #   本轮 push 全失败（凭据失效 / 无权 403 / 网络不通）时远端 sha 仍等于本地
        #   HEAD ⇒ 会让人以为「同步正常」，直到下次提交才暴露。且 `_probe` 用
        #   `ls-remote` 只证**读**权限（public 仓库匿名也可读）⇒ 读通 ≠ 写通，
        #   写权限唯一的真判据就是 push 的 rc。
        prc = push_rc.get(remote, None)
        if prc != 0:
            print(f"  [{remote}] push rc={prc} ≠ 0 ⇒ 本次推送未成功"
                  f"（远端 sha 相等不构成同步成功；读通≠写通）")
        ok = (sha == local) and (prc == 0)
        all_match = all_match and ok
        print(f"[VERIFY] {remote} main = {sha} -> {'MATCH' if ok else 'MISMATCH'}")
    print(f"[VERIFY] RESULT {'ALL-MATCH' if all_match else 'HAS-MISMATCH'}")

    try:
        os.remove(STORE)
        print("[CLEAN] store 已删除")
    except Exception as e:
        print(f"[WARN] 删除 store 失败: {e}")


if __name__ == "__main__":
    main()
