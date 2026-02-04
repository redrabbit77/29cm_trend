"""
Streamlit 전용 설정/헬퍼
"""
from functools import lru_cache

from shared.config import Settings, get_settings


@lru_cache()
def get_app_settings() -> Settings:
    """앱 설정 반환 (캐시)"""
    return get_settings()


APP_TITLE = "29CM 데이터 수집 컨트롤 패널"
APP_ICON = "📊"

