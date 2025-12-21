import os
from pathlib import Path
import pytest
from PyQt5.QtCore import QSettings

def pytest_sessionstart(session):
    Path("Skins").mkdir(exist_ok=True)
    Path("Game").mkdir(exist_ok=True)

@pytest.fixture
def setup_globl(tmp_path):
    from MagicUI import Globl
    Globl.APP_NAME = 'XQMagic'
    Globl.APP_NAME_TEXT = '象棋魔术师'
    Globl.settings = QSettings('XQSoft', Globl.APP_NAME)
    Globl.config_file = Path('XQMagic.ini')
    ini = "[MainEngine]\nengine_type=ucci\nengine_exec=dummy_engine.exe\n"
    Globl.config_file.write_text(ini, encoding='utf-8')
    return Globl

