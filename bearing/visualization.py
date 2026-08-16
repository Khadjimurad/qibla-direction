"""Визуализация направления на Каабу на статической карте."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Never

from PIL import ImageDraw, ImageFont
from PIL.ImageDraw import ImageDraw as ImageDrawType

from bearing.config import log_time
from bearing.geometry import (
    BearingMethod,
    best_wall_turn,
    bearing_deg,
    left_right_text,
    normalize_angle180,
    polygon_orientation_deg,
)
from bearing.map import TileSource, lonlat_to_img_px, static_map
from bearing.osm import get_address_from_coordinates, get_building_polygon

FONT_PATHS = (
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
)

TILE_SOURCE_LABELS: dict[TileSource, str] = {
    "yandex": "Яндекс.Карты",
    "cartodb": "CARTO",
    "osm": "OpenStreetMap",
}


@dataclass(frozen=True)
class QiblaResult:
    qibla: float
    qibla_great_circle: float
    qibla_vincenty: float
    building_axis: float
    wall_turn: float
    wall_name: str
    path: str
    building_found: bool
    address: str | None
    tile_source: TileSource


def draw_arrow(
    draw: ImageDrawType,
    x: float,
    y: float,
    bearing: float,
    length: float = 260,
    color: tuple[int, int, int] = (255, 0, 0),
    width: int = 6,
) -> None:
    """Стрелка: 0 = север, 90 = восток."""
    ang = math.radians(bearing)
    x2 = x + math.sin(ang) * length
    y2 = y - math.cos(ang) * length
    draw.line((x, y, x2, y2), width=width, fill=color)

    head = 22
    left = math.radians((bearing - 150) % 360)
    right = math.radians((bearing + 150) % 360)
    lx, ly = x2 + math.sin(left) * head, y2 - math.cos(left) * head
    rx, ry = x2 + math.sin(right) * head, y2 - math.cos(right) * head
    draw.polygon([(x2, y2), (lx, ly), (rx, ry)], fill=color)


def _load_font(size: int):
    for font_path in FONT_PATHS:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_north_arrow(draw: ImageDrawType, x: float, y: float, size: int = 40) -> None:
    draw_arrow(draw, x, y, 0, length=size, color=(0, 100, 0), width=4)
    font = _load_font(16)
    bbox = draw.textbbox((0, 0), "N", font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    draw.text((x - text_width // 2, y - size - text_height - 5), "N", fill=(0, 100, 0), font=font)


def draw_turn_arc(
    draw: ImageDrawType,
    cx: float,
    cy: float,
    from_bearing: float,
    to_bearing: float,
    radius: float = 120,
    color: tuple[int, int, int] = (255, 165, 0),
) -> None:
    """Дуга поворота от одного направления к другому."""
    turn = normalize_angle180(to_bearing - from_bearing)
    if abs(turn) < 5:
        return

    start_angle_deg = -from_bearing + 90
    end_angle_deg = -to_bearing + 90
    num_segments = max(10, min(30, int(abs(turn))))
    for i in range(num_segments):
        t1 = i / num_segments
        t2 = (i + 1) / num_segments
        angle1 = start_angle_deg + (end_angle_deg - start_angle_deg) * t1
        angle2 = start_angle_deg + (end_angle_deg - start_angle_deg) * t2
        x1 = cx + radius * math.cos(math.radians(angle1))
        y1 = cy + radius * math.sin(math.radians(angle1))
        x2 = cx + radius * math.cos(math.radians(angle2))
        y2 = cy + radius * math.sin(math.radians(angle2))
        draw.line((x1, y1, x2, y2), fill=color, width=4)


def _safe_output_path(address: str | None, lat: float, lon: float) -> str:
    if address:
        safe = re.sub(r'[<>:"/\\|?*]', "_", address)
        safe = safe.replace(",", "_").replace(" ", "_")
        safe = re.sub(r"_+", "_", safe).strip("_")
        if len(safe) > 100:
            safe = safe[:100]
        return f"qibla_{safe}.png"
    return f"qibla_{lat:.5f}_{lon:.5f}.png".replace(".", "_").replace(",", "_")


def build_qibla_image(
    lat: float,
    lon: float,
    out_path: str | None = None,
    zoom: int = 19,
    size_px: int = 900,
    radius_m: int = 150,
    tile_source: TileSource = "yandex",
    method: BearingMethod = "great_circle",
) -> QiblaResult:
    """Карта с направлением на Каабу и подсказкой по стенам здания."""
    log_time(f"Начало обработки координат: {lat:.5f}, {lon:.5f}")

    qibla_great_circle = bearing_deg(lat, lon, method="great_circle")
    qibla_vincenty = bearing_deg(lat, lon, method="vincenty")
    if method == "vincenty":
        qibla = qibla_vincenty
    elif method in ("great_circle", "spherical"):
        qibla = qibla_great_circle
    else:
        unreachable: Never = method
        raise ValueError(f"Неизвестный метод расчёта bearing: {unreachable}")

    log_time(
        f"Направление на Каабу: {qibla:.2f}° "
        f"(great_circle: {qibla_great_circle:.2f}°, vincenty: {qibla_vincenty:.2f}°)"
    )

    address = get_address_from_coordinates(lat, lon)
    if out_path is None:
        out_path = _safe_output_path(address, lat, lon)

    poly = get_building_polygon(lat, lon, radius_m=radius_m)
    building_found = poly is not None

    log_time("Загрузка карты...")
    img, top_left_world, zoom, used_source = static_map(
        lat, lon, zoom=zoom, size_px=size_px, tile_source=tile_source
    )
    draw = ImageDraw.Draw(img)

    user_x, user_y = lonlat_to_img_px(lon, lat, top_left_world, zoom)
    bldg_axis = 0.0
    wall_turn = 0.0
    wall_name = ""
    cx, cy = user_x, user_y

    if building_found and poly is not None:
        log_time("Вычисление ориентации здания...")
        bldg_axis = polygon_orientation_deg(poly)
        log_time(f"Ось здания (самая длинная сторона): {bldg_axis:.1f}°")

        _, wall_turn, wall_name = best_wall_turn(bldg_axis, qibla)
        log_time(
            f"Стена: {wall_name} , поворот от перпендикуляра: {wall_turn:+.2f}°"
        )

        pts = [lonlat_to_img_px(plon, plat, top_left_world, zoom) for (plon, plat) in poly]
        draw.polygon(pts, outline=(0, 0, 255), width=6)
        draw.polygon(pts, outline=(255, 255, 255), width=2)
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)

    marker_r = 8
    draw.ellipse(
        (user_x - marker_r, user_y - marker_r, user_x + marker_r, user_y + marker_r),
        fill=(255, 255, 0),
        outline=(0, 0, 0),
        width=2,
    )
    draw_north_arrow(draw, 50, 50, size=35)
    draw_arrow(draw, cx, cy, qibla, length=300)

    if building_found:
        turn_text = left_right_text(wall_turn)
        text_lines = [
            f"Кибла: {qibla:.2f}° (gc:{qibla_great_circle:.2f}° v:{qibla_vincenty:.2f}°)",
            f"От перпендикуляра к {wall_name} стене",
            f"повернись на {turn_text}",
        ]
    else:
        text_lines = [
            f"Кибла: {qibla:.2f}° (gc:{qibla_great_circle:.2f}° v:{qibla_vincenty:.2f}°)",
            "Контур здания не найден",
            "Используй компас для ориентации",
        ]

    font = _load_font(26)
    line_height = 0
    for line in text_lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_height = max(line_height, bbox[3] - bbox[1])

    line_spacing = 8
    total_height = len(text_lines) * (line_height + line_spacing) - line_spacing
    padding = 18
    draw.rectangle((10, 10, size_px - 10, total_height + padding * 2), fill=(255, 255, 255))

    y_offset = padding
    for line in text_lines:
        draw.text((padding, y_offset), line, fill=(0, 0, 0), font=font)
        draw.text((padding + 1, y_offset + 1), line, fill=(0, 0, 0), font=font)
        y_offset += line_height + line_spacing

    tile_info_text = f"Карта: {TILE_SOURCE_LABELS[used_source]}"
    info_font = _load_font(16)
    info_bbox = draw.textbbox((0, 0), tile_info_text, font=info_font)
    info_width = info_bbox[2] - info_bbox[0]
    info_height = info_bbox[3] - info_bbox[1]
    info_padding = 8
    info_x = 10
    info_y = size_px - info_height - info_padding - 10
    draw.rectangle(
        (
            info_x,
            info_y - info_padding,
            info_x + info_width + info_padding * 2,
            info_y + info_height + info_padding,
        ),
        fill=(255, 255, 255),
    )
    draw.text((info_x + info_padding, info_y), tile_info_text, fill=(100, 100, 100), font=info_font)

    log_time("Сохранение изображения...")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    log_time(f"Изображение сохранено: {out_path}")

    return QiblaResult(
        qibla=qibla,
        qibla_great_circle=qibla_great_circle,
        qibla_vincenty=qibla_vincenty,
        building_axis=bldg_axis,
        wall_turn=wall_turn,
        wall_name=wall_name,
        path=out_path,
        building_found=building_found,
        address=address,
        tile_source=used_source,
    )
