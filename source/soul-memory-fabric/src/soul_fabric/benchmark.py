"""Phase 3: 记忆评测运行器（LongMemEval/LoCoMo/MemoryArena/LoCoMo-Plus）。"""

from __future__ import annotations

import asyncio
import json
import re
import shlex
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from .config import get_fabric_config
from .store import MEMORY_ATOMS, SAFETY_SHADOW, MemoryFabricStore, get_collection


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(round((len(sorted_vals) - 1) * p))
    idx = max(0, min(idx, len(sorted_vals) - 1))
    return float(sorted_vals[idx])


def _normalize_score(raw: float) -> float:
    score = float(raw)
    if score > 1.0 and score <= 100.0:
        score = score / 100.0
    return max(0.0, min(1.0, score))


class MemoryBenchmarkRunner:
    """可扩展基准执行器：优先真实套件命令，缺省才降级代理评分。"""

    def __init__(self, store: MemoryFabricStore):
        self._store = store
        self._cfg = get_fabric_config()

    def has_real_runner(self, suite: str) -> bool:
        return bool(self._suite_command(suite))

    def has_any_real_runner(self, suites: Optional[List[str]] = None) -> bool:
        targets = suites or ["LongMemEval", "LoCoMo", "MemoryArena", "LoCoMo-Plus"]
        return any(self.has_real_runner(suite) for suite in targets)

    async def run(
        self,
        suites: List[str],
        require_real: bool,
        timeout_seconds: float,
    ) -> Dict[str, Any]:
        suites = [self._canonical_suite_name(s) for s in (suites or ["LongMemEval", "LoCoMo", "MemoryArena", "LoCoMo-Plus"])]
        now = datetime.now(timezone.utc).isoformat()

        atoms_coll = await get_collection(MEMORY_ATOMS)
        shadow_coll = await get_collection(SAFETY_SHADOW)
        total_atoms = await atoms_coll.count_documents({}) if atoms_coll is not None else 0
        quarantined = (
            await shadow_coll.count_documents({"state": "quarantined"})
            if shadow_coll is not None
            else 0
        )
        quarantine_ratio = (quarantined / total_atoms) if total_atoms > 0 else 0.0

        slo_rows = await self._store.recent_slo_metrics("recall_latency_ms", limit=400)
        latencies = [float(row.get("metric_value", 0.0)) for row in slo_rows if row.get("metric_value") is not None]
        historical_recall_p95 = _percentile(latencies, 0.95)

        proxy_factors = self._proxy_factors(total_atoms, quarantine_ratio, historical_recall_p95)

        suite_results: Dict[str, Any] = {}
        real_count = 0
        proxy_count = 0
        missing_real = []
        failed_improvement = []
        missing_baseline = []
        min_improvement = max(0.0, float(self._cfg.benchmark_min_improvement))
        real_suite_p95_values: List[float] = []
        real_latency_samples: List[float] = []

        for suite in suites:
            real_result = await self._run_real_suite(suite, timeout_seconds=timeout_seconds)
            if real_result is not None:
                real_count += 1
                entry = real_result
            elif require_real:
                missing_real.append(suite)
                entry = {
                    "score": 0.0,
                    "status": "missing_runner",
                    "mode": "none",
                    "details": {
                        "reason": "benchmark command not configured",
                        "expected_env": self._suite_env_name(suite),
                    },
                }
            else:
                proxy_count += 1
                entry = self._proxy_suite_result(suite, proxy_factors)

            baseline = self._suite_baseline(suite)
            score = float(entry.get("score", 0.0))
            delta = (score - baseline) if baseline is not None else None
            if baseline is None and require_real:
                missing_baseline.append(suite)
            if (
                baseline is not None
                and entry.get("mode") == "real"
                and entry.get("status") == "ok"
                and delta is not None
                and delta < min_improvement
            ):
                failed_improvement.append(
                    {
                        "suite": suite,
                        "score": round(score, 6),
                        "baseline": round(float(baseline), 6),
                        "delta": round(float(delta), 6),
                    }
                )

            if baseline is not None:
                entry.setdefault("details", {})
                entry["details"]["baseline"] = round(float(baseline), 6)
                entry["details"]["delta"] = round(float(delta), 6) if delta is not None else None

            if entry.get("mode") == "real" and entry.get("status") == "ok":
                suite_p95 = (entry.get("details", {}) or {}).get("recall_p95_ms")
                try:
                    if suite_p95 is not None:
                        real_suite_p95_values.append(float(suite_p95))
                except Exception:
                    pass
                sample_values = (entry.get("details", {}) or {}).get("recall_latencies_ms")
                if isinstance(sample_values, list):
                    for item in sample_values:
                        try:
                            real_latency_samples.append(float(item))
                        except Exception:
                            continue

            suite_results[suite] = entry
            await self._store.record_benchmark_run(
                suite=suite,
                score=float(entry.get("score", 0.0)),
                status=str(entry.get("status", "unknown")),
                details={
                    **entry.get("details", {}),
                    "mode": entry.get("mode", "unknown"),
                    "require_real": require_real,
                },
                baseline_delta=delta,
            )

        blocked = bool(missing_real or failed_improvement or missing_baseline) if require_real else False
        warn = bool((failed_improvement or missing_baseline) and not blocked)
        if real_latency_samples:
            recall_p95 = _percentile(real_latency_samples, 0.95)
            recall_p95_source = "real_runner"
        elif real_suite_p95_values:
            recall_p95 = max(real_suite_p95_values)
            recall_p95_source = "real_runner_suite_p95"
        else:
            recall_p95 = historical_recall_p95
            recall_p95_source = "historical_slo_metrics"
        return {
            "timestamp": now,
            "status": "blocked" if blocked else ("warn" if warn else "ok"),
            "require_real": require_real,
            "summary": {
                "total_atoms": total_atoms,
                "quarantined": quarantined,
                "quarantine_ratio": round(quarantine_ratio, 6),
                "recall_p95_ms": round(recall_p95, 3),
                "recall_p95_source": recall_p95_source,
                "historical_recall_p95_ms": round(historical_recall_p95, 3),
                "real_runs": real_count,
                "proxy_runs": proxy_count,
                "missing_real_suites": missing_real,
            },
            "gates": {
                "min_improvement_required": round(min_improvement, 6),
                "failed_improvement_suites": failed_improvement,
                "missing_baseline_suites": missing_baseline,
            },
            "suites": suite_results,
        }

    async def _run_real_suite(self, suite: str, timeout_seconds: float) -> Optional[Dict[str, Any]]:
        cmd = self._suite_command(suite)
        if not cmd:
            return None

        start = time.monotonic()
        try:
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(
                process.communicate(),
                timeout=max(1.0, float(timeout_seconds)),
            )
        except asyncio.TimeoutError:
            logger.warning(f"[Benchmark] {suite} timed out")
            return {
                "score": 0.0,
                "status": "timeout",
                "mode": "real",
                "details": {
                    "timeout_seconds": timeout_seconds,
                    "cmd": cmd,
                },
            }
        except Exception as e:
            logger.warning(f"[Benchmark] {suite} execution error: {e}")
            return {
                "score": 0.0,
                "status": "runner_error",
                "mode": "real",
                "details": {
                    "error": str(e),
                    "cmd": cmd,
                },
            }

        elapsed_ms = int((time.monotonic() - start) * 1000)
        stdout = (stdout_b or b"").decode("utf-8", errors="ignore").strip()
        stderr = (stderr_b or b"").decode("utf-8", errors="ignore").strip()

        if process.returncode != 0:
            return {
                "score": 0.0,
                "status": "runner_failed",
                "mode": "real",
                "details": {
                    "return_code": process.returncode,
                    "stderr": stderr[-1000:],
                    "stdout": stdout[-1000:],
                    "elapsed_ms": elapsed_ms,
                    "cmd": cmd,
                },
            }

        parsed_payload = self._parse_json_payload(stdout)
        if isinstance(parsed_payload, dict):
            payload_score = parsed_payload.get("score", parsed_payload.get("overall"))
            if payload_score is not None:
                try:
                    score = float(payload_score)
                except Exception:
                    score = None
                else:
                    details = dict(parsed_payload.get("details", {}) or {})
                    details.update(
                        {
                            "elapsed_ms": elapsed_ms,
                            "cmd": cmd,
                            "stderr_tail": stderr[-500:],
                            "stdout_tail": stdout[-500:],
                        }
                    )
                    return {
                        "score": _normalize_score(score),
                        "status": str(parsed_payload.get("status", "ok")),
                        "mode": str(parsed_payload.get("mode", "real")),
                        "details": details,
                    }

        score = self._parse_score(stdout)
        if score is None:
            return {
                "score": 0.0,
                "status": "parse_failed",
                "mode": "real",
                "details": {
                    "stdout": stdout[-1000:],
                    "stderr": stderr[-1000:],
                    "elapsed_ms": elapsed_ms,
                    "cmd": cmd,
                },
            }

        return {
            "score": _normalize_score(score),
            "status": "ok",
            "mode": "real",
            "details": {
                "elapsed_ms": elapsed_ms,
                "cmd": cmd,
                "stderr_tail": stderr[-500:],
            },
        }

    @staticmethod
    def _parse_json_payload(stdout: str) -> Optional[Dict[str, Any]]:
        if not stdout:
            return None
        for candidate in [stdout, stdout.splitlines()[-1]]:
            try:
                parsed = json.loads(candidate)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                return parsed
        return None

    @staticmethod
    def _parse_score(stdout: str) -> Optional[float]:
        if not stdout:
            return None

        for candidate in [stdout, stdout.splitlines()[-1]]:
            try:
                parsed = json.loads(candidate)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                if "score" in parsed:
                    return float(parsed["score"])
                if "overall" in parsed:
                    return float(parsed["overall"])
            if isinstance(parsed, (int, float)):
                return float(parsed)

        labeled = re.search(r"(?i)score\s*[:=]\s*(-?\d+(?:\.\d+)?)", stdout)
        if labeled:
            try:
                return float(labeled.group(1))
            except Exception:
                return None

        for line in reversed(stdout.splitlines()):
            text = line.strip()
            if not text:
                continue
            try:
                return float(text)
            except Exception:
                continue

        match = re.search(r"(-?\d+(?:\.\d+)?)", stdout)
        if match:
            try:
                return float(match.group(1))
            except Exception:
                return None
        return None

    def _suite_command(self, suite: str) -> str:
        key = self._canonical_suite_name(suite).strip().lower()
        mapping = {
            "longmemeval": self._cfg.benchmark_cmd_longmemeval,
            "locomo": self._cfg.benchmark_cmd_locomo,
            "memoryarena": self._cfg.benchmark_cmd_memoryarena,
            "locomo-plus": self._cfg.benchmark_cmd_locomo_plus,
            "locomo_plus": self._cfg.benchmark_cmd_locomo_plus,
        }
        configured = (mapping.get(key, "") or "").strip()
        if configured:
            return configured
        return self._default_suite_command(self._canonical_suite_name(suite))

    @staticmethod
    def _default_suite_command(suite: str) -> str:
        runner = Path(__file__).resolve().parent / "scripts" / "suite_runner.py"
        if not runner.exists():
            return ""
        return (
            f"{shlex.quote(sys.executable)} "
            f"{shlex.quote(str(runner))} "
            f"--suite {shlex.quote(suite)}"
        )

    @staticmethod
    def _canonical_suite_name(suite: str) -> str:
        key = (suite or "").strip().lower().replace("_", "-")
        mapping = {
            "longmemeval": "LongMemEval",
            "locomo": "LoCoMo",
            "memoryarena": "MemoryArena",
            "locomo-plus": "LoCoMo-Plus",
        }
        return mapping.get(key, suite or "LongMemEval")

    def _suite_baseline(self, suite: str) -> Optional[float]:
        key = self._canonical_suite_name(suite)
        mapping = {
            "LongMemEval": self._cfg.benchmark_baseline_longmemeval,
            "LoCoMo": self._cfg.benchmark_baseline_locomo,
            "MemoryArena": self._cfg.benchmark_baseline_memoryarena,
            "LoCoMo-Plus": self._cfg.benchmark_baseline_locomo_plus,
        }
        baseline = float(mapping.get(key, 0.0))
        if baseline <= 0:
            return None
        return _normalize_score(baseline)

    @staticmethod
    def _suite_env_name(suite: str) -> str:
        key = suite.strip().upper().replace("-", "_")
        return f"SOUL_BENCHMARK_CMD_{key}"

    @staticmethod
    def _proxy_factors(total_atoms: int, quarantine_ratio: float, recall_p95: float) -> Dict[str, float]:
        capacity_factor = min(1.0, total_atoms / 5000.0)
        safety_factor = max(0.0, min(1.0, 1.0 - quarantine_ratio))
        latency_factor = 1.0 if recall_p95 <= 450 else max(0.0, 450.0 / max(1.0, recall_p95))
        return {
            "capacity_factor": capacity_factor,
            "safety_factor": safety_factor,
            "latency_factor": latency_factor,
        }

    @staticmethod
    def _proxy_suite_result(suite: str, factors: Dict[str, float]) -> Dict[str, Any]:
        capacity = factors["capacity_factor"]
        safety = factors["safety_factor"]
        latency = factors["latency_factor"]
        base_scores = {
            "LongMemEval": 0.45 * capacity + 0.30 * latency + 0.25 * safety,
            "LoCoMo": 0.35 * capacity + 0.35 * latency + 0.30 * safety,
            "MemoryArena": 0.30 * capacity + 0.40 * latency + 0.30 * safety,
            "LoCoMo-Plus": 0.25 * capacity + 0.35 * latency + 0.40 * safety,
        }
        score = float(base_scores.get(suite, base_scores["LongMemEval"]))
        return {
            "score": round(score, 6),
            "status": "proxy",
            "mode": "proxy",
            "details": {
                "capacity_factor": round(capacity, 6),
                "latency_factor": round(latency, 6),
                "safety_factor": round(safety, 6),
                "reason": "no_real_runner_configured",
            },
        }
