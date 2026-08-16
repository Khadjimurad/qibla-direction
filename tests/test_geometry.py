from __future__ import annotations

from bearing.cli import parse_coordinate
from bearing.geometry import (
    KAABA_LAT,
    KAABA_LON,
    best_wall_turn,
    bearing_deg,
    haversine_m,
    left_right_text,
    normalize_angle180,
    smallest_turn,
)


def test_great_circle_matches_spherical_alias() -> None:
    gc = bearing_deg(42.96914, 47.49389, method="great_circle")
    spherical = bearing_deg(42.96914, 47.49389, method="spherical")
    assert gc == spherical


def test_qibla_from_dagestan_is_south_west() -> None:
    bearing = bearing_deg(42.96914, 47.49389)
    assert 190 < bearing < 230


def test_qibla_from_moscow_is_south() -> None:
    bearing = bearing_deg(55.7558, 37.6173)
    assert 160 < bearing < 180


def test_vincenty_close_to_great_circle() -> None:
    gc = bearing_deg(42.96914, 47.49389, method="great_circle")
    vincenty = bearing_deg(42.96914, 47.49389, method="vincenty")
    assert abs(smallest_turn(gc, vincenty)) < 2.0


def test_kaaba_to_itself_is_zero_or_defined() -> None:
    # Совпадающие точки: Vincenty возвращает 0
    assert bearing_deg(KAABA_LAT, KAABA_LON, method="vincenty") == 0.0


def test_normalize_and_turn() -> None:
    assert normalize_angle180(270) == -90
    assert smallest_turn(10, 350) == -20
    assert left_right_text(12.34).endswith("вправо")
    assert left_right_text(-3).endswith("влево")


def test_best_wall_turn_prefers_small_adjustment() -> None:
    wall, turn, name = best_wall_turn(0, 95)
    assert name in {"северной", "восточной", "южной", "западной"}
    assert abs(turn) <= 45
    assert 0 <= wall < 360


def test_haversine_zero() -> None:
    assert haversine_m(42.0, 47.0, 42.0, 47.0) == 0.0


def test_parse_coordinate_comma_and_trailing() -> None:
    assert parse_coordinate("42,96914") == 42.96914
    assert parse_coordinate("42.539388,") == 42.539388
    assert parse_coordinate(" 47.49389 ") == 47.49389
