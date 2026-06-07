# -*- coding: utf-8 -*-
"""QGameManager 和工具类测试.

覆盖范围:
- QGameManager: 模式切换、复盘模式
- 工具函数: trim_fen, getStepsFromFenMoves, calc_move_diff, scaleImage
- ThreadRunner
"""

import pytest

INIT_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"


# =====================================================================
# QGameManager
# =====================================================================
class TestQGameManager:
    """游戏模式管理器."""

    @pytest.fixture
    def gm(self, qtbot):
        from XQMagicUI.Utils import QGameManager

        m = QGameManager()
        qtbot.addWidget(m) if hasattr(m, "show") else None
        return m

    def test_default_mode(self, gm):
        from XQMagicUI.Utils import GameMode

        assert gm.gameMode == GameMode.Free
        assert gm.getGameModeText() == "自由练棋"

    def test_setGameMode_emits_signal(self, gm, qtbot):
        from XQMagicUI.Utils import GameMode

        with qtbot.waitSignal(gm.game_mode_changed_signal, timeout=500) as sig:
            gm.setGameMode(GameMode.EngineAssit)
        new_mode, old_mode = sig.args
        assert new_mode == GameMode.EngineAssit
        assert old_mode == GameMode.Free

    def test_setGameMode_updates_state(self, gm):
        from XQMagicUI.Utils import GameMode

        gm.setGameMode(GameMode.EngineEndGame)
        assert gm.gameMode == GameMode.EngineEndGame
        # 代码中 GameTitle[GameMode.EngineEndGame] 为"杀法挑战"
        assert gm.getGameModeText() == "杀法挑战"

    def test_setGameMode_to_engine_fight(self, gm):
        from XQMagicUI.Utils import GameMode

        gm.setGameMode(GameMode.EngineFight)
        assert gm.gameMode == GameMode.EngineFight
        assert gm.getGameModeText() == "人机对战"

    def test_setGameMode_to_engine_online(self, gm):
        from XQMagicUI.Utils import GameMode

        gm.setGameMode(GameMode.EngineOnline)
        assert gm.gameMode == GameMode.EngineOnline

    def test_reviewModeToggle_first_call(self, gm, qtbot):
        from XQMagicUI.Utils import ReviewMode, Stage

        with qtbot.waitSignal(gm.review_mode_changed_signal, timeout=500) as sig:
            gm.reviewModeToggle(ReviewMode.ByCloud)
        # 第一次调用是 Begin
        assert sig.args[1] == Stage.Begin.value

    def test_reviewModeToggle_second_call(self, gm, qtbot):
        from XQMagicUI.Utils import ReviewMode, Stage

        # 第一次
        gm.reviewModeToggle(ReviewMode.ByCloud)
        # 第二次应该是 End
        with qtbot.waitSignal(gm.review_mode_changed_signal, timeout=500) as sig:
            gm.reviewModeToggle(ReviewMode.ByCloud)
        assert sig.args[1] == Stage.End.value

    def test_setReivewMode_updates_state(self, gm):
        from XQMagicUI.Utils import ReviewMode, Stage

        gm.setReivewMode(ReviewMode.ByEngine, Stage.Begin)
        assert gm.reviewMode == ReviewMode.ByEngine
        assert gm.reviewStage == Stage.Begin

    def test_getGameModeText_for_all_modes(self, gm):
        from XQMagicUI.Utils import GameMode

        # 验证所有模式都有对应中文标题
        for mode in GameMode:
            gm.setGameMode(mode)
            text = gm.getGameModeText()
            assert isinstance(text, str)
            assert len(text) > 0


# =====================================================================
# 工具函数
# =====================================================================
class TestUtils:
    """Utils 模块函数."""

    def test_trim_fen_keeps_only_first_two_parts(self):
        from XQMagicUI.Utils import trim_fen

        full = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
        assert (
            trim_fen(full)
            == "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w"
        )

    def test_getStepsFromFenMoves_initial_position(self):
        from XQMagicUI.Utils import getStepsFromFenMoves

        steps = getStepsFromFenMoves(INIT_FEN, ["h2e2"])
        assert len(steps) == 1
        assert steps[0][0] == INIT_FEN
        assert steps[0][1] == "h2e2"

    def test_getStepsFromFenMoves_multiple(self):
        from XQMagicUI.Utils import getStepsFromFenMoves

        steps = getStepsFromFenMoves(INIT_FEN, ["h2e2", "h9g7"])
        assert len(steps) == 2
        # 第一步起始是初始 FEN
        assert steps[0][0] == INIT_FEN
        # 第二步起始是第一步的 FEN
        assert steps[1][0] != INIT_FEN

    def test_getStepsTextFromFenMoves_legal(self):
        from XQMagicUI.Utils import getStepsTextFromFenMoves

        ok, moves = getStepsTextFromFenMoves(INIT_FEN, ["h2e2"])
        assert ok is True
        assert len(moves) == 1
        # 中文走法
        assert "炮" in moves[0] or "平" in moves[0]

    def test_calc_move_diff_red_to_move(self):
        import cchess

        from XQMagicUI.Utils import calc_move_diff

        # 红方走子时,score - best_score = diff
        diff = calc_move_diff(80, 100, cchess.RED)
        assert diff == -20

    def test_calc_move_diff_black_to_move(self):
        import cchess

        from XQMagicUI.Utils import calc_move_diff

        # 黑方走子时,分数差取反
        diff = calc_move_diff(80, 100, cchess.BLACK)
        assert diff == 20

    def test_calc_move_diff_best_move(self):
        import cchess

        from XQMagicUI.Utils import calc_move_diff

        # 最佳走法 diff=0
        assert calc_move_diff(100, 100, cchess.RED) == 0
        assert calc_move_diff(100, 100, cchess.BLACK) == 0

    def test_getTitle_returns_globl_app_name_text(self, setup_globl):
        from XQMagicUI.Utils import getTitle

        assert getTitle() == "象棋魔术师"


# =====================================================================
# ThreadRunner
# =====================================================================
class TestThreadRunner:
    """线程执行器."""

    def test_runner_executes_callable(self, qtbot):
        from XQMagicUI.Utils import ThreadRunner

        result = {"v": None}

        class MyRunner:
            def run(self):
                result["v"] = 42

        t = ThreadRunner(MyRunner())
        t.start()
        qtbot.waitUntil(lambda: result["v"] is not None, timeout=2000)
        assert result["v"] == 42
