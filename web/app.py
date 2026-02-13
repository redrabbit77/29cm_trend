"""
Streamlit 메인 앱 진입점 및 네비게이션 설정
"""
import sys
import site
from pathlib import Path
import streamlit as st

# 경로 설정
for _sp in (getattr(site, "getsitepackages", lambda: [])() or []):
    if _sp and _sp not in sys.path:
        sys.path.insert(0, _sp)
        break

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# .env 로드
try:
    from dotenv import load_dotenv
    _env_file = _root / ".env"
    if _env_file.exists():
        load_dotenv(_env_file)
except Exception:
    pass

# 공통 스타일 주입 (여기서 미리 로드)
try:
    from web.utils.global_style import inject_global_style
except ImportError:
    pass

# 페이지 정의
# 주의: 경로는 이 파일을 실행하는 위치(프로젝트 루트)가 아니라, 이 파일(web/app.py) 기준 상대 경로 또는 프로젝트 루트 기준일 수 있음.
# streamlit run web/app.py 로 실행 시 CWD는 프로젝트 루트임.
# 따라서 "web/views/..." 형태로 지정.

# 절대 경로로 변환하여 사용 (안전한 방법)
base_dir = Path(__file__).parent.resolve()
views_dir = base_dir / "views"

pages = {
    "App": [
        st.Page(str(views_dir / "home.py"), title="Home", icon="🏠"),
        st.Page(str(views_dir / "result_report.py"), title="Result Report", icon="📊"),
        st.Page(str(views_dir / "brand_review.py"), title="Brand Review", icon="⭐"),
        st.Page(str(views_dir / "pdf_item_review.py"), title="Item Review", icon="✏️"),
    ],
    "Data Collection": [
        st.Page(str(views_dir / "collection.py"), title="Collection", icon="📥"),
        st.Page(str(views_dir / "pdf_analysis.py"), title="PDF Analysis", icon="📄"),
        st.Page(str(views_dir / "settings.py"), title="Settings", icon="⚙️"),
    ],
}

st.set_page_config(
    page_title="29CM 데이터 수집 컨트롤 패널",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="auto",
)

try:
    inject_global_style()
except Exception:
    pass

pg = st.navigation(pages)
pg.run()
