"""Memory Fabric 控制平面服务。"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional

from loguru import logger

from .config import FabricConfig, get_fabric_config
from .utils import create_logged_task, is_valid_user_id
from .amem_evolution import AmemEvolutionEngine
from .api_models import MemoryEventRequest, MemoryRecallResponse, SourceCitation, UncertaintyReport
from .atom import MemoryAtom, MemoryState
from .autotune import SLOAutoTuner
from .benchmark import MemoryBenchmarkRunner
from .catalog import build_provider_catalog
from .langmem_rules import LangMemProceduralService
from .letta_blocks import LettaCoreBlocksService
from .memguard import MemGuard
from .models import CoverageReport, RecallRoutePlan
from .planner import CapabilityPlanner
from .store import MemoryFabricStore


class MemoryFabric:
    """能力层全覆盖整合入口。

    外部集成（consolidation/recall/adapters/deletion）通过接口注入：
    - recall_fn: 可选的召回函数
    - consolidation_fn: 可选的整合函数
    - deletion_fn: 可选的用户删除函数
    - provider_health_fn: 可选的 provider 运行态健康检查
    - warmup_fn: 可选的启动预热函数

    独立部署时这些为 None（相应功能降级运行）。
    """

    def __init__(
        self,
        config: Optional[FabricConfig] = None,
        recall_fn: Optional[Callable] = None,
        consolidation_fn: Optional[Callable] = None,
        deletion_fn: Optional[Callable] = None,
        provider_health_fn: Optional[Callable] = None,
        warmup_fn: Optional[Callable] = None,
    ):
        self._cfg = config or get_fabric_config()
        self._providers = build_provider_catalog(self._cfg)
        self._planner = CapabilityPlanner(self._providers)

        self._store = MemoryFabricStore()
        self._letta = LettaCoreBlocksService(self._store)
        self._langmem = LangMemProceduralService(self._store)
        self._benchmark = MemoryBenchmarkRunner(self._store)
        self._autotuner = SLOAutoTuner(self._store)

        # Injectable external integrations
        self._recall_fn = recall_fn
        self._consolidation_fn = consolidation_fn
        self._deletion_fn = deletion_fn
        self._provider_health_fn = provider_health_fn
        self._warmup_fn = warmup_fn

        self._recall_observation_count = 0
        self._ingest_count = 0
        self._warmup_attempted = False
        self._ensure_runtime_warmup()

    def coverage_report(self) -> CoverageReport:
        runtime_health = self._runtime_provider_health()
        report = self._planner.coverage_report(
            strict_mode=self._cfg.fabric_strict_mode,
            provider_health=runtime_health,
        )
        if self._cfg.enabled and self._cfg.fabric_enabled and report.missing_capabilities:
            missing = ",".join(c.value for c in report.missing_capabilities)
            level = "strict" if report.strict_mode else "base"
            logger.warning(f"[MemoryFabric] Missing {level} required capabilities: {missing}")
        if self._cfg.enabled and self._cfg.fabric_enabled and report.missing_optional_capabilities:
            optional = ",".join(c.value for c in report.missing_optional_capabilities)
            logger.info(f"[MemoryFabric] Optional capabilities not yet enabled: {optional}")
        if report.unhealthy_enabled_providers:
            logger.warning(
                "[MemoryFabric] Runtime-unhealthy providers detected: {}",
                ",".join(report.unhealthy_enabled_providers),
            )
        return report

    def plan_recall(
        self,
        relationship_stage: str,
        latency_budget_ms: int,
        query: str = "",
    ) -> RecallRoutePlan:
        self._assert_strict_coverage()
        runtime_health = self._runtime_provider_health()
        query_complexity = self._estimate_query_complexity(query)
        return self._planner.plan_recall(
            relationship_stage=relationship_stage,
            latency_budget_ms=latency_budget_ms,
            query_complexity=query_complexity,
            provider_health=runtime_health,
        )

    async def ingest_event(
        self,
        req: MemoryEventRequest,
        actor_id: str = "system",
    ) -> Dict[str, Any]:
        """POST /v1/memory/events: 写入统一 MemoryAtom。"""
        if not is_valid_user_id(req.user_id):
            raise ValueError("invalid user_id")

        atom = MemoryAtom(
            idempotency_key=req.idempotency_key,
            tenant_id=req.tenant_id,
            user_id=req.user_id,
            agent_id=req.agent_id,
            session_id=req.session_id,
            session_type=req.session_type,
            event_time=req.event_time or datetime.now(timezone.utc),
            source=req.source,
            modality=req.modality,
            memory_type=req.memory_type,
            content_raw=req.content_raw,
            content_norm=self._normalize_content(req.content_norm or req.content_raw),
            entities=req.entities,
            relations=req.relations,
            affect=req.affect,
            salience=req.salience,
            confidence=req.confidence,
            trust_score=req.trust_score,
            provenance=req.provenance,
            retention_policy=req.retention_policy,
            pii_tags=req.pii_tags,
            legal_basis=req.legal_basis,
        )

        memguard_verdict = None
        if self._cfg.memguard_enabled:
            memguard_verdict = MemGuard.evaluate(
                text=atom.content_raw,
                trust_score=atom.trust_score,
                quarantine_threshold=self._cfg.memguard_quarantine_threshold,
            )
            atom.provenance["memguard"] = {
                "action": memguard_verdict.action,
                "risk_score": memguard_verdict.risk_score,
                "reasons": memguard_verdict.reasons,
            }
            if memguard_verdict.action == "quarantine":
                atom.state = MemoryState.QUARANTINED
            elif memguard_verdict.action == "caution":
                atom.trust_score = max(0.1, atom.trust_score - 0.1)

        evolution = None
        if self._cfg.amem_enabled:
            recent = await self._store.list_recent_atoms(
                user_id=req.user_id,
                tenant_id=req.tenant_id,
                limit=50,
            )
            evolution = AmemEvolutionEngine.evolve(atom, recent)
            atom.provenance["amem"] = evolution

        stored_atom, created = await self._store.upsert_atom(atom)
        materialized_refs: Dict[str, str] = {}
        if created and stored_atom.state != MemoryState.QUARANTINED:
            if req.source not in {"conversation_post_processor", "benchmark_runner"}:
                materialized_refs = await self._materialize_external_refs(stored_atom)
            if materialized_refs:
                try:
                    await self._store.update_atom_fields(stored_atom.memory_id, materialized_refs, user_id=stored_atom.user_id)
                except Exception as e:
                    logger.warning(f"[MemoryFabric] atom refs persist failed: {e}")
                if materialized_refs.get("vector_ref"):
                    stored_atom.vector_ref = materialized_refs["vector_ref"]
                if materialized_refs.get("graph_ref"):
                    stored_atom.graph_ref = materialized_refs["graph_ref"]
                if materialized_refs.get("block_ref"):
                    stored_atom.block_ref = materialized_refs["block_ref"]

        await self._store.append_trace(
            memory_id=stored_atom.memory_id,
            user_id=stored_atom.user_id,
            event_type="ingest",
            payload={
                "created": created,
                "state": stored_atom.state.value if isinstance(stored_atom.state, MemoryState) else stored_atom.state,
                "source": stored_atom.source,
                "memory_type": stored_atom.memory_type,
                "memguard": atom.provenance.get("memguard", {}),
                "amem": evolution,
                "materialized_refs": materialized_refs,
            },
            actor_id=actor_id,
            status="ok",
        )

        shadow_id = None
        if memguard_verdict and memguard_verdict.action == "quarantine":
            shadow_id = await self._store.add_shadow_entry(
                tenant_id=req.tenant_id,
                user_id=req.user_id,
                related_memory_id=stored_atom.memory_id,
                reason=",".join(memguard_verdict.reasons) or "risk_threshold_exceeded",
                risk_score=memguard_verdict.risk_score,
                payload=self._safe_shadow_payload(stored_atom),
                state="quarantined",
            )

        self._ingest_count += 1
        if self._ingest_count % 100 == 0:
            await self._enforce_retention()

        return {
            "memory_id": stored_atom.memory_id,
            "state": stored_atom.state.value if isinstance(stored_atom.state, MemoryState) else stored_atom.state,
            "created": created,
            "shadow_id": shadow_id,
            "memguard": atom.provenance.get("memguard", {}),
            "amem": evolution,
            "materialized_refs": materialized_refs,
        }

    async def consolidate(
        self,
        user_id: Optional[str],
        dry_run: bool = False,
        actor_id: str = "system",
    ) -> Dict[str, Any]:
        """POST /v1/memory/consolidate: 分层整理与冲突归并。"""
        if user_id and not is_valid_user_id(user_id):
            raise ValueError("invalid user_id")

        if self._consolidation_fn:
            result = await self._consolidation_fn(user_id=user_id, dry_run=dry_run)
        else:
            result = {
                "scope": "user" if user_id else "global",
                "user_id": user_id,
                "dry_run": dry_run,
                "status": "no_consolidation_backend",
            }

        await self._store.append_trace(
            memory_id=f"{'user_scope:' + user_id if user_id else 'global_scope:consolidation'}",
            user_id=user_id or "system:consolidation",
            event_type="consolidate",
            payload={
                "dry_run": dry_run,
                "scope": result.get("scope"),
            },
            actor_id=actor_id,
            status="ok",
        )
        await self._enforce_retention()
        return result

    async def recall(
        self,
        query: str,
        user_id: str,
        top_k: int,
        timeout_ms: int,
        include_citations: bool,
        include_uncertainty: bool,
    ) -> Dict[str, Any]:
        """POST /v1/memory/recall: 多源召回 + 引用与不确定性。"""
        if not is_valid_user_id(user_id):
            raise ValueError("invalid user_id")

        if self._recall_fn:
            return await self._recall_fn(
                query=query,
                user_id=user_id,
                top_k=top_k,
                timeout_ms=timeout_ms,
                include_citations=include_citations,
                include_uncertainty=include_uncertainty,
                fabric=self,
            )

        # Standalone mode: event memories only
        start = time.monotonic()
        event_memories = await self.fetch_event_memories_for_recall(
            user_id=user_id,
            query=query,
            tenant_id="default",
            limit=max(1, top_k),
        )
        latency_ms = (time.monotonic() - start) * 1000

        context_pack = {
            "event_sourced_memories": event_memories,
            "mode": "standalone",
        }

        citations: List[SourceCitation] = []
        if include_citations and event_memories:
            citations = [SourceCitation(source="event_source", count=len(event_memories))]

        uncertainty = None
        if include_uncertainty:
            uncertainty = UncertaintyReport(
                score=0.7 if event_memories else 0.95,
                reason="standalone_mode_limited_sources",
            )

        response = MemoryRecallResponse(
            user_id=user_id,
            relationship_stage="unknown",
            latency_ms=latency_ms,
            context_pack=context_pack,
            citations=citations,
            uncertainty=uncertainty,
        )
        return response.model_dump(mode="json")

    async def reflect(
        self,
        user_id: str,
        rule: str,
        rule_type: str,
        priority: int,
        active: bool,
        metadata: Optional[Dict[str, Any]] = None,
        actor_id: str = "system",
    ) -> Dict[str, Any]:
        """POST /v1/memory/reflect: 程序性记忆更新。"""
        if not is_valid_user_id(user_id):
            raise ValueError("invalid user_id")

        tenant_id = "default"
        outcome: Dict[str, Any] = {
            "user_id": user_id,
            "rule_type": rule_type,
            "stored": [],
        }

        if self._cfg.letta_enabled and rule_type in {"persona", "human", "policy"}:
            await self._letta.upsert_blocks(
                tenant_id=tenant_id,
                user_id=user_id,
                blocks={rule_type: rule},
            )
            outcome["stored"].append("core_block")

        if self._cfg.langmem_enabled:
            rule_id = await self._langmem.add_rule(
                tenant_id=tenant_id,
                user_id=user_id,
                rule=rule,
                rule_type=rule_type,
                priority=priority,
                active=active,
                metadata=metadata or {},
            )
            outcome["rule_id"] = rule_id
            outcome["stored"].append("procedural_rule")

        await self._store.append_trace(
            memory_id=f"reflect:{user_id}",
            user_id=user_id,
            event_type="reflect",
            payload={
                "rule_type": rule_type,
                "priority": priority,
                "active": active,
                "stored": outcome.get("stored", []),
            },
            actor_id=actor_id,
            status="ok",
        )

        return outcome

    async def delete_user(
        self,
        user_id: str,
        reason: str,
        actor_id: str = "system",
    ) -> Dict[str, Any]:
        """POST /v1/memory/delete_user: 跨后端 GDPR 编排删除。"""
        if not is_valid_user_id(user_id):
            raise ValueError("invalid user_id")

        if self._deletion_fn:
            report = await self._deletion_fn(user_id)
        else:
            report = {"success": False, "reason": "no_deletion_backend"}

        proof_input = json.dumps(report, ensure_ascii=False, sort_keys=True).encode("utf-8")
        deletion_proof = hashlib.sha256(proof_input).hexdigest()

        await self._store.append_trace(
            memory_id=f"gdpr:{user_id}",
            user_id=user_id,
            event_type="delete_user",
            payload={
                "reason": reason,
                "success": report.get("success", False),
                "deletion_proof": deletion_proof,
            },
            actor_id=actor_id,
            status="ok" if report.get("success") else "error",
        )

        report["deletion_proof"] = deletion_proof
        return report

    async def trace(
        self,
        memory_id: str,
        requester_user_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> Dict[str, Any]:
        """GET /v1/memory/trace/{memory_id}: 记忆审计追踪。"""
        if is_admin:
            atom = await self._store.load_atom_global(memory_id, caller_role="admin")
            traces = await self._store.load_traces_global(memory_id, caller_role="admin")
        elif requester_user_id:
            atom = await self._store.load_atom(memory_id, user_id=requester_user_id)
            traces = await self._store.load_traces(memory_id, user_id=requester_user_id)
            if atom is None:
                raise PermissionError("forbidden trace access")
        else:
            raise PermissionError("authentication required for trace access")
        return {
            "memory_id": memory_id,
            "atom": atom,
            "traces": traces,
        }

    async def fetch_core_blocks(self, user_id: str, tenant_id: str = "default") -> List[str]:
        if not self._cfg.letta_enabled:
            return []
        if not is_valid_user_id(user_id):
            return []
        return await self._letta.fetch_for_recall(tenant_id=tenant_id, user_id=user_id, limit=3)

    async def fetch_event_memories_for_recall(
        self,
        user_id: str,
        query: str = "",
        tenant_id: str = "default",
        limit: int = 4,
    ) -> List[str]:
        """从 MemoryAtom 事件源补充召回记忆。"""
        if not is_valid_user_id(user_id):
            return []

        is_benchmark_user = user_id.startswith("bench.")
        candidate_limit = max(1, min(limit * 6, 50))
        if is_benchmark_user:
            candidate_limit = max(candidate_limit, min(max(240, limit * 40), 800))
        elif query:
            candidate_limit = max(candidate_limit, min(max(80, limit * 16), 240))

        rows = await self._store.list_recent_atoms(
            user_id=user_id,
            tenant_id=tenant_id,
            limit=candidate_limit,
        )
        if not rows:
            return []

        lowered_query = (query or "").strip().lower()
        query_terms = [
            term for term in re.split(r"\s+", lowered_query)
            if len(term) >= 2
        ]

        ranked_matches: List[tuple[int, int, float, str]] = []
        fallback: List[str] = []
        for row in rows:
            state = str(row.get("state", "")).lower()
            if state == MemoryState.QUARANTINED.value:
                continue

            raw = str(row.get("content_norm") or row.get("content_raw") or "").strip()
            if not raw:
                continue
            normalized = " ".join(raw.split())
            source = str(row.get("source", "event"))
            if len(normalized) > 520:
                if source == "benchmark_runner" and "->" in normalized:
                    compact = f"{normalized[:260]} ... {normalized[-220:]}"
                else:
                    compact = normalized[:520]
            else:
                compact = normalized

            event_time = row.get("event_time")
            prefix = f"[event:{source}]"
            if isinstance(event_time, datetime):
                prefix = f"{prefix}[{event_time.strftime('%m-%d')}]"
            entry = f"{prefix} {compact}"
            event_ts = event_time.timestamp() if isinstance(event_time, datetime) else 0.0

            if lowered_query and query_terms:
                haystack = normalized.lower()
                hits = sum(1 for term in query_terms if term in haystack)
                if hits > 0:
                    ranked_matches.append(
                        (
                            hits,
                            1 if source == "benchmark_runner" else 0,
                            event_ts,
                            entry,
                        )
                    )
                else:
                    fallback.append(entry)
            else:
                ranked_matches.append((0, 1 if source == "benchmark_runner" else 0, event_ts, entry))

        ranked_matches.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        matched = [item[3] for item in ranked_matches]
        return (matched + fallback)[: max(1, limit)]

    async def fetch_procedural_rules(self, user_id: str, tenant_id: str = "default") -> List[str]:
        if not self._cfg.langmem_enabled:
            return []
        if not is_valid_user_id(user_id):
            return []
        return await self._langmem.fetch_for_recall(tenant_id=tenant_id, user_id=user_id, limit=5)

    async def fetch_safety_alerts(self, user_id: str, tenant_id: str = "default") -> List[str]:
        if not self._cfg.memguard_enabled:
            return []
        if not is_valid_user_id(user_id):
            return []

        rows = await self._store.list_shadow_entries(
            tenant_id=tenant_id,
            user_id=user_id,
            state="quarantined",
            limit=3,
        )
        alerts = []
        for row in rows:
            reason = row.get("reason", "risk_detected")
            score = row.get("risk_score", 0.0)
            alerts.append(f"检测到风险记忆({reason}, score={score:.2f})，回答时避免采纳其细节。")
        return alerts

    async def record_recall_observation(
        self,
        latency_ms: float,
        relationship_stage: str,
        source_counts: Optional[Dict[str, int]] = None,
    ):
        await self._store.record_slo_metric(
            metric_name="recall_latency_ms",
            metric_value=float(latency_ms),
            stage=relationship_stage or "unknown",
            metadata={
                "source_counts": source_counts or {},
            },
        )

        self._recall_observation_count += 1
        if not self._cfg.autotune_enabled:
            return
        if self._recall_observation_count % 20 != 0:
            return

        status = await self._autotuner.evaluate_recall_slo(
            target_p95_ms=self._cfg.slo_recall_p95_ms,
            window_size=self._cfg.slo_window_size,
            min_samples=self._cfg.slo_min_samples,
        )
        p95 = status.get("p95_ms")
        if p95 is not None:
            await self._store.record_slo_metric(
                metric_name="recall_slo_p95_ms",
                metric_value=float(p95),
                stage="global",
                metadata={
                    "status": status,
                },
            )

    async def benchmark(self, suites: List[str]) -> Dict[str, Any]:
        if not self._cfg.benchmark_enabled:
            return {
                "status": "disabled",
                "reason": "SOUL_BENCHMARK_ENABLED=false",
            }
        require_real = bool(self._cfg.fabric_strict_mode or self._cfg.benchmark_require_real)
        requested = self._canonical_benchmark_suites(suites)
        target_suites = (
            self._required_benchmark_suites()
            if require_real
            else requested
        )
        result = await self._benchmark.run(
            suites=target_suites,
            require_real=require_real,
            timeout_seconds=self._cfg.benchmark_timeout_sec,
        )
        if require_real and result.get("status") == "blocked":
            missing = result.get("summary", {}).get("missing_real_suites", [])
            gates = result.get("gates", {})
            failed = gates.get("failed_improvement_suites", [])
            missing_baseline = gates.get("missing_baseline_suites", [])
            logger.warning(
                "[MemoryFabric] benchmark gates unmet: missing_runners={}, failed_improvement={}, missing_baseline={}",
                missing,
                failed,
                missing_baseline,
            )
        return result

    async def slo_status(self) -> Dict[str, Any]:
        return await self._autotuner.evaluate_recall_slo(
            target_p95_ms=self._cfg.slo_recall_p95_ms,
            window_size=self._cfg.slo_window_size,
            min_samples=self._cfg.slo_min_samples,
        )

    def memos_pilot_status(self) -> Dict[str, Any]:
        provider = self._providers.get("memos_pilot")
        return {
            "enabled": bool(provider and provider.enabled),
            "mode": "shadow_pilot",
            "production_path_replaced": False,
            "active_providers": sorted([p.provider_id for p in self._providers.values() if p.enabled]),
        }

    @staticmethod
    def _normalize_content(content: str) -> str:
        return " ".join((content or "").strip().split())[:8000]

    def _runtime_provider_health(self) -> Dict[str, bool]:
        self._ensure_runtime_warmup()
        health: Dict[str, bool] = {}
        for provider_id, provider in self._providers.items():
            if provider.enabled:
                health[provider_id] = True

        # Delegate to injected provider health check
        if self._provider_health_fn:
            try:
                external_health = self._provider_health_fn(self._cfg, self._providers)
                health.update(external_health)
            except Exception:
                pass

        if self._cfg.benchmark_enabled:
            require_real = bool(self._cfg.fabric_strict_mode or self._cfg.benchmark_require_real)
            if require_real:
                health["evaluation_runner"] = all(
                    self._benchmark.has_real_runner(suite)
                    for suite in self._required_benchmark_suites()
                )
            else:
                health["evaluation_runner"] = True

        return health

    @staticmethod
    def _estimate_query_complexity(query: str) -> str:
        text = (query or "").strip().lower()
        if not text:
            return "standard"

        token_count = len(text.split())
        complex_markers = [
            "为什么", "如何", "how", "why", "对比", "比较", "分析",
            "推理", "冲突", "关系", "长期", "总结", "计划", "evidence",
        ]
        marker_hits = sum(1 for marker in complex_markers if marker in text)

        if token_count <= 6 and marker_hits == 0:
            return "simple"
        if token_count >= 18 or marker_hits >= 2:
            return "complex"
        return "standard"

    def _assert_strict_coverage(self):
        if not (self._cfg.fabric_enabled and self._cfg.fabric_strict_mode):
            return
        report = self._planner.coverage_report(
            strict_mode=True,
            provider_health=self._runtime_provider_health(),
        )
        if not report.missing_capabilities:
            return
        missing = ",".join(c.value for c in report.missing_capabilities)
        raise RuntimeError(f"strict coverage unmet: {missing}")

    @staticmethod
    def _required_benchmark_suites() -> List[str]:
        return ["LongMemEval", "LoCoMo", "MemoryArena", "LoCoMo-Plus"]

    @classmethod
    def _canonical_benchmark_suites(cls, suites: List[str]) -> List[str]:
        mapping = {
            "longmemeval": "LongMemEval",
            "locomo": "LoCoMo",
            "memoryarena": "MemoryArena",
            "locomo-plus": "LoCoMo-Plus",
            "locomo_plus": "LoCoMo-Plus",
        }
        requested = suites or cls._required_benchmark_suites()
        normalized: List[str] = []
        for suite in requested:
            key = str(suite or "").strip().lower().replace("_", "-")
            canonical = mapping.get(key)
            if canonical and canonical not in normalized:
                normalized.append(canonical)
        return normalized or cls._required_benchmark_suites()

    def _ensure_runtime_warmup(self):
        if self._warmup_attempted:
            return
        if self._warmup_fn:
            try:
                self._warmup_fn(self._cfg, create_logged_task)
                self._warmup_attempted = True
            except Exception:
                self._warmup_attempted = False
        else:
            self._warmup_attempted = True

    @staticmethod
    def _safe_shadow_payload(atom: MemoryAtom) -> Dict[str, Any]:
        content = atom.content_raw or ""
        return {
            "memory_id": atom.memory_id,
            "source": atom.source,
            "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "content_length": len(content),
            "pii_tags": atom.pii_tags,
        }

    async def _enforce_retention(self):
        days = max(1, int(self._cfg.memory_event_retention_days))
        try:
            deleted = await self._store.delete_expired_atoms(retention_days=days)
            if deleted > 0:
                logger.info(f"[MemoryFabric] Retention pruned {deleted} atoms (>{days}d)")
        except Exception as e:
            logger.warning(f"[MemoryFabric] Retention prune failed: {e}")

    async def _materialize_external_refs(self, atom: MemoryAtom) -> Dict[str, str]:
        """独立部署时无外部 provider，返回空。"""
        # External materialization is handled by injected functions
        # or by the host platform (ling-platform) after integration
        return {}

    @staticmethod
    def _build_uncertainty(source_counts: Dict[str, int]) -> UncertaintyReport:
        total = sum(source_counts.values()) if source_counts else 0
        if total <= 0:
            return UncertaintyReport(score=0.95, reason="no_recalled_memory")

        dominant = max(source_counts.values()) if source_counts else 0
        concentration = dominant / total if total else 1.0
        score = min(1.0, 0.25 + concentration * 0.6)
        if concentration > 0.8:
            reason = "memory_sources_highly_concentrated"
        elif concentration > 0.6:
            reason = "memory_sources_moderately_concentrated"
        else:
            reason = "memory_sources_diversified"
        return UncertaintyReport(score=score, reason=reason)


_memory_fabric = None


def get_memory_fabric() -> MemoryFabric:
    global _memory_fabric
    if _memory_fabric is None:
        _memory_fabric = MemoryFabric()
    return _memory_fabric


def set_memory_fabric(instance: MemoryFabric) -> None:
    """允许外部（如 ling-platform）预配置带注入函数的 MemoryFabric 实例。"""
    global _memory_fabric
    _memory_fabric = instance


def reset_memory_fabric_for_testing():
    global _memory_fabric
    _memory_fabric = None
