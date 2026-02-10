"""
PDF 텍스트 추출 및 규칙 기반 상품 정보 파싱.

29CM 상품 상세 PDF에서 상품명·브랜드·가격·소재·케어·사이즈·색상 등을 추출.
(비전 API 없이 현재 가능한 수준)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import pdfplumber
except ImportError:
    pdfplumber = None  # type: ignore


def extract_text_from_pdf(pdf_path: Path) -> str:
    """PDF 전체 페이지 텍스트를 하나의 문자열로 반환. PyMuPDF 우선(이전 성공 경험), 빈 결과 시 pdfplumber 시도."""
    text = ""
    # 1) PyMuPDF(fitz) 우선 — 29CM 등 쇼핑몰 PDF에서 텍스트 추출이 잘 되는 경우가 많음
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        parts = []
        for page in doc:
            parts.append(page.get_text())
        doc.close()
        text = "\n\n".join(p for p in parts if p)
    except Exception:
        text = ""
    # 2) 빈 결과면 pdfplumber 시도
    if not text.strip() and pdfplumber is not None:
        try:
            text_parts = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
            text = "\n\n".join(text_parts)
        except Exception:
            pass
    return text or ""


def _first_match(pattern: re.Pattern[str], text: str, group: int = 1) -> str:
    m = pattern.search(text)
    if m:
        return (m.group(group) if m.lastindex and group <= m.lastindex else m.group(0)).strip()
    return ""


def _all_matches(pattern: re.Pattern[str], text: str) -> list[str]:
    return [m.strip() for m in pattern.findall(text) if m and isinstance(m, str)]


def parse_product_from_text(raw_text: str, source_pdf: str = "") -> dict[str, Any]:
    """
    추출된 PDF 텍스트에서 상품 정보를 규칙 기반으로 파싱.
    반환 dict 키: source_pdf, 상품명, 브랜드명, 상세_카테고리명, 가격, 소재, 케어방법, 사이즈, 색상.
    """
    text = raw_text or ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    result: dict[str, Any] = {
        "source_pdf": source_pdf,
        "상품명": "",
        "브랜드명": "",
        "상세_카테고리명": "",
        "가격": None,
        "소재": "",
        "케어방법": "",
        "사이즈": [],
        "사이즈_상세": "",  # 기장·가슴 등 측정값 포함 전체 표(텍스트)
        "색상": [],
    }

    # 가격: (1) 숫자+쉼표 (121,590원) (2) 쉼표 없이 4자리 이상+원 (9900원~)
    def to_int(s: str) -> int:
        return int(s.replace(",", ""))

    price_candidates = re.findall(r"(\d{1,3}(?:,\d{3})+)\s*원?", text)
    if not price_candidates:
        price_candidates = re.findall(r"(\d{4,})\s*원?", text)
    if price_candidates:
        prices = [to_int(p) for p in price_candidates if to_int(p) >= 1000]
        if prices:
            result["가격"] = prices[0]

    # 소재: COMPOSITION / 원단 / 소재 / 구성 다음 줄 (%, COTTON 등) 또는 해당 키워드 포함 줄
    for sep in ["COMPOSITION", "원단", "소재", "구성"]:
        idx = text.find(sep)
        if idx >= 0:
            after = text[idx + len(sep) : idx + len(sep) + 400]
            for ln in after.splitlines():
                ln = ln.strip()
                if not ln or len(ln) < 2:
                    continue
                if "%" in ln or "COTTON" in ln.upper() or "WOOL" in ln.upper() or "POLY" in ln.upper():
                    result["소재"] = ln[:500]
                    break
            if not result["소재"] and after.strip():
                first_line = after.splitlines()[0].strip() if after.splitlines() else ""
                if 10 <= len(first_line) <= 500:
                    result["소재"] = first_line[:500]
            if result["소재"]:
                break
    if not result["소재"]:
        for line in lines[:50]:
            if any(k in line for k in ["소재", "원단", "구성"]) and 10 <= len(line) <= 400:
                result["소재"] = line[:500]
                break

    # 케어방법: 케어 / 케이어 / CARE / 취급 다음 내용 (최대 8줄)
    for sep in ["케어방법", "케이어", "CARE", "취급", "세탁"]:
        idx = text.find(sep)
        if idx >= 0:
            after = text[idx + len(sep) : idx + len(sep) + 800]
            care_lines = [ln.strip() for ln in after.splitlines() if ln.strip() and len(ln.strip()) > 1][:8]
            result["케어방법"] = " ".join(care_lines)[:500]
            break

    # 사이즈: 라벨(S/M/L/XL, Free, ONE SIZE) + 사이즈_상세(기장·가슴 등 측정 표 전체)
    SIZE_BLOCK_LEN = 550  # SIZE/사이즈 구간 뒤 몇 글자까지 볼지

    def _extract_size_block() -> str:
        for sep in ["SIZE", "사이즈", "치수", "SIZE HELP"]:
            idx = text.upper().find(sep.upper())
            if idx >= 0:
                return text[idx + len(sep) : idx + len(sep) + SIZE_BLOCK_LEN]
        return ""

    size_block = _extract_size_block()

    if size_block:
        result["사이즈_상세"] = size_block.strip()[:600].rstrip()

    # Free / ONE SIZE 먼저 확인
    block_upper = size_block.upper()
    if re.search(r"\bONE\s*SIZE\b", block_upper) or "ONESIZE" in block_upper.replace(" ", ""):
        result["사이즈"] = ["ONE SIZE"]
    elif re.search(r"\bFREE\b", block_upper):
        result["사이즈"] = ["Free"]

    # 1) 같은 줄에 SIZE: S M L 이 있으면 그대로 추출 (HELP 제외)
    if not result["사이즈"]:
        size_pattern = re.compile(r"(?:SIZE|사이즈|치수)[\s:]*([SMLXL\d\s,]+)", re.IGNORECASE)
        size_match = size_pattern.search(text)
        if size_match:
            raw = size_match.group(1).strip()
            if "HELP" not in raw.upper() and len(raw) <= 35:
                tokens = re.findall(r"\b(S|M|L|XL|XXL|\d{2,3})\b", raw, re.IGNORECASE)
                if tokens:
                    result["사이즈"] = list(dict.fromkeys(s.upper() if len(s) <= 3 else s for s in tokens))

    # 2) SIZE/사이즈 블록에서 S M L / S, M, L / 한 줄에 S M L 만 있는 경우
    if not result["사이즈"] and size_block:
        block_match = re.search(r"\b(S)\s*[,/]?\s*(M)\s*[,/]?\s*(L)\b", size_block, re.IGNORECASE)
        if block_match:
            result["사이즈"] = ["S", "M", "L"]
        else:
            for line in size_block.splitlines():
                line = line.strip()
                if re.match(r"^[SMLXL\s,/]+$", line, re.IGNORECASE) and 2 <= len(line) <= 30:
                    tokens = re.findall(r"\b(S|M|L|XL|XXL)\b", line, re.IGNORECASE)
                    if len(tokens) >= 2:
                        result["사이즈"] = list(dict.fromkeys(t.upper() for t in tokens))
                        break

    # 3) 텍스트 전체에서 "S M L" 연속 패턴
    if not result["사이즈"]:
        fallback = re.search(r"\b(S)\s+(M)\s+(L)\b", text, re.IGNORECASE)
        if fallback:
            result["사이즈"] = ["S", "M", "L"]

    # 색상: 29CM은 "color" 다음 줄에 "S M L"(사이즈)이 오는 경우가 많아, 같은 줄 값만 사용
    SIZE_LETTERS = {"S", "M", "L", "XL", "XXL"}

    def _is_size_only(tokens: list[str]) -> bool:
        return bool(tokens) and all(t.upper() in SIZE_LETTERS for t in tokens)

    # 1) "color NAVY" / "색상 네이비" 처럼 같은 줄에 색상이 있는 경우
    for line in lines[:40]:
        line_lower = line.lower().strip()
        for sep in ["color", "색상", "colour"]:
            idx = line_lower.find(sep)
            if idx >= 0:
                after = line[idx + len(sep) :].strip()
                # 콜론/공백 제거 후 첫 단어(들)
                after = re.sub(r"^[\s:]+", "", after)
                if after and len(after) <= 80:
                    tokens = [c.strip() for c in re.split(r"[\s,/]+", after) if c.strip()]
                    # S/M/L/XL/XXL 은 사이즈이므로 색상에서 제외
                    color_tokens = [t for t in tokens if t.upper() not in SIZE_LETTERS]
                    if color_tokens:
                        result["색상"] = color_tokens[:5]
                        break
            if result["색상"]:
                break
        if result["색상"]:
            break

    # 2) 없으면 기존 패턴(다음 줄까지) 시도하되, S/M/L만 있으면 버림
    if not result["색상"]:
        color_pattern = re.compile(r"(?:color|색상|COLOR)[\s:]*([A-Za-z가-힣\s,]+?)(?:\n|$|가격|원)", re.IGNORECASE)
        color_match = color_pattern.search(text)
        if color_match:
            raw = color_match.group(1).strip()
            if raw and len(raw) < 100:
                tokens = [c.strip() for c in re.split(r"[\s,/]+", raw) if c.strip()]
                color_tokens = [t for t in tokens if t.upper() not in SIZE_LETTERS]
                if color_tokens:
                    result["색상"] = color_tokens[:5]

    # 3) 여전히 없으면 상품명 괄호 안에서 추출: (NAVY), (BLACK) 등
    if not result["색상"]:
        paren = re.findall(r"\(([A-Za-z가-힣\s]+)\)", text)
        for p in paren:
            p = p.strip()
            if 2 <= len(p) <= 30 and p.upper() not in SIZE_LETTERS and " " not in p:
                result["색상"] = [p]
                break

    # 상품명·브랜드: 상단 라인에서 추론 (영문 대문자 제목 + 괄호 안 색상 등)
    # 29CM 스타일: "브랜드명" 또는 "상품명 (COLOR)" 형태
    for i, line in enumerate(lines[:30]):
        if len(line) < 3:
            continue
        # 괄호 안 색상이 있는 줄 → 상품명 후보
        if "(" in line and ")" in line and re.search(r"\([A-Za-z가-힣\s]+\)", line):
            if not result["상품명"] and 10 <= len(line) <= 200:
                result["상품명"] = line[:300]
        # 대문자만 있는 짧은 줄 → 브랜드 후보 (착용/예약/PICK 등 제외)
        if line.isupper() and 2 <= len(line) <= 50 and not result["브랜드명"]:
            if not re.match(r"^\d+", line):
                result["브랜드명"] = line[:100]
        # [브랜드명] 상품명 형태 — [고윤정 착용], [예약], [PICK] 등은 브랜드로 쓰지 않음
        bracket = re.match(r"\[([^\]]+)\]\s*(.+)", line)
        if bracket and not result["브랜드명"]:
            label = bracket.group(1).strip()
            if "착용" not in label and "예약" not in label and "PICK" not in label and len(label) <= 40:
                result["브랜드명"] = label[:100]
            if len(bracket.group(2)) > 5:
                result["상품명"] = (result["상품명"] or bracket.group(2).strip())[:300]

    # 상품명: 첫 번째로 긴 유의미한 줄 (15~250자)
    if not result["상품명"]:
        for line in lines[:25]:
            if 15 <= len(line) <= 250 and not line.isdigit():
                result["상품명"] = line[:300]
                break
    # 그다음: 5자 이상인 첫 줄 (제목/상품명 후보)
    if not result["상품명"]:
        for line in lines[:30]:
            line = line.strip()
            if len(line) >= 5 and not line.isdigit() and not re.match(r"^\d[\d\s,\.]+$", line):
                result["상품명"] = line[:300]
                break

    # Fallback: 텍스트가 비었을 때만 파일명으로 상품명 채움 (텍스트가 있으면 규칙으로만 채움)
    if not result["상품명"] and source_pdf and len((raw_text or "").strip()) < 50:
        result["상품명"] = Path(source_pdf).name.replace(".pdf", "") or source_pdf

    return result


def analyze_pdf(
    pdf_path: Path,
    base_dir: Path | None = None,
    use_llm: bool = True,
    use_gemini: bool = False,
    use_gemini_vision: bool = False,
    gemini_model: str | None = None,
) -> dict[str, Any]:
    """
    PDF 파일 하나에 대해 텍스트 추출 + 파싱 후 결과 dict 반환.
    - use_gemini=True: GEMINI_API_KEY 있으면 Gemini로 기본 데이터 추출.
    - gemini_model: 사용할 모델 ID (예: gemini-3-pro-preview, gemini-2.0-flash). None이면 GEMINI_MODEL 또는 기본값.
    - use_gemini_vision=True: PDF 페이지 이미지를 Gemini에 보내 이미지 분석(무드·촬영·배경)까지 수행.
    - use_llm=True: OPENAI_API_KEY 있으면 OpenAI LLM 추출 시도.
    우선순위: Gemini(텍스트+이미지) > Gemini(텍스트) > OpenAI LLM > 규칙 기반.
    """
    try:
        text = extract_text_from_pdf(pdf_path)
    except Exception:
        text = ""
    try:
        source = (
            str(pdf_path.relative_to(base_dir)).replace("\\", "/")
            if base_dir and base_dir in pdf_path.parents
            else pdf_path.name
        )
    except Exception:
        source = pdf_path.name

    last_gemini_meta: dict[str, Any] = {}

    def _make_rule_based_result() -> dict[str, Any]:
        r = parse_product_from_text(text, source_pdf=source)
        if "/" in source:
            r["상세_카테고리명"] = r.get("상세_카테고리명") or source.split("/")[0]
        for key in (
            "의류종류", "이미지_무드", "이미지_톤", "이미지_촬영", "이미지_배경", "이미지_요약",
            "사진_구성", "모델_특징", "제품_특징", "브랜드_평",
            "톤_무드", "촬영_특징", "룩북_촬영_배경_무드", "모델링_포즈_특징", "컬러_팔레트", "디자인_컨셉_분석", "상세_리뷰", "리뷰_의견",
            "대표색",
        ):
            r.setdefault(key, "")
        for key in ("스타일_축", "프리미엄_축"):
            r.setdefault(key, None)
        r["_analysis_engine"] = "rule_based"
        r["_analysis_model"] = ""
        r["_analysis_error"] = last_gemini_meta.get("error") or ""
        return r

    try:
        # 1) Gemini (이미지 포함)
        if use_gemini and use_gemini_vision:
            try:
                from analysis.gemini_extract import extract_product_with_gemini, pdf_pages_to_images
                image_parts = pdf_pages_to_images(pdf_path, max_pages=3)
                result, meta = extract_product_with_gemini(
                    text, source_pdf=source, image_parts=image_parts or None, model_id=gemini_model
                )
                last_gemini_meta = meta
                if result:
                    if "/" in source:
                        result["상세_카테고리명"] = result.get("상세_카테고리명") or source.split("/")[0]
                    result["_analysis_engine"] = "gemini"
                    result["_analysis_model"] = meta.get("model_id", "")
                    result["_analysis_error"] = meta.get("error") or ""
                    result["_api_request_sent"] = meta.get("_api_request_sent", True)
                    return result
            except Exception as e:
                last_gemini_meta = {"model_id": "", "success": False, "error": str(e)[:200]}

        # 2) Gemini (텍스트만)
        if use_gemini:
            try:
                from analysis.gemini_extract import extract_product_with_gemini
                result, meta = extract_product_with_gemini(text, source_pdf=source, model_id=gemini_model)
                last_gemini_meta = meta
                if result:
                    if "/" in source:
                        result["상세_카테고리명"] = result.get("상세_카테고리명") or source.split("/")[0]
                    result["_analysis_engine"] = "gemini"
                    result["_analysis_model"] = meta.get("model_id", "")
                    result["_analysis_error"] = meta.get("error") or ""
                    result["_api_request_sent"] = meta.get("_api_request_sent", True)
                    return result
            except Exception as e:
                last_gemini_meta = {"model_id": "", "success": False, "error": str(e)[:200]}

        # 3) OpenAI LLM
        if use_llm:
            try:
                from analysis.llm_extract import extract_product_with_llm
                result = extract_product_with_llm(text, source_pdf=source)
                if result:
                    if "/" in source:
                        result["상세_카테고리명"] = result.get("상세_카테고리명") or source.split("/")[0]
                    result["_analysis_engine"] = "openai"
                    result["_analysis_model"] = "openai"
                    result["_analysis_error"] = ""
                    return result
            except Exception:
                pass

        return _make_rule_based_result()
    except Exception:
        return _make_rule_based_result()
