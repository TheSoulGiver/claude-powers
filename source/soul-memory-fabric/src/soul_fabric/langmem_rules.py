"""Phase 1: LangMem 程序性记忆适配层。"""

from __future__ import annotations

from typing import Any, Dict, List

import httpx
from loguru import logger

from .config import get_fabric_config
from .store import MemoryFabricStore


class LangMemProceduralService:
    """热路径 + 后台策略记忆（支持 local 与 HTTP LangMem 网关）。"""

    def __init__(self, store: MemoryFabricStore):
        self._store = store
        self._cfg = get_fabric_config()

    async def add_rule(
        self,
        tenant_id: str,
        user_id: str,
        rule: str,
        rule_type: str = "policy",
        priority: int = 50,
        active: bool = True,
        metadata: Dict[str, Any] | None = None,
    ) -> str:
        payload = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "rule": rule,
            "rule_type": rule_type,
            "priority": int(priority),
            "active": bool(active),
            "metadata": metadata or {},
        }

        if self._use_http():
            try:
                rule_id = await self._http_add_rule(payload)
                if rule_id:
                    return rule_id
            except Exception as e:
                if self._http_required():
                    raise RuntimeError(f"langmem http add failed: {e}") from e
                logger.warning(f"[SoulFabric] LangMem HTTP add fallback to local: {e}")

        return await self._store.add_procedural_rule(**payload)

    async def list_rules(
        self,
        tenant_id: str,
        user_id: str,
        active_only: bool = True,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        if self._use_http():
            try:
                rows = await self._http_list_rules(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    active_only=active_only,
                    limit=limit,
                )
                if rows:
                    return rows
            except Exception as e:
                if self._http_required():
                    raise RuntimeError(f"langmem http list failed: {e}") from e
                logger.warning(f"[SoulFabric] LangMem HTTP list fallback to local: {e}")

        return await self._store.list_procedural_rules(
            tenant_id=tenant_id,
            user_id=user_id,
            active_only=active_only,
            limit=limit,
        )

    async def fetch_for_recall(
        self,
        tenant_id: str,
        user_id: str,
        limit: int = 5,
    ) -> List[str]:
        rules = await self.list_rules(
            tenant_id=tenant_id,
            user_id=user_id,
            active_only=True,
            limit=limit,
        )
        return [f"[{r.get('rule_type', 'policy')}] {r.get('rule', '')}" for r in rules if r.get("rule")]

    def _use_http(self) -> bool:
        mode = self._cfg.langmem_mode
        if mode == "http":
            return True
        if mode == "auto" and self._cfg.langmem_url:
            return True
        return False

    def _http_required(self) -> bool:
        return self._cfg.langmem_mode == "http"

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._cfg.langmem_api_key:
            headers["Authorization"] = f"Bearer {self._cfg.langmem_api_key}"
        return headers

    async def _http_add_rule(self, payload: Dict[str, Any]) -> str:
        base = self._cfg.langmem_url.rstrip("/")
        timeout = max(1.0, self._cfg.langmem_timeout_sec)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{base}/v1/rules",
                json=payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
        return str(data.get("rule_id", ""))

    async def _http_list_rules(
        self,
        tenant_id: str,
        user_id: str,
        active_only: bool,
        limit: int,
    ) -> List[Dict[str, Any]]:
        base = self._cfg.langmem_url.rstrip("/")
        timeout = max(1.0, self._cfg.langmem_timeout_sec)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                f"{base}/v1/rules",
                params={
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "active_only": str(bool(active_only)).lower(),
                    "limit": max(1, min(limit, 50)),
                },
                headers=self._headers(),
            )
            resp.raise_for_status()
            payload = resp.json()
        rows = payload.get("rules", payload if isinstance(payload, list) else [])
        return [r for r in rows if isinstance(r, dict)]
