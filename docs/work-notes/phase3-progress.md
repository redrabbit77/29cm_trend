# Phase 3 진행 노트 (Local Agent)

## 작성 일시
2026-02-02

## 현재 완료된 항목

### 3.1 에이전트 실행 구조
- **단일 실행 구조**: Streamlit에서 "수집 시작" 시 `agent.run_one` 서브프로세스로 작업 실행
- **run_one.py**: `python -m agent.run_one <task_id>` — 작업 1건 claim → `run_worker_subprocess` 호출
- **run_worker_subprocess**: 별도 프로세스에서 Playwright 실행 (Sync API / asyncio 충돌 회피)
- **실패 시**: 작업 상태 `failed` 업데이트 후 DB에서 해당 작업 삭제 (`delete_task`)

### 3.2 브라우저 및 스크래핑
- Playwright Chromium(Chrome) 실행, 29CM BEST 목록 URL 접근
- **BEST 링크 수집**: `_collect_best_items` — DOM `a[href*='catalog/']` 등 + script JSON 후보
- **상품 상세 파싱**: `_scrape_product_detail` — h1, 상호명, 가격, script JSON(itemName, brandNameKor, sellPrice), **상품설명**(JSON-LD/__NEXT_DATA__/DOM), **사이즈·색상**(__NEXT_DATA__/테이블/script), 이미지 URL
- **대표 이미지**: JSON-LD schema.org Product `image[].contentUrl` 1순위 추출

### 3.3 이미지 수집
- **1순위**: 요소 스크린샷 (`_collect_images_by_screenshot`) — 상품 갤러리·상품설명 영역만 대상, 배너/클릭 객체 내 이미지 제외, **더보기 클릭 후 전체 스크롤**하여 상세 이미지 노출 후 수집 (최대 80장)
- **2순위**: URL 기반 — JSON-LD → __NEXT_DATA__ 상품 이미지 → script/DOM 순으로 URL 추출 후 `collect_and_upload_images`
- **로컬 저장**: `images/{product_id}/lookbook_001.jpg` 등 (설정: `LOCAL_IMAGE_DIR`)
- **Supabase**: Storage 버킷 없으면 자동 생성, bytes 업로드, `product_images` 테이블 insert

### 3.4 수집 관리 UI
- **최근 수집 결과 (로그)**: `logs/last_task_result.txt` 내용을 수집 관리 페이지에 표시 — 실행 결과를 앱에서 바로 확인 가능
- **개별 작업 삭제**: 수집 관리 페이지에서 체크박스로 작업 선택 후 "선택한 작업 삭제" (Supabase 클라이언트로 직접 삭제)
- **기존 로컬 이미지 DB 반영**: "로컬 이미지 DB 반영 실행" 버튼 — 서브프로세스 `python -m agent.sync_local_images` 실행, `images/` 스캔 후 Storage·product_images 반영
- **수집 결과 보기**: ~~`collected_view`~~ (레거시 제거로 페이지 삭제됨)

### 3.5 DataService
- `get_product_images(product_id)`, `create_product_image`, `upload_image_to_storage`, `delete_task`, `update_task_status` 등 구현

## 다음 단계 (권장)

1. **29CM DOM 셀렉터 검증**: 실제 29CM 상세 페이지 구조에 맞게 `BEST_ITEM_LINK_SELECTORS`, `PRODUCT_IMAGE_SELECTORS`, 가격/브랜드 셀렉터 점검·보강 (브라우저 개발자 도구로 확인 후 상수 업데이트)
2. **카테고리별 URL 매핑**: `_category_to_url`에서 남성/카테고리별 `category_large_code` 매핑 확장
3. ~~**진행률·로그 가시화**~~: 수집 관리 페이지에 `logs/last_task_result.txt` 표시 완료
4. **Phase 4**: 브랜드 맵 고도화, 텍스트 기반 컨셉 스코어, 통계 대시보드 (tasks.md Phase 4 참고)

## 기술 스택

- **브라우저 자동화**: Playwright (sync_api), Chromium
- **이미지**: 요소 스크린샷 + URL 다운로드(httpx), Supabase Storage + product_images
- **작업 흐름**: Streamlit → collection_tasks INSERT → run_one 서브프로세스 → claim_task → run_collection_task → 완료/실패 시 상태 업데이트·실패 시 삭제
