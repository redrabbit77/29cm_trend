"""
PDF 분석 결과 페이지: 수집 PDF → 텍스트 추출 → 규칙 기반 구조화 → 표시.
분석 실행 시 PDF 한 건씩 처리 후 화면 갱신으로 진행 상황을 실시간 표시.
"""
from pathlib import Path
import json
import sys

import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 기본값: 수집 페이지의 "PDF 저장 폴더"와 동일하게 맞추면 됨
DEFAULT_PDF_BASE = _PROJECT_ROOT / "pdfs"
OUTPUT_DIR = _PROJECT_ROOT / "data" / "pdf_analysis"
JSON_PATH = OUTPUT_DIR / "pdf_products.json"
PDF_BASE_PATH_FILE = _PROJECT_ROOT / "data" / "pdf_base_path.txt"
UI_CONFIG_PATH = OUTPUT_DIR / "pdf_analysis_ui_config.json"
SETTINGS_DIR = _PROJECT_ROOT / "data" / "settings"
EXPORT_DIR_PATH = SETTINGS_DIR / "export_dir.txt"

GEMINI_MODEL_OPTIONS = [
    "Pro (gemini-3-pro-preview)",
    "3.0 Flash (gemini-3-flash-preview)",
    "2.0 Flash (gemini-2.0-flash)",
]


def _get_saved_ui_config() -> dict:
    """저장된 분석 옵션 복원. 리프레시 후에도 유지."""
    if not UI_CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(UI_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_ui_config(config: dict) -> None:
    """분석 옵션 저장."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    UI_CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_export_dir() -> Path:
    """CSV / 엑셀 결과를 서버에 함께 저장할 폴더."""
    try:
        if EXPORT_DIR_PATH.exists():
            raw = EXPORT_DIR_PATH.read_text(encoding="utf-8").strip()
            if raw:
                p = Path(raw).expanduser()
                p.mkdir(parents=True, exist_ok=True)
                return p
    except Exception:
        pass
    # 기본값: 프로젝트 루트/exports
    p = _PROJECT_ROOT / "exports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _get_saved_pdf_base() -> str:
    """수집 시 지정한 PDF 저장 경로. 없으면 기본값(상대 경로 pdfs) 반환."""
    if PDF_BASE_PATH_FILE.exists():
        try:
            return PDF_BASE_PATH_FILE.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return "pdfs"


def _resolve_pdf_base(raw: str) -> Path:
    """상대 경로면 프로젝트 루트 기준, 절대 경로면 그대로."""
    p = Path(raw.strip()) if raw else DEFAULT_PDF_BASE
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    return p.resolve()

KEY_RUNNING = "pdf_analysis_running"
KEY_FILES = "pdf_analysis_files"
KEY_INDEX = "pdf_analysis_index"
KEY_RESULTS = "pdf_analysis_results"
KEY_CONFIG = "pdf_analysis_config"
KEY_CHECKED = "pdf_analysis_checked"  # 체크된 파일 인덱스 목록 (0-based)

PDF_ANALYSIS_KEYS = [
    "source_pdf", "상품명", "브랜드명", "상세_카테고리명", "의류종류", "가격", "소재", "케어방법",
    "사이즈", "사이즈_상세", "색상",
    "이미지_무드", "이미지_톤", "이미지_배경", "사진_구성", "모델_특징", "제품_특징", "브랜드_평", "이미지_요약",
    "톤_무드", "촬영_특징", "룩북_촬영_배경_무드", "모델링_포즈_특징", "컬러_팔레트", "디자인_컨셉_분석",
    "상세_리뷰", "리뷰_의견",
    "스타일_축", "프리미엄_축", "대표색",
]


def _is_review(p: Path) -> bool:
    return "_review" in p.name.lower() or p.name.lower().endswith("review.pdf")


def _get_pdf_korean_font() -> str:
    """한글이 나오는 PDF용 폰트 등록. 등록 성공 시 폰트명, 실패 시 Helvetica."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        candidates = [
            ("Malgun", "C:/Windows/Fonts/malgun.ttf"),
            ("Malgun", "C:\\Windows\\Fonts\\malgun.ttf"),
            ("AppleGothic", "/System/Library/Fonts/AppleSDGothicNeo.ttc"),
            ("NanumGothic", str(_PROJECT_ROOT / "fonts" / "NanumGothic.ttf")),
        ]
        for name, path in candidates:
            if Path(path).exists():
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                    return name
                except Exception:
                    continue
        return "Helvetica"
    except Exception:
        return "Helvetica"


def _run_one_and_maybe_finish() -> str | None:
    """현재 인덱스 PDF 1건 처리. 완료 시 JSON/CSV 저장 후 상태 초기화."""
    import json
    import csv
    try:
        from analysis.pdf_parser import analyze_pdf
        import logging
        logging.getLogger("pdfminer").setLevel(logging.WARNING)
    except ImportError as e:
        return f"모듈 로드 실패: {e}"

    files = st.session_state.get(KEY_FILES) or []
    idx = st.session_state.get(KEY_INDEX, 0)
    results = st.session_state.get(KEY_RESULTS) or []
    config = st.session_state.get(KEY_CONFIG) or {}

    if idx >= len(files):
        return "인덱스 오류"

    pdf_base = Path(config.get("pdf_base", str(DEFAULT_PDF_BASE)))
    pdf_path = pdf_base / files[idx]
    delay_sec = max(0, int(config.get("request_delay_sec", 4)))
    if delay_sec > 0 and idx > 0:
        import time
        time.sleep(delay_sec)
    try:
        row = analyze_pdf(
            pdf_path,
            base_dir=pdf_base,
            use_llm=config.get("use_llm", False),
            use_gemini=config.get("use_gemini", True),
            use_gemini_vision=config.get("use_gemini_vision", False),
            gemini_model=config.get("gemini_model"),
        )
        results.append(row)
    except Exception as e:
        # 예외 시에도 rule_based로 최소 데이터 추출해 저장 (빈 행 방지)
        try:
            from analysis.pdf_parser import extract_text_from_pdf, parse_product_from_text
            text = extract_text_from_pdf(pdf_path)
            source = str(files[idx]).replace("\\", "/")
            row = parse_product_from_text(text, source_pdf=source)
            if "/" in source:
                row["상세_카테고리명"] = row.get("상세_카테고리명") or source.split("/")[0]
            for key in (
                "의류종류", "이미지_무드", "이미지_톤", "이미지_배경", "이미지_요약",
                "사진_구성", "모델_특징", "제품_특징", "브랜드_평",
                "톤_무드", "촬영_특징", "룩북_촬영_배경_무드", "모델링_포즈_특징", "컬러_팔레트", "디자인_컨셉_분석", "상세_리뷰",
            ):
                row.setdefault(key, "")
            row["_analysis_engine"] = "rule_based"
            row["_analysis_error"] = str(e)[:200]
        except Exception:
            row = {
                "source_pdf": files[idx],
                "상품명": Path(files[idx]).stem or files[idx],
                "브랜드명": "", "상세_카테고리명": "", "의류종류": "", "가격": None,
                "소재": "", "케어방법": "", "사이즈": [], "사이즈_상세": "", "색상": [],
                "이미지_무드": "", "이미지_톤": "", "이미지_배경": "", "사진_구성": "", "모델_특징": "", "제품_특징": "", "브랜드_평": "", "이미지_요약": "",
                "톤_무드": "", "촬영_특징": "", "룩북_촬영_배경_무드": "", "모델링_포즈_특징": "", "컬러_팔레트": "", "디자인_컨셉_분석": "", "상세_리뷰": "",
            }
            row["_analysis_engine"] = "rule_based"
            row["_analysis_error"] = str(e)[:200]
        results.append(row)

    st.session_state[KEY_RESULTS] = results
    st.session_state[KEY_INDEX] = idx + 1

    if idx + 1 >= len(files):
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        csv_path = OUTPUT_DIR / "pdf_products.csv"
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=PDF_ANALYSIS_KEYS, extrasaction="ignore")
            w.writeheader()
            for r in results:
                row = {k: r.get(k, "") for k in PDF_ANALYSIS_KEYS if not k.startswith("_")}
                if isinstance(row.get("사이즈"), list):
                    row["사이즈"] = ",".join(str(x) for x in row["사이즈"])
                if isinstance(row.get("색상"), list):
                    row["색상"] = ",".join(str(x) for x in row["색상"])
                w.writerow(row)
        st.session_state[KEY_RUNNING] = False
        st.session_state["pdf_analysis_just_finished"] = True
        try:
            from shared.services.data_service import DataService
            from scripts.sync_pdf_analysis_to_db import sync_pdf_results_to_db
            created, db_errors = sync_pdf_results_to_db(results, DataService())
            st.session_state["pdf_analysis_db_sync"] = {"created": created, "errors": db_errors}
        except Exception as e:
            st.session_state["pdf_analysis_db_sync"] = {"created": 0, "errors": [str(e)]}
        for k in (KEY_FILES, KEY_INDEX, KEY_RESULTS, KEY_CONFIG):
            if k in st.session_state:
                del st.session_state[k]
    return None


def render() -> None:
    try:
        from web.utils.global_style import inject_global_style, page_header
        inject_global_style()
    except Exception:
        pass

    page_header("PDF 분석", "수집된 PDF에서 텍스트를 추출해 상품명·브랜드·가격·소재·케어·사이즈·색상 등을 구조화합니다. Gemini 또는 OpenAI로 상세 필드를 채울 수 있습니다.")

    # 분석 진행 중이면 맨 위에 진행 상태만 크게 표시 후 1건 처리하고 rerun
    if st.session_state.get(KEY_RUNNING):
        files = st.session_state.get(KEY_FILES) or []
        idx = st.session_state.get(KEY_INDEX, 0)
        total = len(files)
        # 진행률: 완료한 개수 / 전체. idx는 다음에 처리할 인덱스 = 완료 개수
        completed = min(idx, total)
        pct = (completed / total) if total else 0.0
        pct = min(1.0, max(0.0, float(pct)))
        current_name = files[idx] if idx < len(files) else ""

        st.markdown("---")
        st.markdown("### ⏳ PDF 분석 실행 중")
        prog_col1, prog_col2 = st.columns([2, 1])
        with prog_col1:
            st.caption(f"진행률 {completed}/{total}")
            # CSS가 기본 progress 바 너비를 덮어쓸 수 있어, 퍼센트를 직접 반영한 HTML progress 사용
            pct_pct = round(pct * 100, 1)
            st.markdown(
                f"""
                <div style="margin:0.25rem 0;">
                    <div style="background:#e2e8f0; border-radius:999px; height:1.25rem; overflow:hidden;">
                        <div style="width:{pct_pct}%; height:100%; background:linear-gradient(90deg,#2563eb,#3b82f6); border-radius:999px; transition:width 0.2s ease;"></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with prog_col2:
            st.metric("완료", f"{completed} / {total}", f"총 {total}건")
        st.info(f"**현재 처리 중:** `{current_name}`")
        st.caption("한 건씩 처리하며 화면이 자동으로 갱신됩니다. 잠시만 기다려 주세요.")
        st.markdown("---")

        err = _run_one_and_maybe_finish()
        if err:
            st.error(err)
        st.rerun()

    if st.session_state.get("pdf_analysis_just_finished"):
        st.success(f"분석이 완료되었습니다. 결과: {OUTPUT_DIR.relative_to(_PROJECT_ROOT)}")
        del st.session_state["pdf_analysis_just_finished"]
        sync_result = st.session_state.pop("pdf_analysis_db_sync", None)
        if sync_result:
            created, errs = sync_result.get("created", 0), sync_result.get("errors") or []
            if created > 0:
                st.success(f"Supabase DB 자동 반영 완료: **{created}건** 등록되었습니다.")
            if errs:
                st.warning(f"DB 반영 시 일부 오류({len(errs)}건): 브랜드명/카테고리 누락 등. 아래 'DB 반영' 버튼으로 재시도하거나 엔진/API 오류 상세를 확인하세요.")
                with st.expander("DB 반영 오류 목록", expanded=False):
                    for e in errs[:15]:
                        st.caption(e)
                    if len(errs) > 15:
                        st.caption(f"… 외 {len(errs) - 15}건")

    saved = _get_saved_ui_config()
    st.markdown("## 분석 옵션")
    col1, col2 = st.columns([1, 2])
    with col1:
        pdf_folder_default = _get_saved_pdf_base()
        pdf_folder_input = st.text_input(
            "PDF 폴더 경로",
            value=pdf_folder_default,
            help="한 번 지정하면 저장되어, 재변경하지 않으면 다음에도 그대로 재사용됩니다. 수집·분석 중 지정한 경로가 공통으로 적용됩니다.",
        )
        if st.button("경로 저장", key="pdf_path_save_analysis"):
            pdf_base = _resolve_pdf_base(pdf_folder_input)
            PDF_BASE_PATH_FILE.parent.mkdir(parents=True, exist_ok=True)
            PDF_BASE_PATH_FILE.write_text(str(pdf_base), encoding="utf-8")
            st.success(f"경로가 저장되었습니다: {pdf_base}")
            st.rerun()
        pdf_base = _resolve_pdf_base(pdf_folder_input)
        delay_default = saved.get("request_delay_sec", 4)
        request_delay_sec = st.number_input(
            "요청 간 대기(초)",
            min_value=0,
            value=int(delay_default),
            step=1,
            help="429 방지용. 유료 과금해도 RPM(분당 요청) 제한이 있어, 대기 0초면 한도 초과로 429가 날 수 있습니다. 4~6초 권장(분당 약 10~15건).",
        )
        rule_default = saved.get("use_rule_base_only", False)
        use_rule_base_only = st.checkbox(
            "Rule Base만 (AI 미사용)",
            value=bool(rule_default),
            help="체크 시 Gemini·OpenAI 호출 없이 규칙 기반 파싱만 사용. API 키·한도 없이 빠르게 분석.",
        )
        use_llm = st.checkbox("OpenAI LLM (OPENAI_API_KEY)", value=bool(saved.get("use_llm", False)), help="Gemini 미사용 시 OpenAI로 추출", disabled=use_rule_base_only)
        use_gemini = st.checkbox("Gemini (GEMINI_API_KEY)", value=bool(saved.get("use_gemini", True)), help="기본 데이터 추출 (텍스트)", disabled=use_rule_base_only)
        gemini_model_id_saved = saved.get("gemini_model_id", "gemini-3-pro-preview")
        gemini_index = 0
        if gemini_model_id_saved == "gemini-3-flash-preview":
            gemini_index = 1
        elif gemini_model_id_saved == "gemini-2.0-flash":
            gemini_index = 2
        gemini_model_label = st.radio(
            "Gemini 모델",
            GEMINI_MODEL_OPTIONS,
            index=gemini_index,
            horizontal=True,
            help="Pro: 고품질. 3.0 Flash: 빠르고 성능 좋음. 2.0 Flash: 한도 여유 있을 때.",
            disabled=use_rule_base_only,
        )
        if "3.0 Flash" in gemini_model_label:
            gemini_model_id = "gemini-3-flash-preview"
        elif "2.0 Flash" in gemini_model_label:
            gemini_model_id = "gemini-2.0-flash"
        else:
            gemini_model_id = "gemini-3-pro-preview"
        use_gemini_vision = st.checkbox("Gemini 이미지 분석", value=bool(saved.get("use_gemini_vision", False)), help="PDF 페이지 이미지 → 무드·촬영·배경 추출 (비용 증가)", disabled=use_rule_base_only)
        if use_rule_base_only:
            st.caption("**Rule Base만** 선택 시: PDF 텍스트 추출 후 규칙 기반으로 상품명·가격·소재·사이즈·색상 등을 파싱합니다. API 호출 없음.")
        else:
            st.caption("API가 호출되는지 확인하려면 아래 **Gemini API 연결 테스트**를 먼저 실행하세요.")

        # 진단: API 요청이 나가는지 미리 확인
        try:
            from analysis.gemini_extract import has_gemini_api_key
            key_ok = has_gemini_api_key()
        except Exception:
            key_ok = False
        will_call_api = not use_rule_base_only and use_gemini and key_ok
        st.markdown("---")
        st.caption("**진단: API 요청 여부**")
        st.caption(f"- **Gemini API 키:** {'설정됨' if key_ok else '미설정 (.env에 GEMINI_API_KEY 또는 GOOGLE_API_KEY 추가)'}")
        st.caption(f"- **다음 분석 시:** {'Gemini 요청이 나갑니다 (Google AI Studio 사용량에 반영됨)' if will_call_api else 'API 요청이 나가지 않습니다 (Rule Base만 사용 중이거나 API 키 미설정)'}")
        if not will_call_api and not use_rule_base_only and use_gemini:
            st.warning("Gemini를 사용하도록 되어 있으나 API 키가 없습니다. .env 파일에 GEMINI_API_KEY 또는 GOOGLE_API_KEY를 넣고 앱을 다시 실행하세요.")
        st.info("**톤_무드, 촬영_특징, 룩북_촬영_배경_무드** 등 추가 필드는 **Gemini 사용 시**에만 채워집니다. Rule Base만 사용하면 비어 있습니다. API 통계에 요청이 안 보이면 위 '진단'과 'Rule Base만' 해제 여부를 확인하세요.")
        st.caption("**429 Too Many Requests:** 유료 과금 후에도 **RPM(분당 요청)·TPM(분당 토큰)·RPD(일일 요청)** 제한이 있습니다. [AI Studio 사용량](https://aistudio.google.com/usage)에서 현재 한도 확인. 대기 시간을 4~6초로 올리거나, 모델을 2.0 Flash 등 한도 여유 있는 것으로 바꿔 보세요.")

        if st.button("옵션 저장", key="pdf_analysis_save_options"):
            _save_ui_config({
                "request_delay_sec": int(request_delay_sec),
                "use_rule_base_only": use_rule_base_only,
                "use_llm": use_llm,
                "use_gemini": use_gemini,
                "gemini_model_id": gemini_model_id,
                "use_gemini_vision": use_gemini_vision,
            })
            st.success("옵션이 저장되었습니다. 새로고침 후에도 복원됩니다.")
            st.rerun()

    st.markdown("## 분석 대상 PDF")
    all_pdfs = sorted(p for p in pdf_base.rglob("*.pdf") if not _is_review(p))
    if all_pdfs:
        total = len(all_pdfs)
        if KEY_CHECKED not in st.session_state or len(st.session_state.get(KEY_CHECKED, [])) != total:
            st.session_state[KEY_CHECKED] = [True] * total

        checked = st.session_state[KEY_CHECKED]

        st.caption("파일 범위와 체크박스로 분석할 PDF를 선택한 뒤 **PDF 분석 실행**을 누르세요.")
        range_start, range_end = st.slider(
            "분석 파일 범위 (시작 번호 ~ 끝 번호)",
            min_value=1,
            max_value=max(1, total),
            value=(1, total),
            step=1,
            help=f"1~{total}번 중 구간을 선택하세요. 선택한 구간 내에서 체크된 파일만 분석됩니다.",
            key="pdf_range_slider",
        )
        range_start = max(1, min(range_start, total))
        range_end = max(range_start, min(range_end, total))
        # 분석 실행 시 슬라이더 범위를 쓰기 위해 세션에 저장
        st.session_state["pdf_analysis_range"] = (range_start, range_end)

        # 체크박스 키에 버전 포함 → 전체 선택/해제 시 버전 올려서 위젯 재생성, 즉시 반영
        if "pdf_cb_version" not in st.session_state:
            st.session_state["pdf_cb_version"] = 0
        cb_version = st.session_state["pdf_cb_version"]

        # 범위 적용 / 전체 선택(전체 설정) / 전체 해제 버튼
        st.caption("**전체 선택**: 모든 파일 체크 · **전체 해제**: 모든 파일 체크 해제 · **범위만 선택**: 슬라이더 구간만 체크")
        btn_col1, btn_col2, btn_col3, _ = st.columns([1, 1, 1, 2])
        with btn_col1:
            if st.button("범위만 선택", key="apply_range"):
                st.session_state["pdf_cb_version"] = cb_version + 1
                for i in range(total):
                    checked[i] = (range_start - 1 <= i < range_end)
                st.session_state[KEY_CHECKED] = list(checked)
                st.rerun()
        with btn_col2:
            if st.button("전체 선택", key="select_all", help="모든 PDF를 분석 대상으로 체크"):
                st.session_state["pdf_cb_version"] = cb_version + 1
                st.session_state[KEY_CHECKED] = [True] * total
                st.rerun()
        with btn_col3:
            if st.button("전체 해제", key="deselect_all", help="모든 PDF 체크 해제"):
                st.session_state["pdf_cb_version"] = cb_version + 1
                st.session_state[KEY_CHECKED] = [False] * total
                st.rerun()

        # 리스트: 체크박스 + 파일명 (키에 버전 포함해 전체 선택/해제 후 값 확실히 반영)
        with st.expander("📁 분석 대상 PDF 목록 (체크로 개별 선택)", expanded=True):
            st.caption(f"총 {total}개 PDF · **슬라이더 범위 {range_start}~{range_end}번** 안에서 체크된 파일만 분석됩니다.")
            for i in range(range_start - 1, range_end):
                if i >= total:
                    break
                rel = all_pdfs[i].relative_to(pdf_base)
                c = st.checkbox(
                    f" {i+1}. {rel.as_posix()}",
                    value=checked[i],
                    key=f"pdf_cb_{i}_{cb_version}",
                )
                checked[i] = c
            st.session_state[KEY_CHECKED] = list(checked)

        selected_count = sum(1 for c in checked if c)
        st.caption(f"현재 **{selected_count}개** 파일이 분석 대상으로 선택되어 있습니다.")

        st.markdown("### PDF 수동 이미지 추출")
        st.caption("PDF 분석을 다시 실행하지 않고, **선택한 PDF**에서 대표/상세 **이미지 영역만** 추출합니다. 페이지 단위가 아니라 이미지만 캡처해 **상품 리뷰**의 썸네일·상세 이미지로 사용할 수 있습니다.")
        if st.button("선택 PDF에서 이미지만 추출", key="pdf_manual_image_extract"):
            selected_pdfs = [all_pdfs[i] for i in range(total) if checked[i]]
            if not selected_pdfs:
                st.warning("선택된 PDF가 없습니다. 위 목록에서 체크한 뒤 다시 누르세요.")
            else:
                try:
                    from analysis.gemini_extract import save_pdf_product_images
                    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                    done = 0
                    errors = []
                    n = len(selected_pdfs)
                    st.markdown("#### 이미지 추출 진행 상황")
                    status_box = st.empty()
                    progress = st.progress(0.0, text="이미지 추출 대기 중...")
                    with st.spinner("이미지 추출 중입니다. 아래 진행률을 확인하세요."):
                        for idx, pdf_path in enumerate(selected_pdfs, start=1):
                            try:
                                save_pdf_product_images(pdf_path, OUTPUT_DIR, max_pages=10, dpi=150)
                                done += 1
                            except Exception as e:
                                errors.append(f"{pdf_path.name}: {e}")
                            frac = idx / n
                            progress.progress(frac, text=f"{idx}/{n}개 처리 중...")
                            status_box.markdown(f"**{idx}/{n}개 처리 중** · `{pdf_path.name}`")
                    progress.progress(1.0, text="이미지 추출 완료")
                    status_box.markdown("✅ **이미지 추출이 완료되었습니다.**")
                    if done:
                        st.success(f"**{done}개** PDF에서 이미지 추출 완료. `data/pdf_analysis/product_images/` 에 저장되었습니다. **상품 리뷰**에서 썸네일·상세 이미지로 확인하세요.")
                    for err in errors[:5]:
                        st.warning(err)
                    if len(errors) > 5:
                        st.caption(f"외 {len(errors) - 5}건 오류 생략")
                except ImportError as e:
                    st.error("이미지 추출 모듈을 불러올 수 없습니다: " + str(e))
                except Exception as e:
                    st.error("추출 중 오류: " + str(e))

    if st.button("Gemini API 연결 테스트", key="gemini_test"):
        import importlib.util
        import sys
        if str(_PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(_PROJECT_ROOT))
        test_gemini_connection = None
        try:
            from analysis.gemini_extract import test_gemini_connection
        except ImportError:
            try:
                from analysis import test_gemini_connection
            except ImportError:
                pass
        if test_gemini_connection is None:
            # 프로젝트 analysis/gemini_extract.py 파일을 경로로 직접 로드 (다른 패키지에 가려질 때 대비)
            _gemini_path = _PROJECT_ROOT / "analysis" / "gemini_extract.py"
            if _gemini_path.exists():
                try:
                    spec = importlib.util.spec_from_file_location("_gemini_extract_load", _gemini_path)
                    if spec and spec.loader:
                        _mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(_mod)
                        test_gemini_connection = getattr(_mod, "test_gemini_connection", None)
                except Exception:
                    pass
        if test_gemini_connection is None:
            st.error("test_gemini_connection을 불러올 수 없습니다. analysis/gemini_extract.py에 해당 함수가 있는지 확인하세요.")
        else:
            try:
                # UI에서 선택한 Gemini 모델로 테스트 (선택 안 쓰면 Pro 한도만 소모됨)
                ok, summary, detail = test_gemini_connection(model_id=gemini_model_id)
                if ok:
                    st.success(summary)
                    st.caption(detail)
                else:
                    st.error(summary)
                    st.code(detail, language="text")
                    st.caption("위 에러 코드/메시지를 복사해 Gemini 지원에 문의하면 원인 파악에 도움이 됩니다.")
                    if "429" in detail or "ResourceExhausted" in detail or "quota" in detail.lower():
                        st.info("**HTTP 429 / Quota exceeded**: 무료 한도 초과 또는 모델별 제한일 수 있습니다. 위 **Gemini 모델**에서 **3.0 Flash** 또는 **2.0 Flash**로 바꾼 뒤 연결 테스트를 다시 실행하거나, 다음 날 한도 리셋 후 시도해 보세요.")
            except Exception as e:
                st.error(f"테스트 실행 실패: {e}")
                st.code(str(e), language="text")

    if st.button("PDF 분석 실행", type="primary", disabled=bool(st.session_state.get(KEY_RUNNING))):
        pdf_files = sorted(p for p in pdf_base.rglob("*.pdf") if not _is_review(p))
        if not pdf_files:
            st.error(f"PDF가 없습니다: {pdf_base}")
        else:
            total = len(pdf_files)
            checked = st.session_state.get(KEY_CHECKED, [])
            if len(checked) != total:
                checked = [True] * total
            # 슬라이더 범위 내에서만 분석 (숫자 입력 limit 대신 범위 적용)
            range_start, range_end = st.session_state.get("pdf_analysis_range", (1, total))
            range_start = max(1, min(range_start, total))
            range_end = max(range_start, min(range_end, total))
            start_idx = range_start - 1
            end_idx = range_end
            # 범위 안이면서 체크된 파일만
            selected_indices = [i for i in range(start_idx, end_idx) if i < total and checked[i]]
            pdf_files = [pdf_files[i] for i in selected_indices]
            if not pdf_files:
                st.error("선택한 파일이 없습니다. 위 목록에서 분석할 PDF를 체크하세요.")
            else:
                PDF_BASE_PATH_FILE.parent.mkdir(parents=True, exist_ok=True)
                PDF_BASE_PATH_FILE.write_text(str(pdf_base), encoding="utf-8")
                _save_ui_config({
                    "request_delay_sec": int(request_delay_sec),
                    "use_rule_base_only": use_rule_base_only,
                    "use_llm": use_llm,
                    "use_gemini": use_gemini,
                    "gemini_model_id": gemini_model_id,
                    "use_gemini_vision": use_gemini_vision,
                })
                st.session_state[KEY_RUNNING] = True
                st.session_state[KEY_FILES] = [str(p.relative_to(pdf_base)) for p in pdf_files]
                st.session_state[KEY_INDEX] = 0
                st.session_state[KEY_RESULTS] = []
                st.session_state[KEY_CONFIG] = {
                    "use_llm": False if use_rule_base_only else use_llm,
                    "use_gemini": False if use_rule_base_only else use_gemini,
                    "use_gemini_vision": False if use_rule_base_only else use_gemini_vision,
                    "gemini_model": gemini_model_id,
                    "request_delay_sec": int(request_delay_sec),
                    "pdf_base": str(pdf_base),
                }
                st.rerun()

    if not JSON_PATH.exists():
        st.info("아직 분석 결과가 없습니다. 위에서 'PDF 분석 실행'을 눌러 주세요.")
        return

    try:
        import json
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        st.error(f"결과 파일 읽기 실패: {e}")
        return

    st.markdown("## 분석 엔진 현황")
    engine_counts: dict[str, int] = {}
    engine_models: dict[str, set[str]] = {}
    errors_list: list[dict[str, str]] = []
    api_sent_count = sum(1 for r in data if r.get("_api_request_sent") is True or r.get("_analysis_engine") == "gemini")
    for r in data:
        eng = r.get("_analysis_engine") or "rule_based"
        engine_counts[eng] = engine_counts.get(eng, 0) + 1
        model = (r.get("_analysis_model") or "").strip()
        if model:
            if eng not in engine_models:
                engine_models[eng] = set()
            engine_models[eng].add(model)
        err = (r.get("_analysis_error") or "").strip()
        if err:
            errors_list.append({
                "PDF": r.get("source_pdf", ""),
                "엔진": eng,
                "모델": model or "-",
                "오류": err[:150],
            })
    eng_col1, eng_col2, eng_col3 = st.columns(3)
    with eng_col1:
        st.metric("Gemini 분석", f"{engine_counts.get('gemini', 0)}건", "사용 모델 아래 참고")
    with eng_col2:
        st.metric("규칙 기반", f"{engine_counts.get('rule_based', 0)}건", "API 미사용/실패 시 폴백")
    with eng_col3:
        st.metric("OpenAI", f"{engine_counts.get('openai', 0)}건", "")
    if engine_models.get("gemini"):
        st.caption("**Gemini 사용 시 실제 모델:** " + ", ".join(sorted(engine_models["gemini"])))
        gemini_models = engine_models.get("gemini", set())
        if "gemini-3-pro-preview" in gemini_models:
            st.success("Gemini 3.0 Pro로 분석된 건이 있습니다.")
        if "gemini-3-flash-preview" in gemini_models:
            st.success("Gemini 3.0 Flash로 분석된 건이 있습니다.")
        if "gemini-2.0-flash" in gemini_models:
            st.success("Gemini 2.0 Flash로 분석된 건이 있습니다.")
        if engine_counts.get("gemini", 0) > 0 and not gemini_models:
            st.warning("Gemini 분석 건이 있으나 모델 정보가 없습니다. .env의 GEMINI_MODEL을 확인하세요.")
    if engine_counts.get("gemini", 0) == 0 and engine_counts.get("rule_based", 0) > 0:
        st.warning("Gemini로 분석된 건이 없습니다. GEMINI_API_KEY·모델명·API 오류를 확인하세요. 이미지 분석 사용 시 3.0 Flash/2.0 Flash는 레거시 SDK로 재시도됩니다. 아래 '엔진/API 오류 상세'에서 원인을 확인하세요.")
    st.caption(f"**실제 API 요청 전송:** 이번 결과 중 {api_sent_count}건에서 Gemini로 요청이 나갔습니다. 0건이면 API 키 미설정이거나 'Rule Base만' 사용입니다.")
    first_error = next((r.get("_analysis_error", "").strip() for r in data if (r.get("_analysis_error") or "").strip()), "")
    if first_error:
        st.caption(f"**오류 예시:** {first_error[:200]}{'…' if len(first_error) > 200 else ''}")
    if errors_list:
        with st.expander("엔진/API 오류 상세", expanded=True):
            for e in errors_list[:20]:
                st.text(f"PDF: {e['PDF']}")
                st.caption(f"엔진: {e['엔진']} | 모델: {e['모델']} | 오류: {e['오류']}")
            if len(errors_list) > 20:
                st.caption(f"… 외 {len(errors_list) - 20}건")
    st.markdown("---")
    st.markdown("## 상품 목록")
    rows = []
    for r in data:
        eng = r.get("_analysis_engine") or "rule_based"
        model = (r.get("_analysis_model") or "").strip()
        engine_label = f"{eng}" + (f" ({model})" if model else "")
        row = {
            "엔진": engine_label[:40],
            "PDF": r.get("source_pdf", ""),
            "상품명": (r.get("상품명") or "")[:50],
            "브랜드": (r.get("브랜드명") or "")[:20],
            "가격": r.get("가격") or "-",
            "소재": (r.get("소재") or "")[:30],
            "사이즈": ",".join(str(x) for x in (r.get("사이즈") or [])),
            "사이즈_상세": (r.get("사이즈_상세") or "")[:60] + ("…" if len(r.get("사이즈_상세") or "") > 60 else ""),
            "색상": ",".join(str(x) for x in (r.get("색상") or [])),
            "이미지_무드": (r.get("이미지_무드") or "")[:15],
            "이미지_톤": (r.get("이미지_톤") or "")[:15],
            "사진_구성": (r.get("사진_구성") or "")[:20],
            "브랜드_평": (r.get("브랜드_평") or "")[:30],
        }
        rows.append(row)

    st.dataframe(rows, use_container_width=True)
    st.caption(f"총 {len(rows)}건 · JSON: data/pdf_analysis/pdf_products.json · CSV: data/pdf_analysis/pdf_products.csv")

    st.markdown("## 통합 결과 · 내보내기")
    export_cols = [k for k in PDF_ANALYSIS_KEYS if not k.startswith("_")]
    export_rows = []
    for r in data:
        row = {}
        for k in export_cols:
            v = r.get(k)
            if isinstance(v, list):
                row[k] = ", ".join(str(x) for x in v) if v else ""
            else:
                row[k] = v if v is not None else ""
        export_rows.append(row)
    ex_col1, ex_col2, ex_col3 = st.columns(3)
    with ex_col1:
        if export_rows:
            try:
                import pandas as pd
                df_export = pd.DataFrame(export_rows, columns=export_cols)
                excel_bytes = None
                try:
                    from io import BytesIO
                    buf = BytesIO()
                    df_export.to_excel(buf, index=False, engine="openpyxl")
                    buf.seek(0)
                    excel_bytes = buf.getvalue()
                except Exception:
                    pass
                if excel_bytes:
                    # 서버 쪽에도 저장 (지정된 경로)
                    try:
                        export_dir = _get_export_dir()
                        xlsx_path = export_dir / "pdf_analysis_results.xlsx"
                        xlsx_path.write_bytes(excel_bytes)
                        saved_xlsx_msg = f"서버 저장 위치: {xlsx_path}"
                    except Exception:
                        saved_xlsx_msg = ""
                    st.download_button(
                        "엑셀(.xlsx) 다운로드",
                        data=excel_bytes,
                        file_name="pdf_analysis_results.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_excel",
                    )
                    if saved_xlsx_msg:
                        st.caption(saved_xlsx_msg)
                else:
                    st.caption("엑셀 다운로드: openpyxl 설치 필요 (pip install openpyxl)")
            except Exception as e:
                st.caption(f"엑셀 생성 실패: {e}")
    with ex_col2:
        if export_rows:
            try:
                import csv
                from io import StringIO
                buf = StringIO()
                writer = csv.DictWriter(buf, fieldnames=export_cols, extrasaction="ignore")
                writer.writeheader()
                for row in export_rows:
                    writer.writerow(row)
                csv_bytes = buf.getvalue().encode("utf-8-sig")
                # 서버 쪽에도 저장 (지정된 경로)
                saved_csv_msg = ""
                try:
                    export_dir = _get_export_dir()
                    csv_path = export_dir / "pdf_analysis_results.csv"
                    csv_path.write_bytes(csv_bytes)
                    saved_csv_msg = f"서버 저장 위치: {csv_path}"
                except Exception:
                    saved_csv_msg = ""
                st.download_button(
                    "CSV 다운로드",
                    data=csv_bytes,
                    file_name="pdf_analysis_results.csv",
                    mime="text/csv",
                    key="dl_csv",
                )
                st.caption("CSV를 Google Sheet에 가져오기: Google Drive → 새 Google 스프레드시트 → 파일 → 가져오기 → 업로드")
                if saved_csv_msg:
                    st.caption(saved_csv_msg)
            except Exception as e:
                st.caption(f"CSV 생성 실패: {e}")
    with ex_col3:
        if export_rows:
            st.markdown("**Google Sheet로 보내기**")
            # 간단한 방법: 클립보드 복사 → 시트에서 붙여넣기 (설정 없음)
            tsv_lines = ["\t".join(export_cols)]
            for row in export_rows:
                tsv_lines.append("\t".join(str(row.get(c, "")) for c in export_cols))
            tsv_string = "\n".join(tsv_lines)
            if st.button("📋 클립보드에 복사 (시트에 붙여넣기)", key="btn_copy_for_sheet"):
                try:
                    import pyperclip
                    pyperclip.copy(tsv_string)
                    st.success("복사됨! 아래 링크에서 새 스프레드시트를 만든 뒤 **Ctrl+V** 하세요.")
                except Exception:
                    st.warning("클립보드 복사에 실패했습니다. 아래 CSV 다운로드 후 시트에서 파일 → 가져오기로 넣으세요.")
            st.markdown('[→ Google Sheets 열기](https://sheets.google.com)', unsafe_allow_html=False)
            st.caption("새 스프레드시트 → Ctrl+V 로 표 붙여넣기. (설정·계정 없이 가능)")
            st.markdown("---")
            st.caption("**자동 전송** (설정에서 Service Account 등록 후)")
            try:
                from web.utils.sheet_export import push_pdf_analysis_to_sheet
                if st.button("Google Sheet로 자동 전송", key="btn_send_to_sheet"):
                    ok, msg = push_pdf_analysis_to_sheet(export_cols, export_rows)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
            except Exception:
                pass
    ex_col_pdf1, ex_col_pdf2 = st.columns(2)
    with ex_col_pdf1:
        if export_rows:
            try:
                from io import BytesIO
                import xml.sax.saxutils
                from reportlab.lib import colors
                from reportlab.lib.pagesizes import A4, landscape
                from reportlab.lib.styles import ParagraphStyle
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
                _pdf_font = _get_pdf_korean_font()
                buf = BytesIO()
                # 가로 방향으로 넓게 써서 테이블이 잘리지 않도록
                doc = SimpleDocTemplate(
                    buf, pagesize=landscape(A4), rightMargin=24, leftMargin=24, topMargin=30, bottomMargin=30
                )
                headers = export_cols[:18]
                n_cols = len(headers)
                col_width = (doc.pagesize[0] - doc.leftMargin - doc.rightMargin) / n_cols
                # 셀 안에서 줄바꿈되도록 Paragraph 사용 (한글 등 긴 텍스트)
                def _cell_text(s: str, max_len: int = 200) -> str:
                    raw = (s or "")[:max_len].replace("\n", " ")
                    return xml.sax.saxutils.escape(raw)
                cell_style = ParagraphStyle(
                    "pdf_cell", fontName=_pdf_font, fontSize=6, leading=7, wordWrap="CJK"
                )
                header_style = ParagraphStyle(
                    "pdf_header", fontName=("Helvetica-Bold" if _pdf_font == "Helvetica" else _pdf_font),
                    fontSize=6, leading=7, wordWrap="CJK"
                )
                table_data = [[Paragraph(_cell_text(str(h), 30), header_style) for h in headers]]
                for row in export_rows[:200]:
                    table_data.append([
                        Paragraph(_cell_text(str(row.get(h, ""))), cell_style) for h in headers
                    ])
                t = Table(
                    table_data,
                    repeatRows=1,
                    colWidths=[col_width] * n_cols,
                )
                header_font = "Helvetica-Bold" if _pdf_font == "Helvetica" else _pdf_font
                t.setStyle(TableStyle([
                    ("FONTNAME", (0, 0), (-1, 0), header_font),
                    ("FONTNAME", (0, 1), (-1, -1), _pdf_font),
                    ("FONTSIZE", (0, 0), (-1, -1), 6),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]))
                doc.build([t])
                buf.seek(0)
                pdf_bytes = buf.getvalue()
                st.download_button(
                    "PDF 다운로드",
                    data=pdf_bytes,
                    file_name="pdf_analysis_results.pdf",
                    mime="application/pdf",
                    key="dl_pdf",
                )
            except ImportError:
                st.caption("PDF 다운로드: reportlab 설치 필요 (pip install reportlab)")
            except Exception as e:
                st.caption(f"PDF 생성 실패: {e}")
    with ex_col_pdf2:
        pass  # 레이아웃 균형

    # 리뷰/편집 안내 및 이동
    st.markdown("## 리뷰 / 편집")
    st.caption("각 항목별 분석 내용 검토·추가 의견 편집 및 PDF 대표/상세 이미지 기반 리뷰 작성은 **상품 리뷰** 페이지에서 할 수 있습니다.")
    rev_col1, rev_col2 = st.columns([2, 1])
    with rev_col1:
        review_options = [
            (i, f"{i+1}. {(r.get('브랜드명') or '')[:20]} | {(r.get('상품명') or '')[:40]}")
            for i, r in enumerate(data)
        ]
        review_sel = st.selectbox(
            "리뷰할 상품 선택",
            range(len(review_options)),
            format_func=lambda i: review_options[i][1],
            key="pdf_review_select",
        )
    with rev_col2:
        if st.button("해당 항목 리뷰 페이지로", key="go_review"):
            st.session_state["pdf_review_item_index"] = review_sel
            st.switch_page("pages/pdf_item_review.py")
    st.caption("좌측 메뉴에서 **상품 리뷰**를 선택해도 됩니다.")

    st.markdown("## DB 반영 및 브랜드 맵")
    st.caption("**PDF 분석이 완료되면 자동으로 Supabase에 반영됩니다.** 수동으로 다시 반영하려면 아래 'DB에 반영' 버튼을 사용하세요. Gemini로 브랜드 맵(JSON)을 생성할 수도 있습니다.")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("DB에 반영", key="sync_db"):
            import sys
            if str(_PROJECT_ROOT) not in sys.path:
                sys.path.insert(0, str(_PROJECT_ROOT))
            try:
                from scripts.sync_pdf_analysis_to_db import sync_pdf_results_to_db
                from shared.services.data_service import DataService
                created, errs = sync_pdf_results_to_db(data, DataService())
                st.success(f"DB 반영 완료: {created}건")
                for e in errs[:10]:
                    st.warning(e)
            except Exception as ex:
                st.error(f"DB 반영 실패: {ex}")
    with col_b:
        if st.button("브랜드 맵 생성", key="brand_map"):
            import sys
            if str(_PROJECT_ROOT) not in sys.path:
                sys.path.insert(0, str(_PROJECT_ROOT))
            try:
                from analysis.gemini_extract import generate_brand_map
                brand_map = generate_brand_map(data)
                if brand_map:
                    import json
                    (OUTPUT_DIR / "brand_map.json").write_text(json.dumps(brand_map, ensure_ascii=False, indent=2), encoding="utf-8")
                    st.success("브랜드 맵 저장: data/pdf_analysis/brand_map.json")
                    with st.expander("브랜드 맵 미리보기"):
                        st.json(brand_map)
                else:
                    st.warning("브랜드 맵 생성 실패 (GEMINI_API_KEY 확인)")
            except Exception as ex:
                st.error(f"브랜드 맵 생성 실패: {ex}")


render()
