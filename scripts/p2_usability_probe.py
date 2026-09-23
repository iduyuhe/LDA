"""P2 门禁突变探针（v0.9.131）—— 证明 `lda/run_p2_usability_smoke.py` 的判据**会响**。

⚠️ **本脚本只作人工运行，不进 CI core**。理由：它靠「改工作区文件 → 跑门禁 → 按原字节
还原」来取证，若中途异常退出，可能留下**被改坏的文档**在树里。CI 里跑这种自改脚本风险
不对等（门禁本身每次都会跑，探针只需在改动门禁时人工跑一次）。

用法（仓库根）：python scripts/p2_usability_probe.py   → 13/13 全响则 rc=0

铁律：**没被验证过的护栏不算护栏**。

铁律：「没被验证过的护栏不算护栏」。本脚本对每条高价值判据各造一个**真实反例**，
跑门禁，断言「恰好该判据（及可预期的连带项）变红」，然后**按原字节还原**并用
sha256 复核还原成功（不留任何污染）。

用法：python tmp_p2_probe.py
"""
import hashlib
import json
import os
import subprocess
import sys

ROOT = r"D:/agent_LDA"
LDA = os.path.join(ROOT, "lda")
PY = sys.executable
SMOKE = "run_p2_usability_smoke.py"


def _read_bytes(rel):
    return open(os.path.join(ROOT, rel), "rb").read()


def _sha(b):
    return hashlib.sha256(b).hexdigest()[:12]


def run_smoke():
    r = subprocess.run([PY, os.path.join(LDA, SMOKE)], capture_output=True,
                       text=True, errors="replace", cwd=LDA,
                       env=dict(os.environ, PYTHONPATH=LDA))
    # 取**全量 FAIL 行文本**（含段落编号与 detail）——比只取编号更好定位
    fails_full = [ln.strip() for ln in r.stdout.splitlines() if "[FAIL]" in ln]
    return r.returncode, fails_full


def _blank_descriptions(raw: bytes, n: int) -> bytes:
    ref = json.loads(raw.decode("utf-8"))
    for e in ref["endpoints"][:n]:
        e["description"] = ""
        e["source"] = "none"
    return (json.dumps(ref, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _add_fake_endpoint(raw: bytes) -> bytes:
    ref = json.loads(raw.decode("utf-8"))
    ref["endpoints"].append(dict(ref["endpoints"][0], path="/api/__probe_fake__",
                                 handler="h_fake", wildcard=False))
    ref["endpoints"].sort(key=lambda e: (e["method"], e["path"]))
    return (json.dumps(ref, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _insert_author_path(raw: bytes) -> bytes:
    return raw + b'\nPROBE_AUTHOR_PATH = "C:/Users/Administrator/lda_qs_probe/repo"\n'


# 探针 = 对目标文件做一次「真实的性质破坏」，然后看门禁会不会响
def probe_doc_fake_path(b):
    return b + "\n\n补充说明：本版新增 `lda/does_not_exist_xyz.py`。\n".encode("utf-8")


def probe_doc_old_path(b):
    return b + "\n\n示例：`examples/cli_check_example.json`。\n".encode("utf-8")


def probe_interp(b):
    return b.replace("**Python 3.12 或以上**".encode("utf-8"),
                     "**Python 3.11 或以上**".encode("utf-8"), 1)


def probe_extra_step(b):
    return b + "\n\n## 步骤 6 · 探针多加的一步\n\n```bash\necho probe\n```\n".encode("utf-8")


def probe_bad_subcmd(b):
    # ⚠️ 首版把替换目标写成带反引号的形态（`` `lda design RingResonator --target 20` ``），
    #    而文档里该命令在 ```bash 代码块内、**没有反引号** ⇒ 替换命中 0 次、什么都没改，
    #    探针却报「判据不响」—— 探针自己的假阴性（复核哈希未变才发现）。
    return b.replace(b"lda design RingResonator", b"lda desig RingResonator", 1)


def probe_md_drift(b):
    return b.replace("端点总数".encode("utf-8"), "端点数总".encode("utf-8"), 1)


def probe_env_missing(b):
    # ⚠️ 首版替换成 `LDA_ROOTX` —— 它**含子串** `LDA_ROOT` ⇒ `n not in doc` 恒假、
    #    判据照样绿，探针却报「不响」。改用完全不含原名的替换串。
    return b.replace(b"`LDA_ROOT`", b"`LDA_ZZZPROBE`", 1)


def probe_stale_word(b):
    return b.replace("## 10. 作废说明".encode("utf-8"),
                     "本版共 B1–B11 道锚。\n\n## 10. 作废说明".encode("utf-8"), 1)


def probe_hint(b):
    return b.replace(b'id="authHint"', b'id="xHintProbe"', 1)


def probe_cli_default(b):
    return b.replace(b'os.environ.get("LDA_PY") or sys.executable',
                     b'"C:/Users/Administrator/probe/python.exe"', 1)


PROBES = [
    ("① 文档引用了不存在的仓库内路径", "README.md", probe_doc_fake_path,
     "① 文档引用的仓库内路径全部真实存在"),
    ("① 血案路径回潮（缺一层）", "README.md", probe_doc_old_path,
     "① 血案路径 `examples/cli_check_example.json` 已绝迹"),
    ("② 文档出现不存在的子命令", "QUICKSTART.md", probe_bad_subcmd,
     "② 文档中出现的 `lda <子命令>` 全在真实子命令集内"),
    ("③ 正文写回 Python 3.11 要求", "QUICKSTART.md", probe_interp,
     "③ 面向外部文档无第二解释器口径"),
    ("④ 教程加成 6 步", "QUICKSTART.md", probe_extra_step,
     "④ 零基础教程步骤数 ≤5（M5）"),
    ("⑤ 手改自动生成的参考（1 个字）", "docs/API_REFERENCE.md", probe_md_drift,
     "⑤ API 参考与代码同源"),
    ("⑥ 30/138 条端点描述被抹（覆盖率 78.3% < 80%，counts 仍自称 138）",
     "docs/api_reference.json",
     lambda b: _blank_descriptions(b, 30), "⑥ M8 端点描述覆盖率 ≥80%"),
    ("⑦ 参考里塞一条路由表没有的端点", "docs/api_reference.json",
     _add_fake_endpoint, "⑦ 参考里没有路由表之外的多余端点"),
    ("⑧ 从环境变量文档删掉 LDA_ROOT 表格行", "docs/ENVIRONMENT.md", probe_env_missing,
     "⑧ 代码里读到的 LDA_* 环境变量全部有"),
    ("⑨ 部署说明正文塞回旧口径 B1–B11", "LDA_D-13_WebUI内网部署说明.md",
     probe_stale_word, "⑨ 部署说明**现役口径**已无过期清单"),
    ("⑩ 删掉未登录入口提示元素", "lda/lda_webui/static/index.html", probe_hint,
     "⑩ 页面存在未登录入口提示元素"),
    ("⑪ run_cli_smoke 默认值改回写死路径", "lda/run_cli_smoke.py",
     probe_cli_default, "⑪ run_cli_smoke 的解释器默认值 = 当前解释器"),
]

TMP_AUTHOR_FILE = os.path.join(LDA, "tmp_probe_author_path.py")


def main():
    print("=" * 74)
    print("P2 门禁突变探针 —— 每条判据造一个真实反例，看它会不会响")
    print("=" * 74)

    # 基线
    rc, fails = run_smoke()
    print("\n[基线] rc=%d · FAIL 行 %d 条 %s" % (rc, len(fails), fails))
    assert rc == 0 and not fails, "基线必须全绿，否则先修门禁"

    # 额外：往 lda/ 塞一个写死作者路径的新文件
    ok_all = True
    for title, rel, mut, want in PROBES:
        raw = _read_bytes(rel)
        before = _sha(raw)
        try:
            open(os.path.join(ROOT, rel), "wb").write(mut(raw))
            rc, fails = run_smoke()
            hit = any(want in f for f in fails)
            extra = [f for f in fails if want not in f]
            status = "✅ 会响" if hit else "❌ 恒真（不响）"
            print("\n[%s] %s" % (status, title))
            print("    目标判据: %s" % want)
            print("    连带变红 %d 条%s" % (len(extra),
                                        ("：" + " | ".join(x[:70] for x in extra[:4]))
                                        if extra else ""))
            ok_all = ok_all and hit
        finally:
            cur = _read_bytes(rel)
            if _sha(cur) != before:
                open(os.path.join(ROOT, rel), "wb").write(raw)
            after = _sha(_read_bytes(rel))
            assert after == before, "还原失败！%s %s != %s" % (rel, after, before)
            print("    还原 ✓ sha256 %s" % after)

    # ⑪ 的另一半：新建一个含作者路径的 .py
    if os.path.exists(TMP_AUTHOR_FILE):
        os.remove(TMP_AUTHOR_FILE)
    try:
        open(TMP_AUTHOR_FILE, "wb").write(
            b'"""probe"""\nPROBE = "D:/agent_LDA"\n')
        rc, fails = run_smoke()
        want = "⑪ 代码字面量无作者机器路径"
        hit = any(want in f for f in fails)
        print("\n[%s] ⑪ 往 lda/ 新建一个含作者机器路径的 .py"
              % ("✅ 会响" if hit else "❌ 恒真（不响）"))
        ok_all = ok_all and hit
    finally:
        if os.path.exists(TMP_AUTHOR_FILE):
            os.remove(TMP_AUTHOR_FILE)
        print("    还原 ✓ 临时文件已删除:", not os.path.exists(TMP_AUTHOR_FILE))

    # 收尾：全量复查
    rc, fails = run_smoke()
    print("\n[收尾复查] rc=%d · FAIL %d 条" % (rc, len(fails)))
    ok_all = ok_all and rc == 0 and not fails
    print("\n探针结论：%s" % ("全部判据都会响 ✅" if ok_all else "存在恒真判据 ❌"))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
