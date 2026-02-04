"""
PDF 상품 리뷰/편집 페이지: 대시보드(아이템 리스트) → 클릭 시 상세 리뷰/편집.
상세에서 '편집' 버튼으로 편집 모드 진입, '저장'으로 반영.
"""
from pathlib import Path
import json
import sys

import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

OUTPUT_DIR = _PROJECT_ROOT / "data" / "pdf_analysis"
JSON_PATH = OUTPUT_DIR / "pdf_products.json"
PDF_BASE_PATH_FILE = _PROJECT_ROOT / "data" / "pdf_base_path.txt"


def _get_pdf_base() -> Path:
    """수집 시 지정한 PDF 저장 경로. 없으면 프로젝트/pdfs."""
    if PDF_BASE_PATH_FILE.exists():
        try:
            raw = PDF_BASE_PATH_FILE.read_text(encoding="utf-8").strip()
            if raw:
                p = Path(raw)
                if p.is_absolute():
                    return p
                return (_PROJECT_ROOT / p).resolve()
        except Exception:
            pass
    return (_PROJECT_ROOT / "pdfs").resolve()

EDIT_KEYS = [
    "상품명", "브랜드명", "상세_카테고리명", "의류종류", "가격", "소재", "케어방법",
    "사이즈_상세",
    "이미지_무드", "이미지_톤", "이미지_배경", "사진_구성", "모델_특징", "제품_특징", "브랜드_평", "이미지_요약",
    "리뷰_의견",
]
ARRAY_KEYS = ("사이즈", "색상")


def _slug_from_source(source_pdf: str) -> str:
    p = Path(source_pdf)
    parts = list(p.parent.parts) + [p.stem]
    return "_".join(parts).replace(" ", "_")


def _display_value(item: dict, key: str, fallback: str = "-") -> str:
    """표시용 값. 비어 있으면 fallback. 상품명은 source_pdf 파일명으로 채움."""
    val = item.get(key)
    if val is not None and val != "" and (not isinstance(val, list) or val):
        if isinstance(val, list):
            return ", ".join(str(x) for x in val)
        return str(val)
    if key == "상품명" and item.get("source_pdf"):
        return Path(item["source_pdf"]).stem or item["source_pdf"]
    return fallback


def _ensure_product_images(pdf_path: Path, out_base_dir: Path) -> list[Path]:
    from analysis.gemini_extract import save_pdf_product_images
    pdf_base = _get_pdf_base()
    slug = _slug_from_source(pdf_path.relative_to(pdf_base).as_posix())
    img_dir = out_base_dir / "product_images" / slug
    if img_dir.exists():
        saved = sorted(img_dir.glob("page_*.png"))
        if saved:
            return saved
    saved = save_pdf_product_images(pdf_path, out_base_dir, max_pages=10, dpi=150)
    return saved


def _thumbnail_path(source_pdf: str) -> Path | None:
    """캐시된 대표 이미지 경로. 없으면 None."""
    slug = _slug_from_source(source_pdf)
    p = OUTPUT_DIR / "product_images" / slug / "page_0.png"
    return p if p.exists() else None


def render_dashboard(data: list[dict]) -> None:
    """대시보드: 아이템 리스트, 클릭 시 상세로 이동."""
    st.subheader("상품 목록")
    st.caption("항목을 클릭하면 상세 리뷰·편집 페이지로 이동합니다.")

    for i, r in enumerate(data):
        name = (_display_value(r, "상품명") or "-")[:45]
        brand = (r.get("브랜드명") or "-")[:25]
        price = r.get("가격")
        price_str = f"{price:,}원" if isinstance(price, int) else str(price if price is not None else "-")
        source = r.get("source_pdf", "")
        review_snippet = (r.get("리뷰_의견") or "").strip()[:50]
        if review_snippet:
            review_snippet = "💬 " + review_snippet + "…" if len((r.get("리뷰_의견") or "")) > 50 else "💬 " + review_snippet

        thumb_path = _thumbnail_path(source)
        col_img, col_info, col_btn = st.columns([1, 4, 1])
        with col_img:
            if thumb_path:
                st.image(str(thumb_path), use_container_width=True)
            else:
                st.caption("(이미지 없음)")
        with col_info:
            st.markdown(f"**{name}**")
            st.caption(f"{brand} · {price_str} · `{source}`")
            if review_snippet:
                st.caption(review_snippet)
        with col_btn:
            if st.button("상세 보기", key=f"detail_{i}"):
                st.session_state["pdf_review_item_index"] = i
                st.session_state["pdf_review_edit_mode"] = False
                st.rerun()
        st.divider()


def render_detail(data: list[dict], index: int) -> None:
    """상세 리뷰: 읽기 전용 또는 편집 폼. 편집 버튼 → 편집 모드, 저장 버튼 → 저장."""
    item = data[index]
    source_pdf = item.get("source_pdf") or ""
    pdf_base = _get_pdf_base()
    pdf_path = pdf_base / source_pdf
    edit_mode = st.session_state.get("pdf_review_edit_mode", False)

    # 상단: 목록으로, (편집 | 저장)
    top1, top2, top3 = st.columns([1, 1, 2])
    with top1:
        if st.button("← 목록으로"):
            st.session_state["pdf_review_item_index"] = None
            st.session_state["pdf_review_edit_mode"] = False
            st.rerun()
    with top2:
        if not edit_mode:
            if st.button("편집"):
                st.session_state["pdf_review_edit_mode"] = True
                st.rerun()
        else:
            st.caption("아래 폼을 수정한 뒤 **저장** 버튼을 누르세요.")

    display_name = _display_value(item, "상품명") or "(상품명 없음)"
    st.subheader(display_name)
    st.caption(f"PDF: {source_pdf}")

    if not pdf_path.exists():
        st.warning(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
    else:
        st.markdown("---")
        st.markdown("**프로덕트 이미지** (PDF에서 스크랩)")
        with st.spinner("이미지 불러오는 중..."):
            image_paths = _ensure_product_images(pdf_path, OUTPUT_DIR)
        if not image_paths:
            st.caption("이미지를 추출할 수 없습니다. PyMuPDF(fitz) 설치 여부를 확인하세요.")
        else:
            st.image(str(image_paths[0]), use_container_width=True)
            if len(image_paths) > 1:
                cols = st.columns(min(3, len(image_paths) - 1))
                for idx, p in enumerate(image_paths[1:]):
                    with cols[idx % len(cols)]:
                        st.image(str(p), use_container_width=True)

    st.markdown("---")
    st.markdown("**분석 내용 및 리뷰 의견**")

    if not edit_mode:
        # 읽기 전용 (비어 있으면 파일명 등 fallback 표시)
        for key in EDIT_KEYS:
            val = item.get(key)
            if key == "가격":
                if isinstance(val, int):
                    st.text(f"{key}: {val:,}")
                else:
                    st.text(f"{key}: {_display_value(item, key)}")
            else:
                st.text(f"{key}: {_display_value(item, key)}")
        for key in ARRAY_KEYS:
            raw = item.get(key) or []
            st.text(f"{key}: {', '.join(str(x) for x in raw) if raw else '-'}")
        return

    # 편집 모드: 폼으로 입력 후 저장 버튼으로 제출
    with st.form("review_edit_form"):
        edits = {}
        for key in EDIT_KEYS:
            val = item.get(key)
            if key == "가격":
                v = st.number_input(key, value=int(val) if val is not None else 0, min_value=0, step=1000)
                edits[key] = v
            elif key in ("사이즈_상세", "브랜드_평", "이미지_요약", "리뷰_의견"):
                v = st.text_area(key, value=(val or ""), height=100 if key == "리뷰_의견" else 80)
                edits[key] = v
            else:
                v = st.text_input(key, value=(val or ""))
                edits[key] = v
        for key in ARRAY_KEYS:
            raw = item.get(key) or []
            raw_str = ", ".join(str(x) for x in raw) if isinstance(raw, list) else str(raw)
            v = st.text_input(key, value=raw_str, help="쉼표로 구분")
            edits[key] = [x.strip() for x in (v or "").split(",") if x.strip()]

        submitted = st.form_submit_button("저장")
        if submitted:
            for key, value in edits.items():
                item[key] = value
            try:
                JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                st.session_state["pdf_review_edit_mode"] = False
                st.success("저장되었습니다.")
                st.rerun()
            except Exception as e:
                st.error(f"저장 실패: {e}")


def render() -> None:
    st.title("PDF 상품 리뷰 / 편집")
    st.caption("대시보드에서 항목을 선택하면 상세 리뷰 페이지로 이동합니다. 상세에서 '편집'을 누르면 수정 후 '저장'할 수 있습니다.")

    if not JSON_PATH.exists():
        st.info("분석 결과가 없습니다. 먼저 **PDF 분석** 페이지에서 'PDF 분석 실행'을 실행해 주세요.")
        return

    try:
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        st.error(f"결과 파일 읽기 실패: {e}")
        return

    if not data:
        st.info("분석 결과 항목이 없습니다.")
        return

    # PDF 분석 페이지에서 넘어온 경우 선택 인덱스 유지
    selected = st.session_state.get("pdf_review_item_index")
    if hasattr(st, "query_params") and st.query_params.get("item"):
        try:
            q = int(st.query_params.get("item", 0))
            if 0 <= q < len(data):
                selected = q
                st.session_state["pdf_review_item_index"] = q
        except (ValueError, TypeError):
            pass
    if selected is not None and (selected < 0 or selected >= len(data)):
        selected = None

    if selected is not None:
        render_detail(data, selected)
    else:
        render_dashboard(data)


render()
