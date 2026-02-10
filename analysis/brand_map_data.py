"""
브랜드 맵 데이터 집계 (AI 비의존).
PDF 분석 결과(상품별 스타일_축, 프리미엄_축, 대표색)를 브랜드별로 집계해
맵 좌표·크기·표시색을 계산합니다.
"""
from __future__ import annotations

from typing import Any

# 색상명 → hex (브랜드 표시색용, 대소문자 무시)
COLOR_NAME_TO_HEX: dict[str, str] = {
    "black": "#1a1a1a", "white": "#f5f5f5", "navy": "#1a237e", "blue": "#1565c0",
    "grey": "#616161", "gray": "#616161", "beige": "#c4a574", "brown": "#5d4037",
    "khaki": "#8b7355", "green": "#2e7d32", "red": "#c62828", "burgundy": "#880e4f",
    "pink": "#ad1457", "purple": "#6a1b9a", "yellow": "#f9a825", "orange": "#ef6c00",
    "ivory": "#f5f5dc", "cream": "#fffdd0", "charcoal": "#37474f", "mint": "#80cbc4",
    "olive": "#558b2f", "camel": "#c19a6b", "denim": "#1e88e5", "wine": "#6d1b1b",
}


def _color_to_hex(color: str) -> str:
    """대표색 문자열을 hex로. 이미 #이면 그대로, 아니면 COLOR_NAME_TO_HEX 조회."""
    if not color or not isinstance(color, str):
        return "#757575"  # 기본 회색
    s = color.strip()
    if s.startswith("#") and len(s) in (4, 7, 9):
        return s
    for part in s.replace(",", " ").split():
        part = part.strip()
        if part.startswith("#") and len(part) in (4, 7, 9):
            return part
        key = part.lower()
        if key in COLOR_NAME_TO_HEX:
            return COLOR_NAME_TO_HEX[key]
    return COLOR_NAME_TO_HEX.get(s.lower().replace(" ", ""), "#757575")


def build_brand_map_data(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    상품 리스트를 브랜드별로 집계.
    - style_axis: 브랜드별 **상품 수(item_count) 순위**를 0~100 구간으로 선형 매핑
    - premium_axis: 브랜드별 **평균 가격(avg_price) 순위**를 0~100 구간으로 선형 매핑
      (가격·상품 수라는 정량 값만으로도 어느 정도 포지셔닝 가능하도록 함)
    - item_count: 해당 브랜드 상품 수 (맵에서 버블 크기)
    - representative_color: 브랜드 대표색 (상품 대표색 중 첫 번째 → hex)
    - rank: item_count 기준 순위 (1=최다) → 색 농도에 사용
    """
    by_brand: dict[str, list[dict[str, Any]]] = {}
    for p in products:
        name = (p.get("브랜드명") or "").strip()
        if not name:
            continue
        if name not in by_brand:
            by_brand[name] = []
        by_brand[name].append(p)

    # 1차 집계: 브랜드별 평균 가격·상품 수·대표색만 모음
    raw: list[dict[str, Any]] = []
    for brand_name, items in by_brand.items():
        prices: list[int] = []
        colors: list[str] = []
        for p in items:
            c = (p.get("대표색") or "").strip() or (p.get("컬러_팔레트") or "")[:30] or (p.get("색상") or [])
            if isinstance(c, list) and c:
                c = str(c[0]).strip()
            if c:
                colors.append(str(c).strip())
            price = p.get("가격")
            if isinstance(price, (int, float)) and price is not None:
                prices.append(int(price))
        avg_price = sum(prices) / len(prices) if prices else None
        rep_color = colors[0] if colors else ""
        rep_hex = _color_to_hex(rep_color)
        raw.append({
            "brand_name": brand_name,
            "item_count": len(items),
            "avg_price": avg_price,
            "representative_color_hex": rep_hex,
        })

    if not raw:
        return []

    n = len(raw)

    def _rank_to_axis(rank: int, total: int, low: float = 8.0, high: float = 92.0) -> float:
        if total <= 1:
            return 50.0
        return low + (high - low) * (rank / (total - 1))

    # 가격 오름차순으로 premium_axis 배치 (저가→낮은 축, 고가→높은 축)
    sorted_by_price = sorted(
        raw,
        key=lambda x: (x["avg_price"] is None, x["avg_price"] if x["avg_price"] is not None else 0),
    )
    price_rank: dict[str, int] = {row["brand_name"]: i for i, row in enumerate(sorted_by_price)}

    # 상품 수 내림차순으로 style_axis 배치 (많이 팔리는/아이템 많은 브랜드를 한쪽으로)
    sorted_by_count = sorted(raw, key=lambda x: (-x["item_count"], x["brand_name"]))
    count_rank: dict[str, int] = {row["brand_name"]: i for i, row in enumerate(sorted_by_count)}

    result: list[dict[str, Any]] = []
    for row in raw:
        name = row["brand_name"]
        style_axis = _rank_to_axis(count_rank[name], n, low=8.0, high=92.0)
        premium_axis = _rank_to_axis(price_rank[name], n, low=8.0, high=92.0)
        result.append({
            "brand_name": name,
            "style_axis": round(style_axis, 1),
            "premium_axis": round(premium_axis, 1),
            "item_count": row["item_count"],
            "representative_color_hex": row["representative_color_hex"],
            "avg_price": int(row["avg_price"]) if row["avg_price"] is not None else None,
        })

    # rank: item_count 내림차순 1,2,3,...
    result.sort(key=lambda x: (-x["item_count"], x["brand_name"]))
    for i, row in enumerate(result, 1):
        row["rank"] = i

    return result
