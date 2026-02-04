"""
Supabase 수집·상품·이미지 데이터 전체 삭제 (프로젝트 전면 개편용).

- 테이블: product_images → products → collection_tasks → brands (FK 순서, 0건 될 때까지 반복 삭제)
- Storage 버킷(product-images) 내 객체 전체 삭제
- categories는 시드 데이터로 남김 (앱 동작을 위해). 삭제하려면 --include-categories

데이터가 남아 있으면 Supabase 대시보드 > SQL Editor에서
  supabase_local/sql/truncate_all_data.sql
을 실행하세요 (TRUNCATE로 확실히 비움).

사용: 프로젝트 루트에서
  python -m scripts.reset_supabase_all
  python -m scripts.reset_supabase_all --include-categories   # 카테고리도 삭제
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from shared.config import get_settings
from shared.services import get_supabase_client


def delete_storage_contents(client, bucket: str) -> int:
    """Storage 버킷 내 모든 객체 삭제. product_id/파일명 구조 가정, 최대 1000건씩 remove."""
    paths = []
    try:
        top = client.storage.from_(bucket).list()
        for item in top:
            name = item.get("name") if isinstance(item, dict) else str(item)
            if not name:
                continue
            try:
                sub = client.storage.from_(bucket).list(name)
                for s in sub:
                    sn = s.get("name") if isinstance(s, dict) else str(s)
                    if sn:
                        paths.append(f"{name}/{sn}")
            except Exception:
                paths.append(name)
    except Exception as e:
        print(f"Storage 목록 조회 중 오류 (버킷 없음 가능): {e}")
        return 0
    removed = 0
    for i in range(0, len(paths), 1000):
        batch = paths[i : i + 1000]
        try:
            client.storage.from_(bucket).remove(batch)
            removed += len(batch)
        except Exception as e:
            print(f"Storage 삭제 일부 실패: {e}")
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description="Supabase 수집/상품/이미지 데이터 전체 삭제")
    parser.add_argument("--include-categories", action="store_true", help="categories 테이블도 비우기 (재시드 필요)")
    parser.add_argument("--dry-run", action="store_true", help="실제 삭제 없이 예정 작업만 출력")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_key:
        print("오류: .env에 SUPABASE_URL, SUPABASE_SERVICE_KEY 가 필요합니다.")
        sys.exit(1)

    client = get_supabase_client(use_service_key=True)
    bucket = get_settings().supabase_storage_bucket or "product-images"

    if args.dry_run:
        print("[DRY RUN] 다음 순서로 삭제됩니다: product_images → products → collection_tasks → brands")
        if args.include_categories:
            print("[DRY RUN] categories 도 삭제됩니다.")
        print("[DRY RUN] Storage 버킷:", bucket)
        return

    print("Supabase 데이터 전체 삭제를 시작합니다...")
    print("  (PostgREST는 한 번에 삭제 행 수 제한이 있을 수 있어, 0건 될 때까지 반복 삭제합니다.)")

    def delete_all_rows(table_name: str) -> int:
        total = 0
        while True:
            r = (
                client.table(table_name)
                .delete()
                .neq("id", "00000000-0000-0000-0000-000000000000")
                .execute()
            )
            n = len(r.data) if r.data else 0
            total += n
            if n == 0:
                break
        return total

    # 1) product_images
    n1 = delete_all_rows("product_images")
    print(f"  product_images: {n1}행 삭제 완료")

    # 2) products
    n2 = delete_all_rows("products")
    print(f"  products: {n2}행 삭제 완료")

    # 3) collection_tasks
    n3 = delete_all_rows("collection_tasks")
    print(f"  collection_tasks: {n3}행 삭제 완료")

    # 4) brands
    n4 = delete_all_rows("brands")
    print(f"  brands: {n4}행 삭제 완료")

    if args.include_categories:
        n5 = delete_all_rows("categories")
        print(f"  categories: {n5}행 삭제 완료 (재시드 시 initial_schema.sql 실행)")

    # 5) Storage 버킷 내 객체 삭제
    n = delete_storage_contents(client, bucket)
    print(f"  Storage ({bucket}): {n}개 객체 삭제 완료")

    print("전체 삭제가 완료되었습니다.")


if __name__ == "__main__":
    main()
