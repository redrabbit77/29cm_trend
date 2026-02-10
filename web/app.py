"""
Streamlit 메인 앱 진입점
"""
# supabase 패키지가 로컬 폴더와 충돌하지 않도록 site-packages를 먼저 검색
import sys
import site
from pathlib import Path

for _sp in (getattr(site, "getsitepackages", lambda: [])() or []):
    if _sp and _sp not in sys.path:
        sys.path.insert(0, _sp)
        break

# 실행 위치와 관계없이 프로젝트 루트를 path에 추가 (shared, .env 동일하게 사용)
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# .env를 os.environ에 로드 (GEMINI_API_KEY 등이 os.environ.get()으로 읽히도록)
try:
    from dotenv import load_dotenv
    _env_file = _root / ".env"
    if _env_file.exists():
        load_dotenv(_env_file)
except Exception:
    pass

import streamlit as st

from web.utils.global_style import inject_global_style, page_header


def main() -> None:
    """메인 엔트리포인트."""
    st.set_page_config(
        page_title="29CM 데이터 수집 컨트롤 패널",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="auto",
    )
    inject_global_style()

    # OAuth 콜백: Google 로그인 후 리다이렉트되면 code로 토큰 교환
    if st.query_params.get("code"):
        try:
            from web.utils import google_oauth
            code = st.query_params.get("code", "")
            ok, msg = google_oauth.exchange_code_for_tokens(code=code)
            if ok:
                try:
                    for key in list(st.query_params.keys()):
                        del st.query_params[key]
                except Exception:
                    pass
                st.success(msg)
                st.info("설정 → Google Sheet 연동에서 **Google Sheet로 자동 전송**을 사용할 수 있습니다.")
                st.rerun()
            else:
                st.error("Google 연동 실패: " + msg)
        except Exception as e:
            st.error("Google 연동 처리 중 오류: " + str(e))

    page_header("29CM 데이터 수집", "브랜드 포지셔닝 맵 구축을 위한 **데이터 수집 · PDF 분석 · 리뷰**를 한 곳에서 관리합니다.")

    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container():
            st.markdown("#### 📄 PDF 분석")
            st.caption("수집한 PDF에서 상품 정보를 추출하고, Gemini로 상세 필드를 채웁니다.")
    with col2:
        with st.container():
            st.markdown("#### ✏️ PDF 상품 리뷰")
            st.caption("항목별 분석 결과를 검토·편집하고 대표 이미지를 확인합니다.")
    with col3:
        with st.container():
            st.markdown("#### 📊 결과 리포트")
            st.caption("데이터 기반 브랜드 맵과 AI 종합 분석 결과를 확인합니다.")

    st.markdown("---")
    st.caption("왼쪽 사이드바에서 원하는 메뉴를 선택하세요.")


if __name__ == "__main__":
    main()

