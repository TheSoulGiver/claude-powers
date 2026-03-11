"""Memory Fabric 持久化与审计存储（自带 MongoDB 连接管理）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from loguru import logger

from .atom import MemoryAtom, MemoryState
from .config import get_fabric_config

# ---------------------------------------------------------------------------
# Collection name constants
# ---------------------------------------------------------------------------

MEMORY_ATOMS = "soul_memory_atoms"
MEMORY_TRACES = "soul_memory_traces"
CORE_BLOCKS = "soul_core_blocks"
PROCEDURAL_RULES = "soul_procedural_rules"
SAFETY_SHADOW = "soul_safety_shadow"
BENCHMARK_RUNS = "soul_benchmark_runs"
SLO_METRICS = "soul_slo_metrics"

# ---------------------------------------------------------------------------
# Self-contained MongoDB connection
# ---------------------------------------------------------------------------

_client = None


def _get_db():
    global _client
    if _client is None:
        from motor.motor_asyncio import AsyncIOMotorClient

        cfg = get_fabric_config()
        _client = AsyncIOMotorClient(cfg.mongo_url)
    cfg = get_fabric_config()
    return _client[cfg.mongo_database]


async def get_collection(name: str):
    """Returns motor collection or None if connection fails."""
    try:
        db = _get_db()
        return db[name]
    except Exception as e:
        logger.warning(f"[SoulFabric] MongoDB collection '{name}' unavailable: {e}")
        return None


def reset_store_client_for_testing():
    """测试辅助: 重置 MongoDB 客户端。"""
    global _client
    _client = None


# ---------------------------------------------------------------------------
# Store class
# ---------------------------------------------------------------------------


CALLER_ROLES_GLOBAL = {"system", "admin"}


class MemoryFabricStore:
    """控制平面数据库读写封装。"""

    # ------------------------------------------------------------------
    # Query guards — 三层隔离第一层
    # ------------------------------------------------------------------

    @staticmethod
    def _scoped_query(user_id: str, extra_filter: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """构建以 user_id 为强制前缀的查询条件。所有用户级查询必经此方法。"""
        if not user_id or not str(user_id).strip():
            raise ValueError("user_id is required for scoped queries")
        query: Dict[str, Any] = {"user_id": str(user_id).strip()}
        if extra_filter:
            query.update(extra_filter)
        return query

    @staticmethod
    def _global_query(caller_role: str, extra_filter: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """构建全局查询条件。仅 system/admin 角色可调用。"""
        if caller_role not in CALLER_ROLES_GLOBAL:
            raise PermissionError(f"global queries require system/admin role, got '{caller_role}'")
        return dict(extra_filter) if extra_filter else {}

    async def upsert_atom(self, atom: MemoryAtom) -> Tuple[MemoryAtom, bool]:
        """按 idempotency_key 幂等写入 MemoryAtom。"""
        coll = await get_collection(MEMORY_ATOMS)
        if coll is None:
            raise RuntimeError("memory atom collection unavailable")

        if atom.idempotency_key:
            existing = await coll.find_one(
                {
                    "tenant_id": atom.tenant_id,
                    "user_id": atom.user_id,
                    "idempotency_key": atom.idempotency_key,
                }
            )
            if existing:
                existing.pop("_id", None)
                return MemoryAtom.model_validate(existing), False

        doc = atom.model_dump(mode="python")
        if isinstance(doc.get("state"), MemoryState):
            doc["state"] = doc["state"].value

        try:
            await coll.insert_one(doc)
            return atom, True
        except Exception as e:
            logger.warning(f"[SoulFabric] upsert_atom insert failed: {e}")
            if atom.idempotency_key:
                existing = await coll.find_one(
                    {
                        "tenant_id": atom.tenant_id,
                        "user_id": atom.user_id,
                        "idempotency_key": atom.idempotency_key,
                    }
                )
                if existing:
                    existing.pop("_id", None)
                    return MemoryAtom.model_validate(existing), False
            raise

    async def load_atom(
        self,
        memory_id: str,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """加载单条 MemoryAtom，强制 user_id 隔离。"""
        if not user_id or not str(user_id).strip():
            raise ValueError("user_id is required for load_atom (use load_atom_global for admin)")
        coll = await get_collection(MEMORY_ATOMS)
        if coll is None:
            return None
        query = self._scoped_query(user_id, {"memory_id": memory_id})
        doc = await coll.find_one(query)
        if doc:
            doc.pop("_id", None)
        return doc

    async def load_atom_global(
        self,
        memory_id: str,
        caller_role: str = "system",
    ) -> Optional[Dict[str, Any]]:
        """管理员/系统加载 atom（无 user_id 限定）。仅 system/admin 可调用。"""
        query = self._global_query(caller_role, {"memory_id": memory_id})
        coll = await get_collection(MEMORY_ATOMS)
        if coll is None:
            return None
        doc = await coll.find_one(query)
        if doc:
            doc.pop("_id", None)
        return doc

    async def list_recent_atoms(
        self,
        user_id: str,
        tenant_id: str = "default",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        coll = await get_collection(MEMORY_ATOMS)
        if coll is None:
            return []
        query = self._scoped_query(user_id, {"tenant_id": tenant_id})
        cursor = coll.find(
            query,
            sort=[("event_time", -1)],
            limit=max(1, min(limit, 200)),
        )
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results

    async def set_atom_state(
        self,
        memory_id: str,
        state: MemoryState,
        reason: str = "",
        user_id: str = "",
    ) -> bool:
        """修改 atom 状态，强制 user_id 隔离。"""
        if not user_id or not str(user_id).strip():
            raise ValueError("user_id is required for set_atom_state")
        coll = await get_collection(MEMORY_ATOMS)
        if coll is None:
            return False
        query = self._scoped_query(user_id, {"memory_id": memory_id})
        update = {
            "$set": {
                "state": state.value,
                "updated_at": datetime.now(timezone.utc),
            }
        }
        if reason:
            update["$set"]["state_reason"] = reason
        res = await coll.update_one(query, update)
        return bool(res.modified_count)

    async def update_atom_fields(
        self,
        memory_id: str,
        fields: Dict[str, Any],
        user_id: str = "",
    ) -> bool:
        """更新 atom 字段，强制 user_id 隔离。"""
        if not user_id or not str(user_id).strip():
            raise ValueError("user_id is required for update_atom_fields")
        if not fields:
            return False
        coll = await get_collection(MEMORY_ATOMS)
        if coll is None:
            return False
        query = self._scoped_query(user_id, {"memory_id": memory_id})
        payload = dict(fields)
        payload["updated_at"] = datetime.now(timezone.utc)
        res = await coll.update_one(
            query,
            {"$set": payload},
        )
        return bool(res.matched_count)

    async def append_trace(
        self,
        memory_id: str,
        user_id: str,
        event_type: str,
        payload: Dict[str, Any],
        actor_id: str = "system",
        status: str = "ok",
    ) -> str:
        coll = await get_collection(MEMORY_TRACES)
        if coll is None:
            raise RuntimeError("memory trace collection unavailable")

        trace_id = f"trace_{uuid4().hex}"
        await coll.insert_one(
            {
                "trace_id": trace_id,
                "memory_id": memory_id,
                "user_id": user_id,
                "event_type": event_type,
                "status": status,
                "actor_id": actor_id,
                "payload": payload,
                "created_at": datetime.now(timezone.utc),
            }
        )
        return trace_id

    async def load_traces(
        self,
        memory_id: str,
        user_id: str,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """加载审计追踪，强制 user_id 隔离。"""
        if not user_id or not str(user_id).strip():
            raise ValueError("user_id is required for load_traces (use load_traces_global for admin)")
        coll = await get_collection(MEMORY_TRACES)
        if coll is None:
            return []
        query = self._scoped_query(user_id, {"memory_id": memory_id})
        cursor = coll.find(
            query,
            sort=[("created_at", 1)],
            limit=max(1, min(limit, 1000)),
        )
        traces = []
        async for doc in cursor:
            doc.pop("_id", None)
            traces.append(doc)
        return traces

    async def load_traces_global(
        self,
        memory_id: str,
        caller_role: str = "system",
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """管理员/系统加载审计追踪（无 user_id 限定）。仅 system/admin 可调用。"""
        query = self._global_query(caller_role, {"memory_id": memory_id})
        coll = await get_collection(MEMORY_TRACES)
        if coll is None:
            return []
        cursor = coll.find(
            query,
            sort=[("created_at", 1)],
            limit=max(1, min(limit, 1000)),
        )
        traces = []
        async for doc in cursor:
            doc.pop("_id", None)
            traces.append(doc)
        return traces

    async def upsert_core_block(
        self,
        tenant_id: str,
        user_id: str,
        block_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        coll = await get_collection(CORE_BLOCKS)
        if coll is None:
            return False
        now = datetime.now(timezone.utc)
        await coll.update_one(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "block_type": block_type,
            },
            {
                "$set": {
                    "content": content,
                    "metadata": metadata or {},
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "created_at": now,
                },
            },
            upsert=True,
        )
        return True

    async def list_core_blocks(
        self,
        tenant_id: str,
        user_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        coll = await get_collection(CORE_BLOCKS)
        if coll is None:
            return []

        query = self._scoped_query(user_id, {"tenant_id": tenant_id})
        cursor = coll.find(
            query,
            sort=[("updated_at", -1)],
            limit=max(1, min(limit, 50)),
        )
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results

    async def add_procedural_rule(
        self,
        tenant_id: str,
        user_id: str,
        rule: str,
        rule_type: str,
        priority: int,
        active: bool,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        coll = await get_collection(PROCEDURAL_RULES)
        if coll is None:
            raise RuntimeError("procedural rules collection unavailable")

        rule_id = f"rule_{uuid4().hex}"
        now = datetime.now(timezone.utc)
        await coll.insert_one(
            {
                "rule_id": rule_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "rule": rule,
                "rule_type": rule_type,
                "priority": int(priority),
                "active": bool(active),
                "metadata": metadata or {},
                "created_at": now,
                "updated_at": now,
            }
        )
        return rule_id

    async def list_procedural_rules(
        self,
        tenant_id: str,
        user_id: str,
        active_only: bool = True,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        coll = await get_collection(PROCEDURAL_RULES)
        if coll is None:
            return []

        extra: Dict[str, Any] = {"tenant_id": tenant_id}
        if active_only:
            extra["active"] = True
        query = self._scoped_query(user_id, extra)

        cursor = coll.find(
            query,
            sort=[("priority", -1), ("updated_at", -1)],
            limit=max(1, min(limit, 100)),
        )
        rules = []
        async for doc in cursor:
            doc.pop("_id", None)
            rules.append(doc)
        return rules

    async def add_shadow_entry(
        self,
        tenant_id: str,
        user_id: str,
        related_memory_id: Optional[str],
        reason: str,
        risk_score: float,
        payload: Dict[str, Any],
        state: str = "quarantined",
    ) -> str:
        coll = await get_collection(SAFETY_SHADOW)
        if coll is None:
            raise RuntimeError("safety shadow collection unavailable")

        shadow_id = f"shadow_{uuid4().hex}"
        await coll.insert_one(
            {
                "shadow_id": shadow_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "related_memory_id": related_memory_id,
                "reason": reason,
                "risk_score": risk_score,
                "state": state,
                "payload": payload,
                "created_at": datetime.now(timezone.utc),
            }
        )
        return shadow_id

    async def list_shadow_entries(
        self,
        tenant_id: str,
        user_id: str,
        state: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        coll = await get_collection(SAFETY_SHADOW)
        if coll is None:
            return []

        extra: Dict[str, Any] = {"tenant_id": tenant_id}
        if state:
            extra["state"] = state
        query = self._scoped_query(user_id, extra)

        cursor = coll.find(
            query,
            sort=[("created_at", -1)],
            limit=max(1, min(limit, 100)),
        )
        rows = []
        async for doc in cursor:
            doc.pop("_id", None)
            rows.append(doc)
        return rows

    async def record_benchmark_run(
        self,
        suite: str,
        score: float,
        status: str,
        details: Dict[str, Any],
        baseline_delta: Optional[float] = None,
    ):
        coll = await get_collection(BENCHMARK_RUNS)
        if coll is None:
            return
        await coll.insert_one(
            {
                "suite": suite,
                "score": score,
                "status": status,
                "details": details,
                "baseline_delta": baseline_delta,
                "created_at": datetime.now(timezone.utc),
            }
        )

    async def recent_benchmark_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        coll = await get_collection(BENCHMARK_RUNS)
        if coll is None:
            return []
        cursor = coll.find({}, sort=[("created_at", -1)], limit=max(1, min(limit, 100)))
        rows = []
        async for doc in cursor:
            doc.pop("_id", None)
            rows.append(doc)
        return rows

    async def record_slo_metric(
        self,
        metric_name: str,
        metric_value: float,
        stage: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        coll = await get_collection(SLO_METRICS)
        if coll is None:
            return
        await coll.insert_one(
            {
                "metric_name": metric_name,
                "metric_value": float(metric_value),
                "stage": stage,
                "metadata": metadata or {},
                "created_at": datetime.now(timezone.utc),
            }
        )

    async def recent_slo_metrics(
        self,
        metric_name: str,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        coll = await get_collection(SLO_METRICS)
        if coll is None:
            return []

        cursor = coll.find(
            {"metric_name": metric_name},
            sort=[("created_at", -1)],
            limit=max(1, min(limit, 2000)),
        )
        rows = []
        async for doc in cursor:
            doc.pop("_id", None)
            rows.append(doc)
        return rows

    async def delete_expired_atoms(
        self,
        retention_days: int,
        caller_role: str = "system",
    ) -> int:
        coll = await get_collection(MEMORY_ATOMS)
        if coll is None:
            return 0

        cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, int(retention_days)))
        query = self._global_query(caller_role, {
            "ingest_time": {"$lt": cutoff},
            "state": {"$ne": MemoryState.QUARANTINED.value},
        })
        result = await coll.delete_many(query)
        return int(result.deleted_count)
