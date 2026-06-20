# -*- coding: utf-8 -*-
"""Tools/restore_puzzles.py 的测试.

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
# 动态加载 Tools/restore_puzzles.py(Tools 不是 package)
# ----------------------------------------------------------------------------
@pytest.fixture
def restore_module():
    root = Path(__file__).resolve().parent.parent
    script = root / "Tools" / "restore_puzzles.py"
    spec = importlib.util.spec_from_file_location("restore_puzzles", script)
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

    game_path = tmp_path / "Game" / "puzzles.json"
    imported, skipped = restore_module.restore_puzzles(game_path, books)

    assert imported == 2
    assert skipped == 0
    assert game_path.is_file()

    # 数据可被读回
    from XQMagicUI.Storage import PuzzleStore

    store = PuzzleStore(game_path)
    try:
        all_books = store.getAllPuzzles()
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

    game_path = tmp_path / "Game" / "puzzles.json"

    # 第一次:导入
    restore_module.restore_puzzles(game_path, books)

    # 模拟用户挑战完成
    from XQMagicUI.Storage import PuzzleStore

    store = PuzzleStore(game_path)
    try:
        all_books = store.getAllPuzzles()
        first_game = all_books["book_a"][0]
        first_game["ok"] = True
        store.updatePuzzle(first_game)
    finally:
        store.close()

    # 第二次:应当跳过
    imported, skipped = restore_module.restore_puzzles(game_path, books)
    assert imported == 0
    assert skipped == 1

    # ok 标记应保留
    store = PuzzleStore(game_path)
    try:
        all_books = store.getAllPuzzles()
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

    game_path = tmp_path / "Game" / "puzzles.json"
    imported, skipped = restore_module.restore_puzzles(game_path, books, dry_run=True)

    assert imported == 1
    assert skipped == 0
    # dry-run 不创建文件
    assert not game_path.exists()


def test_no_eglib_files_returns_zero(restore_module, tmp_path, capsys):
    books = _make_eglib_dir(tmp_path)  # 空目录

    game_path = tmp_path / "Game" / "puzzles.json"
    imported, skipped = restore_module.restore_puzzles(game_path, books)

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
    game_path = tmp_path / "Game" / "puzzles.json"
    assert not game_path.parent.exists()

    restore_module.restore_puzzles(game_path, books)
    assert game_path.parent.is_dir()
    assert game_path.is_file()


def test_handles_comments_and_blank_lines(restore_module, tmp_path):
    """.eglib 文件的 # 注释和空行应被忽略(loadEglib 已支持)."""
    books = _make_eglib_dir(tmp_path)
    books.joinpath("book_a.eglib").write_text(
        "# 这是注释\n"
        "\n"
        "第一题|9/9/9/9/9/9/9/9/9/9 w - - 0 1\n"
        "\n"
        "第二题|9/9/9/9/9/9/9/9/9/9 b - - 0 1\n",
        encoding="utf-8",
    )
    game_path = tmp_path / "Game" / "puzzles.json"
    imported, _ = restore_module.restore_puzzles(game_path, books)
    assert imported == 1

    from XQMagicUI.Storage import PuzzleStore

    store = PuzzleStore(game_path)
    try:
        all_books = store.getAllPuzzles()
        assert len(all_books["book_a"]) == 2
    finally:
        store.close()

# ----------------------------------------------------------------------------
# JSON 格式(.eglib.json)
# ----------------------------------------------------------------------------
def _make_eglib_json(path: Path, name_fen_pairs: list):
    """写入一个简单的 .eglib.json 文件."""
    import json
    payload = {
        "version": 1,
        "games": [{"name": n, "fen": f} for n, f in name_fen_pairs],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_restores_eglib_json_files(restore_module, tmp_path):
    """.eglib.json 应与 .eglib 行为一致:导入到 TinyDB."""
    books = _make_eglib_dir(tmp_path)
    _make_eglib_json(
        books / "book_a.eglib.json",
        [
            ("第一题", "9/9/9/9/9/9/9/9/9/9 w - - 0 1"),
            ("第二题", "9/9/9/9/9/9/9/9/9/9 b - - 0 1"),
        ],
    )

    game_path = tmp_path / "Game" / "puzzles.json"
    imported, skipped = restore_module.restore_puzzles(game_path, books)

    assert imported == 1
    assert skipped == 0

    from XQMagicUI.Storage import PuzzleStore

    store = PuzzleStore(game_path)
    try:
        all_books = store.getAllPuzzles()
        assert "book_a" in all_books
        assert len(all_books["book_a"]) == 2
        names = {g["name"] for g in all_books["book_a"]}
        assert names == {"第一题", "第二题"}
    finally:
        store.close()


def test_mixed_eglib_and_eglib_json(restore_module, tmp_path):
    """同一目录下 .eglib 和 .eglib.json 都能被批量导入."""
    books = _make_eglib_dir(tmp_path)
    _make_eglib(
        books / "old_book.eglib",
        [("旧题", "9/9/9/9/9/9/9/9/9/9 w - - 0 1")],
    )
    _make_eglib_json(
        books / "new_book.eglib.json",
        [("新题", "9/9/9/9/9/9/9/9/9/9 b - - 0 1")],
    )

    game_path = tmp_path / "Game" / "puzzles.json"
    imported, skipped = restore_module.restore_puzzles(game_path, books)

    assert imported == 2
    assert skipped == 0


def test_save_and_load_eglib_json_roundtrip(tmp_path):
    """Utils.saveEglibJson / loadEglibJson 往返一致性."""
    from XQMagicUI.Utils import loadEglibJson, saveEglibJson

    games = [
        {"name": "题1", "fen": "9/9/9/9/9/9/9/9/9/9 w - - 0 1"},
        {"name": "题2", "fen": "9/9/9/9/9/9/9/9/9/9 b - - 0 1", "moves": "h2e2"},
    ]
    path = tmp_path / "rt.eglib.json"
    saveEglibJson(path, games)

    loaded = loadEglibJson(path)
    assert loaded == games


def test_load_eglib_json_without_moves(tmp_path):
    """moves 字段缺省时,loadEglibJson 不应抛错."""
    import json

    from XQMagicUI.Utils import loadEglibJson

    path = tmp_path / "no_moves.eglib.json"
    path.write_text(
        json.dumps(
            {"version": 1, "games": [{"name": "x", "fen": "9/9/9/9/9/9/9/9/9/9 w - - 0 1"}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    loaded = loadEglibJson(path)
    assert len(loaded) == 1
    assert loaded[0]["name"] == "x"
    assert "moves" not in loaded[0]


def test_load_eglib_json_accepts_legacy_bare_array(tmp_path):
    """旧 JSON 可能直接是顶层数组,loader 应兼容."""
    import json

    from XQMagicUI.Utils import loadEglibJson

    path = tmp_path / "legacy.eglib.json"
    path.write_text(
        json.dumps(
            [{"name": "x", "fen": "9/9/9/9/9/9/9/9/9/9 w - - 0 1"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    loaded = loadEglibJson(path)
    assert len(loaded) == 1
    assert loaded[0]["name"] == "x"
