"""
29CM PDF 수집: 방문 → BEST 클릭 → 카테고리별 1~100위 상세 페이지 → A5 PDF 저장.

흐름:
1. 29cm 페이지 방문
2. 베스트 메뉴 클릭
3. 각 카테고리 페이지 방문
4. 1위~100위 제품 상세 페이지 방문
5. 각 페이지를 A5 사이즈 PDF로 저장 (Chromium 인쇄)
"""
from __future__ import annotations

import logging
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Browser, Page, sync_playwright

logger = logging.getLogger(__name__)

BASE_URL = "https://www.29cm.co.kr"
# PDF 저장 루트 (프로젝트 루트 기준)
PDF_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "pdfs"
# 진행 상황 로그 (UI에서 실시간 표시용)
PROGRESS_FILE = Path(__file__).resolve().parent.parent / "logs" / "pdf_collect_progress.txt"
# A5 용지 (Chromium PDF)
PDF_FORMAT = "A5"

# BEST 메뉴 클릭용 셀렉터 (29CM DOM에 맞게 조정 가능)
BEST_MENU_SELECTORS = [
    'nav a:has-text("BEST")',
    'a:has-text("베스트")',
    'a[href*="best"]',
    '[class*="nav"] a:has-text("BEST")',
    'header a:has-text("BEST")',
]

# 카테고리 BEST 페이지 URL (29CM 베스트 전체 카테고리)
# category_large_code는 29CM 사이트 구조에 맞게 조정 가능
CATEGORY_BEST_URLS = [
    ("여성_의류", "https://www.29cm.co.kr/store/best-items?category_large_code=268100100"),
    ("여성_가방", "https://www.29cm.co.kr/store/best-items?category_large_code=268100200"),
    ("여성_슈즈", "https://www.29cm.co.kr/store/best-items?category_large_code=268100300"),
    ("여성_액세서리", "https://www.29cm.co.kr/store/best-items?category_large_code=268100400"),
    ("여성_주얼리", "https://www.29cm.co.kr/store/best-items?category_large_code=268100500"),
    ("남성_의류", "https://www.29cm.co.kr/store/best-items?category_large_code=268200100"),
    ("남성_가방", "https://www.29cm.co.kr/store/best-items?category_large_code=268200200"),
    ("남성_슈즈", "https://www.29cm.co.kr/store/best-items?category_large_code=268200300"),
    ("남성_액세서리", "https://www.29cm.co.kr/store/best-items?category_large_code=268200400"),
]

# 상품 링크 수집 셀렉터 (카테고리 BEST 페이지에서 1~10위 상품)
PRODUCT_LINK_SELECTORS = [
    "main a[href*='catalog/']",
    "main a[href*='/product/']",
    "a[href*='catalog/']",
    "a[href*='/products/']",
]


def _open_browser(headless: bool = False) -> tuple[sync_playwright, Browser, Page]:
    """Chromium 실행 (PDF는 Chromium만 지원)."""
    p = sync_playwright().start()
    browser = p.chromium.launch(channel="chrome", headless=headless)
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()
    page.set_default_timeout(30_000)
    page.set_default_navigation_timeout(45_000)
    return p, browser, page


def _write_progress(
    phase: str,
    category: str = "",
    current: int = 0,
    total_saved: int = 0,
    message: str = "",
    progress_file: Path | None = None,
) -> None:
    """진행 상황을 파일에 한 줄씩 기록 (UI에서 실시간 표시용)."""
    path = progress_file or PROGRESS_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"{ts}|{phase}|{category}|{current}|{total_saved}|{message}\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        logger.debug("진행 로그 기록 실패: %s", e)


def _clear_progress(progress_file: Path | None = None) -> None:
    """진행 로그 파일 초기화 (수집 시작 시)."""
    path = progress_file or PROGRESS_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    except Exception as e:
        logger.debug("진행 로그 초기화 실패: %s", e)


def _normalize_product_url(href: str) -> str | None:
    """상품 상세 URL만 추출 (catalog 또는 products). 쿼리·해시 제거."""
    if not href or "javascript" in href:
        return None
    href = href.strip()
    if href.startswith("/"):
        href = BASE_URL + href
    if "catalog/" in href or "/products/" in href:
        return href.split("?")[0].split("#")[0].rstrip("/")
    return None


def _base_product_url_and_id(url: str) -> tuple[str, str] | None:
    """
    상품 URL을 '상품정보' 기준 URL로 정규화하고, 상품 ID 추출.
    /review, _review 등 리뷰 경로는 제거해 동일 상품이 두 번 수집되지 않도록 함.
    """
    base = _normalize_product_url(url)
    if not base:
        return None
    # 리뷰 경로 제거: .../12345/review, .../12345_review → .../12345
    base = base.replace("/review", "").replace("_review", "").rstrip("/")
    product_id = base.split("/")[-1] if base else ""
    if not product_id:
        return None
    return (base, product_id)


def _bring_browser_window_to_front() -> None:
    """
    수집 브라우저 창을 최상단으로 올림 (Windows).
    창 제목에 '29cm' 또는 'Chrome'이 포함된 창을 찾아 활성화.
    headless가 아닐 때만 의미 있음.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        hwnd_29cm: list[int] = []
        hwnd_chrome: list[int] = []

        def get_window_title(hwnd: int) -> str:
            length = user32.GetWindowTextLengthW(hwnd) + 1
            buf = ctypes.create_unicode_buffer(length)
            user32.GetWindowTextW(hwnd, buf, length)
            return buf.value or ""

        def enum_callback(hwnd: int, _: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            title = get_window_title(hwnd)
            if "29cm" in title:
                hwnd_29cm.append(hwnd)
            elif "Chrome" in title and len(title) > 2:
                hwnd_chrome.append(hwnd)
            return True

        cb = WNDENUMPROC(enum_callback)
        user32.EnumWindows(cb, 0)
        found_hwnd = (hwnd_29cm or hwnd_chrome)[0] if (hwnd_29cm or hwnd_chrome) else None
        if found_hwnd is not None:
            user32.ShowWindow(found_hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(found_hwnd)
            user32.BringWindowToTop(found_hwnd)
    except Exception as e:
        logger.debug("브라우저 창 최상단 올리기 실패(무시): %s", e)


def _behave_like_human(page: Page, viewport_width: int = 1280, viewport_height: int = 720) -> None:
    """
    페이지 방문 직후 사람처럼 보이도록: 랜덤 스크롤 위치, 랜덤 스크롤량, 랜덤 마우스 이동.
    Playwright 페이지 내부에서만 동작 (시스템 마우스 미사용).
    """
    try:
        # 1) 짧은 랜덤 대기 (페이지를 훑어보는 듯)
        page.wait_for_timeout(random.randint(400, 1200))

        # 2) 랜덤 스크롤 위치로 이동 (문서 높이 내에서)
        doc_height = page.evaluate("() => document.documentElement.scrollHeight")
        max_y = max(0, doc_height - viewport_height)
        if max_y > 0:
            scroll_y = random.randint(0, min(max_y, 800))  # 상단~중간 위주, 가끔 더 아래
            page.evaluate(f"window.scrollTo({{ top: {scroll_y}, left: 0, behavior: 'instant' }})")
            page.wait_for_timeout(random.randint(200, 600))

        # 3) 랜덤 마우스 위치로 1~3번 이동 (뷰포트 좌표)
        for _ in range(random.randint(1, 3)):
            x = random.randint(80, max(81, viewport_width - 80))
            y = random.randint(80, max(81, viewport_height - 80))
            page.mouse.move(x, y)
            page.wait_for_timeout(random.randint(80, 250))

        # 4) 살짝 스크롤 (휠처럼 위/아래)
        delta = random.choice([-120, -80, 0, 80, 120])
        if delta != 0:
            page.mouse.wheel(0, delta)
            page.wait_for_timeout(random.randint(150, 400))

        # 5) 마우스를 한 번 더 다른 위치로
        x = random.randint(100, max(101, viewport_width - 100))
        y = random.randint(100, max(101, viewport_height - 100))
        page.mouse.move(x, y)
        page.wait_for_timeout(random.randint(300, 800))
    except Exception as e:
        logger.debug("인간 행동 모사 중 오류(무시): %s", e)


def visit_and_click_best(page: Page) -> bool:
    """29cm 방문 후 베스트 메뉴 클릭."""
    page.goto(BASE_URL, wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_timeout(1500)
    _behave_like_human(page, viewport_width=1280, viewport_height=720)
    for sel in BEST_MENU_SELECTORS:
        try:
            el = page.locator(sel).first
            if el.count() > 0:
                el.click()
                page.wait_for_timeout(2000)
                return True
        except Exception as e:
            logger.debug("BEST 메뉴 셀렉터 실패 %s: %s", sel, e)
    logger.warning("BEST 메뉴를 찾지 못했습니다. 카테고리 URL 직접 방문합니다.")
    return False


def _scroll_down(page: Page, amount: int = 400) -> None:
    """페이지를 아래로 amount px 스크롤."""
    try:
        page.evaluate(f"window.scrollBy(0, {amount})")
    except Exception:
        pass


def _scroll_to_bottom_gradually(page: Page, step: int = 400, max_steps: int = 80) -> None:
    """페이지 끝까지 단계적으로 스크롤 (지연 로딩 이미지 노출)."""
    for _ in range(max_steps):
        try:
            prev = page.evaluate("() => window.scrollY")
            page.evaluate(f"window.scrollBy(0, {step})")
            page.wait_for_timeout(300)
            curr = page.evaluate("() => window.scrollY")
            if curr == prev:
                break
            doc_height = page.evaluate("() => document.documentElement.scrollHeight")
            view_height = page.evaluate("() => window.innerHeight")
            if curr + view_height >= doc_height:
                break
        except Exception:
            break


def _click_show_more_for_description(page: Page) -> bool:
    """
    상품설명 영역의 '상품설명 더보기'만 클릭. 리뷰/상세 리뷰 탭·버튼은 절대 클릭하지 않음.
    """
    # 1) Playwright: '상품설명 더보기' 텍스트만 대상 (리뷰 탭/더보기 제외)
    for sel in (
        "button:has-text('상품설명 더보기')",
        "a:has-text('상품설명 더보기')",
        "[class*='description'] button:has-text('상품설명 더보기')",
        "[class*='description'] a:has-text('상품설명 더보기')",
        "button:has-text('상품설명'):has-text('더보기')",
        "a:has-text('상품설명'):has-text('더보기')",
    ):
        try:
            loc = page.locator(sel)
            if loc.count() > 0:
                # 리뷰 관련이면 스킵 (부모에 리뷰 문구 있는지)
                first = loc.first
                try:
                    parent_text = first.evaluate(
                        "el => (el.closest('[class*=\"review\"], [class*=\"리뷰\"], [id*=\"review\"], [id*=\"리뷰\"]') || {}).innerText || ''"
                    ) or ""
                    if "리뷰" in (parent_text or "") or "review" in (parent_text or "").lower():
                        continue
                except Exception:
                    pass
                first.scroll_into_view_if_needed()
                page.wait_for_timeout(400)
                first.click(force=True)
                page.wait_for_timeout(1500)
                return True
        except Exception:
            continue

    # 2) JS: '상품설명 더보기'만 클릭, 리뷰/상세 리뷰/탭 제외
    try:
        clicked = page.evaluate(
            """() => {
            const exclude = ['리뷰', '상세 리뷰', 'review'];
            const need = ['상품설명', '더보기'];
            const clickables = document.querySelectorAll('button, a, [role="button"], [onclick], [class*="more"], [class*="expand"]');
            let n = 0;
            for (const el of clickables) {
                const text = (el.innerText || el.textContent || '').trim();
                if (exclude.some(k => text.includes(k))) continue;
                if (!need.every(k => text.includes(k))) continue;
                const anc = el.closest('[class*="review"], [class*="리뷰"], [id*="review"], [id*="리뷰"]');
                if (anc) continue;
                el.scrollIntoView({ block: 'center' });
                el.click();
                n++;
                break;
            }
            return n;
            }"""
        )
        if clicked and clicked > 0:
            page.wait_for_timeout(2000)
            return True
    except Exception:
        pass
    return False


def expand_detail_before_pdf(page: Page, product_url: str | None = None) -> None:
    """
    상품 상세 페이지에서 상품설명 '더보기'만 클릭 후 스크롤.
    페이지 새로고침(goto)은 하지 않음 — 새로고침 시 펼친 상태가 초기화되므로 PDF에 접힌 상태로 나옴.
    """
    # 1) 상단으로 올린 뒤 상품설명 구간만 스크롤하며 '상품설명 더보기'만 클릭
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(600)
    description_click_count = 0
    max_description_clicks = 5
    for _ in range(25):
        _scroll_down(page, 280)
        page.wait_for_timeout(400)
        if _click_show_more_for_description(page):
            description_click_count += 1
            page.wait_for_timeout(2200)
            if description_click_count >= max_description_clicks:
                break

    # 2) 접힌 영역 강제 펼침 (상품설명/상세만, 리뷰 영역 제외)
    try:
        page.evaluate(
            """() => {
            const sel = '[class*="description"], [class*="detail"], [class*="상품설명"], [class*="content"]';
            document.querySelectorAll(sel).forEach(el => {
                const txt = (el.innerText || el.textContent || '').slice(0, 200);
                if (txt.includes('리뷰') || txt.includes('review')) return;
                const s = el.style;
                s.maxHeight = 'none';
                s.overflow = 'visible';
                s.height = 'auto';
                if (s.display === 'none') s.display = '';
                el.classList.remove('collapsed', 'fold', 'is-folded');
            });
            }"""
        )
        page.wait_for_timeout(600)
    except Exception:
        pass

    # 3) 끝까지 스크롤 (지연 로딩 이미지 노출). goto 하지 않음 → 펼친 상태 유지
    _scroll_to_bottom_gradually(page, step=400, max_steps=80)
    page.wait_for_timeout(1200)


def _get_saved_product_ids(cat_dir: Path, min_file_size: int = 512) -> set[str]:
    """
    카테고리 폴더에 이미 저장된 PDF의 상품 ID 집합 반환.
    파일명 형식: 01_3442256.pdf → 상품 ID 3442256.
    min_file_size 미만 파일(손상/미완성)은 제외해 재수집 대상으로 둠.
    """
    saved: set[str] = set()
    if not cat_dir.is_dir():
        return saved
    for f in cat_dir.glob("*.pdf"):
        if f.stat().st_size < min_file_size:
            continue
        stem = f.stem  # e.g. "01_3442256" or "10_3531081_review"
        if "_" not in stem:
            continue
        pid = stem.split("_", 1)[1].replace("_review", "").strip()
        if pid:
            saved.add(pid)
    return saved


def get_product_links_from_category_page(page: Page, max_links: int = 100) -> list[str]:
    """
    현재 페이지(카테고리 BEST)에서 1~100위 상품 링크 수집 (순서 유지).
    동일 상품의 '상품정보'·'리뷰' 링크가 둘 다 있으면 상품정보 URL만 1건으로 통일해,
    최대 100개 상품까지 수집되도록 함.
    """
    seen_ids: set[str] = set()
    links: list[str] = []
    for sel in PRODUCT_LINK_SELECTORS:
        try:
            for el in page.locator(sel).all():
                if len(links) >= max_links:
                    return links[:max_links]
                href = el.get_attribute("href")
                parsed = _base_product_url_and_id(href or "")
                if not parsed:
                    continue
                base_url, product_id = parsed
                if product_id in seen_ids:
                    continue
                seen_ids.add(product_id)
                links.append(base_url)
        except Exception as e:
            logger.debug("상품 링크 수집 실패 %s: %s", sel, e)
        if len(links) >= max_links:
            break
    return links[:max_links]


def save_page_as_pdf(page: Page, path: Path, format: str = PDF_FORMAT) -> bool:
    """현재 페이지를 A5 PDF로 저장 (Chromium만 지원). 인쇄 직전 접힌 영역 한 번 더 펼침.

    실패 시 0KB/아주 작은 파일이 남지 않도록 자동 삭제한다.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # 인쇄 직전 접힌 상품설명 영역 한 번 더 강제 펼침 (PDF에 펼친 상태로 나오도록)
        try:
            page.evaluate(
                """() => {
                document.querySelectorAll('[class*="description"], [class*="detail"], [class*="상품설명"], [class*="content"]').forEach(el => {
                    const txt = (el.innerText || el.textContent || '').slice(0, 200);
                    if (txt.includes('리뷰') || txt.includes('review')) return;
                    el.style.maxHeight = 'none';
                    el.style.overflow = 'visible';
                    el.style.height = 'auto';
                    if (el.style.display === 'none') el.style.display = '';
                });
                }"""
            )
            page.wait_for_timeout(500)
        except Exception:
            pass
        page.pdf(
            path=str(path),
            format=format,
            print_background=True,
            margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"},
        )
        logger.info("  PDF 저장: %s", path)
        return True
    except Exception as e:
        logger.warning("PDF 저장 실패 %s: %s", path, e)
        # 예외가 난 경우 0KB/작은 파일이 남아 있다면 정리
        try:
            if path.exists() and path.stat().st_size < 512:
                path.unlink()
        except Exception:
            pass
        return False


def run_pdf_collection(
    output_dir: Path | None = None,
    headless: bool = False,
    max_categories: int | None = None,
    category_slug: str | None = None,
    progress_file: Path | None = None,
) -> int:
    """
    1. 29cm 방문 → BEST 클릭
    2. 각 카테고리(또는 지정 카테고리 1개) 페이지 방문
    3. 1~100위 상품 상세 페이지 방문 후 A5 PDF 저장

    category_slug: 지정 시 해당 카테고리만 수집 (예: "여성_의류").
    progress_file: 진행 로그를 쓸 파일 경로 (None이면 PROGRESS_FILE).

    Returns:
        저장한 PDF 파일 개수
    """
    out_root = output_dir or PDF_OUTPUT_DIR
    out_root = Path(out_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    prog = progress_file or PROGRESS_FILE

    p = None
    browser = None
    saved_count = 0
    categories = CATEGORY_BEST_URLS
    if category_slug:
        categories = [(name, url) for name, url in CATEGORY_BEST_URLS if name == category_slug]
        if not categories:
            _clear_progress(prog)
            _write_progress("error", message=f"알 수 없는 카테고리: {category_slug}", progress_file=prog)
            return 0
    elif max_categories is not None:
        categories = categories[: max_categories]

    _clear_progress(prog)
    _write_progress("start", message=f"카테고리 {len(categories)}개", progress_file=prog)

    try:
        p, browser, page = _open_browser(headless=headless)

        # 1) 29cm 방문, 베스트 메뉴 클릭
        visit_and_click_best(page)

        # 수집 브라우저를 최상단으로 (headless가 아닐 때, Windows)
        if not headless:
            page.wait_for_timeout(800)
            _bring_browser_window_to_front()

        for cat_name, cat_url in categories:
            _write_progress("category_start", category=cat_name, progress_file=prog)
            logger.info("카테고리: %s", cat_name)
            page.goto(cat_url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(1500)
            _behave_like_human(page, viewport_width=1280, viewport_height=720)

            product_urls = get_product_links_from_category_page(page, max_links=100)
            if not product_urls:
                logger.warning("  상품 링크 0건: %s", cat_url)
                _write_progress("category_end", category=cat_name, total_saved=saved_count, message="상품 0건", progress_file=prog)
                continue

            cat_dir = out_root / re.sub(r'[^\w\-_]', '_', cat_name)
            cat_dir.mkdir(parents=True, exist_ok=True)
            saved_ids = _get_saved_product_ids(cat_dir)
            if saved_ids:
                # 이미 저장된 PDF도 진행률에 포함되도록 saved_count 에 반영
                base_saved = len(saved_ids)
                saved_count += base_saved
                logger.info("  이미 저장된 상품 %d건 포함 (현재 총 %d건)", base_saved, saved_count)

            for rank, url in enumerate(product_urls, start=1):
                product_id = url.rstrip("/").split("/")[-1].replace("_review", "").replace("/review", "") or f"rank{rank}"
                if product_id in saved_ids:
                    _write_progress("product_skipped", category=cat_name, current=rank, total_saved=saved_count, message=url, progress_file=prog)
                    logger.debug("  건너뜀 (이미 저장됨): %s", url)
                    continue
                try:
                    _write_progress("product", category=cat_name, current=rank, total_saved=saved_count, message=url, progress_file=prog)
                    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    page.wait_for_timeout(1000)
                    _behave_like_human(page, viewport_width=1280, viewport_height=720)
                    expand_detail_before_pdf(page, product_url=url)
                    # goto 하지 않음 — 펼친 상태를 유지한 채 PDF 저장
                    safe_id = re.sub(r'[^\w\-.]', '_', product_id)[:80]
                    pdf_path = cat_dir / f"{rank:02d}_{safe_id}.pdf"
                    if save_page_as_pdf(page, pdf_path):
                        saved_count += 1
                        _write_progress("product_saved", category=cat_name, current=rank, total_saved=saved_count, message=str(pdf_path), progress_file=prog)
                except Exception as e:
                    logger.warning("  %d위 상세 페이지 PDF 실패: %s", rank, e)
                    _write_progress("product_error", category=cat_name, current=rank, total_saved=saved_count, message=str(e), progress_file=prog)

            _write_progress("category_end", category=cat_name, total_saved=saved_count, progress_file=prog)

        _write_progress("complete", total_saved=saved_count, message=f"총 {saved_count}개 PDF 저장", progress_file=prog)
        return saved_count
    except Exception as e:
        logger.exception("PDF 수집 중 오류: %s", e)
        _write_progress("error", total_saved=saved_count, message=str(e), progress_file=prog)
        return saved_count
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        if p:
            try:
                p.stop()
            except Exception:
                pass

    return saved_count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    n = run_pdf_collection(headless=False)
    print(f"저장 완료: {n}개 PDF")
