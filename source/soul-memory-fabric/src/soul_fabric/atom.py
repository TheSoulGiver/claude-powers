"""Memory Fabric 的统一记忆原子模型。"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class MemoryState(str, Enum):
    RAW = "raw"
    CONSOLIDATED = "consolidated"
    ACTIVE = "active"
    RETIRED = "retired"
    QUARANTINED = "quarantined"


class MemoryAtom(BaseModel):
    """事件溯源型统一记忆对象。"""

    memory_id: str = Field(default_factory=lambda: f"mem_{uuid4().hex}")
    idempotency_key: Optional[str] = None
    tenant_id: str = "default"
    user_id: str

    @field_validator("user_id")
    @classmethod
    def user_id_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("user_id must not be empty")
        return v.strip()
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    session_type: str = "unknown"

    event_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ingest_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "soul"
    modality: str = "text"
    memory_type: str = "episode"

    content_raw: str = ""
    content_norm: str = ""
    entities: List[str] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)
    affect: Dict[str, Any] = Field(default_factory=dict)
    salience: float = 0.0

    confidence: float = 0.5
    trust_score: float = 0.5
    provenance: Dict[str, Any] = Field(default_factory=dict)

    retention_policy: str = "default"
    pii_tags: List[str] = Field(default_factory=list)
    legal_basis: Optional[str] = None

    vector_ref: Optional[str] = None
    graph_ref: Optional[str] = None
    block_ref: Optional[str] = None
    state: MemoryState = MemoryState.RAW
