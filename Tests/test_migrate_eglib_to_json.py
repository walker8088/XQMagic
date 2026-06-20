# -*- coding: utf-8 -*-
"""Tools/migrate_eglib_to_json.py 的测试.

覆盖:
- 正常迁移:.eglib -> 同名 .eglib.json,数据 round-trip 一致
- 默认跳过已存在的 .eglib.json
- --force 强制覆盖
- --dry-run 不写文件,只统计
- 目录不存在 / 无 .eglib 文件
- 中文文件名 (与 Books/ 已整理残局Book 一致)
"""

import importlib.util
from pathlib import Path

import pytest


# ----------------------------------------------------------------------------
# 动态加载 Tools/migrate_eglib_to_json.py
# ----------------------------------------------------------------------------
@pytest.fixture
def migrate_module():
    root = Path(__file__).resolve().parent.parent
    script = root / "Tools" / "migrate_eglib_to_json.py"
    spec = importlib.util.spec_from_file_location("migrate_eglib_to_json", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_eglib(path: Path, name_fen_pairs: list):
    with path.open("w", encoding="utf-8") as f:
        for name, fen in name_fen_pairs:
            f.write(f"{name}|{fen}\n")


def _make_books_dir(root: Path) -> Path:
    books = root / "Books" / "已整理残局Book"
    books.mkdir(parents=True)
    return books


def test_migrates_all_eglib_files(migrate_module, tmp_path):
    """每个 .eglib 都应被写到同名 .eglib.json,数据 round-trip 一致."""
    books = _make_books_dir(tmp_path)
    _make_eglib(
        books / "book_a.eglib",
        [
            ("第一题", "9/9/9/9/9/9/9/9/9/9 w - - 0 1"),
            ("第二题", "9/9/9/9/9/9/9/9/9/9 b - - 0 1"),
        ],
    )
    _make_eglib(
        books / "book_b.eglib",
        [("第三题", "9/9/9/9/9/9/9/9/9/9 w - - 0 1")],
    )

    written, skipped, verify_failed, total = migrate_module.migrate_eglib_to_json(books)

    assert written == 2
    assert skipped == 0
    assert verify_failed == 0
    assert total == 3
    assert (books / "book_a.eglib.json").is_file()
    assert (books / "book_b.eglib.json").is_file()


def test_skips_existing_json_files(migrate_module, tmp_path):
    """已存在的 .eglib.json 应默认跳过."""
    books = _make_books_dir(tmp_path)
    _make_eglib(
        books / "book_a.eglib",
        [("第一题", "9/9/9/9/9/9/9/9/9/9 w - - 0 1")],
    )
    # 预置 .eglib.json
    (books / "book_a.eglib.json").write_text(
        '{"version": 1, "games": [{"name": "已有", "fen": "placeholder"}]}',
        encoding="utf-8",
    )

    written, skipped, _, _ = migrate_module.migrate_eglib_to_json(books)
    assert written == 0
    assert skipped == 1
    # 已有 .eglib.json 不应被覆盖
    content = (books / "book_a.eglib.json").read_text(encoding="utf-8")
    assert "placeholder" in content


def test_force_overwrites_existing_json(migrate_module, tmp_path):
    """--force 应覆盖已有的 .eglib.json."""
    books = _make_books_dir(tmp_path)
    _make_eglib(
        books / "book_a.eglib",
        [("真题", "9/9/9/9/9/9/9/9/9/9 w - - 0 1")],
    )
    (books / "book_a.eglib.json").write_text(
        '{"version": 1, "games": [{"name": "旧内容"}]}',
        encoding="utf-8",
    )

    written, skipped, _, _ = migrate_module.migrate_eglib_to_json(books, force=True)
    assert written == 1
    assert skipped == 0
    content = (books / "book_a.eglib.json").read_text(encoding="utf-8")
    assert "真题" in content
    assert "旧内容" not in content


def test_dry_run_does_not_write(migrate_module, tmp_path, capsys):
    """--dry-run 应只打印不写文件."""
    books = _make_books_dir(tmp_path)
    _make_eglib(
        books / "book_a.eglib",
        [("题", "9/9/9/9/9/9/9/9/9/9 w - - 0 1")],
    )

    written, skipped, _, total = migrate_module.migrate_eglib_to_json(
        books, dry_run=True
    )
    assert written == 1
    assert total == 0  # dry-run 不算 puzzles
    assert not (books / "book_a.eglib.json").exists()
    captured = capsys.readouterr()
    assert "将写入" in captured.out


def test_no_eglib_files_returns_zero(migrate_module, tmp_path, capsys):
    """无 .eglib 时应返回全零,提示 '未找到'."""
    books = _make_books_dir(tmp_path)  # 空目录

    written, skipped, failed, total = migrate_module.migrate_eglib_to_json(books)
    assert (written, skipped, failed, total) == (0, 0, 0, 0)
    captured = capsys.readouterr()
    assert "未找到" in captured.out


def test_handles_chinese_filenames(migrate_module, tmp_path):
    """中文文件名应能正确处理 (Books/已整理残局Book 真实场景)."""
    books = _make_books_dir(tmp_path)
    _make_eglib(
        books / "00.基本杀法.eglib",
        [
            ("兵的杀法", "9/3k5/3aP4/9/9/9/9/9/9/4K4 w - - 0 1"),
            ("车的杀法", "3a1k3/4a4/9/9/9/4R4/9/9/9/4K4 w - - 0 1"),
        ],
    )

    written, skipped, failed, total = migrate_module.migrate_eglib_to_json(books)
    assert written == 1
    assert skipped == 0
    assert failed == 0
    assert total == 2
    # 输出文件名与源同名
    out = books / "00.基本杀法.eglib.json"
    assert out.is_file()
    # 数据可读回
    from XQMagicUI.Utils import loadEglibJson

    games = loadEglibJson(out)
    assert len(games) == 2
    assert games[0]["name"] == "兵的杀法"


def test_round_trip_preserves_all_fields(migrate_module, tmp_path):
    """round-trip 应保留 name/fen/moves 全部字段,顺序也一致."""
    books = _make_books_dir(tmp_path)
    eglib = books / "book.eglib"
    # 含 name|fen|moves 三段 (虽然真实 .eglib 几乎都是 2 段)
    eglib.write_text(
        "题1|9/9/9/9/9/9/9/9/9/9 w - - 0 1|h2e2\n"
        "题2|9/9/9/9/9/9/9/9/9/9 b - - 0 1|h9g7\n",
        encoding="utf-8",
    )

    migrate_module.migrate_eglib_to_json(books)
    from XQMagicUI.Utils import loadEglibJson

    games = loadEglibJson(books / "book.eglib.json")
    assert len(games) == 2
    assert games[0] == {
        "name": "题1",
        "fen": "9/9/9/9/9/9/9/9/9/9 w - - 0 1",
        "moves": "h2e2",
    }
    assert games[1]["moves"] == "h9g7"


def test_skip_existing_prints_message(migrate_module, tmp_path, capsys):
    """跳过时应在 stdout 给出说明,方便用户决定是否 --force."""
    books = _make_books_dir(tmp_path)
    _make_eglib(
        books / "book.eglib",
        [("题", "9/9/9/9/9/9/9/9/9/9 w - - 0 1")],
    )
    (books / "book.eglib.json").write_text(
        '{"version": 1, "games": []}', encoding="utf-8"
    )

    migrate_module.migrate_eglib_to_json(books)
    captured = capsys.readouterr()
    assert "跳过" in captured.out
    assert "--force" in captured.out
