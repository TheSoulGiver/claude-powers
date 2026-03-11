"""Memory Fabric 能力规划器。"""

from typing import Dict, List, Optional, Set

from .models import CapabilityProvider, CoverageReport, MemoryCapability, RecallRoutePlan


_BASE_REQUIRED_CAPABILITIES = {
    MemoryCapability.EPISODIC,
    MemoryCapability.SEMANTIC,
    MemoryCapability.RELATIONSHIP,
    MemoryCapability.AFFECTIVE,
    MemoryCapability.GOVERNANCE,
}
_STRICT_REQUIRED_CAPABILITIES = set(MemoryCapability)

_ROUTE_COST_MS = {
    "core_blocks": 20,
    "procedural": 20,
    "safety_shadow": 15,
    "evermemos": 70,
    "stories": 40,
    "resonance": 60,
    "abstract": 60,
    "collective": 80,
    "graphiti": 75,
    "mem0": 75,
    "graph": 60,
}

_CORE_COST_MS = 170
_DEFAULT_QUERY_COMPLEXITY = "standard"
_ALL_QUERY_COMPLEXITIES = {"simple", "standard", "complex"}

_ROUTE_ORDER = {
    "simple": [
        "core_blocks",
        "procedural",
        "safety_shadow",
        "evermemos",
        "stories",
        "resonance",
    ],
    "standard": [
        "core_blocks",
        "procedural",
        "safety_shadow",
        "evermemos",
        "resonance",
        "stories",
        "abstract",
        "collective",
        "mem0",
        "graphiti",
        "graph",
    ],
    "complex": [
        "core_blocks",
        "procedural",
        "safety_shadow",
        "graphiti",
        "mem0",
        "evermemos",
        "abstract",
        "resonance",
        "stories",
        "collective",
        "graph",
    ],
}


class CapabilityPlanner:
    """按能力覆盖生成召回路由计划。"""

    def __init__(self, providers: Dict[str, CapabilityProvider]):
        self._providers = providers

    def coverage_report(
        self,
        strict_mode: bool = False,
        provider_health: Optional[Dict[str, bool]] = None,
    ) -> CoverageReport:
        provider_health = provider_health or {}
        capability_map: Dict[MemoryCapability, List[str]] = {
            cap: [] for cap in MemoryCapability
        }
        for provider in self._providers.values():
            if not self._is_available(provider.provider_id, provider_health):
                continue
            for capability in provider.capabilities:
                capability_map[capability].append(provider.provider_id)

        required = _STRICT_REQUIRED_CAPABILITIES if strict_mode else _BASE_REQUIRED_CAPABILITIES
        missing_required = [
            cap for cap in required
            if not capability_map.get(cap)
        ]
        missing_optional = [
            cap for cap in MemoryCapability
            if cap not in required and not capability_map.get(cap)
        ]
        unhealthy = sorted([
            provider.provider_id
            for provider in self._providers.values()
            if provider.enabled and provider_health.get(provider.provider_id) is False
        ])
        return CoverageReport(
            capability_to_providers=capability_map,
            provider_runtime_health=provider_health,
            unhealthy_enabled_providers=unhealthy,
            required_capabilities=sorted(required, key=lambda x: x.value),
            missing_capabilities=sorted(missing_required, key=lambda x: x.value),
            missing_optional_capabilities=sorted(missing_optional, key=lambda x: x.value),
            strict_mode=strict_mode,
        )

    def plan_recall(
        self,
        relationship_stage: str,
        latency_budget_ms: int,
        query_complexity: str = _DEFAULT_QUERY_COMPLEXITY,
        provider_health: Optional[Dict[str, bool]] = None,
    ) -> RecallRoutePlan:
        provider_health = provider_health or {}
        stage = relationship_stage or "stranger"
        complexity = self._normalize_query_complexity(query_complexity)
        budget = max(220, int(latency_budget_ms))

        routes: Dict[str, bool] = {
            "qdrant": True,
            "profile": True,
            "foresight": True,
            "relationship": True,
            "core_blocks": False,
            "procedural": False,
            "safety_shadow": False,
            "evermemos": False,
            "stories": False,
            "resonance": False,
            "abstract": False,
            "collective": False,
            "graphiti": False,
            "mem0": False,
            "graph": False,
        }

        if stage == "stranger":
            selected = self._collect_selected_providers(routes)
            covered_caps = self._collect_covered_capabilities(routes, selected)
            return RecallRoutePlan(
                relationship_stage=stage,
                query_complexity=complexity,
                budget_tier=self._budget_tier(budget),
                latency_budget_ms=budget,
                routes=routes,
                selected_providers=selected,
                covered_capabilities=sorted(covered_caps, key=lambda x: x.value),
            )

        graphiti_available = self._is_available("graphiti", provider_health)
        eligible = {
            "core_blocks": self._is_available("letta_core_blocks", provider_health),
            "procedural": self._is_available("langmem", provider_health),
            "safety_shadow": self._is_available("safety_memory", provider_health),
            "evermemos": True,
            "stories": True,
            "resonance": True,
            "abstract": True,
            "collective": self._is_available("collective", provider_health),
            "graphiti": graphiti_available,
            "mem0": self._is_available("mem0", provider_health),
            "graph": not graphiti_available,
        }

        remaining = budget - _CORE_COST_MS
        route_order = _ROUTE_ORDER[complexity]
        for route_name in route_order:
            if remaining <= 0:
                break
            if not eligible.get(route_name):
                continue
            route_cost = _ROUTE_COST_MS.get(route_name, 50)
            if remaining < route_cost:
                continue
            routes[route_name] = True
            remaining -= route_cost

        selected = self._collect_selected_providers(routes)
        covered_caps = self._collect_covered_capabilities(routes, selected)

        return RecallRoutePlan(
            relationship_stage=stage,
            query_complexity=complexity,
            budget_tier=self._budget_tier(budget),
            latency_budget_ms=budget,
            routes=routes,
            selected_providers=selected,
            covered_capabilities=sorted(covered_caps, key=lambda x: x.value),
        )

    def _is_available(self, provider_id: str, provider_health: Dict[str, bool]) -> bool:
        provider = self._providers.get(provider_id)
        if not provider or not provider.enabled:
            return False
        health = provider_health.get(provider_id)
        if health is None:
            return True
        return bool(health)

    @staticmethod
    def _normalize_query_complexity(query_complexity: str) -> str:
        val = (query_complexity or _DEFAULT_QUERY_COMPLEXITY).strip().lower()
        if val not in _ALL_QUERY_COMPLEXITIES:
            return _DEFAULT_QUERY_COMPLEXITY
        return val

    @staticmethod
    def _budget_tier(latency_budget_ms: int) -> str:
        if latency_budget_ms <= 350:
            return "tight"
        if latency_budget_ms <= 650:
            return "balanced"
        return "expanded"

    def _collect_covered_capabilities(
        self,
        routes: Dict[str, bool],
        selected_providers: List[str],
    ) -> Set[MemoryCapability]:
        covered_caps: Set[MemoryCapability] = set()
        for pid in selected_providers:
            provider = self._providers.get(pid)
            if provider:
                covered_caps.update(provider.capabilities)
        if routes.get("relationship"):
            covered_caps.add(MemoryCapability.RELATIONSHIP)
        if routes.get("profile") or routes.get("abstract"):
            covered_caps.add(MemoryCapability.ABSTRACTION)
        if routes.get("foresight"):
            covered_caps.add(MemoryCapability.EPISODIC)
        if routes.get("resonance"):
            covered_caps.add(MemoryCapability.AFFECTIVE)
        if routes.get("core_blocks"):
            covered_caps.add(MemoryCapability.CORE_BLOCKS)
        if routes.get("procedural"):
            covered_caps.add(MemoryCapability.PROCEDURAL)
        if routes.get("safety_shadow"):
            covered_caps.add(MemoryCapability.SAFETY_MEMORY)
        return covered_caps

    @staticmethod
    def _collect_selected_providers(routes: Dict[str, bool]) -> List[str]:
        providers = []
        if routes.get("qdrant"):
            providers.append("qdrant")
        if routes.get("evermemos"):
            providers.append("evermemos")
        if routes.get("graphiti"):
            providers.append("graphiti")
        if routes.get("mem0"):
            providers.append("mem0")
        if routes.get("collective"):
            providers.append("collective")
        if routes.get("core_blocks"):
            providers.append("letta_core_blocks")
        if routes.get("procedural"):
            providers.append("langmem")
        if routes.get("safety_shadow"):
            providers.append("safety_memory")
        providers.append("mongodb_internal")
        return providers
