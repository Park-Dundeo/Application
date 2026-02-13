from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import csv
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.utils.categories import load_categories


def load_rules(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def save_rules(path: Path, rules: list[dict]) -> None:
    path.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./data/reports/category_review_2025-12.csv")
    top_n = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    if not report_path.exists():
        raise SystemExit(f"report not found: {report_path}")

    allowed = load_categories()
    rules_path = Path("./data/rules.json")
    rules = load_rules(rules_path)

    # build existing set
    existing = {(r.get("category"), r.get("pattern")) for r in rules if isinstance(r, dict)}

    # gather merchants for mismatches where manual exists
    counts = defaultdict(Counter)
    with report_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            manual = (r.get("manual_detail") or "").strip()
            auto = (r.get("auto_category") or "").strip()
            merchant = (r.get("merchant") or "").strip()
            if not manual:
                continue
            if allowed and manual not in allowed:
                continue
            if manual == auto:
                continue
            if not merchant:
                continue
            counts[manual][merchant] += 1

    min_priority = min([r.get("priority", 1000) for r in rules if isinstance(r, dict)] + [100])
    priority = max(1, min_priority - 100)

    new_rules = []
    for category, ctr in counts.items():
        for merchant, _cnt in ctr.most_common(top_n):
            if (category, merchant) in existing:
                continue
            new_rules.append({
                "priority": priority,
                "match_type": "contains",
                "pattern": merchant,
                "category": category,
                "enabled": True,
                "fields": ["merchant"],
            })
            priority += 1

    if new_rules:
        rules = new_rules + rules
        save_rules(rules_path, rules)

    print(f"added_rules: {len(new_rules)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
