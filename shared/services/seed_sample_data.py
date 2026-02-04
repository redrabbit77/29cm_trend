"""
Supabase에 샘플 카테고리/브랜드/상품/작업 데이터를 넣기 위한 유틸리티.

Phase 2 Web UI 를 빠르게 테스트하기 위한 용도이며,
실제 크롤러(Phase 1)와는 별도로 동작하는 간단한 시드 스크립트입니다.
"""
from __future__ import annotations

from uuid import uuid4

from shared.models.category import CategoryCreate
from shared.models.product import ProductCreate
from shared.models.task import CollectionTaskCreate
from shared.services import DataService


def seed_categories(service: DataService) -> None:
    """여성/남성 카테고리 몇 개를 생성 (이미 존재하면 건너뜀)."""
    base_categories = [
        ("여성", "원피스"),
        ("여성", "니트"),
        ("여성", "블라우스"),
        ("남성", "셔츠"),
        ("남성", "슬랙스"),
    ]

    existing = {c.name for c in service.get_categories()}
    for gender, name in base_categories:
        if name in existing:
            continue
        service.create_category(
            CategoryCreate(
                gender=gender,
                name=name,
            )
        )


def seed_brands(service: DataService) -> list[str]:
    """샘플 브랜드를 생성하고, 생성된 브랜드 ID 리스트를 반환."""
    brand_names = ["A-Studio", "TwentyNine", "Urban Mood", "Classic & Co", "Minimalist"]
    ids: list[str] = []
    for name in brand_names:
        brand = service.get_or_create_brand(name)
        ids.append(str(brand.id))
    return ids


def seed_products(service: DataService) -> None:
    """브랜드/카테고리 조합으로 간단한 상품 데이터 생성."""
    categories = service.get_categories()
    if not categories:
        seed_categories(service)
        categories = service.get_categories()

    brand_ids = seed_brands(service)

    price_buckets = [29_000, 49_000, 79_000, 99_000, 129_000]

    for cat in categories:
        for i, base_price in enumerate(price_buckets, start=1):
            for b_id in brand_ids:
                product = ProductCreate(
                    category_id=cat.id,
                    brand_id=b_id,
                    name=f"{cat.gender} {cat.name} {i}차 샘플",
                    price=base_price + (i * 1_000),
                )
                service.create_product(product)


def seed_tasks(service: DataService) -> None:
    """샘플 수집 작업 몇 개 생성."""
    categories = service.get_categories()
    if not categories:
        return
    for cat in categories[:5]:
        task = CollectionTaskCreate(category_id=cat.id)
        service.create_collection_task(task)


def main() -> None:
    service = DataService()
    seed_categories(service)
    seed_brands(service)
    seed_products(service)
    seed_tasks(service)
    print("샘플 데이터 시딩이 완료되었습니다.")


if __name__ == "__main__":
    main()

