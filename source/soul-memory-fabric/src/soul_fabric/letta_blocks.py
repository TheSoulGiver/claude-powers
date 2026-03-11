"""Phase 1: Letta Core Blocks 适配层。"""

from __future__ import annotations

from typing import Dict, List

import httpx
from loguru import logger

from .config import get_fabric_config
from .store import MemoryFabricStore


_DEFAULT_BLOCKS = {
    "persona": "你是一个有长期记忆与稳定价值观的陪伴式智能体。",
    "human": "用户希望被持续理解、被记住并获得可信赖的回应。",
    "policy": "优先正确性、安全性与尊重边界；不确定时明确表达不确定性。",
}


class LettaCoreBlocksService:
    """Core Blocks 服务：支持 local 存储与 HTTP Letta 网关。"""

    def __init__(self, store: MemoryFabricStore):
        self._store = store
        self._cfg = get_fabric_config()

    async def ensure_defaults(self, tenant_id: str, user_id: str):
        existing = await self.list_blocks(tenant_id=tenant_id, user_id=user_id, limit=10)
        existing_types = {row.get("block_type") for row in existing}
        for block_type, content in _DEFAULT_BLOCKS.items():
            if block_type in existing_types:
                continue
            await self.upsert_blocks(
                tenant_id=tenant_id,
                user_id=user_id,
                blocks={block_type: content},
                source="default",
            )

    async def upsert_blocks(
        self,
        tenant_id: str,
        user_id: str,
        blocks: Dict[str, str],
        source: str = "reflect",
    ):
        cleaned = {
            k: (v or "").strip()[:4000]
            for k, v in blocks.items()
            if (v or "").strip()
        }
        if not cleaned:
            return

        if self._use_http():
            try:
                await self._http_upsert(tenant_id, user_id, cleaned, source=source)
                return
            except Exception as e:
                if self._http_required():
                    raise RuntimeError(f"letta http upsert failed: {e}") from e
                logger.warning(f"[SoulFabric] Letta HTTP upsert fallback to local: {e}")

        for block_type, content in cleaned.items():
            await self._store.upsert_core_block(
                tenant_id=tenant_id,
                user_id=user_id,
                block_type=block_type,
                content=content,
                metadata={"source": source, "backend": "local"},
            )

    async def list_blocks(self, tenant_id: str, user_id: str, limit: int = 20) -> List[Dict[str, str]]:
        if self._use_http():
            try:
                rows = await self._http_list(tenant_id=tenant_id, user_id=user_id, limit=limit)
                if rows:
                    return rows
            except Exception as e:
                if self._http_required():
                    raise RuntimeError(f"letta http list failed: {e}") from e
                logger.warning(f"[SoulFabric] Letta HTTP list fallback to local: {e}")
        return await self._store.list_core_blocks(tenant_id=tenant_id, user_id=user_id, limit=limit)

    async def fetch_for_recall(self, tenant_id: str, user_id: str, limit: int = 3) -> List[str]:
        await self.ensure_defaults(tenant_id=tenant_id, user_id=user_id)
        rows = await self.list_blocks(tenant_id=tenant_id, user_id=user_id, limit=limit)
        snippets = []
        for row in rows:
            block_type = row.get("block_type", "block")
            content = row.get("content", "")
            if content:
                snippets.append(f"[{block_type}] {content}")
        return snippets

    def _use_http(self) -> bool:
        mode = self._cfg.letta_mode
        if mode == "http":
            return True
        if mode == "auto" and self._cfg.letta_url:
            return True
        return False

    def _http_required(self) -> bool:
        return self._cfg.letta_mode == "http"

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._cfg.letta_api_key:
            headers["Authorization"] = f"Bearer {self._cfg.letta_api_key}"
        return headers

    async def _http_upsert(
        self,
        tenant_id: str,
        user_id: str,
        blocks: Dict[str, str],
        source: str,
    ):
        base = self._cfg.letta_url.rstrip("/")
        timeout = max(1.0, self._cfg.letta_timeout_sec)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for block_type, content in blocks.items():
                resp = await client.put(
                    f"{base}/v1/blocks/{block_type}",
                    json={
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "content": content,
                        "metadata": {"source": source, "backend": "http"},
                    },
                    headers=self._headers(),
                )
                resp.raise_for_status()

    async def _http_list(self, tenant_id: str, user_id: str, limit: int) -> List[Dict[str, str]]:
        base = self._cfg.letta_url.rstrip("/")
        timeout = max(1.0, self._cfg.letta_timeout_sec)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                f"{base}/v1/blocks",
                params={
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "limit": max(1, min(limit, 20)),
                },
                headers=self._headers(),
            )
            resp.raise_for_status()
            payload = resp.json()
        rows = payload.get("blocks", payload if isinstance(payload, list) else [])
        return [
            {
                "block_type": str(r.get("block_type", "")),
                "content": str(r.get("content", "")),
            }
            for r in rows
            if isinstance(r, dict)
        ]
