"""
브랜드 맵 시각화 페이지 (1차 버전)
"""
import streamlit as st

import pandas as pd
import plotly.express as px

from shared.services import DataService


def render() -> None:
    """브랜드 포지셔닝 맵 UI 렌더링."""
    st.title("브랜드 포지셔닝 맵 (베타)")

    service = DataService()  # 웹 UI에서는 익명 키 사용

    # 브랜드 / 카테고리 정보
    brands = {b.id: b.name for b in service.get_brands()}
    categories = list(service.get_categories())

    st.subheader("필터 & 축 설정")
    col_filter1, col_filter2 = st.columns(2)

    with col_filter1:
        gender = st.radio("성별 필터", ["전체", "여성", "남성"], horizontal=True)

        # 성별에 따른 카테고리 옵션
        category_options = {
            f"{c.gender}/{c.name}": c.id
            for c in categories
            if gender == "전체" or c.gender == gender
        }
        category_label = st.selectbox(
            "카테고리 필터 (선택 시 해당 카테고리만)", ["전체"] + list(category_options.keys())
        )

        limit = st.number_input(
            "최대 상품 수", min_value=100, max_value=5000, value=1000, step=100
        )

    with col_filter2:
        axis_options = {
            "평균 가격": "avg_price",
            "평균 랭킹": "avg_ranking",
            "상품 수": "product_count",
            "컨셉 점수(placeholder)": "concept_score",
            "무드 점수(placeholder)": "mood_score",
            "인기도 점수(placeholder)": "popularity_score",
        }

        col1, col2 = st.columns(2)
        with col1:
            x_label = st.selectbox("X축", list(axis_options.keys()), index=0)
        with col2:
            y_label = st.selectbox("Y축", list(axis_options.keys()), index=1)

        view_mode = st.radio(
            "보기 모드", ["브랜드별 집계", "상품별"], horizontal=True, index=0
        )

    if st.button("브랜드 맵 생성"):
        # 필터 파라미터 계산
        category_id = None
        if category_label != "전체":
            category_id = category_options[category_label]

        products = service.get_products(
            category_id=category_id,
            limit=int(limit),
        )
        if not products:
            st.info("시각화할 데이터가 없습니다.")
            return

        st.caption(
            f"총 상품 수: {len(products)}개, 브랜드 수: {len({p.brand_id for p in products})}개"
        )

        if view_mode == "브랜드별 집계":
            # 브랜드별 집계
            brand_data = {}
            for p in products:
                brand_id = str(p.brand_id)
                brand_name = brands.get(p.brand_id, brand_id)

                if brand_id not in brand_data:
                    brand_data[brand_id] = {
                        "brand_id": brand_id,
                        "brand_name": brand_name,
                        "prices": [],
                        "rankings": [],
                        "product_count": 0,
                        "concept_score": 0,  # Placeholder
                        "mood_score": 0,  # Placeholder
                        "popularity_score": 0,  # Placeholder
                    }

                brand_data[brand_id]["prices"].append(p.price)
                if p.ranking:
                    brand_data[brand_id]["rankings"].append(p.ranking)
                brand_data[brand_id]["product_count"] += 1

            # 평균 계산
            df_rows = []
            for brand_id, data in brand_data.items():
                avg_price = (
                    sum(data["prices"]) / len(data["prices"])
                    if data["prices"]
                    else 0
                )
                avg_ranking = (
                    sum(data["rankings"]) / len(data["rankings"])
                    if data["rankings"]
                    else 0
                )

                df_rows.append(
                    {
                        "brand_id": brand_id,
                        "brand_name": data["brand_name"],
                        "avg_price": avg_price,
                        "avg_ranking": avg_ranking,
                        "product_count": data["product_count"],
                        "concept_score": data["concept_score"],
                        "mood_score": data["mood_score"],
                        "popularity_score": data["popularity_score"],
                    }
                )

            df = pd.DataFrame(df_rows)
            x_col = axis_options[x_label]
            y_col = axis_options[y_label]

            fig = px.scatter(
                df,
                x=x_col,
                y=y_col,
                size="product_count",
                hover_name="brand_name",
                hover_data=[
                    "brand_id",
                    "avg_price",
                    "avg_ranking",
                    "product_count",
                ],
                title=f"브랜드 포지셔닝 맵: {x_label} vs {y_label}",
                labels={
                    x_col: x_label,
                    y_col: y_label,
                    "product_count": "상품 수",
                },
            )
        else:
            # 상품별 표시
            # 상품별 모드에서는 "product_count"를 사용할 수 없으므로 필터링
            product_axis_options = {
                "평균 가격": "price",
                "평균 랭킹": "ranking",
                "컨셉 점수(placeholder)": "concept_score",
                "무드 점수(placeholder)": "mood_score",
                "인기도 점수(placeholder)": "popularity_score",
            }

            # 상품별 모드에서 사용 가능한 축만 선택
            if (
                x_label not in product_axis_options
                or y_label not in product_axis_options
            ):
                st.warning(
                    "상품별 모드에서는 '상품 수' 축을 사용할 수 없습니다. "
                    "브랜드별 집계 모드를 사용하세요."
                )
                return

            df = pd.DataFrame(
                [
                    {
                        "product_id": str(p.id),
                        "brand_name": brands.get(
                            p.brand_id, str(p.brand_id)
                        ),
                        "name": p.name,
                        "price": p.price,
                        "ranking": p.ranking or 0,
                        "concept_score": 0,
                        "mood_score": 0,
                        "popularity_score": 0,
                    }
                    for p in products
                ]
            )

            x_col = product_axis_options[x_label]
            y_col = product_axis_options[y_label]

            fig = px.scatter(
                df,
                x=x_col,
                y=y_col,
                color="brand_name",
                hover_data=["name", "product_id", "price", "ranking"],
                title=f"상품별 포지셔닝 맵: {x_label} vs {y_label}",
            )

        st.plotly_chart(fig, use_container_width=True)

        st.info(
            "※ 컨셉/무드/인기도 점수는 이후 이미지/텍스트 분석을 통해 계산할 예정입니다."
        )


if __name__ == "__main__":
    render()

