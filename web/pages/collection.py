"""
수집 관리 페이지 (PDF 수집만 지원)
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

# Streamlit이 프로젝트 루트에서 실행되므로 web의 부모 = 루트
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PDF_PROGRESS_FILE = _PROJECT_ROOT / "logs" / "pdf_collect_progress.txt"
# pdf_collector.CATEGORY_BEST_URLS와 순서/이름 일치
PDF_CATEGORY_CHOICES = [
    "여성_의류", "여성_가방", "여성_슈즈", "여성_액세서리", "여성_주얼리",
    "남성_의류", "남성_가방", "남성_슈즈", "남성_액세서리",
]

# phase -> 한글 라벨 (그래픽 표시용)
PHASE_LABELS = {
    "start": "시작",
    "category_start": "카테고리 진행",
    "category_end": "카테고리 완료",
    "product": "상품 방문",
    "product_saved": "저장 완료",
    "product_skipped": "건너뜀 (이미 저장)",
    "product_error": "상품 오류",
    "complete": "완료",
    "error": "오류",
}


def _parse_progress_file() -> dict:
    """
    logs/pdf_collect_progress.txt 파싱.
    Returns: total_saved, phase, category, estimated_total, category_counts, log_lines, last_ts
    """
    out = {
        "total_saved": 0,
        "phase": "",
        "category": "",
        "estimated_total": 900,  # 기본 전체 9*100
        "category_counts": {},
        "log_lines": [],
        "last_ts": "",
    }
    if not PDF_PROGRESS_FILE.exists():
        return out
    try:
        raw = PDF_PROGRESS_FILE.read_text(encoding="utf-8")
        lines = [ln.strip() for ln in raw.strip().splitlines() if ln.strip()]
    except Exception:
        return out
    if not lines:
        return out

    for ln in lines:
        parts = ln.split("|", 5)
        if len(parts) < 6:
            out["log_lines"].append(ln)
            continue
        ts, phase, cat, cur, total, msg = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
        out["last_ts"] = ts
        try:
            t = int(total)
            out["total_saved"] = t
        except ValueError:
            pass
        out["phase"] = phase
        out["category"] = cat or ""

        if phase == "start" and msg and "카테고리" in msg:
            m = re.search(r"카테고리\s*(\d+)\s*개", msg)
            if m:
                n_cat = int(m.group(1))
                out["estimated_total"] = n_cat * 100
        if phase == "product_saved" and cat:
            out["category_counts"][cat] = out["category_counts"].get(cat, 0) + 1

        display = f"[{ts}] {phase} | {cat or '-'} | #{cur} | 저장 {total}개 | {msg or '-'}"
        out["log_lines"].append(display)

    return out


def render() -> None:
    """수집 관리 UI 렌더링."""
    st.title("데이터 수집 관리")

    # ----- PDF 수집: 전체 수집 / 카테고리별 수집 -----
    st.subheader("PDF 수집")
    st.caption(
        "29cm 방문 → 베스트 메뉴 클릭 → 카테고리별 1~100위 상품 상세 페이지를 A5 PDF로 저장. "
        "전체 수집 또는 카테고리별 수집을 선택할 수 있습니다. "
        "수집은 **시작부터 종료까지 사람 개입 없이** 진행되며, 결과는 아래 **PDF 수집 진행 상황**에서 확인할 수 있습니다."
    )
    pdf_scope = st.radio(
        "수집 범위",
        ["전체 수집", "카테고리별 수집"],
        horizontal=True,
        key="pdf_scope",
        help="전체 수집: 모든 카테고리. 카테고리별 수집: 선택한 카테고리 1개만.",
    )
    pdf_category_arg = None
    if pdf_scope == "카테고리별 수집":
        pdf_selected_cat = st.selectbox(
            "카테고리",
            PDF_CATEGORY_CHOICES,
            key="pdf_category",
            help="수집할 베스트 카테고리 1개를 선택하세요.",
        )
        pdf_category_arg = pdf_selected_cat
    pdf_headless = st.checkbox(
        "브라우저 창 숨김",
        value=False,
        key="pdf_headless",
        help="체크 해제 시 수집 브라우저가 자동으로 최상단에 올라갑니다(Windows). 창을 보면서 진행 상황을 확인할 수 있습니다.",
    )
    PDF_BASE_PATH_FILE = _PROJECT_ROOT / "data" / "pdf_base_path.txt"
    _saved_pdf_path = "pdfs"
    if PDF_BASE_PATH_FILE.exists():
        try:
            _saved_pdf_path = PDF_BASE_PATH_FILE.read_text(encoding="utf-8").strip() or "pdfs"
        except Exception:
            pass
    pdf_output_input = st.text_input(
        "PDF 저장 폴더",
        value=_saved_pdf_path,
        help="한 번 지정하면 저장되어, 재변경하지 않으면 다음에도 그대로 재사용됩니다. 분석·리뷰 페이지와 공통 적용. 상대 경로는 프로젝트 루트 기준.",
    )
    if st.button("경로 저장", key="pdf_path_save_collection"):
        try:
            out_path = Path(pdf_output_input)
            if not out_path.is_absolute():
                out_path = _PROJECT_ROOT / out_path
            out_path = out_path.resolve()
            PDF_BASE_PATH_FILE.parent.mkdir(parents=True, exist_ok=True)
            PDF_BASE_PATH_FILE.write_text(str(out_path), encoding="utf-8")
            st.success(f"경로가 저장되었습니다: {out_path}")
            st.rerun()
        except Exception as e:
            st.error(f"경로 저장 실패: {e}")

    if st.button("PDF 수집 시작", type="primary", key="pdf_collect_start"):
        try:
            out_path = Path(pdf_output_input)
            if not out_path.is_absolute():
                out_path = _PROJECT_ROOT / out_path
            out_path = out_path.resolve()
            PDF_BASE_PATH_FILE.parent.mkdir(parents=True, exist_ok=True)
            PDF_BASE_PATH_FILE.write_text(str(out_path), encoding="utf-8")
            cmd = [
                sys.executable,
                "-m",
                "agent.run_pdf_collect",
                "--output",
                str(out_path.resolve()),
            ]
            if pdf_category_arg:
                cmd.extend(["--category", pdf_category_arg])
            if pdf_headless:
                cmd.append("--headless")
            env = os.environ.copy()
            subprocess.Popen(
                cmd,
                cwd=str(_PROJECT_ROOT),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            scope_msg = f"카테고리 '{pdf_category_arg}'" if pdf_category_arg else "전체 카테고리"
            st.success(f"PDF 수집을 시작했습니다. ({scope_msg}, 저장 위치: {out_path})")
            if not pdf_headless:
                st.info("수집 브라우저가 곧 최상단에 올라옵니다. **시작부터 종료까지 자동 진행**되며, 아래 **PDF 수집 진행 상황**에서 저장 수·진행률·카테고리별 결과를 확인하세요.")
            else:
                st.info("아래 **PDF 수집 진행 상황**에서 실시간 로그를 확인하세요.")
            st.rerun()
        except Exception as e:
            st.error(f"PDF 수집 시작 실패: {e}")

    # ----- PDF 수집 진행 상황 (그래픽 + 로그) -----
    st.subheader("PDF 수집 진행 상황")
    prog = _parse_progress_file()
    total_saved = prog["total_saved"]
    estimated_total = prog["estimated_total"]
    phase_label = PHASE_LABELS.get(prog["phase"], prog["phase"] or "대기 중")
    category_counts = prog["category_counts"]

    if prog["log_lines"]:
        # 메트릭: 저장된 PDF 수, 진행률, 현재 단계
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("저장된 PDF 수", f"{total_saved}개", delta=None)
        with col2:
            ratio = min(1.0, total_saved / estimated_total) if estimated_total else 0.0
            pct = int(ratio * 100)
            st.metric("진행률", f"{pct}%", f"{total_saved} / {estimated_total} (예상)")
        with col3:
            st.metric("현재 단계", phase_label, prog["category"] or "-")

        # 진행률 바
        progress_ratio = min(1.0, total_saved / estimated_total) if estimated_total else 0.0
        st.progress(progress_ratio)
        st.caption("위 진행률은 '예상 최대 수(카테고리 수 × 100)' 대비 저장된 PDF 수입니다.")

        # 카테고리별 저장 수 (막대 그래프)
        if category_counts:
            st.markdown("**카테고리별 저장 수**")
            df_cat = pd.DataFrame(
                [{"카테고리": k, "저장 수": v} for k, v in sorted(category_counts.items())]
            )
            st.bar_chart(df_cat.set_index("카테고리"), height=220)

        # 진행 로그 (접이식)
        with st.expander("진행 로그 (logs/pdf_collect_progress.txt)", expanded=False):
            progress_text = "\n".join(prog["log_lines"][-80:])
            st.text_area(
                "로그",
                value=progress_text,
                height=200,
                disabled=True,
                label_visibility="collapsed",
                key="pdf_progress_log",
            )
    else:
        st.info("아직 PDF 수집 진행 로그가 없습니다. **PDF 수집 시작**을 누르면 여기에 진행률과 카테고리별 저장 수가 그래픽으로 표시됩니다.")

    pdf_auto_refresh = st.checkbox("PDF 진행 상황 자동 새로고침 (2초 간격)", value=False, key="pdf_auto_refresh")
    if pdf_auto_refresh:
        time.sleep(2)
        st.rerun()


# Streamlit 페이지에서는 모듈 레벨에서 함수를 호출해야 합니다
render()


