## 작업 목록: 29CM 데이터 수집 엔진

이 문서는 `spec.md`와 `plan.md`를 기반으로 생성된 **실행 가능한 작업 리스트**입니다.  
Phase 순서대로 진행하되, 각 Phase 안에서는 의존성을 고려해 구현합니다.

---

## Phase 1: 기반 구조 구축 (공통/DB/설정)

### 1.1 공통 프로젝트 구조 생성
- [ ] `shared/` 디렉토리 생성
  - [ ] `shared/__init__.py` 생성
  - [ ] `shared/models/__init__.py` 생성
  - [ ] `shared/config/__init__.py` 생성
- [ ] `web/`, `agent/`, `docs/`, `logs/` 디렉토리 생성
- [ ] `docs/work-notes/` 디렉토리 생성 (작업 노트 저장용)

### 1.2 설정 및 환경 구성
- [ ] `shared/config/settings.py` 구현
  - [ ] `pydantic-settings` 기반 `Settings` 클래스 정의
  - [ ] Supabase URL/KEY, Storage 버킷명, 로깅 설정 등 포함
  - [ ] `.env`에서 환경 변수 읽도록 구현
- [ ] 프로젝트 루트에 `.env.example` 생성
  - [ ] `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY` 등 키 정의 (값은 비워두기)
  - [ ] 로컬 파일 저장 경로(`LOCAL_IMAGE_DIR`, `LOG_DIR`) 예시 포함

### 1.3 데이터 모델 및 Supabase 스키마
- [ ] `shared/models/category.py` 구현
  - [ ] `Category`, `CategoryCreate` Pydantic 모델 정의 (data-model.md 참고)
- [ ] `shared/models/brand.py` 구현
  - [ ] `Brand`, `BrandCreate` 모델 정의
- [ ] `shared/models/product.py` 구현
  - [ ] `Product`, `ProductCreate` 모델 정의 (size/color는 `List[str]` 처리)
- [ ] `shared/models/task.py` 구현
  - [ ] `CollectionTask`, `CollectionTaskCreate`, `CollectionTaskUpdate` 모델 정의
- [ ] `supabase/sql/initial_schema.sql` 생성
  - [ ] `data-model.md`의 마이그레이션 스크립트 전체 포함
  - [ ] 카테고리 초기 데이터 insert 포함
- [ ] README에 Supabase에서 `initial_schema.sql` 적용 방법 섹션 추가

### 1.4 Supabase 클라이언트 공통 래퍼
- [ ] `shared/services/supabase_client.py` 생성
  - [ ] `create_supabase_client()` 함수 구현 (anon/service 키 모두 지원)
  - [ ] 재사용 가능한 클라이언트 인스턴스 관리 (싱글톤 또는 모듈 레벨)
- [ ] `shared/services/data_service.py` 생성
  - [ ] 카테고리/브랜드/상품/작업 CRUD 공통 함수 정의 (plan.md의 API 설계 참조)

---

## Phase 2: Web Control Plane (Streamlit UI)

### 2.1 기본 Streamlit 앱 뼈대
- [ ] `web/app.py` 생성
  - [ ] 페이지 라우팅 구조 정의 (`pages/` 기반 멀티 페이지)
  - [ ] 공통 사이드바: 현재 Phase/환경 정보 표시
  - [ ] Supabase 클라이언트 초기화 및 캐싱
- [ ] `web/utils/config.py` 생성
  - [ ] Streamlit용 환경설정 헬퍼 (예: 페이지 타이틀, 로고 등)

### 2.2 수집 관리 페이지 (`web/pages/collection.py`)
- [ ] 카테고리 선택 UI 구현
  - [ ] Supabase에서 카테고리 목록 조회
  - [ ] 성별/카테고리별 필터 제공
- [ ] “수집 시작” 버튼 구현
  - [ ] 선택된 카테고리 기준 `collection_tasks` 레코드 생성
  - [ ] 생성된 작업 ID를 화면에 표시
- [ ] 작업 목록/상태 테이블 구현
  - [ ] 최근 작업 목록을 테이블로 표시 (상태/진행률/에러 메시지 등)
  - [ ] 상태별 필터 (pending/running/completed/failed)
- [ ] 작업 상태 실시간 업데이트
  - [ ] 일정 주기 polling 또는 Realtime 구독으로 진행률 갱신

### 2.3 데이터 대시보드 페이지 (`web/pages/dashboard.py`)
- [ ] 기본 테이블 뷰 구현
  - [ ] `products`, `brands`, `categories` join 결과를 테이블로 표시
  - [ ] 페이지네이션 및 컬럼별 정렬
- [ ] 필터링 기능
  - [ ] 브랜드별/카테고리별/가격 범위별/수집 날짜별 필터
- [ ] 데이터 내보내기 기능
  - [ ] 현재 필터가 적용된 데이터를 CSV로 다운로드

### 2.4 브랜드 맵 페이지 (`web/pages/visualization.py`)
- [ ] 축(X/Y) 선택 UI
  - [ ] 가격, 컨셉(텍스트 분석 placeholder), 무드(이미지 분석 placeholder), 인기도 등 옵션 제공
- [ ] Plotly 기반 브랜드 맵 시각화
  - [ ] 브랜드별 포인트 위치 표시
  - [ ] Hover 시 브랜드/대표 상품 정보 표시
  - [ ] 클릭 시 상세 정보(상품 리스트) 모달/expander로 표시

---

## Phase 3: Local Agent (Playwright + 인간 행동 모사)

### 3.1 에이전트 메인 구조 (`agent/main.py`)
- [ ] CLI 엔트리포인트 구현
  - [ ] `python agent/main.py --mode run-once` 등 모드 인자 처리
  - [ ] 설정 로딩 및 로깅 초기화
- [ ] Supabase Realtime 구독 시작
  - [ ] `collection_tasks` 테이블 구독
  - [ ] 새로운 `pending` 작업 감지 시 큐에 추가

### 3.2 작업 모니터/큐 (`agent/collector/task_monitor.py`)
- [ ] 작업 큐 관리 클래스 구현
  - [ ] 새 작업 enqueue/dequeue
  - [ ] 실행 중 작업 상태 추적
- [ ] 상태 업데이트 헬퍼
  - [ ] `running`/`completed`/`failed` 상태 업데이트
  - [ ] 진행률/에러 메시지 반영

### 3.3 브라우저 관리 (`agent/collector/browser_manager.py`)
- [ ] Playwright 브라우저 초기화 함수 구현
  - [ ] Chromium 기반 기본 브라우저
  - [ ] User-Agent/locale/timezone 설정 (research.md 예시 활용)
- [ ] 브라우저 컨텍스트/페이지 관리
  - [ ] 각 작업 단위로 새 컨텍스트 생성
  - [ ] 작업 종료 시 컨텍스트 정리

### 3.4 인간 행동 모사 모듈
- [ ] `agent/collector/human_behavior.py` 구현
  - [ ] `move_mouse_human_like`, `extract_text_by_selection`, `save_image_human_like` 등 stub 구현 채우기
- [ ] `agent/utils/bezier.py` 구현
  - [ ] 베지어 곡선 기반 경로 생성 함수 구현 (numpy 사용 가능)
- [ ] `agent/utils/image_handler.py` 구현
  - [ ] 로컬 임시 디렉토리에 이미지 저장
  - [ ] Supabase Storage 업로드 후 URL 반환

### 3.5 스크래핑 로직 (`agent/collector/scraper.py`)
- [ ] 29CM BEST 목록 페이지 접근 로직 구현
  - [ ] 카테고리/성별별 BEST 1~10 URL 패턴 조사 (초기 하드코딩 후 점진 개선)
- [ ] 상품 상세 페이지 파서 구현
  - [ ] 브랜드명, 상품명, 가격, 사이즈, 색상, 상세 설명 추출
  - [ ] 룩북 이미지 URL/요소 선택 및 다운로드
- [ ] 에러 처리/재시도
  - [ ] 네트워크 에러 시 재시도 (지수 백오프)
  - [ ] 특정 상품 실패 시 로그만 남기고 다음 상품 진행

---

## Phase 4: 시각화 및 대시보드 고도화

### 4.1 브랜드 맵 고도화
- [ ] 간단한 텍스트 기반 컨셉 스코어 계산 (키워드 기반, 1차 버전)
- [ ] 가격/컨셉/무드 축 조합별 프리셋 제공
- [ ] 브랜드 필터/검색 기능 추가

### 4.2 통계 대시보드
- [ ] 브랜드별 상품 수/평균 가격/랭킹 분포 카드 위젯
- [ ] 카테고리별 가격 분포 차트
- [ ] 수집 현황(최근 N일) 타임라인 차트

---

## Phase 5: 테스팅, 최적화, 봇 회피 검증

### 5.1 단위 테스트
- [ ] `shared/models`에 대한 Pydantic 모델 테스트
- [ ] `agent/utils/bezier.py`의 경로 생성 테스트
- [ ] `agent/collector/human_behavior.py`의 시간/경로 특성 테스트 (기본 검증)

### 5.2 통합 테스트
- [ ] 로컬 Supabase 대체(mock 또는 테스트 프로젝트) 환경에서
  - [ ] 작업 생성 → 에이전트 실행 → 데이터 저장까지 end-to-end 흐름 테스트
- [ ] Streamlit UI에서 작업 생성 → 에이전트 수집 → 대시보드 표시까지 수동 E2E 검증

### 5.3 성능/봇 탐지 회피
- [ ] 수집 속도/성공률 측정 스크립트 작성 (간단한 로그 분석)
- [ ] 다양한 딜레이/행동 패턴 설정 실험
- [ ] 29CM 측에서 차단 조짐이 보일 경우 대응 전략 정리 (요청 빈도 감소 등)

---

## 메타 작업

- [ ] 각 Phase/주요 기능 완료 시 `docs/work-notes/`에 작업 노트 작성
- [ ] 의미 있는 기능 단위로 Git 커밋 생성 (TRD 원칙 준수)
- [ ] README에 구현 진행 상황(체크리스트 형태) 반영

