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

# 기본정보 + 사진 분석 통합 요청 (DB 채우기·브랜드맵 기반용). 챗처럼 상세한 리뷰를 받기 위해 분량을 넉넉히 요청.
PROMPT_TEXT = """**필수: 다음 항목은 절대 비워두지 말고, 각각 2~4문장 이상으로 반드시 작성할 것.** 톤_무드, 촬영_특징, 룩북_촬영_배경_무드, 모델링_포즈_특징, 컬러_팔레트, 디자인_컨셉_분석, 브랜드_평, 이미지_요약, 제품_특징, 모델_특징, 상세_리뷰.

아래 텍스트는 쇼핑몰(29CM 등) 상품 상세 PDF에서 추출한 내용입니다. **이 PDF 하나에 나온 상품에 대해** 아래 모든 항목을 **한 번의 응답에서** 빠짐없이 분석·추출해 주세요. **리뷰/분석 항목은 2~4문장 이상 상세히** 작성해 주세요 (한 줄 요약 금지).

**요청 사항**
- 모든 필드를 가능한 한 채워 주세요. 본문에 직접 없어도 문맥·제목·구성에서 추론 가능하면 기입해 주세요.
- **톤_무드, 촬영_특징, 룩북_촬영_배경_무드, 모델링_포즈_특징, 컬러_팔레트, 디자인_컨셉_분석, 상세_리뷰** 는 반드시 비워두지 말고 2문장 이상으로 채우세요. 값이 정말 없으면 "(문맥에서 추론 불가)" 등 짧은 설명이라도 넣으세요.
- **브랜드맵 지표**(숫자 0~100, 없으면 null): 스타일_축(0=클래식/페미닌, 100=시크·미니멀·스트릿), 프리미엄_축(0=데일리, 100=프리미엄). 대표색: hex(예 #2c2c2c) 또는 색상명(예 BLACK, NAVY) 하나.
- JSON의 키는 반드시 아래 한글 키 그대로 사용하세요: 상품명, 브랜드명, 상세_카테고리명, 의류종류, 가격, 소재, 케어방법, 사이즈, 사이즈_상세, 색상, 이미지_무드, 이미지_톤, 이미지_배경, 사진_구성, 모델_특징, 제품_특징, 브랜드_평, 이미지_요약, 톤_무드, 촬영_특징, 룩북_촬영_배경_무드, 모델링_포즈_특징, 컬러_팔레트, 디자인_컨셉_분석, 상세_리뷰, 리뷰_의견, 스타일_축, 프리미엄_축, 대표색
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

【사진/이미지 분석】 (2~4문장 이상 상세히. 텍스트·문맥에서 추론 가능하면 채우고, 이미지가 없으면 빈 문자열)
- 이미지_무드: 사진 분위기(미니멀, 캐주얼, 럭셔리 등)를 구체적으로
- 이미지_톤: 색감·톤(웜톤, 쿨톤, 무채색 등)과 인상
- 이미지_배경: 배경 색/톤/특징과 연출 의도
- 사진_구성: 구도·구성 특징(전신, 클로즈업, 라이프스타일 등) 상세
- 모델_특징: 모델/착용 연출 특징을 2문장 이상으로
- 제품_특징: 제품의 시각적·디자인 특징을 2문장 이상으로
- 브랜드_평: 사진·텍스트를 종합한 브랜드 인상/포지셔닝을 2~3문장으로
- 이미지_요약: 상품 이미지를 2~3문장으로 설명
- 톤_무드: 톤 & 무드 (전체적인 색감·분위기)
- 촬영_특징: 촬영 방식·각도·조명 등 촬영 특징
- 룩북_촬영_배경_무드: 룩북 촬영의 배경 및 무드
- 모델링_포즈_특징: 모델링 및 포즈의 특징
- 컬러_팔레트: 상품/이미지의 컬러 팔레트
- 디자인_컨셉_분석: 디자인 및 컨셉 분석 (2~4문장)

【상세 리뷰】 (Gemini 챗에서 "이 PDF 분석해줘"라고 했을 때 나오는 수준의 종합 분석)
- 상세_리뷰: 이 상품 PDF에 대한 종합 리뷰를 2~4문단(각 2~4문장)으로 작성. 상품의 특징, 타겟, 무드, 구매 포인트, 이미지/카피 인상 등을 포함.
- 리뷰_의견: 상품에 대한 한두 문장 요약 의견(구매 포인트, 무드, 타겟 등).

【브랜드맵 지표】 (숫자 0~100 또는 null, 대표색은 문자열)
- 스타일_축: 0~100. 0=클래식·페미닌, 100=시크·미니멀·스트릿. 문맥/디자인에서 판단.
- 프리미엄_축: 0~100. 0=데일리/캐주얼, 100=프리미엄/럭셔리. 가격·무드·타겟 기준.
- 대표색: 이 상품 대표 색 1개. hex(예 #1a1a2e) 또는 영문 색상명(예 NAVY, BLACK, BEIGE).

---
텍스트:
"""

PROMPT_IMAGE = """**필수: 톤_무드, 촬영_특징, 룩북_촬영_배경_무드, 모델링_포즈_특징, 컬러_팔레트, 디자인_컨셉_분석, 브랜드_평, 이미지_요약, 상세_리뷰는 절대 비워두지 말고 각각 2~4문장 이상으로 작성.**

위 이미지(들)는 동일 상품 상세 PDF의 페이지입니다. 텍스트에서 추출한 기본 정보에 더해, **사진을 꼼꼼히 분석**해 아래 모든 항목을 **한 번의 응답에서 2~4문장 이상 상세히** 채워 주세요.

**다음 키는 반드시 비워두지 말고 2문장 이상으로 채우세요:** 톤_무드, 촬영_특징, 룩북_촬영_배경_무드, 모델링_포즈_특징, 컬러_팔레트, 디자인_컨셉_분석, 상세_리뷰. 이미지에서 읽을 수 있는 내용으로 구체적으로 작성하세요.

JSON의 키는 반드시 한글 그대로 사용하세요: 상품명, 브랜드명, 상세_카테고리명, 의류종류, 가격, 소재, 케어방법, 사이즈, 사이즈_상세, 색상, 이미지_무드, 이미지_톤, 이미지_배경, 사진_구성, 모델_특징, 제품_특징, 브랜드_평, 이미지_요약, 톤_무드, 촬영_특징, 룩북_촬영_배경_무드, 모델링_포즈_특징, 컬러_팔레트, 디자인_컨셉_분석, 상세_리뷰, 리뷰_의견, 스타일_축, 프리미엄_축, 대표색

【브랜드맵 지표】 스타일_축(0~100), 프리미엄_축(0~100), 대표색(hex 또는 색상명 1개).

【기본 정보】(텍스트에서 추출한 값 유지, 보완 가능하면 보완)
【사진 분석】 (이미지에서 읽을 수 있는 내용을 2~4문장 이상으로 기입)
- 이미지_무드, 이미지_톤, 이미지_배경, 사진_구성, 모델_특징, 제품_특징, 브랜드_평, 이미지_요약, 톤_무드, 촬영_특징, 룩북_촬영_배경_무드, 모델링_포즈_특징, 컬러_팔레트, 디자인_컨셉_분석
【상세 리뷰】 상세_리뷰: 이 상품 PDF 전체(텍스트+이미지)에 대한 종합 리뷰를 2~4문단으로 작성.

다른 설명 없이 JSON 하나만 출력하세요.
"""

# 확장 필드만 2차 요청할 때 쓰는 짧은 프롬프트
SUPPLEMENT_EXTENDED_PROMPT = """아래 내용을 보고 다음 7개 키만 JSON으로 채워 주세요. 각 2문장 이상. 키 이름 정확히: 톤_무드, 촬영_특징, 룩북_촬영_배경_무드, 모델링_포즈_특징, 컬러_팔레트, 디자인_컨셉_분석, 상세_리뷰. JSON만 출력.

---
"""

EXTENDED_KEYS = ("톤_무드", "촬영_특징", "룩북_촬영_배경_무드", "모델링_포즈_특징", "컬러_팔레트", "디자인_컨셉_분석", "상세_리뷰")


def _supplement_extended_fields(
    result: dict[str, Any],
    text: str,
    source_pdf: str,
    image_parts: list[tuple[bytes, str]] | None,
    model_id: str,
    api_key: str,
) -> None:
    """result에 확장 필드가 비어 있으면 2차 API 호출로 채움 (result 수정). 디버그용 _supplement_* 메타 저장."""
    if not result:
        return
    need = [k for k in EXTENDED_KEYS if not (result.get(k) or "").strip()]
    if not need:
        return
    result["_supplement_ran"] = True
    result["_supplement_requested"] = list(need)
    prompt = SUPPLEMENT_EXTENDED_PROMPT + (text or "(텍스트 없음)")[:8000]
    raw: str | None = None
    if image_parts and len(image_parts) > 0:
        try:
            import google.generativeai as genai_legacy
            genai_legacy.configure(api_key=api_key)
            model = genai_legacy.GenerativeModel(model_id)
            contents = []
            for img_bytes, mime in image_parts[:3]:
                contents.append({"inline_data": {"mime_type": mime, "data": base64.standard_b64encode(img_bytes).decode("ascii")}})
            contents.append(prompt)
            response = model.generate_content(contents, generation_config=genai_legacy.types.GenerationConfig(temperature=0.2, max_output_tokens=4096))
            if response and response.text:
                raw = response.text.strip()
        except Exception as e:
            result["_supplement_error"] = str(e)[:300]
            return
    if not raw:
        try:
            raw = _call_google_genai(model_id, [prompt], api_key)
            if raw is None:
                raw = _call_google_generativeai(model_id, [prompt], api_key)
        except Exception as e:
            result["_supplement_error"] = str(e)[:300]
            return
    if not raw:
        result["_supplement_error"] = "2차 API 응답 없음"
        return
    result["_supplement_response_preview"] = (raw[:400] + "…") if len(raw) > 400 else raw
    filled: list[str] = []
    try:
        body = _strip_markdown_json(raw)
        data = json.loads(body)
        for k in EXTENDED_KEYS:
            if (result.get(k) or "").strip():
                continue
            v = data.get(k) or _get_key(data, k)
            if v and str(v).strip():
                result[k] = str(v).strip()
                filled.append(k)
        result["_supplement_filled"] = filled
    except Exception as e:
        result["_supplement_error"] = f"JSON파싱:{e}"[:300]


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


def has_gemini_api_key() -> bool:
    """Gemini API 호출 가능 여부(키 설정 여부). UI 진단용."""
    return _get_api_key() is not None


def _strip_markdown_json(raw: str) -> str:
    raw = raw.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if m:
        return m.group(1).strip()
    return raw


# DB·브랜드맵용 공통 필드 목록 (브랜드맵 지표: 스타일_축, 프리미엄_축, 대표색)
EXTRACT_KEYS = [
    "source_pdf", "상품명", "브랜드명", "상세_카테고리명", "의류종류", "가격", "소재", "케어방법",
    "사이즈", "사이즈_상세", "색상",
    "이미지_무드", "이미지_톤", "이미지_배경", "사진_구성", "모델_특징", "제품_특징", "브랜드_평", "이미지_요약",
    "톤_무드", "촬영_특징", "룩북_촬영_배경_무드", "모델링_포즈_특징", "컬러_팔레트", "디자인_컨셉_분석",
    "상세_리뷰",
    "스타일_축", "프리미엄_축", "대표색",
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
    "tone_mood": "톤_무드", "tone_and_mood": "톤_무드", "톤 & 무드": "톤_무드", "톤  무드": "톤_무드",
    "shooting_feature": "촬영_특징", "photography": "촬영_특징", "촬영 특징": "촬영_특징",
    "lookbook_background_mood": "룩북_촬영_배경_무드", "lookbook_mood": "룩북_촬영_배경_무드",
    "룩북 촬영 배경 무드": "룩북_촬영_배경_무드", "룩북 촬영 배경 및 무드": "룩북_촬영_배경_무드",
    "modeling_pose": "모델링_포즈_특징", "model_pose": "모델링_포즈_특징", "모델링 포즈": "모델링_포즈_특징",
    "모델링 및 포즈 특징": "모델링_포즈_특징",
    "color_palette": "컬러_팔레트", "palette": "컬러_팔레트", "컬러 팔레트": "컬러_팔레트",
    "design_concept": "디자인_컨셉_분석", "design_analysis": "디자인_컨셉_분석", "디자인 컨셉": "디자인_컨셉_분석",
    "디자인 및 컨셉 분석": "디자인_컨셉_분석",
    "detail_review": "상세_리뷰", "comprehensive_review": "상세_리뷰", "종합_리뷰": "상세_리뷰",
    "style_axis": "스타일_축", "스타일축": "스타일_축",
    "premium_axis": "프리미엄_축", "프리미엄축": "프리미엄_축",
    "representative_color": "대표색", "brand_color": "대표색", "대표 컬러": "대표색",
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
    # API가 다른 키 이름으로 보낸 경우: 키를 정규화(공백→_, &→_)해서 비교
    for raw_key, val in data.items():
        if val is None or val == "":
            continue
        if not isinstance(raw_key, str):
            continue
        norm = raw_key.replace(" & ", "_").replace(" ", "_").replace("/", "_").replace("-", "_").strip()
        if norm == ko_key or norm.replace(" ", "") == ko_key.replace(" ", ""):
            return val
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
    out["톤_무드"] = _get_key(data, "톤_무드") or ""
    out["촬영_특징"] = _get_key(data, "촬영_특징") or ""
    out["룩북_촬영_배경_무드"] = _get_key(data, "룩북_촬영_배경_무드") or ""
    out["모델링_포즈_특징"] = _get_key(data, "모델링_포즈_특징") or ""
    out["컬러_팔레트"] = _get_key(data, "컬러_팔레트") or ""
    out["디자인_컨셉_분석"] = _get_key(data, "디자인_컨셉_분석") or ""
    out["상세_리뷰"] = _get_key(data, "상세_리뷰") or ""
    out["리뷰_의견"] = _get_key(data, "리뷰_의견") or ""
    # 브랜드맵 지표: 0~100 (없으면 None)
    style_val = _get_key(data, "스타일_축")
    out["스타일_축"] = _to_int_0_100(style_val)
    premium_val = _get_key(data, "프리미엄_축")
    out["프리미엄_축"] = _to_int_0_100(premium_val)
    out["대표색"] = _normalize_color(_get_key(data, "대표색"))
    return out


def _to_int_0_100(val: Any) -> int | None:
    """0~100 정수로 변환. None/빈 값이면 None."""
    if val is None:
        return None
    try:
        n = int(float(val))
        return max(0, min(100, n)) if n >= 0 else None
    except (TypeError, ValueError):
        return None


def _normalize_color(val: Any) -> str:
    """색상 문자열 반환. hex(#으로 시작) 또는 색상명. 리스트면 첫 항목. 빈 값이면 빈 문자열."""
    if val is None:
        return ""
    if isinstance(val, list):
        val = val[0] if val else None
    if val is None:
        return ""
    s = str(val).strip()
    if not s:
        return ""
    if s.startswith("#") and len(s) in (4, 7, 9):
        return s
    return s


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
                config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=8192),
            )
            if response.text:
                return response.text.strip()
            return None
        except Exception as e:
            last_err = e
            if attempt < 2 and _is_retryable_error(e):
                import time
                delay = (10 * (2 ** attempt))  # 429 시 10초, 20초 대기 후 재시도
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
                    max_output_tokens=8192,
                ),
            )
            if response.text:
                return response.text.strip()
            return None
        except Exception as e:
            last_err = e
            if attempt < 2 and _is_retryable_error(e):
                import time
                delay = (10 * (2 ** attempt))  # 429 시 10초, 20초 대기 후 재시도
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
        meta["_api_request_sent"] = False
        return (None, meta)
    # Gemini 3.0 Pro는 컨텍스트가 넓으므로 텍스트를 더 많이 전달 (빈칸 감소)
    text = (raw_text or "")[:max_text_len]

    contents: list[Any] = []
    prompt_for_json = PROMPT_TEXT + (text or "(텍스트 없음)")

    if image_parts and len(image_parts) > 0:
        meta["_api_request_sent"] = True  # 이 분기에서 실제 요청 시도 (진단용)
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
                        generation_config=genai_legacy.types.GenerationConfig(temperature=0.1, max_output_tokens=8192),
                    )
                    if response and response.text:
                        body = _strip_markdown_json(response.text)
                        data = json.loads(body)
                        result = _normalize_result(data, source_pdf)
                        meta["success"] = True
                        return (result, meta)
                    meta["error"] = meta.get("error") or "Gemini API 응답 없음(이미지)"
                    break
                except Exception as e:
                    last_err = e
                    if attempt < 2 and _is_retryable_error(e):
                        time.sleep(10 * (2 ** attempt))  # 429 시 10초, 20초 대기 후 재시도
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
                result = _normalize_result(data, source_pdf)
                meta["success"] = True
                return (result, meta)
        except Exception as e:
            meta["error"] = meta.get("error") or _format_api_error(e)
        return (None, meta)

    # 텍스트만
    contents = [prompt_for_json]
    meta["_api_request_sent"] = True  # 실제 요청 직전 (진단용)
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
        result = _normalize_result(data, source_pdf)
        meta["success"] = True
        return (result, meta)
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


# 최소 영역( pt² ): 이보다 작은 이미지는 아이콘 등으로 간주하고 제외
# (기존 80*80 ▶ 30*30으로 낮춰 실제 상품 이미지 영역을 더 잘 잡도록 완화)
_MIN_IMAGE_AREA_PT2 = 30 * 30


def _find_main_image_bbox_cv(png_bytes: bytes) -> tuple[int, int, int, int] | None:
    """
    전체 페이지 PNG에서 컴퓨터 비전으로 '주요 이미지 영역' 후보를 찾는다.
    - 가장 큰 외곽 컨투어의 bounding box를 사용
    - 페이지의 15%~95% 사이 면적만 허용 (너무 작거나 거의 전체를 덮는 영역 제외)
    """
    try:
        import cv2  # type: ignore[import]
        import numpy as np  # type: ignore[import]
    except Exception:
        return None
    try:
        nparr = np.frombuffer(png_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        h, w = img.shape[:2]
        if h <= 0 or w <= 0:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        page_area = float(w * h)
        best = None
        best_area = 0.0
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            area = float(cw * ch)
            if area <= 0:
                continue
            ratio = area / page_area
            if ratio < 0.15 or ratio > 0.95:
                continue
            # 가로/세로 비율도 너무 극단적인 경우는 제외
            if cw / w < 0.2 or ch / h < 0.2:
                continue
            if area > best_area:
                best_area = area
                best = (x, y, x + cw, y + ch)
        return best
    except Exception:
        return None


def extract_pdf_image_regions(
    pdf_path: Path,
    out_base_dir: Path,
    slug: str | None = None,
    max_pages: int = 10,
    dpi: int = 150,
) -> list[tuple[Path, str]]:
    """
    PDF 페이지에서 **이미지 영역만** 캡처해 product_images/{slug}/ 에 저장.
    - 대표 이미지: 첫 페이지에서 추출한 첫 번째 큰 이미지 영역 (main_0.png)
    - 상세 이미지: 나머지 페이지·이미지 영역 (detail_0.png, detail_1.png, ...)
    get_image_rects 가 비어 있거나 이미지가 없으면 해당 페이지는 전체 페이지를 한 장으로 저장.
    반환: [(Path, "대표"|"상세"), ...]
    """
    try:
        import fitz
    except ImportError:
        return []
    if slug is None:
        stem = pdf_path.stem
        parent = pdf_path.parent
        parts = list(parent.parts) + [stem]
        slug = "_".join(parts).replace(" ", "_")
    out_dir = out_base_dir / "product_images" / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    result: list[tuple[Path, str]] = []
    main_count = 0
    detail_count = 0
    mat = fitz.Matrix(dpi / 72, dpi / 72)

    try:
        doc = fitz.open(pdf_path)
        for page_no in range(min(max_pages, len(doc))):
            page = doc[page_no]
            images = page.get_images(full=True)
            collected_rects = []
            page_area = abs(page.rect.width * page.rect.height) or 1.0
            for img in images:
                xref = img[0]
                try:
                    rects = page.get_image_rects(xref, transform=False)
                except Exception:
                    rects = []
                for r in rects:
                    rect = r[0] if isinstance(r, tuple) else r
                    if not hasattr(rect, "width") or not hasattr(rect, "height"):
                        continue
                    area = abs(rect.width * rect.height)
                    if area < _MIN_IMAGE_AREA_PT2:
                        continue
                    area_ratio = area / page_area
                    # 너무 작은 아이콘 / 배지는 제외 (페이지의 10% 미만)
                    if area_ratio < 0.10:
                        continue
                    # 가로나 세로가 너무 좁은 바(bar) 형태도 제외
                    w_ratio = abs(rect.width) / (abs(page.rect.width) or 1.0)
                    h_ratio = abs(rect.height) / (abs(page.rect.height) or 1.0)
                    if w_ratio < 0.15 or h_ratio < 0.15:
                        continue
                    collected_rects.append(rect)
            if collected_rects:
                for rect in collected_rects:
                    try:
                        pix = page.get_pixmap(matrix=mat, clip=rect, alpha=False)
                        png_bytes = pix.tobytes("png")
                        if page_no == 0 and main_count == 0:
                            path = out_dir / "main_0.png"
                            path.write_bytes(png_bytes)
                            result.append((path, "대표"))
                            main_count += 1
                        else:
                            path = out_dir / f"detail_{detail_count}.png"
                            path.write_bytes(png_bytes)
                            result.append((path, "상세"))
                            detail_count += 1
                    except Exception:
                        continue
            else:
                # 큰 이미지(rect)를 하나도 못 찾은 경우:
                # - 첫 페이지에 한해서만, 전체 페이지를 CV로 분석해 '주요 이미지 영역'을 찾는다.
                # - 나머지 페이지는 "이미지 없음"으로 간주 (텍스트·배너만 있는 페이지 방지)
                if page_no == 0 and main_count == 0:
                    try:
                        full_pix = page.get_pixmap(matrix=mat, alpha=False)
                        full_png = full_pix.tobytes("png")
                        bbox = _find_main_image_bbox_cv(full_png)
                        if bbox is not None:
                            x1, y1, x2, y2 = bbox
                            # OpenCV 좌표(bbox)를 이용해 이미지를 잘라 저장
                            import cv2  # type: ignore[import]
                            import numpy as np  # type: ignore[import]
                            nparr = np.frombuffer(full_png, np.uint8)
                            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                            if img is not None:
                                h, w = img.shape[:2]
                                x1 = max(0, min(x1, w - 1))
                                x2 = max(1, min(x2, w))
                                y1 = max(0, min(y1, h - 1))
                                y2 = max(1, min(y2, h))
                                crop = img[y1:y2, x1:x2]
                                ok, buf = cv2.imencode(".png", crop)
                                if ok:
                                    png_bytes = buf.tobytes()
                                    path = out_dir / "main_0.png"
                                    path.write_bytes(png_bytes)
                                    result.append((path, "대표"))
                                    main_count += 1
                    except Exception:
                        pass
        doc.close()
    except Exception:
        pass
    return result


def save_pdf_product_images(
    pdf_path: Path,
    out_base_dir: Path,
    max_pages: int = 10,
    dpi: int = 150,
    slug: str | None = None,
) -> list[Path]:
    """
    PDF에서 대표/상세 **이미지 영역만** 캡처해 product_images/{slug}/ 에 저장.
    extract_pdf_image_regions 를 사용하고, 결과가 없을 때만 전체 페이지 fallback.
    반환: 저장된 PNG 파일 Path 리스트 (대표=main_0, 상세=detail_0, ... 또는 page_0, page_1).
    """
    if slug is None:
        stem = pdf_path.stem
        parent = pdf_path.parent
        parts = list(parent.parts) + [stem]
        slug = "_".join(parts).replace(" ", "_")
    out_dir = out_base_dir / "product_images" / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) 이미지 영역 캡처 시도 (실패하더라도 예외는 swallow 하고 전체 페이지 fallback)
    region_result: list[tuple[Path, str]] = []
    try:
        region_result = extract_pdf_image_regions(
            pdf_path, out_base_dir, slug=slug, max_pages=max_pages, dpi=dpi
        )
    except Exception:
        region_result = []
    if region_result:
        return [p for p, _ in region_result]
    # 2) 영역 추출 실패 시: 전체 페이지를 page_0, page_1, ...
    images = pdf_pages_to_images(pdf_path, max_pages=max_pages, dpi=dpi)
    saved: list[Path] = []
    for i, (png_bytes, _) in enumerate(images):
        path = out_dir / f"page_{i}.png"
        path.write_bytes(png_bytes)
        saved.append(path)
    return saved


BRAND_COMPREHENSIVE_PROMPT = """아래는 쇼핑몰(29CM 등) 상품 PDF 분석 결과입니다. **전체 브랜드를 종합 분석**해 주세요.

요청:
1. 브랜드별 포지셔닝·타겟·가격대·무드·디자인 방향을 2~3문장씩 요약
2. 브랜드 간 유사점·차이점 비교
3. 전체 시장/트렌드 관점에서의 종합 분석 (2~4문단)
4. 핵심 인사이트 3~5개 (불릿 포인트)

응답은 **JSON 하나만** 출력하세요. 형식:
{
  "브랜드별_요약": [ { "브랜드명": "...", "포지셔닝": "...", "타겟": "...", "가격대": "...", "무드": "..." } ],
  "비교_분석": "브랜드 간 비교 1~2문단",
  "종합_분석": "전체 시장·트렌드 종합 2~4문단",
  "핵심_인사이트": ["인사이트1", "인사이트2", ...]
}

다른 설명 없이 JSON만 출력하세요.

---
상품 분석 결과:
"""


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


def generate_brand_comprehensive_analysis(
    products: list[dict[str, Any]], model_id: str | None = None
) -> dict[str, Any] | None:
    """
    상품 분석 결과를 바탕으로 AI로 전체 브랜드 종합 분석 JSON 생성.
    """
    api_key = _get_api_key()
    if not api_key or not products:
        return None
    model_id = model_id or os.environ.get("GEMINI_MODEL", "gemini-3-pro-preview")
    lines = []
    # 상품 수가 많아도 브랜드 다양하게 포함: 최대 200건까지 전달 (종합 분석이 소수 브랜드만 나오지 않도록)
    for i, p in enumerate(products[:200], 1):
        brand = p.get("브랜드명") or ""
        name = (p.get("상품명") or "")[:50]
        price = p.get("가격") or "-"
        mood = p.get("이미지_무드") or p.get("이미지_톤") or ""
        brand_eval = (p.get("브랜드_평") or "")[:200]
        design = (p.get("디자인_컨셉_분석") or "")[:150]
        lines.append(f"{i}. [{brand}] {name} | 가격:{price} | 무드:{mood} | 브랜드평:{brand_eval} | 디자인:{design}")
    text = "\n".join(lines)
    prompt = BRAND_COMPREHENSIVE_PROMPT + text
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
        return {"종합_분석": body, "브랜드별_요약": [], "비교_분석": "", "핵심_인사이트": []}
