"""
Bearing — направление на Каабу и визуализация на карте.
"""

from bearing.config import APP_VERSION, YANDEX_API_KEY
from bearing.geometry import (
    bearing_deg,
    bearing_of_segment,
    best_wall_turn,
    left_right_text,
    normalize_angle180,
    polygon_orientation_deg,
    smallest_turn,
)
from bearing.map import fetch_tile, latlon_to_world_px, lonlat_to_img_px, static_map
from bearing.osm import get_building_polygon, overpass_building_polygon
from bearing.visualization import (
    QiblaResult,
    build_qibla_image,
    draw_arrow,
    draw_north_arrow,
    draw_turn_arc,
)

__version__ = APP_VERSION

__all__ = [
    "QiblaResult",
    "YANDEX_API_KEY",
    "__version__",
    "bearing_deg",
    "bearing_of_segment",
    "best_wall_turn",
    "build_qibla_image",
    "draw_arrow",
    "draw_north_arrow",
    "draw_turn_arc",
    "fetch_tile",
    "get_building_polygon",
    "latlon_to_world_px",
    "left_right_text",
    "lonlat_to_img_px",
    "normalize_angle180",
    "overpass_building_polygon",
    "polygon_orientation_deg",
    "smallest_turn",
    "static_map",
]
