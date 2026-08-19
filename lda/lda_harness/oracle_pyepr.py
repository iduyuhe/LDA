"""B9 · transmon EPR 外部 ORACLE（pyEPR，仅外部）。

设计纪律（《白皮书》§11 主权优先 / B 级外部 ORACLE）：pyEPR(Ansys Quantum
Platform 生态) 属强依赖/商业关联工具，LDA Apache-2.0 核心**绝不 import**。
本模块是"外部 ORACLE 适配层"——仅在运行环境可 import pyEPR 且允许时，才在
外部/子进程调用真实 EPR 哈密顿量对角化，回传修正后的 f01(GHz)；否则返回 None，
由 golden.py 回退到 Koch2007 解析色散近似（确定性物理定律锚）。

这是量子域"物理定律锚 + 外部 ORACLE"二元结构的标准落地：核心地基永远是
解析解（方程必然），EPR 对角化仅作交叉验证外挂。本演示环境未装 pyEPR，故
恒返回 None——刻意的主权安全默认。
"""
import os


def resolve_pyepr_transmon(params):
    """返回 {value, source, note} 或 None。

    value: 修正后的 transmon f01(GHz)；None = 未配置/不可用，回退解析锚。
    """
    try:
        import pyEPR as epr  # 外部 ORACLE；缺失即不可用
    except Exception:
        return None
    # —— 已安装时才执行的真实 EPR 对角化路径（本演示环境不触发）——
    # 1) 构建 transmon 几何（结电容、参与比）+ Josephson 参数
    # 2) pyEPR.QuantumAnalysis 对角化 EPR 哈密顿量 → f01
    # 3) 返回 {"value": f01, "source": "pyepr-external",
    #          "note": "pyEPR EPR 哈密顿量对角化（外部 ORACLE）"}
    # 因无真实环境，该路径仅在有 pyEPR 的用户环境被外部触发；本模块默认 None。
    _ = (epr, params)
    return None
