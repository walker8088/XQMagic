# -*- coding: utf-8 -*-
"""棋盘相关 Widget 测试.

覆盖范围:
- ChessBoardBaseWidget: FEN 转换、坐标变换、flip / mirror
- ChessBoardWidget: 走子显示、视图控制、信号
- ChessBoardEditWidget: 局面编辑器
"""

from unittest.mock import MagicMock

import cchess
import pytest
from PyQt5.QtCore import QPoint, QRect, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication

INIT_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
EMPTY_FEN = "4k4/9/9/9/9/9/9/9/9/4K4 w - - 0 1"


# =====================================================================
# ChessBoardBaseWidget
# =====================================================================
class TestChessBoardBaseWidget:
    """棋盘基础控件."""

    @pytest.fixture
    def widget(self, qtbot):
        from cchess import ChessBoard

        from XQMagicUI.BoardWidgets import ChessBoardBaseWidget

        board = ChessBoard()
        board.from_fen(INIT_FEN)
        w = ChessBoardBaseWidget(board)
        qtbot.addWidget(w)
        # 给一个非零尺寸避免绘制时除零
        w.resize(500, 560)
        return w

    def test_default_skin_loads_pieces(self, widget):
        # 14 种棋子图片应已加载
        assert len(widget.pieces_img) == 14

    def test_from_fen_replaces_board(self, widget):
        widget.from_fen(EMPTY_FEN)
        assert EMPTY_FEN.split()[0] in widget.to_fen()

    def test_to_fen_returns_initial(self, widget):
        assert widget.to_fen().startswith("rnbakabnr")

    def test_get_move_color(self, widget):
        # 初始 FEN 是红方走子
        assert widget.get_move_color() == cchess.RED

    def test_clearPickup_resets_pickup(self, widget):
        widget.last_pickup = (4, 4)
        widget.clearPickup()
        assert widget.last_pickup is None

    def test_setFlipBoard_toggles(self, widget):
        widget.setFlipBoard(True)
        assert widget.flip_board == 1 or widget.flip_board is True
        # 二次设置相同值不重复触发 update(不会出错)
        widget.setFlipBoard(True)

    def test_setMirrorBoard_toggles(self, widget):
        widget.setMirrorBoard(True)
        assert widget.mirror_board == 1 or widget.mirror_board is True

    def test_board_to_view_roundtrip(self, widget):
        # 在棋盘中心点 (4, 4) 做一次往返变换
        vx, vy = widget.board_to_view(4, 4)
        bx, by = widget.view_to_board(vx, vy)
        assert (bx, by) == (4, 4)

    def test_flip_inverts_coordinates(self, widget):
        widget.setFlipBoard(True)
        # 翻转后 (0,0) 应映射到 (8,9) 原始位置
        x_a, y_a = widget.board_to_view(0, 0)
        x_b, y_b = widget.board_to_view(0, 0)
        # 先看未翻转时 (0,0) 和 (8,9) 的位置差异
        widget.setFlipBoard(False)
        x_0, y_0 = widget.board_to_view(0, 0)
        x_8, y_8 = widget.board_to_view(8, 9)
        widget.setFlipBoard(True)
        x_0_f, y_0_f = widget.board_to_view(0, 0)
        # 翻转后 (0,0) 的位置应等于未翻转时 (8,9) 的位置
        assert abs(x_0_f - x_8) < 5
        assert abs(y_0_f - y_8) < 5

    def test_mirror_x_axis(self, widget):
        # 先记录 (0,5) 的位置
        widget.setMirrorBoard(False)
        vx_0, vy_0 = widget.board_to_view(0, 5)
        vx_8, vy_8 = widget.board_to_view(8, 5)
        # mirror 之后 0 和 8 的位置应互换
        widget.setMirrorBoard(True)
        vx_0_m, vy_0_m = widget.board_to_view(0, 5)
        vx_8_m, vy_8_m = widget.board_to_view(8, 5)
        # 镜像后 x 坐标对换
        assert abs(vx_0_m - vx_8) < 5
        assert abs(vx_8_m - vx_0) < 5

    def test_copyFrom_copies_state(self, qtbot):
        from cchess import ChessBoard

        from XQMagicUI.BoardWidgets import ChessBoardBaseWidget

        src = ChessBoardBaseWidget(ChessBoard())
        dst = ChessBoardBaseWidget(ChessBoard())
        qtbot.addWidget(src)
        qtbot.addWidget(dst)
        src.flip_board = True
        src.mirror_board = True
        src.use_svg = True
        src.copyFrom(dst)  # 目标->源, 反向拷贝
        assert src.flip_board is False
        assert src.mirror_board is False
        assert src.use_svg is False

    def test_getImage_returns_pixmap(self, widget):
        widget.resize(500, 560)
        img = widget.getImage()
        assert isinstance(img, QPixmap)
        assert not img.isNull()

    def test_getBoardRect(self, widget):
        rect = widget.getBoardRect()
        assert isinstance(rect, QRect)
        assert rect.width() > 0 and rect.height() > 0

    def test_sizeHint(self, widget):
        size = widget.sizeHint()
        assert size.width() > 0
        assert size.height() > 0

    def test_resizeEvent_triggers_resizeBoard(self, widget):
        widget.resize(700, 800)
        # resizeBoard 后, board_width 应被更新
        assert widget.board_width > 0


# =====================================================================
# ChessBoardWidget - 用于主界面的可交互棋盘
# =====================================================================
class TestChessBoardWidget:
    """主棋盘."""

    @pytest.fixture
    def widget(self, qtbot):
        from cchess import ChessBoard

        from XQMagicUI.BoardWidgets import ChessBoardWidget

        board = ChessBoard()
        board.from_fen(INIT_FEN)
        w = ChessBoardWidget(board)
        qtbot.addWidget(w)
        w.resize(500, 560)
        return w

    def test_default_state(self, widget):
        assert widget.is_show_best_move is True
        assert widget.view_only is False
        assert widget.move_pieces == []
        assert widget.best_moves == []
        assert widget.best_next_moves == []

    def test_setViewOnly_toggles(self, widget):
        widget.setViewOnly(True)
        assert widget.view_only is True
        widget.setViewOnly(False)
        assert widget.view_only is False

    def test_setShowBestMove_toggles(self, widget):
        widget.setShowBestMove(False)
        assert widget.is_show_best_move is False
        widget.setShowBestMove(True)
        assert widget.is_show_best_move is True

    def test_showIccsMove_updates_state(self, widget, monkeypatch):
        # 屏蔽动画循环以避免在无头环境下挂起
        widget._make_move_steps = lambda *a, **kw: None
        widget.showIccsMove("h2e2")
        # 炮二平五: from=(7,2) to=(4,2)
        assert widget.move_pieces == ((7, 2), (4, 2))

    def test_showMove_with_best_moves(self, widget):
        # 屏蔽动画
        widget._make_move_steps = lambda *a, **kw: None
        widget.showMove((7, 2), (4, 2), best_moves=[((0, 0), (1, 0))])
        assert widget.move_pieces == ((7, 2), (4, 2))
        assert widget.best_moves == [((0, 0), (1, 0))]

    def test_showMoveHint_updates(self, widget):
        widget.showMoveHint([((1, 2), (1, 3))])
        assert widget.best_next_moves == [((1, 2), (1, 3))]

    def test_clearPickup_resets(self, widget):
        widget.move_pieces = ((7, 2), (4, 2))
        widget.best_moves = [((0, 0), (1, 0))]
        widget.best_next_moves = [((0, 0), (1, 0))]
        widget.last_pickup = (0, 0)
        widget.clearPickup()
        assert widget.move_pieces == []
        assert widget.best_moves == []
        assert widget.best_next_moves == []
        assert widget.last_pickup is None

    def test_right_mouse_press_emits_signal(self, widget, qtbot):
        from PyQt5.QtCore import QEvent
        from PyQt5.QtGui import QMouseEvent

        # 构造鼠标事件 - 右键按下
        ev = QMouseEvent(
            QEvent.MouseButtonPress,
            QPoint(50, 50),
            Qt.RightButton,
            Qt.RightButton,
            Qt.NoModifier,
        )
        with qtbot.waitSignal(widget.rightMouseSignal, timeout=500) as sig:
            widget.mousePressEvent(ev)
        assert sig.args[0] is True

    def test_right_mouse_release_emits_signal(self, widget, qtbot):
        from PyQt5.QtCore import QEvent
        from PyQt5.QtGui import QMouseEvent

        ev = QMouseEvent(
            QEvent.MouseButtonRelease,
            QPoint(50, 50),
            Qt.RightButton,
            Qt.RightButton,
            Qt.NoModifier,
        )
        with qtbot.waitSignal(widget.rightMouseSignal, timeout=500) as sig:
            widget.mouseReleaseEvent(ev)
        assert sig.args[0] is False

    def test_left_click_in_view_only_no_signal(self, widget, qtbot):
        from PyQt5.QtCore import QEvent
        from PyQt5.QtGui import QMouseEvent

        widget.setViewOnly(True)
        ev = QMouseEvent(
            QEvent.MouseButtonPress,
            QPoint(50, 50),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        # 应该不触发 tryMoveSignal
        signal_fired = {"v": False}

        def on_signal(*args):
            signal_fired["v"] = True

        widget.tryMoveSignal.connect(on_signal)
        widget.mousePressEvent(ev)
        assert signal_fired["v"] is False

    def test_left_click_own_piece_sets_pickup(self, widget):
        from PyQt5.QtCore import QEvent
        from PyQt5.QtGui import QMouseEvent

        # 初始局面红方先走 - 选中(4,0)红帅或(4,9)黑帅(由 view_only 决定)
        # 找一个红方棋子的位置 (e.g., (0,0) 红车)
        # 构造点击 (0,0) 中心位置
        vx, vy = widget.board_to_view(0, 0)
        ev = QMouseEvent(
            QEvent.MouseButtonPress,
            QPoint(vx + 5, vy + 5),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        widget.mousePressEvent(ev)
        # 应该已选中了(0,0)位置
        assert widget.last_pickup == (0, 0)

    def test_closeEvent_stops_timer(self, widget):
        widget.close()
        assert not widget.timer.isActive()


# =====================================================================
# ChessBoardEditWidget - 局面编辑器
# =====================================================================
class TestChessBoardEditWidget:
    """局面编辑器."""

    @pytest.fixture
    def widget(self, qtbot):
        from XQMagicUI.BoardWidgets import ChessBoardEditWidget

        w = ChessBoardEditWidget(None)
        qtbot.addWidget(w)
        w.resize(600, 580)
        return w

    def test_initial_pieces_setup(self, widget):
        # 14 个棋种,每种至少有 1 个空位计数
        assert len(widget.pieces_off) == 14
        for name, item in widget.pieces_off.items():
            assert item.count >= 0

    def test_from_fen_replaces(self, widget):
        widget.from_fen(EMPTY_FEN)
        assert widget.to_fen().startswith("4k4")

    def test_from_fen_emits_fenChanged(self, widget, qtbot):
        with qtbot.waitSignal(widget.fenChangedSignal, timeout=500) as sig:
            widget.from_fen(EMPTY_FEN)
        assert sig.args[0].startswith("4k4")

    def test_newPiece_adds_to_board(self, widget):
        widget.newPiece("R", (4, 0))  # 红车
        # 该位置应该有红车
        assert widget._board.get_fench((4, 0)) == "R"

    def test_removePiece_removes_from_board(self, widget):
        widget.newPiece("R", (4, 0))
        widget.removePiece((4, 0))
        # cchess 1.26.x 用 ``'.'`` 表示空位 (旧版 None 或空串)
        assert widget._board.get_fench((4, 0)) in (None, "", ".")

    def test_set_move_color(self, widget):
        widget.set_move_color(cchess.BLACK)
        assert widget.get_move_color() == cchess.BLACK
        # 切换回红方
        widget.set_move_color(cchess.RED)
        assert widget.get_move_color() == cchess.RED

    def test_is_king_detects_king(self, widget):
        # ChessBoardEditWidget 默认是空棋盘,需调用 from_fen 加载局面
        widget.from_fen(INIT_FEN)
        # cchess 约定:y=0 是红方,y=9 是黑方
        # 红帅在 (4, 0),黑将在 (4, 9)
        assert widget.is_king((4, 0)) is True
        assert widget.is_king((4, 9)) is True
        # 空位
        assert widget.is_king((0, 4)) is False

    def test_calc_free_pieces_for_empty_board(self, widget):
        widget.from_fen(EMPTY_FEN)
        # 仅剩 2 个王,其他都是空
        for name, item in widget.pieces_off.items():
            fench = widget.pieces_off[name].fench
            if fench.lower() == "k":
                assert item.count == 0
            elif fench.lower() == "p":
                assert item.count == 5  # 兵卒 5 个
            else:
                assert item.count == 2  # 其他 2 个

    def test_showContextMenu_sets_state(self, widget):
        # 使用一个空位的棋盘坐标生成视图点
        vx, vy = widget.board_to_view(0, 4)  # 棋盘中央空位
        from PyQt5.QtCore import QPoint

        widget.showContextMenu(QPoint(vx + 5, vy + 5))
        # _new_pos 应被设置为 (0, 4) 或 last_selected
        assert widget._new_pos == (0, 4) or widget.last_selected == (0, 4)
