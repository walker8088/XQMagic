# -*- coding: utf-8 -*-
import ctypes
import logging
import os
import platform
import sys
import threading
import time
import traceback
from collections import OrderedDict
from configparser import ConfigParser
from enum import Enum, auto
from pathlib import Path

import cchess
from cchess import ChessBoard, EngineErrorException, Game
from PyQt5.QtCore import QByteArray, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtWidgets import (
    QAction,
    QActionGroup,
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QStyle,
    QWidget,
)

from . import Globl
from .BoardWidgets import DEFAULT_SKIN
from .CloudDB import CloudDB
from .Detector import ChessboardDetector
from .Dialogs import (
    EngineConfigDialog,
    PositionEditDialog,
)
from .Ecco import getBookEcco
from .Engine import EngineManager
from .LocalDB import LocalBook, MasterBook, OpenBookPF, OpenBookYfk
from .Online import OnlineDialog, OnlineManager
from .Storage import PuzzleStore
from .TestRunner import TestRunnerWidget
from .Utils import (
    ALTER_BEST_CLOUD,
    ALTER_BEST_ENGINE,
    BEST_MOVE_TOLERANCE,
    GameMode,
    QGameManager,
    TimerMessageBox,
    getStepsFromFenMoves,
    getTitle,
    trim_fen,
)
from .Version import release_version
from .Widgets import (
    BoardActionsWidget,
    BoardPanelWidget,
    BookmarkWidget,
    DockHistoryWidget,
    PuzzleWidget,
    EngineWidget,
    GameLibWidget,
    MoveListDialog,
)

"""
# 设置全局默认字体
font = QFont("Microsoft YaHei", 16)  # 字体名、字号（可选加粗：font.setBold(True)）
font.setBold(True)
app.setFont(font, "QPushButton")  # 或指定类：app.setFont(font, "QPushButton")
"""


# 路径常量
GAME_DIR = Path("Game")
ENGINE_DIR = Path("Engine")
SKINS_DIR = Path("Skins")
SOUND_DIR = Path("Sound")


# -----------------------------------------------------#
class ActionType(Enum):
    MOVE = auto()
    CAPTRUE = auto()
    CHECKING = auto()
    MATE = auto()


# -----------------------------------------------------#

GAME_FILE_TYPES = [".xqf", ".pgn", ".cbr"]
GAME_LIB_TYPES = [".cbl"]
GAME_TYPES_ALL = GAME_FILE_TYPES + GAME_LIB_TYPES


# -----------------------------------------------------#
class MainWindow(QMainWindow):
    initGameSignal = pyqtSignal()
    # moveBeginSignal = pyqtSignal()
    # moveEndSignal = pyqtSignal()
    # newPositionSignal = pyqtSignal()
    changePositionSignal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()

        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAcceptDrops(True)

        self.setWindowIcon(QIcon(":ImgRes/app.ico"))

        if platform.system() == "Windows":
            # 在Windows状态栏上正确显示图标
            myappid = "mycompany.myproduct.subproduct.version"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

        Globl.gameManager = QGameManager()
        Globl.gameManager.game_mode_changed_signal.connect(self.onGameModeChanged)

        self.readConfig()

        gamePath = GAME_DIR
        gamePath.mkdir(exist_ok=True)

        self.openBook = MasterBook()
        self.openBook.open(GAME_DIR / "masterbook.db")

        Globl.puzzleStore = PuzzleStore(GAME_DIR / "puzzles.json")

        Globl.localBook = LocalBook()
        Globl.localBook.open(GAME_DIR / "localbook.db")

        Globl.engineManager = EngineManager(self, id=1)

        self.onlineManager = OnlineManager(self)
        self.onlineManager.load_schema_file(GAME_DIR / "online.json")

        self.board = ChessBoard()
        self.changePositionSignal.connect(self.onChangePosition)

        self.boardPanel = BoardPanelWidget(self.board)
        self.setCentralWidget(self.boardPanel)

        self.boardView = self.boardPanel.boardView  # ChessBoardWidget(self.board)
        # Globl.boardView = self.boardView
        Globl.boardPanel = self.boardPanel
        self.boardView.tryMoveSignal.connect(self.onTryBoardMove)
        self.boardView.rightMouseSignal.connect(self.onBoardRightMouse)

        self.historyDoc = DockHistoryWidget(self)
        self.historyView = self.historyDoc.inner
        self.historyView.bindBoard(self.boardPanel)

        self.historyView.removeFollowSignal.connect(self.removeHistoryFollow)
        self.historyView.positionChangeSignal.connect(self.onSelectHistoryPosition)
        self.historyView.showScoreBox.stateChanged.connect(self.onShowScoreChanged)

        self.puzzleView = PuzzleWidget(self)
        self.puzzleView.setVisible(False)
        self.puzzleView.selectPuzzleSignal.connect(self.onSelectPuzzle)

        # self.moveDbView = MoveDbWidget(self)
        # self.moveDbView.selectMoveSignal.connect(self.onTryBookMove)
        self.actionsView = BoardActionsWidget(self)
        self.actionsView.selectMoveSignal.connect(self.onTryBookMove)
        self.actionsView.queryCloudBox.toggled.connect(self.onCloudModeChanged)

        self.bookmarkView = BookmarkWidget(self)
        self.bookmarkView.setVisible(False)
        Globl.bookmarkView = self.bookmarkView

        self.gamelibView = GameLibWidget(self)
        self.gamelibView.setVisible(False)

        self.engineView = EngineWidget(self, Globl.engineManager)

        self.addDockWidget(Qt.LeftDockWidgetArea, self.actionsView)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.puzzleView)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.gamelibView)
        self.addDockWidget(Qt.RightDockWidgetArea, self.historyDoc)
        # self.addDockWidget(Qt.RightDockWidgetArea, self.bookmarkView)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.engineView)

        # 内嵌的 pytest 测试运行器(默认隐藏,从"窗口"菜单打开)
        self.testRunnerView = TestRunnerWidget(self)
        self.testRunnerView.setVisible(False)
        self.addDockWidget(Qt.RightDockWidgetArea, self.testRunnerView)

        # self.snippingWidget = SnippingWidget()
        # self.snippingWidget.onSnippingCompleted = self.onSnippingCompleted

        Globl.engineManager.readySignal.connect(self.onEngineReady)
        Globl.engineManager.moveBestSignal.connect(self.onTryEngineMove)
        Globl.engineManager.moveInfoSignal.connect(self.onEngineMoveInfo)
        # Globl.engineManager.checkmate_signal.connect(self.onEngineCheckmate)

        self.skins = self.loadSkins()
        self.initSound()
        self.createActions()
        self.createMenus()
        self.createToolBars()

        Globl.detector = ChessboardDetector(ENGINE_DIR / "Detector")

        self.isQueryCloud = False
        self.lastOpenFolder = ""
        self.isNeedSave = False
        self.isRunEngine = False
        self.engineRunColor = [0, 0, 0]
        self.boardActions = OrderedDict()

        self.skin = DEFAULT_SKIN

        self.clearAll()

        self.readSettings()
        # self.loadOpenBook(self.openBookFile)
        # self.cloudQuery = MyScoreDB(self) #CloudDB(self)
        self.cloudQuery = CloudDB(self)
        self.cloudQuery.query_result_signal.connect(self.onCloudQueryResult)
        self.cloudQuery.query_error_signal.connect(self.onCloudQueryError)

        self.switchGameMode(GameMode.Free)

        ok = self.initEngine()
        if not ok:
            sys.exit(-1)

        Globl.engineManager.start()

        # 创建一个定时器，每秒触发一次
        self.timer = QTimer()
        self.timer.timeout.connect(self.onIdleTask)
        self.timer.start(1000)  # 1000毫秒

    def onIdleTask(self):
        QApplication.processEvents()  # 确保界面响应
        # self.label.setText("空闲中...")

    # -----------------------------------------------------------------------
    # 初始化
    def clearAll(self):
        self.positionList = []
        self.currPosition = None

        self.historyView.clear()
        self.engineView.clear()
        self.boardView.setViewOnly(False)
        self.boardActions = OrderedDict()

    def readConfig(self):
        if not Globl.config_file.is_file():
            QMessageBox.critical(
                self,
                f"{getTitle()}",
                f"配置文件[{Globl.config_file}]不存在，请确保该文件存在并配置正确.",
            )
            return False

        self.config = ConfigParser()
        try:
            ok = self.config.read(Globl.config_file)
        except Exception as e:
            QMessageBox.critical(
                self, f"{getTitle()}", f"打开配置文件[{Globl.config_file}]出错：{e}"
            )
            return False

    def initEngine(self):
        try:
            self.engine_type = self.config["MainEngine"]["engine_type"].lower()
            self.engine_exec = Path(self.config["MainEngine"]["engine_exec"])
        except Exception as e:
            QMessageBox.critical(
                self, f"{getTitle()}", f"配置文件[{Globl.config_file}]格式错误：{e}"
            )
            return False

        ok = Globl.engineManager.loadEngine(self.engine_exec, self.engine_type)
        if not ok:
            QMessageBox.critical(
                self,
                f"{getTitle()}",
                f"加载象棋引擎[{self.engine_exec}]出错，请确认该程序能在您的电脑上正确运行。",
            )

        return ok

        """
        try:
            engine_type = self.config['AssitEngine']['engine_type'].lower()
            engine_exec = Path(self.config['AssitEngine']['engine_exec'])
        except Exception as e:
            QMessageBox.critical(self, f'{getTitle()}', f'配置文件[{self.config_file}]格式错误：{e}')
            return False

        ok = Globl.engineManager.loadEngine(engine_exec, engine_type)
        if not ok:
            QMessageBox.critical(self, f'{getTitle()}', f'加载象棋引擎[{self.engine_exec}]出错，请确认该程序能在您的电脑上正确运行。')

        return ok
        """

    def loadOpenBook(self, file_name):
        if not file_name.is_file():
            return

        ext = file_name.suffix.lower()
        if ext == ".yfk":
            self.openBook = OpenBookYfk()
            self.openBook.open(file_name)
            logging.info(f"加载开局库：{file_name}")
            self.openBookFile = file_name
        elif ext == ".pfbook":
            self.openBook = OpenBookPF()
            self.openBook.open(file_name)
            self.openBookFile = file_name
            logging.info(f"加载开局库：{file_name}")
        else:
            self.openBook = OpenBookPF()
            logging.info("无开局库")

    def loadSkins(self):
        skins = {}
        skins["默认"] = {"Folder": None}

        skinsFolder = SKINS_DIR
        for nm in os.listdir(skinsFolder):
            name = SKINS_DIR / nm
            if name.is_dir():
                skins[nm] = {"Folder": name}
        return skins

    def loadQuickBook(self, fileName):
        quick_moves = OrderedDict()

        with open(fileName, "r", encoding="utf-8") as f:
            for line_it in f.readlines():
                line = line_it.strip()
                if not line or line.startswith("#"):
                    continue
                items = line.split(":")
                # print(len(items), line)
                if len(items) != 2:
                    logging.warning(line)
                    continue
                name, moves = items
                name = name[4:]
                quick_moves[name] = moves

        return quick_moves

    # -----------------------------------------------------------------------
    # 声音播放
    def initSound(self):
        self.soundVolume = 0
        self.player = QMediaPlayer()
        # self.audioOutput = QAudioOutput()
        # self.player.setAudioOutput(self.audioOutput)
        # self.player.errorOccurred.connect(self.onPlayError)

    def playSound(self, s_type, quickMode=False):
        if quickMode:
            return

        if self.soundVolume > 0:
            # self.player.setSource(QUrl.fromLocalFile(Path('Sound', f'{s_type}.wav')))
            self.player.setMedia(
                QMediaContent(QUrl.fromLocalFile(str(SOUND_DIR / f"{s_type}.wav")))
            )
            self.player.setVolume(self.soundVolume)
            self.player.setPosition(0)
            self.player.play()

    def onPlayError(self, error, error_string):
        logging.error(f"Sound PlayError: {error_string}")

    # -----------------------------------------------------------------------
    # 基础信息
    def getConfirm(self, msg):
        ok = QMessageBox.question(
            self, getTitle(), msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if ok == QMessageBox.Yes:
            return True
        return False

    def getDefaultGameName(self):
        if len(self.positionList) == 0:
            return "未命名"
        return f"{self.positionList[0].get('ecco', '未命名')}"

    def updateTitle(self, subText=""):
        title = f"{Globl.APP_NAME_TEXT} - {Globl.gameManager.getGameModeText()}"
        if subText:
            title = f"{title} - {subText}"

        self.setWindowTitle(title)

    def getGameIccsMoves(self):
        moves = [it["iccs"] for it in self.positionList[1:]]
        return (self.positionList[0]["fen"], moves)

    def saveGameToDB(self):
        Globl.localBook.savePositionList(self.positionList)
        self.isNeedSave = False

    # -----------------------------------------------------------------------
    # Game 相关
    def switchGameMode(self, mode):
        Globl.gameManager.setGameMode(mode)

    def onGameModeChanged(self, new_mode, old_mode):
        # if new_mode == old_mode:
        #    return

        logging.info(f"Switching to [{new_mode}]")
        self.updateTitle()

        if new_mode == GameMode.Free:
            self.doCaptureAct.setEnabled(False)
            self.myGamesAct.setEnabled(True)
            self.bookmarkAct.setEnabled(True)
            self.puzzleView.hide()
            self.actionsView.show()

            # self.showBestBox.setChecked(True)
            # self.showScoreBox.setChecked(True)

            self.openFileAct.setEnabled(True)
            self.editBoardAct.setEnabled(True)

            self.initGame(cchess.FULL_INIT_FEN)

        elif new_mode == GameMode.EngineAssit:
            self.doCaptureAct.setEnabled(False)
            self.myGamesAct.setEnabled(True)
            self.bookmarkAct.setEnabled(True)
            self.puzzleView.hide()
            self.actionsView.show()

            # self.showScoreBox.setChecked(True)
            # self.showBestBox.setChecked(True)

            self.openFileAct.setEnabled(True)
            self.editBoardAct.setEnabled(True)

            if old_mode in [
                GameMode.Puzzle,
            ]:
                self.initGame(cchess.FULL_INIT_FEN)

        elif new_mode == GameMode.EngineFight:
            self.doCaptureAct.setEnabled(False)
            self.myGamesAct.setEnabled(True)
            self.bookmarkAct.setEnabled(False)
            self.bookmarkView.hide()
            self.puzzleView.hide()
            self.gamelibView.hide()
            self.actionsView.hide()

            # self.actionsView.queryCloudBox.setChecked(False)
            # self.showScoreBox.setChecked(False)
            # self.showBestBox.setChecked(False)

            self.openFileAct.setEnabled(True)
            self.editBoardAct.setEnabled(True)

            if old_mode in [
                GameMode.Puzzle,
            ]:
                self.initGame(cchess.FULL_INIT_FEN)

        elif new_mode == GameMode.EngineOnline:
            self.doCaptureAct.setEnabled(True)
            self.myGamesAct.setEnabled(False)
            self.bookmarkAct.setEnabled(False)
            self.bookmarkView.hide()
            self.puzzleView.hide()
            self.gamelibView.hide()
            self.actionsView.hide()

            # self.actionsView.queryCloudBox.setChecked(False)
            # self.showScoreBox.setChecked(True)
            # self.showBestBox.setChecked(True)

            self.openFileAct.setEnabled(False)
            self.editBoardAct.setEnabled(True)

            self.initGame(cchess.FULL_INIT_FEN)

        elif new_mode == GameMode.Puzzle:
            self.myGamesAct.setEnabled(False)
            self.bookmarkAct.setEnabled(False)
            self.puzzleView.show()
            self.bookmarkView.hide()
            self.gamelibView.hide()
            self.actionsView.hide()

            self.actionsView.queryCloudBox.setChecked(False)
            # self.showScoreBox.setChecked(False)
            # self.showBestBox.setChecked(False)

            self.openFileAct.setEnabled(False)
            self.editBoardAct.setEnabled(False)

            self.puzzleView.nextGame()

    def onGameOver(self, win_side):
        if Globl.gameManager.gameMode == GameMode.Puzzle:
            if win_side == cchess.BLACK:
                msgbox = TimerMessageBox("挑战失败, 重新再来!")
                msgbox.exec()
                self.onRestartGame()
            else:
                msgbox = TimerMessageBox("太棒了！ 挑战成功！！！")
                msgbox.exec()
                self.currGame["ok"] = True
                Globl.puzzleStore.updatePuzzle(self.currGame)
                self.puzzleView.updateCurrent(self.currGame)
                self.puzzleView.nextGame()
        else:
            win_msg = "红方被将死!" if win_side == cchess.BLACK else "黑方被将死!"
            msgbox = TimerMessageBox(win_msg)
            msgbox.exec()

    # -----------------------------------------------------------
    # 走子核心逻辑
    def initGame(self, fen):
        Globl.engineManager.stopThinking()
        self.clearAll()
        self.engineView.clearBgQueue()  # 中断后台思考
        self.moveEvent = threading.Event()
        self.moveEvent.set()

        self.isNeedSave = False
        self.init_fen = fen
        self.boardView.from_fen(self.init_fen, clear=True)

        position = {
            "fen": self.init_fen,
            "fen_engine": self.init_fen,
            "index": 0,
            "move_color": self.boardView.get_move_color(),
        }

        if cchess.FULL_INIT_BOARD in self.init_fen:
            position["ecco"] = ""

        self.currPosition = position

        self.positionList.append(position)
        self.historyView.onNewPostion(self.currPosition)
        self.updateStatus(quickMode=False)
        self.updateEcco()

        self.moveEvent.clear()

        self.initGameSignal.emit()

        self.changePositionSignal.emit(False)

    def updateEcco(self):
        if len(self.positionList) == 0:
            return

        if "ecco" in self.positionList[0]:
            position = self.positionList[-1]

            eccos = ""
            index = position["index"]

            if index >= 25:
                return

            if 8 < index < 25:
                ecco = getBookEcco(self.positionList)
                eccos = "-".join(ecco[1:])
                self.positionList[0]["ecco"] = eccos

            self.updateTitle(eccos)

    def onMoveGo(self, move_iccs, quickMode=False):  # , score = None):
        if not self.board.is_valid_iccs_move(move_iccs):
            return False

        # 用户走子时中断后台思考:
        # 1) 先 stop 引擎正在算的后台命令(清队列只是清 Python list,引擎进程里的思考不会停)
        # 2) 再清空 bgQueue
        if not quickMode:
            if self.engineView.bgProcessing and Globl.engineManager.isReady:
                Globl.engineManager.stopThinking()
            self.engineView.clearBgQueue()

        # --------------------------------
        # 尝试走棋
        move = self.board.move_iccs(move_iccs)
        if move is None:
            # 不能走就返回
            return False

        # self.board在做了这个move动作后，棋子已经更新到新位置了
        # board是下个走子的position了
        self.board.next_turn()
        # --------------------------------

        # 这一行必须有,否则引擎不能正常处理历史走子数据，会走出循环着法
        move_history = [x["move"] for x in self.positionList[1:]]
        move.prepare_for_engine(self.board.move_player, move_history)

        new_fen = self.board.to_fen()

        position = {
            "fen": new_fen,
            "fen_engine": move.to_engine_fen(),
            "fen_prev": move.board.to_fen(),
            "iccs": move_iccs,
            "move": move,
            "index": len(self.positionList),
            "move_color": move.board.move_player.color,
        }

        self.positionList.append(position)
        self.currPosition = position

        if not quickMode:
            self.isNeedSave = True

        # 在fenCach中把招法连起来
        # if new_fen not in Globl.fenCache:
        #    Globl.fenCache[new_fen] = {}
        Globl.fenCache[new_fen].update({"fen_prev": position["fen_prev"]})

        self.historyView.onNewPostion(self.currPosition)
        self.updateStatus(quickMode)
        self.updateEcco()

        self.changePositionSignal.emit(quickMode)

    def onChangePosition(self, quickMode=False):
        position = self.currPosition
        fen = position["fen"]
        move_index = position["index"]

        # 提示最优其他走法
        best_show = []
        if fen in Globl.fenCache:
            fenInfo = Globl.fenCache[fen]
            if "alter_best" in fenInfo:
                best_show = [cchess.iccs2pos(x) for x in fenInfo["alter_best"]]

        # 显示走子移动
        if "move" in position:
            move = position["move"]
            self.boardView.from_fen(move.board.to_fen())
            self.boardView.showMove(move.p_from, move.p_to, best_show)
        else:
            self.boardView.clearPickup()

        # 清空显示，同步棋盘状态
        self.engineView.clear()
        self.actionsView.clear()
        self.boardView.from_fen(fen)
        # self.historyView.selectRow(move_index)

        self.isRunEngine = False
        self.boardActions = OrderedDict()

        if not quickMode:
            self.localSearch(position)

            if self.isQueryCloud:
                self.cloudQuery.startQuery(position)

            # 引擎搜索 #TODO 根据checkbox状态搜索
            if Globl.gameManager.gameMode != GameMode.Free:
                self.runEngine(position)

    def isEndPosition(self):
        index = self.currPosition["index"]
        if index == (len(self.positionList) - 1):
            return True
        return False

    def updateStatus(self, quickMode):
        position = self.currPosition

        if "move" in position:
            move = position["move"]
            if move.is_checking:
                if move.is_checkmate:
                    msg = "将死！"
                    self.playSound("mate", quickMode)
                    self.onGameOver(move.board.move_player)
                else:
                    self.playSound("check", quickMode)
                    msg = "将军！"
            elif move.captured:
                self.playSound("capture", quickMode)
                msg = f"吃{cchess.fench_to_text(move.captured)}"
            else:
                self.playSound("move", quickMode)
                msg = ""

            self.statusBar().showMessage(msg)

    # -----------------------------------------------------------
    # fenCache 核心逻辑
    def updateFenCache(self, fenInfo, isEngine=False, isBackground=False):
        fen = fenInfo["fen"]

        if isEngine:
            if "score" in fenInfo:
                Globl.fenCache[fen]["score_e"] = fenInfo["score"]

            actions = fenInfo["actions"]
            for act in actions.values():
                if ("score" not in act) or ("new_fen" not in act):
                    continue
                new_fen = act["new_fen"]
                Globl.fenCache[new_fen]["score_e"] = act["score"]
        else:
            best_next = []
            Globl.fenCache[fen].update(fenInfo)

            # 此局面的最优下个招法
            if "actions" not in fenInfo:
                return

            actions = fenInfo["actions"]
            for act in actions.values():
                if act["diff"] >= BEST_MOVE_TOLERANCE:
                    best_next.append(act["iccs"])
            if best_next:
                Globl.fenCache[fen]["best_next"] = best_next

            # 本着法的其他更好的招法
            for act in actions.values():
                if "score" not in act:
                    continue
                new_fen = act["new_fen"]

                info = {"score": act["score"], "diff": act["diff"]}
                if (act["diff"] < ALTER_BEST_CLOUD) and best_next:
                    info["alter_best"] = best_next

                # TODO？？？
                if new_fen not in Globl.fenCache:
                    Globl.fenCache[new_fen] = {"fen_prev": fen}

                Globl.fenCache[new_fen].update(info)

            if best_next:
                Globl.fenCache[fen]["best_next"] = best_next

            # 如果这一步的fen不在上个步骤的预测走法里面，需要根据fen_prev的分数建立此步骤的alter_best
            fenInfo = Globl.fenCache[fen]

            if ("diff" not in fenInfo) and ("fen_prev" in fenInfo):
                move_color = cchess.get_move_color(fen)
                fen_prev = fenInfo["fen_prev"]
                if fen_prev in Globl.fenCache:
                    prevInfo = Globl.fenCache[fen_prev]
                    if "score" in prevInfo:
                        diff = prevInfo["score"] - fenInfo["score"]
                        if move_color == cchess.BLACK:
                            diff = -diff
                        fenInfo["diff"] = diff
                        if (diff < ALTER_BEST_ENGINE) and ("best_next" in prevInfo):
                            fenInfo["alter_best"] = prevInfo["best_next"]

        for pos in self.positionList:
            if pos["fen"] == fen:
                self.historyView.onUpdatePosition(pos)
                if isBackground:
                    # 后台模式下只更新匹配的第一行即可
                    break

    # ------------------------------------------------------------------------------
    # None UI Events
    def clearAllScore(self):
        # 清理分数但是保持fen链的完整性
        for pos in self.positionList:
            fen = pos["fen"]
            if fen not in Globl.fenCache:
                continue
            fenInfo = Globl.fenCache[fen]
            newInfo = {}
            if "fen_prev" in fenInfo:
                newInfo["fen_prev"] = fenInfo["fen_prev"]
            Globl.fenCache[fen] = newInfo

            self.historyView.onUpdatePosition(pos)

    def localSearch(self, position):
        fen = position["fen"]

        # 开局库
        openbook_actions = OrderedDict()
        if self.openBook is not None:
            query = self.openBook.getMoves(fen)
            if query:
                openbook_actions = query["actions"]

        # print(openbook_actions)

        # 本地库库
        query = Globl.localBook.getMoves(fen)
        if query:
            local_actions = query["actions"]
        else:
            local_actions = OrderedDict()

        for iccs, act in local_actions.items():
            if iccs in openbook_actions:
                act["score"] = openbook_actions[iccs]["score"]
            act["mark"] = "*"

        # 合并最终的输出
        final_actions = openbook_actions.copy()
        # 合并本地库与开局库
        for iccs, l_act in local_actions.items():
            if iccs in final_actions:
                f_act = final_actions[iccs]
                f_act.update(l_act)
            else:
                final_actions[iccs] = l_act

        # 更新分数
        for act in final_actions.values():
            new_fen = act["new_fen"]
            if "score" in act:
                # Globl.fenCache[new_fen]['score'] = act['score']
                Globl.fenCache[new_fen]["score_e"] = act["score"]

        # boardActions 存储当前局面下的最优走法
        self.boardActions = final_actions
        self.actionsView.updateActions(self.boardActions)

    def onCloudQueryResult(self, query):
        def sort_key(item):
            if "score" in item[1]:
                return item[1]["score"]
            else:
                return 0

        # logging.info(str(query))

        if not query or not self.positionList:
            return

        if self.isQueryCloud:
            self.updateFenCache(query)

        fen = query["fen"]
        move_color = cchess.get_move_color(fen)
        new_actions = {}

        if fen != self.currPosition["fen"]:
            return

        actions = query["actions"]
        for iccs, act in actions.items():
            # print(iccs, act)
            if iccs in self.boardActions:
                old_act = self.boardActions.pop(iccs)
                old_act.update(act)
                new_actions[iccs] = old_act
            else:
                new_actions[iccs] = act

        x = OrderedDict(
            sorted(
                new_actions.items(), key=sort_key, reverse=(move_color == cchess.RED)
            )
        )
        for iccs, act in self.boardActions.items():
            x[iccs] = act

        self.boardActions = x
        self.actionsView.updateActions(self.boardActions)

    def onCloudQueryError(self, fen, error, error_str):
        """云库查询错误时显示提示"""
        msg = f"云库查询失败: {error_str}"
        logging.warning(msg)
        self.statusBar().showMessage(msg, 5000)

    def showBestHint(self, fenInfo):
        best = []

        move = fenInfo.get("iccs", None)
        if not move:
            return
        best.append(cchess.iccs2pos(move))

        ponder = fenInfo.get("ponder", None)
        if ponder:
            best.append(cchess.iccs2pos(ponder))

        self.boardView.showMoveHint(best)

    # -----------------------------------------------------------
    # Engine 最终着法输出
    def onTryEngineMove(self, engine_id, fenInfo):
        # 判断是否为后台分析结果
        is_bg = fenInfo.get("is_background", False)
        if is_bg:
            self.onBgEngineMove(engine_id, fenInfo)
            return

        self.isRunEngine = False

        fen = trim_fen(fenInfo["fen"])
        iccs = fenInfo.get("iccs", "")

        logging.info(f"Engine[{engine_id}] BestMove {iccs}")

        # 安全验证：如果结果fen与当前局面不一致，可能是竞态问题或后台结果
        if self.currPosition and fen != self.currPosition["fen"]:
            # 如果正在后台处理，交给后台处理
            if self.engineView.bgProcessing:
                self.onBgEngineMove(engine_id, fenInfo)
                return
            # 否则忽略此过期结果
            logging.warning(f"引擎结果fen与当前局面不一致，忽略此结果")
            return

        self.updateFenCache(fenInfo, isEngine=True)

        if self.moveEvent.is_set():
            return

        move_color = self.board.get_move_color()
        # 只有在最后一行时，引擎才会触发走子
        if self.isEndPosition() and (self.engineRunColor[move_color] == engine_id):
            self.moveEvent.set()
            self.onMoveGo(iccs)
            self.moveEvent.clear()
        elif not self.isQueryCloud:
            self.showBestHint(fenInfo)

        # 前台分析完成，延迟启动后台思考
        QTimer.singleShot(300, self.startBackgroundThinking)

    def onBgEngineMove(self, engine_id, fenInfo):
        """处理后台分析结果"""
        self.updateFenCache(fenInfo, isEngine=True, isBackground=True)
        # 继续处理队列中的下一个局面
        self.processNextBgPosition()

    def startBackgroundThinking(self):
        """启动后台思考：收集未分析的局面并启动分析"""
        # 检查开关
        if not self.engineView.bgThinkingBox.isChecked():
            return
        # 只在辅助模式下启用后台思考
        if Globl.gameManager.gameMode not in [GameMode.EngineAssit]:
            return
        if not self.positionList:
            return

        # 如果引擎正被前台占用,延迟启动后台思考,避免抢断前台 bestmove
        if Globl.engineManager.isReady and Globl.engineManager._is_analyzing:
            QTimer.singleShot(500, self.startBackgroundThinking)
            return

        # 清空旧队列
        self.engineView.bgQueue.clear()
        seen_fens = set()

        for position in self.positionList:
            fen = position["fen"]
            # 去重
            if fen in seen_fens:
                continue
            seen_fens.add(fen)
            # 跳过空局面
            if cchess.EMPTY_BOARD in fen:
                continue
            # 检查是否已有引擎分数
            fen_cache = Globl.fenCache[fen] if fen in Globl.fenCache else {}
            if "score_e" in fen_cache:
                continue
            # 加入队列
            self.engineView.bgQueue.append(position)

        if not self.engineView.bgQueue:
            return

        self.engineView.bgProcessing = True
        self.engineView.updateBgQueueLabel()

        # 启动队列处理
        QTimer.singleShot(200, self.processNextBgPosition)

    def processNextBgPosition(self):
        """处理后台队列中的下一个局面"""
        if not self.engineView.bgProcessing:
            return
        if not self.engineView.bgQueue:
            self.engineView.bgProcessing = False
            self.engineView.updateBgQueueLabel()
            return
        # 检查是否仍允许后台思考
        if not self.engineView.bgThinkingBox.isChecked():
            self.engineView.bgProcessing = False
            self.engineView.bgQueue.clear()
            self.engineView.updateBgQueueLabel()
            return

        # 互斥检查:如果引擎正被前台占用,不要抢断;300ms 后重试
        if Globl.engineManager.isReady and Globl.engineManager._is_analyzing:
            QTimer.singleShot(300, self.processNextBgPosition)
            return

        # 取出下一个局面
        position = self.engineView.bgQueue.pop(0)
        self.engineView.updateBgQueueLabel()

        # 检查局面是否还在列表中（可能用户已删除后续着法）
        fen = position["fen"]
        still_valid = any(p["fen"] == fen for p in self.positionList)
        if not still_valid:
            self.processNextBgPosition()
            return

        # 检查是否已有分数（可能在等待引擎响应时被其他方式填充了）
        fen_cache = Globl.fenCache[fen] if fen in Globl.fenCache else {}
        if "score_e" in fen_cache:
            self.processNextBgPosition()
            return

        # 设置后台引擎参数：单分支
        Globl.engineManager.setOption("MultiPV", 1)

        # 发送局面到引擎进行后台分析
        bgParams = self.engineView.getBgGoParams()
        fen_engine = position["fen_engine"]
        try:
            Globl.engineManager.goFrom(fen_engine, fen, bgParams)
        except EngineErrorException as e:
            logging.warning(f"后台思考引擎命令出错: {e}")
            self.engineView.bgProcessing = False
            self.engineView.bgQueue.clear()
            self.engineView.updateBgQueueLabel()

    def onEngineMoveInfo(self, engine_id, fenInfo):
        if not self.currPosition:
            return

        fen = fenInfo["fen"]

        # 引擎输出的历史数据,不处理
        if fen != self.currPosition["fen"]:
            return

        """
        currmove = fenInfo.get('currmove', None)
        if (not self.isQueryCloud) and currmove:
            self.boardView.showMoveHint([cchess.iccs2pos(currmove)])
            return
        """

        moves = fenInfo.get("moves", None)
        if not moves:
            return

        iccs = moves[0]
        board = ChessBoard(fen)

        # 引擎输出的历史数据,不处理
        if not board.is_valid_iccs_move(iccs):
            return

        """
        moveShow = [cchess.iccs2pos(x) for x in moves[:2]]
        if not self.isQueryCloud:
            self.boardView.showMoveHint(moveShow)
        """

        self.engineView.onEngineMoveInfo(fenInfo)

    def onEngineReady(self, engine_id, name, engine_options):
        logging.info(f"Engine[{engine_id}] {name} Ready.")
        self.engineView.loadSettings(Globl.settings)
        self.engineView.onEngineReady(engine_id, name, engine_options)
        # 默认只从自由练棋模式开始，减少复杂度
        self.switchGameMode(GameMode.EngineAssit)

        self.detectRunEngine()

    # --------------------------------------------------------------------
    # 引擎相关
    def enginePlayColor(self, engine_id, color, yes):
        if yes:
            self.engineRunColor[color] = engine_id
        else:
            self.engineRunColor[color] = 0

        self.detectRunEngine()

    def detectRunEngine(self):
        if Globl.gameManager.gameMode == GameMode.Free:
            return

        if not self.currPosition:
            return

        needRun = sum(self.engineRunColor) > 0
        if needRun and (not self.isRunEngine):
            self.runEngine(self.currPosition)

    def runEngine(self, position):
        if not Globl.engineManager.isReady:
            return

        fen = position["fen"]
        fen_engine = position["fen_engine"]
        if cchess.EMPTY_BOARD in fen:
            return

        reload = False
        move_color = position["move_color"]  # cchess.get_move_color(fen)
        if (self.engineRunColor[0] > 0) or (self.engineRunColor[move_color] > 0):
            # 设置前台引擎参数：多分支（用户设置）
            fg_multipv = self.engineView.params.get(
                f"{self.engineView.goMode}.MultiPV", 1
            )
            Globl.engineManager.setOption("MultiPV", fg_multipv)

            # 首行会没有move项
            params = self.engineView.getGoParams()
            try:
                ok = Globl.engineManager.goFrom(fen_engine, fen, params)
                self.isRunEngine = ok
            except EngineErrorException as e:
                QMessageBox.critical(
                    self, f"{getTitle()}", f"象棋引擎发送命令出错[{e}]，自动重启引擎。"
                )
                reload = True

        if reload:
            ok = Globl.engineManager.loadEngine(self.engine_exec, self.engine_type)
            if not ok:
                QMessageBox.critical(
                    self,
                    f"{getTitle()}",
                    f"加载象棋引擎[{self.engine_exec}]出错，请确认该程序能在您的电脑上正确运行。",
                )

    # ------------------------------------------------------------------------------
    # UI Events
    def onTryBoardMove(self, move_from, move_to):
        if self.moveEvent.is_set():
            return

        self.moveEvent.set()

        if not self.isEndPosition():
            step_index = self.currPosition["index"]
            self.removeHistoryFollow(step_index)

        move_iccs = cchess.pos2iccs(move_from, move_to)
        self.onMoveGo(move_iccs)

        self.moveEvent.clear()

    def onTryBookMove(self, moveInfo):
        if not self.isEndPosition():
            return

        # 判断重复局面次数，大于2次被认为是循环导入
        iccs = moveInfo["iccs"]
        fen = moveInfo.get("fen", None)
        if fen:
            fen = moveInfo["fen"]
            board = ChessBoard(fen)

            move = board.move_iccs(iccs)
            if move is None:
                return

            board.next_turn()
            new_fen = board.to_fen()

            fen_count = 0
            for position in self.positionList:
                if new_fen == position["fen"]:
                    fen_count += 1

            # 重复的局面次数过多，不再导入
            if fen_count >= 2:
                return

        self.moveEvent.set()
        self.onMoveGo(iccs)
        self.moveEvent.clear()

    def onBoardRightMouse(self, is_mouse_pressed):
        best_next = []

        if is_mouse_pressed:
            fen = self.currPosition["fen"]
            if (fen not in Globl.fenCache) or ("best_next" not in Globl.fenCache[fen]):
                return

            iccs_list = Globl.fenCache[fen]["best_next"]
            best_next = [cchess.iccs2pos(x) for x in iccs_list]

        self.boardView.showMoveHint(best_next)

    def removeHistoryFollow(self, step_index):
        self.positionList = self.positionList[: step_index + 1]
        self.currPosition = self.positionList[-1]
        self.historyView.onRemoveHistoryFollow(step_index)
        # 删除分支时重新触发后台思考（因为局面列表变了）
        if self.engineView.bgProcessing:
            self.engineView.clearBgQueue()
            QTimer.singleShot(500, self.startBackgroundThinking)

        if len(self.positionList) <= 1:
            self.isNeedSave = False

        self.updateEcco()

    def onSelectHistoryPosition(self, move_index):
        if (move_index < 0) or (move_index >= len(self.positionList)):
            return

        # 重复触发同一个事件，忽略
        if move_index == self.currPosition["index"]:
            return

        # 切换局面时中断后台思考
        self.engineView.clearBgQueue()

        self.currPosition = self.positionList[move_index]
        self.changePositionSignal.emit(False)

    def copyEngineFenToClipboard(self):
        if (not self.currPosition) or ("move" not in self.currPosition):
            return

        fen_engine = self.currPosition["fen_engine"]
        clipboard = QApplication.clipboard()
        clipboard.clear()
        clipboard.setText(fen_engine)

    def setQueryCloud(self, yes):
        if yes == self.isQueryCloud:  # 模式未变
            return

        self.isQueryCloud = yes

        # self.clearAllScore()

        # 极少数情况下棋盘是未初始化的
        if self.currPosition:
            self.localSearch(self.currPosition)

        if self.isQueryCloud:
            # self.reviewByEngineBtn.setEnabled(False)
            # self.reviewByCloudBtn.setEnabled(True)
            if self.currPosition:
                self.cloudQuery.startQuery(self.currPosition)
                self.startBgCloudSearch()
        else:
            # self.reviewByEngineBtn.setEnabled(True)
            # self.reviewByCloudBtn.setEnabled(False)
            pass

    def startBgCloudSearch(self):
        """后台搜索云库：对历史无云库分数的局面进行查询"""
        seen_fens = set()
        for position in self.positionList:
            fen = position["fen"]
            # 去重
            if fen in seen_fens:
                continue
            seen_fens.add(fen)
            # 跳过空局面
            if cchess.EMPTY_BOARD in fen:
                continue
            # 检查是否已有云库分数（注意是 score，不是 score_e）
            fen_cache = Globl.fenCache[fen] if fen in Globl.fenCache else {}
            if "score" in fen_cache:
                continue
            # 加入云库查询队列（CloudDB内部自动排队）
            self.cloudQuery.startQuery(position)

    # ------------------------------------------------------------------------------
    # UI Event Handler
    def onDoFreeGame(self):
        self.switchGameMode(GameMode.EngineAssit)

    def onDoFightRobot(self):
        self.switchGameMode(GameMode.EngineFight)

    def onDoPuzzle(self):
        if (Globl.gameManager.gameMode != GameMode.Puzzle) and self.isNeedSave:
            steps = len(self.positionList) - 1
            if not self.getConfirm(
                f"当前棋谱已经走了 {steps} 步, 您确定要切换到 [残局挑战] 模式并丢弃当前棋谱吗?"
            ):
                return
        self.switchGameMode(GameMode.Puzzle)

    def onDoOnline(self):
        if (Globl.gameManager.gameMode != GameMode.Puzzle) and self.isNeedSave:
            steps = len(self.positionList) - 1
            if not self.getConfirm(
                f"当前棋谱已经走了 {steps} 步, 您确定要切换到 [残局挑战] 模式并丢弃当前棋谱吗?"
            ):
                return

        self.switchGameMode(GameMode.EngineOnline)
        self.update()

        screen = QApplication.primaryScreen()
        screen_size = screen.availableSize()
        screen_width = screen_size.width()
        screen_height = screen_size.height()

        win_rect = self.frameGeometry()
        marge_size = self.boardView.getMargeSize()
        new_x = self.pos().x() + (screen_width - win_rect.right() - 5) + marge_size[0]
        self.move(new_x, 0)

        # self.onlineSchemeCombo.clear()
        # names = self.onlineManager.get_schema_names()
        # self.onlineSchemeCombo.addItems(names)

        self.update()
        # self.onDoCapture()

    def onDoCapture(self):
        dlg = OnlineDialog(self, self.onlineManager)
        dlg.show()

    def onRestartGame(self):
        if (
            Globl.gameManager.gameMode in [GameMode.EngineAssit, GameMode.EngineFight]
        ) and self.isNeedSave:
            steps = len(self.positionList) - 1
            if not self.getConfirm(f"当前棋谱已经走了 {steps} 步, 您确定要从新开始吗?"):
                return

        self.initGame(self.init_fen)

    def onSelectPuzzle(self, game):
        if Globl.gameManager.gameMode != GameMode.Puzzle:
            return

        self.currGame = game
        self.book_moves = game["moves"].split(" ") if "moves" in game else []

        fen = game["fen"]
        steps = getStepsFromFenMoves(fen, self.book_moves)

        self.initGame(fen)

        for fen_t, iccs in steps:
            Globl.fenCache[fen_t] = {
                "score": 39999,
                "best_next": [
                    iccs,
                ],
            }

        self.isNeedSave = False
        self.updateTitle(f"{game['book_name']} - {game['name']}")

    def loadBookGame(self, name, game):
        fen = game.init_board.to_fen()

        self.initGame(fen)

        moves = game.dump_iccs_moves()

        if not moves:
            return

        for iccs in moves[0]:
            self.moveEvent.set()
            self.onMoveGo(iccs, quickMode=True)
            # qApp.processEvents()
            self.moveEvent.clear()

        self.isNeedSave = False
        self.updateTitle(name)
        self.detectRunEngine()

    def loadBookmark(self, name, position):
        if self.isNeedSave:
            steps = len(self.positionList) - 1
            if not self.getConfirm(
                f"当前棋谱已经走了 {steps} 步, 您确定要加载收藏并丢弃当前棋谱吗?"
            ):
                return

        self.bookmarkView.setEnabled(False)

        fen = position["fen"]
        self.initGame(fen)

        moves = position.get("moves", [])
        if moves:
            for iccs in moves:
                self.moveEvent.set()
                self.onMoveGo(iccs, quickMode=True)
                self.moveEvent.clear()

        self.isNeedSave = False
        self.updateTitle(name)
        self.bookmarkView.setEnabled(True)

    def onViewBranch(self, fenInfo):
        dlg = MoveListDialog()
        fen = self.currPosition["fen"]
        step_index = self.currPosition["index"]
        dlg.shouMoves(fen, step_index, fenInfo["moves"])

    def onShowMyGames(self):
        if self.myGameView.isVisible():
            self.myGameView.hide()
        else:
            self.myGameView.show()

    def onShowBookmark(self):
        if self.bookmarkView.isVisible():
            self.bookmarkView.hide()
        else:
            self.bookmarkView.show()
            self.bookmarkView.setFocus(Qt.TabFocusReason)

    def onCloudModeChanged(self, state):
        yes = self.actionsView.queryCloudBox.isChecked()
        self.setQueryCloud(yes)
        if yes:
            self.actionsView.show()

    def onShowScoreChanged(self, state):
        self.historyView.setShowScore((Qt.CheckState(state) == Qt.Checked))

    def onEditBoard(self):
        dlg = PositionEditDialog(self, self.skin_folder)
        new_fen = dlg.edit(self.board.to_fen())
        if new_fen:
            self.initGame(new_fen)

    def onCaptureBoard(self):
        pass
        # self.hide()
        # self.snippingWidget.start()

    # def onSnippingCompleted(self, img):
    #    self.show()
    #    self.setWindowState(Qt.WindowActive)
    #    dlg = ImageToBoardDialog(self)
    #    dlg.edit(img)

    def onSearchBoard(self):
        dlg = PositionEditDialog(self)
        new_fen = dlg.edit("")
        if new_fen:
            self.initGame(new_fen)

    def onSetupEngine(self):
        dlg = EngineConfigDialog(self)
        dlg.exec()

    def onQuickStart(self):
        pass

    def onOpenFile(self):
        options = QFileDialog.Options()
        # options |= QFileDialog.DontUseNativeDialog

        fileName, _ = QFileDialog.getOpenFileName(
            self,
            "打开文件",
            self.lastOpenFolder,
            "象棋谱(库)文件(*.pgn;*.xqf;*.cbr;*.cbl);;",
            options=options,
        )

        if not fileName:
            return

        self.openFile(fileName)

    def onOpenPuzzleFile(self):
        options = QFileDialog.Options()
        # options |= QFileDialog.DontUseNativeDialog

        fileName, _ = QFileDialog.getOpenFileName(
            self,
            "打开文件",
            self.lastOpenFolder,
            "残局挑战库文件(*.csv);;",
            options=options,
        )

        if not fileName:
            return

    def onSaveFile(self):
        if not self.positionList:
            return

        fileNameDefault = f"{self.lastOpenFolder}\\{self.getDefaultGameName()}.pgn"

        options = QFileDialog.Options()
        # options |= QFileDialog.DontUseNativeDialog

        fileName, _ = QFileDialog.getSaveFileName(
            self,
            "保存对局文件",
            fileNameDefault,
            "象棋通用格式文件(*.pgn)",
            options=options,
        )

        if not fileName:
            return

        self.saveToFile(fileName)
        self.lastOpenFolder = str(Path(fileName).parent)

    def saveImageToFile(self):
        if not self.positionList:
            return

        fileNameDefault = f"{self.lastOpenFolder}\\{self.getDefaultGameName()}.jpg"

        options = QFileDialog.Options()
        # options |= QFileDialog.DontUseNativeDialog

        fileName, _ = QFileDialog.getSaveFileName(
            self,
            "保存局面图片文件",
            fileNameDefault,
            "图像文件(*.jpg)",
            options=options,
        )

        if not fileName:
            return

        if self.boardPanel.saveImageToFile(fileName):
            self.lastOpenFolder = str(Path(fileName).parent)

    def openFile(self, file_name):
        fileName = Path(file_name)
        if not fileName.is_file():
            msg = f"文件不存在：{fileName}"
            logging.error(msg)
            msgbox = TimerMessageBox(msg)
            msgbox.exec()
            return

        ext = fileName.suffix.lower()
        if ext in GAME_FILE_TYPES:
            game = Game.read_from(fileName)
            if not game:
                msg = f"读取棋谱文件错误：{fileName}"
                logging.error(msg)
                msgbox = TimerMessageBox(msg)
                msgbox.exec()
                return
            self.gamelibView.hide()
            self.loadBookGame(fileName.name, game)
            self.lastOpenFolder = str(fileName.parent)

        elif ext in GAME_LIB_TYPES:
            try:
                game_lib = Game.read_from_lib(fileName)
            except Exception as e:
                msg = f"读取棋谱库文件【{fileName}】错误：{e}"
                logging.error(msg)
                msgbox = TimerMessageBox(msg)
                msgbox.exec()
                return

            self.gamelibView.updateGameLib(game_lib)
            self.gamelibView.show()

            self.lastOpenFolder = str(fileName.parent)
        else:
            msg = f"不支持的文件类型【{fileName}】"
            logging.error(msg)
            msgbox = TimerMessageBox(msg)
            msgbox.exec()

    def saveToFile(self, file_name):
        try:
            board = ChessBoard(self.positionList[0]["fen"])
            game = Game(board.copy())

            for index, pos in enumerate(self.positionList[1:]):
                # print(pos['index'], pos['iccs'])
                move = board.move_iccs(pos["iccs"])
                game.append_next_move(move)
                board.next_turn()

            game.save_to(file_name)
            self.isNeedSave = False
        except Exception as e:
            msg = f"保存文件[{file_name}]{index}步{pos['iccs']}出错：{traceback.format_exc()}"
            logging.error(msg)
            msgbox = TimerMessageBox(msg)
            msgbox.exec()
            return False
        return True

    def onUseOpenBookFile(self):
        options = QFileDialog.Options()
        # options |= QFileDialog.DontUseNativeDialog

        fileName, _ = QFileDialog.getOpenFileName(
            self,
            "打开文件",
            "",
            "YFK格式开局库(*.yfk);;pfBook格式开局库(*.pfBook);;所有文件(*.*)",
            options=options,
        )

        if not fileName:
            return

        fileName = Path(fileName)

        self.loadOpenBook(fileName)

    def onChangedSkin(self, action):
        skin = action.text()
        self.changeSkin(skin)

    def changeSkin(self, skin):
        if skin == self.skin:
            return True

        if skin in self.skins:
            self.skin_folder = self.skins[skin]["Folder"]
            if self.boardView.fromSkinFolder(self.skin_folder):
                self.skins[skin]["action"].setChecked(True)
                self.skin = skin
                return True

        return False

    # ------------------------------------------------------------------------------
    # Online
    def onOnlineSchemeChanged(self, index):
        name = self.onlineSchemeCombo.currentText()
        self.onlineManager.use_schema(name)

    # ------------------------------------------------------------------------------
    # Drag & Drop
    def dragEnterEvent(self, event):
        if Globl.gameManager.gameMode != GameMode.EngineAssit:
            return

        # TODO 先询问是否丢弃当前未保存的内容
        urls = event.mimeData().urls()
        fileName = Path(urls[0].toLocalFile())
        ext = fileName.suffix.lower()
        if ext in GAME_TYPES_ALL:  # '.jpg', '.png', '.bmp', '.jpeg']:
            event.acceptProposedAction()

    def dropEvent(self, event):
        if Globl.gameManager.gameMode != GameMode.EngineAssit:
            return

        fileName = Path(event.mimeData().urls()[0].toLocalFile())
        ext = fileName.suffix.lower()
        if ext in GAME_TYPES_ALL:
            self.openFile(fileName)

    # ------------------------------------------------------------------------------
    # UI Base
    def createActions(self):
        self.openFileAct = QAction(
            self.style().standardIcon(QStyle.SP_DialogOpenButton),
            "打开棋谱",
            self,
            statusTip="打开棋谱（库）文件",
            triggered=self.onOpenFile,
        )

        self.openPuzzleFileAct = QAction(
            self.style().standardIcon(QStyle.SP_DialogOpenButton),
            "打开残局挑战库",
            self,
            statusTip="打开残局挑战库文件（.CSV）",
            triggered=self.onOpenPuzzleFile,
        )

        self.useOpenBookAct = QAction(
            self.style().standardIcon(QStyle.SP_DialogOpenButton),
            "开局库选择",
            self,
            statusTip="选择开局库文件",
            triggered=self.onUseOpenBookFile,
        )

        self.saveFileAct = QAction(
            self.style().standardIcon(QStyle.SP_DialogSaveButton),
            "保存棋谱",
            self,
            statusTip="保存棋谱文件(PGN 格式)",
            triggered=self.onSaveFile,
        )
        self.setupEngineAct = QAction(  # QIcon(':ImgRes/openbook.png'),
            "引擎设置", self, statusTip="设置引擎参数", triggered=self.onSetupEngine
        )

        self.doOpenBookAct = QAction(
            QIcon(":ImgRes/openbook.png"),
            "自由练习",
            self,
            statusTip="自由练习",
            triggered=self.onDoFreeGame,
        )

        self.doPuzzleAct = QAction(
            QIcon(":ImgRes/puzzle.png"),
            "残局中局",
            self,
            statusTip="残局杀法，中局战术",
            triggered=self.onDoPuzzle,
        )

        self.doRobotAct = QAction(
            QIcon(":ImgRes/robot.png"),
            "人机战斗",
            self,
            statusTip="人机战斗",
            triggered=self.onDoFightRobot,
        )

        self.doOnlineAct = QAction(
            QIcon(":ImgRes/online.png"),
            "连线分析",
            self,
            statusTip="连线分析",
            triggered=self.onDoOnline,
        )

        self.doCaptureAct = QAction(
            QIcon(":ImgRes/capture.png"),
            "对弈窗口截图",
            self,
            statusTip="截图对弈界面",
            triggered=self.onDoCapture,
        )

        self.restartAct = QAction(
            QIcon(":ImgRes/restart.png"),
            "重新开始",
            self,
            statusTip="重新开始",
            triggered=self.onRestartGame,
        )

        self.editBoardAct = QAction(
            QIcon(":ImgRes/edit.png"),
            "自定局面",
            self,
            statusTip="从自定局面开始",
            triggered=self.onEditBoard,
        )

        self.searchBoardAct = QAction(
            QIcon(":ImgRes/search.png"),
            "搜索局面",
            self,
            statusTip="从对局库中搜索局面",
            triggered=self.onSearchBoard,
        )

        self.quickStartAct = QAction(  # QIcon(':ImgRes/search.png'),
            "快速开局", self, statusTip="快速走到某个开局", triggered=self.onQuickStart
        )

        self.captureBoardAct = QAction(
            QIcon(":ImgRes/search.png"),
            "屏幕截图",
            self,
            statusTip="从屏幕截图识别局面",
            triggered=self.onCaptureBoard,
        )

        self.myGamesAct = QAction(
            QIcon(":ImgRes/mybook.png"),
            "我的对局库",
            self,
            statusTip="我的对局库",
            triggered=self.onShowMyGames,
        )

        self.bookmarkAct = QAction(
            QIcon(":ImgRes/bookmark.png"),
            "我的收藏",
            self,
            statusTip="我的收藏",
            triggered=self.onShowBookmark,
        )

        self.exitAct = QAction(
            QIcon(":ImgRes/exit.png"),
            "退出程序",
            self,
            shortcut="Ctrl+Q",
            statusTip="退出应用程序",
            triggered=QApplication.closeAllWindows,
        )

        self.aboutAct = QAction(
            "关于...",
            self,
            # statusTip="Show the application's About box",
            triggered=self.about,
        )

    def createMenus(self):
        self.fileMenu = self.menuBar().addMenu("文件")
        self.fileMenu.addAction(self.openFileAct)
        self.fileMenu.addAction(self.saveFileAct)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.useOpenBookAct)
        self.fileMenu.addAction(self.openPuzzleFileAct)
        self.fileMenu.addSeparator()
        # self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.exitAct)

        self.menuBar().addSeparator()

        self.showMoveSoundAct = QAction("走子音效", checkable=True)
        self.showMoveSoundAct.setChecked(True if self.soundVolume > 0 else False)
        self.showMoveSoundAct.toggled.connect(self.onShowMoveSound)

        self.winMenu = self.menuBar().addMenu("窗口")
        self.winMenu.addAction(self.historyDoc.toggleViewAction())
        self.winMenu.addAction(self.engineView.toggleViewAction())
        # self.winMenu.addAction(self.moveDbView.toggleViewAction())
        self.winMenu.addAction(self.actionsView.toggleViewAction())
        self.winMenu.addAction(self.testRunnerView.toggleViewAction())
        self.winMenu.addAction(self.showMoveSoundAct)

        self.skinMenu = self.menuBar().addMenu("皮肤")
        self.skinMenu.triggered.connect(self.onChangedSkin)

        skinActionGroup = QActionGroup(self)
        skinActionGroup.setExclusive(True)

        for index, skin in enumerate(self.skins.keys()):
            action = QAction(skin, self)
            action.setCheckable(True)
            if index == 0:
                action.setChecked(True)
            skinActionGroup.addAction(action)
            self.skinMenu.addAction(action)
            self.skins[skin]["action"] = action

        self.helpMenu = self.menuBar().addMenu("帮助")
        # self.helpMenu.addAction(self.upgradeAct)
        self.helpMenu.addAction(self.aboutAct)

    def createToolBars(self):
        self.fileBar = self.addToolBar("File")
        self.fileBar.setObjectName("File")

        self.fileBar.addAction(self.openFileAct)
        self.fileBar.addAction(self.saveFileAct)
        self.fileBar.addAction(self.bookmarkAct)

        ag = QActionGroup(self)
        ag.setExclusive(True)
        ag.addAction(self.doOpenBookAct)
        ag.addAction(self.doPuzzleAct)
        ag.addAction(self.doRobotAct)
        ag.addAction(self.doOnlineAct)

        self.gameBar = self.addToolBar("Game")
        self.gameBar.setObjectName("Game")

        self.gameBar.addAction(self.doOpenBookAct)
        self.gameBar.addAction(self.doRobotAct)
        self.gameBar.addAction(self.doPuzzleAct)
        # self.gameBar.addAction(self.doOnlineAct)

        self.gameBar.addAction(self.restartAct)
        self.gameBar.addAction(self.editBoardAct)

        # self.doOnlineAct.setEnabled(False)
        # self.gameBar.addAction(self.captureBoardAct)
        # self.gameBar.addAction(self.searchBoardAct)

        self.showBar = self.addToolBar("Show")
        self.showBar.setObjectName("Show")

        # self.showBar.addWidget(self.flipBox)
        # self.showBar.addWidget(self.mirrorBox)
        # self.showBar.addSeparator()

        self.showBar.addSeparator()

        """
        self.onlineBar = self.addToolBar("Online")
        self.onlineBar.setObjectName("Online")
        self.onlineBar.addAction(self.doCaptureAct)
        self.onlineSchemeCombo = QComboBox(self)
        self.onlineSchemeCombo.currentIndexChanged.connect(self.onOnlineSchemeChanged)
        self.onlineBar.addWidget(self.onlineSchemeCombo)
        """

        self.sysBar = self.addToolBar("System")
        self.sysBar.setObjectName("System")

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.sysBar.addWidget(spacer)
        self.sysBar.addAction(self.exitAct)

        self.statusBar().showMessage("Ready")

    def onShowMoveSound(self, yes):
        self.soundVolume = 30 if yes else 0

    def center(self):
        screen = QWidget.screen().screenGeometry()
        size = self.geometry()
        self.move(
            (screen.width() - size.width()) // 2, (screen.height() - size.height()) // 2
        )

    def closeEvent(self, event):
        steps = len(self.positionList) - 1
        if self.isNeedSave and (
            Globl.gameManager.gameMode in [GameMode.EngineAssit, GameMode.EngineFight]
        ):
            if not self.getConfirm(
                f"当前棋谱已经走了 {steps} 步, 尚未保存，您确定要关闭程序吗?"
            ):
                event.ignore()
                return

        self.saveSettings()

        Globl.engineManager.stopThinking()
        Globl.engineManager.quit()
        time.sleep(0.6)

        if self.openBook is not None:
            self.openBook.close()
        # Globl.bookmarkStore.close()
        Globl.puzzleStore.close()
        Globl.localBook.close()

        logging.info("应用关闭.")

    def readSettings(self):
        self.restoreGeometry(Globl.settings.value("geometry", QByteArray()))
        self.restoreState(Globl.settings.value("windowState", QByteArray()))

        self.soundVolume = Globl.settings.value("soundVolume", 30)
        self.showMoveSoundAct.setChecked(self.soundVolume > 0)

        skin = Globl.settings.value("boardSkin", DEFAULT_SKIN)
        if skin != DEFAULT_SKIN:
            self.changeSkin(skin)

        # self.openBookFile = Path(Globl.settings.value("openBookFile", str(Path('game','openbook.yfk'))))
        self.lastOpenFolder = Globl.settings.value("lastOpenFolder", "")

        self.puzzleView.loadSettings(Globl.settings)
        self.historyView.loadSettings(Globl.settings)

        self.boardPanel.loadSettings(Globl.settings)

        self.testRunnerView.loadSettings(Globl.settings)

        cloudMode = Globl.settings.value("cloudMode", True, type=bool)
        self.actionsView.queryCloudBox.setChecked(cloudMode)

    def saveSettings(self):
        # GameMode不保存，下次启动后进入自由练棋模式
        Globl.settings.setValue("geometry", self.saveGeometry())
        Globl.settings.setValue("windowState", self.saveState())

        Globl.settings.setValue("soundVolume", self.soundVolume)

        Globl.settings.setValue("cloudMode", self.actionsView.queryCloudBox.isChecked())

        # Globl.settings.setValue("openBookFile", str(self.openBookFile))
        Globl.settings.setValue("lastOpenFolder", self.lastOpenFolder)
        Globl.settings.setValue("boardSkin", self.skin)

        self.engineView.saveSettings(Globl.settings)
        self.puzzleView.saveSettings(Globl.settings)
        self.historyView.saveSettings(Globl.settings)
        self.boardPanel.saveSettings(Globl.settings)

        self.testRunnerView.saveSettings(Globl.settings)

    def about(self):
        QMessageBox.about(
            self,
            f"关于 {Globl.APP_NAME}",
            f"{Globl.APP_NAME_TEXT} Version {release_version}\n个人棋谱管家.\n 云库支持：https://www.chessdb.cn/\n 引擎支持：皮卡鱼(https://pikafish.org/)\n\n 联系作者：1053386709@qq.com\n QQ 进群：101947824\n",
        )


# -----------------------------------------------------#
