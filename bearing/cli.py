"""CLI: python -m bearing <lat> <lon>"""

from __future__ import annotations

import argparse
import sys
from typing import cast

from bearing.geometry import BearingMethod, left_right_text
from bearing.map import TileSource
from bearing.visualization import build_qibla_image


def parse_coordinate(value: str) -> float:
    """
    Координата с точкой или запятой. Допускается хвостовая запятая
    (например, «42.539388,»).
    """
    cleaned = str(value).strip().rstrip(",")
    return float(cleaned.replace(",", "."))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bearing",
        description="Направление на Каабу и карта с ориентацией здания",
    )
    parser.add_argument(
        "lat",
        type=parse_coordinate,
        help="Широта (точка или запятая)",
    )
    parser.add_argument(
        "lon",
        type=parse_coordinate,
        help="Долгота (точка или запятая)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Путь к PNG (по умолчанию — из адреса или координат)",
    )
    parser.add_argument(
        "-z", "--zoom",
        type=int,
        default=19,
        help="Зум карты (по умолчанию: 19)",
    )
    parser.add_argument(
        "-r", "--radius",
        type=int,
        default=150,
        help="Радиус поиска здания, м (по умолчанию: 150)",
    )
    parser.add_argument(
        "-s", "--size",
        type=int,
        default=900,
        help="Размер изображения, px (по умолчанию: 900)",
    )
    parser.add_argument(
        "--tile-source",
        choices=("yandex", "cartodb", "osm"),
        default="yandex",
        help="Источник карты: yandex (по умолчанию), cartodb или osm",
    )
    parser.add_argument(
        "--method",
        choices=("great_circle", "vincenty"),
        default="great_circle",
        help="Метод азимута: great_circle (по умолчанию) или vincenty",
    )

    args = parser.parse_args(argv)

    try:
        result = build_qibla_image(
            args.lat,
            args.lon,
            out_path=args.output,
            zoom=args.zoom,
            size_px=args.size,
            radius_m=args.radius,
            tile_source=cast(TileSource, args.tile_source),
            method=cast(BearingMethod, args.method),
        )
    except Exception as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1

    print(f"Сохранено: {result.path}")
    print(
        f"Кибла: {result.qibla:.2f}° "
        f"(great_circle: {result.qibla_great_circle:.2f}°, "
        f"vincenty: {result.qibla_vincenty:.2f}°)"
    )
    if result.building_found:
        print(f"Ось здания: {result.building_axis:.1f}°")
        print(
            f"От перпендикуляра к {result.wall_name} стене "
            f"повернись на {left_right_text(result.wall_turn)}"
        )
    else:
        print("Здание не найдено — используйте компас для ориентации")
    if result.address:
        print(f"Адрес: {result.address}")
    print(f"Карта: {result.tile_source}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
