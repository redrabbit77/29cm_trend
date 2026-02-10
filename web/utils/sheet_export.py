"""Google Sheet로 PDF 분석 결과 전송. OAuth(Google 로그인) 우선, 없으면 Service Account."""
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SETTINGS_DIR = _PROJECT_ROOT / "data" / "settings"
GOOGLE_CRED_PATH = SETTINGS_DIR / "google_sheets_credentials.json"


def _get_google_credentials_path() -> str | None:
    p = SETTINGS_DIR / "google_sheets_cred_path.txt"
    if p.exists():
        path = p.read_text(encoding="utf-8").strip()
        if path and Path(path).exists():
            return path
    if GOOGLE_CRED_PATH.exists():
        return str(GOOGLE_CRED_PATH)
    import os
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if path and Path(path).exists():
        return path
    return None


def _get_gspread_client_with_oauth():
    """OAuth(Google 로그인)으로 gspread 클라이언트 생성. 실패 시 None."""
    try:
        from web.utils import google_oauth
        if not google_oauth.is_oauth_ready():
            return None
        credentials = google_oauth.get_oauth_client_config()
        authorized = google_oauth.get_oauth_authorized_user()
        if not credentials or not authorized:
            return None
        import gspread
        gc, _ = gspread.oauth_from_dict(
            credentials=credentials,
            authorized_user_info=authorized,
        )
        return gc
    except Exception:
        return None


def push_pdf_analysis_to_sheet(export_cols: list, export_rows: list) -> tuple[bool, str]:
    """PDF 분석 결과를 Google Sheet에 업로드. OAuth 연동 시 그대로 사용, 없으면 Service Account."""
    gc = None
    # 1) OAuth(설정에서 Google ID/비밀번호 + 로그인) 우선
    gc = _get_gspread_client_with_oauth()
    # 2) 없으면 Service Account
    if not gc:
        cred_path = _get_google_credentials_path()
        if not cred_path:
            return False, "설정에서 **간단 연동**으로 Google Client ID·Secret 저장 후 **Google 로그인**을 하거나, Service Account JSON을 등록하세요."
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            creds = Credentials.from_service_account_file(cred_path, scopes=scopes)
            gc = gspread.authorize(creds)
        except ImportError:
            return False, "gspread 설치 필요: pip install gspread google-auth"
        except Exception as e:
            return False, str(e)

    try:
        sheet_id_path = SETTINGS_DIR / "google_sheet_id.txt"
        if sheet_id_path.exists():
            sheet_id = sheet_id_path.read_text(encoding="utf-8").strip()
            if sheet_id:
                sh = gc.open_by_key(sheet_id)
            else:
                sh = gc.create("PDF 분석 결과 (29CM)")
                sheet_id_path.write_text(sh.id, encoding="utf-8")
        else:
            sh = gc.create("PDF 분석 결과 (29CM)")
            SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
            sheet_id_path.write_text(sh.id, encoding="utf-8")
        worksheet = sh.sheet1
        rows = [export_cols] + [[str(row.get(c, "")) for c in export_cols] for row in export_rows]
        worksheet.clear()
        worksheet.update(rows, value_input_option="USER_ENTERED")
        return True, f"시트에 {len(export_rows)}행 반영됨. (Sheet ID: {sh.id})"
    except Exception as e:
        return False, str(e)
