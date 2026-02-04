"""
데이터 대시보드 페이지
"""
from datetime import date

import pandas as pd
import streamlit as st

from shared.services import DataService


def render() -> None:
    """데이터 대시보드 UI 렌더링."""
    st.title("데이터 대시보드")

    service = DataService()  # 웹 UI에서는 익명 키 사용 (기본값 False)

    # ===== 상단 요약 카드 =====
    with st.spinner("요약 지표를 계산하는 중..."):
        brands = list(service.get_brands())
        categories = list(service.get_categories())
        tasks = service.get_tasks(limit=200)

    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    with col_kpi1:
        st.metric("브랜드 수", len(brands))
    with col_kpi2:
        st.metric("카테고리 수", len(categories))
    with col_kpi3:
        running_cnt = len([t for t in tasks if t.status == "running"])
        st.metric("진행 중 작업 수", running_cnt)

    # 참고용 브랜드/카테고리 맵
    brand_map = {b.id: b.name for b in brands}
    category_map = {c.id: f"{c.gender}/{c.name}" for c in categories}

    # ===== 필터 영역 =====
    st.markdown("---")
    st.subheader("필터")
    col1, col2, col3 = st.columns(3)

    with col1:
        brand_filter_label = st.selectbox(
            "브랜드 필터",
            ["전체"] + sorted({name for name in brand_map.values()}),
        )
    with col2:
        category_filter_label = st.selectbox(
            "카테고리 필터",
            ["전체"] + sorted({label for label in category_map.values()}),
        )
    with col3:
        limit = st.number_input(
            "표시 개수", min_value=10, max_value=500, value=100, step=10
        )

    col4, col5, col6 = st.columns(3)
    with col4:
        min_price = st.number_input("최소 가격", min_value=0, value=0, step=1000)
    with col5:
        max_price = st.number_input(
            "최대 가격", min_value=0, value=1_000_000, step=1000
        )
    with col6:
        start_date: date | None = st.date_input("수집 시작일", value=None)

    end_date: date | None = st.date_input("수집 종료일", value=None)

    if st.button("데이터 조회"):
        # 필터용 ID 계산
        brand_id = None
        if brand_filter_label != "전체":
            for bid, name in brand_map.items():
                if name == brand_filter_label:
                    brand_id = bid
                    break

        category_id = None
        if category_filter_label != "전체":
            for cid, label in category_map.items():
                if label == category_filter_label:
                    category_id = cid
                    break

        products = service.get_products(
            brand_id=brand_id,
            category_id=category_id,
            min_price=min_price or None,
            max_price=max_price or None,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
            limit=int(limit),
        )

        if not products:
            st.info("조건에 맞는 데이터가 없습니다.")
            return

        # DataFrame 구성 (브랜드/카테고리 이름 조인)
        rows = []
        for p in products:
            rows.append(
                {
                    "상품 ID": str(p.id),
                    "브랜드": brand_map.get(p.brand_id, str(p.brand_id)),
                    "카테고리": category_map.get(
                        p.category_id, str(p.category_id)
                    ),
                    "상품명": p.name,
                    "가격": p.price,
                    "랭킹": p.ranking,
                    "수집 시각": p.collected_at,
                }
            )

        df = pd.DataFrame(rows)

        # ===== 요약 차트 =====
        st.subheader("요약 차트")
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            brand_group = (
                df.groupby("브랜드")["상품 ID"]
                .count()
                .sort_values(ascending=False)
                .head(10)
            )
            st.bar_chart(brand_group, use_container_width=True)

        with chart_col2:
            price_group = (
                df[["카테고리", "가격"]]
                .groupby("카테고리")["가격"]
                .mean()
                .sort_values(ascending=False)
                .head(10)
            )
            st.bar_chart(price_group, use_container_width=True)

        # ===== 상세 테이블 =====
        st.subheader("상품 목록")
        st.dataframe(df, use_container_width=True)

        # CSV 다운로드
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="CSV로 다운로드",
            data=csv,
            file_name="products.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    render()

