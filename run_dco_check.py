#!/usr/bin/env python3
"""DCO (Developer Certificate of Origin) sign-off checker for LDA.

Lightweight provenance gate: every commit in the checked range must carry a
`Signed-off-by:` trailer. This preserves inbound-license clarity and, together
with the relicense clause in CONTRIBUTING.md, the maintainer's future
dual-license / commercial-authorization freedom.

Run in GitHub Actions (explicit range from the event payload), in Gitee CI
(same script, explicit --from/--to), or locally:

    python run_dco_check.py                      # origin/main..HEAD, ignore merges
    python run_dco_check.py --from A --to B      # explicit range
    python run_dco_check.py --max-count 50       # last N commits on HEAD
    python run_dco_check.py --no-ignore-merges   # also check merge commits

Exit code: 0 = all signed; 1 = at least one commit missing Signed-off-by.
"""
import argparse
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
SIGNED_OFF_RE = re.compile(r"^Signed-off-by:\s*.+\s*<.+>$", re.IGNORECASE | re.MULTILINE)


def git(*args):
    return subprocess.run(
        ["git", "-C", REPO_ROOT, *args],
        capture_output=True, text=True, check=True,
    ).stdout


def resolve_range(args):
    if args.frm and args.to:
        return f"{args.frm}..{args.to}"
    if args.max_count:
        return f"HEAD~{args.max_count}..HEAD"
    try:
        git("rev-parse", "--verify", "origin/main")
        return "origin/main..HEAD"
    except subprocess.CalledProcessError:
        return "HEAD~50..HEAD"


def main():
    ap = argparse.ArgumentParser(description="DCO Signed-off-by gate")
    ap.add_argument("--from", dest="frm", help="range start ref (exclusive)")
    ap.add_argument("--to", default="HEAD", help="range end ref (default HEAD)")
    ap.add_argument("--max-count", type=int, help="check last N commits on HEAD")
    ap.add_argument("--ignore-merges", action="store_true", default=True)
    ap.add_argument("--no-ignore-merges", dest="ignore_merges",
                    action="store_false")
    args = ap.parse_args()

    rev_range = resolve_range(args)
    # %x1f = field sep (hash|body); %x1e = record sep (between commits).
    # Using %x1e makes machine parsing robust regardless of newlines inside bodies.
    log_args = ["log", "--pretty=%H%x1f%B%x1e"]
    if args.ignore_merges:
        log_args.append("--no-merges")
    log_args.append(rev_range)

    try:
        raw = git(*log_args).strip()
    except subprocess.CalledProcessError:
        print(f"DCO: could not resolve range {rev_range}; nothing to check.")
        return 0

    commits = [c for c in raw.split("\x1e") if c.strip()] if raw else []
    if not commits:
        print(f"DCO: no commits found in range {rev_range} (nothing to check).")
        return 0

    unsigned = []
    for c in commits:
        parts = c.split("\x1f", 1)
        if len(parts) < 2:
            continue
        sha, message = parts
        if not SIGNED_OFF_RE.search(message):
            head = message.strip().split("\n", 1)[0][:60]
            unsigned.append((sha[:8], head))

    if unsigned:
        print(f"DCO CHECK FAILED: {len(unsigned)} commit(s) missing "
              f"Signed-off-by in {rev_range}")
        for sha, head in unsigned:
            print(f"  - {sha}  {head}")
        print("Fix: `git commit -s --amend` (or `git rebase -i` and reword), "
              "then force-push.")
        return 1

    print(f"DCO CHECK PASSED: all {len(commits)} commit(s) in {rev_range} "
          f"carry Signed-off-by.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
