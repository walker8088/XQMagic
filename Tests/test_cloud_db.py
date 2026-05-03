import pytest


def test_clouddb_parse(monkeypatch):
    from XQMagicUI import Globl
    from XQMagicUI.CloudDB import CloudDB

    Globl.fenCache = {}
    c = CloudDB(None)
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
    c.query_worker[fen] = object()
    # 使用合法的 ICCS 移动：炮二平五(h2e2)、马二进三(h0g2)
    resp = "move:h2e2,score:23|move:h0g2,score:25"
    c.onQueryFinished(fen, resp)
    assert fen in c.move_cache
    assert fen in Globl.fenCache
    ret = c.move_cache[fen]
    assert "actions" in ret


def test_clouddb_score_perspective_red_to_move(setup_globl):
    """红方走子时，分数应保持原值（正数=红优），最佳着法 diff=0"""
    from XQMagicUI import Globl
    from XQMagicUI.CloudDB import CloudDB

    Globl.fenCache = {}
    c = CloudDB(None)
    # 红方走子的局面
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
    c.query_worker[fen] = object()
    # 云库返回：炮二平五(score=100) 优于 马二进三(score=50)
    resp = "move:h2e2,score:100|move:h0g2,score:50"
    c.onQueryFinished(fen, resp)

    ret = c.move_cache[fen]
    actions = ret["actions"]
    assert len(actions) == 2

    # 红方走子，分数不应取反
    assert actions["h2e2"]["score"] == 100
    assert actions["h0g2"]["score"] == 50
    # 最佳着法 diff=0
    assert actions["h2e2"]["diff"] == 0
    # 差着 diff 应为负数
    assert actions["h0g2"]["diff"] < 0


def test_clouddb_score_perspective_black_to_move(setup_globl):
    """黑方走子时，分数应取反到红方视角（负数=黑优），最佳着法 diff=0"""
    from XQMagicUI import Globl
    from XQMagicUI.CloudDB import CloudDB

    Globl.fenCache = {}
    c = CloudDB(None)
    # 黑方走子的局面
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR b - - 0 1"
    c.query_worker[fen] = object()
    # 云库返回：卒5进1(score=100) 优于 马8进7(score=50)（黑方视角）
    resp = "move:e6e5,score:100|move:h9g7,score:50"
    c.onQueryFinished(fen, resp)

    ret = c.move_cache[fen]
    actions = ret["actions"]
    assert len(actions) == 2

    # 黑方走子，分数应取反到红方视角（负数表示黑优）
    assert actions["e6e5"]["score"] == -100  # 最佳，黑优100
    assert actions["h9g7"]["score"] == -50  # 较差，黑优50

    # 最佳着法 diff=0
    assert actions["e6e5"]["diff"] == 0
    # 差着 diff 应为负数（表示偏离最佳）
    assert actions["h9g7"]["diff"] < 0


def test_clouddb_black_best_move_ranking(setup_globl):
    """黑方走子时，最佳着法应排在第一位（diff 降序排序）"""
    from XQMagicUI import Globl
    from XQMagicUI.CloudDB import CloudDB
    from XQMagicUI.Utils import CLOUD_SCORE_LIMIT

    Globl.fenCache = {}
    c = CloudDB(None)
    c.score_limit = 0  # 不设置过滤，保留所有着法
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR b - - 0 1"
    c.query_worker[fen] = object()
    # 云库返回三个着法：卒5进1最佳(100), 马8进7中等(70), 炮8平5最差(40)（黑方视角）
    # 合法的 ICCS 移动：e6e5(卒5进1), h9g7(马8进7), h7e7(炮8平5)
    resp = "move:e6e5,score:100|move:h9g7,score:70|move:h7e7,score:40"
    c.onQueryFinished(fen, resp)

    ret = c.move_cache[fen]
    actions = ret["actions"]

    # 验证最佳着法是卒5进1（diff=0）
    assert actions["e6e5"]["diff"] == 0
    # 其他着法 diff 都应为负数
    assert actions["h9g7"]["diff"] < 0
    assert actions["h7e7"]["diff"] < 0
    # 卒5进1 偏离程度应最小
    assert actions["h9g7"]["diff"] > actions["h7e7"]["diff"]


def test_clouddb_cache_update(setup_globl):
    """验证 fenCache 更新正确（分数已转换到红方视角）"""
    from XQMagicUI import Globl
    from XQMagicUI.CloudDB import CloudDB

    Globl.fenCache = {}
    c = CloudDB(None)
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR b - - 0 1"
    c.query_worker[fen] = object()
    # 使用合法的 ICCS 移动
    resp = "move:e6e5,score:150|move:h9g7,score:80"
    c.onQueryFinished(fen, resp)

    # 当前局面分数应缓存（黑方走子时，分数已转换为红方视角）
    assert fen in Globl.fenCache
    assert Globl.fenCache[fen]["score"] == -150  # 红方视角：负数表示黑优

    # 后续局面分数也应缓存
    ret = c.move_cache[fen]
    for act in ret["actions"].values():
        new_fen = act["new_fen"]
        assert new_fen in Globl.fenCache


def test_clouddb_mate_score(setup_globl):
    """将被杀局面分数设为 30000"""
    from XQMagicUI import Globl
    from XQMagicUI.CloudDB import CloudDB

    Globl.fenCache = {}
    c = CloudDB(None)
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
    c.query_worker[fen] = object()
    c.onQueryFinished(fen, "checkmate")

    ret = c.move_cache[fen]
    assert ret["score"] == 30000
    assert ret["mate"] == 0
    assert ret["actions"] == {}


def test_clouddb_unknown_response(setup_globl):
    """云库返回 unknown 时不缓存"""
    from XQMagicUI import Globl
    from XQMagicUI.CloudDB import CloudDB

    Globl.fenCache = {}
    c = CloudDB(None)
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
    c.query_worker[fen] = object()
    c.onQueryFinished(fen, "unknown")

    assert fen not in c.move_cache


def test_clouddb_score_limit_filtering(setup_globl):
    """超过分数限制的着法应被过滤"""
    from XQMagicUI import Globl
    from XQMagicUI.CloudDB import CloudDB
    from XQMagicUI.Utils import CLOUD_SCORE_LIMIT

    Globl.fenCache = {}
    c = CloudDB(None)
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR b - - 0 1"
    c.query_worker[fen] = object()
    c.score_limit = 50  # 设置过滤阈值
    # 卒5进1(score=200) vs 马8进7(score=100)，差值100 > 50，应被过滤
    resp = "move:e6e5,score:200|move:h9g7,score:100"
    c.onQueryFinished(fen, resp)

    ret = c.move_cache[fen]
    actions = ret["actions"]
    # 最佳着法应保留
    assert "e6e5" in actions
    # 差距超过 score_limit 的应被过滤
    assert "h9g7" not in actions


def test_clouddb_equal_scores(setup_globl):
    """多个着法分数相同时，diff 都应为 0"""
    from XQMagicUI import Globl
    from XQMagicUI.CloudDB import CloudDB

    Globl.fenCache = {}
    c = CloudDB(None)
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR b - - 0 1"
    c.query_worker[fen] = object()
    # 使用合法的 ICCS 移动
    resp = "move:e6e5,score:100|move:h9g7,score:100"
    c.onQueryFinished(fen, resp)

    ret = c.move_cache[fen]
    actions = ret["actions"]
    for move_iccs, act in actions.items():
        assert act["diff"] == 0, f"{move_iccs} should have diff=0 when scores are equal"
