"""
애플리케이션 설정 모듈
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# 프로젝트 루트: shared/config/settings.py -> config -> shared -> 루트
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """애플리케이션 설정"""

    # Supabase 설정
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None  # 익명 키 (클라이언트 사이드)
    supabase_service_key: Optional[str] = None  # 서비스 키 (서버 사이드, 선택사항)

    # Storage 설정
    supabase_storage_bucket: str = "product-images"

    # 로컬 파일 저장 경로
    local_image_dir: Path = Path("images")
    log_dir: Path = Path("logs")

    # 로깅 설정
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # 브라우저 설정 (Agent용)
    browser_headless: bool = False
    browser_timeout: int = 30000  # 30초

    # 인간 행동 모사 설정
    min_delay_seconds: float = 0.5
    max_delay_seconds: float = 2.0

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 필수 설정 검증
        if not self.supabase_url or self.supabase_url == "your_supabase_url_here":
            raise ValueError(
                "SUPABASE_URL이 설정되지 않았습니다. "
                ".env 파일에 실제 Supabase URL을 입력하세요. "
                "예: SUPABASE_URL=https://your-project.supabase.co"
            )
        if not self.supabase_key or self.supabase_key == "your_supabase_anon_key_here":
            raise ValueError(
                "SUPABASE_KEY가 설정되지 않았습니다. "
                ".env 파일에 실제 Supabase Anon Key를 입력하세요. "
                "Supabase 대시보드 > Settings > API에서 확인할 수 있습니다."
            )
        # 디렉토리 자동 생성
        self.local_image_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """설정 인스턴스 싱글톤"""
    return Settings()
