
# Refer to https://github.com/harupy/snipping-tool

from PIL import Image, ImageGrab
#from PIL.ImageQt import ImageQt

from PyQt5.QtCore import Qt,QSize, QPoint, QRect, QRectF 
from PyQt5.QtGui import QCursor, QPixmap, QPainter,QPen,QColor
from PyQt5.QtWidgets import QApplication,QWidget

#--------------------------------------------------------------------------------
class QScreenGrab():

    def __init__(self, parent):
        self.parent = parent
        self.screen = QApplication.primaryScreen()
        self.screen_ratio =  self.screen.grabWindow(0).width() / self.screen.size().width() 

    def grabRect(self, begin, end):
        
        pixmap = self.screen.grabWindow(0)
        self.screen_ratio =  pixmap.width() / self.screen.size().width() 
        
        x1 = int(min(begin.x(), end.x()) * self.screen_ratio)
        y1 = int(min(begin.y(), end.y()) * self.screen_ratio)
        x2 = int(max(begin.x(), end.x()) * self.screen_ratio)
        y2 = int(max(begin.y(), end.y()) * self.screen_ratio)
        
        img = pixmap.copy(x1, y1, x2 - x1 + 1, y2 - y1 + 1)
        
        new_height = int(img.height() / self.screen_ratio) 
        new_img = img.scaledToHeight(new_height, mode=Qt.SmoothTransformation)

        return new_img


#--------------------------------------------------------------------------------
class SnippingWidget(QWidget):
    is_snipping = False

    def __init__(self):
        super().__init__()

        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        
        self.screen = QApplication.primaryScreen()
        self.screen_width = self.screen.size().width()
        self.screen_height = self.screen.size().height()
        self.setGeometry(0, 0, self.screen_width, self.screen_height)

        self.grab = QScreenGrab(self)

        self.begin = QPoint()
        self.end = QPoint()
        self.onSnippingCompleted = None
    
    def fullscreen(self):
        img = ImageGrab.grab(bbox=(0, 0, self.screen.size().width(), self.screen.size().height()))
            
        if self.onSnippingCompleted is not None:
            self.onSnippingCompleted(img)
            
    def start(self):
        SnippingWidget.is_snipping = True
        self.setWindowOpacity(0.3)
        QApplication.setOverrideCursor(QCursor(Qt.CrossCursor))
        self.show()

    def paintEvent(self, event):
            
        if SnippingWidget.is_snipping:
            brush_color = (128, 128, 255, 100)
            lw = 3
            opacity = 0.3    
        else:
            brush_color = (0, 0, 0, 0)
            lw = 0
            opacity = 0
        
        qp = QPainter(self)
        qp.setPen(QPen(QColor('black'), lw))
        qp.setBrush(QColor(*brush_color))
        
        local_begin = self.mapFromGlobal(self.begin)
        local_end = self.mapFromGlobal(self.end)

        rect = QRectF(local_begin, local_end)
        qp.drawRect(rect)

        self.setWindowOpacity(opacity)
        
    def mousePressEvent(self, event):
        self.begin = event.globalPos()
        self.end = self.begin
        
        self.update()

    def mouseMoveEvent(self, event):
        self.end = event.globalPos()
        self.update()

    def mouseReleaseEvent(self, event):
        
        QApplication.restoreOverrideCursor()
        
        begin = QPoint(self.begin)
        end = QPoint(self.end)

        SnippingWidget.is_snipping = False
        self.repaint()
        
        qtImg =self.grab.grabRect(begin, end)
        
        self.repaint()
        
        if self.onSnippingCompleted is not None:
            self.onSnippingCompleted(qtImg)

        self.close()

#--------------------------------------------------------------------------------
