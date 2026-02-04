"""
수집 PDF 일괄 분석: 텍스트 추출 → 규칙 기반 구조화 → JSON/CSV 저장.

사용:
  python scripts/analyze_pdfs.py                    # pdfs/ 하위 전체
  python scripts/analyze_pdfs.py pdfs/여성_의류     # 해당 폴더만
  python scripts/analyze_pdfs.py --output data/pdf_analysis  # 출력 폴더 지정

출력:
  - {output}/pdf_products.json  (전체 결과)
  - {output}/pdf_products.csv   (테이블용)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from analysis.pdf_parser import analyze_pdf, extract_text_from_pdf

import logging
logging.getLogger("pdfminer").setLevel(logging.WARNING)


def _is_review_pdf(path: Path) -> bool:
    """_review.pdf 또는 /review/ 등 리뷰 전용 PDF는 스킵."""
    name = path.name.lower()
    return "_review" in name or name.endswith("review.pdf")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="수집 PDF 분석 → 상품 정보 JSON/CSV 저장")
    parser.add_argument("input", nargs="?", default="pdfs", help="PDF 루트 폴더 (기본: pdfs)")
    parser.add_argument("--output", "-o", default="data/pdf_analysis", help="결과 저장 폴더")
    parser.add_argument("--limit", "-n", type=int, default=None, help="처리할 PDF 개수 제한")
    parser.add_argument("--no-llm", action="store_true", help="LLM 미사용, 규칙 기반만 사용 (OPENAI_API_KEY 무시)")
    parser.add_argument("--gemini", action="store_true", help="Gemini 3.0 Pro 사용 (GEMINI_API_KEY 또는 GOOGLE_API_KEY 필요)")
    parser.add_argument("--gemini-vision", action="store_true", help="Gemini 이미지 분석 포함 (PDF 페이지 이미지 → 무드·촬영·배경). --gemini와 함께 사용")
    args = parser.parse_args()

    base = _root / args.input if not Path(args.input).is_absolute() else Path(args.input)
    out_dir = _root / args.output
    out_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(p for p in base.rglob("*.pdf") if not _is_review_pdf(p))
    if args.limit:
        pdf_files = pdf_files[: args.limit]

    if not pdf_files:
        print("PDF 파일이 없습니다:", base)
        return 1

    use_llm = not args.no_llm
    use_gemini = getattr(args, "gemini", False)
    use_gemini_vision = getattr(args, "gemini_vision", False)
    results = []
    for i, pdf_path in enumerate(pdf_files):
        try:
            row = analyze_pdf(
                pdf_path,
                base_dir=base,
                use_llm=use_llm,
                use_gemini=use_gemini,
                use_gemini_vision=use_gemini_vision,
            )
            results.append(row)
            print(f"  [{i+1}/{len(pdf_files)}] {pdf_path.relative_to(base)} → 상품명: {(row.get('상품명') or '')[:40]}...")
        except Exception as e:
            print(f"  [{i+1}/{len(pdf_files)}] {pdf_path.name} 오류: {e}")

    # JSON 저장
    json_path = out_dir / "pdf_products.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {json_path} ({len(results)}건)")

    # CSV 저장 (평탄화)
    if results:
        import csv
        csv_path = out_dir / "pdf_products.csv"
        keys = ["source_pdf", "상품명", "브랜드명", "상세_카테고리명", "의류종류", "가격", "소재", "케어방법", "사이즈", "사이즈_상세", "색상", "이미지_무드", "이미지_톤", "이미지_배경", "사진_구성", "모델_특징", "제품_특징", "브랜드_평", "이미지_요약"]
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            for r in results:
                row = {k: r.get(k) for k in keys}
                if isinstance(row.get("사이즈"), list):
                    row["사이즈"] = ",".join(str(x) for x in row["사이즈"])
                if isinstance(row.get("색상"), list):
                    row["색상"] = ",".join(str(x) for x in row["색상"])
                w.writerow(row)
        print(f"저장: {csv_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
