"""Soul Fabric 配置 — 环境变量驱动的单例。"""

import os

from loguru import logger

_fabric_config = None


class FabricConfig:
    """Memory Fabric 独立配置（从 SoulConfig 提取 fabric 相关字段）。"""

    def __init__(self):
        # 总开关
        self.enabled = os.environ.get("SOUL_ENABLED", "false").lower() in ("true", "1", "yes")
        self.fabric_enabled = os.environ.get("SOUL_FABRIC_ENABLED", "true").lower() in ("true", "1", "yes")
        self.fabric_strict_mode = os.environ.get("SOUL_FABRIC_STRICT_MODE", "false").lower() in ("true", "1", "yes")

        # MongoDB
        self.mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        self.mongo_database = os.environ.get("MONGO_DB", "ling_soul")

        # 记忆保留
        self.memory_event_retention_days = int(os.environ.get("SOUL_MEMORY_EVENT_RETENTION_DAYS", "3650"))

        # Phase 1: 能力层插件 (Letta / LangMem)
        self.letta_enabled = os.environ.get("SOUL_LETTA_ENABLED", "true").lower() in ("true", "1", "yes")
        self.langmem_enabled = os.environ.get("SOUL_LANGMEM_ENABLED", "true").lower() in ("true", "1", "yes")
        self.letta_mode = os.environ.get("SOUL_LETTA_MODE", "local").lower()
        self.letta_url = os.environ.get("SOUL_LETTA_URL", "").strip()
        self.letta_api_key = os.environ.get("SOUL_LETTA_API_KEY", "").strip()
        self.letta_timeout_sec = float(os.environ.get("SOUL_LETTA_TIMEOUT_SEC", "3"))
        self.langmem_mode = os.environ.get("SOUL_LANGMEM_MODE", "local").lower()
        self.langmem_url = os.environ.get("SOUL_LANGMEM_URL", "").strip()
        self.langmem_api_key = os.environ.get("SOUL_LANGMEM_API_KEY", "").strip()
        self.langmem_timeout_sec = float(os.environ.get("SOUL_LANGMEM_TIMEOUT_SEC", "3"))

        # Phase 2: 记忆演化与安全
        self.amem_enabled = os.environ.get("SOUL_AMEM_ENABLED", "true").lower() in ("true", "1", "yes")
        self.memguard_enabled = os.environ.get("SOUL_MEMGUARD_ENABLED", "true").lower() in ("true", "1", "yes")
        self.memguard_quarantine_threshold = float(
            os.environ.get("SOUL_MEMGUARD_QUARANTINE_THRESHOLD", "0.75")
        )

        # Phase 3: 评测与 SLO
        self.benchmark_enabled = os.environ.get("SOUL_BENCHMARK_ENABLED", "true").lower() in ("true", "1", "yes")
        self.autotune_enabled = os.environ.get("SOUL_AUTOTUNE_ENABLED", "true").lower() in ("true", "1", "yes")
        self.slo_recall_p95_ms = int(os.environ.get("SOUL_SLO_RECALL_P95_MS", "450"))
        self.slo_window_size = int(os.environ.get("SOUL_SLO_WINDOW_SIZE", "200"))
        self.slo_min_samples = int(os.environ.get("SOUL_SLO_MIN_SAMPLES", "30"))
        self.benchmark_require_real = os.environ.get("SOUL_BENCHMARK_REQUIRE_REAL", "false").lower() in ("true", "1", "yes")
        self.benchmark_timeout_sec = float(os.environ.get("SOUL_BENCHMARK_TIMEOUT_SEC", "1800"))
        self.benchmark_cmd_longmemeval = os.environ.get("SOUL_BENCHMARK_CMD_LONGMEMEVAL", "").strip()
        self.benchmark_cmd_locomo = os.environ.get("SOUL_BENCHMARK_CMD_LOCOMO", "").strip()
        self.benchmark_cmd_memoryarena = os.environ.get("SOUL_BENCHMARK_CMD_MEMORYARENA", "").strip()
        self.benchmark_cmd_locomo_plus = os.environ.get("SOUL_BENCHMARK_CMD_LOCOMO_PLUS", "").strip()
        self.benchmark_min_improvement = float(os.environ.get("SOUL_BENCHMARK_MIN_IMPROVEMENT", "0.15"))
        self.benchmark_baseline_longmemeval = float(os.environ.get("SOUL_BENCHMARK_BASELINE_LONGMEMEVAL", "0"))
        self.benchmark_baseline_locomo = float(os.environ.get("SOUL_BENCHMARK_BASELINE_LOCOMO", "0"))
        self.benchmark_baseline_memoryarena = float(os.environ.get("SOUL_BENCHMARK_BASELINE_MEMORYARENA", "0"))
        self.benchmark_baseline_locomo_plus = float(os.environ.get("SOUL_BENCHMARK_BASELINE_LOCOMO_PLUS", "0"))

        # 外部 provider 开关（用于 catalog 构建）
        self.graphiti_enabled = os.environ.get("GRAPHITI_ENABLED", "false").lower() in ("true", "1", "yes")
        self.mem0_enabled = os.environ.get("MEM0_ENABLED", "false").lower() in ("true", "1", "yes")
        self.memos_pilot_enabled = os.environ.get("SOUL_MEMOS_PILOT_ENABLED", "false").lower() in ("true", "1", "yes")

        # Port registry（独立部署时通常关闭）
        self.enable_port_registry = os.environ.get("SOUL_PORT_REGISTRY", "false").lower() in ("true", "1", "yes")

        # 记忆衰减参数
        self.decay_flashbulb_intensity = float(os.environ.get("SOUL_FLASHBULB_INTENSITY", "0.8"))

        if self.enabled and self.fabric_enabled:
            logger.info(
                f"[SoulFabric] Memory Fabric 已启用 "
                f"(MongoDB: {self.mongo_url}/{self.mongo_database})"
            )


def get_fabric_config() -> FabricConfig:
    """获取 FabricConfig 单例。"""
    global _fabric_config
    if _fabric_config is None:
        _fabric_config = FabricConfig()
    return _fabric_config


def reset_fabric_config_for_testing():
    """测试辅助: 重置配置单例。"""
    global _fabric_config
    _fabric_config = None
