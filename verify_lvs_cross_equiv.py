"""[DEPRECATED · v0.9.36] LVS 短路检测等价验证 —— 薄委托层。

🔴 历史缺陷（本文件曾自毁）：旧版本在文件内部**内嵌了一份
`_collect_cross_shorts` 副本**（v0.8.44 标量 cell 版），比对的是「自己抄的
副本」而非 `lda/lda_l2/lvs.py` 的生产实现——生产代码改坏了它照样 PASS，
属于「护栏测的不是被护栏的东西」的假护栏（铁律：护栏必须测生产代码）。

v0.9.36 起本文件仅转发到生产级护栏 `lda/run_lvs_cross_equiv_smoke.py`
（直接 import 生产 `lda_l2.lvs._collect_cross_shorts`，48 组断言，
含狭长阵列特护场景）。新代码请直接调用那个 smoke。
"""
import os
import runpy
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_TARGET = os.path.join(_HERE, "lda", "run_lvs_cross_equiv_smoke.py")

if __name__ == "__main__":
    print("[DEPRECATED] 请直接运行 lda/run_lvs_cross_equiv_smoke.py；本入口仅转发。")
    sys.path.insert(0, os.path.join(_HERE, "lda"))
    runpy.run_path(_TARGET, run_name="__main__")
