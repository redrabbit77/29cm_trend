"""
PDF 상품 리뷰/편집 페이지: 대시보드(아이템 리스트) → 클릭 시 상세 리뷰/편집.
상세에서 '편집' 버튼으로 편집 모드 진입, '저장'으로 반영.
대표/상세 이미지는 PDF에서 이미지 영역만 캡처해 표시.
"""
from pathlib import Path
import json
import sys

import pandas as pd
import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

OUTPUT_DIR = _PROJECT_ROOT / "data" / "pdf_analysis"
JSON_PATH = OUTPUT_DIR / "pdf_products.json"
PDF_BASE_PATH_FILE = _PROJECT_ROOT / "data" / "pdf_base_path.txt"


def _render_thumbnail_local(pdf_path: Path, slug: str, out_dir: Path, dpi: int = 120) -> Path | None:
    """PyMuPDF(fitz)로 PDF 첫 페이지를 PNG로 저장. gemini_extract 의존 없음."""
    try:
        import fitz
    except ImportError:
        return None
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            doc.close()
            return None
        page = doc[0]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        png_bytes = pix.tobytes("png")
        doc.close()
    except Exception:
        return None
    save_dir = out_dir / "product_images" / slug
    save_dir.mkdir(parents=True, exist_ok=True)
    out_file = save_dir / "page_0.png"
    out_file.write_bytes(png_bytes)
    return out_file


def _get_pdf_base() -> Path:
    """수집 시 지정한 PDF 저장 경로. 없으면 프로젝트/pdfs.
    Cloud 배포 시 로컬 절대 경로(C:\...)가 저장되어 있으면 무시하고 기본 경로 사용.
    """
    default_path = (_PROJECT_ROOT / "pdfs").resolve()
    if PDF_BASE_PATH_FILE.exists():
        try:
            raw = PDF_BASE_PATH_FILE.read_text(encoding="utf-8").strip()
            if raw:
                # 1. 저장된 경로가 실제로 존재하는지 확인
                p = Path(raw)
                if p.is_absolute():
                    if p.exists():
                        return p
                else:
                    resolved = (_PROJECT_ROOT / p).resolve()
                    if resolved.exists():
                        return resolved
                # 2. 존재하지 않으면(예: 로컬 윈도우 경로를 클라우드에서 읽음), 기본 경로 사용
        except Exception:
            pass
    return default_path

EDIT_KEYS = [
    "상품명", "브랜드명", "상세_카테고리명", "의류종류", "가격", "소재", "케어방법",
    "사이즈_상세",
    "이미지_무드", "이미지_톤", "이미지_배경", "사진_구성", "모델_특징", "제품_특징", "브랜드_평", "이미지_요약",
    "톤_무드", "촬영_특징", "룩북_촬영_배경_무드", "모델링_포즈_특징", "컬러_팔레트", "디자인_컨셉_분석",
    "상세_리뷰", "리뷰_의견",
    "스타일_축", "프리미엄_축", "대표색",
]
ARRAY_KEYS = ("사이즈", "색상")


def _slug_from_source(source_pdf: str) -> str:
    """source_pdf(상대 경로)로부터 product_images 하위 폴더명 생성. Windows 비허용 문자 제거."""
    p = Path((source_pdf or "").replace("\\", "/"))
    parts = list(p.parent.parts) + [p.stem] if p.parent.parts else [p.stem]
    slug = "_".join(parts).replace(" ", "_")
    for c in ('\\', '/', ':', '*', '?', '"', '<', '>', '|'):
        slug = slug.replace(c, "_")
    return slug


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
    """대표/상세 이미지 생성·캐시. 반환: Path 리스트."""
    from analysis.gemini_extract import save_pdf_product_images
    rel_posix = pdf_path.relative_to(_get_pdf_base()).as_posix()
    slug = _slug_from_source(rel_posix)
    img_dir = out_base_dir / "product_images" / slug
    if img_dir.exists():
        # main_0 + detail_* 우선, 없으면 page_*
        main = img_dir / "main_0.png"
        if main.exists():
            saved = [main] + sorted(img_dir.glob("detail_*.png"))
            if saved:
                return saved
        saved = sorted(img_dir.glob("page_*.png"))
        if saved:
            return saved
    try:
        saved = save_pdf_product_images(pdf_path, out_base_dir, max_pages=10, dpi=150, slug=slug)
    except TypeError:
        saved = save_pdf_product_images(pdf_path, out_base_dir, max_pages=10, dpi=150)
    return saved or []


def _get_product_images_with_labels(pdf_path: Path, out_base_dir: Path) -> list[tuple[Path, str]]:
    """대표/상세 이미지 경로와 라벨('대표'|'상세') 리스트. 없으면 생성 시도."""
    try:
        from analysis.gemini_extract import extract_pdf_image_regions, save_pdf_product_images
    except ImportError:
        extract_pdf_image_regions = None
        from analysis.gemini_extract import save_pdf_product_images
    rel_posix = pdf_path.relative_to(_get_pdf_base()).as_posix()
    slug = _slug_from_source(rel_posix)
    img_dir = out_base_dir / "product_images" / slug

    def _labeled_from_dir() -> list[tuple[Path, str]] | None:
        main0 = img_dir / "main_0.png"
        details = sorted(img_dir.glob("detail_*.png"))
        if main0.exists() or details:
            out = [(main0, "대표")] if main0.exists() else []
            out += [(p, "상세") for p in details]
            return out if out else None
        pages = sorted(img_dir.glob("page_*.png"))
        if pages:
            return [(pages[0], "대표")] + [(p, "상세") for p in pages[1:]]
        return None

    if img_dir.exists():
        labeled = _labeled_from_dir()
        # 캐시가 page_0.png 한 장뿐이면(목록 썸네일만 생성된 경우) 상세용으로 전부 재생성
        if labeled is not None and len(labeled) == 1 and (img_dir / "page_0.png").exists():
            try:
                save_pdf_product_images(pdf_path, out_base_dir, max_pages=10, dpi=150, slug=slug)
            except Exception:
                pass
            labeled = _labeled_from_dir()
        if labeled is not None:
            return labeled
    # 캐시 없음: 영역 추출 또는 전체 페이지 생성
    if extract_pdf_image_regions is not None:
        try:
            labeled = extract_pdf_image_regions(pdf_path, out_base_dir, slug=slug, max_pages=10, dpi=150)
            if labeled:
                return labeled
        except Exception:
            pass
    paths = _ensure_product_images(pdf_path, out_base_dir)
    if not paths:
        return []
    return [(paths[0], "대표")] + [(p, "상세") for p in paths[1:]]


def _thumbnail_path(source_pdf: str, pdf_base: Path | None = None) -> Path | None:
    """캐시된 대표 이미지 경로. main_0(영역 캡처) 또는 page_0(전체 페이지) 우선."""
    src = (source_pdf or "").replace("\\", "/")
    slug = _slug_from_source(src)
    for name in ("main_0.png", "page_0.png"):
        p = OUTPUT_DIR / "product_images" / slug / name
        if p.exists():
            return p
    if pdf_base:
        try:
            full = (pdf_base / src).resolve()
            slug2 = _slug_from_source(str(full).replace("\\", "/"))
            for name in ("main_0.png", "page_0.png"):
                p2 = OUTPUT_DIR / "product_images" / slug2 / name
                if p2.exists():
                    return p2
        except Exception:
            pass
    return None


def render_dashboard(data: list[dict]) -> None:
    """대시보드: 아이템 리스트(대표이미지 썸네일), 클릭 시 상세로 이동."""
    st.subheader("상품 목록")
    st.caption("항목을 클릭하면 상세 리뷰·편집 페이지로 이동합니다. 썸네일이 없으면 아래 버튼으로 일괄 생성하세요.")
    pdf_base = _get_pdf_base()
    if st.button("목록 썸네일 일괄 생성 (대표이미지)", key="gen_thumbnails"):
        n = 0
        with st.spinner("PDF 첫 페이지를 썸네일로 저장 중..."):
            for r in data:
                source = (r.get("source_pdf") or "").replace("\\", "/")
                if not source:
                    continue
                if _thumbnail_path(source, pdf_base):
                    continue
                pdf_path = pdf_base / source
                if pdf_path.exists():
                    slug = _slug_from_source(source)
                    if _render_thumbnail_local(pdf_path, slug, OUTPUT_DIR, dpi=120):
                        n += 1
        st.success(f"썸네일 {n}개 생성 완료.")
        st.rerun()

    need_rerun_for_thumb = False
    for i, r in enumerate(data):
        name = (_display_value(r, "상품명") or "-")[:45]
        brand = (r.get("브랜드명") or "-")[:25]
        price = r.get("가격")
        price_str = f"{price:,}원" if isinstance(price, int) else str(price if price is not None else "-")
        source = (r.get("source_pdf") or "").replace("\\", "/")
        review_snippet = (r.get("리뷰_의견") or "").strip()[:50]
        if review_snippet:
            review_snippet = "💬 " + review_snippet + "…" if len((r.get("리뷰_의견") or "")) > 50 else "💬 " + review_snippet

        thumb_path = _thumbnail_path(source, pdf_base)
        # 썸네일 없으면 세션당 1회만 생성 시도
        _thumb_tried_key = f"_thumb_tried_{_slug_from_source(source)}"
        if not thumb_path and source and not st.session_state.get(_thumb_tried_key):
            pdf_path = pdf_base / source
            if pdf_path.exists():
                slug = _slug_from_source(source)
                _render_thumbnail_local(pdf_path, slug, OUTPUT_DIR, dpi=100)
                st.session_state[_thumb_tried_key] = True
                thumb_path = _thumbnail_path(source, pdf_base)
                need_rerun_for_thumb = True
        col_img, col_info, col_btn = st.columns([1, 4, 1])
        with col_img:
            st.caption("대표이미지")
            if thumb_path:
                st.image(str(thumb_path), use_container_width=True)
            else:
                st.caption("(없음)")
        with col_info:
            st.markdown(f"**{name}**")
            st.caption(f"{brand} · {price_str} · `{source}`")
            if review_snippet:
                st.caption(review_snippet)
        with col_btn:
            if st.button("상세 보기", key=f"detail_{i}"):
                st.session_state["pdf_review_item_index"] = i
                if hasattr(st, "query_params"):
                    try:
                        st.query_params["item"] = str(i)
                        if "list" in st.query_params:
                            del st.query_params["list"]
                    except Exception:
                        pass
                st.rerun()
        st.divider()

    if need_rerun_for_thumb:
        st.rerun()


def render_detail(data: list[dict], index: int) -> None:
    """상세 리뷰: 읽기 전용 또는 편집 폼. 편집 버튼 → 편집 모드, 저장 버튼 → 저장."""
    item = data[index]
    source_pdf = item.get("source_pdf") or ""
    pdf_base = _get_pdf_base()
    pdf_path = pdf_base / source_pdf
    edit_mode = st.session_state.get("pdf_review_edit_mode", False)

    # 상단: 목록으로(뒤로가기), (편집 | 저장)
    top1, top2, top3 = st.columns([1, 1, 2])
    with top1:
        if st.button("← 목록으로", type="primary", key="back_to_list"):
            st.session_state["pdf_review_item_index"] = None
            st.session_state["pdf_review_edit_mode"] = False
            if hasattr(st, "query_params"):
                try:
                    if "item" in st.query_params:
                        del st.query_params["item"]
                    st.query_params["list"] = "1"
                except Exception:
                    pass
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

    labeled_images = []
    # 이미지 먼저 로드 시도 (PDF 파일 유무와 관계없이)
    try:
        labeled_images = _get_product_images_with_labels(pdf_path, OUTPUT_DIR)
    except Exception:
        labeled_images = []

    if not pdf_path.exists():
        if labeled_images:
            st.info("⚠️ PDF 원본 파일은 없지만, 미리보기 이미지를 표시합니다. (Cloud 배포 모드)")
        else:
            st.warning(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
    else:
        st.markdown("---")
        st.markdown("**대표 · 상세 이미지** (PDF에서 이미지 영역만 캡처)")
    
    # 이미지 표시 로직 (들여쓰기 주의)
    if not labeled_images and pdf_path.exists():
        # 위에서 로드 실패했으나 PDF는 있는 경우 다시 시도? (위에서 이미 했음)
        st.caption("이미지를 추출할 수 없습니다. PyMuPDF(fitz) 설치 여부를 확인하세요.")
    elif labeled_images:
        # 이미지 표시
        if not pdf_path.exists():
             st.markdown("---")
             st.markdown("**대표 · 상세 이미지**")
        
        rep = [p for p, label in labeled_images if label == "대표"]
        detail = [p for p, label in labeled_images if label == "상세"]
        if rep:
            st.markdown("###### 대표 이미지")
            st.image(str(rep[0]), use_container_width=True)
        if detail:
            st.markdown("###### 상세 이미지")
            n = len(detail)
            cols = st.columns(min(4, n))
            for idx, p in enumerate(detail):
                with cols[idx % len(cols)]:
                    st.image(str(p), use_container_width=True)

    st.markdown("---")
    st.markdown("**분석 내용 및 리뷰 의견**")

    if not edit_mode:
        # 읽기 전용: 깔끔한 테이블로 표시 (모든 항목, 빈 값은 -)
        rows = []
        for key in EDIT_KEYS:
            val = item.get(key)
            if key == "가격":
                disp = f"{val:,}" if isinstance(val, int) else _display_value(item, key)
            else:
                disp = _display_value(item, key)
            rows.append({"항목": key, "값": disp or "-"})
        for key in ARRAY_KEYS:
            raw = item.get(key) or []
            disp = ", ".join(str(x) for x in raw) if raw else "-"
            rows.append({"항목": key, "값": disp})
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "항목": st.column_config.TextColumn("항목", width="medium"),
                "값": st.column_config.TextColumn("값", width="large"),
            },
        )
        return

    # 편집 모드: 폼으로 입력 후 저장 버튼으로 제출
    with st.form("review_edit_form"):
        edits = {}
        for key in EDIT_KEYS:
            val = item.get(key)
            if key == "가격":
                v = st.number_input(key, value=int(val) if val is not None else 0, min_value=0, step=1000)
                edits[key] = v
            elif key in ("스타일_축", "프리미엄_축"):
                v = st.number_input(key, value=int(val) if val is not None else 50, min_value=0, max_value=100, step=5, help="브랜드맵 지표 0~100")
                edits[key] = v
            elif key == "대표색":
                v = st.text_input(key, value=(val or ""), help="hex(예 #1a1a1a) 또는 색상명(NAVY, BLACK 등)")
                edits[key] = v
            elif key in ("사이즈_상세", "브랜드_평", "이미지_요약", "톤_무드", "촬영_특징", "룩북_촬영_배경_무드", "모델링_포즈_특징", "컬러_팔레트", "디자인_컨셉_분석", "상세_리뷰", "리뷰_의견"):
                v = st.text_area(key, value=(val or ""), height=150 if key in ("상세_리뷰", "디자인_컨셉_분석") else (100 if key == "리뷰_의견" else 80))
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
    try:
        from web.utils.global_style import inject_global_style, page_header
        inject_global_style()
    except Exception:
        pass

    page_header("PDF 상품 리뷰", "목록에서 항목을 선택해 상세를 보고, 편집 후 저장할 수 있습니다.")

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

    # URL 쿼리 파라미터 우선 (브라우저 뒤로가기 시 목록으로 복귀되도록)
    selected = None
    
    # 브랜드 리뷰 페이지 등에서 강제로 넘어온 경우 처리
    if st.session_state.get("navigate_from_brand_review"):
        forced_idx = st.session_state.get("pdf_review_item_index")
        if forced_idx is not None:
            selected = forced_idx
            # URL 업데이트 (새로고침 시 유지)
            if hasattr(st, "query_params"):
                st.query_params["item"] = str(forced_idx)
                if "list" in st.query_params:
                    del st.query_params["list"]
        st.session_state["navigate_from_brand_review"] = False  # 플래그 해제
    
    if selected is None and hasattr(st, "query_params"):
        q = st.query_params.get("item")
        if q is not None and q != "":
            try:
                idx = int(q)
                if 0 <= idx < len(data):
                    selected = idx
                    st.session_state["pdf_review_item_index"] = idx
            except (ValueError, TypeError):
                pass
        else:
            # URL에 item 없으면 목록 보기 (뒤로가기 시 여기로 옴)
            st.session_state["pdf_review_item_index"] = None
    if selected is None:
        selected = st.session_state.get("pdf_review_item_index")
    if selected is not None and (selected < 0 or selected >= len(data)):
        selected = None
        st.session_state["pdf_review_item_index"] = None

    # 목록 보기일 때 URL에 list=1 유지 → 상세에서 브라우저 뒤로가기 시 목록으로 복귀
    if selected is None and hasattr(st, "query_params"):
        try:
            if st.query_params.get("list") != "1":
                st.query_params["list"] = "1"
                if "item" in st.query_params:
                    del st.query_params["item"]
                st.rerun()
        except Exception:
            pass

    if selected is not None:
        render_detail(data, selected)
    else:
        render_dashboard(data)


render()
