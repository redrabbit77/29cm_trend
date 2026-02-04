"""
Supabase 클라이언트 래퍼
"""
import importlib
import sys
from typing import TYPE_CHECKING, Optional

# 페이지 스크립트가 app.py 없이 로드될 수 있으므로, 이 모듈 로드 시점에 site-packages 우선 적용
def _ensure_site_packages_first():
    if getattr(_ensure_site_packages_first, "_done", False):
        return
    try:
        import site
        packs = getattr(site, "getsitepackages", lambda: [])() or []
        for sp in packs:
            if sp and sp not in sys.path:
                sys.path.insert(0, sp)
                break
    except Exception:
        pass
    _ensure_site_packages_first._done = True

_ensure_site_packages_first()

if TYPE_CHECKING:
    from supabase import Client

_client: Optional["Client"] = None
_service_client: Optional["Client"] = None
_settings = None


def _get_settings():
    """설정을 지연 로딩"""
    global _settings
    if _settings is None:
        from shared.config import get_settings
        _settings = get_settings()
    return _settings


def _get_create_client():
    """create_client 함수를 설치된 패키지에서만 로드 (경로 강제)"""
    # 잘못 로드된 supabase 캐시 제거
    for k in list(sys.modules):
        if k == "supabase" or k.startswith("supabase."):
            del sys.modules[k]
    # 설치된 supabase가 있는 site-packages를 sys.path 맨 앞에 두기
    site_packages = None
    try:
        from importlib.metadata import distribution
        dist = distribution("supabase")
        pkg_dir = dist.locate_file("supabase/__init__.py").resolve().parent
        site_packages = str(pkg_dir.parent)
    except Exception:
        try:
            import site
            packs = getattr(site, "getsitepackages", lambda: [])() or []
            if packs:
                site_packages = packs[0]
        except Exception:
            pass
    if site_packages:
        if site_packages in sys.path:
            sys.path.remove(site_packages)
        sys.path.insert(0, site_packages)
    # 1) supabase._sync.client 에서 create_client 로드
    try:
        sync_client = importlib.import_module("supabase._sync.client")
        create_client_func = getattr(sync_client, "create_client", None)
        if create_client_func is not None:
            return create_client_func
    except ImportError:
        pass
    # 2) supabase 최상위에서 로드
    try:
        supabase_module = importlib.import_module("supabase")
        create_client_func = getattr(supabase_module, "create_client", None)
        if create_client_func is not None:
            return create_client_func
    except (AttributeError, ImportError):
        pass
    raise ImportError(
        "Supabase 패키지에서 create_client를 가져올 수 없습니다. "
        "pip install supabase 를 실행한 뒤, 프로젝트 루트에 'supabase' 이름의 파일/폴더가 없는지 확인하세요."
    )


def create_supabase_client(use_service_key: bool = False) -> "Client":
    """
    Supabase 클라이언트 생성

    Args:
        use_service_key: True면 서비스 키 사용, False면 익명 키 사용

    Returns:
        Supabase 클라이언트 인스턴스
    """
    global _client, _service_client
    
    create_client = _get_create_client()
    settings = _get_settings()

    if use_service_key:
        if _service_client is None:
            if not settings.supabase_service_key:
                raise ValueError(
                    "서비스 키가 설정되지 않았습니다. SUPABASE_SERVICE_KEY 환경 변수를 설정하세요."
                )
            _service_client = create_client(
                settings.supabase_url, settings.supabase_service_key
            )
        return _service_client
    else:
        if _client is None:
            _client = create_client(settings.supabase_url, settings.supabase_key)
        return _client


def get_supabase_client(use_service_key: bool = False) -> "Client":
    """
    Supabase 클라이언트 인스턴스 반환 (싱글톤)

    Args:
        use_service_key: True면 서비스 키 사용, False면 익명 키 사용

    Returns:
        Supabase 클라이언트 인스턴스
    """
    return create_supabase_client(use_service_key=use_service_key)
