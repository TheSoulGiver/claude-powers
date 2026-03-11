"""Phase 3: SLO 监控与自动调参建议。"""

from __future__ import annotations

from typing import Any, Dict, List

from .store import MemoryFabricStore


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(round((len(sorted_vals) - 1) * p))
    idx = max(0, min(idx, len(sorted_vals) - 1))
    return float(sorted_vals[idx])


class SLOAutoTuner:
    """读取实时指标并给出配置建议。"""

    def __init__(self, store: MemoryFabricStore):
        self._store = store

    async def evaluate_recall_slo(
        self,
        target_p95_ms: int,
        window_size: int,
        min_samples: int,
    ) -> Dict[str, Any]:
        rows = await self._store.recent_slo_metrics(
            metric_name="recall_latency_ms",
            limit=max(window_size, min_samples),
        )
        samples = [float(r.get("metric_value", 0.0)) for r in rows if r.get("metric_value") is not None]
        sample_count = len(samples)
        if sample_count < min_samples:
            return {
                "status": "insufficient_samples",
                "sample_count": sample_count,
                "target_p95_ms": target_p95_ms,
                "recommendations": [
                    "collect_more_data",
                ],
            }

        p95 = _percentile(samples, 0.95)
        p50 = _percentile(samples, 0.50)
        status = "ok" if p95 <= target_p95_ms else "breach"

        recommendations: List[str] = []
        if p95 > target_p95_ms:
            recommendations.extend([
                "prefer_core_routes_for_stranger",
                "reduce_heavy_routes_when_graphiti_unstable",
                "increase_recall_timeout_ms_extended_by_10_percent_if_quality_drops",
            ])
        elif p95 < target_p95_ms * 0.55:
            recommendations.append("consider_tightening_timeout_for_cost_efficiency")

        if p50 > target_p95_ms * 0.8:
            recommendations.append("profile_mongo_and_adapter_pool_sizes")

        return {
            "status": status,
            "sample_count": sample_count,
            "p50_ms": round(p50, 3),
            "p95_ms": round(p95, 3),
            "target_p95_ms": target_p95_ms,
            "recommendations": recommendations,
        }
