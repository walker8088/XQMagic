
import sys
import os
import logging
import traceback

from PyQt5.QtCore import Qt, QByteArray, QSize
from PyQt5.QtGui import *

from PyQt5.QtWidgets import QStyle, QApplication, QMenu, QHBoxLayout, QVBoxLayout, QFormLayout, QDialog, QFileDialog,\
                    QLabel, QSpinBox, QCheckBox, QPushButton, QRadioButton, QLineEdit,QTextEdit,\
                    QWidget, QDockWidget, QDialogButtonBox, QButtonGroup, QListWidget, QListWidgetItem, QInputDialog, \
                    QAbstractItemView, QComboBox, QTreeWidgetItem, QTreeWidget, QSplitter, QMessageBox, QSlider, QGroupBox


import cchess
from cchess import ChessBoard

from .BoardWidgets import ChessBoardEditWidget
#from .SnippingWidget import SnippingWidget

#-----------------------------------------------------#
class NumSlider(QWidget):
    def __init__(self, parent, v_min, v_max, v_step):
        super().__init__(parent)

        self.VLabel = QLabel(self)
        self.Slider = QSlider(Qt.Horizontal)
        self.Slider.setMinimum(v_min)
        self.Slider.setMaximum(v_max)
        self.Slider.setSingleStep(v_step)
        #self.Slider.setValue(value)
        #self.Slider.setTickInterval(400)
        #self.Slider.setTickPosition(QSlider.TicksBothSides)
        #self.Slider.setTickPosition(QSlider.TicksAbove)
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
 

#-----------------------------------------------------#
class TextInputDialog(QInputDialog):
    """
    自定义 QInputDialog，使输入框更宽（默认 500 px，可自行调节）。
    同时支持单行（QLineEdit）或多行（QTextEdit）两种模式。
    """
    def __init__(self, title: str = "", label: str = "", parent=None,
                 multiline: bool = False, width: int = 500):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setLabelText(label)
        self.multiline = multiline
        self.desired_width = width

        # 移除默认的 QLineEdit
        self.layout().removeWidget(self.findChild(QLineEdit))

        if self.multiline:
            self.text_edit = QTextEdit()
            self.text_edit.setAcceptRichText(False)
            self.text_edit.setFixedHeight(100)   # 多行时给个合适高度
        else:
            self.text_edit = QLineEdit()
            self.text_edit.setMinimumWidth(self.desired_width)

        # 重新加入布局（QInputDialog 的布局是 QGridLayout）
        self.layout().addWidget(self.text_edit, 1, 0, 1, 2)

        # 让对话框自适应宽度
        self.resize(self.desired_width + 100, self.sizeHint().height())

    def textValue(self) -> str:
        return self.text_edit.toPlainText().strip() if self.multiline else self.text_edit.text()

    @staticmethod
    def getText(parent, title, label, text="", multiline=False, width=500):
        dialog = LongTextInputDialog(title, label, parent, multiline, width)
        dialog.setTextValue(text)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.textValue(), True
        return "", False


#-----------------------------------------------------#
class PositionEditDialog(QDialog):
    def __init__(self, parent, skinFolder = None):
        super().__init__(parent)

        self.setWindowTitle("局面编辑")

        self.boardEdit = ChessBoardEditWidget(self, skinFolder)
        self.redMoveBtn = QRadioButton("红方走", self)
        self.blackMoveBtn = QRadioButton("黑方走", self)
        self.fenLabel = QLabel()

        group1 = QButtonGroup(self)
        group1.addButton(self.redMoveBtn)
        group1.addButton(self.blackMoveBtn)

        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.redMoveBtn, 0)
        hbox1.addWidget(self.blackMoveBtn, 0)
        hbox1.addWidget(QLabel(''), 1)

        initBtn = QPushButton("初始棋盘", self)
        clearBtn = QPushButton("清空棋盘", self)
        #openImgBtn = QPushButton("打开图片", self)
        initBtn.clicked.connect(self.onInitBoard)
        clearBtn.clicked.connect(self.onClearBoard)
        #openImgBtn.clicked.connect(self.onOpenImage)
        
        okBtn = QPushButton("确定", self)
        cancelBtn = QPushButton("取消", self)

        vbox = QVBoxLayout()
        vbox.addWidget(self.boardEdit)
        vbox.addWidget(self.fenLabel)
        vbox.addLayout(hbox1)

        hbox = QHBoxLayout()
        hbox.addWidget(self.redMoveBtn)
        hbox.addWidget(self.blackMoveBtn)
        hbox.addWidget(initBtn)
        hbox.addWidget(clearBtn)
        #hbox.addWidget(openImgBtn)
        hbox.addWidget(okBtn)
        hbox.addWidget(cancelBtn)

        vbox.addLayout(hbox)
        self.setLayout(vbox)

        self.boardEdit.fenChangedSignal.connect(self.onBoardFenChanged)
        self.redMoveBtn.clicked.connect(self.onRedMoveBtnClicked)
        self.blackMoveBtn.clicked.connect(self.onBlackMoveBtnClicked)

        okBtn.clicked.connect(self.accept)
        cancelBtn.clicked.connect(self.close)
        
        #self.snippingWidget = SnippingWidget()
        #self.snippingWidget.onSnippingCompleted = self.onSnippingCompleted

    def onInitBoard(self):
        self.boardEdit.from_fen(cchess.FULL_INIT_FEN)

    def onClearBoard(self):
        fen = '4k4/9/9/9/9/9/9/9/9/4K4 w'
        self.boardEdit.from_fen(fen)
        
    def onRedMoveBtnClicked(self):
        self.boardEdit.set_move_color(cchess.RED)

    def onBlackMoveBtnClicked(self):
        self.boardEdit.set_move_color(cchess.BLACK)
    
    def onOpenImage(self):
        self.snippingWidget.start()

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


#-----------------------------------------------------#
class PositionHistDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        #self.setFixedSize(200, 120)

        self.setWindowTitle("局面推演")

        vbox = QVBoxLayout()

        self.boardEdit = BoardHistoryWidget()
        vbox.addWidget(self.boardEdit)

        okBtn = QPushButton("完成", self)
        #cancelBtn = QPushButton("取消", self)
        #self.quit.setGeometry(62, 40, 75, 30)

        hbox = QHBoxLayout()
        hbox.addWidget(okBtn)
        vbox.addLayout(hbox)
        self.setLayout(vbox)

        okBtn.clicked.connect(self.accept)
        #cancelBtn.clicked.connect(self.onClose)

    def onInitBoard(self):
        self.boardEdit.from_fen(cchess.FULL_INIT_FEN)
        self.fenLabel.setText(self.boardEdit.to_fen())

#--------------------------------------------------------------#
class ImageView(QWidget):
    def __init__(self, parent, img=None):
        super().__init__()
        
        self.parent = parent
        
        self.left = 0
        self.top = 0
        self.height = 0
        self.width = 0
        self.view_size = None
        
        self.setImage(img)
        
    def setImage(self, img):
        self.img = img
        if img is None:
            return 
        self.height = img.size().height()
        self.width  = img.size().width()
        self.pixmap = img #QPixmap.fromImage() 
        
        pixelRatio = qApp.devicePixelRatio()
        self.pixmap = self.pixmap.scaled(img.size() * pixelRatio, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self.pixmap.setDevicePixelRatio(pixelRatio)
    
        v_size = self.parent.size()
        width = max(self.width, v_size.width())
        height = max(self.height, v_size.height())
        self.setGeometry(0, 0, width, height)

        self.resize()
        self.update()
        
    def resize(self):
        if self.view_size is None:
            self.left = 0
            self.top = 0
            return

        self.left = (self.view_size.width() - self.width) // 2
        if self.left < 0:
            self.left = 0

        self.top = (self.view_size.height() - self.height) // 2
        if self.top < 0:
            self.top = 0
        
    def resizeEvent(self, ev):
        self.view_size = ev.size()
        self.resize()
    
    def paintEvent(self, ev):
        painter = QPainter(self)
        if self.pixmap is not None:
            painter.drawPixmap(self.left, self.top, self.pixmap)
    
    def minimumSizeHint(self):
        return QSize(self.width, self.height)
    
    def showValue(self, pos):
        if (pos.x() < self.left) or (pos.x() >= self.left + self.width)\
            or (pos.y() < self.top) or (pos.y() >= self.top + self.height):
            self.setCursor(Qt.ArrowCursor)
            main_win.status('')
        else:    
            x = pos.x() - self.left
            y = pos.y() - self.top
            pixel = self.img[y,x]
            main_win.status('x={} y={} value={}'.format(x, y, str(pixel)))
            self.setCursor(Qt.CrossCursor) 
        
    def mousePressEvent(self, mouseEvent):
        
        if self.img is None:
            return
            
        if (mouseEvent.button() != Qt.LeftButton):
            return
        
        self.showValue(mouseEvent.position())        
        
    def mouseMoveEvent(self, mouseEvent):
        
        if self.img is None:
            return
        
        self.showValue(mouseEvent.position())        
        
        
    def mouseReleaseEvent(self, mouseEvent):
        self.setCursor(Qt.ArrowCursor)
        

#--------------------------------------------------------------#
class ImageToBoardDialog(QDialog):
    
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle("图片棋盘识别")

        self.imageView = ImageView(self)
        
        #self.boardEdit = ChessBoardEditWidget()
        self.redMoveBtn = QRadioButton("红方走", self)
        self.blackMoveBtn = QRadioButton("黑方走", self)
        
        group1 = QButtonGroup(self)
        group1.addButton(self.redMoveBtn)
        group1.addButton(self.blackMoveBtn)

        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.redMoveBtn, 0)
        hbox1.addWidget(self.blackMoveBtn, 0)
        hbox1.addWidget(QLabel(''), 1)

        initBtn = QPushButton("铺满", self)
        clearBtn = QPushButton("清空", self)
        #openImgBtn = QPushButton("打开图片", self)
        initBtn.clicked.connect(self.onInitBoard)
        clearBtn.clicked.connect(self.onClearBoard)
        #openImgBtn.clicked.connect(self.onOpenImage)
        
        okBtn = QPushButton("确定", self)
        cancelBtn = QPushButton("取消", self)

        vbox = QVBoxLayout()
        vbox.addWidget(self.imageView )
        #vbox.addWidget(self.fenLabel)
        vbox.addLayout(hbox1)

        hbox = QHBoxLayout()
        hbox.addWidget(self.redMoveBtn)
        hbox.addWidget(self.blackMoveBtn)
        hbox.addWidget(initBtn)
        hbox.addWidget(clearBtn)
        #hbox.addWidget(openImgBtn)
        hbox.addWidget(okBtn)
        hbox.addWidget(cancelBtn)

        vbox.addLayout(hbox)
        self.setLayout(vbox)

        #self.boardEdit.fenChangedSignal.connect(self.onBoardFenChanged)
        #self.redMoveBtn.clicked.connect(self.onRedMoveBtnClicked)
        #self.blackMoveBtn.clicked.connect(self.onBlackMoveBtnClicked)

        okBtn.clicked.connect(self.accept)
        cancelBtn.clicked.connect(self.close)
    
    def onInitBoard(self):
        self.boardEdit.from_fen(cchess.FULL_INIT_FEN)
        
    def onClearBoard(self):
        fen = '4k4/9/9/9/9/9/9/9/9/4K4 w'
        self.boardEdit.from_fen(fen)
        
    def onRedMoveBtnClicked(self):
        #self.boardEdit.set_move_color(cchess.RED)
        pass

    def onBlackMoveBtnClicked(self):
        #self.boardEdit.set_move_color(cchess.BLACK)
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
            return 'ok'
        else:
            return None

#--------------------------------------------------------------#

#UCI_Elo:更细致地限制引擎的棋力水平。
#只有开启UCI_LimitStrength才会生效，设置范围1280~3133，越低越弱。如果不满足Skill Level的21个级别划分，
#想要更加细致地划分引擎棋力水平，使用UCI_Elo即可。和Skill Level的限制棋力方式没有区别，只是更加细分。 
#其中Elo=1280等于Skill Level中的0，最高值3133等于Skill Level中的19，2850=13，2568=10，2268=7，1777=4。

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
        
        #vbox = QVBoxLayout()
        #hbox = QHBoxLayout()

        '''
        self.ruleGroup = QButtonGroup(self)
        
        self.asiaBox = QCheckBox('亚洲规则')
        self.chineseBox = QCheckBox('中国规则')
        self.skyBox = QCheckBox('天天象棋规则')

        self.ruleGroup.addButton(self.asiaBox)
        self.ruleGroup.addButton(self.chineseBox)
        self.ruleGroup.addButton(self.skyBox)
        '''
        self.rules = ['AsianRule', 'ChineseRule', 'SkyRule']
        self.ruleCombo = QComboBox(self)

        self.ruleCombo.addItems(self.rules)
        self.ponderMode = QCheckBox('后台思考')

        self.threadsSpin = NumSlider(self, 1, self.MAX_THREADS, 1)
        self.memorySpin  = NumSlider(self, 500, self.MAX_MEM, 100)
        self.multiPVSpin = NumSlider(self, 1, 7, 1)
    
        self.depthSpin = NumSlider(self, 0, 40, 2)
        self.timeSpin = NumSlider(self, 0, 120, 5)
           
        self.scoreFightSlider = NumSlider(self, 1280, 3150, 50)
        self.depthFightSpin = NumSlider(self, 0, 40, 2)
        self.moveTimeFightSpin = NumSlider(self, 0, 120, 5)
        
        engineBox = QGroupBox("引擎配置")
        fbox = QFormLayout()    
        fbox.addRow('引擎路径:', self.enginePath)
        #fbox.addRow('', QLabel())  
        fbox.addRow('引擎类别:', self.engineType)
        fbox.addRow('引擎棋规:', self.ruleCombo)
        fbox.addRow('思考方式:', self.ponderMode)
        fbox.addRow('线程数:', self.threadsSpin)
        fbox.addRow('内存(MB):', self.memorySpin)
        fbox.addRow('分支数:', self.multiPVSpin)
        
        engineBox.setLayout(fbox)
        
        defaultBox = QGroupBox("精确分析设置")
        
        f1 = QFormLayout()    
        f1.addRow('限定深度:', self.depthSpin)
        f1.addRow('限定步时(秒):', self.timeSpin)
        defaultBox.setLayout(f1)
        #hbox.addWidget(defaultBox, 1)
        
        quickBox = QGroupBox("快速分析设置")
        self.quickDepthSpin = NumSlider(self, 5, 16, 2)
        self.quickTimeSpin = NumSlider(self, 1, 3, 1)
        f2 = QFormLayout()    
        f2.addRow('限定深度:', self.quickDepthSpin)
        f2.addRow('限定步时(秒):', self.quickTimeSpin)
        quickBox.setLayout(f2)
        

        fightBox = QGroupBox("人机挑战设置")
        f3 = QFormLayout()
        f3.addRow('限定级别', self.scoreFightSlider)
        f3.addRow('限定深度', self.depthFightSpin)
        f3.addRow('限定步时（秒）', self.moveTimeFightSpin)
        fightBox.setLayout(f3)
        #hbox.addWidget(fightBox, 1)
        
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
        #layout.addLayout(hbox)
        layout.addWidget(buttonBox)

        self.params = {}
        
        self.params['param.Threads'] = self.threadsSpin
        self.params['param.Hash'] = self.memorySpin
        #self.params['param.Ponder'] = self.ponderMode

        self.params['deep.MultiPV'] = self.multiPVSpin
        
        self.params["go.deep.depth"] = self.depthSpin
        self.params["go.deep.movetime"] = self.timeSpin
        
        self.params["go.quick.depth"] = self.quickDepthSpin
        self.params["go.quick.movetime"] = self.quickTimeSpin

        self.params['fight.UCI_Elo'] = self.scoreFightSlider
        self.params["go.fight.depth"] = self.depthFightSpin
        self.params['go.fight.movetime'] = self.moveTimeFightSpin
        
        
    def config(self, params):
        #logging.info(params)
        self.enginePath.setText(params['EnginePath'])
        self.engineType.setText(params['EngineType'])

        for p_name, widget in self.params.items():
            widget.setValue(params[p_name])
        
        self.ponderMode.setChecked(params['param.Ponder'])

        rule_index = self.rules.index(params['param.Repetition Rule'])
        self.ruleCombo.setCurrentIndex(rule_index)
        
        if self.exec() == QDialog.Accepted:
            for p_name, widget in self.params.items():
                params[p_name] = widget.value()
               
            params['param.Ponder'] = self.ponderMode.isChecked()

            ruleName = self.ruleCombo.currentText()        
            params['param.Repetition Rule'] = ruleName
            
            return True
        else:
            return False

#--------------------------------------------------------------#
class QuickBookDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle('快速开局')
        
        layout = QVBoxLayout()
        self.setLayout(layout)



#--------------------------------------------------------------#
class LongTextInputDialog(QInputDialog):
    """
    自定义 QInputDialog，使输入框更宽（默认 500 px，可自行调节）。
    同时支持单行（QLineEdit）或多行（QTextEdit）两种模式。
    """
    def __init__(self, title: str = "", label: str = "", parent=None,
                 multiline: bool = False, width: int = 500):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setLabelText(label)
        self.multiline = multiline
        self.desired_width = width

        # 移除默认的 QLineEdit
        self.layout().removeWidget(self.findChild(QLineEdit))

        if self.multiline:
            from PyQt5.QtWidgets import QTextEdit
            self.text_edit = QTextEdit()
            self.text_edit.setAcceptRichText(False)
            self.text_edit.setFixedHeight(100)   # 多行时给个合适高度
        else:
            self.text_edit = QLineEdit()
            self.text_edit.setMinimumWidth(self.desired_width)

        # 重新加入布局（QInputDialog 的布局是 QGridLayout）
        self.layout().addWidget(self.text_edit, 1, 0, 1, 2)

        # 让对话框自适应宽度
        self.resize(self.desired_width + 100, self.sizeHint().height())

    def textValue(self) -> str:
        return self.text_edit.toPlainText().strip() if self.multiline else self.text_edit.text()

    @staticmethod
    def getText(parent, title, label, text="", multiline=False, width=500):
        dialog = LongTextInputDialog(title, label, parent, multiline, width)
        dialog.setTextValue(text)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.textValue(), True
        return "", False
#--------------------------------------------------------------#
        