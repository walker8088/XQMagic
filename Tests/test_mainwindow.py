import pytest

@pytest.mark.qt
def test_mainwindow_init(qtbot, setup_globl, monkeypatch):
    from MagicUI.Main import MainWindow
    from MagicUI.Engine import EngineManager
    from MagicUI.Utils import GameMode
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
