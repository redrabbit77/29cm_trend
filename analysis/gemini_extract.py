"""
Gemini 3.0 Pro API를 이용한 상품 상세정보 추출 (기본 데이터 + 이미지 분석).

PDF에서 추출한 텍스트와(선택) PDF 페이지 이미지를 Gemini에 보내
상품명·브랜드·가격·소재·사이즈·색상·이미지_분석(무드·촬영·배경 등)을 JSON으로 받음.
GEMINI_API_KEY 또는 GOOGLE_API_KEY가 설정되어 있으면 사용.
"""
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

# 기본정보 + 사진 분석 통합 요청 (DB 채우기·브랜드맵 기반용)
PROMPT_TEXT = """아래 텍스트는 쇼핑몰(29CM 등) 상품 상세 PDF에서 추출한 내용입니다. **이 PDF 하나에 나온 상품에 대해** 아래 모든 항목을 빠짐없이 분석·추출해 주세요.

**요청 사항**
- 모든 필드를 가능한 한 채워 주세요. 본문에 직접 없어도 문맥·제목·구성에서 추론 가능하면 기입해 주세요.
- JSON의 키는 반드시 아래 한글 키 그대로 사용하세요: 상품명, 브랜드명, 상세_카테고리명, 의류종류, 가격, 소재, 케어방법, 사이즈, 사이즈_상세, 색상, 이미지_무드, 이미지_톤, 이미지_배경, 사진_구성, 모델_특징, 제품_특징, 브랜드_평, 이미지_요약
- 다른 설명 없이 JSON 객체 하나만 출력하세요.

【기본 정보】
- 상품명: 제품명(전체)
- 브랜드명: 브랜드 이름
- 상세_카테고리명: 카테고리(예: 여성_의류, 남성_슈즈)
- 의류종류: 의류/가방/슈즈 등 세부 종류
- 가격: 숫자만(원 단위, 없으면 null)
- 소재: 원단/소재 설명(전체)
- 케어방법: 세탁·취급 방법(전체)
- 사이즈: 배열. 예: ["S","M","L"] 또는 ["Free"]
- 사이즈_상세: 기장·가슴 등 측정값이 있는 사이즈 표 텍스트 전체
- 색상: 배열. 예: ["NAVY","BLACK"]

【사진/이미지 분석】 (텍스트·문맥에서 추론 가능하면 채우고, 이미지가 없으면 빈 문자열)
- 이미지_무드: 사진 분위기(미니멀, 캐주얼, 럭셔리 등)
- 이미지_톤: 색감·톤(웜톤, 쿨톤, 무채색 등)
- 이미지_배경: 배경 색/톤/특징
- 사진_구성: 구도·구성 특징(전신, 클로즈업, 라이프스타일 등)
- 모델_특징: 모델/착용 연출 특징
- 제품_특징: 제품의 시각적·디자인 특징
- 브랜드_평: 사진·텍스트를 종합한 브랜드 인상/포지셔닝 한 줄
- 이미지_요약: 상품 이미지 한 줄 설명

---
텍스트:
"""

PROMPT_IMAGE = """위 이미지(들)는 동일 상품 상세 PDF의 페이지입니다. 텍스트에서 추출한 기본 정보에 더해, **사진을 꼼꼼히 분석**해 아래 모든 항목을 가능한 한 채워 주세요.

JSON의 키는 반드시 한글 그대로 사용하세요: 상품명, 브랜드명, 상세_카테고리명, 의류종류, 가격, 소재, 케어방법, 사이즈, 사이즈_상세, 색상, 이미지_무드, 이미지_톤, 이미지_배경, 사진_구성, 모델_특징, 제품_특징, 브랜드_평, 이미지_요약

【기본 정보】(텍스트에서 추출한 값 유지, 보완 가능하면 보완)
【사진 분석】 (이미지에서 읽을 수 있는 내용 모두 기입)
- 이미지_무드, 이미지_톤, 이미지_배경, 사진_구성, 모델_특징, 제품_특징, 브랜드_평, 이미지_요약

다른 설명 없이 JSON 하나만 출력하세요.
"""


def _get_api_key() -> str | None:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key and key.strip():
        return key.strip()
    # .env가 os.environ에 로드되지 않은 경우(CLI/다른 진입점) 폴백
    try:
        from dotenv import load_dotenv
        _root = Path(__file__).resolve().parent.parent
        load_dotenv(_root / ".env")
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        return key.strip() if key and key.strip() else None
    except Exception:
        return None


def _strip_markdown_json(raw: str) -> str:
    raw = raw.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if m:
        return m.group(1).strip()
    return raw


# DB·브랜드맵용 공통 필드 목록
EXTRACT_KEYS = [
    "source_pdf", "상품명", "브랜드명", "상세_카테고리명", "의류종류", "가격", "소재", "케어방법",
    "사이즈", "사이즈_상세", "색상",
    "이미지_무드", "이미지_톤", "이미지_배경", "사진_구성", "모델_특징", "제품_특징", "브랜드_평", "이미지_요약",
]


# Gemini가 영어 키로 반환할 때 매핑
_KEY_ALIASES: dict[str, str] = {
    "product_name": "상품명", "name": "상품명", "title": "상품명",
    "brand": "브랜드명", "brand_name": "브랜드명",
    "category": "상세_카테고리명", "category_name": "상세_카테고리명",
    "product_type": "의류종류", "type": "의류종류",
    "price": "가격",
    "material": "소재", "materials": "소재", "composition": "소재",
    "care": "케어방법", "care_instructions": "케어방법",
    "sizes": "사이즈", "size": "사이즈",
    "size_detail": "사이즈_상세", "size_details": "사이즈_상세",
    "colors": "색상", "color": "색상",
    "image_mood": "이미지_무드", "mood": "이미지_무드",
    "image_tone": "이미지_톤", "tone": "이미지_톤",
    "image_background": "이미지_배경", "background": "이미지_배경",
    "photo_composition": "사진_구성", "composition_photo": "사진_구성",
    "model_feature": "모델_특징", "model": "모델_특징",
    "product_feature": "제품_특징", "product_features": "제품_특징",
    "brand_eval": "브랜드_평", "brand_evaluation": "브랜드_평",
    "image_summary": "이미지_요약", "summary": "이미지_요약",
}


def _get_key(data: dict[str, Any], ko_key: str) -> Any:
    """한글 키 또는 영어 별칭으로 값 조회."""
    v = data.get(ko_key)
    if v is not None and v != "":
        return v
    for en_key, k in _KEY_ALIASES.items():
        if k == ko_key:
            v = data.get(en_key)
            if v is not None and v != "":
                return v
    return None


def _normalize_result(data: dict[str, Any], source_pdf: str) -> dict[str, Any]:
    """LLM/Gemini 응답을 공통 스키마로 정규화 (DB 채우기·브랜드맵용)."""
    out: dict[str, Any] = {"source_pdf": source_pdf}
    out["상품명"] = _get_key(data, "상품명") or ""
    out["브랜드명"] = _get_key(data, "브랜드명") or ""
    out["상세_카테고리명"] = _get_key(data, "상세_카테고리명") or ""
    out["의류종류"] = _get_key(data, "의류종류") or ""
    out["가격"] = _get_key(data, "가격")
    out["소재"] = _get_key(data, "소재") or ""
    out["케어방법"] = _get_key(data, "케어방법") or ""
    sz = _get_key(data, "사이즈")
    out["사이즈"] = sz if isinstance(sz, list) else []
    out["사이즈_상세"] = _get_key(data, "사이즈_상세") or ""
    col = _get_key(data, "색상")
    out["색상"] = col if isinstance(col, list) else []
    out["이미지_무드"] = _get_key(data, "이미지_무드") or ""
    out["이미지_톤"] = _get_key(data, "이미지_톤") or ""
    out["이미지_촬영"] = _get_key(data, "이미지_촬영") or ""  # 하위 호환
    out["이미지_배경"] = _get_key(data, "이미지_배경") or ""
    out["사진_구성"] = _get_key(data, "사진_구성") or ""
    out["모델_특징"] = _get_key(data, "모델_특징") or ""
    out["제품_특징"] = _get_key(data, "제품_특징") or ""
    out["브랜드_평"] = _get_key(data, "브랜드_평") or ""
    out["이미지_요약"] = _get_key(data, "이미지_요약") or ""
    return out


def _format_api_error(e: Exception) -> str:
    """Gemini 지원 문의용: 예외 타입·HTTP코드·메시지를 포맷 (지원 문의 시 복사용)."""
    parts = [type(e).__name__]
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    if code is not None:
        parts.append(f"HTTP {code}")
    msg = str(e).strip()
    if msg:
        parts.append(msg)
    reason = getattr(e, "reason", None)
    if reason and str(reason) not in msg:
        parts.append(f"reason={reason}")
    return " | ".join(str(p) for p in parts if p is not None)[:500]


def _is_retryable_error(e: Exception) -> bool:
    """429 Too Many Requests / 503 Service Unavailable 등 재시도 가능한 오류인지."""
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    if code in (429, 503):
        return True
    msg = (str(e) or "").lower()
    return "429" in msg or "503" in msg or "too many" in msg or "service unavailable" in msg or "resourceexhausted" in msg


def _call_google_genai(
    model_id: str,
    contents: list[Any],
    api_key: str,
) -> str | None:
    """google-genai (신규 SDK) 사용. 429/503 시 백오프 재시도(최대 3회)."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None
    client = genai.Client(api_key=api_key)
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=contents,
                config=types.GenerateContentConfig(temperature=0.1),
            )
            if response.text:
                return response.text.strip()
            return None
        except Exception as e:
            last_err = e
            if attempt < 2 and _is_retryable_error(e):
                import time
                delay = (5 * (2 ** attempt))  # 5, 10초
                time.sleep(delay)
                continue
            raise
    if last_err:
        raise last_err
    return None


def _call_google_generativeai(
    model_id: str,
    contents: list[Any],
    api_key: str,
) -> str | None:
    """google-generativeai (레거시 SDK) 사용. 429/503 시 백오프 재시도(최대 3회)."""
    try:
        import google.generativeai as genai
    except ImportError:
        return None
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_id)
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            response = model.generate_content(
                contents,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                ),
            )
            if response.text:
                return response.text.strip()
            return None
        except Exception as e:
            last_err = e
            if attempt < 2 and _is_retryable_error(e):
                import time
                delay = (5 * (2 ** attempt))  # 5, 10초
                time.sleep(delay)
                continue
            raise
    if last_err:
        raise last_err
    return None


def extract_product_with_gemini(
    raw_text: str,
    source_pdf: str = "",
    image_parts: list[tuple[bytes, str]] | None = None,
    max_text_len: int = 15000,
    model_id: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """
    Gemini 3.0 Pro(또는 지정 모델)로 상품 정보 추출.
    반환: (결과 dict 또는 None, 메타 {"model_id", "success", "error"})
    - success=True 이고 결과가 있으면 실제 API 호출 성공.
    - success=False 이면 error에 사유(API 키 없음, 호출 실패, JSON 파싱 실패 등).
    """
    model_id = model_id or os.environ.get("GEMINI_MODEL", "gemini-3-pro-preview")
    meta: dict[str, Any] = {"model_id": model_id, "success": False, "error": None}

    api_key = _get_api_key()
    if not api_key:
        meta["error"] = "GEMINI_API_KEY(또는 GOOGLE_API_KEY)가 설정되지 않았습니다."
        return (None, meta)
    # Gemini 3.0 Pro는 컨텍스트가 넓으므로 텍스트를 더 많이 전달 (빈칸 감소)
    text = (raw_text or "")[:max_text_len]

    contents: list[Any] = []
    prompt_for_json = PROMPT_TEXT + (text or "(텍스트 없음)")

    if image_parts and len(image_parts) > 0:
        # 멀티모달: 이미지 + 텍스트. 연결 테스트와 동일한 레거시 SDK를 먼저 사용 (3.0 Flash 등 호환).
        full_prompt = prompt_for_json + "\n\n" + PROMPT_IMAGE
        legacy_contents: list[Any] = []
        for img_bytes, mime in image_parts[:5]:
            legacy_contents.append({
                "inline_data": {
                    "mime_type": mime,
                    "data": base64.standard_b64encode(img_bytes).decode("ascii"),
                }
            })
        try:
            import time
            import google.generativeai as genai_legacy
            genai_legacy.configure(api_key=api_key)
            model = genai_legacy.GenerativeModel(model_id)
            last_err: Exception | None = None
            for attempt in range(3):
                try:
                    response = model.generate_content(
                        legacy_contents + [full_prompt],
                        generation_config=genai_legacy.types.GenerationConfig(temperature=0.1),
                    )
                    if response and response.text:
                        body = _strip_markdown_json(response.text)
                        data = json.loads(body)
                        meta["success"] = True
                        return (_normalize_result(data, source_pdf), meta)
                    meta["error"] = meta.get("error") or "Gemini API 응답 없음(이미지)"
                    break
                except Exception as e:
                    last_err = e
                    if attempt < 2 and _is_retryable_error(e):
                        time.sleep(5 * (2 ** attempt))  # 5, 10초
                        continue
                    meta["error"] = _format_api_error(e)
                    break
            if last_err and not meta.get("error"):
                meta["error"] = _format_api_error(last_err)
        except Exception as e:
            meta["error"] = _format_api_error(e)

        # 레거시 실패 시 신규 SDK (google-genai)로 재시도
        try:
            from google import genai as genai_new
            from google.genai import types as types_new
            new_contents: list[Any] = []
            for img_bytes, mime in image_parts[:5]:
                new_contents.append(types_new.Part.from_bytes(data=img_bytes, mime_type=mime))
            new_contents.append(full_prompt)
            raw = _call_google_genai(model_id, new_contents, api_key)
            if raw:
                body = _strip_markdown_json(raw)
                data = json.loads(body)
                meta["success"] = True
                return (_normalize_result(data, source_pdf), meta)
        except Exception as e:
            meta["error"] = meta.get("error") or _format_api_error(e)
        return (None, meta)

    # 텍스트만
    contents = [prompt_for_json]
    try:
        raw = _call_google_genai(model_id, contents, api_key)
        if raw is None:
            raw = _call_google_generativeai(model_id, contents, api_key)
    except Exception as e:
        meta["error"] = _format_api_error(e)
        return (None, meta)
    if not raw:
        meta["error"] = "Gemini API 응답 없음(모델/키/네트워크 확인)"
        return (None, meta)
    try:
        body = _strip_markdown_json(raw)
        data = json.loads(body)
        meta["success"] = True
        return (_normalize_result(data, source_pdf), meta)
    except json.JSONDecodeError as e:
        meta["error"] = f"JSON 파싱 실패: {e}"
        return (None, meta)


def pdf_pages_to_images(pdf_path: Path, max_pages: int = 3, dpi: int = 150) -> list[tuple[bytes, str]]:
    """PDF 처음 max_pages 페이지를 PNG 바이트 리스트로 반환. PyMuPDF 사용."""
    result: list[tuple[bytes, str]] = []
    try:
        import fitz
    except ImportError:
        return result
    try:
        doc = fitz.open(pdf_path)
        for i in range(min(max_pages, len(doc))):
            page = doc[i]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            png_bytes = pix.tobytes("png")
            result.append((png_bytes, "image/png"))
        doc.close()
    except Exception:
        pass
    return result


def save_pdf_product_images(
    pdf_path: Path,
    out_base_dir: Path,
    max_pages: int = 10,
    dpi: int = 150,
) -> list[Path]:
    """
    PDF 페이지를 대표/상세 이미지로 스크랩해 product_images/{slug}/ 에 저장.
    slug = source_pdf 경로에서 .pdf 제거 후 경로 구분자를 _ 로 치환.
    반환: 저장된 PNG 파일 Path 리스트 (대표=첫 페이지, 나머지=상세).
    """
    # slug: 경로 안전한 폴더명 (예: 여성_의류_01_3599047)
    stem = pdf_path.stem
    parent = pdf_path.parent
    parts = list(parent.parts) + [stem]
    slug = "_".join(parts).replace(" ", "_")
    out_dir = out_base_dir / "product_images" / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    images = pdf_pages_to_images(pdf_path, max_pages=max_pages, dpi=dpi)
    saved: list[Path] = []
    for i, (png_bytes, _) in enumerate(images):
        path = out_dir / f"page_{i}.png"
        path.write_bytes(png_bytes)
        saved.append(path)
    return saved


BRAND_MAP_PROMPT = """아래는 쇼핑몰 상품 PDF 분석 결과(여러 상품)입니다. 이 결과를 기반으로 **브랜드 맵**을 작성해 주세요.

요청:
1. 브랜드별로 그룹화해, 각 브랜드의 포지셔닝·무드·타겟·가격대·사진 스타일 등을 요약해 주세요.
2. 브랜드 간 비교(유사점·차이점)를 짧게 정리해 주세요.
3. 전체를 요약한 "브랜드 맵" 설명(텍스트 또는 구조화된 요약)을 주세요.

응답은 반드시 JSON 하나만 출력하세요. 형식 예시:
{
  "브랜드_요약": [
    { "브랜드명": "...", "포지셔닝": "...", "무드": "...", "가격대": "...", "사진_스타일": "..." }
  ],
  "비교_요약": "브랜드 간 비교 한 줄 요약",
  "브랜드_맵_설명": "전체 브랜드 맵을 설명하는 문단"
}

다른 설명 없이 JSON만 출력하세요.

---
상품 분석 결과:
"""


def test_gemini_connection(model_id: str | None = None) -> tuple[bool, str, str]:
    """
    Gemini API 연결 테스트(1회 호출). Gemini 지원 문의 시 에러 코드 확인용.
    반환: (성공 여부, 요약 메시지, 상세 메시지 또는 에러 코드/메시지)
    """
    api_key = _get_api_key()
    if not api_key:
        return (False, "API 키 없음", "GEMINI_API_KEY(또는 GOOGLE_API_KEY)를 .env에 설정하세요.")
    model_id = model_id or os.environ.get("GEMINI_MODEL", "gemini-3-pro-preview")
    contents = ["Reply with only the word OK."]
    try:
        raw = _call_google_genai(model_id, contents, api_key)
        if raw is None:
            raw = _call_google_generativeai(model_id, contents, api_key)
    except Exception as e:
        detail = _format_api_error(e)
        return (False, "연결 실패", f"모델: {model_id}\n에러: {detail}")
    if not raw:
        return (False, "연결 실패", f"모델: {model_id}\n에러: API 응답 없음")
    return (True, "연결 성공", f"모델: {model_id}\n응답: {raw.strip()[:200]}")


def generate_brand_map(products: list[dict[str, Any]], model_id: str | None = None) -> dict[str, Any] | None:
    """
    상품 분석 결과 목록을 Gemini에 보내 브랜드 맵(브랜드별 요약·비교·맵 설명) JSON 생성.
    products: extract_product_with_gemini / analyze_pdf 결과 리스트.
    """
    api_key = _get_api_key()
    if not api_key or not products:
        return None
    model_id = model_id or os.environ.get("GEMINI_MODEL", "gemini-3-pro-preview")
    # 상품 요약 텍스트 (토큰 절약)
    lines = []
    for i, p in enumerate(products[:100], 1):
        brand = p.get("브랜드명") or ""
        name = (p.get("상품명") or "")[:60]
        price = p.get("가격") or "-"
        mood = p.get("이미지_무드") or p.get("이미지_톤") or ""
        brand_eval = p.get("브랜드_평") or ""
        lines.append(f"{i}. [{brand}] {name} | 가격:{price} | 무드/톤:{mood} | 브랜드평:{brand_eval}")
    text = "\n".join(lines)
    prompt = BRAND_MAP_PROMPT + text
    try:
        raw = _call_google_genai(model_id, [prompt], api_key)
        if raw is None:
            raw = _call_google_generativeai(model_id, [prompt], api_key)
    except Exception:
        return None
    if not raw:
        return None
    body = _strip_markdown_json(raw)
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"브랜드_맵_설명": body, "브랜드_요약": [], "비교_요약": ""}
