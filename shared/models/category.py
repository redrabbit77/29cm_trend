"""
카테고리 데이터 모델
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class Category(BaseModel):
    """카테고리 모델"""

    id: UUID
    name: str = Field(..., max_length=50, description="카테고리명")
    gender: str = Field(..., pattern="^(여성|남성)$", description="성별")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CategoryCreate(BaseModel):
    """카테고리 생성 모델"""

    name: str = Field(..., max_length=50, description="카테고리명")
    gender: str = Field(..., pattern="^(여성|남성)$", description="성별")
