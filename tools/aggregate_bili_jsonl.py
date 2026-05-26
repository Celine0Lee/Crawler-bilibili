# -*- coding: utf-8 -*-
"""Merge Bilibili jsonl files by type (comments / creators / contents) for given dates."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Dict, Iterable, List, Optional, Set, Tuple

ITEM_TYPES = ("comments", "creators", "contents")
PREFIXES = ("creator", "detail")
DEDUP_KEYS = {
    "comments": "comment_id",
    "creators": "user_id",
    "contents": "video_id",
}


def _parse_dates(raw: str) -> List[str]:
    dates = [d.strip() for d in raw.split(",") if d.strip()]
    for d in dates:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            raise ValueError(f"Invalid date format: {d!r} (expected YYYY-MM-DD)")
    return sorted(dates)


def _date_suffix(dates: List[str]) -> str:
    compact = [d.replace("-", "") for d in dates]
    if len(compact) == 1:
        return compact[0]
    return f"{compact[0]}-{compact[-1][-4:]}"


def _iter_jsonl(path: str) -> Iterable[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _collect_source_files(jsonl_dir: str, dates: List[str]) -> Dict[str, List[str]]:
    """Return sorted source paths per item_type."""
    found: Dict[str, List[str]] = {t: [] for t in ITEM_TYPES}
    if not os.path.isdir(jsonl_dir):
        return found

    for name in sorted(os.listdir(jsonl_dir)):
        if not name.endswith(".jsonl"):
            continue
        if ".bak-" in name:
            continue
        matched_date = None
        for d in dates:
            if d in name:
                matched_date = d
                break
        if not matched_date:
            continue
        if not name.startswith(PREFIXES):
            continue
        for item_type in ITEM_TYPES:
            token = f"_{item_type}_"
            if token in name:
                found[item_type].append(os.path.join(jsonl_dir, name))
                break

    def sort_key(p: str) -> Tuple:
        base = os.path.basename(p)
        for d in dates:
            if d in base:
                return (d, base)
        return ("", base)

    for item_type in ITEM_TYPES:
        found[item_type].sort(key=sort_key)
    return found


def _dedup_key(obj: Dict, item_type: str) -> Optional[str]:
    field = DEDUP_KEYS[item_type]
    val = obj.get(field)
    if val is None or val == "":
        return None
    return str(val)


def _merge_files(
    paths: List[str],
    item_type: str,
    dedup: bool,
) -> Tuple[List[Dict], int, int]:
    rows: List[Dict] = []
    seen: Set[str] = set()
    scanned = 0
    skipped_dup = 0
    skipped_no_key = 0

    for path in paths:
        for obj in _iter_jsonl(path):
            scanned += 1
            if dedup:
                key = _dedup_key(obj, item_type)
                if key is None:
                    skipped_no_key += 1
                    continue
                if key in seen:
                    skipped_dup += 1
                    continue
                seen.add(key)
            rows.append(obj)

    return rows, scanned, skipped_dup + skipped_no_key


def _write_jsonl(path: str, rows: List[Dict]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _verify_unique(rows: List[Dict], item_type: str) -> Tuple[bool, int]:
    field = DEDUP_KEYS[item_type]
    keys = [_dedup_key(r, item_type) for r in rows]
    keys = [k for k in keys if k is not None]
    dup_count = len(keys) - len(set(keys))
    return dup_count == 0, dup_count


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Aggregate Bilibili jsonl by item type.")
    p.add_argument(
        "--dates",
        default="2026-05-12,2026-05-13,2026-05-18,2026-05-19",
        help="Comma-separated dates (YYYY-MM-DD)",
    )
    p.add_argument(
        "--jsonl-dir",
        default="data/bili/jsonl",
        help="Source jsonl directory",
    )
    p.add_argument(
        "--output-dir",
        default="data/bili/aggregated",
        help="Output base directory",
    )
    p.add_argument(
        "--no-dedup",
        action="store_true",
        help="Append all rows without deduplication",
    )
    args = p.parse_args(argv)

    dates = _parse_dates(args.dates)
    dedup = not args.no_dedup
    suffix = _date_suffix(dates)
    sources = _collect_source_files(args.jsonl_dir, dates)

    print(f"Dates: {', '.join(dates)}")
    print(f"Dedup: {dedup}")
    print()

    for item_type in ITEM_TYPES:
        paths = sources[item_type]
        if not paths:
            print(f"[{item_type}] No source files found.")
            continue

        rows, scanned, skipped = _merge_files(paths, item_type, dedup)
        out_path = os.path.join(
            args.output_dir, item_type, f"bili_{item_type}_{suffix}.jsonl"
        )
        _write_jsonl(out_path, rows)

        unique_ok, dup_n = _verify_unique(rows, item_type)
        print(f"[{item_type}]")
        print(f"  sources ({len(paths)}):")
        for fp in paths:
            print(f"    - {fp}")
        print(f"  scanned={scanned} written={len(rows)} skipped={skipped}")
        print(f"  output={out_path}")
        if dedup:
            print(f"  unique_check={'OK' if unique_ok else f'FAIL dup={dup_n}'}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
