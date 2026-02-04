#!/usr/bin/env python
"""
에이전트 실행 결과 확인 스크립트.

사용법:
    python show_agent_results.py

Supabase에서 최근 수집 작업 목록을 조회해 콘솔에 출력하고,
logs/agent_results.txt 에도 저장합니다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared.services import DataService


def main() -> None:
    # .env 로드 (DataService가 pydantic-settings로 로드하므로 필수 아님)
    env = Path(".env")
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    service = DataService(use_service_key=True)
    tasks = service.get_tasks(status=None, limit=20)

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("에이전트 실행 결과 (최근 수집 작업)")
    lines.append("=" * 60)
    if not tasks:
        lines.append("작업이 없습니다.")
    else:
        for t in tasks:
            lines.append("")
            lines.append(f"  작업 ID: {t.id}")
            lines.append(f"  카테고리 ID: {t.category_id}")
            lines.append(f"  상태: {t.status}")
            lines.append(f"  진행률: {t.progress or 0}%")
            lines.append(f"  총/완료 항목: {t.total_items or 0} / {t.collected_items or 0}")
            if t.started_at:
                lines.append(f"  시작: {t.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
            if t.completed_at:
                lines.append(f"  완료: {t.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
            if t.error_message:
                lines.append(f"  에러: {t.error_message[:200]}")
            lines.append("-" * 40)
    lines.append("")
    text = "\n".join(lines)

    print(text)

    # logs/agent_results.txt 에 저장
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    out_file = log_dir / "agent_results.txt"
    out_file.write_text(text, encoding="utf-8")
    print(f"결과가 저장되었습니다: {out_file.absolute()}")


if __name__ == "__main__":
    main()
