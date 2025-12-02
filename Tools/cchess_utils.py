
import os 
import sys
import time
import traceback
from pathlib import Path
from collections import OrderedDict
import requests

import cchess
#from tinydb import TinyDB, Query

#from peewee import *
#from playhouse.sqlite_ext import *

        
#-----------------------------------------------------#
def fen_mirror(fen):
    b = cchess.ChessBoard(fen)
    return b.mirror().to_fen()
    
def iccs_list_mirror(iccs_list):
    return [cchess.iccs_mirror(x) for x in iccs_list]


#-----------------------------------------------------#
class EngineManager():

    def __init__(self):
        self.engine = None
        
    def load_engine(self, engine_path, engine_type):
        if engine_type == 'uci':
            self.engine = cchess.UciEngine('')
        elif engine_type == 'ucci':
            self.engine = cchess.UcciEngine('')
        else:
            raise Exception('目前只支持[uci, ucci]类型的引擎。') 

        if self.engine.load(engine_path):
            return True
    
    def get_best_moves(self, fen, params):
        #self.stop_thinking()
        self.go_from(fen, params)
        return self.get_result()
        
    def go_from(self, fen_engine, params):   
        return self.engine.go_from(fen_engine, params)
    
    def stop_thinking(self):
        self.engine.stop_thinking()
        time.sleep(0.2)
        self.engine.handle_msg_once()
  
    def get_result(self):
        score_dict = {}
        move_dict = {}
        while True:
            self.engine.handle_msg_once()
            if self.engine.move_queue.empty():
                time.sleep(0.2)
                continue
            output = self.engine.move_queue.get()
            #print(output)
            action = output['action']
            if action == 'bestmove':
                iccs = output['move']
                score_best = score_dict[iccs]
                return {'score':score_best, 'moves': move_dict[iccs]}
                
            elif action == 'info_move':
                score = output['score']
                moves = output['move']
                iccs = moves[0]
                score_dict[iccs] = score
                move_dict[iccs] = moves
                
            elif action in ['dead', 'draw', 'resign']:
                return {}

#-----------------------------------------------------#
def QueryFromCloudDB(fen, score_limit = 0):
    url = 'http://www.chessdb.cn/chessdb.php'
    param = {"action": 'queryall'}
    param['board'] = fen
    
    #数据获取
    try_count = 0
    found = False
    while not found:
        if try_count > 0:
            print("retry", try_count)
        try:
            resp = requests.get(url, params=param, proxies = {})
            found = True
            break
        except Exception as e:
            print(e)
            time.sleep(2)
            try_count += 1
            if try_count >= 3:
                break
    
    if not found:
        return {}
    if resp.status_code != 200:
        print(resp.text)
        return {}
    text = resp.text.rstrip('\0')
    if text.lower() in ['', 'unknown']:
        return {}

    board = cchess.ChessBoard(fen)
    move_color = board.get_move_color()    
    moves = {}
    
    #数据分割
    try:
        steps = text.split('|')
        for it in steps:
            segs = it.strip().split(',')
            items =[x.split(':') for x in segs]
            it = {key:value for key, value in items}
            #print(it_dict)
            moves[it['move']] = {'score': int(it['score'])}
    except Exception as e:
        #traceback.print_exc()
        traceback.print_exception(*sys.exc_info())
        print('cloud query result:', text, "len:", len(text))
    
    return  moves        
