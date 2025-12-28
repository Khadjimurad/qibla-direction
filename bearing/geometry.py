"""
Модуль для геометрических вычислений: bearing, нормализация углов, ориентация полигонов.
"""

import math
import numpy as np

# Координаты Каабы (Мекка, Саудовская Аравия)
# Источник: Google Earth (проверено пользователем)
# Координаты: 21.4225390° N, 39.8261964° E
KAABA_LAT = 21.4225390
KAABA_LON = 39.8261964


def bearing_deg_vincenty(lat1, lon1, lat2, lon2):
    """
    Вычисляет азимут (bearing) по формуле Vincenty, учитывающей эллипсоид Земли.
    Более точная формула для больших расстояний.
    
    Args:
        lat1: Широта начальной точки в градусах
        lon1: Долгота начальной точки в градусах
        lat2: Широта конечной точки в градусах
        lon2: Долгота конечной точки в градусах
    
    Returns:
        Азимут в градусах (0-360), где 0 = север, 90 = восток
    """
    # Параметры эллипсоида WGS84
    a = 6378137.0  # Большая полуось (метры)
    f = 1 / 298.257223563  # Сжатие
    b = (1 - f) * a  # Малая полуось
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    L = math.radians(lon2 - lon1)
    
    U1 = math.atan((1 - f) * math.tan(phi1))
    U2 = math.atan((1 - f) * math.tan(phi2))
    sin_U1 = math.sin(U1)
    cos_U1 = math.cos(U1)
    sin_U2 = math.sin(U2)
    cos_U2 = math.cos(U2)
    
    lambda_p = L
    lambda_val = L
    
    for _ in range(100):  # Итерации для точности
        sin_lambda = math.sin(lambda_val)
        cos_lambda = math.cos(lambda_val)
        sin_sigma = math.sqrt(
            (cos_U2 * sin_lambda) ** 2 +
            (cos_U1 * sin_U2 - sin_U1 * cos_U2 * cos_lambda) ** 2
        )
        if sin_sigma == 0:
            return 0.0  # Точки совпадают
        
        cos_sigma = sin_U1 * sin_U2 + cos_U1 * cos_U2 * cos_lambda
        sigma = math.atan2(sin_sigma, cos_sigma)
        sin_alpha = cos_U1 * cos_U2 * sin_lambda / sin_sigma
        cos2_alpha = 1 - sin_alpha ** 2
        
        if cos2_alpha == 0:
            cos_2sigma_m = 0  # Экваториальная линия
        else:
            cos_2sigma_m = cos_sigma - 2 * sin_U1 * sin_U2 / cos2_alpha
        
        C = f / 16 * cos2_alpha * (4 + f * (4 - 3 * cos2_alpha))
        lambda_p = lambda_val
        lambda_val = L + (1 - C) * f * sin_alpha * (
            sigma + C * sin_sigma * (
                cos_2sigma_m + C * cos_sigma * (-1 + 2 * cos_2sigma_m ** 2)
            )
        )
        
        if abs(lambda_val - lambda_p) < 1e-12:
            break
    
    u2 = cos2_alpha * (a ** 2 - b ** 2) / (b ** 2)
    A = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
    B = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
    delta_sigma = B * sin_sigma * (
        cos_2sigma_m + B / 4 * (
            cos_sigma * (-1 + 2 * cos_2sigma_m ** 2) -
            B / 6 * cos_2sigma_m * (-3 + 4 * sin_sigma ** 2) * (-3 + 4 * cos_2sigma_m ** 2)
        )
    )
    
    # Начальный азимут (bearing)
    alpha1 = math.atan2(
        cos_U2 * sin_lambda,
        cos_U1 * sin_U2 - sin_U1 * cos_U2 * cos_lambda
    )
    
    brng = math.degrees(alpha1)
    return (brng + 360) % 360


def bearing_deg_great_circle(lat1, lon1, lat2, lon2):
    """
    Вычисляет азимут (bearing) методом большого круга (Great Circle).
    Этот метод используется в Google Earth и других картографических системах.
    
    Args:
        lat1: Широта начальной точки в градусах
        lon1: Долгота начальной точки в градусах
        lat2: Широта конечной точки в градусах
        lon2: Долгота конечной точки в градусах
    
    Returns:
        Азимут в градусах (0-360), где 0 = север, 90 = восток
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    
    # Формула большого круга для начального азимута
    y = math.sin(dlam) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    
    brng = math.degrees(math.atan2(y, x))
    return (brng + 360) % 360


def bearing_deg(lat1, lon1, lat2=KAABA_LAT, lon2=KAABA_LON, method="great_circle"):
    """
    Вычисляет азимут (bearing) от точки (lat1, lon1) к точке (lat2, lon2).
    
    По умолчанию использует метод большого круга (Great Circle), который используется
    в Google Earth и других картографических системах.
    
    Примечание: Разница в несколько градусов с Google Earth может быть связана с:
    - Разными системами координат или проекциями
    - Разными методами измерения в Google Earth
    - Учетом магнитного склонения в Google Earth
    - Разными координатами Каабы в разных системах
    
    Args:
        lat1: Широта начальной точки в градусах
        lon1: Долгота начальной точки в градусах
        lat2: Широта конечной точки в градусах (по умолчанию Кааба)
        lon2: Долгота конечной точки в градусах (по умолчанию Кааба)
        method: Метод расчета:
            - "great_circle" (по умолчанию) - метод большого круга, как в Google Earth
            - "vincenty" - формула Vincenty, учитывает эллипсоид Земли
            - "spherical" - сферическая формула (быстрая, но менее точная)
    
    Returns:
        Азимут в градусах (0-360), где 0 = север, 90 = восток
    """
    if method == "vincenty":
        return bearing_deg_vincenty(lat1, lon1, lat2, lon2)
    elif method == "great_circle":
        return bearing_deg_great_circle(lat1, lon1, lat2, lon2)
    else:
        # Сферическая формула (быстрая, но менее точная для больших расстояний)
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dlam = math.radians(lon2 - lon1)

        y = math.sin(dlam) * math.cos(phi2)
        x = math.cos(phi1)*math.sin(phi2) - math.sin(phi1)*math.cos(phi2)*math.cos(dlam)
        brng = math.degrees(math.atan2(y, x))
        return (brng + 360) % 360


def normalize_angle180(a):
    """
    Нормализует угол в диапазон -180..+180 градусов.
    
    Args:
        a: Угол в градусах
    
    Returns:
        Нормализованный угол в диапазоне -180..+180
    """
    a = (a + 180) % 360 - 180
    return a


def left_right_text(angle_deg):
    """
    Форматирует угол поворота в понятный текст с направлением влево/вправо.
    
    Args:
        angle_deg: Угол поворота в градусах
    
    Returns:
        Строка вида "X.XX° вправо" или "X.XX° влево" или "почти ровно"
    """
    a = normalize_angle180(angle_deg)
    if abs(a) < 0.01:
        return f"{a:.2f}° (почти ровно)"
    return f"{abs(a):.2f}° {'вправо' if a > 0 else 'влево'}"


def smallest_turn(from_deg, to_deg):
    """
    Вычисляет минимальный угол поворота от одного направления к другому.
    
    Args:
        from_deg: Начальное направление в градусах
        to_deg: Конечное направление в градусах
    
    Returns:
        Угол поворота в диапазоне -180..+180 (отрицательный = влево, положительный = вправо)
    """
    return normalize_angle180(to_deg - from_deg)


def direction_to_cardinal(deg):
    """
    Преобразует направление в градусах в название стороны света.
    
    Args:
        deg: Направление в градусах (0=север, 90=восток)
    
    Returns:
        Строка с названием стороны света в родительном падеже (северной, восточной, южной, западной)
    """
    deg = deg % 360
    if 315 <= deg or deg < 45:
        return "северной"
    elif 45 <= deg < 135:
        return "восточной"
    elif 135 <= deg < 225:
        return "южной"
    else:  # 225 <= deg < 315
        return "западной"


def best_wall_turn(axis_deg, qibla_deg, debug=False):
    """
    Находит стену здания, у которой перпендикуляр ближе всего к кибле,
    и вычисляет угол поворота от этого перпендикуляра до киблы.
    
    Args:
        axis_deg: Ориентация главной оси здания в градусах
        qibla_deg: Направление на Каабу в градусах
        debug: Если True, выводит отладочную информацию
    
    Returns:
        Кортеж (wall_direction, turn_angle, wall_name):
        - wall_direction: Направление стены в градусах (одна из 4 стен)
        - turn_angle: Угол поворота от перпендикуляра к стене до киблы в градусах
        - wall_name: Название стены (северная, южная, восточная, западная)
    """
    import sys
    
    # Четыре возможных направления стен (ось и перпендикуляры)
    wall_candidates = [
        axis_deg,
        (axis_deg + 90) % 360,
        (axis_deg + 180) % 360,
        (axis_deg + 270) % 360
    ]
    
    # Выбираем стену по минимальному повороту от перпендикуляра
    # Это даст наиболее понятную инструкцию пользователю (минимальный угол поворота)
    best_wall = None
    best_turn = None
    min_turn_abs = float('inf')
    
    if debug:
        print(f"  Анализ стен для киблы {qibla_deg:.1f}°:", file=sys.stderr)
    
    for wall_dir in wall_candidates:
        # Угол между стеной и киблой (для отладки)
        angle_wall_qibla = abs(smallest_turn(wall_dir, qibla_deg))
        
        # Вычисляем перпендикуляры к стене
        perp1 = (wall_dir + 90) % 360
        perp2 = (wall_dir - 90) % 360
        
        # Вычисляем поворот от каждого перпендикуляра до киблы
        turn1 = smallest_turn(perp1, qibla_deg)
        turn2 = smallest_turn(perp2, qibla_deg)
        
        # Всегда используем поворот от перпендикуляра (выбираем ближайший)
        if abs(turn1) < abs(turn2):
            turn = turn1
            used_perp = perp1
        else:
            turn = turn2
            used_perp = perp2
        
        if debug:
            print(f"    Стена {wall_dir:.1f}°: угол с киблой={angle_wall_qibla:.1f}°, поворот от перп {used_perp:.1f}° = {turn:+.1f}°", file=sys.stderr)
        
        # Выбираем стену с минимальным абсолютным поворотом от перпендикуляра
        if abs(turn) < min_turn_abs:
            min_turn_abs = abs(turn)
            best_wall = wall_dir
            best_turn = turn
    
    wall_dir = best_wall
    wall_name = direction_to_cardinal(wall_dir)
    turn_angle = best_turn
    
    if debug:
        print(f"  Выбрана: {wall_name} стена ({wall_dir:.1f}°), поворот: {turn_angle:+.1f}°", file=sys.stderr)
    
    return wall_dir, turn_angle, wall_name


def bearing_of_segment(p1, p2):
    """
    Вычисляет bearing отрезка между двумя точками.
    
    Args:
        p1: Кортеж (x, y) или (lon, lat) первой точки
        p2: Кортеж (x, y) или (lon, lat) второй точки
    
    Returns:
        Bearing в градусах (0=север, 90=восток)
    """
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    # Для координат lon/lat: dx = восток, dy = север
    # atan2(dx, -dy) дает 0 для севера (dy>0, dx=0)
    ang = math.degrees(math.atan2(dx, -dy))
    return (ang + 360) % 360


def polygon_orientation_deg(poly_lonlat):
    """
    Вычисляет ориентацию главной оси полигона по самой длинной стороне.
    Для правильно ориентированных мечетей это более точный метод, чем PCA,
    так как PCA может давать неточные результаты из-за сложной формы полигона.
    
    Args:
        poly_lonlat: Список кортежей (lon, lat) точек полигона
    
    Returns:
        Угол главной оси в градусах (0=север, 90=восток)
    """
    if len(poly_lonlat) < 3:
        return 0.0
    
    best_len = 0
    best_bearing = 0
    
    # Проходим по всем сторонам полигона
    n = len(poly_lonlat)
    for i in range(n):
        p1 = poly_lonlat[i]
        p2 = poly_lonlat[(i + 1) % n]
        
        # Вычисляем bearing между двумя точками
        seg_bearing = bearing_deg(p1[1], p1[0], p2[1], p2[0])
        
        # Вычисляем длину сегмента (используя формулу гаверсинусов)
        lat1, lon1 = math.radians(p1[1]), math.radians(p1[0])
        lat2, lon2 = math.radians(p2[1]), math.radians(p2[0])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        R = 6371000  # радиус Земли в метрах
        length = R * c
        
        if length > best_len:
            best_len = length
            best_bearing = seg_bearing
    
    return best_bearing

