"""可选 SAX ORACLE（B4 add-drop 环形谐振器电路级确定性验证）。

核心 harness 不依赖 SAX；此处为**预留接口**。当环境装有 sax
(Apache-2.0，可深度集成，见《白皮书》§11 许可证红线) 时，`ring_fsr_via_sax`
可建立环形电路提取 drop 端口 FSR，作为解析 ORACLE 的交叉验证。

当前默认返回 None（harness 回退到解析环形 ORACLE），待 SAX 接入环境后启用。
"""


def ring_fsr_via_sax(R, n_g, wl, neff=2.44):
    """预留：用 SAX 电路提取环形谐振器 FSR(nm)。当前未启用，返回 None。

    启用示例（环境装有 sax 时）：
        import sax, numpy as np
        from sax.models import straight, coupler
        ... 建立 ring circuit，扫描波长取 drop 端口 minima 间距 ...
    """
    return None
