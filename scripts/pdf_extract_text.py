"""
PDF 텍스트 추출 (상품 PDF 분석 1단계)

사용:
  python scripts/pdf_extract_text.py                    # pdfs/ 하위 첫 PDF 1개만
  python scripts/pdf_extract_text.py pdfs/여성_의류     # 해당 폴더 내 PDF들
  python scripts/pdf_extract_text.py pdfs/여성_의류/01_3599047.pdf  # 단일 파일

추출된 텍스트는 상품명·브랜드·가격·소재·케어·사이즈·색상 등 구조화(LLM/규칙)의 입력으로 사용 가능.
"""
from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    import pdfplumber
except ImportError:
    print("pdfplumber가 필요합니다: pip install pdfplumber")
    sys.exit(1)

import logging
logging.getLogger("pdfminer").setLevel(logging.WARNING)


def extract_text_from_pdf(pdf_path: Path) -> str:
    """PDF 전체 페이지 텍스트를 하나의 문자열로 반환."""
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n\n".join(text_parts)


def main() -> int:
    base = _root / "pdfs"
    if len(sys.argv) >= 2:
        arg = Path(sys.argv[1])
        if arg.is_absolute():
            base = arg
        else:
            base = _root / arg

    if base.is_file():
        pdf_files = [base]
    else:
        pdf_files = sorted(base.rglob("*.pdf"))[:5]  # 최대 5개

    if not pdf_files:
        print("PDF 파일이 없습니다:", base)
        return 1

    for pdf_path in pdf_files:
        print("=" * 60)
        print("PDF:", pdf_path.relative_to(_root))
        print("=" * 60)
        try:
            text = extract_text_from_pdf(pdf_path)
            preview = (text or "(텍스트 없음)")[:2500]
            print(preview)
            if len(text or "") > 2500:
                print("\n... (이하 생략, 전체", len(text), "자)")
        except Exception as e:
            print("오류:", e)
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
