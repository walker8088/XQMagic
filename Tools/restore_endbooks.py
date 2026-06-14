# -*- coding: utf-8 -*-
"""恢复残局库.

如果 ``Game/endbooks.json`` 被误删/清空(比如旧版 conftest 误清用户目录),
用这个脚本从 ``Books/已整理残局Book/`` 下的 ``.eglib`` 文件批量导入到
TinyDB,恢复出题用的残局库。

已存在的同名残局库会被跳过(不会覆盖用户原有的挑战进度 ``ok`` 标记)。

用法::

    # 在 XQMagic 项目根目录下
    python Tools/restore_endbooks.py

    # 预览会导入哪些库(不实际写文件)
    python Tools/restore_endbooks.py --dry-run
"""

import argparse
import sys
from pathlib import Path

# 直接执行时,把项目根加进 sys.path,让 XQMagicUI 可被导入
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from XQMagicUI.Storage import EndBookStore  # noqa: E402
from XQMagicUI.Utils import loadEglib  # noqa: E402

GAME_DIR = Path("Game")
BOOKS_DIR = Path("Books") / "已整理残局Book"


def restore_endbooks(game_path, books_dir, *, dry_run=False):
    """从 books_dir 下的 .eglib 导入到 game_path.

    Args:
        game_path: 目标 TinyDB 文件路径(``Game/endbooks.json``)
        books_dir: 包含 ``.eglib`` 文件的目录
        dry_run: True 时只统计会做什么,不实际写入

    Returns:
        ``(imported, skipped)`` —— 实际/将导入的数量和跳过的数量
    """
    game_path.parent.mkdir(parents=True, exist_ok=True)

    eglib_files = sorted(books_dir.glob("*.eglib"))
    if not eglib_files:
        print(f"未找到 .eglib 文件: {books_dir}")
        return 0, 0

    if dry_run:
        # 只列举文件,不打开 TinyDB
        for eglib in eglib_files:
            print(f"将导入: {eglib.stem}")
        return len(eglib_files), 0

    store = EndBookStore(game_path)
    try:
        imported = 0
        skipped = 0
        for eglib in eglib_files:
            book_name = eglib.stem
            if store.isEndBookExist(book_name):
                print(f"跳过: {book_name} (已存在,保留挑战进度)")
                skipped += 1
                continue
            games = list(loadEglib(eglib))
            store.saveEndBook(book_name, games)
            print(f"导入: {book_name} ({len(games)} 个残局)")
            imported += 1
        return imported, skipped
    finally:
        store.close()


def main():
    parser = argparse.ArgumentParser(
        description="从 Books/ 下的 .eglib 恢复残局库到 Game/endbooks.json"
    )
    parser.add_argument(
        "--game",
        type=Path,
        default=GAME_DIR / "endbooks.json",
        help="目标 endbooks.json 路径 (默认: Game/endbooks.json)",
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
        help="只打印会做什么,不实际写入",
    )
    args = parser.parse_args()

    imported, skipped = restore_endbooks(args.game, args.books, dry_run=args.dry_run)
    if not args.dry_run:
        print(f"\n完成: 导入 {imported} 个,跳过 {skipped} 个")
    return 0


if __name__ == "__main__":
    sys.exit(main())
