"""OpenStreetMap (Overpass) и обратное геокодирование."""

from __future__ import annotations

import requests

from bearing.config import OVERPASS_SERVERS, YANDEX_API_KEY, http_get, http_post, log_time
from bearing.geometry import LonLat, haversine_m


def get_address_from_coordinates(lat: float, lon: float) -> str | None:
    """Адрес точки: Яндекс.Геокодер, затем Nominatim."""
    address = _yandex_reverse_geocode(lat, lon)
    if address:
        return address
    return _nominatim_reverse_geocode(lat, lon)


def _parse_yandex_geocoder(data: dict) -> str | None:
    features = (
        data.get("response", {})
        .get("GeoObjectCollection", {})
        .get("featureMember", [])
    )
    if not features:
        return None
    meta = (
        features[0]
        .get("GeoObject", {})
        .get("metaDataProperty", {})
        .get("GeocoderMetaData", {})
    )
    address = meta.get("text", "")
    return address or None


def _yandex_reverse_geocode(lat: float, lon: float) -> str | None:
    """
    Яндекс.Геокодер: сначала HTTP API v1 (lat,lon), затем классический 1.x (lon,lat).
    """
    attempts = (
        ("https://geocode-maps.yandex.ru/v1/", f"{lat},{lon}"),
        ("https://geocode-maps.yandex.ru/1.x/", f"{lon},{lat}"),
    )
    for url, geocode in attempts:
        try:
            response = http_get(
                url,
                params={
                    "apikey": YANDEX_API_KEY,
                    "geocode": geocode,
                    "format": "json",
                    "lang": "ru_RU",
                    "results": 1,
                },
                timeout=10,
            )
            response.raise_for_status()
            address = _parse_yandex_geocoder(response.json())
            if address:
                log_time(f"Адрес получен (Яндекс): {address}")
                return address
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            log_time(f"Яндекс.Геокодер ({url}): HTTP {status}")
            if status in (401, 403):
                break
        except (requests.RequestException, ValueError, KeyError) as exc:
            log_time(f"Яндекс.Геокодер ({url}): {exc}")
    return None


def _nominatim_reverse_geocode(lat: float, lon: float) -> str | None:
    try:
        response = http_get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                "lat": lat,
                "lon": lon,
                "format": "json",
                "addressdetails": 1,
                "accept-language": "ru",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        addr = data.get("address", {})
        parts: list[str] = []
        if addr.get("house_number"):
            parts.append(addr["house_number"])
        if addr.get("road"):
            parts.append(addr["road"])
        city = addr.get("city") or addr.get("town") or addr.get("village")
        if city:
            parts.append(city)
        if addr.get("state"):
            parts.append(addr["state"])
        if addr.get("country"):
            parts.append(addr["country"])
        address = ", ".join(parts) if parts else data.get("display_name")
        if address:
            log_time(f"Адрес получен (Nominatim): {address}")
            return address
    except (requests.RequestException, ValueError, KeyError) as exc:
        log_time(f"Ошибка Nominatim: {exc}")
    return None


def _point_in_polygon(lat: float, lon: float, poly: list[LonLat]) -> bool:
    """Ray casting: точка внутри полигона (x=lon, y=lat)."""
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _distance_to_polygon_center(lat: float, lon: float, poly: list[LonLat]) -> float:
    center_lon = sum(p[0] for p in poly) / len(poly)
    center_lat = sum(p[1] for p in poly) / len(poly)
    return haversine_m(lat, lon, center_lat, center_lon)


def _pick_building(lat: float, lon: float, buildings: list[list[LonLat]]) -> list[LonLat] | None:
    inside = [poly for poly in buildings if _point_in_polygon(lat, lon, poly)]
    candidates = inside or buildings
    best_poly: list[LonLat] | None = None
    min_dist = float("inf")
    for poly in candidates:
        dist = _distance_to_polygon_center(lat, lon, poly)
        if dist < min_dist:
            min_dist = dist
            best_poly = poly
    if best_poly is not None:
        where = "точка внутри" if inside else "ближайший центр"
        log_time(
            f"Здание найдено ({where}). Точек: {len(best_poly)}, "
            f"до центра: {min_dist:.1f} м"
        )
    return best_poly


def overpass_building_polygon(lat: float, lon: float, radius_m: int = 60) -> list[LonLat] | None:
    """Полигон ближайшего здания вокруг точки через Overpass API."""
    query = f"""
    [out:json][timeout:25];
    (
      way(around:{radius_m},{lat},{lon})["building"];
      relation(around:{radius_m},{lat},{lon})["building"];
    );
    out geom;
    """
    last_error: Exception | None = None
    for server_url in OVERPASS_SERVERS:
        try:
            log_time(f"Поиск здания в OSM (радиус {radius_m} м, {server_url})...")
            response = http_post(server_url, data=query.encode("utf-8"), timeout=25)
            response.raise_for_status()
            data = response.json()
            buildings: list[list[LonLat]] = []
            for element in data.get("elements", []):
                geom = element.get("geometry")
                if geom and len(geom) >= 4:
                    buildings.append([(p["lon"], p["lat"]) for p in geom])
            if buildings:
                return _pick_building(lat, lon, buildings)
            log_time("На этом сервере зданий нет, пробуем следующий...")
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
            log_time(f"Таймаут/сеть {server_url}, следующий сервер...")
        except (requests.RequestException, ValueError, KeyError) as exc:
            last_error = exc
            log_time(f"Ошибка {server_url}: {exc}")

    if last_error:
        log_time(f"Здание не найдено в OSM ({last_error})")
    else:
        log_time("Здание не найдено в OSM")
    return None


def get_building_polygon(lat: float, lon: float, radius_m: int = 60) -> list[LonLat] | None:
    """Полигон здания: Overpass/OSM (публичный API Яндекса полигоны не отдаёт)."""
    return overpass_building_polygon(lat, lon, radius_m=radius_m)
