"""
전역 UI 스타일: 모던·사용자 친화적 레이아웃 (Collection, PDF Analysis, Item Review, Result Report 공통)
"""
import streamlit as st


def inject_global_style() -> None:
    """앱 전체에 적용할 CSS. 각 페이지 상단에서 한 번 호출."""
    st.markdown(
        """
    <style>
    /* ===== 레이아웃 ===== */
    .stApp { max-width: 1320px; margin: 0 auto; background: #fafbfc; }
    .block-container { padding-top: 2rem !important; padding-bottom: 3rem !important; padding-left: 2rem !important; padding-right: 2rem !important; max-width: 100%; }
    
    /* ===== 사이드바 (페이지 네비게이션) ===== */
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%) !important; }
    [data-testid="stSidebar"] [data-testid="stMarkdown"] { font-weight: 500; color: #334155; }
    [data-testid="stSidebar"] a { text-decoration: none !important; border-radius: 8px; padding: 0.5rem 0.75rem; transition: background 0.15s; }
    [data-testid="stSidebar"] a:hover { background: #f1f5f9 !important; }
    
    /* ===== 타이포그래피 ===== */
    h1 { font-size: 1.85rem !important; font-weight: 700 !important; color: #0f172a !important; letter-spacing: -0.03em; margin-bottom: 0.35rem !important; line-height: 1.25 !important; }
    h2 { font-size: 1.25rem !important; font-weight: 600 !important; color: #1e293b !important; margin-top: 2rem !important; margin-bottom: 0.6rem !important; padding-bottom: 0.35rem; border-bottom: 1px solid #e2e8f0; }
    h3 { font-size: 1.05rem !important; font-weight: 600 !important; color: #334155 !important; margin-top: 1.25rem !important; margin-bottom: 0.5rem !important; }
    p, .stMarkdown { line-height: 1.65 !important; color: #475569 !important; }
    .stCaption { color: #64748b !important; font-size: 0.8125rem !important; line-height: 1.5 !important; margin-top: 0.15rem !important; }
    
    /* ===== 버튼 ===== */
    .stButton > button {
        border-radius: 10px !important;
        font-weight: 500 !important;
        padding: 0.5rem 1rem !important;
        transition: all 0.2s ease !important;
        border: 1px solid #e2e8f0 !important;
    }
    .stButton > button:hover {
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2) !important;
        border-color: #93c5fd !important;
    }
    .stButton > button[kind="primary"] { background: linear-gradient(180deg, #2563eb 0%, #1d4ed8 100%) !important; border-color: #1d4ed8 !important; color: white !important; }
    .stButton > button[kind="primary"]:hover { box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4) !important; }
    
    /* ===== 입력 필드 ===== */
    .stTextInput > div > div > input, .stNumberInput > div > div > input {
        border-radius: 10px !important;
        border: 1px solid #e2e8f0 !important;
        padding: 0.5rem 0.75rem !important;
    }
    .stTextInput > div > div > input:focus, .stNumberInput > div > div > input:focus { border-color: #2563eb !important; box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1) !important; }
    label { font-weight: 500 !important; color: #334155 !important; }
    
    /* ===== 체크박스·라디오 ===== */
    [data-testid="stCheckbox"] label, [data-testid="stRadio"] label { font-weight: 450 !important; color: #475569 !important; }
    
    /* ===== 메트릭 (카드 느낌) ===== */
    [data-testid="stMetric"] {
        background: #ffffff;
        padding: 1rem 1.25rem !important;
        border-radius: 12px !important;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    [data-testid="stMetricValue"] { font-weight: 700 !important; color: #0f172a !important; font-size: 1.5rem !important; }
    [data-testid="stMetricLabel"] { color: #64748b !important; font-size: 0.875rem !important; }
    
    /* ===== 알림 박스 (성공·정보·경고·오류) ===== */
    [data-testid="stAlert"] {
        border-radius: 12px !important;
        padding: 1rem 1.25rem !important;
        border: 1px solid rgba(0,0,0,0.06) !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    }
    
    /* ===== Expander ===== */
    [data-testid="stExpander"] {
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        overflow: hidden;
        margin-bottom: 0.5rem;
    }
    [data-testid="stExpander"] summary { padding: 0.75rem 1rem !important; font-weight: 500 !important; background: #f8fafc !important; }
    [data-testid="stExpander"] summary:hover { background: #f1f5f9 !important; }
    
    /* ===== Progress bar: 트랙만 스타일. 채움 div는 width 미지정(Streamlit 인라인 % 유지) ===== */
    [data-testid="stProgress"] > div > div { border-radius: 999px !important; background: #e2e8f0 !important; }
    [data-testid="stProgress"] > div > div > div { border-radius: 999px !important; background: linear-gradient(90deg, #2563eb, #3b82f6) !important; }
    
    /* ===== 데이터프레임·테이블 ===== */
    [data-testid="stDataFrame"] {
        border-radius: 12px !important;
        overflow: hidden !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
    }
    [data-testid="stDataFrame"] thead tr th { background: #f8fafc !important; font-weight: 600 !important; color: #334155 !important; padding: 0.75rem 1rem !important; }
    
    /* ===== 구분선 ===== */
    hr { margin: 2rem 0 !important; border: none !important; border-top: 1px solid #e2e8f0 !important; }
    
    /* ===== Spinner ===== */
    [data-testid="stSpinner"] { color: #2563eb !important; }
    
    /* ===== Slider ===== */
    [data-testid="stSlider"] > div > div { background: #e2e8f0 !important; border-radius: 999px !important; }
    [data-testid="stSlider"] .stSlider > div > div > div { background: linear-gradient(90deg, #2563eb, #3b82f6) !important; }
    
    /* ===== Select box ===== */
    [data-testid="stSelectbox"] > div { border-radius: 10px !important; border: 1px solid #e2e8f0 !important; }
    
    /* ===== 폼 구역 여백 ===== */
    [data-testid="stForm"] { border: 1px solid #e2e8f0 !important; border-radius: 12px !important; padding: 1.25rem !important; background: #ffffff !important; }
    </style>
    """,
        unsafe_allow_html=True,
    )


def page_header(title: str, description: str = "") -> None:
    """페이지 상단: 제목 + 한 줄 설명. 일관된 여백."""
    st.markdown(f"# {title}")
    if description:
        st.caption(description)
    st.markdown("")  # 여백


def section_header(title: str, caption: str = "") -> None:
    """섹션 제목 + 선택적 캡션."""
    st.markdown(f"### {title}")
    if caption:
        st.caption(caption)
    st.markdown("")
