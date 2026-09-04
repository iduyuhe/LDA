"""CI 护栏（T-7 · v0.9.37）：一键复现入口 quickverify 自身守护。

quickverify.py 是外部人一键复现的核心（环境自检 + 版本核对 + harness 48 锚）。
本 smoke 验证 **quickverify 的守护逻辑本身会响**（铁律：没被验证过的护栏
不算护栏）——通过其内建 `--selfcheck`：
  A. 正向：当前 CI 环境必装依赖齐全、Python ≥ 3.12；
  B. 反向：注入 blocked 集合模拟缺 numpy/scipy/jsonschema ⇒ _check_env
     必须报 missing（若屏蔽后仍 ok=True，说明环境检查是假护栏）；
  C. 版本核对：pyproject 版本串必须能解析（守卫前提不空）。

秒级执行，不跑任何子进程验证（那部分由 quickverify 主模式覆盖）。
"""
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PY = sys.executable


def main() -> int:
    # 必须用当前解释器（quickverify 内 _PY = sys.executable）
    p = subprocess.run([_PY, os.path.join(_HERE, "quickverify.py"),
                        "--selfcheck"],
                       capture_output=True, text=True, encoding="utf-8")
    out = (p.stdout or "") + (("\n" + p.stderr) if p.stderr else "")
    print(out.strip())
    # 兼容历史命名：早期 commit 曾以 88/8x 报 PASS；现以退出码为准。
    if p.returncode != 0:
        print("[run_quickverify_smoke] FAIL · quickverify --selfcheck 退出码非 0")
        return 1
    # 输出里必须含 PASS 字样（防 selfcheck 静默退化却仍返回 0）
    if "PASS" not in out:
        print("[run_quickverify_smoke] FAIL · 输出无 PASS 标记")
        return 1
    print("[run_quickverify_smoke] PASS · quickverify 守护逻辑会响")
    return 0


if __name__ == "__main__":
    sys.exit(main())
