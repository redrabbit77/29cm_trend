"""
상품 이미지 데이터 모델
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProductImage(BaseModel):
    """상품 이미지 모델"""

    id: UUID
    product_id: UUID
    image_url: str = Field(..., description="Supabase Storage URL")
    image_type: str = Field(
        default="lookbook",
        description="lookbook | detail | thumbnail",
    )
    order_index: int = Field(default=0, ge=0, description="이미지 순서")
    created_at: datetime

    class Config:
        from_attributes = True


class ProductImageCreate(BaseModel):
    """상품 이미지 생성 모델"""

    product_id: UUID
    image_url: str = Field(..., description="Supabase Storage URL")
    image_type: str = Field(
        default="lookbook",
        description="lookbook | detail | thumbnail",
    )
    order_index: int = Field(default=0, ge=0)
