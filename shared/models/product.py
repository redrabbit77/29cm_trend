"""
상품 데이터 모델
"""
import json
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class Product(BaseModel):
    """상품 모델"""

    id: UUID
    brand_id: UUID
    category_id: UUID
    name: str = Field(..., max_length=500, description="상품명")
    price: int = Field(..., ge=0, description="가격 (원 단위)")
    size: Optional[List[str]] = None
    color: Optional[List[str]] = None
    description: Optional[str] = None
    ranking: Optional[int] = Field(None, ge=1, le=10, description="BEST 랭킹")
    product_url: Optional[str] = None
    collected_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_db_row(cls, row: dict):
        """데이터베이스 행에서 모델 생성 (JSON 문자열을 리스트로 변환)"""
        data = dict(row)
        if isinstance(data.get("size"), str):
            data["size"] = json.loads(data["size"]) if data["size"] else None
        if isinstance(data.get("color"), str):
            data["color"] = json.loads(data["color"]) if data["color"] else None
        return cls(**data)


class ProductCreate(BaseModel):
    """상품 생성 모델"""

    brand_id: UUID
    category_id: UUID
    name: str = Field(..., max_length=500, description="상품명")
    price: int = Field(..., ge=0, description="가격 (원 단위)")
    size: Optional[List[str]] = None
    color: Optional[List[str]] = None
    description: Optional[str] = None
    ranking: Optional[int] = Field(None, ge=1, le=10, description="BEST 랭킹")
    product_url: Optional[str] = None

    def to_db_dict(self) -> dict:
        """데이터베이스 저장용 딕셔너리로 변환 (UUID→문자열, 리스트→JSON 문자열)"""
        data = self.model_dump()
        if isinstance(data.get("brand_id"), UUID):
            data["brand_id"] = str(data["brand_id"])
        if isinstance(data.get("category_id"), UUID):
            data["category_id"] = str(data["category_id"])
        if data.get("size"):
            data["size"] = json.dumps(data["size"], ensure_ascii=False)
        if data.get("color"):
            data["color"] = json.dumps(data["color"], ensure_ascii=False)
        return data
