from __future__ import annotations

from collections import Counter
from pathlib import Path
import csv
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python3 scripts/report_high_error_merchants.py <report.csv>")
        return 1

    report = Path(sys.argv[1])
    rows = []
    with report.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    valid = [r for r in rows if (r.get("manual_detail") or "").strip()]
    mismatches = [r for r in valid if r.get("match") == "N"]

    merchant_total = Counter(r.get("merchant", "").strip() for r in valid)
    merchant_mismatch = Counter(r.get("merchant", "").strip() for r in mismatches)

    print(f"report: {report}")
    print(f"total rows: {len(rows)}")
    print(f"manual rows: {len(valid)}")

    print("\nHigh-error merchants (mismatch rate >= 30%, min 3 occurrences):")
    for merchant, total in merchant_total.most_common():
        if not merchant:
            continue
        if total < 3:
            continue
        mism = merchant_mismatch.get(merchant, 0)
        rate = mism / total if total else 0
        if rate >= 0.30:
            print(f"{merchant}: {mism}/{total} ({rate:.2%})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
