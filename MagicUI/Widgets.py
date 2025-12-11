# -*- coding: utf-8 -*-
import os
import logging
import traceback
from pathlib import Path
from collections import OrderedDict

from PyQt5.QtCore import pyqtSignal, QSize, Qt, QTimer, QModelIndex
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem, QColor, QBrush
from PyQt5.QtWidgets import QStyle, QApplication, QMenu, QHBoxLayout, QVBoxLayout, QFormLayout, QDialog, QFileDialog,\
                    QLabel, QSpinBox, QCheckBox, QPushButton, QRadioButton, QToolButton, \
                    QWidget, QDockWidget, QDialogButtonBox, QButtonGroup, QListWidget, QListWidgetItem, QInputDialog, \
                    QAbstractItemView, QComboBox, QTreeWidgetItem, QTreeWidget, QTextEdit, QSplitter, QMessageBox, QTableView, \
                    QWidget,QHeaderView, QAbstractItemView

import cchess
from cchess import ChessBoard

from .Utils import Stage, GameMode, ReviewMode, getTitle, TimerMessageBox, getFreeMem, getStepsTextFromFenMoves, loadEglib, loadCsvlib
from .BoardWidgets import ChessBoardWidget, ChessBoardEditWidget
from .SnippingWidget import SnippingWidget
from .Dialogs import EngineConfigDialog

from . import Globl


#------------------------------------------------------------------#
class NumEdit(QWidget):
    """带左右加减按钮的数字编辑控件"""
    valueChanged = pyqtSignal(int)   # 值改变时发出信号

    def __init__(self, value=0, min_value=None, max_value=None, step=1, parent=None):
        super().__init__(parent)

        self.step = step
        self._value = value

        # 创建布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 减按钮
        self.btn_minus = QToolButton(self)
        self.btn_minus.setText("–")          # en dash，更美观
        self.btn_minus.clicked.connect(self.decrease)

        # 数字编辑框（使用 QSpinBox 更方便控制范围和滚轮）
        self.spinbox = QSpinBox(self)
        self.spinbox.setButtonSymbols(QSpinBox.NoButtons)  # 隐藏自带上下箭头
        self.spinbox.setAlignment(Qt.AlignCenter)
        self.spinbox.valueChanged.connect(self._on_spinbox_changed)

        # 加按钮
        self.btn_plus = QToolButton(self)
        self.btn_plus.setText("+")
        self.btn_plus.clicked.connect(self.increase)

        # 添加到布局
        layout.addWidget(self.btn_minus)
        layout.addWidget(self.spinbox)
        layout.addWidget(self.btn_plus)

        # 设置范围
        if min_value is not None:
            self.spinbox.setMinimum(min_value)
        if max_value is not None:
            self.spinbox.setMaximum(max_value)

        # 初始值
        self.setValue(value)

        # 启用滚轮支持
        self.spinbox.wheelEvent = self._wheelEvent

    def increase(self):
        self.setValue(self.value() + self.step)

    def decrease(self):
        self.setValue(self.value() - self.step)

    def value(self):
        return self.spinbox.value()

    def setValue(self, value):
        old = self.value()
        self.spinbox.setValue(value)
        if value != old:
            self.valueChanged.emit(value)

    def setRange(self, min_val, max_val):
        self.spinbox.setRange(min_val, max_val)

    def setStep(self, step):
        self.step = step

    def setReadOnly(self, readonly):
        self.spinbox.setReadOnly(readonly)
        # 可选：只读时也可以隐藏光标
        self.spinbox.setButtonSymbols(QSpinBox.NoButtons if readonly else QSpinBox.NoButtons)

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self.btn_minus.setEnabled(enabled)
        self.btn_plus.setEnabled(enabled)
        self.spinbox.setEnabled(enabled)

    # 内部：spinbox 值改变时同步
    def _on_spinbox_changed(self, value):
        if value != self._value:
            self._value = value
            self.valueChanged.emit(value)

    # 支持鼠标滚轮
    def _wheelEvent(self, event):
        # 只在控件有焦点或鼠标悬停时响应滚轮（默认行为已满足）
        super(QSpinBox, self.spinbox).wheelEvent(event)


#------------------------------------------------------------------#
class DockWidget(QDockWidget):
    def __init__(self, parent, dock_areas):
        super().__init__(parent)
        self.setAllowedAreas(dock_areas)

#------------------------------------------------------------------#
class DocksWidget(QDockWidget):
    def __init__(self, name, parent, inner, dock_areas):
        super().__init__(parent)

        self.setObjectName(name)
        self.inner = inner
        self.setWidget(self.inner)
        self.setWindowTitle(self.inner.title)
        self.setAllowedAreas(dock_areas)


#------------------------------------------------------------------#
class LabelWidget(QWidget):
    def __init__(self, label, widget):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(label))
        layout.addWidget(widget)
        
#------------------------------------------------------------------#
class HistoryWidget(QWidget):
    positionChangeSignal = pyqtSignal(int)
    removeFollowSignal = pyqtSignal(int)
    
    def __init__(self):
        super().__init__()

        self.title = "棋谱记录"        
        self.isShowScore = True 
        self.currRow = -1
        self.posList = []

        self.posView = QTableView()
        self.posView.setSelectionBehavior(QAbstractItemView.SelectRows)   # 选中整行
        self.posView.setSelectionMode(QAbstractItemView.SingleSelection)
        self.posView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.posView.verticalHeader().setVisible(False)                  # 隐藏左侧行号
        self.posView.setShowGrid(False)
        self.posView.setAlternatingRowColors(True)                       # 交替背景色
        self.posView.verticalHeader().setDefaultSectionSize(22)

        # 创建模型
        self.posModel = QStandardItemModel()
        self.posModel.setHorizontalHeaderLabels(["序号", "着法", '*', "云库分", '引擎分'])
        self.posView.setModel(self.posModel)
        self.posView.selectionModel().selectionChanged.connect(self.onSelectionChanged)

        self.posView.setStyleSheet("""
                QTableView {
                    outline: 0;                          /* 去掉虚线框 */
                    gridline-color: #d0d0d0;
                    background-color: #ffffff;
                    alternate-background-color: #f8f9fa;
                }
                QTableView::item {
                    padding: 0px 4px;
                }
                QTableView::item:selected {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                stop:0 #3399ff, stop:1 #1e88e5);
                    color: white;
                }
                /* 关键：失去焦点时依然保持高亮！ */
                QTableView::item:selected:!active {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                                stop:0 #3399ff, stop:1 #1e88e5);
                    color: white;
                }
            """)       

        self.annotationView = QTextEdit()
        self.annotationView.readOnly = True
        
        self.branchView = QListWidget(self)

        self.vsplitter = QSplitter(Qt.Vertical)
        self.vsplitter.addWidget(LabelWidget('注释', self.annotationView))
        self.vsplitter.addWidget(LabelWidget('变招列表', self.branchView))
        
        self.hsplitter = QSplitter(Qt.Horizontal)
        self.hsplitter.addWidget(self.posView)
        self.hsplitter.addWidget(self.vsplitter)
        
        self.reviewByCloudBtn = QPushButton("云库复盘")
        self.reviewByCloudBtn.setEnabled(False)
        self.reviewByEngineBtn = QPushButton("引擎复盘")
                
        self.addBookmarkBtn = QPushButton("收藏局面")
        self.addBookmarkBtn.clicked.connect(self.onAddBookmarkBtnClick)
        self.addBookmarkBookBtn = QPushButton("收藏棋谱")
        self.addBookmarkBookBtn.clicked.connect(self.onAddBookmarkBookBtnClick)
        #self.saveDbBtnBtn = QPushButton("保存到棋谱库")
        #self.saveDbBtnBtn.clicked.connect(self.onSaveDbBtnClick)

        hbox = QHBoxLayout()
        #hbox.addWidget(self.reviewByCloudBtn)
        #hbox.addWidget(self.reviewByEngineBtn)
        hbox.addWidget(self.addBookmarkBookBtn)
        hbox.addWidget(self.addBookmarkBtn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.hsplitter)
        layout.addLayout(hbox)

        self.clear()
    
    def bindBoard(self, boardPanel):
        #面板和走子历史互相绑定，减少全局变量
        self.boardPanel = boardPanel
        self.boardPanel.historyView = self

        self.boardPanel.firstBtn.clicked.connect(self.goFirst)
        self.boardPanel.lastBtn.clicked.connect(self.goLast)
        self.boardPanel.nextBtn.clicked.connect(self.goNext)
        self.boardPanel.privBtn.clicked.connect(self.goPriv)
    
    def goFirst(self):
        self.selectRow(0)
       
    def goLast(self):
        self.selectRow(self.posModel.rowCount() - 1)
       
    def goNext(self):
        self.selectRow(self.currRow + 1)
        
    def goPriv(self):
        self.selectRow(self.currRow - 1)
    
    def getGameIccsMoves(self):
        pass
        '''
        init_fen = 
        moves = []
        for item in self.viewItems[1:]:  
            position = item.data(1, Qt.UserRole)
            moves.append(position['iccs'])
        
        return (init_fen, moves)
        '''

    def selectRow(self, row):
        #代码中移动选择行
        if (row < 0) or (row >= self.posModel.rowCount()) or (row == self.currRow):
            return
        
        # 你想选中的行号（从 0 开始）
        index = self.posModel.index(row, 0)      # 取第 row 行、第 0 列的 QModelIndex
        self.posView.scrollTo(index)
        self.posView.selectRow(row)

    def onSelectionChanged(self, selected, deselected):
        #无论是手动移动还是GUI点击，都会触发到此
        indexes = self.posView.selectedIndexes()
        if not indexes:
            return

        row = indexes[0].row() 
        if row == self.currRow:
            #避免重复触发事件
            return

        self.currRow = row
        self.positionChangeSignal.emit(self.currRow)

    def getCurrPosition(self):
        return self.posList[self.currRow]
        
    def onNewPostion(self, position):
        items = [
                QStandardItem(),
                QStandardItem(),
                QStandardItem(),
                QStandardItem(),
                QStandardItem(),
            ]
        position['view'] = items
        self.posModel.appendRow(items)
        self.posList.append(position)
        
    def onUpdatePosition(self, position):
        viewItems = position['view']

        index = position['index']
        
        if index % 2 == 1:
            viewItems[0].setText(f"{index//2+1}.")

        if 'move' in position:
            move = position['move']
            viewItems[1].setText(move.to_text())
        else:
            viewItems[1].setText('==开始==')
        
        fen = position['fen']

        if not self.isShowScore:
            viewItems[2].setIcon(QIcon())
            viewItems[3].setText('')
        else: 
            if fen not in Globl.fenCache:
                viewItems[2].setIcon(QIcon())    
                viewItems[3].setText('')
            else:    
                fenInfo = Globl.fenCache[fen] 
                if (index > 0) and ('score' in fenInfo) :
                    viewItems[3].setText(str(fenInfo['score']))
                else:
                    viewItems[3].setText('')
                
                if 'diff' in fenInfo:    
                    diff = fenInfo['diff']
                    if diff > -30:
                        viewItems[2].setIcon(QIcon(":ImgRes/star.png"))
                    elif diff > -70:
                        viewItems[2].setIcon(QIcon(":ImgRes/good.png"))
                    elif diff > -100:
                        viewItems[2].setIcon(QIcon(":ImgRes/sad.png"))
                    else:
                        viewItems[2].setIcon(QIcon(":ImgRes/bad.png"))    
                else:
                    viewItems[2].setIcon(QIcon())

        header = self.posView.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)   # 序号
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) #QHeaderView.Stretch)            # 招法拉伸
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)   # 评价
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)   # 云库分
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)   # 引擎分
                    
    
    def onClearFollowBtnClick(self):
        if self.currRow < 0:
            return
        
        self.onRemoveHistoryFollow(self.currRow)
        self.removeFollowSignal.emit(self.currRow)
        
    def onRemoveHistoryFollow(self, row):
        self.posModel.setRowCount(row)
        self.posList = self.posList[:row+1]

    def contextMenuEvent(self, event):

        menu = QMenu(self)

        clearFollowAction = menu.addAction("删除后续着法")
        menu.addSeparator()
        copyFenAction =  menu.addAction("复制-FEN")
        copyFenEngineAction =  menu.addAction("复制-引擎FEN")
        #menu.addSeparator()
        copyImageAction =  menu.addAction("复制-图片")
        saveImageAction =  menu.addAction("保存图片到文件")
        menu.addSeparator()
        bookmarkPositionAction =  menu.addAction("收藏局面")
        bookmarkBookAction =  menu.addAction("收藏棋谱")
        #addToMyLibAction =  menu.addAction("保存到棋谱库")

        action = menu.exec_(self.mapToGlobal(event.pos()))

        if action == clearFollowAction:
            self.onClearFollowBtnClick()
        elif action == copyFenAction:
            self.copyFenToClipboard()
        elif action == copyFenEngineAction:
            self.copyFenEngineToClipboard()
        elif action == copyImageAction:
            self.boardPanel.copyImageToClipboard()
        elif action == saveImageAction:
            pass
            #    self.parent.saveImageToFile()
        elif action == bookmarkPositionAction:
            self.onAddBookmarkBtnClick()
        elif action == bookmarkBookAction:
            self.onAddBookmarkBookBtnClick()
        #elif action == addToMyLibAction:
        #    self.onSaveDbBtnClick()
    
    def copyFenToClipboard(self):
        pos = self.getCurrPosition()      
        clipboard = QApplication.clipboard()
        clipboard.clear()
        clipboard.setText(pos['fen'])
    
    def copyFenEngineToClipboard(self):
        pos = self.getCurrPosition()
        clipboard = QApplication.clipboard()
        clipboard.clear()
        clipboard.setText(pos['fen_engine'])

    def onAddBookmarkBtnClick(self):
        
        fen = self.curr_position['fen']

        if Globl.localBook.isFenInBookmark(fen):
            msgbox = TimerMessageBox("收藏中已经有该局面存在.", timeout = 1)
            msgbox.exec()
            return

        name, ok = QInputDialog.getText(self, getTitle(), '请输入收藏名称:', text = '' ) #self.parent.getDefaultGameName())
        if not ok:
            return

        if Globl.localBook.isNameInBookmark(name):
            msgbox = TimerMessageBox(f'收藏中已经有[{name}]存在.', timeout = 1)
            msgbox.exec()
            return

        Globl.localBook.saveBookmark(name, fen)  
        Globl.bookmarkView.updateBookmarks()

    def onAddBookmarkBookBtnClick(self):
        fen, moves = self.getGameIccsMoves()

        name, ok = QInputDialog.getText(self, getTitle(), '请输入收藏名称:', text = '') #self.parent.getDefaultGameName())
        if not ok:
            return

        if Globl.localBook.isNameInBookmark(name):
            QMessageBox.information(None, f'{getTitle()}, 收藏中已经有[{name}]存在.')
            return

        Globl.localBook.saveBookmark(name, fen, moves)
        Globl.bookmarkView.updateBookmarks()

    def setShowScore(self, yes):
        self.isShowScore = yes
    
    def setSimpleMode(self, yes): 
        if yes:
            self.hsplitter.widget(1).hide()
            self.hsplitter.refresh()

    def clear(self):
        self.posModel.setRowCount(0)
        self.currRow = -1
        
    def sizeHint(self):
        return QSize(500, 600)

    def saveSettings(self, settings):
        h_sizes = self.hsplitter.sizes()
        v_sizes = self.vsplitter.sizes()
        settings.setValue("history/h_splitter/sizes", h_sizes)
        settings.setValue("history/v_splitter/sizes", v_sizes)

    def loadSettings(self, settings):
        
        if settings.contains("history/h_splitter/sizes"):
            h_sizes = settings.value("history/h_splitter/sizes")
            if h_sizes and len(h_sizes) == 2:
                self.hsplitter.setSizes([int(size) for size in h_sizes])
        
        # 恢复垂直分割器状态
        if settings.contains("history/v_splitter/sizes"):
            v_sizes = settings.value("history/v_splitter/sizes")
            if v_sizes and len(v_sizes) == 2:
                self.vsplitter.setSizes([int(size) for size in v_sizes])

#------------------------------------------------------------------#
class DockHistoryWidget(QDockWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setObjectName("DockHistoryWidget")
        self.inner = HistoryWidget()
        self.setWidget(self.inner)
        self.setWindowTitle(self.inner.title)

#------------------------------------------------------------------#
class BoardPanelWidget(QWidget):

    def __init__(self, board):
        super().__init__()
        
        self.boardView = ChessBoardWidget(board)
        self.historyView = None

        # ---- 下部左侧按钮组 ----
        self.flipBox = QCheckBox()  #"翻转")
        self.flipBox.setIcon(QIcon(':ImgRes/up_down.png'))
        self.flipBox.setToolTip('上下翻转')
        self.flipBox.stateChanged.connect(self.onFlipBoardChanged)

        self.mirrorBox = QCheckBox()  #"镜像")
        self.mirrorBox.setIcon(QIcon(':ImgRes/left_right.png'))
        self.mirrorBox.setToolTip('左右镜像')
        self.mirrorBox.stateChanged.connect(self.onMirrorBoardChanged)
   
        self.showBestBox = QCheckBox()  #"最佳提示")
        self.showBestBox.setIcon(QIcon(':ImgRes/info.png'))
        self.showBestBox.setChecked(True)
        self.showBestBox.setToolTip('提示最佳走法')
        self.showBestBox.stateChanged.connect(self.onShowBestMoveChanged)
    
        #self.showScoreBox = QCheckBox()  
        #self.showScoreBox.setIcon(QIcon(':ImgRes/info.png'))
        #self.showScoreBox.setChecked(True)
        #self.showScoreBox.setToolTip('显示走子得分（红优分）')
        #self.showScoreBox.stateChanged.connect(self.onShowScoreChanged)
        
        # 2. 下部按钮工具栏
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(10, 5, 10, 5)
        toolbar_layout.setSpacing(10)
        toolbar_layout.addWidget(self.flipBox)
        toolbar_layout.addWidget(self.mirrorBox)
        toolbar_layout.addWidget(self.showBestBox)
        #toolbar_layout.addWidget(self.showScoreBox)
        #toolbar_layout.addWidget(self.copyBtn)

        # ---- 下部右侧按钮组 ----
        self.firstBtn = QPushButton(self.style().standardIcon(QStyle.SP_ArrowUp), '')
        self.lastBtn = QPushButton(self.style().standardIcon(QStyle.SP_ArrowDown), '')
        self.nextBtn = QPushButton(self.style().standardIcon(QStyle.SP_ArrowForward), '')
        self.privBtn = QPushButton(self.style().standardIcon(QStyle.SP_ArrowBack), '')
 
        toolbar_layout.addStretch()         
        toolbar_layout.addWidget(self.firstBtn)
        toolbar_layout.addWidget(self.privBtn)
        toolbar_layout.addWidget(self.nextBtn)
        toolbar_layout.addWidget(self.lastBtn)
        
        #leftView = QWidget()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.boardView, stretch=1)
        layout.addLayout(toolbar_layout)
    
    def copyFrom(self, other):
        self.boardView.copyFrom(other.boardView)
        self.flipBox.setChecked(other.flipBox.isChecked())
        self.mirrorBox.setChecked(other.mirrorBox.isChecked())
        self.showBestBox.setChecked(other.showBestBox.isChecked())

    def copyFenToClipboard(self):
        fen = self.boardView._board.to_fen()        
        clipboard = QApplication.clipboard()
        clipboard.clear()
        clipboard.setText(fen)
    
    def copyImageToClipboard(self):
        pixmap = self.boardView.getImage()
        clipboard = QApplication.clipboard()
        clipboard.clear()
        clipboard.setPixmap(pixmap)
    
    def saveImageToFile(self, file_name):
        pixmap = self.boardView.getImage()
        pixmap.save(file_name)
    
    def onFlipBoardChanged(self, state):
        self.boardView.setFlipBoard(state)

    def onMirrorBoardChanged(self, state):
        self.boardView.setMirrorBoard(state)
   
    def onShowBestMoveChanged(self, state):
        self.boardView.setShowBestMove((Qt.CheckState(state) == Qt.Checked))
    
    #def onShowScoreChanged(self, state):
    #    self.historyView.setShowScore((Qt.CheckState(state) == Qt.Checked))

 
    def saveSettings(self, settings):
        settings.setValue("flip", self.flipBox.isChecked())
        settings.setValue("mirror", self.mirrorBox.isChecked())
        settings.setValue("showBest", self.showBestBox.isChecked())
        #settings.setValue("showScore", self.showScoreBox.isChecked())

    def loadSettings(self, settings):
        flip = settings.value("flip", False, type=bool)
        self.flipBox.setChecked(flip)
        mirror = settings.value("mirror", False, type=bool)
        self.mirrorBox.setChecked(mirror)
        showBest = settings.value("showBest", True, type=bool)
        self.showBestBox.setChecked(showBest)
        #showScore = settings.value("showScore", True, type=bool)
        #self.showScoreBox.setChecked(showScore)
        #cloudMode = settings.value("cloudMode", True, type=bool)
        
#------------------------------------------------------------------#
class MoveListDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("分支查看")
        self.resize(1000, 700)

        self.board = ChessBoard()

        # 主布局：上下
        main_layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)

        self.boardPanel = BoardPanelWidget(self.board) 
        self.boardPanel.copyFrom(Globl.boardPanel)

        self.historyView = HistoryWidget()
        self.historyView.setSimpleMode(True)
        self.historyView.bindBoard(self.boardPanel)

        splitter.addWidget(self.boardPanel)
        splitter.addWidget(self.historyView)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter, stretch=1)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch() 

        close_btn = QPushButton("关闭")
        close_btn.setFixedWidth(120)
        close_btn.clicked.connect(self.close)
        bottom_layout.addWidget(close_btn)

        main_layout.addLayout(bottom_layout)

    def shouMoves(self, fen, step_index, iccsList):
        self.board.from_fen(fen)
        board = self.board.copy()
        position = {
                'fen': fen,
                'fen_engine': fen,
                'index': step_index,
                'move_color': board.move_player.color
        }
        self.historyView.onNewPostion(position)
        
        for index, iccs in enumerate(iccsList):
            move = board.move_iccs(iccs)
            board.next_turn()
            curr_fen = board.to_fen()
            position = {
                'fen': curr_fen,
                'fen_engine': curr_fen,
                'move': move,
                'index': step_index + index + 1,
                'move_color': board.move_player.color
            }
            self.historyView.onNewPostion(position) 
        
        self.exec_()
            
#------------------------------------------------------------------#
class EngineWidget(QDockWidget):

    def __init__(self, parent, engineMgr):

        super().__init__("引擎", parent)    
        self.setObjectName("EngineWidget")
        
        self.dockedWidget = QWidget(self)
        self.setWidget(self.dockedWidget)
        
        self.parent = parent
        self.engineManager = engineMgr

        Globl.gameManager.game_mode_changed_signal.connect(self.onGameModeChanged)
        Globl.gameManager.review_mode_changed_signal.connect(self.onReviewModeChanged)

        self.goMode = 'deep'
        self.gameMode = None
        self.engineFightLevel = 20
        
        self.MAX_MEM = 5000
        self.MAX_THREADS = os.cpu_count()
        
        self.params = {}
        
        self.params['param.ScoreType'] = 'PawnValueNormalized'
        self.params['param.Repetition Rule'] = 'ChineseRule'
        self.params['param.Ponder']  = False
        self.params["param.Threads"] = self.getDefaultThreads()
        self.params["param.Hash"]    = self.getDefaultMem()
        
        self.params["deep.UCI_LimitStrength"] = False #不参与编辑
        self.params["deep.MultiPV"] = 1
                     
        self.params["go.deep.depth"]    = 25
        self.params["go.deep.movetime"] = 0
            
        self.params["quick.UCI_LimitStrength"] = False #不参与编辑
        self.params["quick.MultiPV"] = 1  
        self.params["go.quick.depth"]    = 16
        self.params["go.quick.movetime"] = 1

        self.params["fight.UCI_LimitStrength"] = True #不参与编辑
        self.params["fight.UCI_Elo"]     = 1350
        self.params["go.fight.depth"]    = 15
        self.params["go.fight.movetime"] = 0
        self.params["fight.MultiPV"]     = 1 #不参与编辑
        

        hbox = QHBoxLayout()

        self.engineLabel = QLabel()
        self.engineLabel.setAlignment(Qt.AlignCenter)
        
        '''
        self.DepthSpin = QSpinBox()
        self.DepthSpin.setRange(0, 100)
        self.DepthSpin.setValue(22)
        self.moveTimeSpin = QSpinBox()
        self.moveTimeSpin.setRange(0, 100)
        self.moveTimeSpin.setValue(0)

        self.threadsSpin = QSpinBox()
        self.threadsSpin.setSingleStep(1)
        self.threadsSpin.setRange(1, self.MAX_THREADS)
        self.threadsSpin.setValue(self.getDefaultThreads())
        self.threadsSpin.valueChanged.connect(self.onThreadsChanged)
        
        
        self.skillLevelSpin = QSpinBox()
        self.skillLevelSpin.setSingleStep(1)
        self.skillLevelSpin.setRange(1, 20)
        self.skillLevelSpin.setValue(20)
        self.skillLevelSpin.valueChanged.connect(self.onSkillLevelChanged)
        '''

        self.multiPVSpin = NumEdit(1, min_value = 1, max_value = 8)
        #self.multiPVSpin.setSingleStep(1)
        #self.multiPVSpin.setRange(1, 7)
        #self.multiPVSpin.setValue(1)
        self.multiPVSpin.valueChanged.connect(self.onMultiPVChanged)
 
        #group_box = QGroupBox("请选择模式:")
        
        # 创建单选按钮
        self.fastModeBtn = QRadioButton("快速")
        self.preciseModeBtn = QRadioButton("精准")
        self.fastModeBtn.setChecked(True)
        self.fastModeBtn.toggled.connect(self.onModeSelected)
        self.preciseModeBtn.toggled.connect(self.onModeSelected)

        self.redBox = QCheckBox("执红")
        self.blackBox = QCheckBox("执黑")
        self.analysisBox = QCheckBox("局面分析")
        self.configBtn = QPushButton("设置")
        self.configBtn.setEnabled(False)

        self.reviewBtn = QPushButton("复盘分析")
        
        self.configBtn.clicked.connect(self.onConfigEngine)
        self.redBox.stateChanged.connect(self.onRedBoxChanged)
        self.blackBox.stateChanged.connect(self.onBlackBoxChanged)
        self.analysisBox.stateChanged.connect(self.onAnalysisBoxChanged)

        hbox.addWidget(self.configBtn, 0)

        '''
        hbox.addWidget(QLabel('深度:'), 0)
        hbox.addWidget(self.DepthSpin, 0)
        hbox.addWidget(QLabel(' 步时(秒):'), 0)
        hbox.addWidget(self.moveTimeSpin, 0)
        hbox.addWidget(QLabel(' 级别:'), 0)
        hbox.addWidget(self.skillLevelSpin, 0)
        '''
        #hbox.addWidget(QLabel(' 线程:'), 0)
        #hbox.addWidget(self.threadsSpin, 0)
        
        hbox.addWidget(self.fastModeBtn, 0)
        hbox.addWidget(self.preciseModeBtn, 0)
        
        hbox.addWidget(QLabel('分支:'), 0)
        hbox.addWidget(self.multiPVSpin, 0)
        
        hbox.addWidget(QLabel('   '), 0)
        hbox.addWidget(self.redBox, 0)
        hbox.addWidget(self.blackBox, 0)
        hbox.addWidget(self.engineLabel, 2)
        hbox.addWidget(self.reviewBtn, 0)
        hbox.addWidget(self.analysisBox, 0)
        
        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        self.dockedWidget.setLayout(vbox)

        self.posView = QTreeWidget()
        self.posView.setColumnCount(1)
        self.posView.setHeaderLabels(["深度", "分支", "红优分", "着法", "后续"])
        self.posView.setColumnWidth(0, 80)
        self.posView.setColumnWidth(1, 40)
        self.posView.setColumnWidth(2, 70)
        self.posView.setColumnWidth(3, 220)
        self.posView.setColumnWidth(4, 380)
        #self.posView.itemSelectionChanged.connect(self.onBranchSelectionChanged)

        vbox.addWidget(self.posView)

        self.branchs = {}
    
    
    def getGoParams(self):

        params = {}
        
        if self.gameMode == GameMode.EngineAssit:
            prefix = f'go.{self.goMode}'
            
        elif self.gameMode == GameMode.EngineFight:
            prefix = 'go.fight'
        elif self.gameMode == GameMode.EngineOnline:
            prefix = 'go.online'
        else:
            prefix = 'go'
            
        name = f'{prefix}.depth'    
        if self.params[name] > 0:
            params['depth'] = self.params[name]
        
        name = f'{prefix}.movetime'    
        if self.params[name] > 0: 
            params['movetime'] = int(self.params[name] * 1000)
        
        return params 

    def onEngineReady(self, engine_id, name, engine_options):
        self.setWindowTitle(f'引擎 {name}')
        self.params['EnginePath'] = self.parent.config['MainEngine']['engine_exec']
        self.params['EngineType'] = self.parent.config['MainEngine']['engine_type']
        self.configBtn.setEnabled(True)
        
    def applyParams(self):
        
        #设置各模式通用参数
        self.applyParamsWithPrefix(['param',])
        
        #设置各模式定制参数
        if self.gameMode == GameMode.EngineAssit:
            self.applyParamsWithPrefix([self.goMode,])
        elif self.gameMode == GameMode.EngineFight:
            self.applyParamsWithPrefix(['fight',])
        elif self.gameMode == GameMode.EngineOnline:
            self.applyParamsWithPrefix(['online',])
            
    def applyParamsWithPrefix(self, prefixs):
        prefix = f"{'.'.join(prefixs)}." 

        for key, value in self.params.items():
            if not key.startswith(prefix):
                continue
            opKey = key[len(prefix):]    
            self.engineManager.setOption(opKey, value)
         
    def onGameModeChanged(self, gameMode, oldMode):
        
        self.gameMode = gameMode
        
        #引擎尚未就绪则不发送命令
        if not self.engineManager.isReady:
            return

        if gameMode in [GameMode.EngineAssit, gameMode.EngineFight, gameMode.EngineOnline]:
            self.analysisBox.setChecked(True)
            
        elif gameMode == GameMode.EngineEndGame:
            self.redBox.setChecked(False)
            self.blackBox.setChecked(True)
            self.analysisBox.setChecked(False)
       
        self.setMultiPV()
        self.applyParams()

    def onReviewBegin(self, mode):
        self.onReviewModeChanged(mode, Stage.Begin)
    
    def onReviewEnd(self, mode):
        self.onReviewModeChanged(mode, Stage.End)

    def onReviewModeChanged(self, mode, stage):        
        
        if stage == Stage.Begin:
            self.savedCheckState = self.analysisBox.isChecked()
            self.redBox.setEnabled(False)
            self.blackBox.setEnabled(False)
            self.analysisBox.setEnabled(False)
            
            if mode == ReviewMode.ByEngine:
                self.analysisBox.setChecked(True)
                
            elif mode == ReviewMode.ByCloud:
                self.analysisBox.setChecked(False)
        
        elif stage == Stage.End:
            self.redBox.setEnabled(True)
            self.blackBox.setEnabled(True)
            self.analysisBox.setEnabled(True)
            
            self.analysisBox.setChecked(self.savedCheckState)
            
    def onConfigEngine(self):  
        dlg = EngineConfigDialog(self.parent)
        ok = dlg.config(self.params)
        if ok:
            self.applyParams()
        
    def onModeSelected(self):
        
        if self.fastModeBtn.isChecked():
            self.goMode = 'quick'
        else:
            self.goMode = 'deep'
    
    def setMultiPV(self):
        if self.gameMode == GameMode.EngineAssit:
            v = self.params[f"{self.goMode}.MultiPV"]    
            self.multiPVSpin.setValue(v)

    def onMultiPVChanged(self, state):
        
        v = self.multiPVSpin.value()
        
        if self.gameMode == GameMode.EngineAssit:
            self.engineManager.stopThinking()
            self.clear()
            self.params[f"{self.goMode}.MultiPV"] = v    
            self.engineManager.setOption('MultiPV', v)
        
            self.engineManager.redoThinking()
            
    def onRedBoxChanged(self, state):
        
        red_checked = self.redBox.isChecked()
        self.parent.enginePlayColor(self.engineManager.id, cchess.RED, red_checked)
        
        if self.gameMode in [GameMode.EngineFight,]:
            self.blackBox.setChecked(not red_checked)
        elif self.gameMode in [GameMode.EngineAssit,]:
            self.analysisBox.setChecked(True)

    def onBlackBoxChanged(self, state):

        black_checked = self.blackBox.isChecked()
        self.parent.enginePlayColor(self.engineManager.id, cchess.BLACK, black_checked)
        
        if self.gameMode in [GameMode.EngineFight, ]:
            red_checked = self.redBox.isChecked()
            if red_checked == black_checked:
                self.redBox.setChecked(not black_checked)
        elif self.gameMode in [GameMode.EngineAssit,]:
            self.analysisBox.setChecked(True)
        
    def onAnalysisBoxChanged(self, state):
        self.parent.enginePlayColor(self.engineManager.id, 0, (Qt.CheckState(state) == Qt.Checked))
        
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        viewBranchAction = menu.addAction("分支推演")
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == viewBranchAction:
            self.onViewBranch()
    
    def onViewBranch(self):
        item = self.posView.currentItem()
        if not item:
            return

        branchId = item.data(0, Qt.UserRole)
        iccsList = self.branchs[branchId]
        self.parent.onViewBranch(iccsList)
        
        
    def onEngineMoveInfo(self, fenInfo):
        
        if "moves" not in fenInfo:
            return

        iccs_str = ','.join(fenInfo["moves"])
        fenInfo['iccs_str'] = iccs_str

        fen = fenInfo['fen']
        
        ok, moves_text = getStepsTextFromFenMoves(fen, fenInfo["moves"])
        if not ok:
            #logging.warning(f'{fen}, moves {fenInfo["moves"]}')
            return
        
        fenInfo['move_1'] = ','.join(moves_text[:2])
        fenInfo['move_2'] = ','.join(moves_text[2:])
        
        pv_index = fenInfo['multipv']
        self.branchs[pv_index] = fenInfo

        found = False
        for i in range(self.posView.topLevelItemCount()):
            it = self.posView.topLevelItem(i)
            it_pv = it.data(0, Qt.UserRole)
            if pv_index == it_pv:
                found = True
                break   

        if not found:
            it = QTreeWidgetItem(self.posView)
        
        self.updateNode(it, fenInfo)
        self.posView.sortItems(1, Qt.AscendingOrder)
        
    def updateNode(self, it, fenInfo):

        depth = int(fenInfo['depth'])
        it.setText(0, f'{depth:02d}')
        pv_index = fenInfo['multipv']
        it.setText(1, str(pv_index))
        it.setData(0, Qt.UserRole, pv_index)
        
        #print(depth, pv_index, fenInfo['move_text'])

        #着法及分数显示只受analysisBox控制，这样在fight模式下也不会看到分数，减少分心        
        if self.analysisBox.isChecked():
            move_color = fenInfo['color']
            mate = fenInfo.get('mate', None)
            if mate is not None:
                if mate == 0:
                    it.setText(2, '杀死')
                else:
                    red_killer = True if move_color == cchess.RED else False
                    if mate < 0:
                        red_killer = not red_killer
                    killer = '红优' if red_killer else '黑优'
                        
                    it.setText(2, f'{killer}{abs(mate)}步杀')
                
            else: 
                score = fenInfo['score']
                #换算到红方分
                if move_color == cchess.BLACK:     
                    score = -score
                it.setText(2, str(score))

            it.setText(3, fenInfo['move_1'])
            it.setText(4, fenInfo['move_2'])

        #it.setData(0, Qt.UserRole, fenInfo['iccs_str'])

    def getDefaultMem(self):
        mem = getFreeMem()/2
        m_count = int((mem // 100 ) * 100)
        if m_count > self.MAX_MEM: 
            m_count = self.MAX_MEM
        
        return m_count

    def getDefaultThreads(self):
        return self.MAX_THREADS // 2

    def saveSettings(self, settings):
        for key, value in self.params.items():
            settings.setValue(key, value)
        
        settings.setValue("engineRed", self.redBox.isChecked()) 
        settings.setValue("engineBlack", self.blackBox.isChecked()) 
        settings.setValue("engineAnalysis", self.analysisBox.isChecked()) 

    def loadSettings(self, settings):
        for key, old_value in self.params.items():
            new_value = settings.value(key, old_value)
            if new_value in ['true', 'false']:
                self.params[key] = True if new_value == 'true' else False  
            else:
                self.params[key] = new_value

        self.redBox.setChecked(settings.value("engineRed", False, type=bool))
        self.blackBox.setChecked(settings.value("engineBlack", False, type=bool))
        self.analysisBox.setChecked(settings.value("engineAnalysis", False, type=bool))

    def clear(self):
        self.posView.clear()
        self.branchs = {}

    def sizeHint(self):
        return QSize(400, 100)

#------------------------------------------------------------------#
"""
class MoveDbWidget(QDockWidget):
    selectMoveSignal = pyqtSignal(dict)

    def __init__(self, parent):
        super().__init__("我的棋谱库", parent)
        
        self.setObjectName("我的棋谱库")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.parent = parent
        
        self.moveListView = QTreeWidget()
        self.moveListView.setColumnCount(1)
        self.moveListView.setHeaderLabels(["备选着法", "红优分", '', '备注'])
        self.moveListView.setColumnWidth(0, 80)
        self.moveListView.setColumnWidth(1, 60)
        self.moveListView.setColumnWidth(2, 1)
        self.moveListView.setColumnWidth(3, 20)

        self.moveListView.clicked.connect(self.onSelectIndex)
        
        self.importFollowMode = False

        self.setWidget( self.moveListView)

    def clear(self):
        self.moveListView.clear()
        
    def contextMenuEvent(self, event):

        menu = QMenu(self)
        importFollowAction = menu.addAction("导入分支(单选)")
        #importAllFollowAction = menu.addAction("导入分支(全部)")
        menu.addSeparator()
        delBranchAction = menu.addAction("!删除该分支!")
        #cleanAction = menu.addAction("***清理非法招数***")

        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == importFollowAction:
            self.onImportFollow()
        elif action == delBranchAction:
            self.onDeleteBranch()
        #elif action == cleanAction:
        #    self.onCleanMoves()

    def onImportFollow(self):
        self.importFollowMode = True
        self.onSelectIndex()
    
    def onCleanMoves(self):
        bad_moves = []
        records = Globl.localbookStore.getAllBookMoves()
        for it in records:
            fen = it['fen']
            board = ChessBoard(fen)
            for act in it['actions']:
                m = board.is_valid_iccs_move(act['iccs'])
                if m is None:
                    bad_moves.append((fen, act['iccs']))
        for fen, iccs in bad_moves:
            print(len(records), fen, iccs)
            Globl.localbookStore.delBookMoves(fen, iccs)

    def onDeleteBranch(self):
        item = self.moveListView.currentItem()
        fenInfo = item.data(0, Qt.UserRole)
        fen = fenInfo['fen']
        iccs = fenInfo['iccs']
        board = ChessBoard()
        todoList = [(fen, iccs)]
        todoListNew = []
        branchs = 1
        delFens = OrderedDict()
        if self.moveListView.topLevelItemCount() == 1:
            delFens[fen] = None
        else:
             delFens[fen] = iccs
            
        while len(todoList) > 0:
            for fen, iccs in todoList:
                board.from_fen(fen)
                move = board.move_iccs(iccs)
                if move is None:
                    raise Exception('invalid move')
                board.next_turn()
                
                new_fen = board.to_fen()
                record = Globl.localbookStore.getAllBookMoves(new_fen)
                if len(record) > 0:
                    #只删除有后续着法记录
                    if new_fen not in delFens:
                        delFens[new_fen] = None
                for it in record:
                    #assert it['fen'] == new_fen
                    actions = it['actions']
                    if len(actions) > 1:
                        branchs = branchs + len(actions) - 1
                    for act in actions:
                        #print(act)
                        todoListNew.append((new_fen, act['iccs']))
                        
            if (len(todoListNew) == 0):
                break
            todoList = todoListNew
            todoListNew = []
                  
        ok = QMessageBox.question(self, getTitle(), f"此局面后续有{branchs}个分支，{len(delFens)}个局面, 您确定要全部删除吗?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ok == QMessageBox.Yes:
            for fen, iccs in delFens.items():
                Globl.localbookStore.delBookMoves(fen, iccs)
            QMessageBox.information(self, getTitle(), "已删除。")
            self.onPositionChanged(self.curr_pos, is_new = False)
            
    def onImportFollowContinue(self):
        if self.moveListView.topLevelItemCount() != 1:
            self.importFollowMode = False
            return
        item = self.moveListView.topLevelItem(0)
        self.moveListView.setCurrentItem(item, 0)
        self.onSelectIndex()
    
    def onPositionChanged(self, position, is_new):  

        def key_func(it):
            try:
                return int(it['score'])
            except ValueError:
                return 0
            except KeyError:
                return 0
            except  TypeError:
                return 0

        self.curr_pos = position
        fen = position['fen']
        
        self.clear()
        board = ChessBoard(fen)
        book_moves = []

        ret = Globl.localbook.getMoves(fen)
        '''
        if len(ret) == 0:
            return
        elif len(ret) > 1:
            raise Exception(f'database error: {fen}, {ret}')

        it = ret[0]
        for act in it['actions']:
            act['fen'] = fen
            m = board.copy().move_iccs(act['iccs'])
            if m is None:
                continue
            act['text'] = m.to_text()   
            new_fen = m.board_done.to_fen()

            #if 'score' in act:
            #    del act['score']
            
            if new_fen in Globl.fenCache:
                fenInfo = Globl.fenCache[new_fen]
                if 'score' in fenInfo:
                    act['score'] = fenInfo['score']
            book_moves.append(act)
            
        is_reverse  = True if board.get_move_color() == cchess.RED else False        
        book_moves.sort(key=key_func, reverse = is_reverse)
        
        self.updateBookMoves(book_moves)
        '''
        
    def updateBookMoves(self, book_moves):
        self.moveListView.clear()
        self.position_len = len(book_moves)
        for act in book_moves:
            item = QTreeWidgetItem(self.moveListView)

            item.setText(0, act['text'])

            if 'score' in act:
                item.setText(1, str(act['score']))
                item.setTextAlignment(1, Qt.AlignRight)

            #item.setText(2, str(act['count']))
            if 'memo' in act:
                item.setText(3, act['memo'])

            item.setData(0, Qt.UserRole, act)

        if self.importFollowMode:
            if self.position_len == 1:
                QTimer.singleShot(500, self.onImportFollowContinue)
            else:
                self.importFollowMode = False
       
    def onSelectIndex(self):
        item = self.moveListView.currentItem()
        if not item:
            return
        act = item.data(0, Qt.UserRole)
        self.selectMoveSignal.emit(act)

    def sizeHint(self):
        return QSize(150, 500)
"""

#------------------------------------------------------------------#
class BoardActionsWidget(QDockWidget):
    selectMoveSignal = pyqtSignal(dict)

    def __init__(self, parent):
        super().__init__("棋谱库", parent)
        self.setObjectName("棋谱库")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.importFollowMode = False
        self.parent = parent         
        self.actionsView = QTreeWidget()

        self.actionsView.setColumnCount(1)
        self.actionsView.setHeaderLabels(['MK', "备选着法", "得分", ''])
        self.actionsView.setColumnWidth(0, 40)
        self.actionsView.setColumnWidth(1, 120)
        self.actionsView.setColumnWidth(2, 80)
        self.actionsView.setColumnWidth(3, 10)
        
        self.actionsView.clicked.connect(self.onSelectIndex)
        
        self.setWidget( self.actionsView)

    def clear(self):
        self.actionsView.clear()
        self.update()
        
    def contextMenuEvent(self, event):
        return
        menu = QMenu(self)
        importBestAction = menu.addAction("导入最优分支")
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == importBestAction:
            self.onImportBest()

    def onImportBest(self):
        #self.importFollowMode = True
        #self.onSelectIndex(0)
        pass
        
    def updateActions(self, actions):
        self.actionsView.clear()
        for act in actions.values():
            item = QTreeWidgetItem(self.actionsView)
            
            if 'mark' in act:
                item.setText(0, act['mark'])
                item.setTextAlignment(0, Qt.AlignLeft)
            
            item.setText(1, act['text'])

            if 'score' in act:
                item.setText(2, str(act['score']))
            item.setTextAlignment(2, Qt.AlignRight)
            
            item.setData(0, Qt.UserRole, act)
        self.update()

    def onSelectIndex(self, index):
        item = self.actionsView.currentItem()
        act = item.data(0, Qt.UserRole)
        self.selectMoveSignal.emit(act)

    def sizeHint(self):
        return QSize(110, 500)

#------------------------------------------------------------------#
class EndBookWidget(QDockWidget):
    selectEndGameSignal = pyqtSignal(dict)

    def __init__(self, parent):
        super().__init__("残局库", parent)
        self.setObjectName("EndBook")
        
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.parent = parent
        
        self.dockedWidget = QWidget(self)
        self.setWidget(self.dockedWidget)

        self.bookView = QListWidget()

        # Add widgets to the layout
        self.bookCombo = QComboBox(self)
        self.bookCombo.currentTextChanged.connect(self.onBookChanged)
        self.importBtn = QPushButton("导入")
        self.importBtn.clicked.connect(self.onImportBtnClick)
        self.openBtn = QPushButton("打开")
        self.openBtn.clicked.connect(self.onOpenBtnClick)
        
        hbox = QHBoxLayout()
        hbox.addWidget(self.bookCombo, 2)
        hbox.addWidget(self.importBtn, 0)
        hbox.addWidget(self.openBtn, 0)
        
        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addWidget(self.bookView)
        self.dockedWidget.setLayout(vbox)

        self.bookView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.bookView.setAlternatingRowColors(True)
        #self.bookView.doubleClicked.connect(self.onItemDoubleClicked)
        #self.bookView.clicked.connect(self.onItemClicked)
        self.bookView.currentItemChanged.connect(self.onCurrentItemChanged)
    
    def updateBooks(self):
      
        self.currBookName = ''
        self.currBook = []
        self.currGame = None

        self.books = Globl.endbookStore.getAllEndBooks()
        self.bookCombo.clear()
        if len(self.books) > 0:
            self.bookCombo.addItems(self.books.keys())
            self.bookCombo.setCurrentIndex(0)
    
    def nextGame(self):

        if len(self.currBook) == 0:
            return
            
        if self.currGame is None :
           self.currGame = self.currBook[0]
           
        if self.currGame['ok'] is False:
            self.selectEndGameSignal.emit(self.currGame)

        index = self.currGame['index']
        while self.currGame['ok'] is True:
            if index < len(self.currBook)-1:
                index += 1
            else:
                break
            self.currGame = self.currBook[index]
        
        if self.currGame['ok'] is False:
            self.bookView.setCurrentItem(self.currGame['widget'])
            
    def updateCurrent(self, game):
        if self.currGame['fen'] != game['fen']:
            return
        self.currGame['ok'] = game['ok']
        self.updateCurrentBook()
     
    def updateCurrentBook(self):
        self.bookView.clear()
        for i, game in enumerate(self.books[self.currBookName]):
            item = QListWidgetItem()
            item.setText(game['name'])
            if game['ok'] is True:
                item.setForeground(Qt.gray)
            item.setData(Qt.UserRole, game)
            game['index'] = i
            game['widget'] = item
            self.bookView.addItem(item)
        
    def onImportBtnClick(self):
        options = QFileDialog.Options()
        #options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(
            self,
            "打开杀局谱文件",
            "",
            "杀局谱文件(*.eglib);;CSV格式文件(*.csv);;All Files (*)",
            options=options)

        if not fileName:
            return

        lib_name = Path(fileName).stem
        if Globl.endbookStore.isEndBookExist(lib_name):
            msgbox = TimerMessageBox(f"杀局谱[{lib_name}]系统中已经存在，不能重复导入。",
                                     timeout=2)
            msgbox.exec()
            return
        ext = Path(fileName).suffix.lower()
        if ext =='.eglib': 
            games = loadEglib(fileName)
            Globl.endbookStore.saveEndBook(lib_name, games)
        if ext =='.csv':  
            games = loadCsvlib(fileName)
            Globl.endbookStore.saveEndBook(lib_name, games)
                
        self.updateBooks()
        self.bookCombo.setCurrentText(lib_name)
    
    def onOpenBtnClick(self):
        pass
            
    def onBookChanged(self, book_name):

        self.bookView.clear()

        if book_name == '':
            return

        if book_name not in self.books:
            return

        self.currBookName = book_name
        self.bookCombo.setCurrentText(self.currBookName)
        self.currBook = self.books[self.currBookName]
        self.currGame = None

        self.updateCurrentBook()
        self.nextGame()

    def onCurrentItemChanged(self, current, previous):
        if current is None:
            return
        self.currGame = current.data(Qt.UserRole)
        self.selectEndGameSignal.emit(self.currGame)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        copyAction = menu.addAction("复制Fen到剪贴板")
        menu.addSeparator()
        remarkAction = menu.addAction("标记未完成")
        remarkAllAction = menu.addAction("标记全部未完成")
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == copyAction:
            QApplication.clipboard().setText(self.parent.board.to_fen())
        
        elif action == remarkAction:
            if self.currGame:
                self.currGame['ok'] = False
                Globl.endbookStore.updateEndBook(self.currGame)
            self.updateCurrentBook()
            
        elif action == remarkAllAction:
            for i, game in enumerate(self.books[self.currBookName]):
                if game['ok'] is True:
                    game['ok'] = False
                    Globl.endbookStore.updateEndBook(game)
            self.updateCurrentBook()
                
    def sizeHint(self):
        return QSize(150, 500)

    def loadSettings(self, settings):
        
        self.updateBooks()

        endBookName = settings.value("endBookName", '')
        if endBookName:
            self.onBookChanged(endBookName)

        index = settings.value("endBookIndex", -1)
        if index < 0:
            self.currGame = None
        else:    
            self.bookView.setCurrentRow(index)
        
    def saveSettings(self, settings):
        settings.setValue("endBookName", self.currBookName)
        if self.currGame:
            settings.setValue("endBookIndex", self.currGame['index'])
        else:
            settings.setValue("endBookIndex", -1)
            
#------------------------------------------------------------------#
class BookmarkWidget(QDockWidget):
    
    def __init__(self, parent):
        super().__init__("我的收藏", parent)
        self.setObjectName("我的收藏")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.parent = parent        
        self.bookmarks = []

        self.dockedWidget = QWidget(self)
        self.setWidget(self.dockedWidget)

        self.bookmarkView = QListWidget()
        self.bookmarkView.doubleClicked.connect(self.onDoubleClicked)

        vbox = QVBoxLayout()
        vbox.addWidget(self.bookmarkView)
        self.dockedWidget.setLayout(vbox)

        self.bookmarkView.setEditTriggers(QAbstractItemView.NoEditTriggers)
    
        self.curr_item = None

        self.updateBookmarks()

    def updateBookmarks(self):
        
        self.bookmarkView.clear()
        self.bookmarks = sorted(Globl.localBook.getAllBookmarks(), key = lambda x: x['name'])

        for i, it in enumerate(self.bookmarks):
            item = QListWidgetItem()
            item.setText(it['name'])
            item.setData(Qt.UserRole, it)
            self.bookmarkView.addItem(item)
    
    def addQuickBooks(self, books):    
        for i,(name, moves_str) in enumerate(books.items()):
            item = QListWidgetItem()
            item.setText(name)
            position = {}
            position['name'] = name
            position['fen'] = cchess.FULL_INIT_FEN
            position['moves'] = moves_str.split(',')
            item.setData(Qt.UserRole, position)
            self.bookmarkView.addItem(item)
        
    def contextMenuEvent(self, event):

        menu = QMenu(self)

        removeAction = menu.addAction("删除")
        renameAction = menu.addAction("改名")
        action = menu.exec_(self.mapToGlobal(event.pos()))

        item = self.bookmarkView.currentItem()
        old_name = item.text()
        fen = item.data(Qt.UserRole)['fen']

        if action == removeAction:
            Globl.localBook.removeBookmark(old_name)
            self.updateBookmarks()
        elif action == renameAction:
            new_name, ok = QInputDialog.getText(self,
                                                getTitle(),
                                                '请输入新名称:',
                                                text=old_name)
            if ok:
                if Globl.localBook.isNameInBookmark(new_name):
                    msgbox = TimerMessageBox(f'收藏中已经有[{new_name}]存在.', timeout = 1)
                    msgbox.exec()
                else:
                    if not Globl.localBook.changeBookmarkName(old_name, new_name):
                        msgbox = TimerMessageBox(f'[{old_name}] -> [{new_name}] 改名失败.', timeout = 2)
                        msgbox.exec()    
                    else:
                        self.updateBookmarks()

    def onBookmarkChanged(self, book_name):
        pass

    def onDoubleClicked(self):
        item = self.bookmarkView.currentItem()
        position = item.data(Qt.UserRole)
        name = item.text()
        #print(position)
        self.parent.loadBookmark(name, position)

    def onSelectIndex(self, index):
        self.curr_item = self.bookmarkView.itemFromIndex(index)

    def sizeHint(self):
        return QSize(150, 500)

#------------------------------------------------------------------#
class GameLibWidget(QDockWidget):
    
    def __init__(self, parent):
        super().__init__("棋库", parent)
        self.setObjectName("GameLibWidget")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.parent = parent        
        self.gameLib = []
        
        self.dockedWidget = QWidget(self)
        self.setWidget(self.dockedWidget)

        self.gamesView = QListWidget()
        self.gamesView.doubleClicked.connect(self.onDoubleClicked)

        vbox = QVBoxLayout()
        #vbox.addLayout(hbox)
        vbox.addWidget(self.gamesView)
        self.dockedWidget.setLayout(vbox)

        #self.gamesModel = QStandardItemModel(self.gamesView)
        #self.gamesView.setModel(self.gamesModel)
        self.gamesView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        #self.gamesView.clicked.connect(self.onSelectIndex)

        #self.curr_item = None


    def updateGameLib(self, gamelib):
        #self.
        self.gamelib = gamelib
        games = gamelib['games']   

        self.gamesView.clear()
        
        for i, it in enumerate(games):
            item = QListWidgetItem()
            item.setText(it.info['title'])
            item.setData(Qt.UserRole, it)
            self.gamesView.addItem(item)
    
    def onDoubleClicked(self):
        item = self.gamesView.currentItem()
        game = item.data(Qt.UserRole)
        name = f'{self.gamelib["name"]}-{game.info["title"]}'
        self.parent.loadBookGame(name, game)

    def onSelectIndex(self, index):
        self.curr_item = self.gamesView.itemFromIndex(index)

    def sizeHint(self):
        return QSize(150, 500)

#------------------------------------------------------------------#



