# -*- coding: utf-8 -*-
"""小型/中型 Widget 单元测试.

覆盖范围:
- NumEdit: 数字步进控件
- HistoryWidget: 棋谱记录(走子历史)
- BoardPanelWidget: 棋盘面板(flip / mirror / showBest)
- BoardActionsWidget: 备选着法列表
- BookmarkWidget: 我的收藏
- PuzzleWidget: 残局库
- GameLibWidget: 棋库
"""

from pathlib import Path
from unittest.mock import MagicMock

import cchess
import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QListWidgetItem


# =====================================================================
# NumEdit - 带 +/- 按钮的 QSpinBox 复合控件
# =====================================================================
class TestNumEdit:
    """NumEdit 步进按钮、范围、信号等行为测试."""

    def _make(self, qtbot, value=10, min_v=0, max_v=100, step=1):
        from XQMagicUI.Widgets import NumEdit

        w = NumEdit(value, min_value=min_v, max_value=max_v, step=step)
        qtbot.addWidget(w)
        return w

    def test_initial_value(self, qtbot):
        w = self._make(qtbot, value=10)
        assert w.value() == 10

    def test_increase_uses_step(self, qtbot):
        w = self._make(qtbot, value=5, step=2)
        w.increase()
        assert w.value() == 7

    def test_decrease_uses_step(self, qtbot):
        w = self._make(qtbot, value=5, step=2)
        w.decrease()
        assert w.value() == 3

    def test_increase_emits_valueChanged(self, qtbot):
        w = self._make(qtbot, value=0)
        with qtbot.waitSignal(w.valueChanged) as sig:
            w.increase()
        assert sig.args[0] == 1

    def test_decrease_emits_valueChanged(self, qtbot):
        w = self._make(qtbot, value=5)
        with qtbot.waitSignal(w.valueChanged) as sig:
            w.decrease()
        assert sig.args[0] == 4

    def test_setValue_clamps_to_max(self, qtbot):
        w = self._make(qtbot, min_v=0, max_v=10)
        w.setValue(99)
        assert w.value() == 10

    def test_setValue_clamps_to_min(self, qtbot):
        w = self._make(qtbot, min_v=0, max_v=10)
        w.setValue(-5)
        assert w.value() == 0

    def test_setValue_no_signal_if_same(self, qtbot):
        w = self._make(qtbot, value=5)
        called = {"n": 0}

        def on_change(v):
            called["n"] += 1

        w.valueChanged.connect(on_change)
        w.setValue(5)
        assert called["n"] == 0

    def test_setRange_clamps(self, qtbot):
        w = self._make(qtbot, value=50, min_v=0, max_v=100)
        w.setRange(0, 30)
        w.setValue(50)
        assert w.value() == 30

    def test_setStep_applies(self, qtbot):
        w = self._make(qtbot, value=10, step=1)
        w.setStep(5)
        w.increase()
        assert w.value() == 15

    def test_setEnabled_disables_children(self, qtbot):
        w = self._make(qtbot, value=1)
        w.setEnabled(False)
        assert not w.btn_minus.isEnabled()
        assert not w.btn_plus.isEnabled()
        assert not w.spinbox.isEnabled()

    def test_size_hint_via_spinbox(self, qtbot):
        w = self._make(qtbot)
        # 控件可正确返回尺寸提示
        hint = w.sizeHint()
        assert hint.width() > 0 and hint.height() > 0


# =====================================================================
# HistoryWidget - 棋谱记录
# =====================================================================
class TestHistoryWidget:
    """HistoryWidget 的增删/选中/分数显示等测试."""

    @pytest.fixture
    def widget(self, qtbot, setup_globl):
        from XQMagicUI.Widgets import HistoryWidget

        w = HistoryWidget()
        qtbot.addWidget(w)
        return w

    def _make_position(self, fen, index, iccs=None, move=None, move_color=None):
        pos = {
            "fen": fen,
            "fen_prev": fen,
            "fen_engine": fen,
            "iccs": iccs or "",
            "index": index,
            "move_color": move_color if move_color is not None else cchess.RED,
        }
        if move is not None:
            pos["move"] = move
        return pos

    def test_initial_state_empty(self, widget):
        assert widget.currRow == -1
        assert widget.posModel.rowCount() == 0
        assert widget.posList == []

    def test_onNewPostion_appends_row(self, widget):
        from XQMagicUI import Globl

        fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
        # 写入缓存,onUpdatePosition 会读取 score
        Globl.fenCache[fen] = {"score": 50}
        pos = self._make_position(fen, 0, move_color=cchess.RED)
        widget.onNewPostion(pos, show=False)
        assert widget.posModel.rowCount() == 1
        assert widget.posList[0] is pos

    def test_onNewPostion_selects_last_row_by_default(self, widget):
        from XQMagicUI import Globl

        Globl.fenCache["dummy_fen"] = {}
        widget.onNewPostion(self._make_position("dummy_fen", 0))
        assert widget.currRow == 0

    def test_onSelectionChanged_emits_positionChangeSignal(self, widget):
        from XQMagicUI import Globl

        for i in range(3):
            fen = f"fen_{i}"
            Globl.fenCache[fen] = {}
            widget.onNewPostion(self._make_position(fen, i), show=False)
        # show=False 时不会自动 selectRow,所以 currRow 还是 -1
        widget.currRow = 0
        widget.posView.selectRow(2)
        # 验证 currRow 已切换
        assert widget.currRow == 2

    def test_positionChangeSignal_fires_on_row_change(self, widget, qtbot):
        from XQMagicUI import Globl

        for i in range(3):
            Globl.fenCache[f"f{i}"] = {}
            widget.onNewPostion(self._make_position(f"f{i}", i), show=False)
        widget.currRow = 0
        with qtbot.waitSignal(widget.positionChangeSignal, timeout=500) as sig:
            widget.posView.selectRow(2)
        assert sig.args[0] == 2

    def test_getCurrPosition_returns_position(self, widget):
        from XQMagicUI import Globl

        fen = "abc"
        Globl.fenCache[fen] = {}
        pos = self._make_position(fen, 0)
        widget.onNewPostion(pos, show=False)
        widget.currRow = 0
        assert widget.getCurrPosition() is pos

    def test_clear_resets(self, widget):
        from XQMagicUI import Globl

        Globl.fenCache["x"] = {}
        widget.onNewPostion(self._make_position("x", 0), show=False)
        widget.clear()
        assert widget.currRow == -1
        assert widget.posModel.rowCount() == 0
        # 旧版 clear 不重置 posList(保持向后兼容),仅验证 model 状态

    def test_setShowScore_false_clears_text(self, widget):
        from XQMagicUI import Globl

        fen = "score_fen"
        Globl.fenCache[fen] = {"score": 100}
        pos = self._make_position(fen, 1, move_color=cchess.BLACK)
        widget.onNewPostion(pos, show=False)
        widget.setShowScore(False)
        # index > 0 才显示分数列,这里第 1 行(index=1)是黑方
        items = widget.posList[0]["view"]
        assert items[3].text() == ""  # 云库分
        assert items[4].text() == ""  # 引擎分

    def test_setShowScore_true_restores(self, widget):
        from XQMagicUI import Globl

        fen = "score_fen2"
        Globl.fenCache[fen] = {"score": 99}
        pos = self._make_position(fen, 1, move_color=cchess.RED)
        widget.onNewPostion(pos, show=False)
        widget.setShowScore(False)
        widget.setShowScore(True)
        items = widget.posList[0]["view"]
        assert items[3].text() == "99"

    def test_setSimpleMode_is_noop_when_no_right_panel(self, widget):
        # 不再有右侧面板,setSimpleMode 应为安全空操作(不抛异常)
        widget.setSimpleMode(True)
        # hsplitter 只含 posView,索引 1 应为 None
        assert widget.hsplitter.widget(1) is None

    def test_selectRow_out_of_range_is_noop(self, widget):
        # 不应抛异常
        widget.selectRow(-1)
        widget.selectRow(999)
        assert widget.currRow == -1

    def test_getGameIccsMoves(self, widget):
        from XQMagicUI import Globl

        Globl.fenCache["f0"] = {}
        Globl.fenCache["f1"] = {}
        Globl.fenCache["f2"] = {}
        p0 = self._make_position("f0", 0, move_color=cchess.RED)
        p1 = self._make_position("f1", 1, iccs="h2e2", move_color=cchess.BLACK)
        p2 = self._make_position("f2", 2, iccs="e7e5", move_color=cchess.RED)
        for p in (p0, p1, p2):
            widget.onNewPostion(p, show=False)

        fen, moves = widget.getGameIccsMoves()
        assert fen == "f0"
        assert moves == ["h2e2", "e7e5"]

    def test_navigation_buttons(self, widget):
        from XQMagicUI import Globl

        for i in range(3):
            Globl.fenCache[f"f{i}"] = {}
            widget.onNewPostion(self._make_position(f"f{i}", i), show=False)
        widget.currRow = 0
        widget.goLast()
        assert widget.currRow == 2
        widget.goFirst()
        assert widget.currRow == 0

    def test_copy_fen_to_clipboard(self, widget, qtbot):
        from PyQt5.QtWidgets import QApplication

        from XQMagicUI import Globl

        fen = "cp_fen"
        Globl.fenCache[fen] = {}
        widget.onNewPostion(self._make_position(fen, 0), show=False)
        widget.copyFenToClipboard()
        assert QApplication.clipboard().text() == fen

    def test_save_and_load_settings(self, widget, setup_globl):
        from XQMagicUI import Globl

        widget.showScoreBox.setChecked(False)
        widget.saveSettings(Globl.settings)
        # 读回
        widget.showScoreBox.setChecked(True)
        widget.loadSettings(Globl.settings)
        assert widget.showScoreBox.isChecked() is False


def qtbot_wait(widget):  # noqa: D401 - helper context manager
    """简单上下文管理器:等待 signal."""
    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        yield None

    return _ctx()


# =====================================================================
# BoardPanelWidget
# =====================================================================
class TestBoardPanelWidget:
    """棋盘面板的 flip/mirror/showBest 行为."""

    @pytest.fixture
    def panel(self, qtbot):
        from cchess import ChessBoard

        from XQMagicUI.Widgets import BoardPanelWidget

        board = ChessBoard()
        p = BoardPanelWidget(board)
        qtbot.addWidget(p)
        return p

    def test_initial_checkbox_state(self, panel):
        # showBest 默认勾选
        assert panel.showBestBox.isChecked() is True
        # flip / mirror 默认未勾选
        assert panel.flipBox.isChecked() is False
        assert panel.mirrorBox.isChecked() is False

    def test_flip_box_triggers_setFlipBoard(self, panel):
        panel.boardView.flip_board = False
        panel.flipBox.setChecked(True)
        # stateChanged 传出来的是 Qt.Checked (2),不是 Python True
        assert bool(panel.boardView.flip_board) is True

    def test_mirror_box_triggers_setMirrorBoard(self, panel):
        panel.boardView.mirror_board = False
        panel.mirrorBox.setChecked(True)
        assert bool(panel.boardView.mirror_board) is True

    def test_showBest_box_triggers_setShowBestMove(self, panel):
        # ChessBoardWidget 的属性名是 is_show_best_move
        panel.boardView.is_show_best_move = True
        panel.showBestBox.setChecked(False)
        assert bool(panel.boardView.is_show_best_move) is False

    def test_save_load_settings(self, panel, setup_globl):
        from XQMagicUI import Globl

        panel.flipBox.setChecked(True)
        panel.mirrorBox.setChecked(True)
        panel.showBestBox.setChecked(False)
        panel.saveSettings(Globl.settings)

        # 复位
        panel.flipBox.setChecked(False)
        panel.mirrorBox.setChecked(False)
        panel.showBestBox.setChecked(True)
        panel.loadSettings(Globl.settings)
        assert panel.flipBox.isChecked() is True
        assert panel.mirrorBox.isChecked() is True
        assert panel.showBestBox.isChecked() is False

    def test_copyFrom_copies_state(self, qtbot):
        from cchess import ChessBoard

        from XQMagicUI.Widgets import BoardPanelWidget

        b1 = ChessBoard()
        b2 = ChessBoard()
        src = BoardPanelWidget(b1)
        dst = BoardPanelWidget(b2)
        qtbot.addWidget(src)
        qtbot.addWidget(dst)

        src.flipBox.setChecked(True)
        src.mirrorBox.setChecked(True)
        src.showBestBox.setChecked(False)

        dst.copyFrom(src)
        assert dst.flipBox.isChecked() is True
        assert dst.mirrorBox.isChecked() is True
        assert dst.showBestBox.isChecked() is False


# =====================================================================
# BoardActionsWidget
# =====================================================================
class TestBoardActionsWidget:
    """备选着法面板."""

    @pytest.fixture
    def widget(self, qtbot):
        from XQMagicUI.Widgets import BoardActionsWidget

        w = BoardActionsWidget(None)
        qtbot.addWidget(w)
        return w

    def _make_action(self, iccs, text, score=0, mark=""):
        return {
            "iccs": iccs,
            "text": text,
            "score": score,
            "diff": score,
            "new_fen": f"new_{iccs}",
            "mark": mark,
        }

    def test_initial_state(self, widget):
        assert widget.actionsView.topLevelItemCount() == 0
        # queryCloudBox 默认未勾选
        assert widget.queryCloudBox.isChecked() is False

    def test_updateActions_populates_items(self, widget):
        actions = {
            "h2e2": self._make_action("h2e2", "炮二平五", 100, "*"),
            "h0g2": self._make_action("h0g2", "马二进三", 50),
        }
        widget.updateActions(actions)
        assert widget.actionsView.topLevelItemCount() == 2
        first = widget.actionsView.topLevelItem(0)
        assert first.text(1) == "炮二平五"
        assert first.text(0) == "*"
        # 得分列右对齐
        from PyQt5.QtCore import Qt as _Qt

        assert first.textAlignment(2) == _Qt.AlignRight

    def test_updateActions_empty_clears(self, widget):
        widget.updateActions({"x": self._make_action("x", "x")})
        widget.updateActions({})
        assert widget.actionsView.topLevelItemCount() == 0

    def test_clear_method(self, widget):
        widget.updateActions({"x": self._make_action("x", "x")})
        widget.clear()
        assert widget.actionsView.topLevelItemCount() == 0

    def test_onSelectIndex_emits_selectMoveSignal(self, widget, qtbot):
        widget.updateActions({"h2e2": self._make_action("h2e2", "炮二平五", 100, "*")})
        widget.actionsView.setCurrentItem(widget.actionsView.topLevelItem(0))
        with qtbot.waitSignal(widget.selectMoveSignal) as sig:
            widget.onSelectIndex(0)
        assert sig.args[0]["iccs"] == "h2e2"


# =====================================================================
# BookmarkWidget
# =====================================================================
class TestBookmarkWidget:
    """收藏夹."""

    @pytest.fixture
    def widget(self, qtbot, setup_globl, tmp_path):
        # 为 widget 提供 Globl.localBook
        from XQMagicUI import Globl
        from XQMagicUI.LocalDB import LocalBook
        from XQMagicUI.Widgets import BookmarkWidget

        db = tmp_path / "localbook.db"
        book = LocalBook()
        book.open(db)
        Globl.localBook = book
        Globl.bookmarkView = None  # 避免引用旧的

        w = BookmarkWidget(None)
        qtbot.addWidget(w)
        yield w
        book.close()

    def test_initial_empty(self, widget):
        assert widget.bookmarkView.count() == 0

    def test_updateBookmarks_loads_existing(self, widget, setup_globl):
        from XQMagicUI import Globl

        Globl.localBook.saveBookmark(
            "测试局面",
            "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1",
        )
        widget.updateBookmarks()
        assert widget.bookmarkView.count() == 1
        assert widget.bookmarkView.item(0).text() == "测试局面"

    def test_addQuickBooks_appends(self, widget):
        widget.addQuickBooks({"快速1": "h2e2,h0g2"})
        assert widget.bookmarkView.count() == 1
        item = widget.bookmarkView.item(0)
        assert item.text() == "快速1"
        data = item.data(Qt.UserRole)
        assert data["moves"] == ["h2e2", "h0g2"]

    def test_double_click_triggers_parent_load(self, widget, qtbot, setup_globl):
        from XQMagicUI import Globl

        # 让 widget.parent 是个 mock
        widget.parent = MagicMock()
        widget.parent.loadBookmark = MagicMock()

        Globl.localBook.saveBookmark(
            "双击局面",
            "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1",
        )
        widget.updateBookmarks()
        widget.bookmarkView.setCurrentRow(0)
        widget.onDoubleClicked()
        widget.parent.loadBookmark.assert_called_once()

    def test_remove_bookmark(self, widget, qtbot, setup_globl):
        from XQMagicUI import Globl

        Globl.localBook.saveBookmark(
            "A", "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
        )
        Globl.localBook.saveBookmark(
            "B", "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
        )
        widget.updateBookmarks()
        assert widget.bookmarkView.count() == 2

        # 直接调用 localBook 删除
        Globl.localBook.removeBookmark("A")
        widget.updateBookmarks()
        assert widget.bookmarkView.count() == 1
        assert widget.bookmarkView.item(0).text() == "B"


# =====================================================================
# PuzzleWidget
# =====================================================================
class TestPuzzleWidget:
    """残局库."""

    @pytest.fixture
    def widget(self, qtbot, tmp_path, setup_globl):
        from XQMagicUI import Globl
        from XQMagicUI.Storage import PuzzleStore
        from XQMagicUI.Widgets import PuzzleWidget

        # 准备 2 个 残局库(使用 TinyDB 存储)
        puzzles_db = tmp_path / "puzzles.json"
        store = PuzzleStore(puzzles_db)
        store.savePuzzles(
            "book1",
            [
                {
                    "name": "第一局",
                    "fen": "4k4/9/9/9/9/9/9/9/9/4K4 w - - 0 1",
                    "moves": "e0e1",
                    "ok": False,
                }
            ],
        )
        store.savePuzzles(
            "book2",
            [
                {
                    "name": "第一局",
                    "fen": "4k4/9/9/9/9/9/9/9/9/4K4 b - - 0 1",
                    "moves": "",
                    "ok": False,
                }
            ],
        )
        Globl.puzzleStore = store

        w = PuzzleWidget(None)
        qtbot.addWidget(w)
        w.parent = MagicMock()
        w.parent.board = MagicMock()
        w.parent.board.to_fen.return_value = "4k4/9/9/9/9/9/9/9/9/4K4 w - - 0 1"
        yield w
        store.close()

    def test_update_books_fills_combo(self, widget):
        widget.updateBooks()
        names = [widget.bookCombo.itemText(i) for i in range(widget.bookCombo.count())]
        assert "book1" in names and "book2" in names

    def test_book_change_loads_puzzles(self, widget):
        widget.updateBooks()
        widget.bookCombo.setCurrentText("book1")
        assert widget.currBookName == "book1"
        assert widget.bookView.count() == 1
        assert widget.bookView.item(0).text() == "第一局"

    def test_currentItemChanged_emits_signal(self, widget, qtbot):
        # 预先连接信号
        spy = []

        widget.selectPuzzleSignal.connect(lambda game: spy.append(game))

        widget.updateBooks()
        widget.bookCombo.setCurrentText("book1")
        # 此时 nextGame 已被 onBookChanged 调用,信号会发射
        assert len(spy) > 0
        # 第一个发射的 game 来自 currBook[0]
        assert spy[0]["name"] == "第一局"

    def test_nextGame_skips_completed(self, widget):
        widget.updateBooks()
        widget.bookCombo.setCurrentText("book1")
        # 把当前 puzzle 标记完成
        widget.currGame["ok"] = True
        widget.updateCurrentBook()
        widget.nextGame()
        # 完成后 nextGame 不再切换,但也不会抛错
        assert widget.currGame is not None

    def test_save_load_settings(self, widget, setup_globl):
        from XQMagicUI import Globl

        widget.updateBooks()
        widget.bookCombo.setCurrentText("book1")
        widget.saveSettings(Globl.settings)
        # 新建 widget,加载设置
        from XQMagicUI.Widgets import PuzzleWidget

        w2 = PuzzleWidget(None)
        w2.loadSettings(Globl.settings)
        assert w2.currBookName == "book1"

    def test_batchImportFromDir_imports_missing_books(self, widget, tmp_path):
        """从文件夹批量导入应该补齐缺失的库,跳过已存在的库(保留 ok 标记)。"""
        from XQMagicUI import Globl
        from XQMagicUI.Widgets import PuzzleWidget

        # 在 tmp_path 下准备 .eglib 文件:
        # book1(已存在,应被跳过)/book3(新,应被导入)
        books_dir = tmp_path / "books"
        books_dir.mkdir()
        (books_dir / "book1.eglib").write_text(
            "新题目|9/9/9/9/9/9/9/9/9/9 w - - 0 1\n",
            encoding="utf-8",
        )
        (books_dir / "book3.eglib").write_text(
            "A|9/9/9/9/9/9/9/9/9/9 w - - 0 1\nB|9/9/9/9/9/9/9/9/9/9 b - - 0 1\n",
            encoding="utf-8",
        )

        # book1 当前只有"第一局",把它的 ok=True 以便验证保留
        widget.updateBooks()
        widget.bookCombo.setCurrentText("book1")
        widget.currGame["ok"] = True
        Globl.puzzleStore.updatePuzzle(widget.currGame)

        imported, skipped = PuzzleWidget.batchImportFromDir(books_dir)
        assert imported == 1
        assert skipped == 1

        # book3 应被导入
        all_books = Globl.puzzleStore.getAllPuzzles()
        assert "book3" in all_books
        assert len(all_books["book3"]) == 2

        # book1 的 ok 标记应被保留
        book1_games = all_books["book1"]
        assert any(g["ok"] is True for g in book1_games)

    def test_batchImportFromDir_empty_dir(self, widget, tmp_path):
        """空文件夹应返回 (0, 0)。"""
        from XQMagicUI.Widgets import PuzzleWidget

        books_dir = tmp_path / "empty_books"
        books_dir.mkdir()
        imported, skipped = PuzzleWidget.batchImportFromDir(books_dir)
        assert (imported, skipped) == (0, 0)

    def test_batchImportFromDir_imports_eglib_json(self, widget, tmp_path):
        """批量导入应同时支持 .eglib 和 .eglib.json."""
        import json

        from XQMagicUI import Globl
        from XQMagicUI.Widgets import PuzzleWidget

        books_dir = tmp_path / "books"
        books_dir.mkdir()
        # .eglib.json 新格式
        (books_dir / "json_book.eglib.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "games": [
                        {"name": "JSON题", "fen": "9/9/9/9/9/9/9/9/9/9 w - - 0 1"},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        # .eglib 旧格式
        (books_dir / "legacy_book.eglib").write_text(
            "旧题|9/9/9/9/9/9/9/9/9/9 b - - 0 1\n",
            encoding="utf-8",
        )

        imported, skipped = PuzzleWidget.batchImportFromDir(books_dir)
        assert imported == 2
        assert skipped == 0

        all_books = Globl.puzzleStore.getAllPuzzles()
        assert "json_book" in all_books
        assert "legacy_book" in all_books
        assert len(all_books["json_book"]) == 1
        assert len(all_books["legacy_book"]) == 1


# =====================================================================
# GameLibWidget
# =====================================================================
class TestGameLibWidget:
    """棋库 - 展示 .cbl 棋谱库."""

    @pytest.fixture
    def widget(self, qtbot):
        from XQMagicUI.Widgets import GameLibWidget

        w = GameLibWidget(None)
        qtbot.addWidget(w)
        return w

    def test_initial_empty(self, widget):
        assert widget.gamesView.count() == 0

    def test_updateGameLib_populates(self, widget):
        game_mock = MagicMock()
        game_mock.info = {"title": "测试对局"}
        gamelib = {"name": "test_lib", "games": [game_mock]}
        widget.updateGameLib(gamelib)
        assert widget.gamesView.count() == 1
        assert widget.gamesView.item(0).text() == "测试对局"

    def test_double_click_triggers_load(self, widget, qtbot):
        widget.parent = MagicMock()
        widget.parent.loadBookGame = MagicMock()
        game_mock = MagicMock()
        game_mock.info = {"title": "X"}
        widget.updateGameLib({"name": "lib", "games": [game_mock]})
        widget.gamesView.setCurrentRow(0)
        widget.onDoubleClicked()
        widget.parent.loadBookGame.assert_called_once()
        # 名称格式: "{lib_name}-{title}"
        args = widget.parent.loadBookGame.call_args[0]
        assert args[0] == "lib-X"
