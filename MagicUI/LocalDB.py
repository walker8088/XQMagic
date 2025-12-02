# -*- coding: utf-8 -*-

import time
import logging
import threading
from pathlib import Path
from collections import OrderedDict

import cchess
from cchess import ChessBoard

from peewee import Proxy, Model, CharField, IntegerField, BigIntegerField, TextField, BlobField
from playhouse.sqlite_ext import SqliteExtDatabase, JSONField
from playhouse.shortcuts import model_to_dict, dict_to_model

from . import Globl
        
#----------------------------------------------------------------
#python -m pwiz -e sqlite path/to/sqlite_database.db > 要生成的python文件名称.py

'''
#------------------------------------------------------------------------------
book_db = SqliteExtDatabase(None)
#'game/openbook.db', pragmas=(
#    ('cache_size', -1024 * 64),  # 64MB page-cache.
#   ('journal_mode', 'wal'),  # Use WAL-mode (you should always use this!).
#   #('foreign_keys', 1),
#    ))  # Enforce foreign-key constraints.

     
#------------------------------------------------------------------------------
class PosMove(Model):
    fen = CharField(unique=True, index=True)
    vkey = BigIntegerField(unique=True)
    step  = IntegerField()
    score = IntegerField()
    mark  = CharField(null=True)
    vmoves = JSONField()
   
    class Meta:
        database = book_db
'''

#------------------------------------------------------------------------------
#本地古典库，大师库
#
master_book_db = Proxy()

#------------------------------------------------------------------------------
class MasterEvBook(Model):
    #fen = CharField(unique=True, index=True)
    key   = BigIntegerField()
    step  = IntegerField()
    score = IntegerField(null=True)
    iccs  = CharField()
    mark  = CharField(null=True)
    memo  = JSONField(null=True)
    
    class Meta:
        database = master_book_db
        table_name = 'evbook'

#------------------------------------------------------------------------------
#本地库
#
local_book_db = Proxy()

class LocalModel(Model):
    class Meta:
        database = local_book_db
    
#------------------------------------------------------------------------------

class Book(LocalModel):
    fen = CharField(index=True)
    iccs  = CharField()
    score = IntegerField(null=True)
    memo  = JSONField(null=True)
    
    class Meta:
        table_name = 'book'

#------------------------------------------------------------------------------
class Bookmark(LocalModel):
    name = CharField(unique=True, index=True)
    fen = CharField(index=True)
    moves  = JSONField(null=True)
    
    class Meta:
        table_name = 'Bookmark'

#------------------------------------------------------------------------------

class MoveBookMixIn():
    #def __init__(self):
    #    self.book_cls = book_cls
        
    def getMoves(self, fen):
        
        query = self.getRecord(fen)
        if not query:
            return {}

        records, record_state = query    
        actions = OrderedDict()    
        score_best = None
        board = ChessBoard(fen)
        move_color = board.get_move_color()        
        
        for item in records:
            ics = item.iccs
            score = item.score
            if record_state == 'mirror':
                iccs = cchess.iccs_mirror(ics)
            else:
                iccs = ics

            m = {}  
            m['mark'] = item.mark
            m['iccs'] = iccs
            move_it = board.copy().move_iccs(iccs)
            m['text'] = move_it.to_text()
            m['new_fen'] = move_it.board_done.to_fen()
            
            if score is not None:
                if score_best is  None:
                    score_best = score
                m['score'] = score 
                if move_color == cchess.BLACK:
                    m['score'] = -m['score']
                m['diff'] = score - score_best
            
            #if 'mt' in act:
            #    m['mate'] = act['mt']

            actions[iccs] = m
            
        ret = {}
        ret['fen'] = fen
        ret['mirror'] = (record_state == 'mirror')
        
        if score_best is not None:
            ret['score'] = score_best 
        ret['actions'] = actions
        
        return ret
    
    def removeMoves(self, fen, iccs):
        
        query = self.getRecord(fen)
        
        #没有fen的记录
        if query is None:
            return False

        record, record_state = query
        if record_state == 'mirror':
            new_iccs = cchess.iccs_mirror(iccs)
        else:
            ne_iccs = iccs

        
    def savePositionList(self, positionList):
        for position in positionList[1:]:
            fen = position['fen_prev']
            step = position['index']
            score = None
            self.saveRecord(fen, step, score, position['iccs'])        
    
    def getRecord(self, fen, iccs = None):
        board = ChessBoard(fen)
        for b, b_state in [(board, ''), (board.mirror(), 'mirror')]:
            if iccs :
                query = self.book_cls.select().where(self.book_cls.key == b.zhash(), self.book_cls.iccs == iccs).order_by(-self.book_cls.score)
            else:
                query = self.book_cls.select().where(self.book_cls.key == b.zhash()).order_by(-self.book_cls.score)
            
            query.execute()
            #print(query.count(), b_state) 
            if query.count() > 0:
                break
            
        if query.count() == 0:
            return None
    
        return (query, b_state)
    
    def saveRecord(self, fen, step, score, iccs):
        item = self.getRecord(fen)
        board = ChessBoard(fen)
        if item is None:
            #没查到数据，直接保存
            new_record = self.book_cls(board.zhash(), step, score, iccs)
            new_record.save()
        else:
            #查到数据了，要进行合并
            record, record_state = item
            
            if record_state == 'mirror':
                #查到的数据与本次保存的相比是镜像移动，本次移动镜像化
                new_iccs = cchess.iccs_mirror(iccs)
                board = board.mirror()
            else:
                new_iccs = iccs

            #存在相同数据，不重复保存
            if new_iccs == iccs:
                return True

            保存数据
            new_record = self.book_cls(board.zhash, step, new_score, new_iccs)
            new_record.save()
                    
    
#------------------------------------------------------------------------------
#MasterBook #存储古典以及大师对局谱
class MasterBook(MoveBookMixIn):
    def __init__(self):
        #super(self).__init__(MasterEvBook)
        self.book_cls = MasterEvBook
        self.db_master = None

    def open(self, fileName):
        global master_book_db

        if not Path(fileName).is_file():
            return False

        self.db_master = SqliteExtDatabase(fileName)
        master_book_db.initialize(self.db_master)

        return True
    
    def close(self):
        if self.db_master:
            self.db_master.close()
        self.db_master = None    

    def removeMoves(self, fen, iccs, mark):
        return False

    '''
    def getMoves(self, fen):
        
        item = self.getRecord(fen)
        if not item:
            return {}

        record, record_state = item    
        actions = OrderedDict()    
        score_best = None
        board = ChessBoard(fen)
        move_color = board.get_move_color()        
        
        for ics, act in record.actions.items():
            score = act['sc']
            if record_state == 'mirror':
                iccs = cchess.iccs_mirror(ics)
            else:
                iccs = ics

            m = {}  
            m['mark'] = act['mk']
            m['iccs'] = iccs
            move_it = board.copy().move_iccs(iccs)
            m['text'] = move_it.to_text()
            m['new_fen'] = move_it.board_done.to_fen()
            
            if score is not None:
                if score_best is  None:
                    score_best = score
                m['score'] = score 
                if move_color == cchess.BLACK:
                    m['score'] = -m['score']
                m['diff'] = score - score_best
            
            if 'mt' in act:
                m['mate'] = act['mt']

            actions[iccs] = m
            
        ret = {}
        ret['fen'] = fen
        ret['mirror'] = (record_state == 'mirror')
        
        if score_best is not None:
            ret['score'] = score_best 
        ret['actions'] = actions
        
        return ret
    
    def removeMoves(self, fen, iccs, mark):
        
        item = self.getRecord(fen)
        
        #没有fen的记录
        if item is None:
            return False

        record, record_state = item
        if record_state == 'mirror':
            new_iccs = cchess.iccs_mirror(iccs)
        else:
            ne_iccs = iccs

        #没有iccs的记录    
        if iccs not in record.actions:
            return False

        if not mark:
            #该走子的全部数据都删除
            del record.actions[iccs]
        else:
            #只去掉这个走子的mark
            act = record.actions[iccs]
            
            old_mark =  act['mk']
            act['mk'] = old_mark.replace(mark, '')

            if len(act['mk']) == 0:
                #这个步骤的mark为空，可以移走了           
                del record.actions[iccs]

        if len(record.actions) == 0:
            #该局面移动为空，删除
            self.removeRecord(fen, record_state)
        else:
            #尚有其他数据，保存新结果
            record.save()
    
    #界面的类型转化为数据库类型然后保存        
    def saveActions(self, fen, step, score, actions, mark):
        db_actions = {}
        for iccs, act in actions.items():
            it = {}
            if 'score' in act:
                it['sc'] = act['score']
            else:
                it['sc'] = None
            it['mk'] = mark
            db_actions[iccs] = it
        return saveRecord(fen, step, score, db_actions)        
    
    def savePositionList(self, positionList, mark):
        for position in positionList:
            fen = position['fen_prev']
            step = position['index']
            score = None
            actions = [position['iccs']]
            self.saveActions(fen, step, score, actions, mark)

    #--------------------------------------------------------------
    #底层处理
    def getRecord(self, fen):
        board = ChessBoard(fen)
        for b, b_state in [(board, ''), (board.mirror(), 'mirror')]:
            query = MasterPosAction.select().where(MasterPosAction.fen == b.to_fen())
            query.execute()
            #print(query.count(), b_state) 
            if query.count() > 0:
                break
            
        if query.count() == 0:
            return None
        
        if query.count() > 1:
            raise Exception(f'database error：{b_state} {fen}')
        
        return (list(query)[0], b_state)
    
    def removeRecord(self, fen, state): 

        if state == 'mirror':
            new_fen = ChessBoard(fen).mirror().to_fen() 
        else:
            new_fen = fen 
        
        query = MasterPosAction.delete().where(MasterPosAction.fen == new_fen)
        query.execute()
        
        return True

    def saveRecord(self, fen, step, score, actions):
        item = self.getRecord(fen)
        if item is None:
            #没查到数据，直接保存
            new_record = PosAction(fen, step, score, actions)
            new_record.save()
        else:
            #查到数据了，要进行合并
            record, record_state = item
            
            if record_state == 'mirror':
                #查到的数据与本次保存的相比是镜像移动，本次移动镜像化
                new_actions = { cchess.iccs_mirror(iccs):act for iccs, act in actions.items() }
            else:
                new_actions = actions
            
            #要保存的数据与已有的数据进行合并
            for iccs, act in new_actions:
                if iccs not in record.actions:
                    record.actions[iccs] = act
                else:
                    old_act = record.actions[iccs]

                    if act['score'] is not None:
                        old_act['score'] = act['score']
                    
                    mark = act['mk']
                    if mark not in old_act['mk']:
                        old_act['mk'].append(mark)

            #处理新旧记录的分数合并，避免无分数冲掉有分数
            if score is not None:
                new_score = score
            else:
                new_score = record.score                    
            #保存数据
            new_record = PosAction(fen, record.step, new_score, record.actions)
            new_record.save()
                    
    '''
#------------------------------------------------------------------------------
#LocalBook #存储个人保存的棋谱及收藏
class LocalBook():
    def __init__(self):
        self.db_local = None

    def open(self, fileName):
        global local_book_db

        isInit = False
        if not Path(fileName).is_file():
            isInit = True

        self.db_local = SqliteExtDatabase(fileName)
        local_book_db.initialize(self.db_local)
        if isInit:
            local_book_db.create_tables([Book, Bookmark])

        return True
    
    def close(self):
        if self.db_local:
            self.db_local.close()
        self.db_local = None
    
    def getAllBookmarks(self):
        
        q = Bookmark.select().execute()
        return [model_to_dict(x) for x in q]

    def saveBookmark(self, name, fen, moves=None):

        if self.isNameInBookmark(name):
            return False

        book = Bookmark(name = name, fen = fen, moves = moves)
        book.save()
        return True

    def isFenInBookmark(self, fen):
        q = Bookmark.select().where(Bookmark.fen == fen).execute()
        return len(q) > 0

    def isNameInBookmark(self, name):
        q = Bookmark.select().where(Bookmark.name == name).execute()
        return len(q) > 0

    def removeBookmark(self, name):
        Bookmark.delete().where(Bookmark.name == name).execute()
        return True

    def changeBookmarkName(self, old_name, new_name):
        query = Bookmark.update(name = new_name).where(Bookmark.name == old_name).execute()
        return True

    def saveBook(self, fen, moves):
        book = Book(fen = fen, moves = moves)
        book.save()
        return True

    def savePositionList(self, positionList):
        #TODO: 更新分数
        for position in positionList[1:]:
            fen = position['fen_prev']
            iccs = position['iccs']
            score = None
            self.saveRecord(fen, iccs, score)

    def saveRecord(self, fen, iccs, score):

        ret_len, is_mirror = self.getRecord(fen, iccs)
        
        if ret_len == 0:
            new_record = Book(fen = fen, iccs = iccs, score = score)
            new_record.save()
        else:
            #TODO 更新score
            pass
        
        return True
            
    def getRecord(self, fen, iccs):

        f_mirror = cchess.fen_mirror(fen)
        i_mirror = cchess.iccs_mirror(iccs)

        query = Book.select().where(  ((Book.fen == fen) & (Book.iccs == iccs)) 
                                        | ((Book.fen == f_mirror) & (Book.iccs == i_mirror)) )
        query.execute()
            
        if len(query) == 0:
            return (0, False)
        
        if len(query) > 1:
            raise Exception(f"Local Storage Multi Record Error:{fen}, {iccs}")
        
        is_mirror = False
        if query[0].fen == f_mirror:
            True

        return (1, is_mirror)
    
    def getMoves(self, fen):

        board = ChessBoard(fen)
        f_mirror = cchess.fen_mirror(fen)
        query = Book.select().where((Book.fen == fen) | (Book.fen == f_mirror)).execute()
        
        actions = OrderedDict() 
        for it in query:
            
            iccs = it.iccs
            if it.fen == f_mirror:
                iccs = cchess.iccs_mirror(iccs)
            
            m = {}
            m['iccs'] = iccs
            if it.score:
                m['score'] = it.score
                #m['diff'] =  0
            
            move_it = board.copy().move_iccs(iccs)
            if move_it:
                m['text'] = move_it.to_text()
                m['new_fen'] = move_it.board_done.to_fen()
            else:
                m['text'] = 'move error'
            
            actions[iccs] = m

        ret = {}
        ret['fen'] = fen
        ret['score'] = None 
        ret['actions'] = actions

        return ret
        
#------------------------------------------------------------------------------
#勇芳格式开局库
openBookYfk = Proxy()

class YfkBaseModel(Model):
    class Meta:
        database = openBookYfk

class Bhobk(YfkBaseModel):
    vindex = IntegerField(null=True)
    vkey = IntegerField(null=True)
    vdraw = IntegerField(null=True)
    vlost = IntegerField(null=True)
    vmove = IntegerField(null=True)
    vscore = IntegerField(null=True)
    vvalid = IntegerField(null=True)
    vwin = IntegerField(null=True)

    class Meta:
        table_name = 'bhobk'

class Ltext(YfkBaseModel):
    lma = TextField(null=True)

    class Meta:
        table_name = 'ltext'

#------------------------------------------------------------------------------
#鹏飞格式开局库
openBookPF = Proxy()

class BaseModelPfBook(Model):
    class Meta:
        database = openBookPF

class BookVersion(BaseModelPfBook):
    key = TextField(index=True, null=True)
    version = TextField(null=True)

    class Meta:
        table_name = 'bookVersion'
        primary_key = False

class PfBook(BaseModelPfBook):
    vindex = IntegerField(null=True)
    vkey = IntegerField(index=True, null=True)
    vdraw = IntegerField(null=True)
    vlost = IntegerField(null=True)
    vwin = IntegerField(null=True)
    vmove = IntegerField(null=True)
    vscore = IntegerField(null=True)
    vvalid = IntegerField(null=True)
    vmemo = BlobField(null=True)
    
    class Meta:
        table_name = 'pfBook'

#------------------------------------------------------------------------------
#开局库基础类
class OpenBookDB():    
    c90 =   [ 
        0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3a, 0x3b,
        0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49, 0x4a, 0x4b,
        0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5a, 0x5b,
        0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6a, 0x6b,
        0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7a, 0x7b,
        0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89, 0x8a, 0x8b,
        0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9a, 0x9b,
        0xa3, 0xa4, 0xa5, 0xa6, 0xa7, 0xa8, 0xa9, 0xaa, 0xab,
        0xb3, 0xb4, 0xb5, 0xb6, 0xb7, 0xb8, 0xb9, 0xba, 0xbb,
        0xc3, 0xc4, 0xc5, 0xc6, 0xc7, 0xc8, 0xc9, 0xca, 0xcb
        ]

    s90 = [ 
        "a9", "b9", "c9", "d9", "e9", "f9", "g9", "h9", "i9",
        "a8", "b8", "c8", "d8", "e8", "f8", "g8", "h8", "i8",
        "a7", "b7", "c7", "d7", "e7", "f7", "g7", "h7", "i7",
        "a6", "b6", "c6", "d6", "e6", "f6", "g6", "h6", "i6",
        "a5", "b5", "c5", "d5", "e5", "f5", "g5", "h5", "i5",
        "a4", "b4", "c4", "d4", "e4", "f4", "g4", "h4", "i4",
        "a3", "b3", "c3", "d3", "e3", "f3", "g3", "h3", "i3",
        "a2", "b2", "c2", "d2", "e2", "f2", "g2", "h2", "i2",
        "a1", "b1", "c1", "d1", "e1", "f1", "g1", "h1", "i1",
        "a0", "b0", "c0", "d0", "e0", "f0", "g0", "h0", "i0"
        ]
    
    CoordMap = {}
        
    def __init__(self):
        
        self.isBookOpened = False
        self.db = None
        self.name = ''
        self.isUseScore = False

        if not self.CoordMap:
            for i in range(90):
                self.CoordMap[self.c90[i]] = self.s90[i]
    
    def open(self, fileName, globDatabase, useScore):
        
        if self.isBookOpened:
            return False

        if not Path(fileName).is_file():
            return False

        self.db = SqliteExtDatabase(fileName)
        globDatabase.initialize(self.db)

        self.isBookOpened = True
        self.isUseScore = useScore

        try:
            self.getMoves(cchess.FULL_INIT_FEN)
        except Exception as e:
            logging.error(str(e))
            self.isBookOpened = False
        
        return self.isBookOpened
        
    def close(self):
       if self.db:
            self.db.close()     
            self.isBookOpened = False
            
#------------------------------------------------------------------------------
class OpenBookYfk(OpenBookDB):
    
    def __init__(self):
        super().__init__()
        self.name = '勇芳'

    def open(self, fileName, useScore = False):
        super().open(fileName, openBookYfk, useScore)
        
    #鹏飞库与勇芳库的高低位是反的，其他数据一样
    def vmove2iccs(self, vmove):
        v_from =  vmove & 0xff
        v_to = vmove >> 8
        return self.CoordMap[v_from] + self.CoordMap[v_to]

    def getMoves(self, fen):

        if not self.isBookOpened:
            return None

        board = ChessBoard(fen)
        zhash = board.zhash()
        zhash_mirror = board.mirror().zhash()
        
        query = Bhobk.select().where(((Bhobk.vkey == zhash) | (Bhobk.vkey == zhash_mirror)) & (Bhobk.vvalid == 1))\
                                    .order_by(-Bhobk.vscore).execute()
        
        if len(query) == 0:
            return None

        actions = OrderedDict() 
        score_best = None
        
        for it in query:
            iccs = self.vmove2iccs(it.vmove)
            
            score = it.vscore
            if score_best is None:
                score_best = score
            
            if it.vkey == zhash_mirror:
                iccs = cchess.iccs_mirror(iccs)
                
            m = {}  
            m['iccs'] = iccs
            m['score'] = score
            m['diff'] =  score - score_best
            
            bd = board.copy()
            move_it = bd.move_iccs(iccs)
            if move_it is not None:
                m['text'] = move_it.to_text()
                m['new_fen'] = move_it.board_done.to_fen()
            else:
                m['text'] = f'err:{iccs}'
                logging.error(f"{bd.to_fen()} move {iccs} error")
            
            actions[iccs] = m
        
        ret = {}
        ret['fen'] = fen
        ret['score'] = score_best 
        ret['actions'] = actions

        return ret
        

#------------------------------------------------------------------------------
class OpenBookPF(OpenBookDB):
    
    def __init__(self):
        super().__init__()
        self.name = '鹏飞'
        self.isUseScore = False
    
    def open(self, fileName, useScore = False):
        super().open(fileName, openBookPF, useScore)
        
    #鹏飞库与勇芳库的高低位是反的，其他数据一样
    def vmove2iccs(self, vmove):
        v_to =  vmove & 0xff
        v_from = vmove >> 8
        return self.CoordMap[v_from] + self.CoordMap[v_to]

    def getMoves(self, fen):
        
        if not self.isBookOpened:
            return {}

        board = ChessBoard(fen)
        zhash = board.zhash()
        zhash_mirror = board.mirror().zhash()
        
        query = PfBook.select().where(((PfBook.vkey == zhash) | (PfBook.vkey == zhash_mirror)) & (PfBook.vvalid == 1))\
                                    .order_by(-PfBook.vscore).execute()
        
        if len(query) == 0:
            return None
                    
        actions = OrderedDict() 
        score_best = None
        #move_color = board.get_move_color()        
        
        for it in query:
            iccs = self.vmove2iccs(it.vmove)
        
            score = it.vscore
            if score_best is None:
               score_best = score
                    
            if it.vkey == zhash_mirror:
                iccs = cchess.iccs_mirror(iccs)
                
            if iccs in actions:
                continue

            m = {}  
            m['iccs'] = iccs
                
            if isinstance(it.vmemo, str):
                m['memo'] = it.vmemo
            elif isinstance(it.vmemo, bytes):
                m['memo'] = it.vmemo.decode('utf-8')
            else:
                m['memo'] = str(it.vmemo)
            
            m['score'] = score
            m['diff'] =  score - score_best
        
            move_it = board.copy().move_iccs(iccs)
            if move_it is not None:
                m['text'] = move_it.to_text()
                m['new_fen'] = move_it.board_done.to_fen()
            else:
                m['text'] = f'err:{iccs}'
                logging.error(f"{bd.to_fen()} move {iccs} error")
            
            actions[iccs] = m
        
        ret = {}
        ret['fen'] = fen
        ret['score'] = score_best 
        ret['actions'] = actions

        return ret
        
