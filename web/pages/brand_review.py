"""
브랜드별 상품 모아보기 페이지.
결과 리포트의 브랜드 맵에서 브랜드를 클릭하면 이 페이지로 이동합니다.
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


def _load_data() -> list[dict] | None:
    if not JSON_PATH.exists():
        return None
    try:
        return json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _get_thumbnail_path(source_pdf: str) -> Path | None:
    """PDF 소스 경로에서 썸네일(main_0.png 또는 page_0.png) 경로 찾기."""
    if not source_pdf:
        return None
    try:
        src = source_pdf.replace("\\", "/")
        p = Path(src)
        parts = list(p.parent.parts) + [p.stem] if p.parent.parts else [p.stem]
        slug = "_".join(parts).replace(" ", "_")
        for c in ('\\', '/', ':', '*', '?', '"', '<', '>', '|'):
            slug = slug.replace(c, "_")
        
        img_dir = OUTPUT_DIR / "product_images" / slug
        for name in ("main_0.png", "page_0.png"):
            img_path = img_dir / name
            if img_path.exists():
                return img_path
    except Exception:
        pass
    return None


def render() -> None:
    try:
        from web.utils.global_style import inject_global_style, page_header
        inject_global_style()
    except Exception:
        pass

    page_header("브랜드별 리뷰", "특정 브랜드의 모든 상품을 모아보고 상세 리뷰로 이동합니다.")

    data = _load_data()
    if not data:
        st.info("분석 결과가 없습니다.")
        return

    # 1. 브랜드 목록 추출
    brands = sorted(list({(item.get("브랜드명") or "미지정").strip() for item in data}))
    
    # 2. 선택된 브랜드 확인 (세션/쿼리 파라미터)
    selected_brand_idx = 0
    query_brand = ""
    if hasattr(st, "query_params"):
        query_brand = st.query_params.get("brand", "")
    
    target_brand = st.session_state.get("brand_review_target", query_brand)
    
    if target_brand and target_brand in brands:
        selected_brand_idx = brands.index(target_brand)

    selected_brand = st.selectbox(
        "브랜드 선택", 
        brands, 
        index=selected_brand_idx,
        key="brand_review_select"
    )

    # 선택 변경 시 쿼리 파라미터 업데이트 (선택사항)
    if selected_brand != query_brand:
        if hasattr(st, "query_params"):
            st.query_params["brand"] = selected_brand

    # 3. 해당 브랜드 상품 필터링
    items = [
        (i, item) for i, item in enumerate(data) 
        if (item.get("브랜드명") or "미지정").strip() == selected_brand
    ]

    if not items:
        st.warning("이 브랜드에는 상품이 없습니다.")
        return

    # 4. 통계 표시
    prices = [int(item.get("가격", 0) or 0) for _, item in items if item.get("가격")]
    avg_price = sum(prices) / len(prices) if prices else 0
    
    st.markdown(f"### {selected_brand}")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("상품 수", f"{len(items)}개")
    with col2:
        st.metric("평균 가격", f"{avg_price:,.0f}원")

    st.markdown("---")
    st.caption("상품을 클릭하면 상세 리뷰 페이지로 이동합니다.")

    # 5. 그리드 뷰
    cols = st.columns(4)
    for idx, (original_idx, item) in enumerate(items):
        with cols[idx % 4]:
            thumb = _get_thumbnail_path(item.get("source_pdf", ""))
            name = item.get("상품명") or "상품명 없음"
            price = item.get("가격") or 0
            
            # 카드 형태
            with st.container():
                if thumb:
                    st.image(str(thumb), use_container_width=True)
                else:
                    st.markdown(":frame_with_picture: (이미지 없음)")
                
                st.markdown(f"**{name[:20]}**")
                st.caption(f"{price:,}원" if isinstance(price, int) else str(price))
                
                if st.button("상세 보기", key=f"go_item_{original_idx}"):
                    # 상세 페이지로 이동 설정
                    st.session_state["pdf_review_item_index"] = original_idx
                    st.session_state["navigate_from_brand_review"] = True  # 플래그 설정
                    if hasattr(st, "query_params"):
                        st.query_params["item"] = str(original_idx)
                        if "list" in st.query_params:
                            del st.query_params["list"]
                    st.switch_page("pages/pdf_item_review.py")
            st.markdown("---")


if __name__ == "__main__":
    render()
