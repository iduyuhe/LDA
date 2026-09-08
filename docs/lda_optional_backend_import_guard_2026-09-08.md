# LDA · 可选后端（torch / numba / cupy）残留硬依赖清零 —— v0.9.59 交付报告

**日期**：2026-09-08
**对应剩余清单**：① 可立即推进 · 第 3 项「torch/numba 残留硬 import 清理（低优先）」
**版本**：v0.9.58 → **v0.9.59** ｜ **CI core 134 → 135**（新增 1 个 smoke）
**结论**：核心求解链对 torch / numba 的**硬依赖至此为零**；顶层 GPU / 基准 / 自检脚本在缺后端时
由「ImportError 裸崩」改为「打印安装指引 + 退出码 2」。**零物理判据改动、零 golden 改动、
52 锚与三分类 26/1/25 均不变。**

---

## 1. 背景：v0.9.53 治理⑤ 做了一半

v0.9.53（治理⑤）把**核心导入链**上的两个模块改成 try/except 优雅降级：

| 模块 | 处理 |
|---|---|
| `lda_solver/fdtd3d_torch.py` | `import torch` → try/except + `_HAVE_TORCH` |
| `lda_solver/fdtd3d_numba.py` | `from numba import njit, prange` → try/except + `_HAVE_NUMBA` |

但**顶层脚本**没跟着改。当时记录为「低优先，仅顶层误引才触发」—— 本轮把它收掉。

## 2. 实测盘点

用 ast 精确判定「模块级（顶层、非 try / 非函数类体内）裸 import」后，`lda/` 全包 393 个 .py 中
命中 **4 处**，全部在 `lda/lda_solver/`：

| 文件 | 行 | 语句 |
|---|---|---|
| `activate_gpu_fdtd3d.py` | 28 | `import torch` |
| `run_fdtd3d_torch_selfcheck.py` | 18 | `import torch` |
| `run_large_grid.py` | 22 | `import torch` |
| `verify_gpu_focused.py` | 10 | `import torch` |

⚠️ **盘点方法本身差点出错**：第一轮用 grep 全文搜 `^\s*import torch`，结果被仓库内的
`lda_cuda_venv/`（第三方 site-packages，上百条 torch 自身源码）淹没，且**缩进内的合法
try/except 也会被误计**。改用 ast 解析 + 排除 try / 函数 / 类体后才是真清单。

**动态实跑又额外暴露 2 个同类缺陷**（静态扫描抓不到，因为它们的 import 在 `main()` 函数体内）：

| 文件 | 症状 |
|---|---|
| `benchmark_fdtd3d_torch.py` | `main()` 内 `import torch as _t` 判 CUDA ⇒ 缺 torch 时裸崩 |
| `run_fdtd3d_numba_selfcheck.py` | 无任何守卫 ⇒ 缺 numba 时 `solve_spectrum_numba` 抛 ImportError 裸崩 |

⇒ 本轮共修 **6 个文件**（4 静态 + 2 动态）。

## 3. 改动

统一范式（与 v0.9.53 完全一致）：

```python
try:  # torch 为可选性能后端（[torch] extra）；缺失时本脚本仍可导入，main() 打印指引后退出码 2
    import torch
    _HAVE_TORCH = True
except Exception:  # noqa: BLE001
    torch = None
    _HAVE_TORCH = False
```

入口守卫（退出码 **2** = 「依赖不可用」，与 `activate_gpu_fdtd3d.py` 原有的
`_guide_and_exit()` 语义一致，不占用 0/1 的 PASS/FAIL 语义）：

```python
def main():
    if not _HAVE_TORCH:
        print(">>> 未安装 torch（可选依赖）：……")
        print(">>> 安装：pip install torch --index-url https://mirrors.tuna.tsinghua.edu.cn/pytorch/whl/cu128")
        print(">>> CPU 路径不受影响；核心求解链不依赖 torch。")
        return 2
```

| 文件 | 无后端时的行为（改后） |
|---|---|
| `activate_gpu_fdtd3d.py` | 打印「未安装 torch」+ 原有 CUDA 安装指引，退出 2 |
| `run_fdtd3d_torch_selfcheck.py` | 打印指引并**指向纯 numpy sovereign 核**（`run_fdtd3d_selfcheck.py`），退出 2 |
| `run_large_grid.py` | 打印指引，退出 2（在 `parse_args` 之后，不启动仿真） |
| `verify_gpu_focused.py` | 打印指引，退出 2（原为 `assert` 崩溃） |
| `benchmark_fdtd3d_torch.py` | **剔除 torch-cpu / torch-cuda 后端，照常跑 numpy / numba-cpu 基准**，正常结束 |
| `run_fdtd3d_numba_selfcheck.py` | 打印指引并指向 numpy 核，退出 2 |

🔴 **有后端时行为逐字不变**：守卫不触发，走原路径。本机（CI 解释器）torch 与 numba 均在场 ⇒
零回归风险。

## 4. 护栏：`run_optional_import_guard_smoke.py`（16 判据，进 CI core）

设计上刻意避开「硬编码清单」这个定时炸弹（v0.9.41 扩库铁律：凡「等值断言 + 会增长的集合」
= 定时炸弹，一律改**包含式 + 动态计数**）。

### ① 静态：ast 全包扫描

- 扫描 `lda/` 全包 **393 个 .py**（`lda_cuda_venv/` 在包外，天然排除）。
- 判定：任何**模块级**（不在 `try` / 函数 / 类体内）的 `import torch|numba|cupy` 或
  `from torch|numba|cupy import ...` 即为违规。
  - 函数内延迟导入**放行**（语义上不是硬依赖，v0.9.53 同口径）。
- 附防漂移断言：扫描文件数必须 > 200（写窄了会红）。

### ② 静态：点名可选后端的模块必须有守卫标志

文件名含 `torch` / `numba` / `cupy` 的模块必须有 `HAVE_TORCH` / `HAVE_NUMBA` / `HAVE_CUPY`
（子串匹配，兼容 `_HAVE_TORCH` 与历史命名 `HAVE_NUMBA` 两种写法）。当前 **7 个**全覆盖。

### ③ 动态：屏蔽环境实跑顶层脚本

子进程内劫持 `builtins.__import__`（对 torch / numba / cupy 抛 ImportError）后
`runpy.run_path(script, run_name="__main__")`，断言：**不裸崩**，且缺后端时退出码 = 2
并打印 torch 指引。

自动发现条件（三条同时成立）：
1. 文件名匹配顶层脚本命名约定 `run_` / `activate_` / `verify_`;
2. 含 `__name__ == "__main__"`;
3. 含 `_HAVE_TORCH` 守卫标志。

当前命中 4 个，配「发现数 ≥ 4」防漂移断言。

### 反向测试（铁律：新护栏必须反向测试会响）

| 编号 | 内容 |
|---|---|
| R1-a | 坏样本「顶层 `import torch`」→ **必须被抓** |
| R1-b | 好样本「try 内 import」→ **必须放行** |
| R1-c | 好样本「函数体内延迟导入」→ **必须放行** |
| R1-d | 坏样本「顶层 `from numba import njit`」→ **必须被抓** |
| R1-e | 无 `HAVE_*` 标志的源码 → 必须判为「缺守卫」 |
| R1-f | 含 `_HAVE_NUMBA` 的源码 → 必须判为「有守卫」 |
| R2 | **顶层裸 import 的临时坏脚本实跑必须裸崩（退出码 −999）**，而非优雅 2 |

R1 是**双向标定**——只测坏样本不测好样本的话，扫描器写反了（把所有 import 都判违规）
也会全绿。R2 证明步骤③真的能区分「优雅降级」与「硬依赖」。

实测：**16 PASS / 0 FAIL**。

## 5. 过程中自己踩并修掉的两个坑

### 坑① 自动发现条件过宽 —— 把求解核模块拉进来实跑

第一版条件是「源码含 torch 且含 `__name__ == "__main__"`」，命中 **9 个**，其中
`fdtd2d_ring.py` / `fdtd3d_torch.py` / `adjoint_fdtd.py` / `fdtd3d_coupler.py` 是
**求解核模块**，自带 demo 型 `__main__` 块，实跑会真的启动 FDTD：

- `fdtd2d_ring.py` 跑超 **300 s** 触发 smoke 超时;
- `benchmark_fdtd3d_torch.py` 直接裸崩（EXITCODE −999）。

⇒ 收窄为「命名约定前缀 + 有 `_HAVE_TORCH` 守卫」。核模块的「可 import 不崩」由 v0.9.53 的
`run_torch_numba_optional_smoke.py` 负责，两个护栏职责不重叠。

### 坑② `runpy` 只改 `sys.argv[0]`

引导脚本用 `python -c BOOT <script>` 传脚本路径，于是 `sys.argv = ['-c', '<script>']`。
`runpy.run_path` 只把 `argv[0]` 换成脚本路径，**`argv[1]` 残留**，被 `run_large_grid.py`
的 argparse 当成未知位置参数 ⇒ 报 `unrecognized arguments` 并退出 2 —— 退出码凑巧对了，
但打印的是 usage 错误而非 torch 指引，`HINT_TORCH=False` 暴露了它。

⇒ 引导脚本内显式 `sys.argv = [script]`。

## 6. 诚实边界（本轮**没有**做的事）

- **没把 numba 顶层脚本纳入实跑清单**：本机 numba 在场，实跑 `run_fdtd3d_numba_selfcheck.py`
  会真跑 5 例 3D FDTD（分钟级），会明显拖慢 CI。它只受**源码级守卫断言**（②）约束 + 已修入口守卫。
  ⇒ 若将来要求「动态实跑」也覆盖 numba，需要给它加一个小规模 `--quick` 参数。
- **`cupy` 本机不可用**（ModuleNotFoundError），其路径只有静态扫描覆盖，无动态实跑证据。
- 没改任何物理判据、golden、tol；三分类 **26 严格独立 / 1 降级 / 25 自证桩**不变，
  52 锚不变。
- 求解核模块（`fdtd2d_ring.py` 等）的 demo `__main__` **未**加入口守卫 —— 它们不是人工操作入口，
  且加守卫会改动求解核源码；如有需要可后续统一。

## 7. 文件清单

| 文件 | 变更 |
|---|---|
| `lda/lda_solver/activate_gpu_fdtd3d.py` | 改 |
| `lda/lda_solver/run_fdtd3d_torch_selfcheck.py` | 改 |
| `lda/lda_solver/run_large_grid.py` | 改 |
| `lda/lda_solver/verify_gpu_focused.py` | 改 |
| `lda/lda_solver/benchmark_fdtd3d_torch.py` | 改 |
| `lda/lda_solver/run_fdtd3d_numba_selfcheck.py` | 改 |
| `lda/run_optional_import_guard_smoke.py` | **新增**（16 判据） |
| `lda/run_ci_regression.py` | CORE_SMOKES 增登记（134→135） |
| `pyproject.toml` | 0.9.58 → 0.9.59 |
| `README.md` | 顶行版本说明 + 账本 `CI core 134→135` |
| `docs/lda_optional_backend_import_guard_2026-09-08.md` | 本文件 |
