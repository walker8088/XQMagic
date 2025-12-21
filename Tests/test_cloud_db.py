import pytest

def test_clouddb_parse(monkeypatch):
    from MagicUI.CloudDB import CloudDB
    from MagicUI import Globl
    Globl.fenCache = {}
    c = CloudDB(None)
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
    c.query_worker[fen] = object()
    resp = "move:a0a1,score:23|move:a1a2,score:25"
    c.onQueryFinished(fen, resp)
    assert fen in c.move_cache
    assert fen in Globl.fenCache
    ret = c.move_cache[fen]
    assert 'actions' in ret

