import pytest
import sys
from unittest.mock import MagicMock

@pytest.mark.qt
def test_mainwindow_init(qtbot, setup_globl, monkeypatch):
    # Mock onnxruntime 和 cchess_board 以避免 DLL 加载失败
    monkeypatch.setitem(sys.modules, 'onnxruntime', MagicMock())
    monkeypatch.setitem(sys.modules, 'cchess_board', MagicMock())
    monkeypatch.setitem(sys.modules, 'cchess_board.detector', MagicMock())
    
    from XQMagicUI.Main import MainWindow
    from XQMagicUI.Engine import EngineManager
    from XQMagicUI.Utils import GameMode
    monkeypatch.setattr(EngineManager, "loadEngine", lambda self, p, t: True)
    monkeypatch.setattr(EngineManager, "start", lambda self: None)
    win = MainWindow()
    qtbot.addWidget(win)
    assert win.windowTitle() != ""
    win.switchGameMode(GameMode.Free)
    win.readSettings()
    win.saveSettings()
    win.clearAll()
    win.close()
