import sys
import os
import logging
import traceback

import cv2
import numpy as np

from PyQt5.QtCore import Qt, QByteArray, QSize
from PyQt5.QtGui import *
from PyQt5.QtWidgets import (
    QStyle,
    QApplication,
    QMenu,
    QHBoxLayout,
    QVBoxLayout,
    QFormLayout,
    QDialog,
    QFileDialog,
    QLabel,
    QSpinBox,
    QCheckBox,
    QPushButton,
    QRadioButton,
    QLineEdit,
    QTextEdit,
    QWidget,
    QDockWidget,
    QDialogButtonBox,
    QButtonGroup,
    QListWidget,
    QListWidgetItem,
    QInputDialog,
    QAbstractItemView,
    QComboBox,
    QTreeWidgetItem,
    QTreeWidget,
    QSplitter,
    QMessageBox,
    QSlider,
    QGroupBox,
)


import cchess
from cchess import ChessBoard

from .BoardWidgets import ChessBoardEditWidget

# from .SnippingWidget import SnippingWidget
from .Utils import TimerMessageBox, getTitle

from . import Globl


# --------------------------------------------------------------#
class ImageView(QWidget):
    def __init__(self, parent, img=None):
        super().__init__()

        self.pixmap = None
        self.scaledPixmap = None

        self.setImage(img)

        # Black background
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), QColor(0, 0, 0))
        self.setPalette(p)

    def setImage(self, img):
        self.pixmap = img
        self.scaledPixmap = None
        self.update()

    def resizeEvent(self, ev):
        self._scalePixmap()
        super().resizeEvent(ev)

    def _scalePixmap(self):
        if self.pixmap is None:
            self.scaledPixmap = None
            return
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            self.scaledPixmap = None
            return
        self.scaledPixmap = self.pixmap.scaled(
            w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0))
        if self.scaledPixmap is not None:
            x = (self.width() - self.scaledPixmap.width()) // 2
            y = (self.height() - self.scaledPixmap.height()) // 2
            painter.drawPixmap(x, y, self.scaledPixmap)
        painter.end()

    def minimumSizeHint(self):
        return QSize(200, 200)


# -----------------------------------------------------#
class NumSlider(QWidget):
    def __init__(self, parent, v_min, v_max, v_step):
        super().__init__(parent)

        self.VLabel = QLabel(self)
        self.Slider = QSlider(Qt.Horizontal)
        self.Slider.setMinimum(v_min)
        self.Slider.setMaximum(v_max)
        self.Slider.setSingleStep(v_step)
        # self.Slider.setValue(value)
        # self.Slider.setTickInterval(400)
        # self.Slider.setTickPosition(QSlider.TicksBothSides)
        # self.Slider.setTickPosition(QSlider.TicksAbove)
        self.Slider.valueChanged.connect(self.onSlideValueChanged)

        hbox = QHBoxLayout()
        hbox.addWidget(self.Slider)
        hbox.addWidget(self.VLabel)

        self.setLayout(hbox)

    def value(self):
        return self.Slider.value()

    def setValue(self, value):
        self.VLabel.setText(str(value))
        self.Slider.setValue(value)

    def onSlideValueChanged(self, value):
        self.VLabel.setText(str(value))


##-----------------------------------------------------#
class PositionHistDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        # self.setFixedSize(200, 120)

        self.setWindowTitle("局面推演")

        vbox = QVBoxLayout()

        self.boardEdit = BoardHistoryWidget()
        vbox.addWidget(self.boardEdit)

        okBtn = QPushButton("完成", self)
        # cancelBtn = QPushButton("取消", self)
        # self.quit.setGeometry(62, 40, 75, 30)

        hbox = QHBoxLayout()
        hbox.addWidget(okBtn)
        vbox.addLayout(hbox)
        self.setLayout(vbox)

        okBtn.clicked.connect(self.accept)
        # cancelBtn.clicked.connect(self.onClose)

    def onInitBoard(self):
        self.boardEdit.from_fen(cchess.FULL_INIT_FEN)
        self.fenLabel.setText(self.boardEdit.to_fen())


# --------------------------------------------------------------#
class ImageToBoardDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle("图片棋盘识别")

        self.imageView = ImageView(self)

        self.boardEdit = ChessBoardEditWidget()
        self.redMoveBtn = QRadioButton("红方走", self)
        self.blackMoveBtn = QRadioButton("黑方走", self)

        group1 = QButtonGroup(self)
        group1.addButton(self.redMoveBtn)
        group1.addButton(self.blackMoveBtn)

        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.redMoveBtn, 0)
        hbox1.addWidget(self.blackMoveBtn, 0)
        hbox1.addWidget(QLabel(""), 1)

        initBtn = QPushButton("铺满", self)
        clearBtn = QPushButton("清空", self)
        # openImgBtn = QPushButton("打开图片", self)
        initBtn.clicked.connect(self.onInitBoard)
        clearBtn.clicked.connect(self.onClearBoard)
        # openImgBtn.clicked.connect(self.onOpenImage)

        okBtn = QPushButton("确定", self)
        #cancelBtn = QPushButton("取消", self)

        vbox = QVBoxLayout()
        vbox.addWidget(self.imageView)
        # vbox.addWidget(self.fenLabel)
        vbox.addLayout(hbox1)

        hbox = QHBoxLayout()
        hbox.addWidget(self.redMoveBtn)
        hbox.addWidget(self.blackMoveBtn)
        hbox.addWidget(initBtn)
        hbox.addWidget(clearBtn)
        # hbox.addWidget(openImgBtn)
        hbox.addWidget(okBtn)
        
        vbox.addLayout(hbox)
        self.setLayout(vbox)

        # self.boardEdit.fenChangedSignal.connect(self.onBoardFenChanged)
        # self.redMoveBtn.clicked.connect(self.onRedMoveBtnClicked)
        # self.blackMoveBtn.clicked.connect(self.onBlackMoveBtnClicked)

        okBtn.clicked.connect(self.accept)
        #cancelBtn.clicked.connect(self.close)

    def onInitBoard(self):
        self.boardEdit.from_fen(cchess.FULL_INIT_FEN)

    def onClearBoard(self):
        fen = "4k4/9/9/9/9/9/9/9/9/4K4 w"
        self.boardEdit.from_fen(fen)

    def onRedMoveBtnClicked(self):
        # self.boardEdit.set_move_color(cchess.RED)
        pass

    def onBlackMoveBtnClicked(self):
        # self.boardEdit.set_move_color(cchess.BLACK)
        pass

    def onBoardFenChanged(self, fen):
        self.fenLabel.setText(fen)

        color = self.boardEdit.get_move_color()
        if color == cchess.RED:
            self.redMoveBtn.setChecked(True)
        elif color == cchess.BLACK:
            self.blackMoveBtn.setChecked(True)

    def edit(self, img):
        self.imageView.setImage(img)
        if self.exec() == QDialog.Accepted:
            return "ok"
        else:
            return None


# -----------------------------------------------------#
class PositionEditDialog(QDialog):
    def __init__(self, parent, skinFolder=None):
        super().__init__(parent)

        self.setWindowTitle("局面编辑")

        self.boardEdit = ChessBoardEditWidget(self, skinFolder)
        self.redMoveBtn = QRadioButton("红方先行", self)
        self.blackMoveBtn = QRadioButton("黑方先行", self)
        self.fenLabel = QLabel()
        self.flipedBox = QCheckBox("翻转", self)

        group1 = QButtonGroup(self)
        group1.addButton(self.redMoveBtn)
        group1.addButton(self.blackMoveBtn)

        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.flipedBox, 0)
        hbox1.addWidget(self.redMoveBtn, 0)
        hbox1.addWidget(self.blackMoveBtn, 0)
        hbox1.addWidget(QLabel(""), 1)

        initBtn = QPushButton("初始棋盘", self)
        clearBtn = QPushButton("清空棋盘", self)
        openImgBtn = QPushButton("图片识别", self)
        initBtn.clicked.connect(self.onInitBoard)
        clearBtn.clicked.connect(self.onClearBoard)
        openImgBtn.clicked.connect(self.onOpenImage)

        okBtn = QPushButton("确定", self)
        cancelBtn = QPushButton("取消", self)

        self.imageView = ImageView(self)
        self.imageView.setMinimumSize(200, 200)
        self.imageView.hide()

        rightWidget = QWidget()
        rightLayout = QVBoxLayout(rightWidget)
        rightLayout.addWidget(self.fenLabel)
        rightLayout.addWidget(self.boardEdit, stretch=1)
        rightLayout.addLayout(hbox1)
        rightLayout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.imageView)
        self.splitter.addWidget(rightWidget)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

        vbox = QVBoxLayout()
        vbox.addWidget(self.splitter)

        hbox = QHBoxLayout()
        hbox.addWidget(openImgBtn)
        hbox.addWidget(initBtn)
        hbox.addWidget(clearBtn)
        hbox.addWidget(okBtn)
        hbox.addWidget(cancelBtn)

        vbox.addLayout(hbox)
        self.setLayout(vbox)

        self.boardEdit.fenChangedSignal.connect(self.onBoardFenChanged)
        self.redMoveBtn.clicked.connect(self.onRedMoveBtnClicked)
        self.blackMoveBtn.clicked.connect(self.onBlackMoveBtnClicked)
        self.flipedBox.stateChanged.connect(self.onFlipedChanged)

        okBtn.clicked.connect(self.accept)
        cancelBtn.clicked.connect(self.close)

        self.sourceImage = None

    def onInitBoard(self):
        self.boardEdit.from_fen(cchess.FULL_INIT_FEN)

    def onClearBoard(self):
        fen = "4k4/9/9/9/9/9/9/9/9/4K4 w"
        self.boardEdit.from_fen(fen)

    def onRedMoveBtnClicked(self):
        self.boardEdit.set_move_color(cchess.RED)

    def onBlackMoveBtnClicked(self):
        self.boardEdit.set_move_color(cchess.BLACK)

    def onFlipedChanged(self, state):
        self.boardEdit.flip_board = self.flipedBox.isChecked()
        self.boardEdit.update()

    def onOpenImage(self):
        options = QFileDialog.Options()

        fileName, _ = QFileDialog.getOpenFileName(
            self, "打开文件", "", "图片文件(*.jpg;*.jpeg;*.png;);;", options=options
        )

        if not fileName:
            return

        cv_img = cv2.imdecode(
            np.fromfile(str(fileName), dtype=np.uint8), cv2.IMREAD_COLOR
        )
        if cv_img is None:
            msgbox = TimerMessageBox("无法读取图片文件", timeout=2)
            msgbox.exec()
            return

        try:
            marked_pixmap, fen, is_fliped = Globl.detector.cv_image_to_fen_with_marked(
                cv_img
            )
            if fen:
                self.boardEdit.from_fen(fen)
                self.fenLabel.setText(fen)
                self.flipedBox.setChecked(is_fliped)

                self.boardEdit.flip_board = is_fliped

                if marked_pixmap:
                    self.imageView.setImage(marked_pixmap)
                    self.imageView.show()
                    h = self.height()
                    w_new = h * 2
                    center_x = self.x() + self.width() // 2
                    center_y = self.y() + self.height() // 2
                    self.resize(w_new, h)
                    self.move(center_x - w_new // 2, center_y - h // 2)
                    QApplication.processEvents()
                    total = self.splitter.width()
                    self.splitter.setSizes([total // 2, total // 2])
            else:
                msgbox = TimerMessageBox(
                    "未能识别出棋盘，请确保图片中包含完整的棋盘", timeout=3
                )
                msgbox.exec()
        except Exception as e:
            logging.error(f"图片识别失败: {e}")
            msgbox = TimerMessageBox(f"识别失败: {e}", timeout=3)
            msgbox.exec()

    def onSnippingCompleted(self, img):
        self.setWindowState(Qt.WindowActive)

    def onBoardFenChanged(self, fen):
        self.fenLabel.setText(fen)

        color = self.boardEdit.get_move_color()
        if color == cchess.RED:
            self.redMoveBtn.setChecked(True)
        elif color == cchess.BLACK:
            self.blackMoveBtn.setChecked(True)

    def edit(self, fen_str):
        self.boardEdit.from_fen(fen_str)

        if self.exec_() == QDialog.Accepted:
            return self.boardEdit.to_fen()
        else:
            return None

    def edit_img(self, img):
        self.imageView.setImage(img)
        if self.exec() == QDialog.Accepted:
            return "ok"
        else:
            return None

    def edit_img(self, img):
        self.imageView.setImage(img)
        if self.exec() == QDialog.Accepted:
            return "ok"
        else:
            return None


# --------------------------------------------------------------#

# UCI_Elo:更细致地限制引擎的棋力水平。
# 只有开启UCI_LimitStrength才会生效，设置范围1280~3133，越低越弱。如果不满足Skill Level的21个级别划分，
# 想要更加细致地划分引擎棋力水平，使用UCI_Elo即可。和Skill Level的限制棋力方式没有区别，只是更加细分。
# 其中Elo=1280等于Skill Level中的0，最高值3133等于Skill Level中的19，2850=13，2568=10，2268=7，1777=4。


class EngineConfigDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle("引擎设置")

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.MAX_MEM = 5000
        self.MAX_THREADS = os.cpu_count()

        self.enginePath = QLabel()
        self.engineType = QLabel()

        # vbox = QVBoxLayout()
        # hbox = QHBoxLayout()

        """
        self.ruleGroup = QButtonGroup(self)
        
        self.asiaBox = QCheckBox('亚洲规则')
        self.chineseBox = QCheckBox('中国规则')
        self.skyBox = QCheckBox('天天象棋规则')

        self.ruleGroup.addButton(self.asiaBox)
        self.ruleGroup.addButton(self.chineseBox)
        self.ruleGroup.addButton(self.skyBox)
        """
        self.rules = ["AsianRule", "ChineseRule", "SkyRule"]
        self.ruleCombo = QComboBox(self)

        self.ruleCombo.addItems(self.rules)
        self.ponderMode = QCheckBox("后台思考")

        self.threadsSpin = NumSlider(self, 1, self.MAX_THREADS, 1)
        self.memorySpin = NumSlider(self, 500, self.MAX_MEM, 100)
        self.multiPVSpin = NumSlider(self, 1, 7, 1)

        self.depthSpin = NumSlider(self, 0, 40, 2)
        self.timeSpin = NumSlider(self, 0, 120, 5)

        self.scoreFightSlider = NumSlider(self, 1280, 3150, 50)
        self.depthFightSpin = NumSlider(self, 0, 40, 2)
        self.moveTimeFightSpin = NumSlider(self, 0, 120, 5)

        engineBox = QGroupBox("引擎配置")
        fbox = QFormLayout()
        fbox.addRow("引擎路径:", self.enginePath)
        # fbox.addRow('', QLabel())
        fbox.addRow("引擎类别:", self.engineType)
        fbox.addRow("引擎棋规:", self.ruleCombo)
        fbox.addRow("思考方式:", self.ponderMode)
        fbox.addRow("线程数:", self.threadsSpin)
        fbox.addRow("内存(MB):", self.memorySpin)
        fbox.addRow("分支数:", self.multiPVSpin)

        engineBox.setLayout(fbox)

        defaultBox = QGroupBox("精确分析设置")

        f1 = QFormLayout()
        f1.addRow("限定深度:", self.depthSpin)
        f1.addRow("限定步时(秒):", self.timeSpin)
        defaultBox.setLayout(f1)
        # hbox.addWidget(defaultBox, 1)

        quickBox = QGroupBox("快速分析设置")
        self.quickDepthSpin = NumSlider(self, 0, 16, 2)
        self.quickTimeSpin = NumSlider(self, 0, 3, 1)
        f2 = QFormLayout()
        f2.addRow("限定深度:", self.quickDepthSpin)
        f2.addRow("限定步时(秒):", self.quickTimeSpin)
        quickBox.setLayout(f2)

        fightBox = QGroupBox("人机挑战设置")
        f3 = QFormLayout()
        f3.addRow("限定级别", self.scoreFightSlider)
        f3.addRow("限定深度", self.depthFightSpin)
        f3.addRow("限定步时（秒）", self.moveTimeFightSpin)
        fightBox.setLayout(f3)
        # hbox.addWidget(fightBox, 1)

        QBtn = (
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        buttonBox = QDialogButtonBox(QBtn)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        layout.addWidget(engineBox)
        layout.addWidget(defaultBox)
        layout.addWidget(quickBox)
        layout.addWidget(fightBox)
        # layout.addLayout(hbox)
        layout.addWidget(buttonBox)

        self.params = {}

        self.params["param.Threads"] = self.threadsSpin
        self.params["param.Hash"] = self.memorySpin
        # self.params['param.Ponder'] = self.ponderMode

        self.params["deep.MultiPV"] = self.multiPVSpin

        self.params["go.deep.depth"] = self.depthSpin
        self.params["go.deep.movetime"] = self.timeSpin

        self.params["go.quick.depth"] = self.quickDepthSpin
        self.params["go.quick.movetime"] = self.quickTimeSpin

        self.params["fight.UCI_Elo"] = self.scoreFightSlider
        self.params["go.fight.depth"] = self.depthFightSpin
        self.params["go.fight.movetime"] = self.moveTimeFightSpin

    def config(self, params):
        # logging.info(params)
        self.enginePath.setText(params["EnginePath"])
        self.engineType.setText(params["EngineType"])

        for p_name, widget in self.params.items():
            widget.setValue(params[p_name])

        self.ponderMode.setChecked(params["param.Ponder"])

        rule_index = self.rules.index(params["param.Repetition Rule"])
        self.ruleCombo.setCurrentIndex(rule_index)

        if self.exec() == QDialog.Accepted:
            for p_name, widget in self.params.items():
                params[p_name] = widget.value()

            params["param.Ponder"] = self.ponderMode.isChecked()

            ruleName = self.ruleCombo.currentText()
            params["param.Repetition Rule"] = ruleName

            return True
        else:
            return False


# --------------------------------------------------------------#
class QuickBookDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle("快速开局")

        layout = QVBoxLayout()
        self.setLayout(layout)


# --------------------------------------------------------------#
