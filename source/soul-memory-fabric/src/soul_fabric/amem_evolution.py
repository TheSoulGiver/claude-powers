"""Phase 2: A-MEM 风格记忆演化器。"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from .atom import MemoryAtom


_NEGATION_MARKERS = ["不", "不是", "没", "没有", "never", "not", "no "]


class AmemEvolutionEngine:
    """在写入时执行轻量连边、冲突标记与置信度微调。"""

    @staticmethod
    def evolve(atom: MemoryAtom, recent_atoms: List[Dict[str, Any]]) -> Dict[str, Any]:
        best = AmemEvolutionEngine._find_best_match(atom, recent_atoms)
        if not best:
            return {
                "linked": False,
                "relation": None,
                "updated_confidence": atom.confidence,
                "updated_trust_score": atom.trust_score,
            }

        similarity = best["similarity"]
        prior = best["atom"]
        prior_id = prior.get("memory_id")
        prior_norm = str(prior.get("content_norm", "") or prior.get("content_raw", ""))

        is_conflict = AmemEvolutionEngine._is_conflict(atom.content_norm or atom.content_raw, prior_norm)
        relation_type = "conflicts" if is_conflict else "reinforces"

        atom.relations.append(
            {
                "type": relation_type,
                "target_memory_id": prior_id,
                "confidence": round(similarity, 4),
            }
        )

        if is_conflict:
            atom.confidence = max(0.2, min(atom.confidence, 0.6))
            atom.trust_score = max(0.1, atom.trust_score - 0.15)
        else:
            atom.confidence = min(1.0, atom.confidence + 0.05)
            atom.trust_score = min(1.0, atom.trust_score + 0.03)

        return {
            "linked": True,
            "relation": relation_type,
            "target_memory_id": prior_id,
            "similarity": similarity,
            "updated_confidence": atom.confidence,
            "updated_trust_score": atom.trust_score,
        }

    @staticmethod
    def _find_best_match(atom: MemoryAtom, recent_atoms: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        base = (atom.content_norm or atom.content_raw).strip().lower()
        if not base:
            return None

        best_atom = None
        best_score = 0.0
        for item in recent_atoms:
            text = str(item.get("content_norm", "") or item.get("content_raw", "")).strip().lower()
            if not text:
                continue
            score = SequenceMatcher(None, base[:500], text[:500]).ratio()
            if score > best_score:
                best_score = score
                best_atom = item

        if not best_atom or best_score < 0.72:
            return None

        return {
            "atom": best_atom,
            "similarity": float(best_score),
        }

    @staticmethod
    def _is_conflict(current: str, prior: str) -> bool:
        now = current.lower()
        prev = prior.lower()

        now_neg = any(token in now for token in _NEGATION_MARKERS)
        prev_neg = any(token in prev for token in _NEGATION_MARKERS)
        if now_neg != prev_neg:
            return True

        if "但是" in now or "but" in now:
            return True

        return False
