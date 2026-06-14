# -*- coding: utf-8 -*-
"""CacheManager 与 PositionInfo 单元测试.

覆盖范围:
- PositionInfo: 字段默认值、to_dict/update 兼容性、字典式访问 (__getitem__/__setitem__/__contains__/get)
- CacheManager: 基础 CRUD、LRU 淘汰、remove/clear、get_stats、字典式访问
"""

import threading

import pytest

from XQMagicUI.Cache import CacheManager, PositionInfo

INIT_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"


# =====================================================================
# PositionInfo
# =====================================================================
class TestPositionInfoDefaults:
    """PositionInfo 默认值."""

    def test_all_fields_have_defaults(self):
        p = PositionInfo()
        assert p.source == ""
        assert p.score_cloud is None
        assert p.score_engine is None
        assert p.diff is None
        assert p.best_moves == []
        assert p.best_prev == ""
        assert p.meta == {}

    def test_default_list_is_independent_per_instance(self):
        # 防止可变默认值共享
        a = PositionInfo()
        b = PositionInfo()
        a.best_moves.append("h2e2")
        assert b.best_moves == []


class TestPositionInfoToDict:
    """to_dict 兼容性映射."""

    def test_to_dict_maps_score_to_score_cloud(self):
        p = PositionInfo()
        p.score_cloud = 100
        p.score_engine = 150
        p.diff = -20
        p.best_moves = ["h2e2"]
        d = p.to_dict()
        assert d["score"] == 100
        assert d["score_e"] == 150
        assert d["diff"] == -20
        assert d["best_moves"] == ["h2e2"]
        assert d["source"] == ""

    def test_to_dict_includes_meta(self):
        p = PositionInfo()
        p.update({"custom_key": 42})
        d = p.to_dict()
        assert d["custom_key"] == 42


class TestPositionInfoUpdate:
    """update 方法对老式 dict 字段的兼容."""

    def test_update_score_key_maps_to_score_cloud(self):
        p = PositionInfo()
        p.update({"score": 50})
        assert p.score_cloud == 50

    def test_update_score_e_key_maps_to_score_engine(self):
        p = PositionInfo()
        p.update({"score_e": 80})
        assert p.score_engine == 80

    def test_update_known_attribute(self):
        p = PositionInfo()
        p.update({"diff": -10, "best_prev": "h9g7"})
        assert p.diff == -10
        assert p.best_prev == "h9g7"

    def test_update_unknown_key_goes_to_meta(self):
        p = PositionInfo()
        p.update({"custom_marker": "!?"})
        assert p.meta == {"custom_marker": "!?"}


class TestPositionInfoDictProtocol:
    """PositionInfo 的字典式访问."""

    def test_getitem_score_alias(self):
        p = PositionInfo()
        p.score_cloud = 99
        assert p["score"] == 99

    def test_getitem_score_e_alias(self):
        p = PositionInfo()
        p.score_engine = 200
        assert p["score_e"] == 200

    def test_getitem_direct_attribute(self):
        p = PositionInfo()
        p.diff = -30
        assert p["diff"] == -30

    def test_getitem_meta_key(self):
        p = PositionInfo()
        p.meta["note"] = "good"
        assert p["note"] == "good"

    def test_setitem_score_alias(self):
        p = PositionInfo()
        p["score"] = 42
        assert p.score_cloud == 42

    def test_setitem_score_e_alias(self):
        p = PositionInfo()
        p["score_e"] = 77
        assert p.score_engine == 77

    def test_setitem_direct_attribute(self):
        p = PositionInfo()
        p["diff"] = -5
        assert p.diff == -5

    def test_setitem_unknown_key_goes_to_meta(self):
        p = PositionInfo()
        p["bookmark_id"] = "abc"
        assert p.meta == {"bookmark_id": "abc"}

    def test_contains_score_when_set(self):
        p = PositionInfo()
        p.score_cloud = 1
        assert "score" in p
        assert "score" not in PositionInfo()

    def test_contains_score_e_when_set(self):
        p = PositionInfo()
        p.score_engine = 1
        assert "score_e" in p

    def test_contains_diff_when_set(self):
        p = PositionInfo()
        p.diff = 0  # None 时不在,设了 0 也在
        assert "diff" in p

    def test_contains_best_moves_and_prev_and_source_always_true(self):
        p = PositionInfo()
        for key in ("best_moves", "best_prev", "source"):
            assert key in p

    def test_contains_meta_key(self):
        p = PositionInfo()
        p.meta["marker"] = "!"
        assert "marker" in p

    def test_get_returns_value(self):
        p = PositionInfo()
        p.score_cloud = 5
        assert p.get("score") == 5

    def test_get_returns_default_for_missing(self):
        p = PositionInfo()
        assert p.get("score") is None
        assert p.get("score", -1) == -1
        assert p.get("totally_missing") is None
        assert p.get("totally_missing", "fallback") == "fallback"


# =====================================================================
# CacheManager
# =====================================================================
class TestCacheManagerBasics:
    """基础 CRUD 行为."""

    def test_empty_cache(self):
        cm = CacheManager(max_size=10)
        assert cm.get_stats() == {
            "size": 0,
            "max_size": 10,
            "memory_usage_mb": 0.0,
        }

    def test_setitem_then_getitem(self):
        cm = CacheManager(max_size=10)
        cm[INIT_FEN] = {"score": 100}
        item = cm[INIT_FEN]
        assert item.score_cloud == 100

    def test_getitem_unknown_creates_entry(self):
        cm = CacheManager(max_size=10)
        # default dict 语义:访问不存在的 fen 会创建空 PositionInfo
        item = cm[INIT_FEN]
        assert isinstance(item, PositionInfo)
        assert item.score_cloud is None
        # 应被放入缓存
        assert INIT_FEN in cm

    def test_contains(self):
        cm = CacheManager(max_size=10)
        assert INIT_FEN not in cm
        cm[INIT_FEN] = {"score": 1}
        assert INIT_FEN in cm

    def test_get_returns_empty_for_unknown(self):
        cm = CacheManager(max_size=10)
        item = cm.get(INIT_FEN)
        # get 不会自动创建缓存项,只返回临时空对象
        assert isinstance(item, PositionInfo)
        assert item.score_cloud is None
        assert INIT_FEN not in cm

    def test_get_returns_existing_with_lru_touch(self):
        cm = CacheManager(max_size=10)
        cm[INIT_FEN] = {"score": 10}
        item = cm.get(INIT_FEN)
        assert item.score_cloud == 10

    def test_update_existing_merges(self):
        cm = CacheManager(max_size=10)
        cm[INIT_FEN] = {"score": 10}
        cm.update(INIT_FEN, {"diff": -5})
        item = cm[INIT_FEN]
        assert item.score_cloud == 10  # 旧值保留
        assert item.diff == -5  # 新值合并

    def test_remove_existing(self):
        cm = CacheManager(max_size=10)
        cm[INIT_FEN] = {"score": 1}
        cm.remove(INIT_FEN)
        assert INIT_FEN not in cm

    def test_remove_missing_is_noop(self):
        cm = CacheManager(max_size=10)
        cm.remove("nonexistent")  # 不抛异常
        assert cm.get_stats()["size"] == 0

    def test_clear_empties_cache(self):
        cm = CacheManager(max_size=10)
        cm[INIT_FEN] = {"score": 1}
        cm["other_fen"] = {"score": 2}
        cm.clear()
        assert cm.get_stats()["size"] == 0
        assert INIT_FEN not in cm

    def test_get_stats_reflects_size(self):
        cm = CacheManager(max_size=5)
        for i in range(3):
            cm[f"fen_{i}"] = {"score": i}
        stats = cm.get_stats()
        assert stats["size"] == 3
        assert stats["max_size"] == 5
        # memory_usage_mb 是估算值,只校验是正数
        assert stats["memory_usage_mb"] > 0


class TestCacheManagerLRU:
    """LRU 淘汰语义."""

    def test_evicts_oldest_when_over_max_size(self):
        cm = CacheManager(max_size=2)
        cm["a"] = {"score": 1}
        cm["b"] = {"score": 2}
        cm["c"] = {"score": 3}  # 触发淘汰,a 应被移除
        assert "a" not in cm
        assert "b" in cm
        assert "c" in cm

    def test_update_existing_does_not_evict(self):
        cm = CacheManager(max_size=2)
        cm["a"] = {"score": 1}
        cm["b"] = {"score": 2}
        cm.update("a", {"score": 99})  # 更新已有,不应触发淘汰
        assert "a" in cm
        assert "b" in cm
        assert cm.get_stats()["size"] == 2

    def test_get_marks_as_recently_used(self):
        cm = CacheManager(max_size=2)
        cm["a"] = {"score": 1}
        cm["b"] = {"score": 2}
        # 访问 a,使其成为最近使用
        cm.get("a")
        cm["c"] = {"score": 3}
        # b 应被淘汰
        assert "a" in cm
        assert "b" not in cm
        assert "c" in cm

    def test_getitem_marks_as_recently_used(self):
        cm = CacheManager(max_size=2)
        cm["a"] = {"score": 1}
        cm["b"] = {"score": 2}
        _ = cm["a"]  # 触发 LRU touch
        cm["c"] = {"score": 3}
        assert "a" in cm
        assert "b" not in cm


class TestCacheManagerThreadSafety:
    """线程安全 smoke test."""

    def test_concurrent_writes_do_not_corrupt(self):
        cm = CacheManager(max_size=1000)
        errors = []

        def writer(prefix, count):
            try:
                for i in range(count):
                    cm[f"{prefix}_{i}"] = {"score": i}
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(f"t{i}", 50)) for i in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert cm.get_stats()["size"] == 8 * 50
