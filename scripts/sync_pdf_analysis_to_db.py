"""
PDF 분석 결과(JSON)를 DB(products, brands)에 반영.

사용:
  python scripts/sync_pdf_analysis_to_db.py
  python scripts/sync_pdf_analysis_to_db.py --input data/pdf_analysis/pdf_products.json
  python scripts/sync_pdf_analysis_to_db.py --brand-map  # 브랜드 맵 생성 후 저장
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from shared.services.data_service import DataService
from shared.models.product import ProductCreate


def _category_slug_to_name_gender(slug: str) -> tuple[str, str]:
    """상세_카테고리명(예: 여성_의류, 남성_슈즈) → (name, gender)."""
    slug = (slug or "").strip()
    if "_" in slug:
        parts = slug.split("_", 1)
        return (parts[1].strip(), parts[0].strip())
    if slug in ("여성", "남성"):
        return ("의류", slug)
    return ("의류", "여성")  # 기본


def _build_description(row: dict) -> str:
    """소재·케어·이미지 분석 필드를 한 텍스트로 합침 (DB description용)."""
    parts = []
    if row.get("소재"):
        parts.append(f"[소재] {row['소재']}")
    if row.get("케어방법"):
        parts.append(f"[케어] {row['케어방법']}")
    if row.get("사이즈_상세"):
        parts.append(f"[사이즈상세] {row['사이즈_상세'][:500]}")
    for key in ("이미지_무드", "이미지_톤", "이미지_배경", "사진_구성", "모델_특징", "제품_특징", "브랜드_평"):
        if row.get(key):
            parts.append(f"[{key}] {row[key]}")
    if row.get("이미지_요약"):
        parts.append(f"[요약] {row['이미지_요약']}")
    return "\n".join(parts) if parts else ""


def sync_pdf_results_to_db(
    products: list[dict],
    data_service: DataService | None = None,
    dry_run: bool = False,
) -> tuple[int, list[str]]:
    """
    PDF 분석 결과 리스트를 DB(products, brands)에 반영.
    Returns: (성공 건수, 에러 메시지 리스트)
    """
    service = data_service or DataService()
    created = 0
    errors: list[str] = []

    for row in products:
        brand_name = (row.get("브랜드명") or "").strip()
        if not brand_name:
            errors.append(f"브랜드명 없음: {row.get('source_pdf', '')}")
            continue

        name = (row.get("상품명") or "").strip() or "(상품명 없음)"
        price_val = row.get("가격")
        if price_val is None or (isinstance(price_val, (int, float)) and price_val < 0):
            price_val = 0
        try:
            price = int(price_val)
        except (TypeError, ValueError):
            price = 0

        slug = row.get("상세_카테고리명") or row.get("의류종류") or ""
        cat_name, gender = _category_slug_to_name_gender(slug)
        category = service.get_category_by_name_and_gender(cat_name, gender)
        if not category:
            errors.append(f"카테고리 없음 name={cat_name} gender={gender}: {row.get('source_pdf', '')}")
            continue

        if dry_run:
            created += 1
            continue

        brand = service.get_or_create_brand(brand_name)
        size = row.get("사이즈")
        if not isinstance(size, list):
            size = []
        color = row.get("색상")
        if not isinstance(color, list):
            color = []
        description = _build_description(row)

        try:
            service.create_product(
                ProductCreate(
                    brand_id=brand.id,
                    category_id=category.id,
                    name=name[:500],
                    price=price,
                    size=size if size else None,
                    color=color if color else None,
                    description=description or None,
                    ranking=None,
                    product_url=None,
                )
            )
            created += 1
        except Exception as e:
            errors.append(f"{row.get('source_pdf', '')}: {e}")

    return created, errors


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="PDF 분석 결과를 DB에 반영")
    parser.add_argument(
        "--input", "-i",
        default=str(_root / "data" / "pdf_analysis" / "pdf_products.json"),
        help="pdf_products.json 경로",
    )
    parser.add_argument("--dry-run", action="store_true", help="실제 insert 없이 건수만 확인")
    parser.add_argument("--brand-map", action="store_true", help="브랜드 맵 생성 후 data/pdf_analysis/brand_map.json 저장")
    args = parser.parse_args()

    path = Path(args.input)
    if not path.is_absolute():
        path = _root / path
    if not path.exists():
        print(f"파일 없음: {path}")
        return 1

    with open(path, encoding="utf-8") as f:
        products = json.load(f)
    if not isinstance(products, list):
        print("JSON이 배열이 아닙니다.")
        return 1

    service = DataService()
    created, errors = sync_pdf_results_to_db(products, data_service=service, dry_run=args.dry_run)
    print(f"DB 반영: {created}건 성공")
    for e in errors[:20]:
        print(f"  오류: {e}")
    if len(errors) > 20:
        print(f"  ... 외 {len(errors) - 20}건")

    if args.brand_map and products:
        try:
            from analysis.gemini_extract import generate_brand_map
            brand_map = generate_brand_map(products)
            if brand_map:
                out_path = path.parent / "brand_map.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(brand_map, f, ensure_ascii=False, indent=2)
                print(f"브랜드 맵 저장: {out_path}")
            else:
                print("브랜드 맵 생성 실패 (GEMINI_API_KEY 확인)")
        except Exception as e:
            print(f"브랜드 맵 생성 오류: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
