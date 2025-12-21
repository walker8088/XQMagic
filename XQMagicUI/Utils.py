# -*- coding: utf-8 -*-

import sys
import csv
import uuid
import traceback
from enum import Enum, auto
from dataclasses import dataclass
from collections import OrderedDict, namedtuple

import psutil
import requests

from PyQt5.QtCore import QTimer, QThread, Qt, pyqtSignal, QObject
from PyQt5.QtWidgets import QMessageBox, QApplication

#import numpy as np
#import cv2 as cv
#from PIL import Image

from . import Globl

from cchess import ChessBoard, Move, BLACK 

#-----------------------------------------------------#
class GameMode(Enum):
    Free = auto()
    EngineAssit = auto()
    EngineFight = auto()
    EngineEndGame = auto()
    EngineOnline = auto()

GameTitle = {
    GameMode.Free:          '自由练棋', 
    GameMode.EngineAssit:   '引擎辅助',
    GameMode.EngineFight:   '人机对战', 
    GameMode.EngineEndGame:  '杀法挑战', 
    GameMode.EngineOnline:  '连线分析',          
}

#-----------------------------------------------------#
class Stage(Enum):
    Begin = auto()
    End = auto()

class ReviewMode(Enum):
    ByEngine = auto()
    ByCloud = auto()

#-----------------------------------------------------#
class QGameManager(QObject):
    game_mode_changed_signal = pyqtSignal(GameMode, GameMode)
    review_mode_changed_signal = pyqtSignal(ReviewMode, Stage)
    
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
        self.review_mode_changed_signal.emit(self.reviewMode, self.reviewStage)

#-----------------------------------------------------#
class ReviewMode(Enum):
    ByCloud = auto()
    ByEngine = auto()

#-----------------------------------------------------#
@dataclass
class Position:
    fen: str
    fen_prev: str
    iccs:str
    score: int
    index: int
    move_color: int
    move: Move

#Point = namedtuple('Point', ['x', 'y'])

#-----------------------------------------------------#
def scaleImage(img, scale):

    if scale == 1.0:
        return img

    new_height = int(img.height() * scale)
    new_img = img.scaledToHeight(new_height, mode=Qt.SmoothTransformation)

    return new_img

#-----------------------------------------------------#
def SvgToPixmap(svg, width, height):
    pix = QPixmap(QSize(width, height))
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHints(QPainter.Antialiasing)
    svg.render(painter)
    #pix.save('test.png')
    return pix

'''
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

'''    
#-----------------------------------------------------#
def trim_fen(fen):
    return ' '.join(fen.split(' ')[:2])
    
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
            raise Exception(f'{index}-{iccs}')

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

#-----------------------------------------------------#
def get_mac_address():
    mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
    return ":".join([mac[e:e + 2] for e in range(0, 11, 2)])

def getFreeMem():
    return psutil.virtual_memory().available/1024/1024
        
#-----------------------------------------------------#
def getTitle():
    return Globl.APP_NAME_TEXT

#-----------------------------------------------------#
class ThreadRunner(QThread):
    def __init__(self, runner):
        super().__init__()
        self.runner = runner

    def run(self):
        self.runner.run()

#-----------------------------------------------------#
def loadEglib(lib_file):
    games = OrderedDict()

    with open(lib_file, 'rb') as f:
        lines = f.readlines()

    for line in lines:
        it = line.strip().decode('utf-8')
        if it.startswith('#') or it == '':
            continue
        its = it.split('|')

        name = its[0]
        if name not in games:
            games[name] = {'name': name, 'fen': its[1]}

        if len(its) == 3:
            games[name]['moves'] = its[2]

    return games.values()

#-----------------------------------------------------#
def loadCsvlib(lib_file):
    with open(lib_file, 'r') as file:
        csv_reader = csv.DictReader(file)
        data = [row for row in csv_reader]
        
    return data

#-----------------------------------------------------#
class TimerMessageBox(QMessageBox):
    def __init__(self, text, timeout = 2):
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

     
#-----------------------------------------------------#
def QueryFromCloudDB(fen, score_limit = 70):
    url = 'http://www.chessdb.cn/chessdb.php'
    param = {"action": 'queryall'}
    param['board'] = fen
    
    #数据获取
    try:
        resp = requests.get(url, params=param,  timeout = 3)
    except Exception as e:
        print(e)
        return []
        
    text = resp.text.rstrip('\0')
    if text.lower() in ['', 'unknown']:
        return []

    board = ChessBoard(fen)
    move_color = board.get_move_color()    
    moves = []
    
    #数据分割
    try:
        steps = text.split('|')
        for it in steps:
            segs = it.strip().split(',')
            items =[x.split(':') for x in segs]
            it_dict = {key:value for key, value in items}
            #print(it_dict)
            moves.append(it_dict)
    except Exception:
        #traceback.print_exc()
        traceback.print_exception(*sys.exc_info())
        print('cloud query result:', text, "len:", len(text))
    
    #添加中文走子标记       
    for move in moves:
        move_it = board.copy().move_iccs(move['move'])
        if move_it:
            move['text'] = move_it.to_text()
        move['score'] = -int(move['score'])  if move_color == BLACK  else  int(move['score'])
    
    ret =[]
    score_base = moves[0]['score']
    for it in moves:
        it['diff'] =  it['score'] - score_base
        if move_color == BLACK :
            it['diff'] = -it['diff']
        if  score_limit > 0 and abs(it['diff']) >  score_limit:
                continue
        ret.append(it)       
    return  ret        
