"""D-94 生态共建 · 社区提交入口 — 报告生成器。

输出 lda/reports/ecosystem_d94.json：提交链路验收 + 贡献库计数 + 提案计数 +
诚实边界标注。贡献库写入临时文件，不污染仓库。
"""
import os
import json
import tempfile
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from lda_pdk.submit import (
    submit_device, submit_devices_batch, submit_benchmark_proposal,
    list_contributions, infer_sovereign_class,
)

REPORT_DIR = os.path.join(HERE, "reports")
REPORT_PATH = os.path.join(REPORT_DIR, "ecosystem_d94.json")


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="lda_eco_d94_")
    cp = os.path.join(tmp, "contributions.json")

    # --- 提交链路实测 ---
    s1 = submit_device({
        "id": "eco-soi-community-1", "name": "SOI 波导 450nm", "tech": "光子·SOI",
        "foundry": "community", "layers": ["wg-core"], "params": {"w_um": 0.45},
        "tags": ["waveguide"], "note": "社区贡献样例",
    }, contrib_path=cp)
    s2 = submit_device({"id": "eco-soi-community-1", "name": "重名", "tech": "光子·SOI",
                        "foundry": "community"}, contrib_path=cp)  # 冲突
    s3 = submit_device({"name": "缺id", "tech": "光子·SOI", "foundry": "community"},
                       contrib_path=cp)  # 拒绝
    s4 = submit_device({
        "id": "eco-b-1", "name": "基于 gdsfactory 的器件", "tech": "光子·SOI",
        "foundry": "gdsfactory fork",
    }, contrib_path=cp)  # 自动推断 B
    batch = submit_devices_batch([
        {"id": "eco-batch-1", "name": "批量A", "tech": "光子·SiN", "foundry": "community"},
        {"id": "eco-batch-2", "name": "批量B", "tech": "量子·超导", "foundry": "community"},
        {"id": "eco-soi-community-1", "name": "重名", "tech": "光子·SOI", "foundry": "community"},
    ], contrib_path=cp)
    p1 = submit_benchmark_proposal({
        "id": "B19", "title": "微环 FSR", "metric": "FSR_GHz",
        "formula": "FSR = c / (n_g * L)", "oracle_fn_name": "b19_micro_ring_fsr",
        "tol": 0.5, "default_params": {"L_um": 100.0, "n_g": 4.0},
        "proposed_by": "community",
    }, contrib_path=cp)

    comm = list_contributions(contrib_path=cp)

    infer_samples = {
        "community foundry": infer_sovereign_class({"foundry": "community"}),
        "gdsfactory": infer_sovereign_class({"foundry": "gdsfactory fork"}),
        "Lumerical": infer_sovereign_class({"foundry": "Lumerical (Ansys)"}),
        "explicit A": infer_sovereign_class({"sovereign_class": "A"}),
    }

    acceptance = [
        {"name": "submit 有效器件 → accepted + 推断 C",
         "ok": s1["status"] == "accepted" and s1.get("sovereign_class") == "C",
         "detail": str(s1)},
        {"name": "重复提交 → conflict",
         "ok": s2["status"] == "conflict", "detail": str(s2)},
        {"name": "无效提交（缺 id）→ rejected",
         "ok": s3["status"] == "rejected", "detail": str(s3)},
        {"name": "gdsfactory foundry → 自动推断 B + accepted",
         "ok": s4["status"] == "accepted" and s4.get("sovereign_class") == "B",
         "detail": str(s4)},
        {"name": "批量导入 2 接受 / 1 冲突",
         "ok": sum(1 for x in batch if x["status"] == "accepted") == 2
              and sum(1 for x in batch if x["status"] == "conflict") == 1,
         "detail": f"{[x['status'] for x in batch]}"},
        {"name": "harness 提案 → accepted_pending",
         "ok": p1["status"] == "accepted_pending" and p1.get("review_status") == "pending",
         "detail": str(p1)},
        {"name": "贡献库快照自洽（器件 4 / 提案 1）",
         "ok": comm["device_count"] == 4 and comm["proposal_count"] == 1,
         "detail": f"device_count={comm['device_count']} proposal_count={comm['proposal_count']}"},
    ]

    report = {
        "d_task": "D-94 生态共建深化 · 社区提交入口",
        "submit_chain": {
            "device_single": s1, "device_dup": s2, "device_invalid": s3,
            "batch": batch, "proposal": p1,
        },
        "infer_sovereign_class_samples": infer_samples,
        "community_store": {
            "registry_stats": comm["registry_stats"],
            "device_count": comm["device_count"],
            "proposal_count": comm["proposal_count"],
            "devices": comm["devices"],
            "proposals": comm["proposals"],
        },
        "honest_boundary": "真实晶圆厂 NDA-PDK 对接仍属发动期事项(D-62)，暂缓；本入口仅登记元数据，不硬编码商业 PDK。harness 提案仅登记 pending，需代码评审 + golden.dispatch/physical_law 注册后方可纳入回归（LLM 不进判决路径）。",
        "acceptance": {"passed": all(c["ok"] for c in acceptance), "checks": acceptance},
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"D-94 报告已生成：{REPORT_PATH}")
    print(f"acceptance.passed = {report['acceptance']['passed']}")
    for c in acceptance:
        print(f"  [{'✓' if c['ok'] else '✗'}] {c['name']}")
    print(f"社区贡献库：器件 {comm['device_count']} · 提案 {comm['proposal_count']}")
    print(f"主权分级推断样例：{infer_samples}")
    return report


if __name__ == "__main__":
    main()
