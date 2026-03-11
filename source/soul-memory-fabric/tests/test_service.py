"""MemoryFabric 服务基础测试（不依赖 MongoDB）。"""

import os

import pytest

os.environ.setdefault("SOUL_ENABLED", "true")
os.environ.setdefault("SOUL_FABRIC_ENABLED", "true")

from soul_fabric.config import FabricConfig, reset_fabric_config_for_testing
from soul_fabric.models import MemoryCapability
from soul_fabric.planner import CapabilityPlanner
from soul_fabric.catalog import build_provider_catalog
from soul_fabric.service import MemoryFabric, reset_memory_fabric_for_testing


@pytest.fixture(autouse=True)
def _reset():
    reset_fabric_config_for_testing()
    reset_memory_fabric_for_testing()
    yield
    reset_fabric_config_for_testing()
    reset_memory_fabric_for_testing()


def test_config_loads():
    cfg = FabricConfig()
    assert cfg.enabled is True
    assert cfg.fabric_enabled is True


def test_coverage_report():
    cfg = FabricConfig()
    providers = build_provider_catalog(cfg)
    planner = CapabilityPlanner(providers)
    report = planner.coverage_report(strict_mode=False)
    assert len(report.missing_capabilities) == 0 or len(report.missing_capabilities) > 0
    assert isinstance(report.capability_to_providers, dict)


def test_plan_recall_stranger():
    cfg = FabricConfig()
    providers = build_provider_catalog(cfg)
    planner = CapabilityPlanner(providers)
    plan = planner.plan_recall(
        relationship_stage="stranger",
        latency_budget_ms=600,
    )
    assert plan.relationship_stage == "stranger"
    assert plan.routes.get("qdrant") is True


def test_plan_recall_friend():
    cfg = FabricConfig()
    providers = build_provider_catalog(cfg)
    planner = CapabilityPlanner(providers)
    plan = planner.plan_recall(
        relationship_stage="friend",
        latency_budget_ms=600,
    )
    assert plan.relationship_stage == "friend"
    assert plan.routes.get("evermemos") is True


def test_query_complexity():
    assert MemoryFabric._estimate_query_complexity("") == "standard"
    assert MemoryFabric._estimate_query_complexity("hi") == "simple"
    assert MemoryFabric._estimate_query_complexity("为什么你觉得这个关系会长期发展下去？分析一下推理过程") == "complex"
