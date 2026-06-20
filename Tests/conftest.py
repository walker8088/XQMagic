# -*- coding: utf-8 -*-
"""测试共享的 fixture.

提供:
- ``setup_globl``: 为测试准备 ``XQMagicUI.Globl`` 的全局状态。
- ``patched_engine``: 阻断真实引擎启动。
- ``patched_cloud``: 屏蔽云库 HTTP 请求。
- ``patched_modules``: 屏蔽缺失的原生模块。
"""

import os
import sys
from pathlib import Path

import pytest
from PyQt5.QtCore import QSettings

# 让 conftest.py 可单独被 pytest 加载
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 在无显示器的 CI 上避免 Qt 启动失败
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def pytest_sessionstart(session):
    """测试会话开始前,准备运行所需的目录。"""
    cwd = Path(os.getcwd())
    for sub in ("Skins", "Game", "Engine", "Sound", "Books", "ImgRes"):
        (cwd / sub).mkdir(exist_ok=True)


def pytest_collection_modifyitems(config, items):
    """给所有 UI/Widget 相关测试自动加 ``qt`` 标记,避免 PytestUnknownMarkWarning。"""
    for item in items:
        if "qtbot" in item.fixturenames or "TestUI" in item.nodeid:
            item.add_marker(pytest.mark.qt)


@pytest.fixture
def setup_globl(tmp_path):
    """初始化 XQMagicUI.Globl 全局变量,避免测试之间相互污染。"""
    from XQMagicUI import Globl
    from XQMagicUI.Cache import CacheManager

    # 重置关键全局对象,避免被前一个测试覆盖
    Globl.APP_NAME = "XQMagic"
    Globl.APP_NAME_TEXT = "象棋魔术师"
    # 使用独立的临时 INI 文件作为 QSettings 后端,而非全局注册表,
    # 避免 pytest-xdist / CI 并行测试时多进程互相覆盖同一个注册表键。
    # 同时也防止覆盖用户真实的 XQMagic 设置。
    settings_path = tmp_path / "qt_settings.ini"
    Globl.settings = QSettings(str(settings_path), QSettings.IniFormat)
    Globl.settings.clear()
    # 关闭云库默认,避免单元测试中走外网
    Globl.settings.setValue("cloudMode", False)
    Globl.fenCache = CacheManager(max_size=10000)
    Globl.puzzleStore = None
    Globl.endbookStore = None
    Globl.gameManager = None
    Globl.bookmarkView = None
    Globl.boardPanel = None

    # 使用 tmp_path 写入测试专用配置文件,避免污染用户真实的 XQMagic.ini
    # (之前的实现直接覆盖项目根目录的 ini,会破坏用户的引擎配置)
    Globl.config_file = tmp_path / "XQMagic.ini"
    Globl.config_file.write_text(
        "[MainEngine]\nengine_type=ucci\nengine_exec=dummy_engine.exe\n",
        encoding="utf-8",
    )

    yield Globl

    # 不再清理 Game/ Skins/ 等真实用户目录——之前的实现会误删用户的皮肤/对局数据。
    # pytest 的 tmp_path 负责清理本次测试产生的临时文件。


@pytest.fixture
def patched_modules(monkeypatch):
    """屏蔽缺失的原生模块(DLL 加载会失败)."""
    from unittest.mock import MagicMock

    monkeypatch.setitem(sys.modules, "onnxruntime", MagicMock())
    monkeypatch.setitem(sys.modules, "cchess_board", MagicMock())
    monkeypatch.setitem(sys.modules, "cchess_board.detector", MagicMock())


@pytest.fixture
def patched_engine(monkeypatch):
    """阻断真实引擎启动。"""
    from XQMagicUI.Engine import EngineManager

    monkeypatch.setattr(EngineManager, "loadEngine", lambda self, p, t: True)
    monkeypatch.setattr(EngineManager, "start", lambda self: None)
    monkeypatch.setattr(EngineManager, "stopThinking", lambda self: None)
    monkeypatch.setattr(EngineManager, "quit", lambda self: None)
    monkeypatch.setattr(EngineManager, "goFrom", lambda self, *a, **kw: True)
    monkeypatch.setattr(EngineManager, "setOption", lambda self, *a, **kw: None)
    monkeypatch.setattr(EngineManager, "redoThinking", lambda self: None)


@pytest.fixture
def patched_cloud(monkeypatch):
    """屏蔽云库 HTTP 请求,避免测试中真实访问外网。"""
    from XQMagicUI.CloudDB import CloudDB

    monkeypatch.setattr(CloudDB, "startQuery", lambda self, *a, **kw: None)
