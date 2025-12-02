import os, sys
import time
import pickle
from pathlib import Path

import requests

from cchess import *

from peewee import *
from playhouse.sqlite_ext import *

#---------------------------------------------------------
book_db = SqliteExtDatabase('openbook.db', pragmas=(
    ('cache_size', -1024 * 64),  # 64MB page-cache.
    ('journal_mode', 'wal'),  # Use WAL-mode (you should always use this!).
    ('foreign_keys', 1)))  # Enforce foreign-key constraints.

class PosMove(Model):
    fen = CharField(unique=True, index=True)
    vkey = BigIntegerField(unique=True)
    step  = IntegerField()
    score = IntegerField()
    mark  = CharField(null=True)
    vmoves = JSONField()
    
    class Meta:
        database = book_db

#-----------------------------------------------------#

def QueryFromCloudDB(fen):
    url = 'http://www.chessdb.cn/chessdb.php'
    param = {"action": 'queryall'}
    param['board'] = fen
    
    #数据获取
    try:
        resp = requests.get(url, params=param,  timeout = 10)
    except Exception as e:
        print(e)
        return []
        
    text = resp.text.rstrip('\0')
    if len(text) < 20:
        print(text)
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
    except Exception as e:
        #traceback.print_exc()
        traceback.print_exception(*sys.exc_info())
        print('cloud query result:', text, "len:", len(text))
        return  None
        
    for move in moves:
        move['score'] = int(move['score'])
    
    return moves
    
#---------------------------------------------------------------------------
def get_pos_moves(fen):
    query = PosMove.select().where(PosMove.fen == fen)
    for it in query:
        print(it.fen, it.moves)
        for m in it.moves:  
            print(m)
        
#---------------------------------------------------------------------------
def is_fen_exist(fen):
    board = ChessBoard(fen)
    zhash = board.zhash() 
    query = list(PosMove.select().where(PosMove.vkey == zhash))
    if len(query) > 0:
        return True
    
    zhash2 = board.mirror().zhash()
    query = list(PosMove.select().where(PosMove.vkey == zhash2))
    if len(query) > 0:
        print('mirror found.')
        return True
 
    return False
    
#---------------------------------------------------------------------------
def clean_moves(fen, step, moves):
    step_limits = [13, ]
    ret = []
    save_moves = {}
    score_best = moves[0]['score']
    for i, m in enumerate(moves):
        diff =  abs( m['score'] - score_best)
            
        if step == 1 and m['score'] < 0:
            continue
        else:
            if step >= 2 and (m['score'] < -65):
                continue
            
            elif i > 3 and score_best < 0:
                continue  
            elif i > 3 and diff > 50:
                continue
            elif i >= 7 and diff > 30:
                continue
            elif step > 6 and diff > 50:
                continue
            
            elif score_best < 0 and diff > 30:
                continue  
    
            elif score_best > 10 and m['score'] < -score_best:
                continue  
            
            elif diff > 60:
                continue
                
        save_moves[m['move']] = m['score']    
        ret.append({'fen': fen, 'iccs': m['move'], 'score': m['score']})
    
    return (score_best, ret, save_moves)
    
def save_pos_move(fen, zhash, score, step, records): 
    
    if is_fen_exist(fen):
        print('Inbook:', fen)
        return False
        
    if len(records) > 0:    
        PosMove.create(fen = fen, vkey = zhash, score = score, step = step, vmoves = records)   
    return True
    
#---------------------------------------------------------------------------

#get_pos_moves(FULL_INIT_FEN)

#sys.exit(0)

table_file = 'table.pickle'

if not Path(table_file).is_file():
    PosMove.create_table()
    tables = []
    fen = FULL_INIT_FEN
    step = 1 
    board = ChessBoard(fen)        
    zhash = board.zhash()
    
    print(f"Step:{step} Query:{fen}")
    moves = QueryFromCloudDB(fen)
    if len(moves) == 0:
        print("None Moves Found in CloundDB.")
        sys.exit(-1)

    score, records, save_moves = clean_moves(fen, step, moves)
    print(len(save_moves))
    if save_pos_move(fen, zhash, score, step, save_moves): 
        for it in records:
            b = board.copy()
            move = b.move_iccs(it['iccs'])
            b.next_turn()
            tables.append(b.to_fen())
else:
    with open(table_file, 'rb') as f:
        step, tables = pickle.load(f)
        print(f"Step：{step}, Load {len(tables)} Records")

#消费数据
new_tables = []
step += 1
count = len(tables)
for index, fen in enumerate(tables):
    #生产数据
    try_count = 0        
    zhash = ChessBoard().zhash(fen)   
    while try_count < 5:
        print(f"Step:{step} {index+1}/{count} Query:{fen}")
        moves = QueryFromCloudDB(fen)
        if len(moves) == 0:
            time.sleep(3)
            try_count += 1
        else:
            break
   
    if len(moves) == 0:
        sys.exit(-1)
    
    score,records, save_moves = clean_moves(fen, step, moves)
    if save_pos_move(fen, zhash, score, step, save_moves):    
        print(step, score, save_moves)
        board = ChessBoard(fen)
        for it in records:
            b = board.copy()
            move = b.move_iccs(it['iccs'])
            b.next_turn()
            new_fen = b.to_fen()
            if not is_fen_exist(new_fen):
                new_tables.append(new_fen)
        #time.sleep(0.2)
    
#保存CheckPoint
print("table len:", len(new_tables))
with open(table_file, 'wb') as f:
    pickle.dump((step, new_tables), f)

#交换数据
#tables = new_tables
#mirror
#rnbakabnr/9/7c1/pcp1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR b
