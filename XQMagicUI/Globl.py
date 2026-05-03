from .Cache import CacheManager

# 初始化全局缓存 (限制为 10000 个局面)
fenCache = CacheManager(max_size=10000)
