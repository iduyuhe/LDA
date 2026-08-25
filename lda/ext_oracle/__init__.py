"""ext_oracle — 外部 ORACLE 桥接（B 级主权副本，GPL 隔离）。

`meep_oracle.py` 在隔离环境以子进程方式运行 Meep（FDTD 确定性求解器），
作为 LDA 验证体系的可选 ORACLE（非 AI ground 之一）。仅当显式启用时调用，
缺省零依赖的 numpy 自举求解核即可满足核心验证。
"""
