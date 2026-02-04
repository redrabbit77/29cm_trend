"""
브랜드 데이터 모델
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class Brand(BaseModel):
    """브랜드 모델"""

    id: UUID
    name: str = Field(..., max_length=100, description="브랜드명")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BrandCreate(BaseModel):
    """브랜드 생성 모델"""

    name: str = Field(..., max_length=100, description="브랜드명")
