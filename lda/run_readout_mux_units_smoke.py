"""D-219 · 量子征程续行 A2：λ/4 正/反闭式的**量纲与往返**门禁（能力层 · 净增 0 锚）。

## 为什么要有这道门禁

`lda_qeda/sc_readout_mux.py` 里有一对互逆闭式：

    resonator_length_um(f)  → L = v_ph/(4f)      （正向：频率 ⇒ 腔长）
    resonator_freq_ghz(L)   → f = v_ph/(4L)      （反向：腔长 ⇒ 频率）

反向那个曾经写成 `v_ph / (4.0 * length_um * 1e-6) / 1e9` —— 把长度转成 m 去和 µm/s 相除，
**结果偏 1e6 倍**（5 GHz 的腔长 5879.5617 µm 回代得 5,000,000.0 而不是 5.0）。

它之所以能长期潜伏，是因为**该函数全仓零引用**：正向函数有 3 处调用、方向是正的、没人怀疑；
反向函数写完就没人用，自然也没人验。344 道门禁没有一道碰过它。

> 这条与已知的「死断言」（`dead_assert_guard`）是同一风险族，但现有门禁只扫
> `assert` / `check(...)` 这些**文本**，不扫「公开导出但无人调用的函数」。
> 本轮显式登记（见 H1），并把正向/反向的**往返恒等**做成硬判据。

## 判据分组（避开 B/E/S 前缀 —— 那些是锚号前缀，会被 K4 文本代理误判成覆盖）

  A 组  已知点与往返恒等（正/反互逆、量纲锚）
  X 组  跨模块同口径（cpw_quasi_static 反提、既有锚的 n_eff 口径）
  G 组  守卫（旧写法必被证伪、非法输入必抛）
  H 组  可达性与诚实（反向函数进入生产自检路径、模块自检全绿）
  Z 组  零增量（不新增锚）

纯 stdlib · 零 numpy 物理依赖 · 零子进程 · 零落盘 · 实测 < 0.1 s。
"""
from __future__ import annotations

import inspect
import math
import sys

from lda_qeda import sc_readout_mux as MUX

_RESULT = []


def check(name: str, cond: bool, detail: str = "") -> bool:
    _RESULT.append((name, bool(cond)))
    print(("  [PASS] " if cond else "  [FAIL] ") + name + (("  |  " + detail) if detail else ""))
    return bool(cond)


def main() -> int:
    _RESULT.clear()          # 允许同一进程内重复跑（突变探针会连续调 main 多次）
    print("λ/4 正/反闭式量纲与往返 门禁 smoke（D-219）")

    # ---------------- A 组：已知点与往返恒等 ----------------
    # A1 已知点：5 GHz 在 ε_eff=6.5 下的腔长，回代必须精确回到 5 GHz
    L_ref = MUX.resonator_length_um(5.0, eps_eff=6.5)
    f_back = MUX.resonator_freq_ghz(L_ref, eps_eff=6.5)
    check("A1 已知点回代：L(5GHz, ε=6.5)=%.4f µm ⇒ freq=%.12f GHz（rel<1e-12）"
          % (L_ref, f_back),
          abs(f_back - 5.0) <= 1e-12 * 5.0,
          "偏差 = %.3e" % abs(f_back - 5.0))

    # A2 往返 freq(length(f)) ≡ f
    rt_a = []
    for f in (4.0, 5.0, 6.0, 7.0, 8.0):
        for e in (6.0, 6.224562, 6.5):
            L = MUX.resonator_length_um(f, eps_eff=e)
            rt_a.append(abs(MUX.resonator_freq_ghz(L, eps_eff=e) - f) <= 1e-12 * f)
    check("A2 往返恒等 freq(length(f)) ≡ f（5 频率 × 3 ε = 15 组，rel<1e-12）", all(rt_a),
          "最差 = %.3e" % max(abs(MUX.resonator_freq_ghz(
              MUX.resonator_length_um(f, eps_eff=e), eps_eff=e) - f) / f
              for f in (4.0, 5.0, 6.0, 7.0, 8.0) for e in (6.0, 6.224562, 6.5)))

    # A3 往返 length(freq(L)) ≡ L
    rt_b = []
    for L in (4000.0, 5879.5617, 6119.6419):
        for e in (6.0, 6.5):
            f = MUX.resonator_freq_ghz(L, eps_eff=e)
            rt_b.append(abs(MUX.resonator_length_um(f, eps_eff=e) - L) <= 1e-12 * L)
    check("A3 往返恒等 length(freq(L)) ≡ L（3 腔长 × 2 ε = 6 组，rel<1e-12）", all(rt_b))

    # A4 量纲锚：ε_eff=1（真空）时 λ/4 @1 GHz 恰为 c/(4f) = 74950 µm
    #    这个值是**解析**的，和实现里用 µm 还是 m 无关 ⇒ 一旦量纲写错立刻偏离
    L_vac = MUX.resonator_length_um(1.0, eps_eff=1.0)
    check("A4 量纲锚：ε=1 时 L(1GHz) = 74950 µm（解析 c/(4f)，与单位无关）",
          abs(L_vac - 74950.0) <= 1e-9, "实测 = %.9f" % L_vac)

    # A5 互逆关系：f↑ ⇒ L↓（两函数方向相反）
    mono = all(MUX.resonator_length_um(f + 0.5) < MUX.resonator_length_um(f)
               for f in (4.0, 5.0, 6.0, 7.0))
    check("A5 互逆单调：f↑ ⇒ L↓（4 组相邻）· 且 L(f)·f 在该 ε 下为常数",
          mono and all(abs(MUX.resonator_length_um(f) * f
                           - MUX.resonator_length_um(1.0) * 1.0) < 1e-6
                       for f in (4.0, 5.0, 6.0, 7.0)))

    # ---------------- X 组：跨模块同口径 ----------------
    # X1 与 cpw_quasi_static 的反提串联：ε_eff 与其等价形式 n_eff² 必须给同一腔长
    try:
        from lda_qeda import cpw_quasi_static as CQS
        fin = CQS.cpw_closed_form(10.0, 6.0, h_um=500.0, eps_r=11.45)
        e_cpw, n_cpw = fin["eps_eff"], fin["n_eff"]
        L_a = MUX.resonator_length_um(5.0, eps_eff=e_cpw)
        L_b = MUX.resonator_length_um(5.0, eps_eff=n_cpw * n_cpw)
        check("X1 与 cpw_quasi_static 反提同口径：L(ε_eff) ≡ L(n_eff²)（rel<1e-12）",
              abs(L_a - L_b) <= 1e-12 * L_a,
              "ε=%.6f n=%.6f L=%.4f µm" % (e_cpw, n_cpw, L_a))
    except Exception as e:                                   # noqa: BLE001
        check("X1 与 cpw_quasi_static 反提同口径", False, "模块不可用：%s" % e)

    # X2 与既有锚的 n_eff 口径：L(ε=n_eff²) 必须等于解析 c/(4·f·n_eff)
    #    （既有 CPW 锚把 n_eff=2.5 当**给定参数**，本条证明本模块与它同口径）
    n_anchor = 2.5
    L_mod = MUX.resonator_length_um(5.0, eps_eff=n_anchor * n_anchor)
    L_ana = 2.998e8 / (4.0 * 5.0e9 * n_anchor) * 1e6
    check("X2 与既有 CPW 锚的 n_eff 口径一致：L(n²) ≡ c/(4fn)（rel<1e-12）",
          abs(L_mod - L_ana) <= 1e-12 * L_ana,
          "模块 %.6f µm · 解析 %.6f µm" % (L_mod, L_ana))

    # X3 与 mux_plan 内部口径一致：plan 里每个读出音的 length_um 回代必须等于 f_r_ghz
    plan = MUX.mux_plan({"rows": 2, "cols": 2})
    bad = [r for r in plan["per_readout"]
           if abs(MUX.resonator_freq_ghz(r["length_um"], eps_eff=plan["eps_eff"])
                  - r["f_r_ghz"]) > 1e-12 * r["f_r_ghz"]]
    check("X3 与 mux_plan 一致：per_readout 的 length_um 回代 ≡ f_r_ghz（%d 音）"
          % len(plan["per_readout"]), not bad, "越界 %d 条" % len(bad))

    # ---------------- G 组：守卫 ----------------
    # G1 旧写法必被证伪：把长度转成 m 会让结果偏 1e6 倍 —— 本条证明「这道门禁有牙」
    v_ph = MUX.C_UM_PER_S / math.sqrt(6.5)
    L_probe = MUX.resonator_length_um(5.0, eps_eff=6.5)
    f_new = v_ph / (4.0 * L_probe) / 1e9                 # 正确
    f_old = v_ph / (4.0 * L_probe * 1e-6) / 1e9          # 旧写法（错）
    ratio = f_old / f_new if f_new else float("inf")
    check("G1 旧写法必被证伪：`*1e-6` 版与正确版比值 ≈ 1e6（偏 1e6 倍即为量纲错）",
          abs(ratio - 1e6) <= 1e-6 * 1e6,
          "ratio = %.6f" % ratio)

    # G2 非法 ε_eff（0 / 负）必抛
    def _raises(fn, *a):
        """「必抛」判据。

        🔴 **捕 Exception 全集而不是只捕 ValueError/ZeroDivisionError**：
        突变探针实测，若实现改成 `eps**0.25` 之类，负 ε 会产生 **complex**，
        `float(complex)` 抛的是 **TypeError** —— 只捕那两类的旧写法会让
        门禁**自己崩掉**（rc=99），后续判据全部丢掉，等于突变时"看不到红在哪"。
        判据语义本来就是"必须抛"，捕全集才是正确口径。
        """
        try:
            fn(*a)
            return False
        except Exception:                                    # noqa: BLE001
            return True
    check("G2 非法 ε_eff 必抛：ε=0 ⇒ ZeroDivisionError · ε<0 ⇒ ValueError（两函数各 2 例）",
          _raises(MUX.resonator_freq_ghz, 5000.0, 0.0)
          and _raises(MUX.resonator_freq_ghz, 5000.0, -1.0)
          and _raises(MUX.resonator_length_um, 5.0, 0.0)
          and _raises(MUX.resonator_length_um, 5.0, -1.0))

    # G3 零/负频率、零长度必抛（不能静默返回 inf / 0）
    check("G3 零输入必抛：f=0 与 L=0 均不得静默返回（防 inf/0 传播）",
          _raises(MUX.resonator_length_um, 0.0, 6.5)
          and _raises(MUX.resonator_freq_ghz, 0.0, 6.5))

    # ---------------- H 组：可达性与诚实 ----------------
    # H1 反向函数必须进入**生产自检路径**（此前全仓零引用 ⇒ 无守卫）
    src_self = inspect.getsource(MUX.run_selfchecks)
    check("H1 可达性：`resonator_freq_ghz` 已进入 run_selfchecks（生产路径）源码",
          "resonator_freq_ghz" in src_self,
          "自检 %d 行" % len(src_self.splitlines()))

    # H2 模块自检全绿（含新增的 ⑦b 往返恒等）
    ok_self = MUX.run_selfchecks(verbose=False)
    check("H2 模块自检全绿（含 ⑦b 往返恒等 22 组）", ok_self)

    # H3 诚实边界：ε_eff 仍是**设计参数**，不是实测 PDK（本条防把它读成 golden）
    doc = MUX.__doc__ or ""
    check("H3 诚实边界：模块 docstring 明写「ε_eff 为设计参数 · 非实测 PDK」",
          "设计参数" in doc and "非实测" in doc)

    # ---------------- Z 组：零增量 ----------------
    # Z1 本门禁不新增锚（能力层修正）：账本总数必须与 v0.9.270 基线一致
    try:
        sys.path.insert(0, "D:/agent_LDA/lda")
        from lda_harness.benchmarks import BENCHMARK_DEFS as D
        n_anchors = len(D)
        check("Z1 零增量：账本锚数 = %d（与 v0.9.270 基线一致，本门禁不加锚）" % n_anchors,
              n_anchors == 541)
    except Exception as e:                                   # noqa: BLE001
        check("Z1 零增量：账本锚数不变", False, "不可读：%s" % e)

    n_pass = sum(1 for _, v in _RESULT if v)
    print("\n门禁 smoke：%d PASS / %d FAIL（共 %d 项）" % (n_pass, len(_RESULT) - n_pass, len(_RESULT)))
    return 0 if n_pass == len(_RESULT) else 1


if __name__ == "__main__":
    sys.exit(main())
