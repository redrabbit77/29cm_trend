"""
수집 작업 데이터 모델
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CollectionTask(BaseModel):
    """수집 작업 모델"""

    id: UUID
    category_id: UUID
    status: str = Field(
        ...,
        pattern="^(pending|running|completed|failed|cancelled)$",
        description="작업 상태",
    )
    progress: int = Field(default=0, ge=0, le=100, description="진행률 (0-100)")
    total_items: int = Field(default=0, ge=0, description="총 수집할 항목 수")
    collected_items: int = Field(default=0, ge=0, description="수집 완료된 항목 수")
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CollectionTaskCreate(BaseModel):
    """수집 작업 생성 모델"""

    category_id: UUID


class CollectionTaskUpdate(BaseModel):
    """수집 작업 업데이트 모델"""

    status: Optional[str] = Field(
        None, pattern="^(pending|running|completed|failed|cancelled)$"
    )
    progress: Optional[int] = Field(None, ge=0, le=100)
    total_items: Optional[int] = Field(None, ge=0)
    collected_items: Optional[int] = Field(None, ge=0)
    error_message: Optional[str] = None
