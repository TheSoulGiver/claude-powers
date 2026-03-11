"""Memory Fabric 核心模型。"""

from enum import Enum
from typing import Dict, List, Set

from pydantic import BaseModel, Field


class MemoryCapability(str, Enum):
    """能力层分类（用于覆盖率与路由规划）。"""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    ENTITY = "entity"
    TEMPORAL_GRAPH = "temporal_graph"
    RELATIONSHIP = "relationship"
    AFFECTIVE = "affective"
    ABSTRACTION = "abstraction"
    COLLECTIVE = "collective"
    CORE_BLOCKS = "core_blocks"
    PROCEDURAL = "procedural"
    SAFETY_MEMORY = "safety_memory"
    GOVERNANCE = "governance"
    EVALUATION = "evaluation"


class CapabilityProvider(BaseModel):
    """单个能力提供方（后端或算法模块）。"""

    provider_id: str
    display_name: str
    enabled: bool = True
    capabilities: Set[MemoryCapability] = Field(default_factory=set)
    tags: Set[str] = Field(default_factory=set)


class RecallRoutePlan(BaseModel):
    """召回路由计划。"""

    relationship_stage: str = "stranger"
    query_complexity: str = "standard"
    budget_tier: str = "balanced"
    latency_budget_ms: int = 600
    routes: Dict[str, bool] = Field(default_factory=dict)
    selected_providers: List[str] = Field(default_factory=list)
    covered_capabilities: List[MemoryCapability] = Field(default_factory=list)


class CoverageReport(BaseModel):
    """能力覆盖报告。"""

    capability_to_providers: Dict[MemoryCapability, List[str]] = Field(default_factory=dict)
    provider_runtime_health: Dict[str, bool] = Field(default_factory=dict)
    unhealthy_enabled_providers: List[str] = Field(default_factory=list)
    required_capabilities: List[MemoryCapability] = Field(default_factory=list)
    missing_capabilities: List[MemoryCapability] = Field(default_factory=list)
    missing_optional_capabilities: List[MemoryCapability] = Field(default_factory=list)
    strict_mode: bool = False
