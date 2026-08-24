"""D-94 生态共建 · 社区提交入口 — smoke 测试。

覆盖 submit_device / submit_devices_batch / submit_benchmark_proposal 三条
提交链路 + 自动推断主权分级 + 冲突感知 + 提案 pending。贡献库写入临时文件，
不污染仓库 contributions.json。验收 6/6。
"""
import os
import tempfile
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lda_pdk.submit import (
    submit_device, submit_devices_batch, submit_benchmark_proposal,
    list_contributions, infer_sovereign_class,
)

PASS = []
FAIL = []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name}" + (f" — {detail}" if detail else ""))


def main():
    tmp = tempfile.mkdtemp(prefix="lda_eco_submit_")
    cp = os.path.join(tmp, "contributions.json")

    # 1) 提交有效器件（community → 应推断 C）
    r1 = submit_device({
        "id": "eco-soi-community-1", "name": "SOI 波导 450nm",
        "tech": "光子·SOI", "foundry": "community",
        "layers": ["wg-core", "clad-oxide"], "params": {"w_um": 0.45, "h_um": 0.22},
        "tags": ["waveguide"], "note": "社区贡献样例",
    }, contrib_path=cp)
    check("submit 有效器件 → accepted", r1["status"] == "accepted", str(r1))
    check("  自动推断主权分级 = C", r1.get("sovereign_class") == "C",
          f"sovereign_class={r1.get('sovereign_class')}")

    # 2) 重复提交（同 id，不覆盖）→ conflict
    r2 = submit_device({
        "id": "eco-soi-community-1", "name": "重名冲突", "tech": "光子·SOI",
        "foundry": "community",
    }, contrib_path=cp)
    check("重复提交 → conflict", r2["status"] == "conflict", str(r2))

    # 3) 无效提交（缺 id）→ rejected
    r3 = submit_device({"name": "缺 id 的器件", "tech": "光子·SOI",
                        "foundry": "community"}, contrib_path=cp)
    check("无效提交（缺 id）→ rejected", r3["status"] == "rejected", str(r3))

    # 4) 自动推断分级：foundry 含 gdsfactory → B
    sc = infer_sovereign_class({"foundry": "gdsfactory fork"})
    check("infer_sovereign_class(gdsfactory) → B", sc == "B", f"->{sc}")
    r4 = submit_device({
        "id": "eco-b-1", "name": "基于 gdsfactory 的器件", "tech": "光子·SOI",
        "foundry": "gdsfactory fork",
    }, contrib_path=cp)
    check("  submit gdsfactory 器件 → accepted + B",
          r4["status"] == "accepted" and r4.get("sovereign_class") == "B", str(r4))

    # 5) 批量导入：2 接受 + 1 冲突
    r5 = submit_devices_batch([
        {"id": "eco-batch-1", "name": "批量A", "tech": "光子·SiN", "foundry": "community"},
        {"id": "eco-batch-2", "name": "批量B", "tech": "量子·超导", "foundry": "community"},
        {"id": "eco-soi-community-1", "name": "重名", "tech": "光子·SOI", "foundry": "community"},
    ], contrib_path=cp)
    acc = sum(1 for x in r5 if x["status"] == "accepted")
    con = sum(1 for x in r5 if x["status"] == "conflict")
    rej = sum(1 for x in r5 if x["status"] == "rejected")
    check("批量导入 2 接受 / 1 冲突 / 0 拒绝",
          acc == 2 and con == 1 and rej == 0, f"acc={acc} con={con} rej={rej}")

    # 6) harness 提案 → accepted_pending
    r6 = submit_benchmark_proposal({
        "id": "B19", "title": "微环 FSR", "metric": "FSR_GHz",
        "formula": "FSR = c / (n_g * L)", "oracle_fn_name": "b19_micro_ring_fsr",
        "tol": 0.5, "default_params": {"L_um": 100.0, "n_g": 4.0},
        "proposed_by": "community",
    }, contrib_path=cp)
    check("harness 提案 → accepted_pending",
          r6["status"] == "accepted_pending" and r6.get("review_status") == "pending",
          str(r6))

    # 快照一致性
    comm = list_contributions(contrib_path=cp)
    check("贡献库快照：器件数 = 4（1+1+2，冲突不计）",
          comm["device_count"] == 4, f"device_count={comm['device_count']}")
    check("贡献库快照：提案数 = 1",
          comm["proposal_count"] == 1, f"proposal_count={comm['proposal_count']}")

    print("\n=== D-94 提交入口 smoke 结果 ===")
    print(f"PASS={len(PASS)} FAIL={len(FAIL)}")
    if FAIL:
        print("失败项：")
        for n, d in FAIL:
            print(f"  - {n} ({d})")
        sys.exit(1)
    print("全部通过 ✅")
    sys.exit(0)


if __name__ == "__main__":
    main()
