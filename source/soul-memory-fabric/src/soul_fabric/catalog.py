"""Memory Fabric provider 目录。"""

from typing import Dict

from .models import CapabilityProvider, MemoryCapability


def build_provider_catalog(cfg) -> Dict[str, CapabilityProvider]:
    """基于当前配置构建能力提供方目录。"""
    providers: Dict[str, CapabilityProvider] = {
        "mongodb_internal": CapabilityProvider(
            provider_id="mongodb_internal",
            display_name="MongoDB Soul Internal",
            enabled=cfg.enabled,
            capabilities={
                MemoryCapability.RELATIONSHIP,
                MemoryCapability.AFFECTIVE,
                MemoryCapability.ABSTRACTION,
                MemoryCapability.GOVERNANCE,
            },
            tags={"internal", "primary"},
        ),
        "qdrant": CapabilityProvider(
            provider_id="qdrant",
            display_name="Qdrant Episodic/Semantic",
            enabled=cfg.enabled,
            capabilities={MemoryCapability.SEMANTIC, MemoryCapability.EPISODIC},
            tags={"vector", "fast"},
        ),
        "evermemos": CapabilityProvider(
            provider_id="evermemos",
            display_name="EverMemOS Episodic",
            enabled=cfg.enabled,
            capabilities={MemoryCapability.EPISODIC},
            tags={"episodic", "long_term"},
        ),
        "graphiti": CapabilityProvider(
            provider_id="graphiti",
            display_name="Graphiti Temporal Graph",
            enabled=cfg.enabled and cfg.graphiti_enabled,
            capabilities={MemoryCapability.TEMPORAL_GRAPH},
            tags={"graph", "temporal"},
        ),
        "mem0": CapabilityProvider(
            provider_id="mem0",
            display_name="Mem0 Entity Memory",
            enabled=cfg.enabled and cfg.mem0_enabled,
            capabilities={MemoryCapability.ENTITY, MemoryCapability.SEMANTIC},
            tags={"entity", "semantic"},
        ),
        "collective": CapabilityProvider(
            provider_id="collective",
            display_name="Collective Wisdom Retriever",
            enabled=cfg.enabled,
            capabilities={MemoryCapability.COLLECTIVE},
            tags={"wisdom", "derived"},
        ),
        "letta_core_blocks": CapabilityProvider(
            provider_id="letta_core_blocks",
            display_name="Letta Core Memory Blocks",
            enabled=cfg.enabled and cfg.letta_enabled,
            capabilities={MemoryCapability.CORE_BLOCKS, MemoryCapability.GOVERNANCE},
            tags={"identity", "core"},
        ),
        "langmem": CapabilityProvider(
            provider_id="langmem",
            display_name="LangMem Procedural Manager",
            enabled=cfg.enabled and cfg.langmem_enabled,
            capabilities={MemoryCapability.PROCEDURAL, MemoryCapability.GOVERNANCE},
            tags={"manager", "procedural"},
        ),
        "safety_memory": CapabilityProvider(
            provider_id="safety_memory",
            display_name="Safety Shadow Memory",
            enabled=cfg.enabled and cfg.memguard_enabled,
            capabilities={MemoryCapability.SAFETY_MEMORY},
            tags={"security", "safety"},
        ),
        "evaluation_runner": CapabilityProvider(
            provider_id="evaluation_runner",
            display_name="Memory Benchmark Runner",
            enabled=cfg.enabled and cfg.benchmark_enabled,
            capabilities={MemoryCapability.EVALUATION},
            tags={"benchmark", "evaluation"},
        ),
        "memos_pilot": CapabilityProvider(
            provider_id="memos_pilot",
            display_name="MemOS Pilot Orchestrator",
            enabled=cfg.enabled and cfg.memos_pilot_enabled,
            capabilities={MemoryCapability.GOVERNANCE, MemoryCapability.EVALUATION},
            tags={"pilot", "orchestrator"},
        ),
    }
    return providers
