#!/usr/bin/env python3
"""
记忆召回过滤器 — 去重 + 压缩 + 限额
用法: echo "条目1\n---\n条目2" | python3 recall-filter.py --max 8
"""
import sys
import argparse
from difflib import SequenceMatcher
from typing import List


def deduplicate(entries: List[str]) -> List[str]:
    """SequenceMatcher 前 100 字符，ratio>0.8 视为重复，保留更长条目"""
    kept: List[str] = []
    for entry in entries:
        prefix = entry[:100]
        duplicate_idx = None
        for i, existing in enumerate(kept):
            if SequenceMatcher(None, prefix, existing[:100]).ratio() > 0.8:
                duplicate_idx = i
                break
        if duplicate_idx is not None:
            if len(entry) > len(kept[duplicate_idx]):
                kept[duplicate_idx] = entry
        else:
            kept.append(entry)
    return kept


def compress(entry: str) -> str:
    """>150 字符截取前两句；无句号时截取前 120 字符"""
    if len(entry) <= 150:
        return entry
    parts = entry.split("。")
    if len(parts) >= 3:
        return parts[0] + "。" + parts[1] + "。"
    return entry[:120] + "..."


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=8)
    args = parser.parse_args()

    raw = sys.stdin.read().strip()
    if not raw:
        return

    entries = [e.strip() for e in raw.split("---") if e.strip()]
    entries = deduplicate(entries)
    entries = [compress(e) for e in entries]
    entries = entries[: args.max]

    print("\n---\n".join(entries))


if __name__ == "__main__":
    main()
