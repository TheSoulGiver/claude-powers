"""
EverMemOS 查询结果缓存 — Phase 1 性能优化
进程内 LRU 缓存，减少重复查询的数据库/向量库访问
"""
import hashlib
import time
import logging
from collections import OrderedDict
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LRUQueryCache:
    """进程内 LRU 查询缓存，支持 TTL 过期"""

    def __init__(self, maxsize: int = 500, ttl: int = 300):
        self._cache: OrderedDict = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            val, ts = self._cache[key]
            if time.time() - ts < self._ttl:
                self._cache.move_to_end(key)
                self._hits += 1
                return val
            del self._cache[key]
        self._misses += 1
        return None

    def set(self, key: str, value: Any) -> None:
        if key in self._cache:
            del self._cache[key]
        self._cache[key] = (value, time.time())
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    def invalidate_user(self, user_id: str) -> int:
        """失效指定用户的所有缓存，返回清除数量"""
        keys_to_del = [k for k in self._cache if f":{user_id}:" in k]
        for k in keys_to_del:
            del self._cache[k]
        if keys_to_del:
            logger.debug(f"缓存失效: user={user_id}, 清除{len(keys_to_del)}条")
        return len(keys_to_del)

    def clear(self) -> None:
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "maxsize": self._maxsize,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self._hits / total:.1%}" if total > 0 else "N/A",
        }


# 全局单例
_global_cache = LRUQueryCache(maxsize=500, ttl=300)


def get_query_cache() -> LRUQueryCache:
    return _global_cache


def make_cache_key(user_id: str, query: str, method: str = "hybrid") -> str:
    """生成缓存 key"""
    qh = hashlib.md5(query.encode()).hexdigest()[:12]
    return f"evermemos:{user_id}:{qh}:{method}"
