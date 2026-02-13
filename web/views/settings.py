"""
설정 페이지: .env 편집·저장, Google Sheet 연동(자동 전송용) 설정.
"""
from pathlib import Path
import os
import sys

import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

ENV_PATH = _PROJECT_ROOT / ".env"
SETTINGS_DIR = _PROJECT_ROOT / "data" / "settings"
GOOGLE_CRED_PATH = SETTINGS_DIR / "google_sheets_credentials.json"
EXPORT_DIR_PATH = SETTINGS_DIR / "export_dir.txt"


def _load_env_content() -> str:
    if not ENV_PATH.exists():
        return ""
    try:
        return ENV_PATH.read_text(encoding="utf-8")
    except Exception:
        return ""


def _save_env_content(content: str) -> None:
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    ENV_PATH.write_text(content, encoding="utf-8")


def _load_google_cred_path() -> str:
    """저장된 Google Service Account JSON 경로 또는 내용 경로."""
    p = SETTINGS_DIR / "google_sheets_cred_path.txt"
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")


def _save_google_cred_path(path: str) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    (SETTINGS_DIR / "google_sheets_cred_path.txt").write_text(path.strip(), encoding="utf-8")


def _load_export_dir() -> str:
    """CSV / 엑셀 등 결과 파일 기본 저장 경로."""
    if EXPORT_DIR_PATH.exists():
        return EXPORT_DIR_PATH.read_text(encoding="utf-8").strip()
    # 기본값: 프로젝트 루트의 exports 폴더
    return str(_PROJECT_ROOT / "exports")


def _save_export_dir(path: str) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR_PATH.write_text(path.strip(), encoding="utf-8")


def render() -> None:
    try:
        from web.utils.global_style import inject_global_style, page_header
        inject_global_style()
    except Exception:
        pass

    page_header("설정", ".env 편집 및 Google Sheet 연동 설정.")

    st.markdown("## .env 편집")
    st.caption("프로젝트 루트의 .env 파일 내용을 편집하고 저장합니다. API 키·Supabase 등이 포함될 수 있으니 유의하세요.")
    env_content = st.text_area(
        ".env 내용",
        value=_load_env_content(),
        height=280,
        key="settings_env_content",
        label_visibility="collapsed",
    )
    if st.button(".env 저장", key="settings_save_env"):
        try:
            _save_env_content(env_content)
            st.success("저장되었습니다. 앱을 재시작하면 새 값이 적용됩니다.")
        except Exception as e:
            st.error(f"저장 실패: {e}")

    st.markdown("---")
    st.markdown("## Google Sheet 연동 (PDF 분석 결과 자동 전송)")

    # ----- 간단 연동: Google ID / 비밀번호 + 로그인 한 번 -----
    try:
        from web.utils import google_oauth
        oauth_ready = google_oauth.is_oauth_ready()
        oauth_client_ok = google_oauth.get_oauth_client_config() is not None
    except Exception:
        oauth_ready = False
        oauth_client_ok = False

    st.markdown("### 간단 연동 (Google 로그인)")
    st.caption("Google Cloud 콘솔에서 OAuth 2.0 클라이언트 ID(데스크톱 앱)를 만든 뒤, 아래 Client ID·비밀번호를 입력하고 **Google 로그인**을 한 번 하면 시트 전송을 사용할 수 있습니다. (Service Account JSON 없이 가능)")
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)

    oauth_client_path = SETTINGS_DIR / "google_oauth_client.json"
    _oauth_data = {}
    if oauth_client_path.exists():
        try:
            import json
            d = json.loads(oauth_client_path.read_text(encoding="utf-8"))
            if isinstance(d.get("installed"), dict):
                _oauth_data = d["installed"]
            elif d.get("client_id") or d.get("client_secret"):
                _oauth_data = d
        except Exception:
            pass

    oauth_cid = st.text_input(
        "Google OAuth Client ID",
        value=_oauth_data.get("client_id", ""),
        placeholder="xxxxx.apps.googleusercontent.com",
        key="settings_oauth_client_id",
        type="default",
    )
    oauth_secret = st.text_input(
        "Google OAuth Client Secret",
        value=_oauth_data.get("client_secret", ""),
        placeholder="GOCSPX-...",
        key="settings_oauth_client_secret",
        type="password",
    )
    if st.button("Client ID/Secret 저장", key="settings_save_oauth_client"):
        if oauth_cid.strip() and oauth_secret.strip():
            import json
            client_json = {
                "client_id": oauth_cid.strip(),
                "client_secret": oauth_secret.strip(),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            oauth_client_path.write_text(json.dumps(client_json, indent=2), encoding="utf-8")
            st.success("저장되었습니다. 아래 **Google 로그인** 링크를 클릭해 계정을 연동하세요.")
            st.rerun()
        else:
            st.warning("Client ID와 Client Secret을 모두 입력하세요.")

    if oauth_client_ok:
        auth_url, auth_err = google_oauth.build_authorization_url()
        if auth_url:
            st.markdown("**Google 로그인** (한 번만 하면 됨)")
            st.markdown(f"[🔗 여기를 클릭해 Google 계정으로 로그인]({auth_url})")
            st.caption("로그인 후 이 앱으로 돌아오면 연동이 완료됩니다. 리다이렉트 URI에 http://localhost:8501/ 를 등록해 두세요.")
        else:
            st.caption(f"인증 URL 생성 실패: {auth_err}")
        if oauth_ready:
            st.success("✅ Google 계정 연동됨 — PDF 분석 결과를 **Google Sheet로 자동 전송**할 수 있습니다.")
        else:
            st.info("위 링크로 로그인하면 시트 자동 전송이 가능해집니다.")
    else:
        st.caption("Client ID·Secret을 입력하고 저장하면 Google 로그인 링크가 나타납니다.")

    st.markdown("---")
    st.markdown("### Service Account 방식 (선택)")
    st.caption("Service Account JSON 파일 경로를 지정해도 PDF 분석 결과를 Google Sheet로 자동 전송할 수 있습니다. 위 간단 연동을 쓰면 생략 가능합니다.")
    cred_path = st.text_input(
        "Service Account JSON 파일 경로",
        value=_load_google_cred_path(),
        placeholder="예: C:\\path\\to\\credentials.json 또는 data/settings/google_sheets_credentials.json",
        key="settings_google_cred_path",
    )
    if st.button("경로 저장", key="settings_save_google_path"):
        _save_google_cred_path(cred_path)
        st.success("저장되었습니다.")

    st.caption("또는 아래에 JSON 내용을 붙여넣으면 data/settings/google_sheets_credentials.json 으로 저장됩니다.")
    cred_json = st.text_area("Service Account JSON 붙여넣기", height=120, key="settings_google_json")
    if st.button("JSON 저장", key="settings_save_google_json"):
        if cred_json.strip():
            try:
                import json
                json.loads(cred_json)  # 검증
                GOOGLE_CRED_PATH.write_text(cred_json, encoding="utf-8")
                st.success("저장되었습니다.")
            except json.JSONDecodeError as e:
                st.error(f"JSON 형식 오류: {e}")
            except Exception as e:
                st.error(f"저장 실패: {e}")
        else:
            st.warning("JSON 내용을 입력하세요.")

    sheet_id_path = SETTINGS_DIR / "google_sheet_id.txt"
    current_sheet_id = sheet_id_path.read_text(encoding="utf-8").strip() if sheet_id_path.exists() else ""
    sheet_id_input = st.text_input(
        "Google Sheet ID (비우면 첫 전송 시 새 시트 생성)",
        value=current_sheet_id,
        placeholder="예: 1ABC... 시트 URL의 /d/ 다음 부분",
        key="settings_sheet_id",
    )
    if st.button("Sheet ID 저장", key="settings_save_sheet_id"):
        if sheet_id_input.strip():
            sheet_id_path.write_text(sheet_id_input.strip(), encoding="utf-8")
            st.success("저장되었습니다.")
        else:
            if sheet_id_path.exists():
                sheet_id_path.unlink()
            st.success("Sheet ID를 비웠습니다. 다음 전송 시 새 시트가 생성됩니다.")

    st.markdown("---")
    st.markdown("## 결과 파일 저장 경로 (CSV / 엑셀)")
    st.caption("PDF 분석 결과 CSV·엑셀(.xlsx)을 서버에서 자동으로 저장할 기본 폴더를 지정합니다. Mac / iPhone 등에서 공유 폴더를 열어볼 때 유용합니다.")
    export_dir = st.text_input(
        "결과 파일 저장 폴더 경로",
        value=_load_export_dir(),
        placeholder=r"예: D:\29CMTREND\exports 또는 \\SERVER\share\29cm_exports",
        key="settings_export_dir",
    )
    if st.button("저장 경로 저장", key="settings_save_export_dir"):
        try:
            p = Path(export_dir).expanduser()
            p.mkdir(parents=True, exist_ok=True)
            _save_export_dir(str(p))
            st.success(f"저장되었습니다. 이후 CSV/엑셀 내보내기 시 이 폴더에도 함께 저장됩니다. ({p})")
        except Exception as e:
            st.error(f"폴더 생성/저장 실패: {e}")


render()
