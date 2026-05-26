# -*- coding: utf-8 -*-
"""B 站评论 jsonl 补爬辅助：按 video_id 删除旧行、从源文件合并、覆盖率报告。"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from collections import Counter
from datetime import datetime
from typing import Dict, Iterable, List, Set

def _current_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _default_source_jsonl() -> str:
    """Prefer detail_comments then creator_comments for today's crawl output."""
    base = os.path.join("data", "bili", "jsonl")
    date = _current_date()
    for prefix in ("detail", "creator"):
        path = os.path.join(base, f"{prefix}_comments_{date}.jsonl")
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            return path
    return os.path.join(base, f"creator_comments_{date}.jsonl")


def _parse_video_ids(raw: str) -> Set[str]:
    return {v.strip() for v in raw.split(",") if v.strip()}


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


def _backup_file(path: str, enabled: bool) -> str | None:
    if not enabled or not os.path.isfile(path):
        return None
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = f"{path}.bak-{ts}"
    shutil.copy2(path, bak)
    print(f"Backup: {bak}")
    return bak


def _write_jsonl(path: str, rows: List[Dict]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def cmd_strip(args: argparse.Namespace) -> int:
    target = args.comments_jsonl
    if not os.path.isfile(target):
        print(f"File not found: {target}", file=sys.stderr)
        return 1

    video_ids = _parse_video_ids(args.video_ids)
    if not video_ids:
        print("No video_ids provided.", file=sys.stderr)
        return 2

    _backup_file(target, args.backup)

    kept: List[Dict] = []
    removed = 0
    for obj in _iter_jsonl(target):
        vid = str(obj.get("video_id", ""))
        if vid in video_ids:
            removed += 1
            continue
        kept.append(obj)

    _write_jsonl(target, kept)
    print(f"strip: removed={removed} kept={len(kept)} path={target}")
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    target = args.comments_jsonl
    source = args.source_jsonl
    if not source:
        source = _default_source_jsonl()
    if not os.path.isfile(source):
        print(f"Source not found: {source}", file=sys.stderr)
        return 1
    if not os.path.isfile(target):
        print(f"Target not found: {target}", file=sys.stderr)
        return 1

    video_ids = _parse_video_ids(args.video_ids)
    if not video_ids:
        print("No video_ids provided.", file=sys.stderr)
        return 2

    to_append: List[Dict] = []
    for obj in _iter_jsonl(source):
        if str(obj.get("video_id", "")) in video_ids:
            to_append.append(obj)

    if not to_append:
        print(f"merge: no matching rows in source={source}", file=sys.stderr)
        return 3

    existing: List[Dict] = list(_iter_jsonl(target))
    _write_jsonl(target, existing + to_append)
    print(f"merge: appended={len(to_append)} target_total={len(existing) + len(to_append)} path={target}")

    if args.prune_source:
        _backup_file(source, args.backup)
        pruned = [o for o in _iter_jsonl(source) if str(o.get("video_id", "")) not in video_ids]
        _write_jsonl(source, pruned)
        print(f"prune_source: kept={len(pruned)} path={source}")

    return 0


def cmd_report(args: argparse.Namespace) -> int:
    contents_path = args.contents_jsonl
    comments_path = args.comments_jsonl
    if not os.path.isfile(contents_path):
        print(f"Contents not found: {contents_path}", file=sys.stderr)
        return 1
    if not os.path.isfile(comments_path):
        print(f"Comments not found: {comments_path}", file=sys.stderr)
        return 1

    video_ids = _parse_video_ids(args.video_ids) if args.video_ids else None
    expected: Dict[str, int] = {}
    for obj in _iter_jsonl(contents_path):
        vid = str(obj.get("video_id", ""))
        if not vid:
            continue
        if video_ids is not None and vid not in video_ids:
            continue
        try:
            expected[vid] = int(obj.get("video_comment") or 0)
        except (TypeError, ValueError):
            expected[vid] = 0

    counts: Counter = Counter()
    for obj in _iter_jsonl(comments_path):
        vid = str(obj.get("video_id", ""))
        if vid in expected:
            counts[vid] += 1

    print(f"{'video_id':<20} {'local':>8} {'expected':>10} {'coverage':>10} {'ok':>4}")
    all_ok = True
    threshold = float(args.threshold)
    for vid in sorted(expected.keys()):
        local = counts.get(vid, 0)
        exp = expected[vid]
        cov = (100.0 * local / exp) if exp > 0 else (100.0 if local == 0 else 0.0)
        ok = cov >= threshold if exp > 0 else True
        if not ok:
            all_ok = False
        print(f"{vid:<20} {local:>8} {exp:>10} {cov:>9.1f}% {'YES' if ok else 'NO':>4}")

    if all_ok:
        print(f"All videos meet coverage threshold (>={threshold}%).")
    else:
        print(f"Some videos below threshold (>={threshold}%).")
    return 0 if all_ok else 4


def _add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--comments-jsonl",
        default="data/bili/jsonl/creator_comments_2026-05-18.jsonl",
        help="Target comments jsonl",
    )
    p.add_argument(
        "--contents-jsonl",
        default="data/bili/jsonl/creator_contents_2026-05-18.jsonl",
        help="Contents jsonl for report (video_comment field)",
    )
    p.add_argument(
        "--video-ids",
        default="",
        help="Comma-separated video_id (aid) list",
    )
    p.add_argument(
        "--source-jsonl",
        default="",
        help="Source for merge (default: creator_comments_{today}.jsonl)",
    )
    p.add_argument(
        "--backup",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Backup file before strip/prune",
    )
    p.add_argument(
        "--prune-source",
        action="store_true",
        help="After merge, remove merged video_ids from source jsonl",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=90.0,
        help="Coverage threshold percent for report",
    )


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    _add_common_args(common)

    p = argparse.ArgumentParser(description="Refill Bilibili comment JSONL by video_id.")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("strip", parents=[common], help="Remove video_id rows from target jsonl")
    sub.add_parser("merge", parents=[common], help="Append matching rows from source to target")
    sub.add_parser("report", parents=[common], help="Print coverage vs video_comment")
    return p


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "strip":
        return cmd_strip(args)
    if args.command == "merge":
        return cmd_merge(args)
    if args.command == "report":
        return cmd_report(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
