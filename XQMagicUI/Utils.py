# -*- coding: utf-8 -*-
import csv
import json
import os
import sys
import traceback
import uuid
from collections import OrderedDict, namedtuple
from dataclasses import dataclass
from enum import Enum, auto

import psutil
import requests
from cchess import BLACK, ChessBoard, Move
from PyQt5.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication, QInputDialog, QMessageBox

# import numpy as np
# import cv2 as cv
# from PIL import Image
from . import Globl

# -----------------------------------------------------#
# 图标判断阈值（diff 分数差）
ICON_DIFF_STAR = -30  # 好棋阈值
ICON_DIFF_GOOD = -70  # 一般阈值
ICON_DIFF_SAD = -100  # 劣着阈值

# 招法质量阈值
BEST_MOVE_TOLERANCE = -5  # 最优招法容忍范围
ALTER_BEST_CLOUD = -50  # 云库偏离最佳阈值
ALTER_BEST_ENGINE = -40  # 引擎偏离预测阈值

# 引擎分数
MATE_SCORE = 29999  # 绝杀分数

# 云库查询
CLOUD_QUERY_DELAY = 500  # 云库查询间隔(ms)
CLOUD_SCORE_LIMIT = 90  # 云库分数限制


# -----------------------------------------------------#
class GameMode(Enum):
    Free = auto()
    EngineAssit = auto()
    EngineFight = auto()
    Puzzle = auto()
    EngineOnline = auto()


GameTitle = {
    GameMode.Free: "自由练棋",
    GameMode.EngineAssit: "引擎辅助",
    GameMode.EngineFight: "人机对战",
    GameMode.Puzzle: "杀法挑战",
    GameMode.EngineOnline: "连线分析",
}


# -----------------------------------------------------#
class Stage(Enum):
    Begin = auto()
    End = auto()


class ReviewMode(Enum):
    ByEngine = auto()
    ByCloud = auto()


# -----------------------------------------------------#
class QGameManager(QObject):
    game_mode_changed_signal = pyqtSignal(GameMode, GameMode)
    review_mode_changed_signal = pyqtSignal(int, int)

    def __init__(self):
        super().__init__()
        self.gameMode = GameMode.Free
        self.reviewMode = None
        self.reviewType = None

    def getGameModeText(self):
        return GameTitle[self.gameMode]

    def setGameMode(self, mode):
        last_mode = self.gameMode
        self.gameMode = mode
        self.game_mode_changed_signal.emit(self.gameMode, last_mode)

    def reviewModeToggle(self, mode):
        if self.reviewMode is None:
            self.setReivewMode(mode, Stage.Begin)
        else:
            self.setReivewMode(mode, Stage.End)

    def setReivewMode(self, mode, stage):
        self.reviewMode = mode
        self.reviewStage = stage
        self.review_mode_changed_signal.emit(
            self.reviewMode.value, self.reviewStage.value
        )


# -----------------------------------------------------#
class ReviewMode(Enum):
    ByCloud = auto()
    ByEngine = auto()


# -----------------------------------------------------#
@dataclass
class Position:
    fen: str
    fen_prev: str
    iccs: str
    score: int
    index: int
    move_color: int
    move: Move


# Point = namedtuple('Point', ['x', 'y'])


# -----------------------------------------------------#
def scaleImage(img, scale):
    if scale == 1.0:
        return img

    new_height = int(img.height() * scale)
    new_img = img.scaledToHeight(new_height, mode=Qt.SmoothTransformation)

    return new_img


# -----------------------------------------------------#
def SvgToPixmap(svg, width, height):
    pix = QPixmap(QSize(width, height))
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHints(QPainter.Antialiasing)
    svg.render(painter)
    # pix.save('test.png')
    return pix


"""
#-----------------------------------------------------#
def cv2qt_image(image):

    size = image.shape
    step = int(image.size / size[0])
    qformat = QImage.Format_Indexed8

    if len(size) == 3:
        if size[2] == 4:
            qformat = QImage.Format_RGBA8888
        else:
            qformat = QImage.Format_RGB888

    img = QImage(image, size[1], size[0], step, qformat).rgbSwapped()

    return img

def cv2pil_image(cv_img):
    return Image.fromarray(cv.cvtColor(cv_img, cv.COLOR_BGR2RGB))

def pil2cv_image(pil_img):
    return cv.cvtColor(np.array(pil_img), cv.COLOR_RGB2BGR)

"""


# -----------------------------------------------------#
def trim_fen(fen):
    return " ".join(fen.split(" ")[:2])


def getStepsFromFenMoves(fen, moves):
    fen_steps = []
    board = ChessBoard(fen)
    for index, iccs in enumerate(moves):
        fen_steps.append([fen, iccs])
        move = board.move_iccs(iccs)
        if move is not None:
            board.next_turn()
            fen = board.to_fen()
        else:
            raise Exception(f"{index}-{iccs}")

    return fen_steps


def getStepsTextFromFenMoves(fen, moves):
    ok = True
    fen_steps = []
    board = ChessBoard(fen)
    for iccs in moves:
        move = board.move_iccs(iccs)
        board.next_turn()
        if move is not None:
            fen_steps.append(move.to_text())
        else:
            fen_steps.append(iccs)
            ok = False

    return (ok, fen_steps)


# -----------------------------------------------------#
def get_mac_address():
    mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
    return ":".join([mac[e : e + 2] for e in range(0, 11, 2)])


def getFreeMem():
    return psutil.virtual_memory().available / 1024 / 1024


# -----------------------------------------------------#
def getTitle():
    return Globl.APP_NAME_TEXT


# -----------------------------------------------------#
class ThreadRunner(QThread):
    def __init__(self, runner):
        super().__init__()
        self.runner = runner

    def run(self):
        self.runner.run()


# -----------------------------------------------------#
def loadEglib(lib_file):
    games = OrderedDict()

    with open(lib_file, "rb") as f:
        lines = f.readlines()

    for line in lines:
        it = line.strip().decode("utf-8")
        if it.startswith("#") or it == "":
            continue
        its = it.split("|")

        name = its[0]
        if name not in games:
            games[name] = {"name": name, "fen": its[1]}

        if len(its) == 3:
            games[name]["moves"] = its[2]

    return games.values()


# -----------------------------------------------------#
def loadEglibJson(lib_file):
    """从 .eglib.json 加载题库.

    JSON schema (顶层包对象,防劫持):
        {
            "version": 1,
            "games": [
                {"name": "...", "fen": "...", "moves": "..."},
                ...
            ]
        }
    ``moves`` 字段可选. 兼容 ``version`` 缺失的旧 JSON.
    """
    with open(lib_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    games = data["games"] if isinstance(data, dict) and "games" in data else data
    out = []
    for g in games:
        item = {"name": g["name"], "fen": g["fen"]}
        if "moves" in g and g["moves"]:
            item["moves"] = g["moves"]
        out.append(item)
    return out


def saveEglibJson(lib_file, games):
    """保存题库到 .eglib.json.

    ``games`` 为 list[dict],每项至少含 ``name``、``fen``,可选 ``moves``.
    顶层带 ``version`` 字段,便于未来 schema 演进.
    """
    payload = {"version": 1, "games": []}
    for g in games:
        item = {"name": g["name"], "fen": g["fen"]}
        if "moves" in g and g["moves"]:
            item["moves"] = g["moves"]
        payload["games"].append(item)
    with open(lib_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


# -----------------------------------------------------#
def loadCsvlib(lib_file):
    with open(lib_file, "r") as file:
        csv_reader = csv.DictReader(file)
        data = [row for row in csv_reader]

    return data


# -----------------------------------------------------#
class TimerMessageBox(QMessageBox):
    def __init__(self, text, timeout=2):
        super().__init__()
        self.setWindowTitle(getTitle())
        self.time_to_wait = timeout
        self.setText(text)
        self.setStandardButtons(QMessageBox.NoButton)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.changeContent)
        self.timer.start()

    def changeContent(self):
        self.time_to_wait -= 1
        if self.time_to_wait <= 0:
            self.close()

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()


# --------------------------------------------------------------#
class LongTextInputDialog(QInputDialog):
    """
    自定义 QInputDialog，使输入框更宽（默认 500 px，可自行调节）。
    同时支持单行（QLineEdit）或多行（QTextEdit）两种模式。
    """

    def __init__(
        self,
        title: str = "",
        label: str = "",
        parent=None,
        multiline: bool = False,
        width: int = 500,
    ):
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
            self.text_edit.setFixedHeight(100)  # 多行时给个合适高度
        else:
            self.text_edit = QLineEdit()
            self.text_edit.setMinimumWidth(self.desired_width)

        # 重新加入布局（QInputDialog 的布局是 QGridLayout）
        self.layout().addWidget(self.text_edit, 1, 0, 1, 2)

        # 让对话框自适应宽度
        self.resize(self.desired_width + 100, self.sizeHint().height())

    def textValue(self) -> str:
        return (
            self.text_edit.toPlainText().strip()
            if self.multiline
            else self.text_edit.text()
        )

    @staticmethod
    def getText(parent, title, label, text="", multiline=False, width=500):
        dialog = LongTextInputDialog(title, label, parent, multiline, width)
        dialog.setTextValue(text)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.textValue(), True
        return "", False


# -----------------------------------------------------#
def QueryFromCloudDB(fen, score_limit=None):
    if score_limit is None:
        score_limit = CLOUD_SCORE_LIMIT
    url = "http://www.chessdb.cn/chessdb.php"
    param = {"action": "queryall"}
    param["board"] = fen

    # 数据获取
    try:
        resp = requests.get(url, params=param, timeout=3)
    except Exception as e:
        print(e)
        return []

    text = resp.text.rstrip("\0")
    if text.lower() in ["", "unknown"]:
        return []

    board = ChessBoard(fen)
    move_color = board.get_move_color()
    moves = []

    # 数据分割
    try:
        steps = text.split("|")
        for it in steps:
            segs = it.strip().split(",")
            items = [x.split(":") for x in segs]
            it_dict = {key: value for key, value in items}
            # print(it_dict)
            moves.append(it_dict)
    except Exception:
        # traceback.print_exc()
        traceback.print_exception(*sys.exc_info())
        print("cloud query result:", text, "len:", len(text))

    # 添加中文走子标记
    for move in moves:
        move_it = board.copy().move_iccs(move["move"])
        if move_it:
            move["text"] = move_it.to_text()
        move["score"] = (
            -int(move["score"]) if move_color == BLACK else int(move["score"])
        )

    ret = []
    score_base = moves[0]["score"]
    for it in moves:
        it["diff"] = it["score"] - score_base
        if move_color == BLACK:
            it["diff"] = -it["diff"]
        if score_limit > 0 and abs(it["diff"]) > score_limit:
            continue
        ret.append(it)
    return ret


# -----------------------------------------------------#
BASE_URL = "https://www.wfmrwh.com/board_server"


# -----------------------------------------------------#
class BoardImageClient:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.headers = {
            # "Authorization": f"Bearer {token}"
        }

    def image_to_fen(self, img_file, time_out=30):
        try:
            with open(img_file, "rb") as f:
                files = {"image": (os.path.basename(img_file), f, "image/jpeg")}
                response = requests.post(
                    f"{self.base_url}/recognize",
                    headers=self.headers,
                    files=files,
                    # verify=False,
                    timeout=15,
                )

            if response.status_code == 200:
                data = response.json()
                if "status" not in data:
                    return {"status": "error", "raw": data}

                status = data["status"]
                if status in ["ok", "busy", "error"]:
                    return data

            else:
                return {
                    "status": "error",
                    "code": response.status_code,
                    "text": response.text,
                }

        except requests.exceptions.Timeout:
            return {"status": "error", "message": f"超时未响应"}
        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": str(e)}


# -----------------------------------------------------#


# -----------------------------------------------------#
def calc_move_diff(score, score_best, move_color):
    """计算着法与最佳着法的分数差

    Args:
        score: 当前着法分数（红方视角）
        score_best: 最佳着法分数（红方视角）
        move_color: 走棋方（cchess.RED 或 cchess.BLACK）

    Returns:
        int: 分数差，0 表示最佳着法，负数表示偏离最佳
    """
    diff = score - score_best
    if move_color == BLACK:
        diff = -diff
    return diff
