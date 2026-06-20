# -*- coding: utf-8 -*-
"""把 Books/ 下的 .eglib 转写为 .eglib.json (一次性迁移工具).

该脚本把 ``Books/已整理残局Book/*.eglib`` 转写为同名 ``*.eglib.json``,
便于后续管理(版本控制 diff、可读性、字段扩展).

向后兼容:
- 原 ``.eglib`` 不删除,保留作为只读备份
- ``PuzzleWidget`` / ``Tools/restore_puzzles.py`` 同时识别两种格式
- 重复运行默认跳过(``--force`` 强制覆盖)

用法::

    # 在 XQMagic 项目根目录下
    # 1. 预览:统计会处理哪些文件,不实际写
    python Tools/migrate_eglib_to_json.py --dry-run

    # 2. 实际迁移
    python Tools/migrate_eglib_to_json.py

    # 3. 强制覆盖已存在的 .eglib.json
    python Tools/migrate_eglib_to_json.py --force

    # 4. 指定其它目录
    python Tools/migrate_eglib_to_json.py --books Books/已整理残局Book

每个文件默认跑 round-trip 校验 (loadEglib vs loadEglibJson 数据一致),
``--no-verify`` 可跳过以加速大批量迁移.
"""

import argparse
import sys
from pathlib import Path

# 直接执行时,把项目根加进 sys.path,让 XQMagicUI 可被导入
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from XQMagicUI.Utils import loadEglib, loadEglibJson, saveEglibJson  # noqa: E402

BOOKS_DIR = Path("Books") / "已整理残局Book"


def migrate_one(eglib_path: Path, *, force: bool = False, verify: bool = True):
    """迁移单个 .eglib -> 同名 .eglib.json.

    Args:
        eglib_path: 源 .eglib 文件路径
        force: True 时覆盖已存在的 .eglib.json;否则跳过
        verify: True 时 round-trip 校验(loadEglib == loadEglibJson)

    Returns:
        ("written" | "skipped" | "verified" | "verify_failed", count)
    """
    json_path = eglib_path.with_suffix(eglib_path.suffix + ".json")
    if json_path.exists() and not force:
        return ("skipped", 0)

    games_eglib = list(loadEglib(eglib_path))
    saveEglibJson(json_path, games_eglib)

    if verify:
        games_json = loadEglibJson(json_path)
        if games_json != games_eglib:
            return ("verify_failed", len(games_eglib))

    return ("written", len(games_eglib))


def migrate_eglib_to_json(books_dir, *, dry_run=False, force=False, verify=True):
    """迁移 books_dir 下所有 .eglib -> .eglib.json.

    Args:
        books_dir: 含 .eglib 的目录
        dry_run: True 只统计,不实际写
        force: True 覆盖已存在的 .eglib.json
        verify: True 时 round-trip 校验

    Returns:
        ``(written, skipped, verify_failed, total_puzzles)``
    """
    eglib_files = sorted(books_dir.glob("*.eglib"))
    if not eglib_files:
        print(f"未找到 .eglib 文件: {books_dir}")
        return 0, 0, 0, 0

    if dry_run:
        for eglib in eglib_files:
            json_path = eglib.with_suffix(eglib.suffix + ".json")
            marker = "[已存在]" if json_path.exists() else "[将写入]"
            print(f"{marker} {eglib.name} -> {json_path.name}")
        return len(eglib_files), 0, 0, 0

    written = 0
    skipped = 0
    verify_failed = 0
    total_puzzles = 0

    for eglib in eglib_files:
        status, count = migrate_one(eglib, force=force, verify=verify)
        if status == "written":
            print(f"已写入: {eglib.name} ({count} 题)")
            written += 1
            total_puzzles += count
        elif status == "skipped":
            print(f"跳过:   {eglib.name} (.eglib.json 已存在,使用 --force 覆盖)")
            skipped += 1
        elif status == "verify_failed":
            print(f"校验失败: {eglib.name} (round-trip 不一致!)")
            verify_failed += 1

    return written, skipped, verify_failed, total_puzzles


def main():
    parser = argparse.ArgumentParser(
        description="把 Books/ 下的 .eglib 转写为 .eglib.json (保留原文件)"
    )
    parser.add_argument(
        "--books",
        type=Path,
        default=BOOKS_DIR,
        help="含 .eglib 的目录 (默认: Books/已整理残局Book)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印会处理哪些文件,不实际写入",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="覆盖已存在的 .eglib.json",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="跳过 round-trip 校验(加速大批量迁移)",
    )
    args = parser.parse_args()

    if not args.books.is_dir():
        print(f"目录不存在: {args.books}")
        return 1

    written, skipped, verify_failed, total_puzzles = migrate_eglib_to_json(
        args.books,
        dry_run=args.dry_run,
        force=args.force,
        verify=not args.no_verify,
    )

    if not args.dry_run:
        print(
            f"\n完成: 写入 {written} 个,跳过 {skipped} 个,"
            f"校验失败 {verify_failed} 个,共迁移 {total_puzzles} 题"
        )
        if verify_failed > 0:
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
