"""
Bearing - модуль для вычисления направления на Каабу и визуализации на карте.
"""

from bearing.geometry import (
    bearing_deg, normalize_angle180, polygon_orientation_deg,
    left_right_text, best_wall_turn, smallest_turn, bearing_of_segment
)
from bearing.osm import overpass_building_polygon, get_building_polygon
from bearing.map import latlon_to_world_px, fetch_tile, static_map, lonlat_to_img_px
from bearing.visualization import draw_arrow, build_qibla_image, draw_north_arrow, draw_turn_arc

__all__ = [
    'bearing_deg',
    'normalize_angle180',
    'polygon_orientation_deg',
    'left_right_text',
    'best_wall_turn',
    'smallest_turn',
    'bearing_of_segment',
    'overpass_building_polygon',
    'get_building_polygon',
    'latlon_to_world_px',
    'fetch_tile',
    'static_map',
    'lonlat_to_img_px',
    'draw_arrow',
    'build_qibla_image',
    'draw_north_arrow',
    'draw_turn_arc',
]

