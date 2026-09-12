# LDA T1-B-W1 · DEVSIM 主权镜像冷备与离线构建证据

> 配套 `lda/lda_pdk/sovereign_deps.py`（DEVSIM = B 级 Apache-2.0，借今踢后）
> 与 `docs/lda_t1b_ear74423_compliance.md`（成熟节点用途声明 + EAR 744.23）。
> 本文件是 **T1-B-W1** 交付物：DEVSIM fork 镜像冷备 + 锁定提交 + 离线 wheel 清单
> + subprocess 隔离纪律 + CI 门禁。主权扫描 B 级登记已在 `sovereign_deps.py` 完成。

---

## 1. 主权分级与许可证（已登记）

- **分级**：B 级（MIT/BSD/Apache-2.0，可 fork 主权副本，借今踢后）。
- **许可证**：Apache-2.0（PyPI `devsim` 元数据 `license = Apache License, Version 2.0`，
  `sovereign_deps.py` 条目 `"DEVSIM (TCAD 内核)", "B", "Apache-2.0"`）。
- **EAR 734.7b 基础**：公开可得源码（Apache-2.0）默认不受出口管制，可合法 fork。
- **用途纪律**：仅用于**成熟节点 / 非先进用途**（EAR 744.23 按「用途」管制，非代码许可）。
  详见 `docs/lda_t1b_ear74423_compliance.md`。

---

## 2. 锁定提交（源码镜像冷备）

| 项 | 值 |
|---|---|
| 仓库 | https://github.com/devsim/devsim |
| 锁定分支/版本 | **r2.11.0**（= `main` HEAD，与 PyPI 发布 wheel 2.11.0 对齐） |
| **锁定提交（pin）** | `43b41ca845184c47e22b72d144db7e7db8509377` |
| 本地镜像路径 | `vendor/devsim_mirror/`（gitignored，不进版本库） |
| 远程主权副本目标 | Gitee fork（规划 `fork_to="Gitee"`，离线环境执行） |

> 注：GitHub 另有 `r2.11.1` 补丁分支，但 PyPI 发布 wheel 为 2.11.0。为保持
> 「源码提交 ↔ 发布 wheel 版本」供应链一致，镜像锁定 **r2.11.0 = 2.11.0**。

---

## 3. 离线 wheel 清单（PyPI 2.11.0，cp39-abi3）

离线安装缓存（`pip download devsim==2.11.0 --no-deps -d vendor/devsim_wheels`）：
4 个预编译 wheel，单个 ~4.5–5.8 MB：

| 平台 | wheel 文件名 | 大小 (B) |
|---|---|---|
| macOS arm64 | `devsim-2.11.0-cp39-abi3-macosx_14_0_arm64.whl` | 4,992,357 |
| manylinux aarch64 | `devsim-2.11.0-cp39-abi3-manylinux_2_26_aarch64.manylinux_2_28_aarch64.whl` | 5,832,675 |
| manylinux x86_64 | `devsim-2.11.0-cp39-abi3-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl` | 5,632,794 |
| Windows amd64 | `devsim-2.11.0-cp39-abi3-win_amd64.whl` | 4,584,317 |

- `cp39-abi3` → 兼容 CPython 3.9+（ABI3 稳定 ABI）。
- **离线获取命令**（离线/空气间隙环境执行，记录 sha256 进 `vendor/devsim_wheels/SHA256SUMS`）：
  `pip download devsim==2.11.0 --no-deps -d vendor/devsim_wheels`
  `cd vendor/devsim_wheels && sha256sum *.whl > SHA256SUMS`
- 本环境已确认 PyPI 元数据可达（见 `_devsim_wheels.txt`）；实际 wheel 下载留待
  离线构建环境（避免大二进制进仓库）。

---

## 4. subprocess 隔离纪律（核心永不污染）

> 对齐 `lda/lda_harness/oracle_tidy3d.py` 的 B 级处理：**核心绝不 import DEVSIM**。

- DEVSIM 只经 **`lda/lda_solver/devsim_bridge.py`** 调起（subprocess 外部进程），
  **仅回标量**（dict of float / None），不回传任何 DEVSIM 内部对象/数组引用。
- DEVSIM 解出的 N(x)/P(x) 仅作**候选交叉校验**，与自研 C 级候选
  (`drift_diffusion_1d.solve_pn_junction_1d`) 互证；**永不**作 ORACLE 真值
  （T1 输出不作 ORACLE 纪律）。死标量判决由 Sze 教科书闭式 golden 定。
- DEVSIM 进程崩溃 → 捕获异常 → 返回 None（不污染核心、不静默假绿），由调用方
  回退自研 C 级候选。这是刻意主权安全默认。
- 本环境未安装 DEVSIM（仅镜像冷备），故跨校验默认 None，链路走自研候选。

---

## 5. CI 门禁（offline build evidence gate）

`lda/run_t1b_devsim_cold_backup_smoke.py`（已注册 `CORE_SMOKES`，core 160→161）：
1. **镜像存在**：`vendor/devsim_mirror/` 存在 → 否则 FAIL（冷备缺失）。
2. **提交锁定**：`git -C vendor/devsim_mirror rev-parse HEAD == 43b41ca...` → 否则 FAIL。
3. **许可证**：镜像内含 `LICENSE`（Apache-2.0）→ 否则 FAIL。
4. **可选 import 标量隔离**：若 `devsim` 可 import/可执行，运行最小 p-n 跨校验，
   断言返回为**标量 dict（非对象）**；不可用时 SKIP（不破坏 CI）。

门禁同时闭合 T1-B-W3 收尾的「离线构建证据 CI 门禁」（`run_optional_import_guard_smoke`
的 T1 内核许可扫描）缺口：源码提交锁定 + 许可证 + 隔离纪律，三位一体证据链。

---

## 6. 重建步骤（从零恢复冷备）

```bash
# 1) 源码镜像（锁定 r2.11.0）
git clone --depth 1 --branch r2.11.0 https://github.com/devsim/devsim vendor/devsim_mirror
git -C vendor/devsim_mirror rev-parse HEAD   # 须 = 43b41ca845184c47e22b72d144db7e7db8509377

# 2) 离线 wheel 缓存（离线环境）
pip download devsim==2.11.0 --no-deps -d vendor/devsim_wheels
cd vendor/devsim_wheels && sha256sum *.whl > SHA256SUMS

# 3) 远程主权副本（Gitee fork，离线/空气间隙执行）
git -C vendor/devsim_mirror push git@github.com:du-org/devsim.git r2.11.0:r2.11.0
```
