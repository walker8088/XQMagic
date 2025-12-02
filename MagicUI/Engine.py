# -*- coding: utf-8 -*-

import time
import logging

#import threading

from PyQt5.QtCore import pyqtSignal, QObject

import cchess
from cchess import ChessBoard, UcciEngine, UciEngine

from .Utils import ThreadRunner

#-----------------------------------------------------#
class EngineManager(QObject):

    readySignal = pyqtSignal(int, str, list)
    moveBestSignal = pyqtSignal(int, dict)
    moveInfoSignal = pyqtSignal(int, dict)
    checkmateSignal = pyqtSignal(int, dict)
    drawSignal = pyqtSignal(int, dict)

    def __init__(self, parent, id):
        super().__init__()
        self.id = id
        self.parent = parent
        
        self.options = {}

        self.fen = None
        self.fen_engine = None
        
        self.isRunning = False
        self.isReady = False
        

    def loadEngine(self, engine_path, engine_type):
        if engine_type == 'uci':
            engine = UciEngine('')
        elif engine_type == 'ucci':
            engine = UcciEngine('')
        else:
            raise Exception('目前只支持[uci, ucci]类型的引擎。') 

        if engine.load(engine_path):
            self.engine = engine
            return True 
        else:
            return False
            
    def setOption(self, name, value):
        
        self.options[name] = value

        if not self.isReady:
            return False

        logging.info(f'Engine[{self.id}] setOption: {name} = {value}')
        self.engine.set_option(name, value)
        
        return True
        
    def goFrom(self, fen_engine, fen = None, params = {}):
        
        if not self.isReady:
            return False
        
        if not fen:
            fen = fen_engine

        #跳过不合理的fen,免得引擎误报
        if (cchess.EMPTY_BOARD in fen_engine) or (cchess.EMPTY_BOARD in fen):
            return False

        self.fen_engine = fen_engine
        self.fen = fen
        self.stopThinking()
        
        logging.info(f'Engine[{self.id}] goFrom: {fen} {params}')
        return self.engine.go_from(fen_engine, params)
    
    def stopThinking(self):
        if not self.isReady:
            return True
            
        logging.info(f'Engine[{self.id}] stop_thinking')
        self.engine.stop_thinking()
        #time.sleep(0.2)
        #self.engine.get_action()
        
        return True 

    def start(self):
        self.thread = ThreadRunner(self)
        self.thread.start()

    def stop(self):
        self.isRunning = False
    
    def quit(self):
        
        if not self.isReady:
            return 
        
        self.stop()
        time.sleep(0.2)
        self.engine.quit()
        logging.info(f'Engine[{self.id}] quit.')
        
    def run(self):
        self.isRunning = True
        while self.isRunning:
            try:
                self._runOnce()
            except Exception as e:
                logging.error(str(e))
            time.sleep(0.1)
        #self.engine.stop_thinking()

    def _runOnce(self):

        action = self.engine.get_action()
        if action is None:
            return 
        
        act_id = action['action']

        if act_id == 'ready':
            self.isReady = True
            self.readySignal.emit(self.id, self.engine.ids['name'], self.engine.options)
            return 
        
        #move_color = cchess.get_move_color(self.fen)
        if self.fen:
            action['fen'] = self.fen
            board = ChessBoard(self.fen)
            move_color = board.get_move_color()
            
        if act_id == 'bestmove':
            ret = {}
            ret.update(action)
            iccs = ret['iccs'] = ret.pop('move')
            m = board.copy().move_iccs(iccs) 
            
            #引擎有时会输出以前的局面的着法，这里预先验证一下能不能走，不能走的着法都忽略掉
            if m is None:
                return

            #分数换算到红方得分
            if move_color == cchess.BLACK:
                for key in ['score', 'mate'] :
                    if key in ret:
                        ret[key] = - ret[key]
                    
            #再处理出现mate时，score没分的情况
            if 'mate' in ret:
                mate_flag = 1 if ret['mate'] > 0 else -1
                ret['score'] = 29999 * mate_flag
            
            
            new_fen = m.board_done.to_fen()
            iccs_dict = {'iccs': iccs, 'diff': 0, 'new_fen': new_fen}
            for key in ['score', 'mate']:
                if key in ret:
                  iccs_dict[key] = ret[key]    
            
            ret['actions'] = {iccs: iccs_dict}
            self.moveBestSignal.emit(self.id, ret)

        elif act_id == 'info_move':
            #分数换算到红方得分
            #if move_color == cchess.BLACK:
            #    for key in ['score', 'mate']:
            #        if key in action:
            #            action[key] = -action[key]
            action['color'] = move_color
            self.moveInfoSignal.emit(self.id, action)
        elif act_id == 'dead':  #引擎被将死
            self.checkmateSignal.emit(self.id, action)
        elif act_id == 'draw':  #引擎认输
            self.drawSignal.emit(self.id, action)
        

#-----------------------------------------------------#
