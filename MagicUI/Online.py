
import os
import time
import json
import datetime as dt
from collections import defaultdict, namedtuple
from pathlib import Path

import cv2 as cv
import numpy as np

from PIL import Image, ImageDraw, ImageOps, ImageGrab
#from PIL.ImageQt import ImageQt

from PyQt5 import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

import pygetwindow as gw

import cchess
from cchess import ChessBoard

from .Utils import scaleImage, TimerMessageBox, ThreadRunner

Point = namedtuple('Point', ['x', 'y'])
Size = namedtuple('Size', ['width', 'height'])

#-----------------------------------------------------------------------------------------#      
pieces_pos = {
    'K': (4, 0),
    'k': (4, 9),
    'A': (3, 0),
    'a': (3, 9),
    'B': (2, 0),
    'b': (2, 9),
    'N': (1, 0),
    'R': (0, 0),
    'C': (1, 2),
    'P': (0, 3),
    'p': (0, 6),
}

FEN_EMPTY = '9/9/9/9/9/9/9/9/9/9'
FEN_FULL = 'rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR'
FEN_FULL_LOWER = FEN_FULL.lower()


#-----------------------------------------------------------------------------------------#  
def image_cv2qt(image):

    size = image.shape
    step = int(image.size / size[0])
    qformat = QImage.Format_Indexed8

    if len(size) == 3:
        if size[2] == 4:
            qformat = QImage.Format_RGBA8888
        else:
            qformat = QImage.Format_RGB888

    img = QImage(image.data.tobytes(), size[1], size[0], step, qformat).rgbSwapped()

    return img

def image_qt2cv(img):
    incomingImage = img.convertToFormat(QImage.Format_RGB32)
    
    width = img.width()
    height = img.height()

    ptr = incomingImage.bits()
    ptr.setsize(incomingImage.byteCount())
    
    arr = np.array(ptr).reshape(height, width, 4)
    return cv.cvtColor(arr, cv.COLOR_RGBA2RGB)
    
#-----------------------------------------------------------------------------------------#  
def image_cv2pil(img_cv): 
    return Image.fromarray(cv.cvtColor(img_cv, cv.COLOR_BGR2RGB))

def image_pil2cv(img_pil): 
    return cv.cvtColor(np.array(img_pil), cv.COLOR_RGB2BGR)

#-----------------------------------------------------------------------------------------#      
class NumpyArrayEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)

#-----------------------------------------------------------------------------------------#      
def outRect(points):
    x_list = [p.x for p in points]
    y_list = [p.y for p in points]

    return(min(x_list), min(y_list), max(x_list), max(y_list))

def circleInnerRect(x, y, radius):
    v = int(radius / 1.5)
    return (x-v, y-v, x+v, y+v)
        

#-----------------------------------------------------------------------------------------# 
class ImageSource():
    def __init__(self):
        pass
    
#-----------------------------------------------------------------------------------------        
class MovieSource():

    def open(self, file_name):
        self.movie = cv.VideoCapture(file_name)
        
        ok, frame = self.movie.read()
        if not ok:
            return False
            
        self.height, self.width = frame.shape[:2]
        
        self.start_x = 0 #self.width//5
        self.end_x = self.width #- self.width//5
        
        return True
    
    def get_image(self):
        ok, frame = self.movie.read()      
        
        if not ok:
            return None
        
        for x in range(1):
            ok, frame_new = self.movie.read()      
            
            if not ok:
                break
            
            frame = frame_new
        
        return frame
        
    def get_image_roi(self, roi_rect = None):
    
        ok, frame = self.movie.read()      
        if not ok:
            return None
        
        if roi_rect is not None:    
            img_roi = cv.split(frame[roi_rect[0][1]:roi_rect[1][1], roi_rect[0][0]:roi_rect[1][0]])[0]

        for x in range(25):
            ok, new_frame = self.movie.read()
            if not ok:
                break
            
            if roi_rect is not None:
                img_new_roi = cv.split(new_frame[roi_rect[0][1]:roi_rect[1][1], roi_rect[0][0]:roi_rect[1][0]])[0]

                chang_count = 0
                change = cv.absdiff(img_roi, img_new_roi)
    
                #cv.imshow('INIT BOARD',img_new_roi)
                #cv.waitKey(0)

                for y in range(change.shape[0]):
                    for x in range(change.shape[1]):
                        p = change[y, x]
                        if p > 15:
                            chang_count += 1
                
                #print(chang_count)            
                if chang_count < 500:
                    break
                
                img_roi = img_new_roi                
            frame = new_frame        
        
        return frame 

#-----------------------------------------------------------------------------------------------------
class ScreenSource():
    
    def __init__(self):
    
        self.app = None
        self.win = None
        self.title = ''
        self.img = None
        
    def connect(self, window_title, marge):

        self.win = None
        windows = gw.getWindowsWithTitle(window_title)
        if len(windows) == 0:
            return False

        self.win = windows[0]
        self.title = window_title
        self.marge = marge
        
        return True
    
    def is_connected(self):
        return not (self.win is None)

    def move_click(self, s_move):
        mouse.click(button='left', coords = s_move[0])
        time.sleep(0.3)
        mouse.click(button='left', coords = s_move[1])
        time.sleep(0.2)
        mouse.move(coords=(0, 0))
        
    def grab(self):
        
        if not self.title:
            return None

        windows = gw.getWindowsWithTitle(self.title)
        if len(windows) == 0:
            return None
        
        self.win = windows[0]
        self.win.activate()
        
        box = self.win.box

        bbox = (box.left + self.marge.x, 
                box.top + self.marge.y, 
                box.left + box.width - self.marge.x, 
                box.top + box.height - self.marge.y) 
        
        #left = int(box.width * 355 / 2625.0)
        #top = int(box.height * 60 / 1455.0)
        #right = int(box.width * 1515 / 2625.0)
        #bottom = int(box.height * 1255 / 1455.0)

        try:
            img_pil = ImageGrab.grab(bbox)
        except Exception as e:
            return None

        #img_board = img.crop((left, top, right, bottom))
        return img_pil

#-----------------------------------------------------------------------------------------#
class OnlineManager(QObject):

    readySignal = pyqtSignal(int, str, list)
    moveSignal = pyqtSignal(int, dict)
    moveInfoSignal = pyqtSignal(int, dict)
    
    def __init__(self, parent):
        super().__init__()

        self.parent = parent
        self.source = ScreenSource()
        
        self.board_pos = Point(0, 0)
        self.board_size = Size(0, 0)
        self.board_grid = Size(0, 0)
        
        self.piece_radius = 0
        self.piece_points = []
        self.piece_tmpl = {}
    
        self.img_size = Size(0, 0)    
        self.img = None
    
        self.roi_pos = Point(0, 0)
        self.roi_size = Size(0, 0)
        
        self.schemas = {}
    
        self.isRunning = False
        self.thread = None

    def start(self):
        self.thread = ThreadRunner(self)
        self.thread.start()

    def stop(self):
        self.isRunning = False
    
    def run(self):
        self.isRunning = True
        while self.isRunning:
            try:
                self.run_board()
            except Exception as e:
                logging.error(str(e))
            time.sleep(0.1)
        #self.engine.stop_thinking()

    def run_board(self):
        img = self.grab_image()
        if img is None:
            return None
        #self.boardImageView.updateImage(img)
        fen = self.to_fen()

    def is_ready(self):
        return self.source.is_connected()
    
    def set_roi(self, roi_pos, roi_size):
        self.roi_pos = roi_pos
        self.roi_size = roi_size

    def grab_image(self):
        
        img_pil = self.source.grab()
        if img_pil is None:
            return None

        self.img_cv = image_pil2cv(img_pil)
        
        self.img_base = QPixmap.fromImage(image_cv2qt(self.img_cv))
        self.img_size = Size(self.img_base.width(), self.img_base.height())

        return self.img_base

    def point_board_to_image(self, pt,  bias = 0):

        board_x = self.board_pos.x + self.board_grid.width * pt.x
        board_y = self.board_pos.y + self.board_grid.height * (9 - pt.y)

        return Point(int(board_x + bias), int(board_y + bias))

    def point_image_to_board(self, pt):

        x = int((pt.x - self.board_pos.x) / self.board_grid.width)
        y = 9 - int((pt.y - self.board_pos.y) / self.board_grid.height)

        if self.flip_board:
            x = 8 - x
            y = 9 - y

        return Point(x, y)
    
    def get_piece_img(self, pt, gray = False, small = False):
  
        pos = self.point_board_to_image(pt)
        radius = self.piece_radius / 1.2 if small else self.piece_radius 
        left, top, right, bottom = circleInnerRect(pos.x, pos.y, radius)
            
        im = self.img_cv[top : bottom, left :right] 
        
        return im
            
    def detect_board(self):
        
        img_src = self.img_cv.copy()
        
        # 图像预处理
        gray = cv.cvtColor(img_src, cv.COLOR_BGR2GRAY)
        
        '''
        self.gause_times = 1
        for i in range(self.gause_times):
            gray = cv.GaussianBlur(gray, (5, 5),0)
        '''
        
        r_min = self.roi_size.width // 40
        r_max = int(r_min * 2)
        
        #圆检测
        circles = cv.HoughCircles(gray, cv.HOUGH_GRADIENT_ALT, 1, r_min*2, param1=100, param2=0.9, minRadius=r_min, maxRadius=r_max)
        if circles is None:
            return False
        
        roiRect = QRect(self.roi_pos.x, self.roi_pos.y, self.roi_size.width, self.roi_size.height)
        
        #先找到出现最多的那个圆半径
        radius_dict = defaultdict(int)
        for x, y, r in circles[0,:]: 
            if not roiRect.contains(int(x), int(y)):
                continue
            radius_dict[int(r)] += 1
        
        if len(radius_dict) == 0:
            return False

        self.piece_radius = sorted(radius_dict.items(), key = lambda x: x[1])[-1][0]
        self.piece_radius -= 2

        #print(r_min, r_max, self.piece_radius)

        color = (0, 255, 0)
        self.piece_points = []
        
        for x, y, _ in circles[0,:]: 
            x, y = int(x), int(y)
            if not roiRect.contains(x, y):
                continue
            self.piece_points.append(Point(x,y))
            cv.circle(img_src, (x, y), self.piece_radius, color, 1)
            
        left, top, right, bottom = outRect(self.piece_points)
        
        self.board_pos = Point(left, top)
        self.board_size = Size(right-left+1 , bottom-top+1)
        self.board_grid = Size(self.board_size.width/8, self.board_size.height/9)
        
        cv.rectangle(img_src, (left, top), (right, bottom), (0, 0, 255), 1)
                        
        self.img_roi = QPixmap.fromImage(image_cv2qt(img_src))
        
        return True

    def match_board(self, board, is_flip = False):
        
        img_src = self.img_cv.copy()

        self.piece_tmpl = {}
        miss_count = 0
        for piece in board.get_pieces():
            xx = 8-piece.x if is_flip else piece.x
            yy = 9-piece.y if is_flip else piece.y
            pt = Point(xx, yy) 
            pos = self.point_board_to_image(pt)
            color = (255, 0, 0) if piece.fench.islower() else (0, 0, 255)    
            left, top, right, bottom = circleInnerRect(pos.x, pos.y, self.piece_radius)
            #cv.rectangle(img_src, (left, top), (right, bottom), color, 1)
            rect = QRect(left, top, right - left + 1, bottom - top + 1)        
            found = False
            for p in self.piece_points:
                if rect.contains(p.x, p.y):
                    #cv.rectangle(img_src, (left, top), (right, bottom), color, 1)
                    #cv.circle(img_src, pos, self.piece_radius+5, color, 1)
                    found = True
                    fench = piece.fench
                    if fench not in self.piece_tmpl:
                        self.piece_tmpl[fench] = self.get_piece_img(pt, gray = False, small = False)
                        #cv.imwrite(str(Path('Online',f'{piece.get_color_fench()}.jpg')), self.piece_tmpl[fench])
                    break
            if not found:
                miss_count += 1

        for y in range(10):
            for x in range(9):
                pt = Point(x, y)
                pos = self.point_board_to_image(pt)
                img = self.get_piece_img(pt, small = True)
                fench, max_match, _ = self.detect_piece(img)
                if not fench:
                    continue
                color = (255, 0, 0) if fench.islower() else (0, 0, 255)
                name = fench #cchess.fench_to_text(fench)    
                if max_match > 0.9:
                    img_src = cv.putText(img_src, name, tuple(pos), cv.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        
        self.img_roi = QPixmap.fromImage(image_cv2qt(img_src))
        
    def to_fen(self):
        
        pieces = []
        img_src = self.img_cv.copy()
        for y in range(10):
            for x in range(9):
                pt = Point(x, y)
                pos = self.point_board_to_image(pt)
                img = self.get_piece_img(pt, small = True)
                fench, max_match, img_match = self.detect_piece(img)
                if not fench:
                    continue
                color = (255, 0, 0) if fench.islower() else (0, 0, 255)
                name = fench #cchess.fench_to_text(fench)    
                if max_match > 0.7:
                    #print(x, y, fench, max_match)
                    pieces.append((fench, pt))
                    #cv.circle(img_src, tuple(pos), self.piece_radius+2, color, 1)
                    img_src = cv.putText(img_src, name, tuple(pos), cv.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                    
                    #file_name = os.path.join('Game', f'match_{fench}_{x}_{y}.png') 
                    #cv.imencode(ext='.png', img=img_match)[1].tofile(file_name)
    
        self.img_roi = QPixmap.fromImage(image_cv2qt(img_src))
      
        #根据将帅的位置检测棋盘翻转
        flip = False
        for fench, pt in pieces:
            if fench == 'k' and pt.y < 5:
                flip = True

        board = ChessBoard()
        for fench, pt in pieces:
            x, y = pt
            if flip:
                x = 8-pt.x
                y = 9-pt.y
            board.put_fench(fench, (x, y))    
        
        return board.to_fen()

    def detect_piece(self, img_src):
        ret = None
        max_match = 0.0 
        for key, img_tmpl in self.piece_tmpl.items():
            #print(img_src.shape, img_tmpl.shape)
            
            result = cv.matchTemplate(img_src, img_tmpl, cv.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv.minMaxLoc(result)
            #print(min_val, max_val)
            if max_val > max_match:
                max_match = max_val
                ret = key
        
        img = None
        if max_match > 0.8:
            bottom,right = img_src.shape[:2]
            im = self.piece_tmpl[ret][0:bottom, 0:right] 
        
            img = np.concatenate((img_src, im), axis=0)
            
        return (ret, max_match, img)
        
    def to_schema(self, name):

        if name not in self.schemas:
            self.schemas[name] = {}
        
        templ = self.schemas[name]
            
        base = self.img_size.width

        templ['img'] = self.img_size,
        templ['roi'] = [self.roi_pos.x / base, self.roi_pos.y / base,
                        self.roi_size.width / base, self.roi_size.height / base]
        
        templ['board'] = [self.board_pos.x / base, self.board_pos.y  / base,
                        self.board_size.width / base, self.board_size.height / base]

        templ['piece_radius'] = self.piece_radius / base
        templ['title'] = self.source.title
        templ['name'] = name
        
        self.save_schema_image(name)
        
        return templ

    def use_schema(self, name):

        if name not in self.schemas:
            return False

        templ = self.schemas[name]        
        self.curr_schema = templ
        
        base = self.img_size.width
        if base == 0:
            base = templ['img'][0][0]
            
        item = templ['roi'] 
        self.roi_pos = Point(int(base * item[0]), int(base * item[1]))
        self.roi_size = Size(int(base * item[2]), int(base * item[3]))
        
        item = templ['board']
        self.board_pos = Point(int(base * item[0]), int(base * item[1]))
        self.board_size = Size(int(base * item[2]), int(base * item[3]))
        
        self.board_grid = Size(self.board_size.width/8, self.board_size.height/9)
        
        self.piece_radius = int(templ['piece_radius'] * base)
        
        return self.load_schema_image(name)
        
    def save_schema(self):
        templs = json.dumps(self.schemas)
        with open(self.schema_file, 'w', encoding = 'utf-8') as f:
            f.write(templs)

    def save_schema_image(self, name):        
        img_row = []
        for i in range(2):    
            imgs = []
            for fench in ['k', 'a', 'b', 'n', 'r', 'c', 'p']:
                if i==1:
                    fench = fench.upper()
                imgs.append(self.piece_tmpl[fench])
            img_line = np.concatenate(imgs, axis=1)
            img_row.append(img_line)
        
        img_save = np.concatenate(img_row, axis=0)
        file_name = os.path.join('Game', f'{name}.png') 
        cv.imencode(ext='.png', img=img_save)[1].tofile(file_name)
    
    def load_schema_image(self, name):
        
        file_name = Path('Game', f'{name}.png') 
        
        if not file_name.is_file():
            return False

        image = cv.imdecode(np.fromfile(file=str(file_name), dtype=np.uint8), cv.IMREAD_COLOR)     
        if image is None:
            return False

        img_height, img_width = image.shape[:2]
        
        piece_width = img_width//7
        piece_height = img_height//2 

        for row in range(2):    
            imgs = []
            for col, fench in enumerate(['k', 'a', 'b', 'n', 'r', 'c', 'p']):
                if row == 1:
                    fench = fench.upper()

                left = col * piece_width
                right = (col + 1) * piece_width
                top = row * piece_height
                bottom = (row + 1) * piece_height
                
                self.piece_tmpl[fench] = image[top : bottom, left :right]
        
        return True 

    def load_schema_file(self, templ_file):
        self.schema_file = templ_file
        if templ_file.is_file(): 
            with open(templ_file, 'r', encoding = 'utf-8') as f:
                self.schemas = json.load(f)
                    
    def get_schema_names(self, win_title = None):
        names = []
        for name, templ in self.schemas.items():
            if (not win_title) or (templ['title'] == win_title):
                names.append(name)
        return names

#-----------------------------------------------------------------------------------------------------
class BoardImageView(QWidget):
    roiBeginSignal = pyqtSignal()
    roiEndSignal = pyqtSignal()
    
    def __init__(self, parent = None):

        super().__init__(parent)
    
        self.setAutoFillBackground(True)

        p = self.palette()
        p.setColor(self.backgroundRole(), QColor(40, 40, 40))
        self.setPalette(p)
        
        self.roi_pos = Point(0, 0)
        self.roi_size = Size(0, 0)
    
        self.roiRect = None

        self.useCutRoi = False
        self.isCutting = False

        self.img_size = Size(0, 0)
        
        self.img = None
        self.img_roi = None
        
        self.is_recting = False
        
    def set_roi(self, roi_pos, roi_size):
        self.roi_pos = roi_pos
        self.roi_size = roi_size

    def resizeEvent(self, ev):
        pass
                
    def updateImage(self, img):

        self.img_roi = None
        self.img = img
        self.img_size = Size(self.img.width(), self.img.height())
        
        self.update()

    def setCuttingMode(self, yes):

        self.isCutting = yes
        self.update()

    def paintEvent(self, ev):

        painter = QPainter(self)
        
        if self.img_roi:
            painter.drawPixmap(0,  0, self.img_roi)
        elif self.img:
            painter.drawPixmap(0,  0, self.img)
        
        if self.roi_size.width > 0:
            pen = QPen(QColor(0, 255, 0), 2, QtCore.Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(self.roi_pos.x, self.roi_pos.y, self.roi_size.width, self.roi_size.height)
        
        #if self.board_size[0] > 0:
        #    painter.setPen(QColor(0, 0, 255))
        #    painter.drawRect(self.board_pos.x, self.board_pos.y, self.board_size[0], self.board_size[1])
                  

    def mousePressEvent(self, mouseEvent):
        
        if (mouseEvent.button() != Qt.LeftButton):
            return
        
        if not self.isCutting:
            return

        self.is_recting = True
       
        pos = mouseEvent.pos()
        
        self.roi_pos = Point(pos.x(), pos.y())
        self.roi_size = Size(0, 0)
        
        self.update()
        self.roiBeginSignal.emit()
        
    def mouseMoveEvent(self, mouseEvent):
        
        if not self.is_recting:
            return
                
        pos = mouseEvent.pos()
        x, y = pos.x(), pos.y()
        
        if x < 0:
            x = 0
        if x >= self.img_size.width:
            x = self.img_size.width - 1     
        
        if y < 0:
            y = 0
        if y >= self.img_size.height:
            y = self.img_size.height - 1     
        
        if x < self.roi_pos.x:
            new_width = self.roi_pos.x - x + 1
            new_x = x
        else:
            new_with = x - self.roi_pos.x + 1
            new_x = self.roi_pos.x

        if y < self.roi_pos.y:
            new_height = self.roi_pos.y - y + 1
            new_y = y
        else:
            new_height = y - self.roi_pos.y + 1
            new_y = self.roi_pos.y
        
        self.roi_pos = Point(new_x, new_y)
        self.roi_size = Size(new_with, new_height)
        
        self.update()
            
    def mouseReleaseEvent(self, mouseEvent):
        if (mouseEvent.button() != Qt.LeftButton):
            return
    
        self.is_recting = False
        self.isCutting = False
        
        #self.roiRect = QRect(self.roi_pos.x, self.roi_pos.y, self.roi_size.width, self.roi_size.height)    
        
        self.update()
        self.roiEndSignal.emit()
        
     
#-----------------------------------------------------------------------------------------#
class OnlineDialog(QDialog):
    def __init__(self, parent, manager):
        super().__init__(parent)

        self.setWindowTitle("连线分析-方案编辑")
        self.setMinimumSize(600, 800)
        
        self.manager = manager

        self.boardImageView = BoardImageView(self)
        self.editModeBox = QCheckBox("方案编辑", self)
        self.editModeBox.stateChanged.connect(self.onEditModeBoxChanged)
    
        self.schemaNameEdit = QLineEdit('天天象棋', self)
        #self.schemaNameEdit.setEditable(True)
        #self.schemaNameEdit.currentIndexChanged.connect(self.onProjectChanged)
        
        self.titleEdit = QLineEdit('天天象棋', self)
        self.titleEdit.textChanged.connect(self.onTitleChanged)
        self.blackDownBox = QCheckBox("黑下红上", self)
        self.blackDownBox.stateChanged.connect(self.onBlackDownBoxChanged)

        self.fenEdit = QLineEdit('', self)

        hbox1 = QHBoxLayout()
        hbox1.addWidget(QLabel('窗口:'), 0)
        hbox1.addWidget(self.titleEdit, 0)
        hbox1.addWidget(QLabel('连线方案:'), 0)
        hbox1.addWidget(self.schemaNameEdit, 0)
        hbox1.addWidget(self.editModeBox, 0)
        hbox1.addWidget(QLabel(''), 1)

        hbox2 = QHBoxLayout()
        hbox2.addWidget(self.blackDownBox, 0)
        hbox2.addWidget(self.fenEdit, 0)

        self.captureBtn = QPushButton("窗口截图", self)
        self.captureBtn.clicked.connect(self.onCapture)
        self.cutAreaBtn = QPushButton("区域框选", self)
        self.cutAreaBtn.clicked.connect(self.onCutArea)
        
        self.detectBoardBtn = QPushButton("棋盘匹配", self)
        self.detectBoardBtn.clicked.connect(self.onDetectBoard)

        #self.matchBtn = QPushButton("棋子匹配", self)
        #self.matchBtn.clicked.connect(self.onMatch)
        
        self.toFenBtn = QPushButton("局面识别", self)
        self.toFenBtn.clicked.connect(self.onImageToFen)
        
        self.saveBtn = QPushButton("保存方案", self)
        self.saveBtn.clicked.connect(self.onSave)
        
        self.toFenWorkBtn = QPushButton("连续识别", self)
        self.toFenWorkBtn.clicked.connect(self.onImageToFenWork)
        
        okBtn = QPushButton("关闭", self)
        
        vbox = QVBoxLayout()
        vbox.addLayout(hbox1)
        vbox.addWidget(self.boardImageView, 2)
        #vbox.addWidget(self.fenEdit)
        vbox.addLayout(hbox2)

        hbox3 = QHBoxLayout()
        hbox3.addWidget(self.captureBtn)
        hbox3.addWidget(self.cutAreaBtn)
        hbox3.addWidget(self.detectBoardBtn)
        #hbox3.addWidget(self.matchBtn)
        hbox3.addWidget(self.toFenBtn)
        hbox3.addWidget(self.saveBtn)
        hbox3.addWidget(self.toFenWorkBtn)
        
        hbox3.addWidget(okBtn)
        #hbox3.addWidget(cancelBtn)

        vbox.addLayout(hbox3)
        self.setLayout(vbox)
        
        self.boardImageView.roiEndSignal.connect(self.onRoiEnd)
        
        okBtn.clicked.connect(self.accept)
        
        #self.editModeBox.setChecked(True)
        #templ_names = self.manager.get_schema_names()
        #self.schemaNameEdit.addItems(templ_names)
        
        self.onEditModeBoxChanged(False)

    def showEvent(self, event):

        if self.manager.source.is_connected():
            title = self.manager.source.title
            self.titleEdit.setText(title)
        
        else:
            win_rect = self.frameGeometry()
            inner_rect = self.geometry()
            
            self.capture_marge = Point(inner_rect.x() - win_rect.x(), inner_rect.y() - win_rect.y())
            
            for title in gw.getAllTitles():
                if len(title) > 12:
                    continue

                if ('象棋' in title) and ('神机象棋' not in title):
                    win = gw.getWindowsWithTitle(title)[0]
                    win.activate()
                    #top = win.topleft[0]
                    #win.moveTo(0, top)
                    #print(win.topleft)
                    self.titleEdit.setText(title)
                    
                    names = self.manager.get_schema_names(title)
                    #self.schemaNameEdit.clear()
                    #self.schemaNameEdit.addItems(names)
                    #self.schemaNameEdit.setCurrentIndex(0)

                    break
        
        roi_pos = self.manager.roi_pos
        roi_size = self.manager.roi_size
        self.boardImageView.set_roi(roi_pos,roi_size)

    def onTitleChanged(self, text):
        names = self.manager.get_schemas(text)
        #self.schemaNameEdit.clear()
        #self.schemaNameEdit.addItems(names)
        #self.schemaNameEdit.setCurrentIndex(0)

    def onProjectChanged(self, index):
        name = self.schemaNameEdit.text()
        if not self.manager.use_schema(name):
            return

        roi_pos = self.manager.roi_pos
        roi_size = self.manager.roi_size
    
        self.boardImageView.set_roi(roi_pos,roi_size)

    def onEditModeBoxChanged(self, state):            
        yes = self.editModeBox.isChecked()
        
        self.cutAreaBtn.setEnabled(yes)
        self.detectBoardBtn.setEnabled(yes)
        #self.matchBtn.setEnabled(yes)
        self.saveBtn.setEnabled(yes)
        
        if yes:
            self.captureBtn.setText("窗口截图")
        else:
            self.captureBtn.setText("截图识别")
            
    def onCapture(self):
        title= self.titleEdit.text()
        if self.manager.source.title != title:
            if not self.manager.source.connect(title, self.capture_marge):
                msgbox = TimerMessageBox(f"查找窗口【{title}】失败。")
                msgbox.exec()
                return
        
        print(self.manager.source.title)
                
        img = self.manager.grab_image()
        if img is None:
            msgbox = TimerMessageBox(f"截图【{title}】失败。请确认窗口是否存在。")
            msgbox.exec()
            return
            
        self.boardImageView.updateImage(img)
        
        if not self.editModeBox.isChecked():
            self.onImageToFen()

    def onCutArea(self):
        if not self.boardImageView.isCutting:
            self.boardImageView.setCuttingMode(True)
            self.cutAreaBtn.setText('取消框选')
        else:
            self.boardImageView.setCuttingMode(False)
            self.cutAreaBtn.setText('区域框选')
        
    def onRoiEnd(self):

        roi_pos = self.boardImageView.roi_pos
        roi_size = self.boardImageView.roi_size

        self.manager.set_roi(roi_pos,roi_size)
        self.cutAreaBtn.setText('区域框选')
        
    def onDetectBoard(self):
        if self.boardImageView.roi_size.width  < 5:
            msgbox = TimerMessageBox("请先用鼠标在截图上划出棋盘区域，再进行识别。")
            msgbox.exec()
            return

        if self.manager.detect_board():
            board = self.parent().board
            self.manager.match_board(board, self.blackDownBox.isChecked())
            self.boardImageView.updateImage(self.manager.img_roi)
        
    def onMatch(self):
        board = self.parent().board
        self.manager.match_board(board, self.blackDownBox.isChecked())    
        self.boardImageView.updateImage(self.manager.img_roi)
        
    def onImageToFen(self):
        fen = self.manager.to_fen()
        self.fenEdit.setText(fen)
        self.boardImageView.updateImage(self.manager.img_roi)
        
    def onImageToFenWork(self):
        
        #self.boardImageView.imageToFen()
        pass

    def onSelectBoard(self):
        pass

    def onSave(self):
        self.manager.to_schema(self.schemaNameEdit.text())
        self.manager.save_schema()

    def onBlackDownBoxChanged(self, state):
        #self.boardEdit.set_move_color(BLACK)
        pass

    def onBoardFenChanged(self, fen):

        self.fenEdit.setText(fen)

        color = self.boardEdit.get_move_color()
        if color == RED:
            self.redDownBtn.setChecked(True)
        elif color == BLACK:
            self.blackDownBtn.setChecked(True)
    
 
"""
#-----------------------------------------------------------------------------------------------------
class BoardScreen():
    def __init__(self, img = None, flip = False):
    
        self.flip = flip
        
        self.board_begin = [0,0]
        self.board_end = [0,0]
        self.grid_size = [0,0]
        
        self.piece_size = 0
        self.pieces_templ = {}
        
        self.black_index = 0
        
        self.match_precision = 0.7
        
        self.update(img)
        
    def update(self, img):
        
        self.img = img
        
        if self.img is None:
            self.img_gray = None
            self.img_red = None
        else:
            self.img_gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY) 
            b, g, self.img_red = cv.split(img) 
    
    def sizeHint(self): 
        return QSize(400, 400)
    
    def calc_grid(self):
        self.grid_size = [ (self.board_end[0] - self.board_begin[0])/8.0, (self.board_end[1] - self.board_begin[1])/9.0 ]
        
    def board_to_img(self, x, y):
        
        if self.flip:
            x = 8 - x
            y = 9 - y
            
        return (int(self.board_begin[0] + x * self.grid_size[0]), int(self.board_begin[1] + (9 - y) * self.grid_size[1]))
    
    def img_to_board(self, ix, iy):
        
        x = int((ix + self.piece_size - self.board_begin[0]) / self.grid_size[0])
        y = 9 - int((iy + self.piece_size - self.board_begin[1]) / self.grid_size[1])
        
        if self.flip:
            x = 8 - x
            y = 9 - y
        
        return (x, y)
        
        
    def board_move_to_screen(self, p_from, p_to):
        
        s_from = self.board_to_img(*p_from)
        s_to = self.board_to_img(*p_to)
        
        return (s_from, s_to)
    
    def get_roi_rect(self):
        return ((self.board_begin[0] - self.piece_size, self.board_begin[1] - self.piece_size), 
            (self.board_end[0] + self.piece_size, self.board_end[1] + self.piece_size))
    
    def pos_in_roi(self, pos):
        start, stop = self.get_roi_rect()
        
        if (start[0] <= pos[0] <= stop[0]) and (start[1] <= pos[1] <= stop[1]):
            return True
            
        return False
            
        
    def get_piece_img(self, x, y, gray = True, small = False):
  
        img_pos = self.board_to_img(x, y)
        
        if small:
            half_size = int(self.piece_size / 1.6)
        else:
            half_size = int(self.piece_size / 1.1)
            
        if gray:
            im = self.img_gray[img_pos[1] - half_size : img_pos[1] + half_size, img_pos[0] - half_size : img_pos[0] + half_size] 
        else:        
            im = self.img[img_pos[1] - half_size : img_pos[1] + half_size, img_pos[0] - half_size : img_pos[0] + half_size] 
        
        return im
    
    def make_schema(self, config_file_name):
        
        ok = self.auto_detect()
        if not ok:
            return False
            
        board = cchess.ChessBoard() 
        fen = self.to_fen(board)
        
        board.print_board()
        
        config = {
            'image_size': self.img_size,
            'board_begin': self.board_begin,
            'board_end': self.board_end,
            'piece_size': self.piece_size,
            'black_index': self.black_index,
            'match_precision': self.match_precision,
        }
        
        with open(f'{config_file_name}.json', "w") as f:
            json.dump(config, f, indent = 6)
        
        imgs = [self.pieces_templ[key] for key in pieces_pos]
        tmpl_img = cv.hconcat(imgs)
        
        cv.imwrite(f'{config_file_name}.png', tmpl_img)
        
    def load_schema(self, config_file_name):
        
        with open(f'{config_file_name}.json', "r") as f:
            config = json.load(f)
            self.img_size = config['image_size']
            self.board_begin = config['board_begin']
            self.board_end = config['board_end']
            self.piece_size = config['piece_size']
            self.black_index = config['black_index']
            self.match_precision = config['match_precision']
        
        self.calc_grid()
        
        img_src = cv.imread(f'{config_file_name}.png')     
        #print(img_src.shape)
        tmpl_img = cv.cvtColor(img_src, cv.COLOR_BGR2GRAY)
        height,width = tmpl_img.shape[:2]
        
        self.pieces_templ = {}    
        index = 0
        for index, key, in enumerate(pieces_pos):
            self.pieces_templ[key] = tmpl_img[0 : height, height * index: height * (index + 1)]
            
    def test_image(self, img):
    
        board = cchess.ChessBoard()
        self.update(img)
        
        fen = self.to_fen(board)
        
        return fen
        
    def auto_detect(self):
    
        img_src = self.img.copy()
        
        r_min = img_src.shape[1] // 60
        r_max = int(r_min * 4)
        
        # 图像预处理
        gray = cv.cvtColor(img_src, cv.COLOR_BGR2GRAY)
        #img = cv.medianBlur(gray, 7)
        gaussian = cv.GaussianBlur(gray, (7, 7),0)
        circles = cv.HoughCircles(gaussian,cv.HOUGH_GRADIENT,1, r_min, param1=100, param2=60, minRadius=r_min, maxRadius=r_max)
                                      
        if circles is None:
            return False
            
        #圆检测
        ims = []
        y_counts = {}
        #circles = np.uint16(np.around(circles))
        for x, y, r in circles[0,:]: 
            x, y, r = int(x), int(y), int(r) 
            #print(x, y, r)
            cv.circle(img_src, (x, y), r, (0, 255, 0), 1, cv.LINE_AA)
            im = img_src[y - r : y + r, x - r : x + r] 
            ims.append((im, x, y, r))
            
            find_y = False
            for y_key, y_count in y_counts.items():
                if abs(y - y_key) < r_min:
                    y_counts[y_key].append((x, y, r)) 
                    find_y = True
                    continue
            if not find_y:
                y_counts[y] = [(x, y, r)]
        
        #cv.imshow('CIRCLE BOARD', img_src)
        #cv.waitKey(0)
        
        x_points = []
        y_points = []
        r_min = -1
        
        img_src = self.img.copy()
                
        for y_key, it in y_counts.items():
            if len(it) == 9:
                for x, y, r in it:
                    #cv.circle(img_src, (x, y), r, (255, 0, 0), 1, cv.LINE_AA)
                    x_points.append(x)
                    y_points.append(y)
                        
                    if r_min < 0 or r < r_min:
                        r_min = r
                    
        board_rect = [min(x_points), min(y_points), max(x_points), max(y_points)]
        
        self.img_size = self.img.shape[:2]
        self.board_begin = board_rect[:2]
        self.board_end = board_rect[2:]
        self.calc_grid()
        self.piece_size = r_min
        
        cv.rectangle(img_src, self.board_begin, self.board_end, (255, 0, 0), 2)
        
        for x in range(9):
            for y in range(10):
                cv.circle(img_src, self.board_to_img(x, y), self.piece_size, (0, 0, 255), 1, cv.LINE_AA)
                pass
        
        cv.imshow('CIRCLE BOARD', img_src)
        cv.waitKey(0)
        
        #使用红色分量检测红黑分界线
        self.flip = False
        
        red_img = cv.split(self.get_piece_img(0, 0, gray = False))[2]
        red_hist = cv.calcHist([red_img],[0],None,[256],[0,256])
        red_sum = np.uint16(np.around(np.cumsum(red_hist)))
        
        black_img = cv.split(self.get_piece_img(0, 9, gray = False))[2]
        black_hist = cv.calcHist([black_img],[0],None,[256],[0,256])
        black_sum = np.uint16(np.around(np.cumsum(black_hist)))
        
        black_count = [0,0]
        for i in range(200):
            #print(black_sum[i],red_sum[i]) 
            if black_sum[i] == 0 and red_sum[i] == 0:
                black_count[0] = i
            
            elif black_sum[i] > 0 and red_sum[i] == 0: 
                black_count[1] = i
        #print('black_count', black_count)        
        
        self.black_index = (black_count[0] + black_count[1]) // 2
        
        self.init_pieces_schema()

        return True
        
            
    def init_pieces_schema(self):    
        #模板获取    
        for key, (x, y) in pieces_pos.items():
            img = self.get_piece_img(x, y, gray = True, small = True)
            self.pieces_templ[key] = img
        
    def detect_piece(self, img_src, match_precision):
        
        #d = pytesseract.image_to_data(img_src, lang = "chi_sim", output_type=Output.DICT)
        #print(d['text'])
        
        #cv.imshow('CIRCLE BOARD', img_src)
        #cv.waitKey(0)
        ret = None
        for key, img_tmpl in self.pieces_templ.items():
            result = cv.matchschema(img_src, img_tmpl, cv.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv.minMaxLoc(result)
            #print(min_val, max_val)
            if max_val > match_precision:
                ret = key
                break
        if ret:
            return ret
               
        return ret        
    
    def detect_piece_best(self, img_src):
    
        ret = None
        max_match = 0.0 
        for key, img_tmpl in self.pieces_templ.items():
            result = cv.matchschema(img_src, img_tmpl, cv.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv.minMaxLoc(result)
            #print(min_val, max_val)
            if max_val > max_match:
                max_match = max_val
                ret = key
        
        return (ret, max_match)
        
    
    '''
    def detect_filp(self):
    
        #红黑检测
        b,g,img_up = cv.split(self.get_piece_img(0, 9))
        b,g,img_down = cv.split(self.get_piece_img(0, 0))
        height,width = img_up.shape[:2]
        black_count = [0,0]
        
        for row in range(height):   
            for col in range(width):
                v = img_up[row][col]
                if v <= self.black_index:    
                    black_count[0] += 1
                
                v = img_down[row][col]
                if v <= self.black_index:    
                    black_count[1] += 1
        #up red
        if black_count[0] < black_count[1]:
            self.flip = True
            #self.black_count = (self.black_count[1], self.black_count[0])
    '''
    
    def detect_color(self, img):
        
        b,g,red = cv.split(img)
        
        height, width = img.shape[:2]
        
        b_count = 0
        for row in range(height):
            for col in range(width):         
                pv = red[row, col]
                #print(pv)
                if pv <= self.black_index:    
                    b_count += 1
        return 2 if b_count >= 5 else 1                
     
    def detect_pos_circles(self):
        
        img_src = self.img.copy()
        gray = cv.cvtColor(img_src, cv.COLOR_BGR2GRAY)
        gaussian = cv.GaussianBlur(gray, (5, 5),0)
        circles = cv.HoughCircles(gaussian,cv.HOUGH_GRADIENT, 1, self.piece_size * 2, param1 = 100, param2 = 40, minRadius = self.piece_size - 2, maxRadius = self.piece_size + 5)
        
        if circles is None:
            return []
            
        ims = []
        for x, y, r in circles[0,:]: 
            x, y, r = int(x), int(y), int(r) 
            bx, by = self.img_to_board(x, y)
            if (bx < 0) or (bx > 8) or (by < 0) or (by > 9): 
                continue
            #cv.putText(img_src, f'{bx}{by}', (x, y), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2, cv.LINE_AA)
            im = self.img_gray[y - r : y + r, x - r : x + r] 
            #cv.circle(img_src, (x, y), 5, (0, 0, 255), 2, cv.LINE_AA)
            ims.append((bx, by, im))
            
        #cv.imshow('INIT BOARD',img_src)
        #cv.waitKey(0)
        return ims
        
    def to_fen(self, board):
        
        board.clear()
        
        ims = self.detect_pos_circles()
        for x, y, img in ims:
            #img = self.get_piece_img(x, y)
            #cv.imshow('INIT BOARD',img)
            #cv.waitKey(0)
        
            ret, max_match = self.detect_piece_best(img)   
            #ret = self.detect_piece(img, self.match_precision)
            if ret:
                if ret.isupper(): #红色才需要进一步测试颜色，黑色棋子根据模板已经识别出来了
                    c_img = self.get_piece_img(x, y, gray = False, small = True)
                    color = self.detect_color(c_img)
                
                    if color == 1:
                        fen_ch = ret.upper() 
                    else:
                        fen_ch = ret.lower()
                else:
                    fen_ch = ret
                
                board.put_fench(fen_ch, (x, y))
            else:
                
                fen_ch, max_match = self.detect_piece_best(img)
                print("circle empty", x, y, fen_ch, max_match)
                
        '''
        for x in range(9):
            for y in range(10):
                img = self.get_piece_img(x, y)
                ret = self.detect_piece(img)
                if ret:
                    if ret: #.isupper(): #红色才需要进一步测试颜色，黑色棋子根据模板已经识别出来了
                        img_small = self.get_piece_img(x, y, small = True) 
                        color = self.detect_color(img_small)
                    
                        if color == 1:
                            fen_ch = ret.upper() 
                        else:
                            fen_ch = ret.lower()
                    else:
                        fen_ch = ret
                        
                    if self.flip:
                        x = 8 - x
                        y = 9 - y
                    
                    board.put_fench(fen_ch, (x, y))
        '''
        
        return board.to_fen_base().split(' ')[0]
        
    def show_grid(self):
        
        img_src = self.img.copy()
        
        #board_end = (self.board_begin[0] + self.grid_size[0]*8, self.board_begin[1] + self.grid_size[1]*9)
        #cv.rectangle(img_src, self.board_begin, board_end, (255, 0, 0), 1)
        
        for x in range(9):
            for y in range(10):
                #cv.circle(img_src, self.board_to_img(x, y), self.piece_size, (0, 0, 255), 2, cv.LINE_AA)
                pass
                
        cv.imshow('INIT BOARD',img_src)
        cv.waitKey(0)
        
    def show_move(self, s_move):
        
        s_from, s_to = s_move
        
        img_src = self.img.copy()
        
        cv.circle(img_src, s_from, 6, (0, 0, 255), 2, cv.LINE_AA)
        cv.circle(img_src, s_to, 6, (0, 255, 0), 2, cv.LINE_AA)
                
        cv.imshow('INIT BOARD',img_src)
        cv.waitKey(0)
                
    

class GameMaster():
    def __init__(self, screen, img_src, engine):
        
        self.screen = screen
        self.img_src = img_src
        
        self.engine = engine
        self.board = cchess.ChessBoard() 
        
        self.player = None
    
    
    '''        
    def start_recording(self):
        file_name = f'videos\{dt.datetime.now().strftime("%Y%m%d_%H%M%S%f")}.mp4'
        img_size = self.img.shape[:2]
        self.video_writer = cv.VideoWriter(file_name, cv.VideoWriter_fourcc(*'mp4v'), 15, img_size)
        
    def stop_recording(self):
        self.video_writer.release()
    '''
    
    
    def wait_for_init(self):
        
        board_new = cchess.ChessBoard()
        
        while True:
            img = self.img_src.get_image()
            
            if img is None:
                break
                
            self.screen.update(img)
            
            new_fen = self.screen.to_fen(board_new)
            #print(new_fen)
            if new_fen == FEN_EMPTY:
                continue
            
            if new_fen[0].isupper():
                self.screen.flip = True
                #print(self.screen.flip)
                #new_fen = self.screen.to_fen(board_new)
                #self.board.from_fen(new_fen)
            
            break
            
        self.player = cchess.ChessPlayer(cchess.BLACK) if self.screen.flip  else cchess.ChessPlayer(cchess.RED)
        
        print("Play", self.player)
        
        return True
       
    def run(self):
        
        #self.board.move_player = cchess.ChessPlayer(cchess.RED)
        last_fen = self.screen.to_fen(self.board)
        print('init', last_fen)
        self.board.print_board()
        
        board_new = cchess.ChessBoard()
        
        while True:
            
            img = self.img_src.get_image()
            
            if img is None:
                break
            
            self.screen.update(img)
            
            new_fen = self.screen.to_fen(board_new)
            
            if new_fen != last_fen:
                #print(new_fen)
                #print(board_new.to_fen())    
                #return
                
                m = self.board.detect_move_pieces(board_new)
                
                print(m)
                board_new.print_board()
                
                if (len(m[0]) != 1) or (len(m[1]) != 1):
                    pass
                    
                else:    
                    move_it = self.board.create_move_from_board(board_new)
                        
                    if not move_it:
                        continue
                    
                    color = self.board.get_fench_color(move_it[0])
                    move = self.board.move(move_it[0], move_it[1])
                    print(move_it, move.to_chinese())
                    
                    self.board.move_player.color = color 
                    self.board.move_player.next()
                    
                    print('board_play:', self.board.move_player, 'my_play:', self.player)
                    
                    last_fen = new_fen
                    
                    if self.board.move_player == self.player:
                        self.engine.go_from(self.board.to_fen())
                        tmp_board = self.board.copy()
                        while True:
                            print('.')
                            self.engine.handle_msg_once()
                            if self.engine.move_queue.empty():
                                time.sleep(0.2)
                                continue
                            output = self.engine.move_queue.get()
                            action = output['action']
                            if action == 'best_move':
                                p_from, p_to = output["move"]
                                print("Engine move", p_from, p_to)
                                move_str = tmp_board.move(p_from, p_to).to_chinese()
                                print(move_str)
                                s_move = self.screen.board_move_to_screen(p_from, p_to)
                                print(s_move)
                                #self.screen.show_move(s_move)
                                self.img_src.move_click(s_move)
                                break
                            elif action == 'dead':
                                dead = True
                                break
                            elif action == 'draw':
                                dead = True
                                break
                            elif action == 'resign':
                                dead = True
                                break    
                

"""
#-----------------------------------------------------#
