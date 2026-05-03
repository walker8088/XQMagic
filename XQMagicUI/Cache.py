# -*- coding: utf-8 -*-
"""
棋局缓存管理模块
提供线程安全的 LRU 缓存机制，用于存储局面评分、最佳着法等信息
"""

import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict


# -----------------------------------------------------#
# 1. 定义数据结构
# -----------------------------------------------------#
@dataclass
class PositionInfo:
    """棋局状态信息的结构化定义"""

    # 来源: 'engine' 或 'cloud'
    source: str = ""

    # 云库评分 (Red's perspective)
    score_cloud: int | None = None

    # 引擎评分 (Red's perspective)
    score_engine: int | None = None

    # 评分差 (相对于最佳着法)
    diff: int | None = None

    # 最佳后续着法列表 (ICCS)
    best_moves: list = field(default_factory=list)

    # 最佳前一步
    best_prev: str = ""

    # 其他自定义数据
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为普通字典 (兼容旧代码)"""
        return {
            "source": self.source,
            "score": self.score_cloud,
            "score_e": self.score_engine,
            "diff": self.diff,
            "best_moves": self.best_moves,
            "best_prev": self.best_prev,
            **self.meta,
        }

    def update(self, data: dict):
        """从外部字典更新属性"""
        for key, value in data.items():
            # 兼容旧代码中的 'score' -> 'score_cloud' 映射
            if key == "score":
                self.score_cloud = value
            elif key == "score_e":
                self.score_engine = value
            elif hasattr(self, key) and key != "meta":
                setattr(self, key, value)
            else:
                self.meta[key] = value

    # -----------------------------------------------------#
    # 支持字典式访问 (兼容旧代码: cache[fen]['score'] = 10)
    # -----------------------------------------------------#
    def __getitem__(self, key: str) -> Any:
        if key == "score":
            return self.score_cloud
        if key == "score_e":
            return self.score_engine
        if hasattr(self, key):
            return getattr(self, key)
        return self.meta.get(key)

    def __setitem__(self, key: str, value: Any):
        if key == "score":
            self.score_cloud = value
        elif key == "score_e":
            self.score_engine = value
        elif hasattr(self, key) and key not in ("meta", "to_dict", "update"):
            setattr(self, key, value)
        else:
            self.meta[key] = value

    def __contains__(self, key: str) -> bool:
        if key == "score":
            return self.score_cloud is not None
        if key == "score_e":
            return self.score_engine is not None
        if key == "diff":
            return self.diff is not None
        if key in ("best_moves", "best_prev", "source"):
            return True
        return hasattr(self, key) or key in self.meta

    def get(self, key: str, default=None):
        try:
            return self[key]
        except (AttributeError, KeyError):
            return default


# -----------------------------------------------------#
# 2. 缓存管理器
# -----------------------------------------------------#
class CacheManager:
    """
    线程安全的 LRU 缓存管理器
    """

    def __init__(self, max_size: int = 10000):
        self._max_size = max_size
        # OrderedDict 维护插入顺序，用于 LRU
        self._store: OrderedDict[str, PositionInfo] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, fen: str) -> PositionInfo:
        """获取缓存项，如果不存在则返回空对象，并将其标记为'最近使用'"""
        with self._lock:
            if fen in self._store:
                # 移动到末尾（表示最近使用过）
                self._store.move_to_end(fen)
                return self._store[fen]
            return PositionInfo()

    def update(self, fen: str, data: dict):
        """
        更新缓存项
        如果是新项且超出最大限制，则淘汰最旧的项
        """
        with self._lock:
            if fen in self._store:
                item = self._store[fen]
                item.update(data)
                self._store.move_to_end(fen)
            else:
                # 达到上限时，删除第一个（最久未使用）的元素
                if len(self._store) >= self._max_size:
                    self._store.popitem(last=False)

                # 创建新项并更新
                item = PositionInfo()
                item.update(data)
                self._store[fen] = item

    def remove(self, fen: str):
        """删除特定缓存"""
        with self._lock:
            self._store.pop(fen, None)

    def clear(self):
        """清空所有缓存"""
        with self._lock:
            self._store.clear()

    def get_stats(self) -> dict:
        """获取缓存统计信息"""
        with self._lock:
            return {
                "size": len(self._store),
                "max_size": self._max_size,
                "memory_usage_mb": len(self._store) * 0.005,  # 估算值
            }

    # 兼容旧代码: 允许直接像字典一样访问 Globl.cache[fen]['key'] = value
    def __getitem__(self, fen: str) -> PositionInfo:
        """返回 PositionInfo 对象，支持直接修改属性"""
        with self._lock:
            if fen in self._store:
                self._store.move_to_end(fen)
                return self._store[fen]
            # 如果不存在，创建一个新的并放入缓存（类似 defaultdict 行为）
            item = PositionInfo()
            self._store[fen] = item
            return item

    def __setitem__(self, fen: str, data: dict):
        """用于 cache[fen] = {...} 这种整体赋值场景"""
        self.update(fen, data)

    def __contains__(self, fen: str) -> bool:
        with self._lock:
            return fen in self._store
