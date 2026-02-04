"""
LLM API를 이용한 상품 상세정보 추출.

PDF에서 추출한 텍스트를 LLM에 넘겨 JSON 형태로 상품명·브랜드·가격·소재·사이즈·색상 등을 받음.
OPENAI_API_KEY가 설정되어 있으면 사용. 실패 시 None 반환 → 규칙 기반 폴백.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

PROMPT = """아래는 29CM 등 쇼핑몰 상품 상세 페이지에서 추출한 텍스트입니다.
이 텍스트에서 다음 필드를 추출해 JSON 객체 하나만 반환해 주세요. 다른 설명 없이 JSON만 출력하세요.

필드:
- 상품명: 상품 제목
- 브랜드명: 브랜드 이름
- 상세_카테고리명: 카테고리(없으면 빈 문자열)
- 가격: 숫자만(원 단위, 없으면 null)
- 소재: 원단/소재 설명
- 케어방법: 세탁·취급 방법
- 사이즈: 배열. 예: ["S","M","L"] 또는 ["Free"] 또는 ["ONE SIZE"]
- 사이즈_상세: 기장·가슴·어깨 등 측정값이 있는 사이즈 표 전체 텍스트(없으면 빈 문자열)
- 색상: 배열. 예: ["NAVY","BLACK"]

---
텍스트:
"""
# 토큰 제한 고려해 텍스트는 호출부에서 잘라서 전달 (예: 6000자)


def _strip_markdown_json(raw: str) -> str:
    """응답에서 ```json ... ``` 또는 ``` ... ``` 블록만 추출."""
    raw = raw.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if m:
        return m.group(1).strip()
    return raw


def extract_product_with_llm(raw_text: str, source_pdf: str = "", max_text_len: int = 5500) -> dict[str, Any] | None:
    """
    PDF 텍스트를 LLM에 보내 상품 정보 JSON을 받음.
    OPENAI_API_KEY가 없거나 API 호출 실패 시 None 반환.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not api_key.strip():
        return None

    try:
        import openai
    except ImportError:
        return None

    text = (raw_text or "")[:max_text_len]
    if not text.strip():
        return None

    prompt = PROMPT + text

    try:
        client = openai.OpenAI(api_key=api_key.strip())
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        content = (resp.choices[0].message.content or "").strip()
        if not content:
            return None
        body = _strip_markdown_json(content)
        data = json.loads(body)
    except Exception:
        return None

    # 스키마 맞추기: 필수 키가 있으면 반환
    result: dict[str, Any] = {
        "source_pdf": source_pdf,
        "상품명": data.get("상품명") or "",
        "브랜드명": data.get("브랜드명") or "",
        "상세_카테고리명": data.get("상세_카테고리명") or "",
        "가격": data.get("가격"),
        "소재": data.get("소재") or "",
        "케어방법": data.get("케어방법") or "",
        "사이즈": data.get("사이즈") if isinstance(data.get("사이즈"), list) else [],
        "사이즈_상세": data.get("사이즈_상세") or "",
        "색상": data.get("색상") if isinstance(data.get("색상"), list) else [],
    }
    return result
