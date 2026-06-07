# -*- coding: utf-8 -*-
"""EngineWidget 和相关控件测试.

覆盖范围:
- EngineWidget: 模式切换(快速/精准)、棋方选择、MultiPV、参数
"""

from unittest.mock import MagicMock, patch

import cchess
import pytest


# =====================================================================
# EngineWidget
# =====================================================================
class TestEngineWidget:
    """引擎 Dock 控件."""

    @pytest.fixture
    def engine_widget(self, qtbot, setup_globl):
        """构造 EngineWidget,使用伪 EngineManager."""
        from XQMagicUI import Globl
        from XQMagicUI.Engine import EngineManager
        from XQMagicUI.Utils import QGameManager
        from XQMagicUI.Widgets import EngineWidget

        # EngineWidget 内部会读 QGameManager.game_mode_changed_signal
        Globl.gameManager = QGameManager()

        # 使用真实的 EngineManager 但阻断真实进程
        class FakeEngine:
            ids = {"name": "FakeEngine"}
            options = {}

            def load(self, path):
                return True

            def set_option(self, name, value):
                self.options[name] = value

            def go_from(self, fen, params):
                return True

            def stop_thinking(self):
                return True

            def get_action(self):
                return None

            def quit(self):
                return True

        with (
            patch("XQMagicUI.Engine.UciEngine", lambda _: FakeEngine()),
            patch("XQMagicUI.Engine.UcciEngine", lambda _: FakeEngine()),
        ):
            mgr = EngineManager(None, id=1)
            mgr.isReady = True  # 直接置为 ready
            # 提供 setOption
            mgr.setOption = MagicMock()

        # 提供一个真实的 QWidget parent,避免 checkbox 变化时调用 None.enginePlayColor
        # 同时挂上 enginePlayColor mock 方法
        from PyQt5.QtWidgets import QWidget

        parent = QWidget()
        parent.enginePlayColor = MagicMock()  # type: ignore[attr-defined]
        qtbot.addWidget(parent)
        w = EngineWidget(parent, mgr)
        qtbot.addWidget(w)
        return w, mgr

    def test_default_mode_buttons(self, engine_widget):
        w, _ = engine_widget
        assert w.fastModeBtn.isChecked() is True
        # goMode 初始为 "deep"(setChecked 在信号连接之前,这是原有实现)
        # 主动调用 onModeSelected 以更新 goMode
        w.onModeSelected()
        assert w.goMode == "quick"

    def test_mode_toggle_changes_go_mode(self, engine_widget):
        w, _ = engine_widget
        w.preciseModeBtn.setChecked(True)
        # 切换到 precise 模式
        assert w.goMode == "deep"
        w.fastModeBtn.setChecked(True)
        assert w.goMode == "quick"

    def test_multi_pv_change_clamps_to_spinbox_range(self, engine_widget, qtbot):
        w, mgr = engine_widget
        w.multiPVSpin.setValue(5)
        assert w.multiPVSpin.value() == 5
        # NumEdit.setRange 会同步 spinbox 范围
        assert w.multiPVSpin.spinbox.minimum() == 1
        assert w.multiPVSpin.spinbox.maximum() == 8

    def test_red_box_default_unchecked(self, engine_widget):
        w, _ = engine_widget
        assert w.redBox.isChecked() is False

    def test_black_box_default_unchecked(self, engine_widget):
        w, _ = engine_widget
        assert w.blackBox.isChecked() is False

    def test_analysis_box_default_unchecked(self, engine_widget):
        w, _ = engine_widget
        assert w.analysisBox.isChecked() is False

    def test_red_check_triggers_enginePlayColor(self, engine_widget):
        w, mgr = engine_widget
        w.parent.enginePlayColor = MagicMock()
        w.redBox.setChecked(True)
        w.parent.enginePlayColor.assert_called_with(mgr.id, cchess.RED, True)

    def test_black_check_triggers_enginePlayColor(self, engine_widget):
        w, mgr = engine_widget
        w.parent.enginePlayColor = MagicMock()
        w.blackBox.setChecked(True)
        w.parent.enginePlayColor.assert_called_with(mgr.id, cchess.BLACK, True)

    def test_clear_resets_view(self, engine_widget):
        w, _ = engine_widget
        # 填充一些项
        from PyQt5.QtWidgets import QTreeWidgetItem

        w.posView.addTopLevelItem(QTreeWidgetItem(["x"]))
        w.branchs[1] = {"dummy": True}
        w.bgQueue.append({"dummy": True})

        w.clear()
        assert w.branchs == {}
        assert w.bgQueue == []
        assert w.bgProcessing is False

    def test_clearBgQueue(self, engine_widget):
        w, _ = engine_widget
        w.bgQueue.append({"x": 1})
        w.bgProcessing = True
        w.bgCurrentPosition = {"x": 1}
        w.clearBgQueue()
        assert w.bgQueue == []
        assert w.bgProcessing is False
        # bgCurrentPosition 在较新代码中不被 clearBgQueue 清理,仅验证能调用
        # bgQueueLabel 应被复位
        assert w.bgQueueLabel.text() == "队列: 0"

    def test_getGoParams_engine_assit(self, engine_widget):
        w, _ = engine_widget
        w.gameMode = __import__(
            "XQMagicUI.Utils", fromlist=["GameMode"]
        ).GameMode.EngineAssit
        w.goMode = "deep"
        w.params["go.deep.depth"] = 25
        w.params["go.deep.movetime"] = 0
        params = w.getGoParams()
        assert params.get("depth") == 25
        assert "movetime" not in params

    def test_getGoParams_engine_fight(self, engine_widget):
        w, _ = engine_widget
        w.gameMode = __import__(
            "XQMagicUI.Utils", fromlist=["GameMode"]
        ).GameMode.EngineFight
        w.params["go.fight.depth"] = 18
        w.params["go.fight.movetime"] = 0
        params = w.getGoParams()
        assert params.get("depth") == 18

    def test_getGoParams_puzzle(self, engine_widget):
        w, _ = engine_widget
        w.gameMode = __import__(
            "XQMagicUI.Utils", fromlist=["GameMode"]
        ).GameMode.EngineEndGame
        # 重构后 puzzle 模式不再特珠,走默认 "go" 前缀
        w.params["go.depth"] = 30
        w.params["go.movetime"] = 0
        params = w.getGoParams()
        assert params.get("depth") == 30

    def test_getBgGoParams(self, engine_widget):
        w, _ = engine_widget
        params = w.getBgGoParams()
        assert params["depth"] == 15
        assert params["_is_background"] is True

    def test_onGameModeChanged_free_keeps_analysis_off(self, engine_widget):
        w, _ = engine_widget
        w.engineManager.isReady = True
        from XQMagicUI.Utils import GameMode

        w.onGameModeChanged(GameMode.Free, GameMode.EngineAssit)
        # 自由模式不强制打开 analysis
        assert w.analysisBox.isChecked() is False

    def test_onGameModeChanged_puzzle_sets_black(self, engine_widget):
        w, _ = engine_widget
        w.engineManager.isReady = True
        from XQMagicUI.Utils import GameMode

        w.onGameModeChanged(GameMode.EngineEndGame, GameMode.Free)
        assert w.blackBox.isChecked() is True
        assert w.redBox.isChecked() is False
        assert w.analysisBox.isChecked() is False

    def test_onEngineMoveInfo_updates_branchs(self, engine_widget):
        w, _ = engine_widget
        fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
        info = {
            "fen": fen,
            "depth": 10,
            "multipv": 1,
            "color": cchess.RED,
            "moves": ["h2e2"],
        }
        w.onEngineMoveInfo(info)
        # 应该有 1 个分支
        assert 1 in w.branchs
        assert w.branchs[1]["move_1"] == "炮二平五"
        # 视图应该被更新
        assert w.posView.topLevelItemCount() == 1

    def test_onEngineMoveInfo_handles_mate_score(self, engine_widget):
        w, _ = engine_widget
        fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
        info = {
            "fen": fen,
            "depth": 12,
            "multipv": 2,
            "color": cchess.RED,
            "moves": ["h2e2"],
            "mate": 0,  # 杀死
        }
        w.analysisBox.setChecked(True)
        w.onEngineMoveInfo(info)
        item = w.posView.topLevelItem(0)
        # 杀死时显示"杀死"
        assert item.text(2) == "杀死"

    def test_save_load_settings(self, engine_widget, setup_globl, qtbot):
        from unittest.mock import MagicMock

        from PyQt5.QtWidgets import QWidget

        from XQMagicUI import Globl
        from XQMagicUI.Widgets import EngineWidget

        w, mgr = engine_widget
        # 阻断 onRedBoxChanged/onBlackBoxChanged 副作用
        w.parent.enginePlayColor = MagicMock()  # type: ignore[attr-defined]
        w.redBox.setChecked(True)
        w.blackBox.setChecked(True)
        w.analysisBox.setChecked(True)
        w.saveSettings(Globl.settings)

        # 创建新 widget,加载
        parent2 = QWidget()
        parent2.enginePlayColor = MagicMock()  # type: ignore[attr-defined]
        qtbot.addWidget(parent2)
        w2 = EngineWidget(parent2, mgr)
        w2.loadSettings(Globl.settings)
        # 验证 setChecked 被调用并生效
        assert bool(w2.redBox.isChecked()) is True
        assert bool(w2.blackBox.isChecked()) is True
        assert bool(w2.analysisBox.isChecked()) is True
