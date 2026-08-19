"""LDA · L3 自研求解核包（agent-native，C 级第一天自主）。

区别于 Meep/Lumerical 等"为人类操作而设计"的遗留系统：本包求解器从第一性
原理实现，暴露**机器优先接口**——结构化 spec 进、结构化谱 dict 出，agent 一
步消费出结果，人只做方向与判断（对应 LDA 人机协作总纲）。

当前落地：
- fdtd1d.py  自研 1D FDTD（Yee + 海绵吸收），求解一维麦克斯韦方程组
- tmm.py     多层膜传输矩阵法解析解（物理定律锚，作 FDTD 的非 AI ORACLE）

零外部依赖（仅 numpy），离线可跑，不 import 任何 GPL/商业求解器。
"""
from .fdtd1d import solve_spectrum as fdtd1d_spectrum
from .tmm import solve_spectrum as tmm_spectrum

__all__ = ["fdtd1d_spectrum", "tmm_spectrum"]
