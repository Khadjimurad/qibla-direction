"""Геометрические вычисления: bearing, нормализация углов, ориентация полигонов."""

from __future__ import annotations

import math
import sys
from typing import Literal, Never, Sequence

# Координаты Каабы (Мекка, Саудовская Аравия)
# Источник: Google Earth
KAABA_LAT = 21.4225390
KAABA_LON = 39.8261964

EARTH_RADIUS_M = 6_371_000.0

BearingMethod = Literal["great_circle", "vincenty", "spherical"]
LonLat = tuple[float, float]


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние между двумя точками по сфере, в метрах."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlat = phi2 - phi1
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(min(1.0, a)))


def bearing_deg_vincenty(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Начальный азимут по формуле Vincenty (эллипсоид WGS84).
    Точнее сферической формулы на больших расстояниях.
    """
    f = 1 / 298.257223563

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    L = math.radians(lon2 - lon1)

    U1 = math.atan((1 - f) * math.tan(phi1))
    U2 = math.atan((1 - f) * math.tan(phi2))
    sin_U1 = math.sin(U1)
    cos_U1 = math.cos(U1)
    sin_U2 = math.sin(U2)
    cos_U2 = math.cos(U2)

    lambda_val = L
    sin_lambda = math.sin(L)
    cos_lambda = math.cos(L)

    for _ in range(100):
        sin_lambda = math.sin(lambda_val)
        cos_lambda = math.cos(lambda_val)
        sin_sigma = math.sqrt(
            (cos_U2 * sin_lambda) ** 2
            + (cos_U1 * sin_U2 - sin_U1 * cos_U2 * cos_lambda) ** 2
        )
        if sin_sigma == 0:
            return 0.0

        cos_sigma = sin_U1 * sin_U2 + cos_U1 * cos_U2 * cos_lambda
        sigma = math.atan2(sin_sigma, cos_sigma)
        sin_alpha = cos_U1 * cos_U2 * sin_lambda / sin_sigma
        cos2_alpha = 1 - sin_alpha ** 2

        if cos2_alpha == 0:
            cos_2sigma_m = 0.0
        else:
            cos_2sigma_m = cos_sigma - 2 * sin_U1 * sin_U2 / cos2_alpha

        C = f / 16 * cos2_alpha * (4 + f * (4 - 3 * cos2_alpha))
        lambda_prev = lambda_val
        lambda_val = L + (1 - C) * f * sin_alpha * (
            sigma + C * sin_sigma * (
                cos_2sigma_m + C * cos_sigma * (-1 + 2 * cos_2sigma_m ** 2)
            )
        )
        if abs(lambda_val - lambda_prev) < 1e-12:
            break

    alpha1 = math.atan2(
        cos_U2 * sin_lambda,
        cos_U1 * sin_U2 - sin_U1 * cos_U2 * cos_lambda,
    )
    return (math.degrees(alpha1) + 360) % 360


def bearing_deg_great_circle(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Начальный азимут по ортодромии (большой круг на сфере).
    Тот же алгоритм, что и классическая сферическая формула initial bearing.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    y = math.sin(dlam) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def bearing_deg(
    lat1: float,
    lon1: float,
    lat2: float = KAABA_LAT,
    lon2: float = KAABA_LON,
    method: BearingMethod = "great_circle",
) -> float:
    """
    Азимут от (lat1, lon1) к (lat2, lon2). По умолчанию — на Каабу.

    method:
        great_circle / spherical — ортодромия на сфере (как в большинстве карт)
        vincenty — эллипсоид WGS84
    """
    if method == "vincenty":
        return bearing_deg_vincenty(lat1, lon1, lat2, lon2)
    if method in ("great_circle", "spherical"):
        return bearing_deg_great_circle(lat1, lon1, lat2, lon2)
    unreachable: Never = method
    raise ValueError(f"Неизвестный метод расчёта bearing: {unreachable}")


def normalize_angle180(a: float) -> float:
    """Нормализует угол в диапазон -180..+180 градусов."""
    return (a + 180) % 360 - 180


def left_right_text(angle_deg: float) -> str:
    """Форматирует угол поворота: «X.XX° вправо/влево»."""
    a = normalize_angle180(angle_deg)
    if abs(a) < 0.01:
        return f"{a:.2f}° (почти ровно)"
    return f"{abs(a):.2f}° {'вправо' if a > 0 else 'влево'}"


def smallest_turn(from_deg: float, to_deg: float) -> float:
    """Минимальный поворот от одного направления к другому (-180..+180)."""
    return normalize_angle180(to_deg - from_deg)


def direction_to_cardinal(deg: float) -> str:
    """Сторона света в родительном падеже (северной, восточной, …)."""
    deg = deg % 360
    if 315 <= deg or deg < 45:
        return "северной"
    if 45 <= deg < 135:
        return "восточной"
    if 135 <= deg < 225:
        return "южной"
    return "западной"


def best_wall_turn(
    axis_deg: float,
    qibla_deg: float,
    debug: bool = False,
) -> tuple[float, float, str]:
    """
    Стена, чей перпендикуляр ближе всего к кибле, и угол поворота до киблы.

    Returns:
        (направление стены, угол поворота, название стены)
    """
    wall_candidates = [
        axis_deg,
        (axis_deg + 90) % 360,
        (axis_deg + 180) % 360,
        (axis_deg + 270) % 360,
    ]

    best_wall = wall_candidates[0]
    best_turn = 0.0
    min_turn_abs = float("inf")

    if debug:
        print(f"  Анализ стен для киблы {qibla_deg:.1f}°:", file=sys.stderr)

    for wall_dir in wall_candidates:
        angle_wall_qibla = abs(smallest_turn(wall_dir, qibla_deg))
        perp1 = (wall_dir + 90) % 360
        perp2 = (wall_dir - 90) % 360
        turn1 = smallest_turn(perp1, qibla_deg)
        turn2 = smallest_turn(perp2, qibla_deg)

        if abs(turn1) < abs(turn2):
            turn = turn1
            used_perp = perp1
        else:
            turn = turn2
            used_perp = perp2

        if debug:
            print(
                f"    Стена {wall_dir:.1f}°: угол с киблой={angle_wall_qibla:.1f}°, "
                f"поворот от перп {used_perp:.1f}° = {turn:+.1f}°",
                file=sys.stderr,
            )

        if abs(turn) < min_turn_abs:
            min_turn_abs = abs(turn)
            best_wall = wall_dir
            best_turn = turn

    wall_name = direction_to_cardinal(best_wall)
    if debug:
        print(
            f"  Выбрана: {wall_name} стена ({best_wall:.1f}°), поворот: {best_turn:+.1f}°",
            file=sys.stderr,
        )
    return best_wall, best_turn, wall_name


def bearing_of_segment(p1: Sequence[float], p2: Sequence[float]) -> float:
    """Bearing отрезка в плоскости (x=восток, y=север)."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    ang = math.degrees(math.atan2(dx, -dy))
    return (ang + 360) % 360


def polygon_orientation_deg(poly_lonlat: Sequence[LonLat]) -> float:
    """
    Ориентация главной оси полигона по самой длинной стороне.
    Для прямоугольных зданий это надёжнее PCA.
    """
    if len(poly_lonlat) < 3:
        return 0.0

    best_len = 0.0
    best_bearing = 0.0
    n = len(poly_lonlat)
    for i in range(n):
        p1 = poly_lonlat[i]
        p2 = poly_lonlat[(i + 1) % n]
        seg_bearing = bearing_deg(p1[1], p1[0], p2[1], p2[0])
        length = haversine_m(p1[1], p1[0], p2[1], p2[0])
        if length > best_len:
            best_len = length
            best_bearing = seg_bearing
    return best_bearing
