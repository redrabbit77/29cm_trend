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

PDF_ANALYSIS_KEYS = [
    "source_pdf", "상품명", "브랜드명", "상세_카테고리명", "의류종류", "가격", "소재", "케어방법",
    "사이즈", "사이즈_상세", "색상",
    "이미지_무드", "이미지_톤", "이미지_배경", "사진_구성", "모델_특징", "제품_특징", "브랜드_평", "이미지_요약",
]


def _is_review(p: Path) -> bool:
    return "_review" in p.name.lower() or p.name.lower().endswith("review.pdf")


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
    delay_sec = max(0, int(config.get("request_delay_sec", 2)))
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
        for k in (KEY_FILES, KEY_INDEX, KEY_RESULTS, KEY_CONFIG):
            if k in st.session_state:
                del st.session_state[k]
    return None


def render() -> None:
    st.title("PDF 분석 결과")

    # 분석 진행 중이면 맨 위에 진행 상태만 크게 표시 후 1건 처리하고 rerun
    if st.session_state.get(KEY_RUNNING):
        files = st.session_state.get(KEY_FILES) or []
        idx = st.session_state.get(KEY_INDEX, 0)
        total = len(files)
        pct = (idx / total) if total else 0
        current_name = files[idx] if idx < len(files) else ""

        st.markdown("---")
        st.markdown("### ⏳ PDF 분석 실행 중")
        prog_col1, prog_col2 = st.columns([2, 1])
        with prog_col1:
            st.progress(pct, text=f"진행률 {idx}/{total}")
        with prog_col2:
            st.metric("완료", f"{idx} / {total}", f"총 {total}건")
        st.info(f"**현재 처리 중:** `{current_name}`")
        st.caption("한 건씩 처리하며 화면이 자동으로 갱신됩니다. 잠시만 기다려 주세요.")
        st.markdown("---")

        err = _run_one_and_maybe_finish()
        if err:
            st.error(err)
        st.rerun()

    st.caption("수집된 PDF에서 텍스트를 추출해 상품명·브랜드·가격·소재·케어·사이즈·색상 등을 구조화합니다. Gemini 3.0 Pro(GEMINI_API_KEY) 또는 OpenAI(OPENAI_API_KEY) 사용 가능. 이미지 분석 시 PDF 페이지를 Gemini에 보내 무드·촬영·배경을 추출합니다.")

    if st.session_state.get("pdf_analysis_just_finished"):
        st.success(f"분석이 완료되었습니다. 결과: {OUTPUT_DIR.relative_to(_PROJECT_ROOT)}")
        del st.session_state["pdf_analysis_just_finished"]

    saved = _get_saved_ui_config()
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
        limit_default = saved.get("limit", 100)
        limit = st.number_input("처리 PDF 개수 제한", min_value=0, value=int(limit_default), step=10, help="0이면 전체, 기본 100건")
        delay_default = saved.get("request_delay_sec", 2)
        request_delay_sec = st.number_input("요청 간 대기(초)", min_value=0, value=int(delay_default), step=1, help="429/503 방지. PDF 건당 API 호출 전 대기. 0이면 대기 없음.")
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
        if st.button("옵션 저장", key="pdf_analysis_save_options"):
            _save_ui_config({
                "limit": limit if limit else 100,
                "request_delay_sec": int(request_delay_sec),
                "use_rule_base_only": use_rule_base_only,
                "use_llm": use_llm,
                "use_gemini": use_gemini,
                "gemini_model_id": gemini_model_id,
                "use_gemini_vision": use_gemini_vision,
            })
            st.success("옵션이 저장되었습니다. 새로고침 후에도 복원됩니다.")
            st.rerun()
    limit = None if limit == 0 else limit

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
        if limit:
            pdf_files = pdf_files[:limit]
        if not pdf_files:
            st.error(f"PDF가 없습니다: {pdf_base}")
        else:
            PDF_BASE_PATH_FILE.parent.mkdir(parents=True, exist_ok=True)
            PDF_BASE_PATH_FILE.write_text(str(pdf_base), encoding="utf-8")
            _save_ui_config({
                "limit": limit or 100,
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

    # 분석 엔진 현황 (Gemini 3.0 Pro 사용 여부 확인)
    st.subheader("분석 엔진 현황")
    engine_counts: dict[str, int] = {}
    engine_models: dict[str, set[str]] = {}
    errors_list: list[dict[str, str]] = []
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
        # Gemini 시도 후 rule_based로 떨어진 건의 오류 요약 표시 (첫 건 기준)
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

    st.subheader("상품 목록")
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

    # 리뷰/편집 안내 및 이동
    st.subheader("리뷰 / 편집")
    st.caption("각 항목별 분석 내용 검토·추가 의견 편집 및 PDF 대표/상세 이미지 기반 리뷰 작성은 **PDF 상품 리뷰** 페이지에서 할 수 있습니다.")
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
    st.caption("좌측 메뉴에서 **PDF 상품 리뷰**를 선택해도 됩니다.")

    # DB 반영 / 브랜드 맵
    st.subheader("DB 반영 및 브랜드 맵")
    st.caption("분석 결과를 Supabase products·brands에 반영하거나, Gemini로 브랜드 맵을 생성합니다.")
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
