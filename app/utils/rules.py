from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import json
import os
import re
from app.utils.categories import load_categories


@dataclass(frozen=True)
class Rule:
    priority: int
    match_type: str
    pattern: str | None
    category: str
    enabled: bool = True
    fields: list[str] | None = None
    min_amount: float | None = None
    max_amount: float | None = None


DEFAULT_FIELDS = ["merchant", "memo", "account", "raw_text", "sub_category", "main_category"]


def load_rules() -> list[Rule]:
    allowed = load_categories()
    path = Path(os.environ.get("RULES_PATH", "./data/rules.json"))
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    rules: list[Rule] = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            rules.append(
                Rule(
                    priority=int(item.get("priority", 1000)),
                    match_type=str(item.get("match_type", "contains")),
                    pattern=item.get("pattern"),
                    category=str(item.get("category", "")),
                    enabled=bool(item.get("enabled", True)),
                    fields=item.get("fields"),
                    min_amount=_to_float(item.get("min_amount")),
                    max_amount=_to_float(item.get("max_amount")),
                )
            )
    if allowed:
        rules = [r for r in rules if r.category and r.category in allowed]
    else:
        rules = [r for r in rules if r.category]
    return sorted(rules, key=lambda r: r.priority)


def apply_rules(row: dict, rules: Iterable[Rule]) -> tuple[str | None, str | None]:
    data = _extract_fields(row)
    for rule in rules:
        if not rule.enabled:
            continue
        if _match(rule, data):
            return rule.category, "rule"
    return None, None


def _extract_fields(row: dict) -> dict:
    amount = _to_float(row.get("금액"))
    merchant = (row.get("내용") or "").strip()
    memo = (row.get("메모") or "").strip()
    account = (row.get("결제수단") or "").strip()
    sub_category = (row.get("소분류") or "").strip()
    main_category = (row.get("대분류") or "").strip()
    raw_text = " ".join([merchant, memo, account, sub_category, main_category]).strip()
    return {
        "amount": amount,
        "merchant": merchant,
        "memo": memo,
        "account": account,
        "sub_category": sub_category,
        "main_category": main_category,
        "raw_text": raw_text,
    }


def _match(rule: Rule, data: dict) -> bool:
    if rule.match_type == "amount_range":
        return _match_amount(rule, data)

    fields = rule.fields or DEFAULT_FIELDS
    targets = [data.get(f, "") for f in fields]
    targets = [t for t in targets if isinstance(t, str) and t]

    if rule.match_type == "contains":
        if not rule.pattern:
            return False
        pat = rule.pattern
        for t in targets:
            if pat in t:
                return True
        return False

    if rule.match_type == "regex":
        if not rule.pattern:
            return False
        try:
            rgx = re.compile(rule.pattern)
        except re.error:
            return False
        for t in targets:
            if rgx.search(t):
                return True
        return False

    return False


def _match_amount(rule: Rule, data: dict) -> bool:
    amt = data.get("amount")
    if amt is None:
        return False
    if rule.min_amount is not None and amt < rule.min_amount:
        return False
    if rule.max_amount is not None and amt > rule.max_amount:
        return False
    return True


def _to_float(val) -> float | None:
    if val is None:
        return None
    try:
        if isinstance(val, str):
            val = val.replace(",", "").replace("₩", "").strip()
        return float(val)
    except Exception:
        return None
