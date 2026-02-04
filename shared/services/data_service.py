"""
데이터 서비스 - Supabase CRUD 작업
"""
import io
import logging
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

if TYPE_CHECKING:
    from supabase import Client

from storage3.exceptions import StorageApiError

from shared.models.brand import Brand, BrandCreate
from shared.models.category import Category, CategoryCreate
from shared.models.product import Product, ProductCreate
from shared.models.product_image import ProductImage, ProductImageCreate
from shared.models.task import (
    CollectionTask,
    CollectionTaskCreate,
    CollectionTaskUpdate,
)
from shared.services.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


class DataService:
    """데이터 서비스 클래스"""

    def __init__(self, client: Optional["Client"] = None, use_service_key: bool = False):
        """
        Args:
            client: Supabase 클라이언트 (None이면 자동 생성)
            use_service_key: 서비스 키 사용 여부
        """
        self.client = client or get_supabase_client(use_service_key=use_service_key)

    # ========== 카테고리 ==========

    def get_categories(
        self, gender: Optional[str] = None
    ) -> List[Category]:
        """카테고리 목록 조회"""
        query = self.client.table("categories").select("*")
        if gender:
            query = query.eq("gender", gender)
        result = query.execute()
        return [Category(**row) for row in result.data]

    def get_category(self, category_id: UUID) -> Optional[Category]:
        """카테고리 조회"""
        result = (
            self.client.table("categories")
            .select("*")
            .eq("id", str(category_id))
            .execute()
        )
        if result.data:
            return Category(**result.data[0])
        return None

    def get_category_by_name_and_gender(self, name: str, gender: str) -> Optional[Category]:
        """카테고리명·성별로 조회 (예: name='의류', gender='여성'). PDF 상세_카테고리명 매칭용."""
        if not name or not gender:
            return None
        result = (
            self.client.table("categories")
            .select("*")
            .eq("name", name)
            .eq("gender", gender)
            .execute()
        )
        if result.data:
            return Category(**result.data[0])
        return None

    def create_category(self, category: CategoryCreate) -> Category:
        """카테고리 생성"""
        result = (
            self.client.table("categories")
            .insert(category.model_dump())
            .execute()
        )
        return Category(**result.data[0])

    # ========== 브랜드 ==========

    def get_brands(self) -> List[Brand]:
        """브랜드 목록 조회"""
        result = self.client.table("brands").select("*").execute()
        return [Brand(**row) for row in result.data]

    def get_brand(self, brand_id: UUID) -> Optional[Brand]:
        """브랜드 조회"""
        result = (
            self.client.table("brands")
            .select("*")
            .eq("id", str(brand_id))
            .execute()
        )
        if result.data:
            return Brand(**result.data[0])
        return None

    def get_or_create_brand(self, brand_name: str) -> Brand:
        """브랜드 조회 또는 생성"""
        # 먼저 조회
        result = (
            self.client.table("brands")
            .select("*")
            .eq("name", brand_name)
            .execute()
        )
        if result.data:
            return Brand(**result.data[0])

        # 없으면 생성
        result = (
            self.client.table("brands")
            .insert({"name": brand_name})
            .execute()
        )
        return Brand(**result.data[0])

    # ========== 상품 ==========

    def get_products(
        self,
        brand_id: Optional[UUID] = None,
        category_id: Optional[UUID] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "collected_at",
        order_desc: bool = True,
    ) -> List[Product]:
        """상품 목록 조회"""
        query = self.client.table("products").select("*")
        if brand_id:
            query = query.eq("brand_id", str(brand_id))
        if category_id:
            query = query.eq("category_id", str(category_id))
        if min_price is not None:
            query = query.gte("price", min_price)
        if max_price is not None:
            query = query.lte("price", max_price)
        if start_date:
            # 수집 날짜 하한 (YYYY-MM-DD 형식 문자열 기대)
            query = query.gte("collected_at", start_date)
        if end_date:
            # 수집 날짜 상한
            query = query.lte("collected_at", end_date)

        # 정렬
        if order_desc:
            query = query.order(order_by, desc=True)
        else:
            query = query.order(order_by, desc=False)

        # 페이지네이션
        query = query.range(offset, offset + limit - 1)

        result = query.execute()
        return [Product.from_db_row(row) for row in result.data]

    def create_product(self, product: ProductCreate) -> Product:
        """상품 생성"""
        result = (
            self.client.table("products")
            .insert(product.to_db_dict())
            .execute()
        )
        return Product.from_db_row(result.data[0])

    def delete_product(self, product_id: UUID) -> None:
        """상품 삭제 (product_images는 FK CASCADE로 함께 삭제됨)."""
        self.client.table("products").delete().eq("id", str(product_id)).execute()

    # ========== 상품 이미지 ==========

    def get_product_images(self, product_id: UUID) -> List[ProductImage]:
        """상품별 이미지 목록 조회 (order_index 순)."""
        result = (
            self.client.table("product_images")
            .select("*")
            .eq("product_id", str(product_id))
            .order("order_index")
            .execute()
        )
        return [ProductImage(**row) for row in result.data]

    def create_product_image(
        self, image: ProductImageCreate
    ) -> ProductImage:
        """상품 이미지 레코드 생성"""
        payload = image.model_dump()
        if isinstance(payload.get("product_id"), UUID):
            payload["product_id"] = str(payload["product_id"])
        result = (
            self.client.table("product_images")
            .insert(payload)
            .execute()
        )
        return ProductImage(**result.data[0])

    def upload_image_to_storage(
        self,
        file_bytes: bytes,
        storage_path: str,
        content_type: str = "image/jpeg",
        bucket: Optional[str] = None,
    ) -> str:
        """
        Storage에 이미지 업로드 후 공개 URL 반환.

        Args:
            file_bytes: 이미지 바이트
            storage_path: 버킷 내 경로 (예: product_id/lookbook_001.jpg)
            content_type: MIME 타입
            bucket: 버킷명 (None이면 설정값 사용)

        Returns:
            공개 URL (get_public_url 결과)
        """
        if bucket is None:
            from shared.config import get_settings
            bucket = get_settings().supabase_storage_bucket
        # storage3: file 인자는 bytes 또는 경로(str/Path). BytesIO는 미지원 → 항상 bytes로 통일
        if isinstance(file_bytes, bytes):
            data = file_bytes
        elif hasattr(file_bytes, "read"):
            data = file_bytes.read()
            if not isinstance(data, bytes):
                data = data.encode() if isinstance(data, str) else b""
        else:
            data = file_bytes if isinstance(file_bytes, bytes) else b""

        def _upload() -> None:
            self.client.storage.from_(bucket).upload(
                path=storage_path,
                file=data,
                file_options={
                    "content-type": content_type,
                    "upsert": "false",
                },
            )

        try:
            _upload()
        except StorageApiError as e:
            is_bucket_not_found = (
                "Bucket not found" in (str(e) or "")
                or (getattr(e, "code", None) or "").lower() == "bucket not found"
            )
            if is_bucket_not_found:
                logger.info("Storage 버킷이 없어 생성합니다: %s", bucket)
                try:
                    self.client.storage.create_bucket(
                        bucket,
                        options={"public": True},
                    )
                except Exception as create_err:
                    logger.warning("버킷 생성 실패 (수동 생성 필요): %s", create_err)
                    raise
                _upload()
            else:
                raise
        resp = self.client.storage.from_(bucket).get_public_url(storage_path)
        return getattr(resp, "publicUrl", None) or str(resp)

    # ========== 수집 작업 ==========

    def create_collection_task(
        self, task: CollectionTaskCreate
    ) -> CollectionTask:
        """수집 작업 생성"""
        payload = task.model_dump()
        # Supabase HTTP 클라이언트가 UUID를 직렬화할 수 있도록 문자열로 변환
        if isinstance(payload.get("category_id"), UUID):
            payload["category_id"] = str(payload["category_id"])
        result = (
            self.client.table("collection_tasks")
            .insert(payload)
            .execute()
        )
        return CollectionTask(**result.data[0])

    def get_pending_tasks(self, limit: int = 10) -> List[CollectionTask]:
        """에이전트용: 대기(pending) 상태의 작업 목록 조회."""
        return self.get_tasks(status="pending", limit=limit)

    def claim_task(self, task_id: UUID) -> Optional[CollectionTask]:
        """
        에이전트용: pending → running 으로 상태를 전이하면서 작업을 가져온다.

        여러 에이전트가 동시에 동작할 수 있으므로,
        status='pending' 조건을 함께 걸어 경쟁 상태를 완화한다.
        """
        update = CollectionTaskUpdate(status="running")
        data = update.model_dump(exclude_none=True)
        result = (
            self.client.table("collection_tasks")
            .update(data)
            .eq("id", str(task_id))
            .eq("status", "pending")
            .execute()
        )
        if not result.data:
            return None
        return CollectionTask(**result.data[0])

    def get_tasks(
        self, status: Optional[str] = None, limit: int = 50
    ) -> List[CollectionTask]:
        """작업 목록 조회"""
        query = self.client.table("collection_tasks").select("*")
        if status:
            query = query.eq("status", status)
        query = query.order("created_at", desc=True).limit(limit)
        result = query.execute()
        return [CollectionTask(**row) for row in result.data]

    def get_task(self, task_id: UUID) -> Optional[CollectionTask]:
        """작업 조회"""
        result = (
            self.client.table("collection_tasks")
            .select("*")
            .eq("id", str(task_id))
            .execute()
        )
        if result.data:
            return CollectionTask(**result.data[0])
        return None

    def update_task_status(
        self,
        task_id: UUID,
        update_data: CollectionTaskUpdate,
    ) -> CollectionTask:
        """작업 상태 업데이트"""
        data = update_data.model_dump(exclude_none=True)
        result = (
            self.client.table("collection_tasks")
            .update(data)
            .eq("id", str(task_id))
            .execute()
        )
        return CollectionTask(**result.data[0])

    def delete_task(self, task_id: UUID) -> None:
        """수집 작업 1건을 DB에서 삭제. (collection_tasks 테이블)"""
        self.client.table("collection_tasks").delete().eq("id", str(task_id)).execute()

    def delete_failed_tasks(self) -> int:
        """status='failed'인 수집 작업을 모두 삭제. 삭제된 건수를 반환."""
        failed = self.get_tasks(status="failed", limit=500)
        for task in failed:
            self.delete_task(task.id)
        return len(failed)
