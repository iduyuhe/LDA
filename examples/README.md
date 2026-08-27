# LDA 示例库（examples）

最小可跑示例，帮助新人 5 分钟跑通「设计 → 版图 → 主权几何 DRC / 寄生估算 → 报告」闭环。

## 1. 生成示例版图并跑主权几何 DRC

```bash
# 生成示例 GDS（环型器件 + 金属走线）
python examples/sample_layout.py sample_layout.gds

# 主权几何 DRC 快查（gds_drc，子集诚实标注非 foundry 全量）
lda check --gds sample_layout.gds
```

## 2. 跑一个设计（CLI 薄壳）

```bash
# 设计一个环形分波器，返回被验证过的设计包
lda design --kind RingAddDrop --params '{"R":10.0,"gap":0.3}'

# 生成对照报告（--quick 跑子集，更快）
lda report --quick
```

## 3. gdsfactory 兼容（可选，B 级依赖）

> gdsfactory 未安装时 `lda gf` 会打印指引并优雅退出（不阻断 LDA 自有路径）。

```bash
# 把 gdsfactory 组件转成 LDA 链路 spec
lda gf your_component.py --out your_component.lda_spec.json
```

## 诚实边界

- 几何 DRC / 几何寄生估算为**主权子集**，标注"非 foundry 工艺级全量 deck"。
- 真实 PDK 接入、晶圆实测回流、封装测试属发动期（物理/资源边界）。

详见仓库根 `LDA_一页纸_概览.md` 与 `README.md` 的「当前账本」段。
