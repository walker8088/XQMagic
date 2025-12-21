import pytest

def test_trim_and_steps():
    from MagicUI.Utils import trim_fen, getStepsFromFenMoves
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
    assert trim_fen(fen).endswith("w")
    steps = getStepsFromFenMoves(fen, ["a0a1"])
    assert steps[0][1] == "a0a1"

def test_qgamemanager_signals(qtbot):
    from MagicUI.Utils import QGameManager, GameMode, ReviewMode, Stage
    gm = QGameManager()
    sig = qtbot.waitSignal(gm.game_mode_changed_signal, timeout=1000)
    gm.setGameMode(GameMode.EngineAssit)
    assert sig.args[0] == GameMode.EngineAssit
    sig2 = qtbot.waitSignal(gm.review_mode_changed_signal, timeout=1000)
    gm.reviewModeToggle(ReviewMode.ByCloud)
    assert sig2.args[0] == ReviewMode.ByCloud

