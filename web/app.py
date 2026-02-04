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

from shared.config import get_settings


def render_sidebar() -> None:
    """공통 사이드바 렌더링."""
    settings = get_settings()

    st.sidebar.title("29CM Scraper")
    st.sidebar.markdown("**Mode**: Web Control Plane")
    st.sidebar.markdown("**Phase**: 2 - Web UI")

    with st.sidebar.expander("Environment", expanded=False):
        st.write(f"Supabase URL: `{settings.supabase_url}`")
        st.write(f"Storage bucket: `{settings.supabase_storage_bucket}`")

    st.sidebar.markdown("---")
    st.sidebar.markdown("페이지는 상단 탭 또는 좌측 메뉴에서 선택하세요.")


def main() -> None:
    """메인 엔트리포인트."""
    st.set_page_config(
        page_title="29CM 데이터 수집 컨트롤 패널",
        page_icon="📊",
        layout="wide",
    )

    render_sidebar()

    st.title("29CM 데이터 수집 컨트롤 패널")
    st.markdown(
        """
        이 대시보드는 29CM 브랜드 포지셔닝 맵 구축을 위한
        **데이터 수집 작업 제어 및 시각화**를 제공합니다.

        좌측 사이드바 또는 상단의 페이지 탭에서 기능을 선택하세요.
        """
    )

    st.info(
        "상단의 `pages/collection.py`, `pages/dashboard.py`, "
        "`pages/visualization.py` 페이지에서 구체적인 기능을 구현할 예정입니다."
    )


if __name__ == "__main__":
    main()

