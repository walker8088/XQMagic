# -*- coding: utf-8 -*-

import time
import logging
import threading
from pathlib import Path
from collections import OrderedDict

import cchess
from cchess import ChessBoard

from tinydb import TinyDB, Query

from . import Globl

"""        
#------------------------------------------------------------------------------
#OpenBookJson
class OpenBookJson():
    def __init__(self):
        pass

    def loadBookFile(self, fileName):
        self.db = TinyDB(fileName)

    def getMoves(self, fen):
        
        board = ChessBoard(fen)
        
        for b, b_state in [(board, ''), (board.mirror(), 'mirror')]:
            fen = b.to_fen()
            result = self.db.search(Query().fen == fen)
            if len(result) > 0:
                break
        
        #print("GET:", b_state, query)
        if len(result) == 0:
            return {}
        
        
        actions = [] #OrderedDict()    
        move_color = board.get_move_color()        
        score_best = None
        
        moves = result[0]
        #print(moves)

        for ics, info in moves['action'].items():
            score = info['score']
            if b_state == 'mirror':
                iccs = iccs_mirror(ics)
            else:
                iccs = ics
            m = {}  
            m['iccs'] = iccs
            
            if score_best is  None:
                score_best = score

            move_it = board.copy().move_iccs(iccs)
            m['text'] = move_it.to_text()
            m['score'] = score
            m['diff'] =  score - score_best
            if move_color == cchess.BLACK:
                m['score'] = -m['score']
            m['new_fen'] = move_it.board_done.to_fen()
            actions.append(m)
            
        ret = {}
        ret['fen'] = fen
        ret['score'] = score_best 
        ret['actions'] = actions

        return ret
"""
#------------------------------------------------------------------------------
#Bookmarks
'''
class BookmarkStore():
    def __init__(self, fileName):
       self.db = TinyDB(fileName)

    def close(self):
        self.db.close()
        
    def getAllBookmarks(self):
        return self.db.search(Query().name.exists())
        
    def saveBookmark(self, name, fen, moves=None):

        if self.isFenInBookmark(fen) or self.isNameInBookmark(name) > 0:
            return False

        item = {'name': name, 'fen': fen, 'moves': moves}

        if moves is not None:
            item['moves'] = moves

        self.db.insert(item)

        return True

    def isFenInBookmark(self, fen):
        q = Query()
        return len(self.db.search(q.fen == fen)) > 0

    def isNameInBookmark(self, name):
        q = Query()
        return len(self.db.search(q.name == name)) > 0

    def removeBookmark(self, name):
        q = Query()
        return self.db.remove(q.name == name)

    def changeBookmarkName(self, fen, new_name):
        q = Query()
        ret = self.db.update({'name': new_name},
                                         (q.fen == fen))
        if len(ret) == 1:
            return True
        return False
'''
#------------------------------------------------------------------------------
#Endbooks
class EndBookStore():
    def __init__(self, fileName):
        self.endbooks = TinyDB(fileName)
    
    def close(self):
        self.endbooks.close()

    def getAllEndBooks(self):
        q = Query()
        books = {}
        ret = self.endbooks.search(q.book_name.exists())
        for it in ret:
            if 'ok' not in it:
                it['ok'] = False
            book_name = it['book_name']
            if book_name not in books:
                books[book_name] = []
            books[book_name].append(it)
        return books

    def saveEndBook(self, book_name, games):
        q = Query()
        for game in games:
            game['book_name'] = book_name
            ret = self.endbooks.search((q.book_name == book_name)
                                            & (q.name == game['name']))
            if len(ret) == 0:
                self.endbooks.insert(game)
                #yield game['name']
    
    def updateEndBook(self, game):
        q = Query()
        
        ret = self.endbooks.search((q.book_name ==  game['book_name'] )
                                            & (q.name == game['name']))
        if len(ret) != 1:
            raise Exception(f"Game Not Exist：{game}")
        else:    
            self.endbooks.update({'ok':game['ok']}, ((q.book_name ==  game['book_name'])
                                            & (q.name == game['name'])))
            
    def isEndBookExist(self, book_name):
        q = Query()
        ret = self.endbooks.search((q.book_name == book_name))
        return len(ret) >= 1

    def deleteEndBook(self, book_name):
        q = Query()
        self.endbooks.remove((q.book_name == book_name))
    
    
#------------------------------------------------------------------------------
'''
#LocalBooks
class LocalBookStore():
    def __init__(self, fileName):
        self.localbooks = TinyDB(fileName)
        self.lock = threading.RLock()
        
    def close(self):
        self.localbooks.close()

    def getMoves(self, fen):
        with self.lock:
            ret = self.localbooks.search(Query().fen == fen)
            
            if len(ret) == 0:
                return None

            elif len(ret) > 1:
                raise Exception(f'database error: {fen}, {ret}')
            
            book_actions = {}

            board = ChessBoard(fen)
            it = ret[0]
            for act in it['actions']:
                act['fen'] = fen
                m = board.copy().move_iccs(act['iccs'])
                if m is None:
                    continue
                act['text'] = m.to_text()
                act['new_fen'] = m.board_done.to_fen()

                book_actions[act['iccs']] = act
                
            return {'actions': book_actions}
        
    def delBookMoves(self, fen, iccs):
        with self.lock:
            q = Query()
            
            if iccs is None: #删除该fen对应的数据记录
                self.localbooks.remove(q.fen == fen)
            else: #删除该fen和该iccs对应的数据记录
                ret = self.localbooks.search(q.fen == fen)
                if len(ret) == 0:
                    return False
                record = ret[0]
                found = False
                new_record = []    
                for act in record['actions']:
                    if iccs == act['iccs']:
                        found = True
                    else:
                        new_record.append(act)
                if found:
                    if len(new_record) > 0: 
                        #该fen尚有其它actions
                        self.localbooks.update({'actions': new_record}, q.fen == fen)
                    else:
                        #该fen下的actions已经为空了
                        self.localbooks.remove(q.fen == fen)
                        
    def saveMovesToBook(self, positions):
        with self.lock:
            board = ChessBoard()
            q = Query()
            for position in positions:
                #print(position)
                #move = position['move']
                fen = position['fen_prev']
                move_iccs = position['iccs']
                board.from_fen(fen)
                if not board.is_valid_iccs_move(move_iccs):
                    raise Exception(f'**ERROR** {fen} move {move_iccs}')
                ret = self.localbooks.search(q.fen == fen)
                
                action_to_save = {'iccs': move_iccs}
                
                if len(ret) == 0:
                    self.localbooks.insert({
                        'fen': fen,
                        'actions': [
                            action_to_save,
                        ]
                    })
                elif len(ret) == 1:
                    db_actions = ret[0]['actions']
                    act_found = False
                    for act in db_actions:

                        if act['iccs'] == move_iccs:
                            act_found = True
                            act.update(action_to_save)
                            self.localbooks.update({'actions': db_actions},
                                                       q.fen == fen)
                            break
                    if not act_found:
                        db_actions.append(action_to_save)
                        self.localbooks.update({'actions': db_actions},
                                                   q.fen == fen)
                else:
                    print('database error', ret)
        
#------------------------------------------------------------------------------
'''