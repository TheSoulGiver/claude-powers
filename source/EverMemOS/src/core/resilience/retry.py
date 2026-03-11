"""
指数退避重试 — EverMemOS Phase 2 可靠性增强
"""
import asyncio
import logging
from typing import TypeVar, Callable
from functools import wraps

logger = logging.getLogger(__name__)
T = TypeVar("T")


def async_retry(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
    """指数退避重试装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(
                            f"[Retry] {func.__name__} 第{attempt+1}次失败, "
                            f"{delay:.1f}s后重试: {e}"
                        )
                        await asyncio.sleep(delay)
            raise last_exc
        return wrapper
    return decorator
