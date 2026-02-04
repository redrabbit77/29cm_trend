"""
PDF 기반 상품 정보 분석 (텍스트 추출 + 규칙 기반 구조화).
"""
from .pdf_parser import extract_text_from_pdf, parse_product_from_text

try:
    from .gemini_extract import test_gemini_connection
except ImportError:
    test_gemini_connection = None  # type: ignore[misc, assignment]

__all__ = [
    "extract_text_from_pdf",
    "parse_product_from_text",
    "test_gemini_connection",
]
