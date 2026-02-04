"""
PDF 수집 실행 진입점.

사용 (프로젝트 루트에서):
  python -m agent.run_pdf_collect
  python -m agent.run_pdf_collect --headless
  python -m agent.run_pdf_collect --output pdfs --max-categories 1
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from agent.pdf_collector import (
    CATEGORY_BEST_URLS,
    PDF_OUTPUT_DIR,
    PROGRESS_FILE,
    run_pdf_collection,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="29CM BEST 1~10위 상품 상세 페이지를 A5 PDF로 저장")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=PDF_OUTPUT_DIR,
        help=f"PDF 저장 폴더 (기본: {PDF_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="브라우저 창 숨김",
    )
    parser.add_argument(
        "--max-categories",
        type=int,
        default=None,
        help="처리할 카테고리 수 제한 (전체 수집 시 사용, 기본: 전체)",
    )
    parser.add_argument(
        "--category", "-c",
        type=str,
        default=None,
        choices=[name for name, _ in CATEGORY_BEST_URLS],
        help="카테고리 1개만 수집 (예: 여성_의류). 지정 시 --max-categories 무시.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    n = run_pdf_collection(
        output_dir=args.output,
        headless=args.headless,
        max_categories=args.max_categories,
        category_slug=args.category,
        progress_file=PROGRESS_FILE,
    )
    print(f"저장 완료: {n}개 PDF → {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
