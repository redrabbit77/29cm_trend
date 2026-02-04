"""
status='failed'인 수집 작업을 DB에서 모두 삭제.

사용: 프로젝트 루트에서
  python -m scripts.delete_failed_tasks
"""
from pathlib import Path
import sys

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from shared.services import DataService


def main() -> None:
    service = DataService(use_service_key=True)
    n = service.delete_failed_tasks()
    print(f"삭제 완료: failed 상태 작업 {n}건")


if __name__ == "__main__":
    main()
