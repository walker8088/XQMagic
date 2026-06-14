import pytest
from PyQt5.QtCore import QObject


class FakeEngine(QObject):
    def __init__(self):
        super().__init__()
        self.ids = {"name": "Fake"}
        self.options = []  # 真实 cchess.UciEngine().options 类型是 list,保持一致
        self._actions = [
            {"action": "ready"},
            {"action": "bestmove", "move": "a0a1", "score": 10},
        ]

    def load(self, path):
        return True

    def set_option(self, name, value):
        self.options[name] = value

    def go_from(self, fen, params):
        return True

    def stop_thinking(self):
        return True

    def get_action(self):
        return self._actions.pop(0) if self._actions else None

    def quit(self):
        return True


@pytest.mark.qt
def test_engine_manager_signals(qtbot, monkeypatch):
    import XQMagicUI.Engine as Eng

    monkeypatch.setattr(Eng, "UciEngine", lambda _: FakeEngine())
    monkeypatch.setattr(Eng, "UcciEngine", lambda _: FakeEngine())
    mgr = Eng.EngineManager(None, id=1)
    assert mgr.loadEngine("dummy", "ucci")
    ready = qtbot.waitSignal(mgr.readySignal, timeout=1000)
    mgr._runOnce()
    assert ready.args[0] == 1
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
    mgr.fen = fen
    # 模拟引擎正在分析中,避免 _runOnce 内的 stale-bestmove 防护将 bestmove 丢弃
    mgr._is_analyzing = True
    best = qtbot.waitSignal(mgr.moveBestSignal, timeout=1000)
    mgr._runOnce()
    assert "actions" in best.args[1]
