"""Memory Fabric 独立 API 路由（可作为微服务运行）。"""

from __future__ import annotations

import os

from fastapi import APIRouter, FastAPI, HTTPException, Request
from loguru import logger

from ..api_models import (
    MemoryBenchmarkRequest,
    MemoryConsolidateRequest,
    MemoryDeleteUserRequest,
    MemoryEventRequest,
    MemoryRecallRequest,
    MemoryReflectRequest,
)
from ..service import get_memory_fabric

_AGENT_KEY = os.environ.get("SOUL_AGENT_KEY", "")


def _authenticate(request: Request) -> dict:
    """Simple agent key authentication for standalone mode."""
    if not _AGENT_KEY:
        return {"id": "anonymous", "role": "admin", "agent": True}

    key = request.headers.get("x-agent-key", "")
    if key and key == _AGENT_KEY:
        agent_id = request.headers.get("x-agent-id", "agent")
        return {"id": f"agent:{agent_id}", "role": "admin", "agent": True}

    raise HTTPException(status_code=401, detail="Invalid or missing X-Agent-Key")


def create_memory_fabric_router() -> APIRouter:
    router = APIRouter(prefix="/v1/memory", tags=["memory-fabric"])

    @router.post("/events")
    async def ingest_event(request: Request, payload: MemoryEventRequest):
        user = _authenticate(request)
        try:
            return await get_memory_fabric().ingest_event(
                req=payload,
                actor_id=str(user["id"]),
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @router.post("/consolidate")
    async def consolidate(request: Request, payload: MemoryConsolidateRequest):
        user = _authenticate(request)
        try:
            return await get_memory_fabric().consolidate(
                user_id=payload.user_id,
                dry_run=payload.dry_run,
                actor_id=str(user["id"]),
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @router.post("/recall")
    async def recall(request: Request, payload: MemoryRecallRequest):
        user = _authenticate(request)
        target_user_id = payload.user_id or str(user["id"])
        try:
            return await get_memory_fabric().recall(
                query=payload.query,
                user_id=target_user_id,
                top_k=payload.top_k,
                timeout_ms=payload.timeout_ms,
                include_citations=payload.include_citations,
                include_uncertainty=payload.include_uncertainty,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @router.post("/reflect")
    async def reflect(request: Request, payload: MemoryReflectRequest):
        user = _authenticate(request)
        target_user_id = payload.user_id or str(user["id"])
        try:
            return await get_memory_fabric().reflect(
                user_id=target_user_id,
                rule=payload.rule,
                rule_type=payload.rule_type,
                priority=payload.priority,
                active=payload.active,
                metadata=payload.metadata,
                actor_id=str(user["id"]),
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @router.post("/delete_user")
    async def delete_user(request: Request, payload: MemoryDeleteUserRequest):
        user = _authenticate(request)
        target_user_id = payload.user_id or str(user["id"])
        try:
            return await get_memory_fabric().delete_user(
                user_id=target_user_id,
                reason=payload.reason,
                actor_id=str(user["id"]),
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @router.get("/trace/{memory_id}")
    async def get_trace(request: Request, memory_id: str):
        user = _authenticate(request)
        try:
            return await get_memory_fabric().trace(
                memory_id=memory_id,
                requester_user_id=str(user["id"]),
                is_admin=True,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail="无权访问该记忆追踪") from e

    @router.get("/coverage")
    async def coverage(request: Request):
        _authenticate(request)
        report = get_memory_fabric().coverage_report()
        return report.model_dump(mode="json")

    @router.get("/slo")
    async def slo_status(request: Request):
        _authenticate(request)
        return await get_memory_fabric().slo_status()

    @router.post("/benchmark")
    async def benchmark(request: Request, payload: MemoryBenchmarkRequest):
        _authenticate(request)
        try:
            return await get_memory_fabric().benchmark(payload.suites)
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        except Exception as e:
            logger.warning(f"[MemoryFabric] benchmark failed: {e}")
            raise HTTPException(status_code=500, detail="benchmark failed") from e

    @router.get("/memos_pilot/status")
    async def memos_pilot_status(request: Request):
        _authenticate(request)
        return get_memory_fabric().memos_pilot_status()

    @router.get("/status")
    async def status(request: Request):
        return {"status": "ok", "service": "soul-memory-fabric"}

    return router


def create_app() -> FastAPI:
    """Create standalone FastAPI application."""
    app = FastAPI(
        title="Soul Memory Fabric",
        description="记忆控制平面微服务",
        version="0.1.0",
    )
    app.include_router(create_memory_fabric_router())
    return app


app = create_app()
