"""Memory Fabric 控制平面 API 模型。"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from .utils import is_valid_user_id


class MemoryEventRequest(BaseModel):
    """POST /v1/memory/events"""

    idempotency_key: str = Field(min_length=8, max_length=256)
    tenant_id: str = Field(default="default", max_length=128)
    user_id: Optional[str] = Field(default=None, max_length=128)
    agent_id: Optional[str] = Field(default=None, max_length=128)
    session_id: Optional[str] = Field(default=None, max_length=128)
    session_type: str = Field(default="unknown", max_length=32)

    event_time: Optional[datetime] = None
    source: str = Field(default="soul", max_length=64)
    modality: str = Field(default="text", max_length=32)
    memory_type: str = Field(default="episode", max_length=64)

    content_raw: str = Field(min_length=1, max_length=8000)
    content_norm: str = Field(default="", max_length=8000)
    entities: List[str] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)
    affect: Dict[str, Any] = Field(default_factory=dict)

    salience: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    trust_score: float = Field(default=0.5, ge=0.0, le=1.0)
    provenance: Dict[str, Any] = Field(default_factory=dict)

    retention_policy: str = Field(default="default", max_length=64)
    pii_tags: List[str] = Field(default_factory=list)
    legal_basis: Optional[str] = Field(default=None, max_length=128)

    @field_validator("entities")
    @classmethod
    def _trim_entities(cls, value: List[str]) -> List[str]:
        clean = []
        for item in value[:32]:
            text = item.strip()
            if text:
                clean.append(text[:128])
        return clean

    @field_validator("user_id")
    @classmethod
    def _validate_user_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        user_id = str(value).strip()
        if not is_valid_user_id(user_id):
            raise ValueError("invalid user_id")
        return user_id


class MemoryConsolidateRequest(BaseModel):
    """POST /v1/memory/consolidate"""

    user_id: Optional[str] = Field(default=None, max_length=128)
    dry_run: bool = False

    @field_validator("user_id")
    @classmethod
    def _validate_user_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        user_id = str(value).strip()
        if not is_valid_user_id(user_id):
            raise ValueError("invalid user_id")
        return user_id


class MemoryRecallRequest(BaseModel):
    """POST /v1/memory/recall"""

    user_id: Optional[str] = Field(default=None, max_length=128)
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=3, ge=1, le=12)
    timeout_ms: int = Field(default=600, ge=100, le=3000)
    include_citations: bool = True
    include_uncertainty: bool = True

    @field_validator("user_id")
    @classmethod
    def _validate_user_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        user_id = str(value).strip()
        if not is_valid_user_id(user_id):
            raise ValueError("invalid user_id")
        return user_id


class MemoryReflectRequest(BaseModel):
    """POST /v1/memory/reflect"""

    user_id: Optional[str] = Field(default=None, max_length=128)
    rule: str = Field(min_length=1, max_length=2000)
    rule_type: str = Field(default="policy", max_length=64)
    priority: int = Field(default=50, ge=0, le=100)
    active: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("user_id")
    @classmethod
    def _validate_user_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        user_id = str(value).strip()
        if not is_valid_user_id(user_id):
            raise ValueError("invalid user_id")
        return user_id


class MemoryDeleteUserRequest(BaseModel):
    """POST /v1/memory/delete_user"""

    user_id: Optional[str] = Field(default=None, max_length=128)
    reason: str = Field(default="user_request", max_length=256)

    @field_validator("user_id")
    @classmethod
    def _validate_user_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        user_id = str(value).strip()
        if not is_valid_user_id(user_id):
            raise ValueError("invalid user_id")
        return user_id


class MemoryBenchmarkRequest(BaseModel):
    """POST /v1/memory/benchmark"""

    suites: List[str] = Field(default_factory=lambda: [
        "LongMemEval",
        "LoCoMo",
        "MemoryArena",
        "LoCoMo-Plus",
    ])

    @field_validator("suites")
    @classmethod
    def _normalize_suites(cls, value: List[str]) -> List[str]:
        mapping = {
            "longmemeval": "LongMemEval",
            "locomo": "LoCoMo",
            "memoryarena": "MemoryArena",
            "locomo-plus": "LoCoMo-Plus",
            "locomo_plus": "LoCoMo-Plus",
        }
        normalized: List[str] = []
        for raw in value or []:
            key = str(raw or "").strip().lower().replace("_", "-")
            suite = mapping.get(key)
            if suite and suite not in normalized:
                normalized.append(suite)
        return normalized or [
            "LongMemEval",
            "LoCoMo",
            "MemoryArena",
            "LoCoMo-Plus",
        ]


class SourceCitation(BaseModel):
    source: str
    count: int


class UncertaintyReport(BaseModel):
    score: float
    reason: str


class MemoryRecallResponse(BaseModel):
    user_id: str
    relationship_stage: str
    latency_ms: float
    context_pack: Dict[str, Any]
    citations: List[SourceCitation] = Field(default_factory=list)
    uncertainty: Optional[UncertaintyReport] = None


class MemoryTraceResponse(BaseModel):
    memory_id: str
    atom: Optional[Dict[str, Any]] = None
    traces: List[Dict[str, Any]] = Field(default_factory=list)
