"""
Модуль для работы с OpenStreetMap через Overpass API и Яндекс API.
"""

import requests
import sys
from datetime import datetime
from bearing.map import YANDEX_API_KEY

def log_time(msg):
    """Выводит сообщение с временной меткой"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {msg}", file=sys.stderr)


def get_address_from_coordinates(lat, lon):
    """
    Получает адрес по координатам через Яндекс.Геокодер API или Nominatim (OSM).
    
    Args:
        lat: Широта точки
        lon: Долгота точки
    
    Returns:
        Строка с адресом или None, если адрес не найден
    """
    # Сначала пробуем Яндекс API
    try:
        url = "https://geocode-maps.yandex.ru/1.x/"
        params = {
            "apikey": YANDEX_API_KEY,
            "geocode": f"{lon},{lat}",
            "format": "json",
            "results": 1
        }
        
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        # Проверяем, есть ли результаты
        features = data.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])
        if features:
            geo_obj = features[0].get("GeoObject", {})
            # Получаем полный адрес из компонентов
            meta_data = geo_obj.get("metaDataProperty", {}).get("GeocoderMetaData", {})
            address = meta_data.get("text", "")
            
            if address:
                log_time(f"Адрес получен (Яндекс): {address}")
                return address
    except Exception as e:
        log_time(f"Яндекс API недоступен для получения адреса: {e}")
    
    # Fallback: используем Nominatim (OSM)
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json",
            "addressdetails": 1
        }
        headers = {
            'User-Agent': 'Bearing-Qibla-App/1.0'
        }
        
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        # Формируем адрес из компонентов
        address_parts = []
        addr = data.get("address", {})
        
        # Добавляем компоненты адреса в порядке от конкретного к общему
        if addr.get("house_number"):
            address_parts.append(addr["house_number"])
        if addr.get("road"):
            address_parts.append(addr["road"])
        if addr.get("city") or addr.get("town") or addr.get("village"):
            city = addr.get("city") or addr.get("town") or addr.get("village")
            address_parts.append(city)
        if addr.get("state"):
            address_parts.append(addr["state"])
        if addr.get("country"):
            address_parts.append(addr["country"])
        
        if address_parts:
            address = ", ".join(address_parts)
            log_time(f"Адрес получен (Nominatim): {address}")
            return address
        
        # Если компонентов нет, используем display_name
        display_name = data.get("display_name")
        if display_name:
            log_time(f"Адрес получен (Nominatim): {display_name}")
            return display_name
        
    except Exception as e:
        log_time(f"Ошибка при получении адреса через Nominatim: {e}")
    
    return None


def yandex_building_polygon(lat, lon, radius_m=60):
    """
    Пытается получить информацию о здании через Яндекс.Геокодер API.
    Использует ключ Яндекс Tiles API для запроса.
    Если Яндекс API недоступен или не возвращает нужные данные, возвращает None.
    
    Args:
        lat: Широта точки
        lon: Долгота точки
        radius_m: Радиус поиска в метрах (не используется напрямую в Яндекс API)
    
    Returns:
        None (Яндекс API не предоставляет полигоны зданий напрямую)
        Функция всегда возвращает None, чтобы перейти к OSM fallback
    """
    try:
        # Яндекс.Геокодер API для получения информации об объекте
        # Используем ключ Яндекс Tiles API
        url = "https://geocode-maps.yandex.ru/1.x/"
        params = {
            "apikey": YANDEX_API_KEY,
            "geocode": f"{lon},{lat}",
            "format": "json",
            "kind": "house",  # Ищем здания
            "results": 1
        }
        
        log_time(f"Попытка получить информацию о здании через Яндекс API (ключ Tiles API)...")
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        # Проверяем, есть ли результаты
        features = data.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])
        if features:
            geo_obj = features[0].get("GeoObject", {})
            name = geo_obj.get("name", "неизвестно")
            log_time(f"Яндекс API вернул информацию об объекте: {name}")
            log_time("Полигоны зданий недоступны через публичный API, используем OSM")
            # Яндекс API не предоставляет полигоны зданий через публичный API
            # Поэтому возвращаем None и переходим к OSM
        else:
            log_time("Яндекс API не нашел объект")
        
        return None  # Всегда возвращаем None, чтобы использовать OSM для полигонов
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            log_time("Яндекс API: закончились бесплатные токены или доступ запрещен")
        else:
            log_time(f"Яндекс API: HTTP ошибка {e.response.status_code}")
        return None
    except (requests.Timeout, requests.ConnectionError) as e:
        log_time(f"Яндекс API: ошибка соединения или таймаут")
        return None
    except Exception as e:
        log_time(f"Яндекс API: неожиданная ошибка: {e}")
        return None


def _point_in_polygon(lat, lon, poly):
    """
    Проверяет, находится ли точка внутри полигона (алгоритм ray casting).
    
    Args:
        lat: Широта точки
        lon: Долгота точки
        poly: Список кортежей (lon, lat) точек полигона
    
    Returns:
        True, если точка внутри полигона, False иначе
    """
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


def _distance_to_polygon_center(lat, lon, poly):
    """
    Вычисляет расстояние от точки до центра полигона здания.
    
    Args:
        lat: Широта точки
        lon: Долгота точки
        poly: Список кортежей (lon, lat) точек полигона
    
    Returns:
        Расстояние в метрах (приблизительно)
    """
    import math
    
    # Вычисляем центр полигона
    center_lon = sum(p[0] for p in poly) / len(poly)
    center_lat = sum(p[1] for p in poly) / len(poly)
    
    # Вычисляем расстояние от точки до центра
    dlat = math.radians(center_lat - lat)
    dlon = math.radians(center_lon - lon)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat)) * math.cos(math.radians(center_lat)) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    dist = 6371000 * c  # Радиус Земли в метрах
    
    return dist


def overpass_building_polygon(lat, lon, radius_m=60):
    """
    Получает полигон ближайшего здания вокруг точки через Overpass API.
    Выбирает здание, которое находится ближе всего к точке пользователя.
    
    Args:
        lat: Широта точки
        lon: Долгота точки
        radius_m: Радиус поиска в метрах (по умолчанию 60)
    
    Returns:
        Список кортежей (lon, lat) точек полигона или None, если здание не найдено
    
    Raises:
        requests.RequestException: При ошибке запроса к Overpass API
    """
    query = f"""
    [out:json][timeout:25];
    (
      way(around:{radius_m},{lat},{lon})["building"];
      relation(around:{radius_m},{lat},{lon})["building"];
    );
    out geom;
    """
    try:
        # Пробуем несколько серверов Overpass API для надежности
        servers = [
            "https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.openstreetmap.ru/api/interpreter"
        ]
        
        for server_url in servers:
            try:
                log_time(f"Поиск здания в OSM (радиус {radius_m}м, сервер: {server_url})...")
                r = requests.post(server_url, data=query.encode("utf-8"), timeout=15)
                r.raise_for_status()
                data = r.json()
                
                # Собираем все здания с геометрией
                buildings = []
                for el in data.get("elements", []):
                    geom = el.get("geometry")
                    if geom and len(geom) >= 4:
                        poly = [(p["lon"], p["lat"]) for p in geom]
                        buildings.append(poly)
                
                if buildings:
                    # Сначала ищем здание, внутри которого находится точка пользователя
                    inside_buildings = []
                    for poly in buildings:
                        if _point_in_polygon(lat, lon, poly):
                            inside_buildings.append(poly)
                    
                    if inside_buildings:
                        # Если точка внутри нескольких зданий, выбираем самое маленькое (ближайший центр)
                        best_poly = None
                        min_dist = float('inf')
                        for poly in inside_buildings:
                            dist = _distance_to_polygon_center(lat, lon, poly)
                            if dist < min_dist:
                                min_dist = dist
                                best_poly = poly
                        log_time(f"Здание найдено (точка внутри)! Точек в полигоне: {len(best_poly)}, расстояние до центра: {min_dist:.1f}м")
                        return best_poly
                    
                    # Если точка не внутри зданий, выбираем здание с ближайшим центром
                    best_poly = None
                    min_dist = float('inf')
                    for poly in buildings:
                        dist = _distance_to_polygon_center(lat, lon, poly)
                        if dist < min_dist:
                            min_dist = dist
                            best_poly = poly
                    
                    if best_poly:
                        log_time(f"Здание найдено! Точек в полигоне: {len(best_poly)}, расстояние до центра: {min_dist:.1f}м")
                        return best_poly
                
                # Если элементов нет, пробуем следующий сервер
                break
            except (requests.Timeout, requests.ConnectionError) as e:
                log_time(f"Таймаут/ошибка соединения с {server_url}, пробуем следующий...")
                continue
            except requests.RequestException as e:
                log_time(f"Ошибка запроса к {server_url}, пробуем следующий...")
                continue
        
        log_time("Здание не найдено в OSM")
        return None
    except (KeyError, ValueError) as e:
        print(f"Ошибка при обработке данных OSM: {e}", file=sys.stderr)
        return None


def get_building_polygon(lat, lon, radius_m=60):
    """
    Получает полигон ближайшего здания вокруг точки через OSM.
    Всегда использует OSM для получения полигонов зданий.
    
    Args:
        lat: Широта точки
        lon: Долгота точки
        radius_m: Радиус поиска в метрах (по умолчанию 60)
    
    Returns:
        Список кортежей (lon, lat) точек полигона или None, если здание не найдено
    """
    # Всегда используем OSM для получения полигонов зданий
    # Яндекс API не предоставляет полигоны зданий через публичный API
    return overpass_building_polygon(lat, lon, radius_m=radius_m)

