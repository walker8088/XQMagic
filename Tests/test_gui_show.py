# -*- coding: utf-8 -*-
"""GUI 测试 —— 实际显示程序界面（区别于 ``test_ui_*`` 的无 headless 测试）.

本模块的设计目标:
    * 在 ``Tests`` 目录下提供一个 **可视化** 的测试入口,
      用来人工核验程序界面在真实显示器上的显示效果.
    * 与项目根级 ``conftest.py`` 中强制设置的
      ``QT_QPA_PLATFORM=offscreen`` 不同,本模块在导入时
      **先清掉该变量**,让 Qt 走默认平台插件(Windows 上是 ``windows``),
      真正弹窗.
    * 既可以用 ``pytest -m qt Tests/test_gui_show.py`` 运行,
      也可以用 ``python Tests/test_gui_show.py`` 直接启动主界面.

覆盖范围:
    * 启动 ``MainWindow`` 并显示主界面
    * 触发走子流程让棋盘真的有"内容"
    * 弹出各种对话框 (``PositionEditDialog`` / ``EngineConfigDialog`` / ``MoveListDialog``)
    * 单独显示各个 Dock 部件与 ``BoardPanelWidget``

运行示例::

    # 全部运行
    pytest -m qt Tests/test_gui_show.py -v

    # 直接启动主界面(关闭即退出)
    python Tests/test_gui_show.py

    # 仅启动主界面,不进入 pytest 收集
    python -m Tests.test_gui_show

注意:
    * 本模块需要在带显示器的环境运行(Linux 需 ``$DISPLAY``,Windows / macOS 直接可用).
    * 在 CI 或无显示器环境中,Qt 会自动退回 ``offscreen``,
      此时 ``pytest.skip`` 会跳过需要真实显示器的用例.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ----------------------------------------------------------------------
# 重要:必须在 import XQMagicUI / PyQt5 之前清掉 offscreen 平台变量,
# 这样 Qt 才会加载 native 平台插件(Windows 上即 windows 平台,
# 真正弹出窗口).如果留在 offscreen,所有"显示"测试都会变成无头运行。
# ----------------------------------------------------------------------
os.environ.pop("QT_QPA_PLATFORM", None)
# Windows / macOS 上 platform 变量为 None 时默认走 native;Linux 上若有
# $DISPLAY,会自然选 xcb/wayland;若没有,则 Qt 会再次回退,届时由本模块的
# ``_have_display()`` 守卫跳过相关测试。

# 让 PyQt5 / XQMagicUI 可被导入
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication

# 初始局面 FEN(中国象棋标准开局)
INIT_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"


# =====================================================================
# 工具函数
# =====================================================================
def _have_display() -> bool:
    """判断当前是否有真实显示器可用.

    在 Linux 无 DISPLAY / CI offscreen 环境,Qt 会回退到 ``offscreen`` 平台.
    这种情况下"显示"测试没有意义,应直接跳过。
    """
    platform = QApplication.platformName()
    return platform not in ("offscreen", "minimal")


def _ensure_qapp() -> QApplication:
    """获取或创建 ``QApplication``(供非 pytest 入口使用)."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        app.setApplicationName("XQMagic")
    return app


# =====================================================================
# pytest fixture
# =====================================================================
@pytest.fixture(scope="session")
def qapp_show():
    """会话级 ``QApplication``,用真实平台插件.

    ``qtbot`` 也会自带 ``qapp`` fixture,但本模块期望它走非 offscreen 平台,
    所以显式构造一份并把它绑到 ``QApplication.instance()`` 上,
    供后续 fixture / ``qtbot`` 共用。
    """
    os.environ.pop("QT_QPA_PLATFORM", None)
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
    # 不主动 quit() —— pytest 收尾时统一处理


@pytest.fixture
def show_main_window(qtbot, qapp_show, tmp_path, monkeypatch):
    """创建 ``MainWindow`` 并显示.

    与 ``test_ui_mainwindow.py`` 中的 ``main_window`` 类似,
    但本 fixture **不强制 offscreen**,而且会在尾部调用 ``w.show()``。
    """
    if not _have_display():
        pytest.skip("当前无可用显示器,跳过显示类测试")

    # 与 ``setup_globl`` 一致:初始化全局状态,避免污染
    from PyQt5.QtCore import QSettings

    from XQMagicUI import Globl
    from XQMagicUI.Cache import CacheManager
    from XQMagicUI.Storage import PuzzleStore

    Globl.APP_NAME = "XQMagic"
    Globl.APP_NAME_TEXT = "象棋魔术师"
    # 使用独立临时 INI,避免与其他测试共享全局注册表
    settings_path = tmp_path / "qt_settings.ini"
    Globl.settings = QSettings(str(settings_path), QSettings.IniFormat)
    Globl.settings.clear()
    Globl.settings.setValue("cloudMode", False)
    Globl.fenCache = CacheManager(max_size=10000)
    Globl.puzzleStore = None
    Globl.puzzleStore = PuzzleStore(tmp_path / "puzzles.json")

    # 阻断真实引擎/云库请求,避免在人工运行期间触发下载或加载外部进程
    from XQMagicUI.CloudDB import CloudDB
    from XQMagicUI.Engine import EngineManager

    monkeypatch.setattr(EngineManager, "loadEngine", lambda self, p, t: True)
    monkeypatch.setattr(EngineManager, "start", lambda self: None)
    monkeypatch.setattr(EngineManager, "stopThinking", lambda self: None)
    monkeypatch.setattr(EngineManager, "quit", lambda self: None)
    monkeypatch.setattr(EngineManager, "goFrom", lambda self, *a, **kw: True)
    monkeypatch.setattr(EngineManager, "setOption", lambda self, *a, **kw: None)
    monkeypatch.setattr(EngineManager, "redoThinking", lambda self: None)
    monkeypatch.setattr(CloudDB, "startQuery", lambda self, *a, **kw: None)

    # Game 数据目录也重定向到 tmp_path,避免污染用户数据
    import XQMagicUI.Main as M

    monkeypatch.setattr(M, "GAME_DIR", tmp_path)

    # 必要的 ini 文件
    Globl.config_file = tmp_path / "XQMagic.ini"
    Globl.config_file.write_text(
        "[MainEngine]\nengine_type=ucci\nengine_exec=dummy_engine.exe\n",
        encoding="utf-8",
    )

    from XQMagicUI.Main import MainWindow

    w = MainWindow()
    w.isQueryCloud = False
    if hasattr(w, "engineView") and hasattr(w.engineView, "engineManager"):
        w.engineView.engineManager.isReady = True
    # 屏蔽动画循环,避免无头渲染卡顿
    w.boardView._make_move_steps = lambda *a, **kw: None  # type: ignore[attr-defined]
    # 主窗口置中并显示
    w.resize(1200, 800)
    w.show()
    qtbot.addWidget(w)

    yield w

    try:
        w.close()
    except Exception:
        pass


# =====================================================================
# 测试用例
# =====================================================================
@pytest.mark.qt
class TestShowMainWindow:
    """``MainWindow`` 真正显示的端到端测试.

    合并为一个测试方法,避免每个子检查都触发一次 ``MainWindow`` 构造。
    """

    def test_main_window_end_to_end(self, show_main_window, qtbot, tmp_path):
        w = show_main_window
        qtbot.wait(50)

        # 1) 可见性 + 标题
        assert w.isVisible() is True
        assert w.windowTitle() != ""

        # 2) 关键 dock 部件已挂载
        for attr in ("engineView", "actionsView", "historyView"):
            assert hasattr(w, attr), f"缺少部件: {attr}"

        # 3) 开局后历史表里至少有初始局面
        assert len(w.positionList) >= 1

        # 4) 走一步 "炮二平五"(h2e2),验证棋盘与历史都更新
        before = len(w.positionList)
        w.onMoveGo("h2e2")
        qtbot.wait(50)
        assert len(w.positionList) == before + 1
        assert w.board.to_fen() != INIT_FEN

        # 5) 截图保存到 tmp_path,方便人工对比 GUI 布局
        shot = w.grab()
        out = tmp_path / "main_window.png"
        ok = shot.save(str(out), "PNG")
        assert ok is True
        assert out.exists() and out.stat().st_size > 0


@pytest.mark.qt
class TestShowDialogs:
    """对话框的"显示"测试,主要验证能在真实窗口中弹出.

    合并为一个测试方法,共享一个 ``MainWindow`` 实例。
    """

    def test_dialogs_show(self, show_main_window, qtbot):
        w = show_main_window
        qtbot.wait(50)

        # 1) PositionEditDialog
        from XQMagicUI.Dialogs import PositionEditDialog

        dlg_pos = PositionEditDialog(w)
        dlg_pos.resize(640, 720)
        dlg_pos.show()
        qtbot.addWidget(dlg_pos)
        qtbot.wait(20)
        assert dlg_pos.isVisible() is True
        assert dlg_pos.windowTitle() == "局面编辑"

        # 2) EngineConfigDialog
        from XQMagicUI.Dialogs import EngineConfigDialog

        dlg_eng = EngineConfigDialog(w)
        dlg_eng.show()
        qtbot.addWidget(dlg_eng)
        qtbot.wait(20)
        assert dlg_eng.isVisible() is True
        assert dlg_eng.windowTitle() == "引擎设置"

        # 3) MoveListDialog——先走几步充数据,再弹出
        from XQMagicUI.Widgets import MoveListDialog

        iccs_list = []
        for iccs in ("h2e2", "b9c9", "e2e7"):
            try:
                w.onMoveGo(iccs)
                iccs_list.append(iccs)
            except Exception:
                break
        qtbot.wait(20)

        dlg_moves = MoveListDialog(w)
        dlg_moves.resize(420, 360)
        try:
            dlg_moves.shouMoves(w.board.to_fen(), 0, iccs_list)
        except Exception:
            # 即使注入数据失败,只要能显示也通过
            pass
        dlg_moves.show()
        qtbot.addWidget(dlg_moves)
        qtbot.wait(20)
        assert dlg_moves.isVisible() is True


@pytest.mark.qt
class TestShowDocks:
    """逐个显示各 Dock 部件,便于在 GUI 测试 / 截图脚本中复用.

    合并为一个测试方法,共享一个 ``MainWindow`` 实例。
    """

    def test_all_docks_show(self, show_main_window, qtbot):
        w = show_main_window
        qtbot.wait(50)

        # 每个 dock 单独 show 后,验证可见
        docks = [
            ("boardPanel", w.boardPanel),
            ("engineView", w.engineView),
            ("actionsView", w.actionsView),
            ("historyDoc", w.historyDoc),
            ("puzzleView", w.puzzleView),
            ("bookmarkView", w.bookmarkView),
            ("gamelibView", w.gamelibView),
            ("testRunnerView", w.testRunnerView),
        ]
        for name, dock in docks:
            dock.show()
            qtbot.wait(20)
            assert dock.isVisible() is True, f"{name} 未可见"


# =====================================================================
# 直接运行入口 —— 无 pytest 时也能启动 GUI
# =====================================================================
def _run_gui_demo():
    """手动启动主界面,关闭窗口即退出.

    可用于:
        * 在没有测试框架时,直接打开 GUI 进行人工目检
        * 截图脚本:在本函数前后加 ``grab().save()`` 即可
    """
    from PyQt5.QtCore import QSettings

    from XQMagicUI import Globl
    from XQMagicUI.Cache import CacheManager

    # 真实启动:不强制 offscreen,使用项目默认 Game/Engine 目录
    app = _ensure_qapp()
    if not _have_display():
        print(
            "[test_gui_show] 当前无可用显示器(Qt 平台 = "
            f"{QApplication.platformName()!r}),仍以无头模式启动."
        )

    Globl.APP_NAME = "XQMagic"
    # 手动启动:使用用户默认注册表路径(不是测试,需要保留用户设置)
    Globl.settings = QSettings("XQSoft", Globl.APP_NAME)
    Globl.fenCache = CacheManager(max_size=10000)
    Globl.config_file = Path("XQMagic.ini")

    from XQMagicUI.Main import MainWindow

    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    # 启动后让界面停留:用户关闭窗口即退出
    QTimer.singleShot(0, lambda: None)
    return app, w


if __name__ == "__main__":
    # 直接运行:启动主界面,关窗即退出
    app, win = _run_gui_demo()
    sys.exit(app.exec())
