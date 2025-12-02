
import asyncio
import tornado

from peewee import *
from playhouse.sqlite_ext import *

import cchess

from cchess_utils import *

PIKA_BOOK_FILE = 'pikabook.db'
#---------------------------------------------------------
book_db = SqliteExtDatabase(PIKA_BOOK_FILE, pragmas=(
    ('cache_size', -1024 * 128),  # 128MB page-cache.
    ('journal_mode', 'wal'),  # Use WAL-mode (you should always use this!).
    ('synchronous', 0),
    ('foreign_keys', 0)))  # Enforce foreign-key constraints.

class BoardMove(Model):
    fen = CharField(index=True)
    deep  = IntegerField()
    score = IntegerField()
    mark  = CharField(null=True)
    move  = CharField()
    
    class Meta:
        database = book_db

#---------------------------------------------------------------------------
def is_fen_exist_in_db(fen):
    board = cchess.ChessBoard(fen)
    
    query = list(BoardMove.select().where(BoardMove.fen == fen))
    if len(query) > 0:
        return True
    
    fen_mirror = board.mirror().to_fen()
    query = list(BoardMove.select().where(BoardMove.fen == fen))
    if len(query) > 0:
        return True
 
    return False
    
#---------------------------------------------------------
if not Path(PIKA_BOOK_FILE).is_file():
        BoardMove.create_table()

engineMgr = EngineManager()
  