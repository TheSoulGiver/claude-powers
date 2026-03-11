"""Store 模块测试（查询守卫 + 导入测试，不需要真实 MongoDB）。"""

import pytest

from soul_fabric.store import (
    MEMORY_ATOMS,
    MEMORY_TRACES,
    CORE_BLOCKS,
    PROCEDURAL_RULES,
    SAFETY_SHADOW,
    BENCHMARK_RUNS,
    SLO_METRICS,
    MemoryFabricStore,
)


def test_collection_constants():
    assert MEMORY_ATOMS == "soul_memory_atoms"
    assert MEMORY_TRACES == "soul_memory_traces"
    assert CORE_BLOCKS == "soul_core_blocks"
    assert PROCEDURAL_RULES == "soul_procedural_rules"
    assert SAFETY_SHADOW == "soul_safety_shadow"
    assert BENCHMARK_RUNS == "soul_benchmark_runs"
    assert SLO_METRICS == "soul_slo_metrics"


def test_store_instantiation():
    store = MemoryFabricStore()
    assert store is not None


# -------------------------------------------------------------------
# _scoped_query guard tests
# -------------------------------------------------------------------

def test_scoped_query_valid():
    q = MemoryFabricStore._scoped_query("alice")
    assert q == {"user_id": "alice"}


def test_scoped_query_with_extra():
    q = MemoryFabricStore._scoped_query("bob", {"tenant_id": "default"})
    assert q == {"user_id": "bob", "tenant_id": "default"}


def test_scoped_query_empty_user_id_raises():
    with pytest.raises(ValueError, match="user_id is required"):
        MemoryFabricStore._scoped_query("")


def test_scoped_query_none_user_id_raises():
    with pytest.raises(ValueError, match="user_id is required"):
        MemoryFabricStore._scoped_query(None)


def test_scoped_query_whitespace_user_id_raises():
    with pytest.raises(ValueError, match="user_id is required"):
        MemoryFabricStore._scoped_query("   ")


# -------------------------------------------------------------------
# _global_query guard tests
# -------------------------------------------------------------------

def test_global_query_system():
    q = MemoryFabricStore._global_query("system", {"state": "raw"})
    assert q == {"state": "raw"}


def test_global_query_admin():
    q = MemoryFabricStore._global_query("admin")
    assert q == {}


def test_global_query_user_raises():
    with pytest.raises(PermissionError, match="global queries require system/admin"):
        MemoryFabricStore._global_query("user")


def test_global_query_agent_raises():
    with pytest.raises(PermissionError, match="global queries require system/admin"):
        MemoryFabricStore._global_query("agent:ling-finder")
