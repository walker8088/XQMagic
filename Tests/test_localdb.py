from pathlib import Path
import pytest

def test_localbook_crud(tmp_path):
    from MagicUI.LocalDB import LocalBook
    db = tmp_path / "local.db"
    lb = LocalBook()
    assert lb.open(db)
    assert lb.saveBookmark("t1", "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1")
    allb = lb.getAllBookmarks()
    assert any(b['name'] == 't1' for b in allb)
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
    assert lb.saveRecord(fen, "a0a1", None)
    moves = lb.getMoves(fen)
    assert 'actions' in moves
    lb.close()

