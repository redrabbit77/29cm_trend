"""
인간 행동 모사 유틸리티 모듈.

Phase 3 계획서의 5.x 섹션에 해당하는 기능을
실제 동작 가능한 형태로 구현한 1차 버전입니다.
"""
from __future__ import annotations

import math
import random
import time
from typing import List, Tuple

import pyautogui

Point = Tuple[int, int]


def generate_bezier_path(
    start: Point,
    end: Point,
    control_points: List[Point] | None = None,
    num_points: int = 50,
) -> List[Point]:
    """
    베지어 곡선을 따라 마우스 경로 생성.

    - start/end 사이에 1~2개의 랜덤 제어점을 생성해 자연스러운 곡선 생성
    - num_points 개수만큼의 중간 좌표를 반환
    """
    if num_points < 2:
        num_points = 2

    sx, sy = start
    ex, ey = end

    if control_points is None:
        # start/end 를 기준으로 살짝 위/아래로 휘는 제어점 2개 생성
        mid_x = (sx + ex) / 2
        delta_x = ex - sx
        delta_y = ey - sy or 1
        cp1 = (
            int(sx + delta_x * 0.3),
            int(sy + delta_y * 0.3 + random.randint(-40, 40)),
        )
        cp2 = (
            int(sx + delta_x * 0.7),
            int(sy + delta_y * 0.7 + random.randint(-40, 40)),
        )
        control_points = [cp1, cp2]

    if len(control_points) == 1:
        # 2차 베지어
        (cx, cy) = control_points[0]

        def quad_bezier(t: float) -> Point:
            x = (1 - t) ** 2 * sx + 2 * (1 - t) * t * cx + t**2 * ex
            y = (1 - t) ** 2 * sy + 2 * (1 - t) * t * cy + t**2 * ey
            return int(x), int(y)

        return [quad_bezier(i / (num_points - 1)) for i in range(num_points)]

    # 3차 베지어 (기본)
    (c1x, c1y), (c2x, c2y) = control_points[:2]

    def cubic_bezier(t: float) -> Point:
        x = (
            (1 - t) ** 3 * sx
            + 3 * (1 - t) ** 2 * t * c1x
            + 3 * (1 - t) * t**2 * c2x
            + t**3 * ex
        )
        y = (
            (1 - t) ** 3 * sy
            + 3 * (1 - t) ** 2 * t * c1y
            + 3 * (1 - t) * t**2 * c2y
            + t**3 * ey
        )
        return int(x), int(y)

    return [cubic_bezier(i / (num_points - 1)) for i in range(num_points)]


def random_delay(min_seconds: float = 0.5, max_seconds: float = 2.0) -> None:
    """인간의 불규칙한 행동을 흉내 내는 랜덤 딜레이."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def move_mouse_human_like(start: Point | None, end: Point) -> None:
    """
    인간처럼 자연스러운 마우스 이동.

    - 베지어 곡선 경로 생성
    - 각 포인트마다 소량의 랜덤 딜레이
    """
    if start is None:
        start = pyautogui.position()

    path = generate_bezier_path(start, end, num_points=random.randint(30, 70))
    for x, y in path:
        pyautogui.moveTo(x, y, duration=0)  # 시간은 sleep 로 제어
        time.sleep(random.uniform(0.003, 0.012))


def random_scroll() -> None:
    """랜덤 스크롤 (페이지 탐색 시뮬레이션)."""
    amount = random.randint(-800, 800)
    if amount == 0:
        return
    pyautogui.scroll(amount)
    random_delay(0.2, 0.8)


def random_mouse_movement() -> None:
    """랜덤 마우스 움직임 (활성 상태 유지 및 인간 행동 흉내)."""
    width, height = pyautogui.size()
    cur_x, cur_y = pyautogui.position()
    # 화면 내 임의의 위치로 살짝 이동
    target = (
        max(0, min(width - 1, cur_x + random.randint(-200, 200))),
        max(0, min(height - 1, cur_y + random.randint(-150, 150))),
    )
    move_mouse_human_like((cur_x, cur_y), target)
    random_delay(0.1, 0.5)


__all__ = [
    "generate_bezier_path",
    "move_mouse_human_like",
    "random_delay",
    "random_scroll",
    "random_mouse_movement",
]

