# -*- coding: utf-8 -*-
"""Tools/restore_endbooks.py 的测试.

覆盖:
- 正常导入:把 .eglib 文件写入 TinyDB
- 幂等性:已存在的库被跳过,不覆盖 ``ok`` 标记
- dry-run:不写文件,只打印
- 无 .eglib 时:不报错,返回 0/0
- 目标目录不存在:自动创建
"""

import importlib.util
import sys
from pathlib import Path

import pytest


# ----------------------------------------------------------------------------
# 动态加载 Tools/restore_endbooks.py(Tools 不是 package)
# ----------------------------------------------------------------------------
@pytest.fixture
def restore_module():
    root = Path(__file__).resolve().parent.parent
    script = root / "Tools" / "restore_endbooks.py"
    spec = importlib.util.spec_from_file_location("restore_endbooks", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_eglib(path: Path, name_fen_pairs: list):
    """写入一个简单的 .eglib 文件."""
    with path.open("w", encoding="utf-8") as f:
        for name, fen in name_fen_pairs:
            f.write(f"{name}|{fen}\n")


def _make_eglib_dir(root: Path) -> Path:
    books = root / "Books" / "已整理残局Book"
    books.mkdir(parents=True)
    return books


def test_restores_all_eglib_files(restore_module, tmp_path):
    books = _make_eglib_dir(tmp_path)
    _make_eglib(
        books / "book_a.eglib",
        [
            ("第一题", "9/9/9/9/9/9/9/9/9/9 w - - 0 1"),
            ("第二题", "9/9/9/9/9/9/9/9/9/9 b - - 0 1"),
        ],
    )
    _make_eglib(
        books / "book_b.eglib",
        [
            ("第三题", "9/9/9/9/9/9/9/9/9/9 w - - 0 1"),
        ],
    )

    game_path = tmp_path / "Game" / "endbooks.json"
    imported, skipped = restore_module.restore_endbooks(game_path, books)

    assert imported == 2
    assert skipped == 0
    assert game_path.is_file()

    # 数据可被读回
    from XQMagicUI.Storage import EndBookStore

    store = EndBookStore(game_path)
    try:
        all_books = store.getAllEndBooks()
        assert "book_a" in all_books
        assert "book_b" in all_books
        assert len(all_books["book_a"]) == 2
        assert len(all_books["book_b"]) == 1
        # 数据完整性
        names_a = {g["name"] for g in all_books["book_a"]}
        assert names_a == {"第一题", "第二题"}
        for g in all_books["book_a"]:
            assert g["book_name"] == "book_a"
    finally:
        store.close()


def test_skips_existing_books_preserves_ok_flag(restore_module, tmp_path):
    """第二次运行同目录,不应覆盖已有的 ok 标记."""
    books = _make_eglib_dir(tmp_path)
    _make_eglib(
        books / "book_a.eglib",
        [
            ("第一题", "9/9/9/9/9/9/9/9/9/9 w - - 0 1"),
        ],
    )

    game_path = tmp_path / "Game" / "endbooks.json"

    # 第一次:导入
    restore_module.restore_endbooks(game_path, books)

    # 模拟用户挑战完成
    from XQMagicUI.Storage import EndBookStore

    store = EndBookStore(game_path)
    try:
        all_books = store.getAllEndBooks()
        first_game = all_books["book_a"][0]
        first_game["ok"] = True
        store.updateEndBook(first_game)
    finally:
        store.close()

    # 第二次:应当跳过
    imported, skipped = restore_module.restore_endbooks(game_path, books)
    assert imported == 0
    assert skipped == 1

    # ok 标记应保留
    store = EndBookStore(game_path)
    try:
        all_books = store.getAllEndBooks()
        assert all_books["book_a"][0]["ok"] is True
    finally:
        store.close()


def test_dry_run_does_not_write(restore_module, tmp_path):
    books = _make_eglib_dir(tmp_path)
    _make_eglib(
        books / "book_a.eglib",
        [
            ("第一题", "9/9/9/9/9/9/9/9/9/9 w - - 0 1"),
        ],
    )

    game_path = tmp_path / "Game" / "endbooks.json"
    imported, skipped = restore_module.restore_endbooks(game_path, books, dry_run=True)

    assert imported == 1
    assert skipped == 0
    # dry-run 不创建文件
    assert not game_path.exists()


def test_no_eglib_files_returns_zero(restore_module, tmp_path, capsys):
    books = _make_eglib_dir(tmp_path)  # 空目录

    game_path = tmp_path / "Game" / "endbooks.json"
    imported, skipped = restore_module.restore_endbooks(game_path, books)

    assert imported == 0
    assert skipped == 0
    captured = capsys.readouterr()
    assert "未找到" in captured.out


def test_creates_game_dir_if_missing(restore_module, tmp_path):
    """Game/ 目录不存在时,应自动创建."""
    books = _make_eglib_dir(tmp_path)
    _make_eglib(
        books / "book_a.eglib",
        [
            ("第一题", "9/9/9/9/9/9/9/9/9/9 w - - 0 1"),
        ],
    )

    # Game/ 不存在
    game_path = tmp_path / "Game" / "endbooks.json"
    assert not game_path.parent.exists()

    restore_module.restore_endbooks(game_path, books)
    assert game_path.parent.is_dir()
    assert game_path.is_file()


def test_handles_comments_and_blank_lines(restore_module, tmp_path):
    """.eglib 文件的 # 注释和空行应被忽略(loadEglib 已支持)。"""
    books = _make_eglib_dir(tmp_path)
    books.joinpath("book_a.eglib").write_text(
        "# 这是注释\n"
        "\n"
        "第一题|9/9/9/9/9/9/9/9/9/9 w - - 0 1\n"
        "\n"
        "第二题|9/9/9/9/9/9/9/9/9/9 b - - 0 1\n",
        encoding="utf-8",
    )
    game_path = tmp_path / "Game" / "endbooks.json"
    imported, _ = restore_module.restore_endbooks(game_path, books)
    assert imported == 1

    from XQMagicUI.Storage import EndBookStore

    store = EndBookStore(game_path)
    try:
        all_books = store.getAllEndBooks()
        assert len(all_books["book_a"]) == 2
    finally:
        store.close()
