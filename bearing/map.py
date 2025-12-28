"""
Модуль для работы с картами: преобразование координат, загрузка тайлов OSM.
"""

import math
import io
import time
import requests
from PIL import Image

# API ключ для Яндекс.Карт Tiles API
YANDEX_API_KEY = "242746bf-f9aa-4da3-b5fd-e9c5d9b19234"


def latlon_to_world_px(lat, lon, zoom):
    """
    Преобразует координаты lat/lon в пиксели WebMercator для заданного зума.
    
    Args:
        lat: Широта в градусах
        lon: Долгота в градусах
        zoom: Уровень зума
    
    Returns:
        Кортеж (x, y) координат в пикселях WebMercator
    """
    siny = math.sin(math.radians(lat))
    siny = min(max(siny, -0.9999), 0.9999)
    x = 256 * (0.5 + lon / 360) * (2 ** zoom)
    y = 256 * (0.5 - math.log((1 + siny) / (1 - siny)) / (4 * math.pi)) * (2 ** zoom)
    return x, y


def fetch_tile(z, x, y, tile_source="cartodb"):
    """
    Загружает тайл карты по координатам тайла.
    Поддерживает несколько источников: CartoDB (по умолчанию), Яндекс.Карты.
    
    Args:
        z: Уровень зума
        x: X координата тайла
        y: Y координата тайла
        tile_source: Источник тайлов ("cartodb" или "yandex")
    
    Returns:
        PIL Image объект тайла
    
    Raises:
        requests.RequestException: При ошибке загрузки тайла
    """
    headers = {
        'User-Agent': 'Bearing-Qibla-App/1.0 (Python/requests)'
    }
    
    # Небольшая задержка перед запросом для соблюдения политики использования тайлов
    # Уменьшена для ускорения загрузки
    if tile_source == "yandex":
        time.sleep(0.02)  # Яндекс.Карты быстрее
    else:
        time.sleep(0.01)  # CartoDB еще быстрее
    
    if tile_source == "yandex":
        # Яндекс.Карты Tiles API
        # Согласно документации: https://yandex.ru/maps-api/docs/tiles-api/index.html
        # Формат запроса: https://core-renderer-tiles.maps.yandex.net/tiles?l=map&x={x}&y={y}&z={z}&apikey={key}
        # Параметр l может быть: map (обычная карта со зданиями), skl (схема), sat (спутник)
        # Пробуем сначала без scale, так как он может вызывать проблемы для некоторых регионов
        url = f"https://core-renderer-tiles.maps.yandex.net/tiles?l=map&x={x}&y={y}&z={z}&apikey={YANDEX_API_KEY}"
    else:
        # CartoDB (по умолчанию) - более лоялен к использованию
        # Можно использовать разные стили: light_all, dark_all, rastertiles/voyager
        url = f"https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"
    
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        
        # Яндекс API возвращает изображение в режиме P (палитра), нужно конвертировать в RGB
        tile_img = Image.open(io.BytesIO(r.content))
        if tile_img.mode != "RGB":
            tile_img = tile_img.convert("RGB")
        
        # Проверяем качество тайла от Яндекс API
        if tile_source == "yandex":
            import numpy as np
            arr = np.array(tile_img)
            avg_color = arr.mean(axis=(0, 1))
            # Если средний цвет голубой (синий и зеленый доминируют, красный низкий), это ошибка
            if avg_color[2] > 200 and avg_color[1] > 200 and avg_color[0] < 200:
                # Это голубой фон ошибки - используем fallback
                raise ValueError("Яндекс API вернул голубой фон (ошибка)")
            # Если тайл слишком светлый (почти белый), возможно, данных нет для этого региона
            # Проверяем стандартное отклонение - если оно очень низкое, тайл пустой
            std_dev = arr.std()
            if std_dev < 5:  # Очень низкое стандартное отклонение = пустой тайл
                raise ValueError(f"Яндекс API вернул пустой тайл (std={std_dev:.1f})")
        
        return tile_img
    except (requests.RequestException, ValueError) as e:
        # Для Яндекс API не делаем fallback здесь - пусть исключение пробросится в static_map
        # чтобы можно было перезагрузить все тайлы через CartoDB
        if tile_source == "yandex":
            raise
        # Для других источников пробуем повторить запрос
        raise RuntimeError(f"Ошибка при загрузке тайла {z}/{x}/{y}: {e}") from e


def static_map(center_lat, center_lon, zoom=18, size_px=800, tile_source="cartodb"):
    """
    Создает статическую карту из тайлов вокруг заданной точки.
    
    Args:
        center_lat: Широта центра карты
        center_lon: Долгота центра карты
        zoom: Уровень зума (по умолчанию 18)
        size_px: Размер карты в пикселях (по умолчанию 800)
        tile_source: Источник тайлов ("cartodb" или "yandex")
    
    Returns:
        Кортеж (Image, (left, top), zoom):
        - Image: PIL Image объект карты
        - (left, top): Координаты левого верхнего угла в world pixels
        - zoom: Уровень зума
    """
    cx, cy = latlon_to_world_px(center_lat, center_lon, zoom)
    half = size_px / 2

    # координаты окна в world px
    left = cx - half
    top = cy - half

    # тайлы
    tile_size = 256
    x0 = int(left // tile_size)
    y0 = int(top // tile_size)
    x1 = int((cx + half) // tile_size)
    y1 = int((cy + half) // tile_size)

    import sys
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from datetime import datetime
    
    def log_time(msg):
        """Выводит сообщение с временной меткой"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] {msg}", file=sys.stderr)
    
    total_tiles = (x1 - x0 + 1) * (y1 - y0 + 1)
    loaded_tiles = 0
    
    img = Image.new("RGB", (size_px, size_px))
    
    # Загружаем тайлы параллельно для ускорения
    # Отслеживаем, были ли ошибки с Яндекс API
    yandex_failed_tiles = []
    
    def load_tile(tx, ty):
        try:
            tile = fetch_tile(zoom, tx, ty, tile_source=tile_source)
            px = int(tx * tile_size - left)
            py = int(ty * tile_size - top)
            return (tx, ty, tile, px, py)
        except Exception as e:
            # Если Яндекс API не работает, запоминаем координаты тайла
            if tile_source == "yandex":
                yandex_failed_tiles.append((tx, ty))
            return None
    
    def load_tile_cartodb(tx, ty):
        """Загружает тайл через CartoDB"""
        try:
            url = f"https://a.basemaps.cartocdn.com/light_all/{zoom}/{tx}/{ty}.png"
            headers = {'User-Agent': 'Bearing-Qibla-App/1.0 (Python/requests)'}
            r = requests.get(url, headers=headers, timeout=20)
            r.raise_for_status()
            tile = Image.open(io.BytesIO(r.content)).convert("RGB")
            px = int(tx * tile_size - left)
            py = int(ty * tile_size - top)
            return (tx, ty, tile, px, py)
        except Exception:
            return None
    
    # Используем ThreadPoolExecutor для параллельной загрузки
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for tx in range(x0, x1 + 1):
            for ty in range(y0, y1 + 1):
                future = executor.submit(load_tile, tx, ty)
                futures[future] = (tx, ty)
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                tx, ty, tile, px, py = result
                img.paste(tile, (px, py))
                loaded_tiles += 1
                if loaded_tiles % 4 == 0 or loaded_tiles == total_tiles:  # Показываем прогресс каждые 4 тайла
                    log_time(f"Загрузка карты: {loaded_tiles}/{total_tiles} тайлов")
    
    # Если для Яндекс API были проблемы с тайлами, перезагружаем все через CartoDB
    if tile_source == "yandex" and yandex_failed_tiles:
        log_time(f"Обнаружены проблемы с {len(yandex_failed_tiles)} тайлами от Яндекс API, перезагружаем все через CartoDB...")
        # Перезагружаем все тайлы через CartoDB
        img = Image.new("RGB", (size_px, size_px))
        loaded_tiles = 0
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {}
            for tx in range(x0, x1 + 1):
                for ty in range(y0, y1 + 1):
                    future = executor.submit(load_tile_cartodb, tx, ty)
                    futures[future] = (tx, ty)
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    tx, ty, tile, px, py = result
                    img.paste(tile, (px, py))
                    loaded_tiles += 1
                    if loaded_tiles % 4 == 0 or loaded_tiles == total_tiles:
                        log_time(f"Загрузка карты (CartoDB): {loaded_tiles}/{total_tiles} тайлов")
    
    log_time(f"Загрузка карты завершена: {loaded_tiles}/{total_tiles} тайлов")
    return img, (left, top), zoom


def lonlat_to_img_px(lon, lat, top_left_world, zoom):
    """
    Преобразует координаты lon/lat в пиксели изображения карты.
    
    Args:
        lon: Долгота в градусах
        lat: Широта в градусах
        top_left_world: Кортеж (left, top) координат левого верхнего угла карты в world pixels
        zoom: Уровень зума
    
    Returns:
        Кортеж (x, y) координат в пикселях изображения
    """
    wx, wy = latlon_to_world_px(lat, lon, zoom)
    left, top = top_left_world
    return (wx - left, wy - top)

