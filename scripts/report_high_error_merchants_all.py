from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def main() -> int:
    base = Path('./data/reports')
    reports = sorted(base.glob('category_review_*.csv'))
    if not reports:
        print('no reports found')
        return 1

    for report in reports:
        print('=' * 80)
        print(f"Report: {report}")
        subprocess.run([sys.executable, 'scripts/report_high_error_merchants.py', str(report)], check=False)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
