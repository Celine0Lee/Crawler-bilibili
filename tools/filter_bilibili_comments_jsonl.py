# -*- coding: utf-8 -*-
"""从 MediaCrawler 导出的 B 站评论 jsonl 中按关键词筛选行（数据表合作/负面/语言风格等后处理）。"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from typing import Iterable, List


def iter_comment_jsonl(paths: Iterable[str]):
    for path in paths:
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield path, json.loads(line)
                except json.JSONDecodeError:
                    continue


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Filter Bilibili comments JSONL by keywords (substring match).")
    p.add_argument(
        "--input",
        default="",
        help="单个 jsonl 文件路径；留空则匹配 data/bili/jsonl/*_comments_*.jsonl",
    )
    p.add_argument(
        "--keywords",
        required=True,
        help="关键词列表，英文逗号分隔，命中任一即输出该行",
    )
    p.add_argument(
        "--output",
        default="data/bili/jsonl/filtered_comments.jsonl",
        help="输出 jsonl 路径（父目录会自动创建）",
    )
    args = p.parse_args(argv)

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    if not keywords:
        print("No keywords after parsing.", file=sys.stderr)
        return 2

    if args.input:
        if not os.path.isfile(args.input):
            print(f"Input file not found: {args.input}", file=sys.stderr)
            return 1
        paths = [args.input]
    else:
        paths = sorted(glob.glob(os.path.join("data", "bili", "jsonl", "*_comments_*.jsonl")))

    if not paths:
        print("No input jsonl files found. Run crawler first or pass --input.", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
    n_in, n_out = 0, 0
    with open(args.output, "w", encoding="utf-8") as out:
        for _path, obj in iter_comment_jsonl(paths):
            n_in += 1
            text = (obj.get("content") or "") if isinstance(obj, dict) else ""
            if not any(k in text for k in keywords):
                continue
            out.write(json.dumps(obj, ensure_ascii=False) + "\n")
            n_out += 1

    print(f"Scanned lines: {n_in}, matched: {n_out}, output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
