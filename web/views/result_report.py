"""
결과 리포트 페이지: PDF 분석 결과를 바탕으로 AI 전체 브랜드 종합 분석 및 브랜드 맵 생성.
"""
from pathlib import Path
import json
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

OUTPUT_DIR = _PROJECT_ROOT / "data" / "pdf_analysis"
JSON_PATH = OUTPUT_DIR / "pdf_products.json"
REPORT_JSON_PATH = OUTPUT_DIR / "brand_comprehensive_report.json"
BRAND_MAP_PATH = OUTPUT_DIR / "brand_map.json"
# BRAND_MAP_TABLE_PATH는 수동 그리기 삭제로 사용하지 않을 수 있으나, 호환성을 위해 남겨둠 (또는 삭제)
BRAND_MAP_TABLE_PATH = OUTPUT_DIR / "brand_map_table.json"


def _load_data() -> list[dict] | None:
    if not JSON_PATH.exists():
        return None
    try:
        return json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def render() -> None:
    try:
        from web.utils.global_style import inject_global_style, page_header
        inject_global_style()
    except Exception:
        pass

    page_header("결과 리포트", "데이터 기반 브랜드 맵과 AI 종합 분석·브랜드 맵을 확인합니다.")

    data = _load_data()
    if not data:
        st.info("분석 결과가 없습니다. 먼저 **PDF 분석** 페이지에서 'PDF 분석 실행'을 실행해 주세요.")
        return

    st.success(f"총 **{len(data)}건** 분석 결과를 불러왔습니다.")

    # =========================================================
    # 1) 브랜드 맵: 그래프(데이터 기반) + AI 설명 생성 (최상단으로 이동)
    # =========================================================
    st.markdown("## 브랜드 맵")
    st.caption("아래 그래프는 PDF 분석 데이터(스타일_축·프리미엄_축·대표색·상품 수)로 그립니다. **AI 맵 설명** 버튼으로 포지셔닝·무드 요약 텍스트를 추가 생성할 수 있습니다.")
    try:
        from analysis.brand_map_data import build_brand_map_data
        brand_map_data = build_brand_map_data(data)
        if not brand_map_data:
            st.caption("브랜드명이 있는 상품이 없어 맵을 그리지 않습니다.")
        else:
            names = [b["brand_name"] for b in brand_map_data]
            style_axis = [b["style_axis"] for b in brand_map_data]
            premium_axis = [b["premium_axis"] for b in brand_map_data]
            item_count = [b["item_count"] for b in brand_map_data]
            colors_hex = [b["representative_color_hex"] for b in brand_map_data]
            ranks = [b["rank"] for b in brand_map_data]
            max_count = max(item_count) if item_count else 1
            sizes = [12 + (c / max_count) * 28 for c in item_count]
            opacities = [max(0.35, 1.0 - (r - 1) * 0.06) for r in ranks]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=style_axis,
                y=premium_axis,
                text=names,
                textposition="top center",
                mode="markers+text",
                marker=dict(
                    size=sizes,
                    color=colors_hex,
                    opacity=opacities,
                    line=dict(width=1, color="rgba(0,0,0,0.3)"),
                ),
                textfont=dict(size=11),
                name="",
            ))
            fig.update_layout(
                title="브랜드 맵 (스타일 × 프리미엄)",
                xaxis_title="스타일 축 ← 클래식/페미닌 · 시크/미니멀/스트릿 →",
                yaxis_title="프리미엄 축 ← 데일리 · 프리미엄 →",
                # 줌/팬 활성화를 위해 고정 범위 설정 대신 초기 범위만 제안하거나, fixedrange=False(기본값) 유지
                xaxis=dict(range=[-5, 105], zeroline=True, fixedrange=False),
                yaxis=dict(range=[-5, 105], zeroline=True, fixedrange=False),
                showlegend=False,
                height=500,
                margin=dict(b=60, t=50),
            )
            
            # 클릭(선택) 이벤트 처리
            st.caption("ℹ️ **사용 팁**: 브랜드 점을 **한 번 클릭**하면 상세 페이지로 이동합니다. (더블 클릭은 줌 초기화)")
            event = st.plotly_chart(
                fig, 
                use_container_width=True, 
                on_select="rerun", 
                selection_mode="points",
                key="brand_map_chart",
                config={'scrollZoom': True, 'displayModeBar': True}
            )

            # 선택된 포인트가 있으면 페이지 이동 처리
            if event and event.selection and event.selection.points:
                # 디버깅용: 선택된 데이터 확인
                # st.write("선택된 데이터:", event.selection)
                try:
                    point = event.selection.points[0]
                    # Streamlit 1.35+ event.selection.points[0]은 dict 형태일 수 있음
                    # point_index 접근 방식 확인: point['point_index'] 또는 point.point_index
                    idx = point.get('point_index') if isinstance(point, dict) else getattr(point, 'point_index', None)
                    
                    if idx is not None and idx < len(names):
                        selected_brand = names[idx]
                        # st.success(f"이동 중: {selected_brand}")  # 이동 전 메시지
                        st.session_state["brand_review_target"] = selected_brand
                        if hasattr(st, "query_params"):
                            st.query_params["brand"] = selected_brand
                        st.switch_page("pages/brand_review.py")
                    else:
                        st.warning(f"브랜드를 찾을 수 없습니다. (Index: {idx})")
                except Exception as e:
                    st.error(f"이동 오류: {e}")
            
            with st.expander("브랜드별 집계 데이터"):
                st.dataframe(
                    [{"브랜드": b["brand_name"], "스타일_축": b["style_axis"], "프리미엄_축": b["premium_axis"], "상품 수": b["item_count"], "순위": b["rank"], "평균가격": b.get("avg_price")} for b in brand_map_data],
                    use_container_width=True,
                )
    except Exception as e:
        st.caption(f"브랜드 맵 그래프 오류: {e}")

    # AI 맵 설명 생성 (브랜드 맵 바로 아래 배치)
    st.markdown("---")
    st.markdown("**AI 맵 설명 생성** (선택): Gemini로 브랜드별 포지셔닝·무드 요약 텍스트를 생성합니다.")
    if st.button("AI 맵 설명 생성", key="run_brand_map"):
        with st.spinner("AI 브랜드 맵 설명 생성 중..."):
            try:
                from analysis.gemini_extract import generate_brand_map
                brand_map = generate_brand_map(data)
                if brand_map:
                    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                    BRAND_MAP_PATH.write_text(
                        json.dumps(brand_map, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    st.session_state["brand_map_result"] = brand_map
                    st.success("AI 맵 설명이 저장되었습니다. 아래에서 확인하세요.")
                    st.rerun()
                else:
                    st.warning("AI 맵 설명 생성 실패 (GEMINI_API_KEY 확인)")
            except Exception as e:
                st.error(f"실행 오류: {e}")

    brand_map = st.session_state.get("brand_map_result")
    if not brand_map and BRAND_MAP_PATH.exists():
        try:
            brand_map = json.loads(BRAND_MAP_PATH.read_text(encoding="utf-8"))
        except Exception:
            brand_map = None

    if brand_map:
        st.markdown("**AI 브랜드 맵 결과**")
        desc = brand_map.get("브랜드_맵_설명") or brand_map.get("브랜드맵_설명") or ""
        if desc:
            st.markdown("###### 브랜드 맵 설명")
            st.write(desc)
        summary = brand_map.get("브랜드_요약") or []
        if isinstance(summary, list) and summary:
            st.markdown("###### 브랜드별 요약")
            rows = []
            for s in summary:
                if isinstance(s, dict):
                    rows.append({k: v for k, v in s.items()})
                else:
                    rows.append({"요약": str(s)})
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        comp = brand_map.get("비교_요약") or ""
        if comp:
            st.markdown("###### 비교 요약")
            st.write(comp)
        with st.expander("AI 맵 원본 JSON", expanded=False):
            st.json(brand_map)

    # =========================================================
    # 2) 전체 브랜드 종합 분석 (AI) (하단으로 이동)
    # =========================================================
    st.markdown("---")
    st.markdown("## 전체 브랜드 종합 분석 (AI)")
    st.caption("Gemini API로 분석 결과를 종합해 브랜드별 요약·비교·시장 관점 종합 분석을 생성합니다.")
    if st.button("종합 분석 실행", key="run_comprehensive"):
        with st.spinner("AI 종합 분석 중..."):
            try:
                from analysis.gemini_extract import generate_brand_comprehensive_analysis
                report = generate_brand_comprehensive_analysis(data)
                if report:
                    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                    REPORT_JSON_PATH.write_text(
                        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    st.session_state["brand_comprehensive_report"] = report
                    st.success("종합 분석이 완료되었습니다.")
                    st.rerun()
                else:
                    st.warning("종합 분석 생성 실패 (GEMINI_API_KEY 확인)")
            except Exception as e:
                st.error(f"실행 오류: {e}")

    report = st.session_state.get("brand_comprehensive_report")
    if not report and REPORT_JSON_PATH.exists():
        try:
            report = json.loads(REPORT_JSON_PATH.read_text(encoding="utf-8"))
        except Exception:
            report = None

    if report:
        with st.expander("종합 분석 결과 보기", expanded=True):
            for key in ("종합_분석", "비교_분석", "브랜드별_요약", "핵심_인사이트"):
                val = report.get(key)
                if val is None:
                    continue
                st.markdown(f"**{key}**")
                if isinstance(val, list):
                    for i, item in enumerate(val, 1):
                        if isinstance(item, dict):
                            st.json(item)
                        else:
                            st.text(f"  {i}. {item}")
                else:
                    st.write(val)
                st.markdown("---")


if __name__ == "__main__":
    render()
