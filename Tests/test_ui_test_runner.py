# -*- coding: utf-8 -*-
"""测试运行器面板的单元测试.

覆盖范围:
- AST 解析器识别测试类/方法/模块级函数
- discover_tests 能扫描真实 Tests/ 目录
- TestRunnerWidget 控件创建/按钮状态/选择收集/输出解析
"""

import ast
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTreeWidgetItem


# =====================================================================
# _TestVisitor - AST 解析器
# =====================================================================
class TestTestVisitor:
    """AST 解析器应正确识别测试类、方法和模块级测试函数."""

    def test_finds_test_classes(self):
        from XQMagicUI.TestRunner import _TestVisitor

        code = """
class TestFoo:
    def test_one(self):
        pass
    def test_two(self):
        pass

class TestBar:
    def test_three(self):
        pass

def test_module_level():
    pass
"""
        tree = ast.parse(code)
        f = Path("Tests/test_fake.py")
        visitor = _TestVisitor(f, Path("."))
        visitor.visit(tree)
        names = [r["display"] for r in visitor.results]
        assert "TestFoo::test_one" in names
        assert "TestFoo::test_two" in names
        assert "TestBar::test_three" in names
        assert "test_module_level" in names

    def test_nodeid_format(self):
        from XQMagicUI.TestRunner import _TestVisitor

        code = """
class TestX:
    def test_a(self):
        pass
def test_b():
    pass
"""
        tree = ast.parse(code)
        f = Path("Tests/test_fake.py")
        visitor = _TestVisitor(f, Path("."))
        visitor.visit(tree)
        nodeids = [r["nodeid"] for r in visitor.results]
        assert "Tests/test_fake.py::TestX::test_a" in nodeids
        assert "Tests/test_fake.py::test_b" in nodeids

    def test_class_attr_set(self):
        from XQMagicUI.TestRunner import _TestVisitor

        code = """
class TestX:
    def test_a(self):
        pass
"""
        tree = ast.parse(code)
        f = Path("Tests/test_fake.py")
        visitor = _TestVisitor(f, Path("."))
        visitor.visit(tree)
        assert len(visitor.results) == 1
        r = visitor.results[0]
        assert r["class"] == "TestX"
        assert r["method"] == "test_a"
        # Windows 下 Path 转 str 可能用反斜杠,只比较末尾文件名
        assert r["file"].endswith("test_fake.py")
        assert "test_fake.py" in r["file"]

    def test_non_test_class_ignored(self):
        from XQMagicUI.TestRunner import _TestVisitor

        code = """
class Helper:
    def test_foo(self):
        pass
def helper_func():
    pass
"""
        tree = ast.parse(code)
        f = Path("Tests/test_fake.py")
        visitor = _TestVisitor(f, Path("."))
        visitor.visit(tree)
        # 非 Test* 类内/非 test_ 开头的函数都不应被收录
        assert visitor.results == []


# =====================================================================
# discover_tests - 测试发现
# =====================================================================
class TestDiscoverTests:
    def test_finds_real_tests(self):
        from XQMagicUI.TestRunner import discover_tests

        tests = discover_tests(Path("Tests"))
        # 重点不是“至少多少个”，而是“能扫到东西且与文件数能对得上”。
        # 断言 (1) 非空 (2) 不少于测试文件数 (3) 任何后续维护都能继续通过。
        assert len(tests) > 0
        # 7+ 过于脆弱；改为“远多于文件数”保证并不随个别测试增减而
        # 被频繁地修改阈值。具体数字取 200，未覆盖时只会提醒不需破环代码。
        assert len(tests) > 200  # 足够保护“大部分主要代码都有测试”

    def test_nodeids_are_unique(self):
        from XQMagicUI.TestRunner import discover_tests

        tests = discover_tests(Path("Tests"))
        nodeids = [t["nodeid"] for t in tests]
        assert len(nodeids) == len(set(nodeids))

    def test_nonexistent_dir_returns_empty(self):
        from XQMagicUI.TestRunner import discover_tests

        tests = discover_tests(Path("nonexistent_dir_xyz"))
        assert tests == []


# =====================================================================
# TestRunnerWidget - 面板行为
# =====================================================================
class TestTestRunnerWidget:
    def test_creation_discovers_tests(self, qtbot, setup_globl):
        from XQMagicUI.TestRunner import TestRunnerWidget

        w = TestRunnerWidget()
        qtbot.addWidget(w)
        assert w.tree.topLevelItemCount() > 0
        # 至少有一个文件行 + 子测试行
        first_file = w.tree.topLevelItem(0)
        assert first_file.childCount() > 0

    def test_buttons_disabled_when_idle(self, qtbot, setup_globl):
        from XQMagicUI.TestRunner import TestRunnerWidget

        w = TestRunnerWidget()
        qtbot.addWidget(w)
        assert w.stopBtn.isEnabled() is False
        assert w.runSelectedBtn.isEnabled() is True
        assert w.runAllBtn.isEnabled() is True

    def test_run_all_starts_qprocess(self, qtbot, setup_globl):
        from XQMagicUI.TestRunner import TestRunnerWidget

        w = TestRunnerWidget()
        qtbot.addWidget(w)
        with patch("XQMagicUI.TestRunner.QProcess") as mock_proc:
            mock_instance = MagicMock()
            mock_proc.return_value = mock_instance
            w.runAll()
            mock_instance.start.assert_called_once()
            # 启动后 stopBtn 应启用
            assert w.stopBtn.isEnabled() is True
            assert w.runAllBtn.isEnabled() is False
            assert w.runSelectedBtn.isEnabled() is False

    def test_run_selected_starts_qprocess(self, qtbot, setup_globl):
        from XQMagicUI.TestRunner import TestRunnerWidget

        w = TestRunnerWidget()
        qtbot.addWidget(w)
        if w.tree.topLevelItemCount() > 0 and w.tree.topLevelItem(0).childCount() > 0:
            w.tree.topLevelItem(0).child(0).setCheckState(0, Qt.Checked)
        with patch("XQMagicUI.TestRunner.QProcess") as mock_proc:
            mock_instance = MagicMock()
            mock_proc.return_value = mock_instance
            w.runSelected()
            mock_instance.start.assert_called_once()
            # QProcess.start(program, arguments) - call_args[0] = (program, args_list)
            call_args = mock_instance.start.call_args[0]
            program, arg_list = call_args[0], call_args[1]
            assert program == sys.executable
            assert "-m" in arg_list
            assert "pytest" in arg_list
            # 末尾应是选中的那个 nodeid
            assert arg_list[-1].startswith("Tests/")

    def test_run_selected_no_selection_logs(self, qtbot, setup_globl):
        from XQMagicUI.TestRunner import TestRunnerWidget

        w = TestRunnerWidget()
        qtbot.addWidget(w)
        w.runSelected()
        # 没有选中任何测试,日志中应有提示
        assert "[!]" in w.log.toPlainText()
        assert "未选中" in w.log.toPlainText()

    def test_double_run_is_rejected(self, qtbot, setup_globl):
        from XQMagicUI.TestRunner import TestRunnerWidget

        w = TestRunnerWidget()
        qtbot.addWidget(w)
        with patch("XQMagicUI.TestRunner.QProcess") as mock_proc:
            mock_instance = MagicMock()
            mock_proc.return_value = mock_instance
            w.runAll()
            w._appendLog("")  # 触发一次日志写入
            # 第二次 runAll 应被拒绝
            w.runAll()
            # 只应启动一次
            assert mock_instance.start.call_count == 1
            # 第二次尝试应在日志里写警告
            assert w.log.toPlainText().count("已有测试在运行") >= 1

    def test_stop_kills_process(self, qtbot, setup_globl):
        from XQMagicUI.TestRunner import TestRunnerWidget

        w = TestRunnerWidget()
        qtbot.addWidget(w)
        with patch("XQMagicUI.TestRunner.QProcess") as mock_proc:
            mock_instance = MagicMock()
            mock_proc.return_value = mock_instance
            w.runAll()
            w.stop()
            mock_instance.kill.assert_called_once()

    def test_get_selected_nodeids(self, qtbot, setup_globl):
        from XQMagicUI.TestRunner import TestRunnerWidget

        w = TestRunnerWidget()
        qtbot.addWidget(w)
        assert w._getSelectedNodeids() == []
        if w.tree.topLevelItemCount() > 0:
            fi = w.tree.topLevelItem(0)
            if fi.childCount() > 0:
                c = fi.child(0)
                c.setCheckState(0, Qt.Checked)
                nodeids = w._getSelectedNodeids()
                assert len(nodeids) == 1
                assert "::" in nodeids[0]

    def test_parse_progress_marks_pass(self, qtbot, setup_globl):
        from XQMagicUI.TestRunner import TestRunnerWidget

        w = TestRunnerWidget()
        qtbot.addWidget(w)

        # 注入一个伪造测试到树里
        fi = QTreeWidgetItem(["fake.py", ""])
        c = QTreeWidgetItem(["test_x", ""])
        c.setData(0, Qt.UserRole, "Tests/test_fake.py::test_x")
        fi.addChild(c)
        w.tree.addTopLevelItem(fi)

        w._parseProgress("Tests/test_fake.py::test_x PASSED in 0.01s\n")
        assert c.text(1) == "通过"
        assert w.results_count["pass"] == 1

    def test_parse_progress_marks_fail(self, qtbot, setup_globl):
        from XQMagicUI.TestRunner import TestRunnerWidget

        w = TestRunnerWidget()
        qtbot.addWidget(w)
        fi = QTreeWidgetItem(["fake.py", ""])
        c = QTreeWidgetItem(["test_y", ""])
        c.setData(0, Qt.UserRole, "Tests/test_fake.py::test_y")
        fi.addChild(c)
        w.tree.addTopLevelItem(fi)

        w._parseProgress("Tests/test_fake.py::test_y FAILED\n")
        assert c.text(1) == "失败"
        assert w.results_count["fail"] == 1

    def test_parse_progress_handles_class_method(self, qtbot, setup_globl):
        from XQMagicUI.TestRunner import TestRunnerWidget

        w = TestRunnerWidget()
        qtbot.addWidget(w)
        fi = QTreeWidgetItem(["fake.py", ""])
        c = QTreeWidgetItem(["TestZ::test_z", ""])
        c.setData(0, Qt.UserRole, "Tests/test_fake.py::TestZ::test_z")
        fi.addChild(c)
        w.tree.addTopLevelItem(fi)

        w._parseProgress("Tests/test_fake.py::TestZ::test_z SKIPPED\n")
        assert c.text(1) == "跳过"
        assert w.results_count["skip"] == 1

    def test_parse_progress_ignores_unrelated_lines(self, qtbot, setup_globl):
        from XQMagicUI.TestRunner import TestRunnerWidget

        w = TestRunnerWidget()
        qtbot.addWidget(w)
        # 这些行不应该增加任何计数
        w._parseProgress("===== test session starts =====\n")
        w._parseProgress("platform linux -- Python 3.11\n")
        assert sum(w.results_count.values()) == 0

    def test_clear_output(self, qtbot, setup_globl):
        from XQMagicUI.TestRunner import TestRunnerWidget

        w = TestRunnerWidget()
        qtbot.addWidget(w)
        w._appendLog("一些日志\n")
        assert w.log.toPlainText() != ""
        w.clearBtn.click()
        assert w.log.toPlainText() == ""

    def test_save_load_settings(self, qtbot, setup_globl):
        from XQMagicUI import Globl
        from XQMagicUI.TestRunner import TestRunnerWidget

        w = TestRunnerWidget()
        qtbot.addWidget(w)
        # 验证 save/load 不报异常,splitter 状态可读写
        w.saveSettings(Globl.settings)
        w2 = TestRunnerWidget()
        qtbot.addWidget(w2)
        # splitter 状态是 base64 字符串,可成功读写
        assert Globl.settings.value("testRunner/splitter") is not None

    def test_refresh_rebuilds_tree(self, qtbot, setup_globl):
        from XQMagicUI.TestRunner import TestRunnerWidget

        w = TestRunnerWidget()
        qtbot.addWidget(w)
        n_before = w.tree.topLevelItemCount()
        w.refresh()
        n_after = w.tree.topLevelItemCount()
        assert n_before == n_after
        assert n_after > 0
