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
from ctypes import wintypes

REPO = sys.argv[1] if len(sys.argv) > 1 else "D:/agent_LDA"
STORE = sys.argv[2] if len(sys.argv) > 2 else "/tmp/lda_cred_store_push"

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


def main():
    adv = _setup()
    creds = {}
    for host, target in [("gitee.com", "git:https://gitee.com"),
                        ("github.com", "git:https://github.com")]:
        user, tok = credread(adv, target)
        if not tok:
            print(f"[WARN] 未找到 {target} 凭据，跳过")
            continue
        creds[host] = (user, tok)
    if not creds:
        print("[FATAL] 无任何凭据，无法推送")
        sys.exit(1)

    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_CONFIG_SYSTEM": "/dev/null"}
    for host, (user, tok) in creds.items():
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

    if "gitee.com" in creds:
        print("[PUSH] gitee main ...")
        r = subprocess.run([*base, "push", "gitee", "main"], cwd=REPO, env=env2)
        print(f"  gitee exit={r.returncode}")
    if "github.com" in creds:
        print("[PUSH] github main (via socks5h proxy) ...")
        r = subprocess.run([*base, "-c", "http.proxy=socks5h://127.0.0.1:7890",
                            "push", "github", "main"], cwd=REPO, env=env2)
        print(f"  github exit={r.returncode}")

    try:
        os.remove(STORE)
        print("[CLEAN] store 已删除")
    except Exception as e:
        print(f"[WARN] 删除 store 失败: {e}")


if __name__ == "__main__":
    main()
