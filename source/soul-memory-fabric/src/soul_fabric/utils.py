"""Soul Fabric 内联工具函数（从 ling-platform 解耦）。"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Coroutine, Literal, Set

from loguru import logger

# ---------------------------------------------------------------------------
# Validation (from soul/utils/validation.py)
# ---------------------------------------------------------------------------

USER_ID_PATTERN = re.compile(r"^[\w\-.:]{1,128}$")


def is_valid_user_id(user_id: Any) -> bool:
    """校验 user_id 是否为安全的字符串标识。"""
    return isinstance(user_id, str) and bool(USER_ID_PATTERN.fullmatch(user_id))


# ---------------------------------------------------------------------------
# Sensitive filter (from soul/ethics/sensitive_filter.py)
# ---------------------------------------------------------------------------

NEVER_STORE_PATTERNS = [
    r'密码[是为:].*\S+',
    r'password\s*[:=]\s*\S+',
    r'信用卡|银行卡号|CVV',
    r'\b\d{13,19}\b',
    r'(?:他|她|别人)说.*(?:不要告诉|秘密)',
    r'(?:api[_\s]?key|secret[_\s]?key|access[_\s]?token)\s*[:=]\s*\S+',
]

CAUTION_PATTERNS = [
    r'诊断.*(?:癌|抑郁|HIV|艾滋)',
    r'(?:确诊|检查出).*(?:疾病|病)',
]

_never_compiled = [re.compile(p, re.IGNORECASE) for p in NEVER_STORE_PATTERNS]
_caution_compiled = [re.compile(p, re.IGNORECASE) for p in CAUTION_PATTERNS]


def check_sensitivity(text: str) -> Literal["safe", "caution", "block"]:
    """三级检查: safe=可存储, caution=可存储但需脱敏, block=禁止存储"""
    if not text:
        return "safe"
    if any(p.search(text) for p in _never_compiled):
        return "block"
    if any(p.search(text) for p in _caution_compiled):
        return "caution"
    return "safe"


def contains_sensitive(text: str) -> bool:
    """检查文本是否包含不应存储的敏感信息（仅 NEVER_STORE 级别）"""
    return check_sensitivity(text) == "block"


# ---------------------------------------------------------------------------
# Background tasks (from soul/utils/async_tasks.py)
# ---------------------------------------------------------------------------

_BACKGROUND_TASKS: Set[asyncio.Task] = set()
_MAX_BACKGROUND_TASKS = 5000


def _prune_done_tasks():
    if not _BACKGROUND_TASKS:
        return
    done_tasks = {t for t in _BACKGROUND_TASKS if t.done()}
    if done_tasks:
        _BACKGROUND_TASKS.difference_update(done_tasks)


def create_logged_task(coro: Coroutine[Any, Any, Any], label: str) -> asyncio.Task:
    """创建后台任务并在完成时统一回收异常，同时持有强引用。"""
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    if len(_BACKGROUND_TASKS) > _MAX_BACKGROUND_TASKS:
        _prune_done_tasks()
        if len(_BACKGROUND_TASKS) > _MAX_BACKGROUND_TASKS:
            logger.warning(
                f"[SoulFabric] Too many background tasks ({len(_BACKGROUND_TASKS)}), "
                f"latest={label}"
            )

    def _on_done(done_task: asyncio.Task):
        _BACKGROUND_TASKS.discard(done_task)
        try:
            done_task.result()
        except asyncio.CancelledError:
            logger.debug(f"[SoulFabric] Background task cancelled: {label}")
        except Exception as e:
            logger.warning(f"[SoulFabric] Background task failed ({label}): {e}")

    task.add_done_callback(_on_done)
    return task


def reset_background_tasks_for_testing():
    """测试辅助: 取消并清空后台任务引用集合。"""
    for task in list(_BACKGROUND_TASKS):
        if not task.done():
            task.cancel()
    _BACKGROUND_TASKS.clear()
