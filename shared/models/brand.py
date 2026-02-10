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
    style_axis: float | None = Field(None, ge=0, le=100, description="브랜드맵 스타일 축 0~100")
    premium_axis: float | None = Field(None, ge=0, le=100, description="브랜드맵 프리미엄 축 0~100")
    representative_color: str | None = Field(None, max_length=20, description="브랜드 표시색 hex 또는 색상명")

    class Config:
        from_attributes = True


class BrandCreate(BaseModel):
    """브랜드 생성 모델"""

    name: str = Field(..., max_length=100, description="브랜드명")
    style_axis: float | None = None
    premium_axis: float | None = None
    representative_color: str | None = None
