from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import csv
import sys


def analyze_report(path: Path):
    rows = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    valid = [r for r in rows if (r.get("manual_detail") or "").strip()]
    mismatches = [r for r in valid if r.get("match") == "N"]

    manual_counts = Counter(r["manual_detail"] for r in valid)
    manual_mismatch = Counter(r["manual_detail"] for r in mismatches)

    auto_counts = Counter(r["auto_category"] for r in valid)
    auto_mismatch = Counter(r["auto_category"] for r in mismatches)

    return {
        "total": len(rows),
        "manual_total": len(valid),
        "manual_counts": manual_counts,
        "manual_mismatch": manual_mismatch,
        "auto_counts": auto_counts,
        "auto_mismatch": auto_mismatch,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python3 scripts/report_high_error_categories.py <report.csv>")
        return 1

    report = Path(sys.argv[1])
    data = analyze_report(report)

    print(f"report: {report}")
    print(f"total rows: {data['total']}")
    print(f"manual rows: {data['manual_total']}")

    print("\nManual categories with high error rate:")
    for cat, total in data["manual_counts"].most_common():
        mism = data["manual_mismatch"].get(cat, 0)
        if total < 3:
            continue
        rate = mism / total if total else 0
        if rate >= 0.3:
            print(f"{cat}: {mism}/{total} ({rate:.2%})")

    print("\nAuto categories frequently wrong:")
    for cat, total in data["auto_counts"].most_common():
        mism = data["auto_mismatch"].get(cat, 0)
        if total < 3:
            continue
        rate = mism / total if total else 0
        if rate >= 0.3:
            print(f"{cat}: {mism}/{total} ({rate:.2%})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
