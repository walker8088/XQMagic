# -*- coding: utf-8 -*-
import sys
import logging
import traceback
from pathlib import Path

from PyQt5.QtCore import QSettings, QCommandLineOption, QCommandLineParser
from PyQt5.QtWidgets import QApplication, QMessageBox

from .Version import release_version
from .Main import MainWindow
from . import Globl

#-----------------------------------------------------#
# Back up the reference to the exceptionhook
sys._excepthook = sys.excepthook

def my_exception_hook(exctype, value, tb):
    # Print the error and traceback
    msg = ''.join(traceback.format_exception(exctype, value, tb))
    #QMessageBox.critical(None, getTitle(), msg)
    logging.error(f'Critical Error: {msg}')

# Set the exception hook to our wrapping function
sys.excepthook = my_exception_hook

#-----------------------------------------------------#
class ChessApp(QApplication):
    def __init__(self, *argv):
        super().__init__(*argv)

        self.config = {}

        Globl.APP_NAME = 'XQMagic'
        Globl.APP_NAME_TEXT = "象棋魔术师"
        Globl.settings = QSettings('XQSoft', Globl.APP_NAME)

        self.setApplicationName(Globl.APP_NAME)
        self.setApplicationVersion(release_version)

        parser = QCommandLineParser()
        parser.addHelpOption()
        parser.addVersionOption()
        debug_option = QCommandLineOption( ["d", "debug"], "Debug app.")
        parser.addOption(debug_option)
        clean_option = QCommandLineOption( ["c", "clean"], "Clean app setttings.")
        parser.addOption(clean_option)
        parser.addPositionalArgument("file", "File to open.", "[file]")
        parser.process(self)
        
        files = parser.positionalArguments()
        if len(files) > 0:
            self.openFile = files[0]
        else:
            self.openFile = None

        self.isDebug = parser.isSet(debug_option)
        self.isClean = parser.isSet(clean_option)
        
        if self.isClean:
            Globl.settings.clear()

        if self.isDebug:
            logging.basicConfig(filename = f'{Globl.APP_NAME}.log', filemode = 'w', level = logging.DEBUG)
        else:
            logging.basicConfig(filename = f'{Globl.APP_NAME}.log', filemode = 'w', level = logging.INFO) 
        
        logging.info('应用启动')

        Globl.config_file = Path(f'{Globl.APP_NAME}.ini')

    def showWin(self):
        self.mainWin = MainWindow()
        self.mainWin.show()
        
        if self.openFile:
            self.mainWin.onDoFreeGame()
            self.mainWin.openFile(self.openFile)

        '''
        splash = QSplashScreen( QPixmap(":images/splash.png"))
        splash.show()
        
        splash.showMessage("Loaded modules")
        QCoreApplication.processEvents()
        splash.showMessage("Established connections")
        QCoreApplication.processEvents()
        '''
        
#-----------------------------------------------------#
def run():
    Globl.app = ChessApp(sys.argv)
    Globl.app.showWin()
    sys.exit(Globl.app.exec())

