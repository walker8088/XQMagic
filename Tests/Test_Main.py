# test_dialog.py
import pytest
from pytestqt.qt_compat import qt_api   # 自动支持 PyQt5/PySide2/PySide6
from myapp.dialog import LoginDialog

def test_login_success(qtbot):          # qtbot 是核心 fixture
    dialog = LoginDialog()
    qtbot.addWidget(dialog)             # 自动注册到 qtbot，自动处理关闭
    dialog.show()                       # 可选，CI 可以 headless

    # 模拟用户输入
    qtbot.keyClicks(dialog.ui.username_edit, "admin")
    qtbot.keyClicks(dialog.ui.password_edit, "123456")
    qtbot.mouseClick(dialog.ui.login_button, qt_api.QtCore.Qt.LeftButton)

    # 断言登录成功后弹出了主窗口或者信号发出
    assert dialog.result() == qt_api.QtWidgets.QDialog.Accepted