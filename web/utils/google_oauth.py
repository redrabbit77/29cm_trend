"""
Google OAuth2 (로그인 한 번으로 시트 API 사용).
- 인증 URL 생성, 콜백에서 code → 토큰 교환 후 저장.
- sheet_export에서 이 토큰으로 gspread 사용.
"""
from pathlib import Path
import json
import os

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SETTINGS_DIR = _PROJECT_ROOT / "data" / "settings"
OAUTH_CLIENT_FILE = SETTINGS_DIR / "google_oauth_client.json"
OAUTH_AUTHORIZED_FILE = SETTINGS_DIR / "google_oauth_authorized_user.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Streamlit 기본 URL (리다이렉트 URI). Google Cloud 콘솔에 이 주소를 등록해야 함.
DEFAULT_REDIRECT_URI = "http://localhost:8501/"


def get_oauth_client_config() -> dict | None:
    """OAuth 클라이언트 설정 (client_id, client_secret 등). 파일 또는 env에서 로드."""
    if OAUTH_CLIENT_FILE.exists():
        try:
            data = json.loads(OAUTH_CLIENT_FILE.read_text(encoding="utf-8"))
            if isinstance(data.get("installed"), dict):
                return data
            if data.get("client_id") and data.get("client_secret"):
                return {
                    "installed": {
                        "client_id": data["client_id"],
                        "client_secret": data["client_secret"],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                }
        except Exception:
            pass
    cid = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    if cid and secret:
        return {
            "installed": {
                "client_id": cid,
                "client_secret": secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
    return None


def get_oauth_authorized_user() -> dict | None:
    """저장된 사용자 토큰(refresh_token 등)."""
    if not OAUTH_AUTHORIZED_FILE.exists():
        return None
    try:
        return json.loads(OAUTH_AUTHORIZED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_oauth_authorized_user(info: dict) -> None:
    """인증 후 받은 토큰 정보 저장 (gspread oauth_from_dict 호환 형식)."""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    OAUTH_AUTHORIZED_FILE.write_text(json.dumps(info, indent=2), encoding="utf-8")


def build_authorization_url(redirect_uri: str | None = None) -> tuple[str | None, str]:
    """
    Google 로그인 링크 URL 생성.
    반환: (url, error_message). url이 None이면 error_message에 이유.
    """
    redirect_uri = redirect_uri or DEFAULT_REDIRECT_URI
    config = get_oauth_client_config()
    if not config:
        return None, "OAuth 클라이언트가 없습니다. 설정에서 Client ID / Client Secret을 입력하세요."
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_config(
            config, SCOPES, redirect_uri=redirect_uri
        )
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            include_granted_scopes="true",
        )
        return auth_url, ""
    except ImportError:
        return None, "google-auth-oauthlib 설치 필요: pip install google-auth-oauthlib"
    except Exception as e:
        return None, str(e)


def exchange_code_for_tokens(
    code: str,
    redirect_uri: str | None = None,
    full_redirect_url: str | None = None,
) -> tuple[bool, str]:
    """
    인증 코드를 액세스/리프레시 토큰으로 교환하고 저장.
    full_redirect_url: 브라우저가 리다이렉트된 전체 URL (state 등 포함 시 검증용). 없으면 code만 사용.
    반환: (성공 여부, 메시지)
    """
    redirect_uri = redirect_uri or DEFAULT_REDIRECT_URI
    config = get_oauth_client_config()
    if not config:
        return False, "OAuth 클라이언트 설정이 없습니다."
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_config(
            config, SCOPES, redirect_uri=redirect_uri
        )
        if full_redirect_url:
            flow.fetch_token(authorization_response=full_redirect_url)
        else:
            flow.fetch_token(code=code)
        creds = flow.credentials
        # gspread oauth_from_dict 호환 형식으로 저장
        authorized = {
            "token": getattr(creds, "token", None) or "",
            "refresh_token": getattr(creds, "refresh_token") or "",
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes) if creds.scopes else SCOPES,
            "expiry": (creds.expiry.isoformat() if getattr(creds, "expiry", None) else "") or "",
        }
        save_oauth_authorized_user(authorized)
        return True, "Google 계정 연동이 완료되었습니다. 이제 시트 자동 전송을 사용할 수 있습니다."
    except ImportError:
        return False, "google-auth-oauthlib 설치 필요: pip install google-auth-oauthlib"
    except Exception as e:
        return False, str(e)


def is_oauth_ready() -> bool:
    """OAuth로 시트 API 사용 가능 여부 (클라이언트 + 사용자 토큰 모두 있음)."""
    return get_oauth_client_config() is not None and get_oauth_authorized_user() is not None
