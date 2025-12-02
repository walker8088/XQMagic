# -*- coding: utf-8 -*-
import json
import time
import logging
import threading
from pathlib import Path
from collections import OrderedDict

import cchess
from cchess import ChessBoard

from PyQt5.QtCore import QObject, pyqtSignal, QUrl, QUrlQuery
from PyQt5.QtNetwork import QNetworkRequest, QNetworkAccessManager

from . import Globl

#------------------------------------------------------------------------------
def updateCache(qResult):
    fen = qResult['fen']
    if fen not in Globl.fenCache:
        Globl.fenCache[fen] = {}
    Globl.fenCache[fen].update({'score': qResult['score']}) 

    best_moves = []
    actions = qResult['actions']
    for act in actions.values():
        if act['diff'] == 0:
            best_moves.append(act['iccs'])
        m = {'score': act['score'], 'diff': act['diff']}
        new_fen = act['new_fen']
        if new_fen not in Globl.fenCache:
            Globl.fenCache[new_fen] = m
        else:
            Globl.fenCache[new_fen].update(m)    
    
    if len(best_moves) > 0: 
        Globl.fenCache[fen].update({ 'best_moves': best_moves })
        #print(Globl.fenCache[fen])        
        

#------------------------------------------------------------------------------
class NetQuery(QObject):
    query_ret_signal = pyqtSignal(str, str)
    query_err_signal = pyqtSignal(str)
    
    def __init__(self, parent, url, fen):
        super().__init__(parent)

        self.url = url
        self.net_mgr = QNetworkAccessManager()
        
        self.fen = fen
        self.reply = None
        self.tryCount = 0
        
    def startQuery(self):

        url = QUrl(self.url)
        query = QUrlQuery()
        query.addQueryItem('board', self.fen)
        query.addQueryItem("action", 'queryall')
        url.setQuery(query)
        
        self.req = QNetworkRequest(url)
        self.reply = self.net_mgr.get(self.req)
        self.reply.finished.connect(self.onQueryFinished)
        self.reply.errorOccurred.connect(self.onQueryError)
        
    def onQueryFinished(self):
        resp = self.reply.readAll().data().decode().rstrip('\0')
        self.query_ret_signal.emit(self.fen, resp)

    def onQueryError(self, error):
        self.reply = None
        
        self.tryCount += 1
        if self.tryCount < 3:
            logging.warning(f'Query From CloudDB Error, retry { self.tryCount}')
            time.sleep(2)
            self.reply = self.net_mgr.get(self.req)
            self.reply.finished.connect(self.onQueryFinished)
            self.reply.errorOccurred.connect(self.onQueryError)
        else:
            self.query_err_signal.emit(self.fen)
    
class CloudDB(QObject):
    query_result_signal = pyqtSignal(dict)
    
    def __init__(self, parent):
        super().__init__(parent)
        self.url = 'http://www.chessdb.cn/chessdb.php'
        
        self.move_cache = {}
        self.query_worker = {}

    def startQuery(self, position, score_limit = 90):

        fen = position['fen']
        
        logging.info(f"Cloud Query: {fen}")

        if fen in self.move_cache:
            ret = self.move_cache[fen]
            self.query_result_signal.emit(ret)
            return 

        #还在工作尚未完成             
        if fen in self.query_worker:
            return

        q = NetQuery(self, self.url, fen)
        self.query_worker[fen] = q
        q.query_ret_signal.connect(self.onQueryFinished)
        q.query_err_signal.connect(self.onQueryError) 
        q.startQuery()

    def onQueryFinished(self, fen, resp):
        
        self.score_limit = 90
        ret = {}
        
        self.query_worker.pop(fen)

        #resp: 若局面代码错误，返回 invalid board ，
        #若所查询的局面没有已知着法，返回 unknown ，若走棋方被将死或困毙，返回 checkmate / stalemate
        resp = resp.lower()
        if resp in ['', 'unknown']:
            #TOFO fix return
            return 
        
        #杀死
        if resp == 'checkmate':
            #ret['index'] = self.index
            ret['fen'] = fen
            ret['score'] = 30000
            ret['mate'] = 0
            ret['actions'] = {}
        
            self.move_cache[fen] = ret
            self.reply = None
            self.query_result_signal.emit(ret)
            
            return

        board = ChessBoard(fen)    
        move_color = board.get_move_color()    
        moves = []
        
        #数据分割
        try:
            steps = resp.split('|')
            for index, it in enumerate(steps):
                segs = it.strip().split(',')
                items =[x.split(':') for x in segs]
                it_dict = {}
                for name, value in items:
                    if name == 'score':
                        it_dict['score'] = value
                    elif name == 'move':
                        it_dict['iccs'] = value
                #if index > 3:
                #    break        
                moves.append(it_dict)
        except Exception as e:
            logging.error(f"云库查询数据解析错误：{e} {resp}")
            
        if not moves: 
            return

        score_best = int(moves[0]['score'])
        for act in moves:
            move_it = board.copy().move_iccs(act['iccs'])
            if move_it:
                act['text'] = move_it.to_text()
            act['score'] = int(act['score']) 
            act['diff'] =  act['score'] - score_best
            if move_color == cchess.BLACK:
                act['score'] = -act['score']
            act['new_fen'] = move_it.board_done.to_fen()

            
        #moves = filter(lambda x : is_odd, moves)        

        #for it in moves:
        #   if self. score_limit > 0 and abs(it['diff']) >  self.score_limit:
        #           continue
        
        moves =  sorted(moves, key = lambda x:x['diff'], reverse = True) 
        
        moves_clean = OrderedDict()
        score_best = moves[0]['score']
        for it in moves:
            it['diff'] =  it['score'] - score_best
            if move_color == cchess.BLACK :
                it['diff'] = -it['diff']
            if self.score_limit > 0 and abs(it['diff']) >  self.score_limit:
                    continue
                    
            moves_clean[it['iccs']] = it
            
        #ret['index'] = self.index
        ret['fen'] = fen
        ret['score'] = score_best
        ret['actions'] = moves_clean
            
        self.move_cache[fen]  = ret
        
        updateCache(ret)

        self.reply = None
        self.query_result_signal.emit(ret)
        
    def onQueryError(self, fen):
        self.query_worker.pop(fen)

#------------------------------------------------------------------------------
class MyScoreDB(QObject):
    query_result_signal = pyqtSignal(dict)
    
    def __init__(self, parent):
        super().__init__(parent)

        self.url = 'http://212.64.28.112:8887/query'
        #self.url = 'http://127.0.0.1:8887/query'
        self.net_mgr = QNetworkAccessManager()
        
        self.reply = None
        self.fen = None
        self.board = ChessBoard()
        self.tryCount = 0
        self.score_limit = 0
        self.move_cache = {}
        
    def startQuery(self, position):

        fen = position['fen']
        
        logging.info(f"Score Query: {fen}")

        if fen in self.move_cache:
            ret = self.move_cache[fen]
            self.query_result_signal.emit(ret)
            return 
             
        if (self.reply is not None) and (not self.reply.isFinished()):
            self.reply.abort()
        
        self.index = position['index']
        self.fen = fen
        self.board.from_fen(fen)
        
        url = QUrl(self.url)
        query = QUrlQuery()
        query.addQueryItem('fen', fen)
        #query.addQueryItem("action", 'queryall')
        url.setQuery(query)
        
        self.tryCount = 1
        self.req = QNetworkRequest(url)
        self.reply = self.net_mgr.get(self.req)
        self.reply.finished.connect(self.onQueryFinished)
        self.reply.errorOccurred.connect(self.onQueryError)
        
    def onQueryFinished(self):
        
        if not self.reply:
            return
        
        ret = {}

        resp = self.reply.readAll().data().decode()
        if len(resp) == 0:
            return
        
        move_color = self.board.get_move_color()    
        moves = json.loads(resp)
        
        if not moves: 
            return

        score_best = int(moves[0]['score'])
        for act in moves:
            act['iccs'] = act.pop('move')
            move_it = self.board.copy().move_iccs(act['iccs'])
            if move_it:
                act['text'] = move_it.to_text()
            act['score'] = int(act['score']) 
            act['diff'] =  act['score'] - score_best
            if move_color == cchess.BLACK:
                act['score'] = -act['score']
            act['new_fen'] = move_it.board_done.to_fen()
    
        #moves = filter(lambda x : is_odd, moves)        

        #for it in moves:
        #   if self. score_limit > 0 and abs(it['diff']) >  self.score_limit:
        #           continue
        
        moves =  sorted(moves, key = lambda x:x['diff'], reverse = True) 
        
        moves_clean = OrderedDict()
        score_best = moves[0]['score']
        for it in moves:
            it['diff'] =  it['score'] - score_best
            if move_color == cchess.BLACK :
                it['diff'] = -it['diff']
            if self.score_limit > 0 and abs(it['diff']) >  self.score_limit:
                    continue
                    
            moves_clean[it['iccs']] = it
            
        ret['index'] = self.index
        ret['fen'] = self.fen
        ret['score'] = score_best
        ret['actions'] = moves_clean
        
        self.reply = None
        self.query_result_signal.emit(ret)
        
        
    def onQueryError(self, error):
        self.reply = None
        
        self.tryCount += 1
        if self.tryCount < 5:
            logging.warning(f'Query from ScoreDB Error, retry { self.tryCount}')
            time.sleep(2)
            self.reply = self.net_mgr.get(self.req)
            self.reply.finished.connect(self.onQueryFinished)
            self.reply.errorOccurred.connect(self.onQueryError)
        else:
            self.query_result_signal.emit({})
        
