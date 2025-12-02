
import asyncio
import tornado


from peewee import *
from playhouse.sqlite_ext import *

from cchess_utils import *

#---------------------------------------------------------
book_db = SqliteExtDatabase('pikabook.db', pragmas=(
    ('cache_size', -1024 * 128),  # 128MB page-cache.
    ('journal_mode', 'wal'),  # Use WAL-mode (you should always use this!).
    ('synchronous', 0),
    ('foreign_keys', 0)))  # Enforce foreign-key constraints.

class PosMove(Model):
    fen = CharField(index=True)
    deep  = IntegerField()
    score = IntegerField()
    mark  = CharField(null=True)
    vmoves = JSONField()
    
    class Meta:
        database = book_db

#---------------------------------------------------------
engineMgr = EngineManager()
            
#---------------------------------------------------------
class MainHandler(tornado.web.RequestHandler):
    def get(self):
        global engineMgr
        fen = self.get_argument("fen", None, True)
        go_params = { 'depth': 3 }
        print(fen)
        ret = engineMgr.get_best_moves(fen, go_params)
        print(ret)
        self.write(str(ret))
    
    def put(self):
        body = json.loads(self.request.body)
        # do some stuff here
        self.write("{} your ID is {}".format(body['name'], body['id']))
        
def make_app():
    return tornado.web.Application([
        (r"/querybest", MainHandler),
    ])

#---------------------------------------------------------
async def main():
    ok = engineMgr.load_engine('.././Engine/pikafish_230408/pikafish.exe', 'uci')
    print(ok)          
    app = make_app()
    app.listen(8000)
    await asyncio.Event().wait()

#---------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())