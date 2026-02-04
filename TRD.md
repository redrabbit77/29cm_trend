# [TRD] 29CM 하이브리드 수집 및 분석 시스템 기술 명세서
-TDD/Speck kit 기반개발 
-작업내용은 항상 Commit으로 만든다
-작업후 작업노트를 정리해서 md파일로 백업해둔다.
## 1. 시스템 아키텍처
본 시스템은 **Web Control Plane**과 **Local Execution Plane**의 하이브리드 구조로 구성됩니다.
- **Web UI**: 사용자의 명령 수신 및 데이터 시각화 (Streamlit 기반).
- **Local Agent**: 사용자 PC에서 실제 브라우저를 제어하여 데이터 수집 (Playwright 기반).
- **Central DB**: 수집 데이터 공유 및 상태 동기화 (Supabase 기반).

## 2. 기술 스택 (Tech Stack)
- **언어**: Python 3.10+
- **웹 인터페이스**: Streamlit
- **데이터베이스**: Supabase (PostgreSQL - Free Tier)
- **수집 엔진**: Playwright (Python Library)
- **인간 행위 모사**: PyAutoGUI, pyperclip
- **통신**: Supabase Realtime 또는 FastAPI (Local Tunneling)

## 3. 상세 기술 구현 방안
### 3.1 인간 행동 모사 알고리즘
- **Mouse Movement**: 베지어 곡선(Bezier Curve) 알고리즘을 사용하여 마우스 경로 생성.
- **Text Scraping**: 마우스 드래그 -> `Ctrl+C` -> `pyperclip.paste()`로 텍스트 수집.
- **Image Saving**: 우클릭 -> 단축키 'V'(이미지 저장) -> 파일명 자동 입력 흐름 모사.

### 3.2 데이터 동기화 프로세스
1. **Web (Streamlit)**: 유저가 수집 요청을 Supabase `tasks` 테이블에 저장.
2. **Local Agent**: `tasks` 테이블 실시간 감지 후 수집 루틴 실행.
3. **Storage**: 수집된 이미지는 로컬 저장 후 Supabase Storage로 업로드.

## 4. 비용 절감 설계 (Zero-Cost Plan)
- **Hosting**: Streamlit Community Cloud (무료)
- **Database**: Supabase Free Tier (무료)
- **Scraping**: 본인 소유의 데스크탑 PC 자원 활용.