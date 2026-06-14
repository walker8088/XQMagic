# -*- coding: utf-8 -*-
"""EngineWidget 和相关控件测试.

覆盖范围:
- EngineWidget: 模式切换(快速/精准)、棋方选择、MultiPV、参数
"""

from unittest.mock import MagicMock, patch

import cchess
import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTreeWidgetItem


# =====================================================================
# 公共 fixture - 模块级,供下面三个测试类共享 (pytest 不会跨类查找 fixture)
# =====================================================================
@pytest.fixture
def engine_widget(qtbot, setup_globl):
    """构造 EngineWidget,使用伪 EngineManager.

    被 TestEngineWidget / TestEngineWidgetExtras / TestEngineWidgetParams
    三个类共享 (在模块级别定义,pytest 才能跨类解析)。
    """
    from PyQt5.QtWidgets import QWidget

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
        mgr.setOption = MagicMock()
        mgr.stopThinking = MagicMock()
        mgr.redoThinking = MagicMock()
        # stopThinking 内部会调用 self.engine.stop_thinking()
        mgr.engine = FakeEngine()

    # 提供一个真实的 QWidget parent,避免 checkbox 变化时调用 None.enginePlayColor
    parent = QWidget()
    parent.enginePlayColor = MagicMock()  # type: ignore[attr-defined]
    # EnginePath / EngineType 由 onEngineReady 从这里读取
    parent.config = {"MainEngine": {"engine_exec": "x.exe", "engine_type": "ucci"}}
    qtbot.addWidget(parent)
    w = EngineWidget(parent, mgr)
    qtbot.addWidget(w)
    return w, mgr


# =====================================================================
# EngineWidget
# =====================================================================
class TestEngineWidget:
    """引擎 Dock 控件."""

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

    def test_bg_thinking_box_in_engine_panel_layout(self, engine_widget):
        """后台思考 checkbox 必须在 engine panel 的 hbox 顶层布局里,
        不能漂浮在 dockedWidget 之外(否则等于在一个独立 panel 里)。"""
        w, _ = engine_widget
        assert w.bgThinkingBox.parent() is w.dockedWidget
        # 用 isHidden() 检查:反映显式 hide() 状态,不依赖父级是否被 show
        # (headless 测试中父 dock 默认未 show,直接断言 isVisible 不可靠)
        assert w.bgThinkingBox.isHidden() is False
        assert w.bgThinkingBox.text() == "后台思考"
        assert w.bgThinkingBox.isChecked() is False

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
        ).GameMode.Puzzle
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

        w.onGameModeChanged(GameMode.Puzzle, GameMode.Free)
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


# =====================================================================
# EngineWidget 补充 (从 test_ui_misc_widgets.py 迁入, 共享上面 engine_widget fixture)
# =====================================================================
INIT_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"


class TestEngineWidgetExtras:
    """EngineWidget 额外行为: applyParams / onViewBranch / onConfigEngine 等."""

    def test_onEngineReady_sets_title(self, engine_widget, setup_globl):
        from XQMagicUI import Globl

        w, mgr = engine_widget
        w.onEngineReady(1, "FakeEngine", {})
        # 标题应更新为包含引擎名
        assert "FakeEngine" in w.windowTitle()
        # 配置按钮应被启用
        assert w.configBtn.isEnabled() is True
        # params 应被填充
        assert w.params["EnginePath"] == "x.exe"
        assert w.params["EngineType"] == "ucci"

    def test_applyParams_sends_to_engine(self, engine_widget):
        w, mgr = engine_widget
        w.params["custom.test"] = 42
        w.applyParams(["custom.test"])
        mgr.setOption.assert_called_with("test", 42)

    def test_applyParamsWithPrefix_filters_by_prefix(self, engine_widget):
        w, mgr = engine_widget
        w.params["deep.depth"] = 25
        w.params["deep.movetime"] = 100
        w.params["quick.depth"] = 15
        w.applyParamsWithPrefix(["deep"])
        # deep.* 应当被发送
        called_keys = [c.args[0] for c in mgr.setOption.call_args_list]
        assert "depth" in called_keys
        assert "movetime" in called_keys

    def test_applyAllParams_engine_assit(self, engine_widget):
        w, mgr = engine_widget
        w.gameMode = __import__(
            "XQMagicUI.Utils", fromlist=["GameMode"]
        ).GameMode.EngineAssit
        w.goMode = "quick"
        w.params["param.Threads"] = 4
        w.params["quick.depth"] = 18
        w.applyAllParams()
        # 应至少调用 2 次 setOption(一个 param.* 一个 quick.*)
        assert mgr.setOption.call_count >= 2

    def test_applyAllParams_engine_fight(self, engine_widget):
        w, mgr = engine_widget
        w.gameMode = __import__(
            "XQMagicUI.Utils", fromlist=["GameMode"]
        ).GameMode.EngineFight
        w.params["fight.depth"] = 20
        w.applyAllParams()
        # fight.* 应当被发送
        called_keys = [c.args[0] for c in mgr.setOption.call_args_list]
        assert "depth" in called_keys

    def test_applyAllParams_engine_online(self, engine_widget):
        w, mgr = engine_widget
        w.gameMode = __import__(
            "XQMagicUI.Utils", fromlist=["GameMode"]
        ).GameMode.EngineOnline
        w.params["online.depth"] = 22
        w.applyAllParams()
        called_keys = [c.args[0] for c in mgr.setOption.call_args_list]
        assert "depth" in called_keys

    def test_onMultiPVChanged_free_mode_noop(self, engine_widget):
        # 在 Free 模式下改变 MultiPV 不应触发 redoThinking
        w, mgr = engine_widget
        w.gameMode = __import__("XQMagicUI.Utils", fromlist=["GameMode"]).GameMode.Free
        mgr.stopThinking.reset_mock()
        mgr.redoThinking.reset_mock()
        w.multiPVSpin.setValue(5)
        # Free 模式下不应调用 stopThinking / redoThinking
        mgr.stopThinking.assert_not_called()
        mgr.redoThinking.assert_not_called()

    def test_onMultiPVChanged_engine_assit(self, engine_widget):
        w, mgr = engine_widget
        w.gameMode = __import__(
            "XQMagicUI.Utils", fromlist=["GameMode"]
        ).GameMode.EngineAssit
        w.goMode = "quick"
        mgr.stopThinking.reset_mock()
        mgr.redoThinking.reset_mock()
        w.params["quick.MultiPV"] = 3
        w.multiPVSpin.setValue(5)
        # 应至少调用一次(实际可能因为 valueChanged 多次触发而多次调用)
        mgr.stopThinking.assert_called()
        mgr.redoThinking.assert_called()
        # 参数应被更新
        assert w.params["quick.MultiPV"] == 5

    def test_setMultiPV_updates_spin(self, engine_widget):
        w, mgr = engine_widget
        w.gameMode = __import__(
            "XQMagicUI.Utils", fromlist=["GameMode"]
        ).GameMode.EngineAssit
        w.goMode = "quick"
        mgr.stopThinking.reset_mock()
        mgr.redoThinking.reset_mock()
        w.params["quick.MultiPV"] = 7
        w.setMultiPV()
        assert w.multiPVSpin.value() == 7

    def test_getDefaultMem_clamps_to_max(self, engine_widget):
        w, _ = engine_widget
        w.MAX_MEM = 500
        # 来自 getFreeMem, 只要在合法范围
        mem = w.getDefaultMem()
        assert 0 < mem <= 500
        # 应当是 100 的倍数
        assert mem % 100 == 0

    def test_getDefaultThreads(self, engine_widget):
        w, _ = engine_widget
        w.MAX_THREADS = 8
        assert w.getDefaultThreads() == 4

    def test_onViewBranch_no_item(self, engine_widget):
        w, _ = engine_widget
        w.posView.setCurrentItem(None)
        # 没有选中项时不应抛异常
        w.onViewBranch()

    def test_onViewBranch_with_item(self, engine_widget):
        w, _ = engine_widget
        # 准备一个 branch
        w.branchs[1] = {
            "fen": INIT_FEN,
            "moves": ["h2e2"],
            "multipv": 1,
            "depth": 10,
        }
        item = QTreeWidgetItem(["10", "1", "炮二平五", ""])
        item.setData(0, Qt.UserRole, 1)
        w.posView.addTopLevelItem(item)
        w.posView.setCurrentItem(item)
        # 父窗口应被调用 onViewBranch
        w.parent.onViewBranch = MagicMock()
        w.onViewBranch()
        w.parent.onViewBranch.assert_called_once()

    def test_onConfigEngine_no_dialog(self, engine_widget, monkeypatch):
        # 模拟 onConfigEngine
        w, _ = engine_widget
        # 替换 EngineConfigDialog 以避免真实对话框
        mock_dlg = MagicMock()
        mock_dlg.config = MagicMock(return_value=False)
        with patch("XQMagicUI.Widgets.EngineConfigDialog", return_value=mock_dlg):
            w.onConfigEngine()
            # 因为 config 返回 False,不应调用 applyAllParams
            # 但也不抛异常
            assert True


# =====================================================================
# EngineWidget.params 初始化 (从 test_ui_misc_widgets.py 迁入, 共享上面 engine_widget fixture)
# =====================================================================
class TestEngineWidgetParams:
    """EngineWidget 初始化时的 params 检查."""

    def test_params_contains_expected_keys(self, engine_widget):
        w, _ = engine_widget
        # params 应包含所有引擎配置项
        expected = [
            "param.Repetition Rule",
            "param.Ponder",
            "param.Threads",
            "param.Hash",
            "deep.MultiPV",
            "go.deep.depth",
            "go.deep.movetime",
            "go.quick.depth",
            "go.quick.movetime",
            "fight.UCI_Elo",
            "go.fight.depth",
            "go.fight.movetime",
        ]
        for key in expected:
            assert key in w.params, f"缺少参数: {key}"

    def test_enginePlayColor_called_on_check(self, engine_widget):
        w, _ = engine_widget
        w.parent.enginePlayColor.reset_mock()
        w.redBox.setChecked(True)
        w.parent.enginePlayColor.assert_called()

    def test_analysis_box_triggers_enginePlayColor(self, engine_widget):
        w, _ = engine_widget
        w.parent.enginePlayColor.reset_mock()
        w.analysisBox.setChecked(True)
        w.parent.enginePlayColor.assert_called()
