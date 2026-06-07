# -*- coding: utf-8 -*-
"""程序内嵌的 pytest 测试运行器面板.

扫描 ``Tests/`` 目录下的测试文件,在 dock 面板中以树形展示所有可运行测试,
用户可勾选子集/全选,点击"运行"后通过 ``QProcess`` 启动子进程跑 pytest,
输出流式回显到日志面板,每个测试的通过/失败状态实时在树中标注。
"""

import ast
import sys
from pathlib import Path

from PyQt5.QtCore import QProcess, QProcessEnvironment, Qt
from PyQt5.QtGui import QColor, QFont, QTextCursor
from PyQt5.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import Globl


# --------------------------------------------------------------------------- #
# 测试发现 (AST)                                                               #
# --------------------------------------------------------------------------- #
class _TestVisitor(ast.NodeVisitor):
    """收集 class Test* 内的 def test_* 方法,以及模块级 def test_* 函数。"""

    def __init__(self, file_path, tests_dir):
        self.file_path = Path(file_path)
        self.tests_dir = Path(tests_dir)
        self.results = []
        self._class_stack = []

    def visit_ClassDef(self, node):
        if node.name.startswith("Test"):
            self._class_stack.append(node.name)
            self.generic_visit(node)
            self._class_stack.pop()
        # 非 Test* 类(含 TestCase 子类、辅助类等)内部的 def test_* 不是 pytest 收集对象,直接跳过
        return

    def visit_FunctionDef(self, node):
        if not node.name.startswith("test_"):
            self.generic_visit(node)
            return
        try:
            rel_file = str(self.file_path.relative_to(self.tests_dir.parent))
        except ValueError:
            rel_file = str(self.file_path)
        nodeid = f"Tests/{self.file_path.name}"
        if self._class_stack:
            cls = self._class_stack[-1]
            nodeid += f"::{cls}::{node.name}"
            display = f"{cls}::{node.name}"
        else:
            nodeid += f"::{node.name}"
            display = node.name
        self.results.append(
            {
                "file": rel_file,
                "nodeid": nodeid,
                "class": self._class_stack[-1] if self._class_stack else None,
                "method": node.name,
                "display": display,
            }
        )
        self.generic_visit(node)


def discover_tests(tests_dir):
    """扫描 tests_dir 下的 test_*.py,返回所有 pytest 测试节点列表."""
    tests_dir = Path(tests_dir)
    results = []
    if not tests_dir.exists():
        return results
    for f in sorted(tests_dir.glob("test_*.py")):
        try:
            source = f.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(f))
        except (OSError, SyntaxError):
            continue
        visitor = _TestVisitor(f, tests_dir)
        visitor.visit(tree)
        results.extend(visitor.results)
    return results


# --------------------------------------------------------------------------- #
# 结果标签与颜色                                                                #
# --------------------------------------------------------------------------- #
_RESULT_LABELS = {
    "pass": "通过",
    "fail": "失败",
    "skip": "跳过",
    "xfail": "预期失败",
    "xpass": "意外通过",
    "error": "错误",
}

_RESULT_TAGS = (
    (" PASSED", "pass", QColor(0, 130, 0)),
    (" FAILED", "fail", QColor(200, 0, 0)),
    (" SKIPPED", "skip", QColor(130, 130, 130)),
    (" XFAILED", "xfail", QColor(130, 130, 130)),
    (" XPASSED", "xpass", QColor(180, 130, 0)),
    (" ERROR", "error", QColor(200, 0, 0)),
)


# --------------------------------------------------------------------------- #
# 主面板                                                                       #
# --------------------------------------------------------------------------- #
class TestRunnerWidget(QDockWidget):
    """在主窗口内运行的 pytest 测试运行器.

    - 树形展示所有发现的测试,每行可勾选
    - "运行选中" / "运行全部" 启动 QProcess 跑 pytest
    - 日志面板流式显示 pytest 输出,实时高亮通过/失败
    - "停止" 终止子进程
    """

    def __init__(self, parent=None):
        super().__init__("测试运行器", parent)
        self.setObjectName("TestRunnerWidget")
        self.setAllowedAreas(Qt.AllDockWidgetAreas)

        self.process = None
        self.tests = []
        self.results_count = {k: 0 for k in _RESULT_LABELS}

        container = QWidget()
        self.setWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(4, 4, 4, 4)

        # 按钮行 ---------------------------------------------------------------
        btn_row = QHBoxLayout()
        self.refreshBtn = QPushButton("刷新")
        self.runSelectedBtn = QPushButton("运行选中")
        self.runAllBtn = QPushButton("运行全部")
        self.stopBtn = QPushButton("停止")
        self.clearBtn = QPushButton("清空输出")
        self.stopBtn.setEnabled(False)
        btn_row.addWidget(self.refreshBtn)
        btn_row.addWidget(self.runSelectedBtn)
        btn_row.addWidget(self.runAllBtn)
        btn_row.addWidget(self.stopBtn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.clearBtn)
        root.addLayout(btn_row)

        # 树 + 日志(垂直分割) -------------------------------------------------
        self.splitter = QSplitter(Qt.Vertical)
        root.addWidget(self.splitter, 1)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["测试", "结果"])
        self.tree.setColumnWidth(0, 320)
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.splitter.addWidget(self.tree)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
        mono = QFont("Consolas", 9)
        mono.setStyleHint(QFont.Monospace)
        self.log.setFont(mono)
        self.splitter.addWidget(self.log)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([300, 300])

        # 状态栏 ---------------------------------------------------------------
        self.statusLabel = QLabel("就绪")
        root.addWidget(self.statusLabel)

        # 信号 -----------------------------------------------------------------
        self.refreshBtn.clicked.connect(self.refresh)
        self.runSelectedBtn.clicked.connect(self.runSelected)
        self.runAllBtn.clicked.connect(self.runAll)
        self.stopBtn.clicked.connect(self.stop)
        self.clearBtn.clicked.connect(self.log.clear)

        # 初始发现
        self.refresh()
        if Globl.settings is not None:
            self.loadSettings(Globl.settings)

    # ------------------------------------------------------------------ #
    # 测试发现                                                           #
    # ------------------------------------------------------------------ #
    def _projectRoot(self):
        return Path(__file__).resolve().parent.parent

    def _testsDir(self):
        return self._projectRoot() / "Tests"

    def refresh(self):
        tests = discover_tests(self._testsDir())
        self.tests = tests
        self.tree.clear()
        files = {}
        for t in tests:
            files.setdefault(t["file"], []).append(t)
        for file_name in sorted(files):
            file_item = QTreeWidgetItem([file_name, ""])
            file_item.setFlags(file_item.flags() | Qt.ItemIsUserCheckable)
            file_item.setCheckState(0, Qt.Unchecked)
            file_item.setData(0, Qt.UserRole, None)
            for t in files[file_name]:
                test_item = QTreeWidgetItem([t["display"], ""])
                test_item.setFlags(test_item.flags() | Qt.ItemIsUserCheckable)
                test_item.setCheckState(0, Qt.Unchecked)
                test_item.setData(0, Qt.UserRole, t["nodeid"])
                file_item.addChild(test_item)
            self.tree.addTopLevelItem(file_item)
            file_item.setExpanded(True)
        n_files = len(files)
        self.statusLabel.setText(f"已发现 {len(tests)} 个测试 ({n_files} 个文件)")

    # ------------------------------------------------------------------ #
    # 运行                                                               #
    # ------------------------------------------------------------------ #
    def _getSelectedNodeids(self):
        nodeids = []
        for i in range(self.tree.topLevelItemCount()):
            file_item = self.tree.topLevelItem(i)
            for j in range(file_item.childCount()):
                child = file_item.child(j)
                if child.checkState(0) == Qt.Checked:
                    nid = child.data(0, Qt.UserRole)
                    if nid:
                        nodeids.append(nid)
        return nodeids

    def runSelected(self):
        nodeids = self._getSelectedNodeids()
        if not nodeids:
            self._appendLog("[!] 未选中任何测试\n")
            self.statusLabel.setText("未选中任何测试")
            return
        self._run(nodeids)

    def runAll(self):
        nodeids = [t["nodeid"] for t in self.tests]
        if not nodeids:
            self._appendLog("[!] 未发现任何测试\n")
            return
        self._run(nodeids)

    def _run(self, nodeids):
        if self.process is not None:
            self._appendLog("[!] 已有测试在运行,请先停止\n")
            return

        # 清空上一轮状态
        for i in range(self.tree.topLevelItemCount()):
            fi = self.tree.topLevelItem(i)
            fi.setText(1, "")
            for j in range(fi.childCount()):
                c = fi.child(j)
                c.setText(1, "")
                c.setForeground(1, QColor())
        for k in self.results_count:
            self.results_count[k] = 0

        project_root = self._projectRoot()
        args = [
            "-u",
            "-m",
            "pytest",
            "-v",
            "--tb=short",
            "--no-header",
            "--color=no",
        ] + nodeids

        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(project_root))

        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONPATH", str(project_root))
        env.insert("QT_QPA_PLATFORM", "offscreen")
        # 提示子进程使用 tmp_path 配置文件(防止误删用户 XQMagic.ini)
        env.insert("XQ_TEST_USE_TMP", "1")
        self.process.setProcessEnvironment(env)

        self.process.readyReadStandardOutput.connect(self._onStdout)
        self.process.readyReadStandardError.connect(self._onStderr)
        self.process.finished.connect(self._onFinished)
        self.process.errorOccurred.connect(self._onProcessError)

        self._appendLog(f"\n=== 开始运行 {len(nodeids)} 个测试 ===\n")
        self._appendLog(f"$ {sys.executable} {' '.join(args)}\n\n")

        self._setRunning(True)
        self.statusLabel.setText(f"运行中…(0/{len(nodeids)})")
        self.process.start(sys.executable, args)

    def stop(self):
        if self.process is not None:
            self._appendLog("\n[!] 正在终止子进程…\n")
            self.process.kill()

    # ------------------------------------------------------------------ #
    # QProcess 输出                                                       #
    # ------------------------------------------------------------------ #
    def _onStdout(self):
        if self.process is None:
            return
        data = bytes(self.process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        self._appendLog(data)
        self._parseProgress(data)

    def _onStderr(self):
        if self.process is None:
            return
        data = bytes(self.process.readAllStandardError()).decode(
            "utf-8", errors="replace"
        )
        self._appendLog(data)

    def _onProcessError(self, err):
        self._appendLog(f"\n[进程错误] {self.process.errorString()}\n")

    def _onFinished(self, exit_code, exit_status):
        self._appendLog(f"\n=== 进程结束(退出码 {exit_code}) ===\n")
        rc = self.results_count
        self.statusLabel.setText(
            f"完成 · 通过 {rc['pass']} · 失败 {rc['fail']} · 跳过 {rc['skip']}"
            f" · 预期失败 {rc['xfail']} · 意外通过 {rc['xpass']} · 错误 {rc['error']}"
        )
        self.process = None
        self._setRunning(False)

    # ------------------------------------------------------------------ #
    # 解析 pytest -v 输出                                                  #
    # ------------------------------------------------------------------ #
    def _parseProgress(self, data):
        for raw in data.splitlines():
            line = raw.strip()
            if "::" not in line:
                continue
            for tag, key, color in _RESULT_TAGS:
                if tag in line:
                    nodeid = line.split(tag, 1)[0].strip()
                    self._markResult(nodeid, _RESULT_LABELS[key], color)
                    self.results_count[key] += 1
                    break

    def _markResult(self, nodeid, text, color):
        for i in range(self.tree.topLevelItemCount()):
            fi = self.tree.topLevelItem(i)
            for j in range(fi.childCount()):
                c = fi.child(j)
                if c.data(0, Qt.UserRole) == nodeid:
                    c.setText(1, text)
                    c.setForeground(1, color)
                    return

    # ------------------------------------------------------------------ #
    # 工具                                                               #
    # ------------------------------------------------------------------ #
    def _setRunning(self, running):
        self.refreshBtn.setEnabled(not running)
        self.runSelectedBtn.setEnabled(not running)
        self.runAllBtn.setEnabled(not running)
        self.stopBtn.setEnabled(running)
        self.clearBtn.setEnabled(not running)

    def _appendLog(self, text):
        if not text:
            return
        self.log.moveCursor(QTextCursor.End)
        self.log.insertPlainText(text)
        self.log.moveCursor(QTextCursor.End)

    # ------------------------------------------------------------------ #
    # 设置持久化                                                          #
    # ------------------------------------------------------------------ #
    def loadSettings(self, settings):
        if settings is None:
            return
        state = settings.value("testRunner/splitter")
        if state:
            self.splitter.restoreState(state)

    def saveSettings(self, settings):
        if settings is None:
            return
        settings.setValue("testRunner/splitter", self.splitter.saveState())
