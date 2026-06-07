#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试CacheManager的实际使用情况
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from XQMagicUI.Cache import CacheManager, PositionInfo
from XQMagicUI.Globl import fenCache


def test_cache_manager_usage():
    """测试CacheManager的基本使用"""
    print("=== 测试CacheManager使用情况 ===")

    # 1. 检查fenCache的类型
    print(f"1. fenCache类型: {type(fenCache)}")
    print(f"   isinstance of CacheManager: {isinstance(fenCache, CacheManager)}")

    # 2. 测试基本操作（字典式访问）
    test_fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"

    # 2.1 测试__getitem__和__setitem__
    print(f"\n2. 测试字典式访问:")
    print(f"   fenCache['{test_fen}'] = {{'score': 100, 'score_e': 150}}")
    fenCache[test_fen] = {"score": 100, "score_e": 150}

    # 2.2 测试获取缓存项
    item = fenCache[test_fen]
    print(f"   获取缓存项类型: {type(item)}")
    print(f"   isinstance of PositionInfo: {isinstance(item, PositionInfo)}")
    print(f"   item['score']: {item['score']}")
    print(f"   item['score_e']: {item['score_e']}")

    # 2.3 测试update方法
    print(f"\n3. 测试update方法:")
    fenCache.update(test_fen, {"diff": 0, "best_moves": ["h2e2", "h0g2"]})
    item = fenCache[test_fen]
    print(f"   item['diff']: {item['diff']}")
    print(f"   item['best_moves']: {item['best_moves']}")

    # 2.4 测试__contains__
    print(f"\n4. 测试__contains__:")
    print(f"   test_fen in fenCache: {test_fen in fenCache}")
    print(f"   'invalid_fen' in fenCache: {'invalid_fen' in fenCache}")

    # 2.5 测试get方法
    print(f"\n5. 测试get方法:")
    item = fenCache.get(test_fen)
    print(f"   get(test_fen)类型: {type(item)}")
    print(f"   get('invalid_fen'): {fenCache.get('invalid_fen')}")

    # 2.6 测试to_dict方法
    print(f"\n6. 测试to_dict方法:")
    item_dict = item.to_dict()
    print(f"   to_dict()结果: {item_dict}")

    # 3. 测试实际使用模式
    print(f"\n7. 测试实际使用模式:")

    # 模式1: 直接赋值（字典式）
    fenCache["test_fen_1"] = {"score": 200, "source": "cloud"}
    print(f"   模式1: fenCache['test_fen_1'] = {{...}}")

    # 模式2: 更新现有项
    fenCache["test_fen_1"]["score_e"] = 250
    print(f"   模式2: fenCache['test_fen_1']['score_e'] = 250")

    # 模式3: 使用update方法
    fenCache.update("test_fen_2", {"score": 300, "diff": 10})
    print(f"   模式3: fenCache.update('test_fen_2', {{...}})")

    # 模式4: 检查键是否存在
    if "test_fen_2" in fenCache:
        print(f"   模式4: if 'test_fen_2' in fenCache: 通过")

    # 4. 测试缓存统计
    print(f"\n8. 测试缓存统计:")
    stats = fenCache.get_stats()
    print(f"   缓存统计: {stats}")

    # 5. 测试清除缓存
    print(f"\n9. 测试清除缓存:")
    fenCache.clear()
    stats_after = fenCache.get_stats()
    print(f"   清除后缓存大小: {stats_after['size']}")

    print(f"\n=== 测试完成 ===")


def test_compatibility_with_existing_code():
    """测试与现有代码的兼容性"""
    print(f"\n=== 测试与现有代码兼容性 ===")

    # 模拟现有代码中的使用模式
    test_fen = "test_fen_compat"

    # 模式A: 检查是否存在并创建
    if test_fen not in fenCache:
        fenCache[test_fen] = {}
    fenCache[test_fen].update({"score": 500, "diff": 5})
    print(f"   模式A: if fen not in fenCache: fenCache[fen] = {{}}")

    # 模式B: 直接访问和修改
    fenCache[test_fen]["score_e"] = 600
    print(f"   模式B: fenCache[fen]['score_e'] = value")

    # 模式C: 获取值并检查
    if "score" in fenCache[test_fen]:
        score = fenCache[test_fen]["score"]
        print(f"   模式C: if 'score' in fenCache[fen]: score = {score}")

    # 模式D: 整体赋值
    fenCache["test_fen_direct"] = {"score": 700, "best_moves": ["a0a1"]}
    print(f"   模式D: fenCache[fen] = {{...}}")

    # 验证结果
    item = fenCache[test_fen]
    print(f"\n   验证结果:")
    print(f"   fenCache['{test_fen}']['score']: {item['score']}")
    print(f"   fenCache['{test_fen}']['score_e']: {item['score_e']}")
    print(f"   fenCache['{test_fen}']['diff']: {item['diff']}")

    print(f"\n=== 兼容性测试完成 ===")


if __name__ == "__main__":
    test_cache_manager_usage()
    test_compatibility_with_existing_code()
