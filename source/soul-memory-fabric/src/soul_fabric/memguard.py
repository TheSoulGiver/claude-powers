"""Phase 2: A-MemGuard 风格安全防线。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .utils import check_sensitivity


_POISON_MARKERS = [
    "ignore previous",
    "system prompt",
    "developer instruction",
    "越狱",
    "请忽略",
    "泄露",
    "密钥",
    "token",
]


@dataclass
class GuardVerdict:
    action: str
    risk_score: float
    reasons: List[str]


class MemGuard:
    """投毒检测 + 隔离策略。"""

    @staticmethod
    def evaluate(text: str, trust_score: float, quarantine_threshold: float) -> GuardVerdict:
        content = (text or "").strip()
        if not content:
            return GuardVerdict(action="allow", risk_score=0.0, reasons=[])

        risk = 0.0
        reasons: List[str] = []

        sensitivity = check_sensitivity(content)
        if sensitivity == "block":
            risk += 0.8
            reasons.append("contains_blocked_sensitive_data")
        elif sensitivity == "caution":
            risk += 0.25
            reasons.append("contains_caution_sensitive_data")

        lowered = content.lower()
        poison_hits = [marker for marker in _POISON_MARKERS if marker in lowered]
        if poison_hits:
            risk += min(0.5, 0.15 * len(poison_hits))
            reasons.append("possible_prompt_or_memory_poisoning")

        if trust_score < 0.35:
            risk += 0.2
            reasons.append("low_trust_score")

        if len(content) > 4000:
            risk += 0.15
            reasons.append("oversized_event_payload")

        risk = min(risk, 1.0)
        if risk >= quarantine_threshold:
            return GuardVerdict(action="quarantine", risk_score=risk, reasons=reasons)
        if risk >= 0.45:
            return GuardVerdict(action="caution", risk_score=risk, reasons=reasons)
        return GuardVerdict(action="allow", risk_score=risk, reasons=reasons)
