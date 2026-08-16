"""Карты: Web Mercator, загрузка тайлов Яндекс / CARTO / OSM."""

from __future__ import annotations

import io
import math
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Literal, Never

import requests
from PIL import Image

from bearing.config import YANDEX_API_KEY, http_get, log_time

TileSource = Literal["yandex", "cartodb", "osm"]

TILE_SIZE = 256


def latlon_to_world_px(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    """lat/lon → пиксели сферического Web Mercator для зума."""
    siny = min(max(math.sin(math.radians(lat)), -0.9999), 0.9999)
    scale = 256 * (2 ** zoom)
    x = scale * (0.5 + lon / 360)
    y = scale * (0.5 - math.log((1 + siny) / (1 - siny)) / (4 * math.pi))
    return x, y


def _yandex_official_url(z: int, x: int, y: int) -> str:
    return (
        "https://tiles.api-maps.yandex.ru/v1/tiles/"
        f"?apikey={YANDEX_API_KEY}&lang=ru_RU&x={x}&y={y}&z={z}"
        "&l=map&projection=web_mercator"
    )


def _yandex_legacy_url(z: int, x: int, y: int) -> str:
    return (
        "https://core-renderer-tiles.maps.yandex.net/tiles"
        f"?l=map&x={x}&y={y}&z={z}&apikey={YANDEX_API_KEY}"
    )


def _carto_url(z: int, x: int, y: int) -> str:
    subdomain = ("a", "b", "c", "d")[(x + y) % 4]
    return f"https://{subdomain}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"


def _osm_url(z: int, x: int, y: int) -> str:
    return f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"


def _tile_is_invalid(tile_img: Image.Image) -> str | None:
    """Почти однотонный тайл — пустой ответ или экран ошибки API."""
    extrema = tile_img.getextrema()
    if not extrema:
        return "нет данных"
    if all((mx - mn) < 6 for mn, mx in extrema[:3]):
        return "пустой или ошибочный тайл"
    return None


def _download_tile_image(url: str) -> Image.Image:
    response = http_get(url, timeout=20)
    response.raise_for_status()
    tile_img = Image.open(io.BytesIO(response.content))
    if tile_img.mode != "RGB":
        tile_img = tile_img.convert("RGB")
    return tile_img


def fetch_tile(z: int, x: int, y: int, tile_source: TileSource = "cartodb") -> Image.Image:
    """
    Один тайл карты.

    Для yandex: официальный Tiles API (web_mercator), затем устаревший renderer.
    Fallback на другой провайдер делается в static_map, чтобы вся карта была одного стиля.
    """
    if tile_source == "yandex":
        urls = [_yandex_official_url(z, x, y), _yandex_legacy_url(z, x, y)]
        last_error: Exception | None = None
        for url in urls:
            try:
                tile_img = _download_tile_image(url)
                reason = _tile_is_invalid(tile_img)
                if reason:
                    last_error = ValueError(reason)
                    continue
                return tile_img
            except (requests.RequestException, ValueError, OSError) as exc:
                last_error = exc
        raise RuntimeError(f"Яндекс тайл {z}/{x}/{y}: {last_error}") from last_error

    if tile_source == "osm":
        url = _osm_url(z, x, y)
    elif tile_source == "cartodb":
        url = _carto_url(z, x, y)
    else:
        unreachable: Never = tile_source
        raise ValueError(f"Неизвестный источник тайлов: {unreachable}")

    try:
        return _download_tile_image(url)
    except (requests.RequestException, OSError) as exc:
        raise RuntimeError(f"Ошибка загрузки тайла {z}/{x}/{y}: {exc}") from exc


def _paste_tiles(
    size_px: int,
    left: float,
    top: float,
    x0: int,
    x1: int,
    y0: int,
    y1: int,
    loader,
    label: str,
    max_workers: int,
) -> tuple[Image.Image, int, int]:
    img = Image.new("RGB", (size_px, size_px))
    total = (x1 - x0 + 1) * (y1 - y0 + 1)
    loaded = 0
    failed = 0
    lock = threading.Lock()

    def job(tx: int, ty: int):
        tile = loader(tx, ty)
        if tile is None:
            return None
        px = int(tx * TILE_SIZE - left)
        py = int(ty * TILE_SIZE - top)
        return tx, ty, tile, px, py

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(job, tx, ty): (tx, ty)
            for tx in range(x0, x1 + 1)
            for ty in range(y0, y1 + 1)
        }
        for future in as_completed(futures):
            result = future.result()
            if result is None:
                with lock:
                    failed += 1
                continue
            _, _, tile, px, py = result
            img.paste(tile, (px, py))
            with lock:
                loaded += 1
                if loaded % 4 == 0 or loaded + failed == total:
                    log_time(f"{label}: {loaded}/{total} тайлов")

    return img, loaded, failed


def static_map(
    center_lat: float,
    center_lon: float,
    zoom: int = 18,
    size_px: int = 800,
    tile_source: TileSource = "cartodb",
) -> tuple[Image.Image, tuple[float, float], int, TileSource]:
    """
    Статическая карта из тайлов вокруг точки.

    Если часть тайлов выбранного источника не загрузилась, вся карта
    пересобирается из запасного провайдера (единый стиль).
    """
    cx, cy = latlon_to_world_px(center_lat, center_lon, zoom)
    half = size_px / 2
    left = cx - half
    top = cy - half

    x0 = int(left // TILE_SIZE)
    y0 = int(top // TILE_SIZE)
    x1 = int((cx + half) // TILE_SIZE)
    y1 = int((cy + half) // TILE_SIZE)

    def make_loader(source: TileSource):
        def loader(tx: int, ty: int) -> Image.Image | None:
            try:
                return fetch_tile(zoom, tx, ty, tile_source=source)
            except Exception:
                return None
        return loader

    workers = 2 if tile_source == "osm" else 4
    img, loaded, failed = _paste_tiles(
        size_px, left, top, x0, x1, y0, y1,
        make_loader(tile_source),
        f"Загрузка карты ({tile_source})",
        workers,
    )

    fallback_order: tuple[TileSource, ...]
    if tile_source == "yandex":
        fallback_order = ("cartodb", "osm")
    elif tile_source == "cartodb":
        fallback_order = ("osm",)
    elif tile_source == "osm":
        fallback_order = ("cartodb",)
    else:
        unreachable: Never = tile_source
        raise ValueError(f"Неизвестный источник тайлов: {unreachable}")

    used_source: TileSource = tile_source
    if failed:
        for fallback in fallback_order:
            log_time(
                f"Не загрузилось {failed} тайлов ({used_source}), "
                f"пересобираем карту через {fallback}..."
            )
            fb_workers = 2 if fallback == "osm" else 4
            img, loaded, failed = _paste_tiles(
                size_px, left, top, x0, x1, y0, y1,
                make_loader(fallback),
                f"Загрузка карты ({fallback})",
                fb_workers,
            )
            used_source = fallback
            if not failed:
                break

    total = (x1 - x0 + 1) * (y1 - y0 + 1)
    log_time(f"Загрузка карты завершена: {loaded}/{total} тайлов ({used_source})")
    return img, (left, top), zoom, used_source


def lonlat_to_img_px(
    lon: float,
    lat: float,
    top_left_world: tuple[float, float],
    zoom: int,
) -> tuple[float, float]:
    """lon/lat → пиксели готового изображения карты."""
    wx, wy = latlon_to_world_px(lat, lon, zoom)
    left, top = top_left_world
    return wx - left, wy - top
