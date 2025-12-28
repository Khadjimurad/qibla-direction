"""
Модуль для визуализации: рисование стрелок, создание изображений с направлением на Каабу.
"""

import math
from PIL import ImageDraw, ImageFont

from bearing.geometry import (
    bearing_deg, normalize_angle180, polygon_orientation_deg,
    left_right_text, smallest_turn, direction_to_cardinal, KAABA_LAT, KAABA_LON
)
from bearing.osm import get_building_polygon
from bearing.map import static_map, lonlat_to_img_px


def draw_arrow(draw, x, y, bearing, length=260, color=(255, 0, 0), width=6):
    """
    Рисует стрелку на изображении, указывающую направление.
    
    Args:
        draw: PIL ImageDraw объект
        x: X координата начала стрелки
        y: Y координата начала стрелки
        bearing: Направление в градусах (0=север, 90=восток)
        length: Длина стрелки в пикселях (по умолчанию 260)
        color: Цвет стрелки (по умолчанию красный)
        width: Толщина линии (по умолчанию 6)
    """
    # bearing: 0 север, 90 восток
    ang = math.radians(bearing)
    dx = math.sin(ang) * length
    dy = -math.cos(ang) * length
    x2, y2 = x + dx, y + dy
    draw.line((x, y, x2, y2), width=width, fill=color)

    # наконечник
    head = 22
    left = math.radians((bearing - 150) % 360)
    right = math.radians((bearing + 150) % 360)
    lx, ly = x2 + math.sin(left) * head, y2 - math.cos(left) * head
    rx, ry = x2 + math.sin(right) * head, y2 - math.cos(right) * head
    draw.polygon([(x2, y2), (lx, ly), (rx, ry)], fill=color)


def draw_north_arrow(draw, x, y, size=40):
    """
    Рисует стрелку Севера.
    
    Args:
        draw: PIL ImageDraw объект
        x: X координата центра стрелки
        y: Y координата центра стрелки
        size: Размер стрелки в пикселях
    """
    # Стрелка на север (bearing = 0)
    draw_arrow(draw, x, y, 0, length=size, color=(0, 100, 0), width=4)
    # Подпись "N"
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "N", font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    # Текст немного выше стрелки
    draw.text((x - text_width // 2, y - size - text_height - 5), "N", fill=(0, 100, 0), font=font)


def draw_turn_arc(draw, cx, cy, from_bearing, to_bearing, radius=120, color=(255, 165, 0)):
    """
    Рисует дугу поворота от одного направления к другому.
    
    Args:
        draw: PIL ImageDraw объект
        cx: X координата центра
        cy: Y координата центра
        from_bearing: Начальное направление в градусах
        to_bearing: Конечное направление в градусах
        radius: Радиус дуги в пикселях
        color: Цвет дуги
    """
    # Вычисляем угол поворота
    turn = normalize_angle180(to_bearing - from_bearing)
    
    if abs(turn) < 5:  # Слишком маленький поворот, не рисуем
        return
    
    # Конвертируем bearing в углы для PIL (PIL: 0 = 3 часа, против часовой)
    # bearing: 0 = север (вверх), 90 = восток (вправо)
    # PIL: 0 = вправо, 90 = вверх
    start_angle_deg = -from_bearing + 90
    end_angle_deg = -to_bearing + 90
    
    # Рисуем дугу сегментами
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


def build_qibla_image(lat, lon, out_path=None, zoom=19, size_px=900, radius_m=150, tile_source="yandex"):
    """
    Создает изображение карты с визуализацией направления на Каабу и ориентации здания.
    
    Args:
        lat: Широта точки
        lon: Долгота точки
        out_path: Путь для сохранения изображения (по умолчанию "qibla.png")
    zoom: Уровень зума карты (по умолчанию 19)
    size_px: Размер изображения в пикселях (по умолчанию 900)
    radius_m: Радиус поиска здания в метрах (по умолчанию 150)
    
    Returns:
        Кортеж (qibla, bldg_axis, wall_turn, out_path):
        - qibla: Направление на Каабу в градусах
        - bldg_axis: Ориентация оси здания в градусах
        - wall_turn: Угол поворота от ближайшей стены до киблы в градусах
        - out_path: Путь к сохраненному файлу
    
    Raises:
        RuntimeError: Если не удалось найти здание в OSM (только если radius_m слишком мал)
    """
    import sys
    from datetime import datetime
    
    def log_time(msg):
        """Выводит сообщение с временной меткой"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] {msg}", file=sys.stderr)
    
    log_time(f"Начало обработки координат: {lat:.5f}, {lon:.5f}")
    
    # Вычисляем bearing всеми тремя методами для сравнения
    qibla_spherical = bearing_deg(lat, lon, method="spherical")
    qibla_vincenty = bearing_deg(lat, lon, method="vincenty")
    qibla_great_circle = bearing_deg(lat, lon, method="great_circle")
    
    # Используем метод большого круга по умолчанию
    qibla = qibla_great_circle
    
    log_time(f"Направление на Каабу: {qibla:.2f}° (spherical: {qibla_spherical:.2f}°, vincenty: {qibla_vincenty:.2f}°, great_circle: {qibla_great_circle:.2f}°)")

    # Получаем адрес для имени файла
    from bearing.osm import get_address_from_coordinates
    address = get_address_from_coordinates(lat, lon)
    
    # Генерируем имя файла на основе адреса или координат
    if out_path is None:
        if address:
            # Очищаем адрес от недопустимых символов для имени файла
            import re
            safe_address = re.sub(r'[<>:"/\\|?*]', '_', address)
            safe_address = safe_address.replace(',', '_').replace(' ', '_')
            # Убираем двойные подчеркивания
            safe_address = re.sub(r'_+', '_', safe_address).strip('_')
            # Ограничиваем длину имени файла
            if len(safe_address) > 100:
                safe_address = safe_address[:100]
            out_path = f"qibla_{safe_address}.png"
        else:
            # Используем координаты, если адрес не найден
            out_path = f"qibla_{lat:.5f}_{lon:.5f}.png".replace('.', '_').replace(',', '_')

    # Пытаемся найти здание (сначала Яндекс API, затем OSM fallback)
    poly = get_building_polygon(lat, lon, radius_m=radius_m)
    building_found = poly is not None

    log_time("Загрузка карты...")
    img, top_left_world, zoom = static_map(lat, lon, zoom=zoom, size_px=size_px, tile_source=tile_source)
    draw = ImageDraw.Draw(img)

    # Координаты пользователя (всегда используем их для маркера "вы здесь")
    user_x, user_y = lonlat_to_img_px(lon, lat, top_left_world, zoom)
    
    if building_found:
        log_time("Вычисление ориентации здания...")
        bldg_axis = polygon_orientation_deg(poly)
        log_time(f"Ось здания (PCA): {bldg_axis:.1f}°")
        
        # Находим стену, которую пересекает стрелка киблы
        # Выбираем стену, у которой перпендикуляр ближе всего к кибле (стрелка почти перпендикулярна стене)
        walls = [
            bldg_axis,
            (bldg_axis + 90) % 360,
            (bldg_axis + 180) % 360,
            (bldg_axis + 270) % 360
        ]
        
        best_wall = None
        min_turn_from_perp = float('inf')
        
        for wall_dir in walls:
            # Вычисляем перпендикуляры к стене
            perp1 = (wall_dir + 90) % 360
            perp2 = (wall_dir - 90) % 360
            
            # Выбираем перпендикуляр, который ближе к кибле
            turn1 = abs(smallest_turn(perp1, qibla))
            turn2 = abs(smallest_turn(perp2, qibla))
            min_turn = min(turn1, turn2)
            
            # Выбираем стену с минимальным поворотом от перпендикуляра
            if min_turn < min_turn_from_perp:
                min_turn_from_perp = min_turn
                best_wall = wall_dir
        
        # Вычисляем перпендикуляры к выбранной стене
        perp1 = (best_wall + 90) % 360
        perp2 = (best_wall - 90) % 360
        
        # Выбираем перпендикуляр, который ближе к кибле
        turn1 = smallest_turn(perp1, qibla)
        turn2 = smallest_turn(perp2, qibla)
        
        if abs(turn1) < abs(turn2):
            wall_turn = turn1
            used_perp = perp1
        else:
            wall_turn = turn2
            used_perp = perp2
        
        # Поворот уже правильный: положительный = вправо, отрицательный = влево
        # Не инвертируем знак
        
        wall_name = direction_to_cardinal(best_wall)
        log_time(f"Стена, пересекаемая стрелкой: {wall_name} ({best_wall:.1f}°), поворот от перпендикуляра: {wall_turn:+.2f}°")
        
        # полигон здания
        pts = [lonlat_to_img_px(plon, plat, top_left_world, zoom) for (plon, plat) in poly]
        # Рисуем полигон более заметным: синий контур с белой обводкой для лучшей видимости
        draw.polygon(pts, outline=(0, 0, 255), width=6)
        # Дополнительная белая обводка для контраста
        draw.polygon(pts, outline=(255, 255, 255), width=2)
        
        # Центр здания для стрелки киблы
        bldg_cx = sum(p[0] for p in pts) / len(pts)
        bldg_cy = sum(p[1] for p in pts) / len(pts)
        
        # Маркер "вы здесь" - координаты пользователя
        # Стрелка киблы - центр здания
        cx, cy = bldg_cx, bldg_cy
    else:
        # Если здание не найдено, используем координаты пользователя
        cx, cy = user_x, user_y
        bldg_axis = 0
        wall_turn = 0
        wall_name = ""

    r = 8
    # Маркер "вы здесь" - всегда координаты пользователя
    draw.ellipse((user_x-r, user_y-r, user_x+r, user_y+r), fill=(255, 255, 0), outline=(0, 0, 0), width=2)

    # Стрелка Севера (в левом верхнем углу)
    north_x, north_y = 50, 50
    draw_north_arrow(draw, north_x, north_y, size=35)

    # Дугу поворота убираем - она непонятна пользователю

    # Стрелка на Каабу
    draw_arrow(draw, cx, cy, qibla, length=300)

    # Подпись на русском языке с понятными инструкциями
    # Вычисляем bearing всеми методами для отображения
    qibla_spherical = bearing_deg(lat, lon, method="spherical")
    qibla_vincenty = bearing_deg(lat, lon, method="vincenty")
    qibla_great_circle = bearing_deg(lat, lon, method="great_circle")
    
    if building_found:
        # Вычисляем угол поворота для всех трех методов bearing
        # Для каждого метода bearing вычисляем угол поворота
        def calc_turn_for_qibla(qibla_val):
                walls = [
                    bldg_axis,
                    (bldg_axis + 90) % 360,
                    (bldg_axis + 180) % 360,
                    (bldg_axis + 270) % 360
                ]
                
                # Выбираем стену, у которой перпендикуляр ближе всего к кибле
                best_wall_for_qibla = None
                min_turn_from_perp = float('inf')
                
                for wall_dir in walls:
                    perp1 = (wall_dir + 90) % 360
                    perp2 = (wall_dir - 90) % 360
                    turn1 = abs(smallest_turn(perp1, qibla_val))
                    turn2 = abs(smallest_turn(perp2, qibla_val))
                    min_turn = min(turn1, turn2)
                    
                    if min_turn < min_turn_from_perp:
                        min_turn_from_perp = min_turn
                        best_wall_for_qibla = wall_dir
                
                # Вычисляем поворот от перпендикуляра к кибле
                perp1 = (best_wall_for_qibla + 90) % 360
                perp2 = (best_wall_for_qibla - 90) % 360
                turn1 = smallest_turn(perp1, qibla_val)
                turn2 = smallest_turn(perp2, qibla_val)
                
                if abs(turn1) < abs(turn2):
                    return turn1  # Поворот уже правильный
                else:
                    return turn2
        
        turn_spherical = calc_turn_for_qibla(qibla_spherical)
        turn_vincenty = calc_turn_for_qibla(qibla_vincenty)
        turn_great_circle = calc_turn_for_qibla(qibla_great_circle)
        
        turn_text = left_right_text(wall_turn)
        
        # Форматируем углы поворота с сотыми долями для всех методов
        turn_val_spherical = f"{turn_spherical:.2f}°"
        turn_val_vincenty = f"{turn_vincenty:.2f}°"
        turn_val_great_circle = f"{turn_great_circle:.2f}°"
        
        text_lines = [
            f"Кибла: {qibla:.2f}° (s:{qibla_spherical:.2f}° v:{qibla_vincenty:.2f}° gc:{qibla_great_circle:.2f}°)",
            f"От перпендикуляра к {wall_name} стене",
            f"повернись на {turn_text} (s:{turn_val_spherical} v:{turn_val_vincenty} gc:{turn_val_great_circle})"
        ]
    else:
        text_lines = [
            f"Кибла: {qibla:.2f}° (s:{qibla_spherical:.2f}° v:{qibla_vincenty:.2f}° gc:{qibla_great_circle:.2f}°)",
            "Контур здания не найден",
            "Используй компас для ориентации"
        ]
    
    # Информация об источнике тайлов в левом нижнем углу
    tile_source_text = "CartoDB" if tile_source == "cartodb" else "Яндекс.Карты"
    tile_info_text = f"Карта: {tile_source_text}"
    
    # Пытаемся загрузить системный шрифт
    font_size = 26
    font = None
    
    # Список возможных путей к шрифтам (для разных ОС)
    font_paths = [
        # macOS
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        # Windows (обычно в системных папках)
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    
    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, font_size)
            break
        except:
            continue
    
    # Если не удалось загрузить системный шрифт, создаем увеличенный встроенный
    if font is None:
        try:
            # Пробуем создать шрифт из встроенного, увеличив его
            font = ImageFont.load_default()
            # Для встроенного шрифта используем больший размер через масштабирование
            # Но лучше использовать truetype, поэтому попробуем еще раз с другими путями
            import os
            if os.name == 'nt':  # Windows
                font = ImageFont.truetype("arial.ttf", font_size)
            else:
                # Используем встроенный шрифт, но увеличим размер текста через stroke
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()
    
    # Вычисляем размер текста для всех строк
    line_height = 0
    max_width = 0
    for line in text_lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_height = max(line_height, bbox[3] - bbox[1])
        max_width = max(max_width, bbox[2] - bbox[0])
    
    # Высота всего блока текста
    line_spacing = 8
    total_height = len(text_lines) * (line_height + line_spacing) - line_spacing
    
    # Рисуем фон для текста с запасом
    padding = 18
    draw.rectangle((10, 10, size_px-10, total_height + padding * 2), fill=(255, 255, 255))
    
    # Рисуем каждую строку текста
    y_offset = padding
    for line in text_lines:
        # Рисуем текст (повторяем с небольшим смещением для эффекта жирности и четкости)
        draw.text((padding, y_offset), line, fill=(0, 0, 0), font=font)
        draw.text((padding+1, y_offset+1), line, fill=(0, 0, 0), font=font)
        y_offset += line_height + line_spacing
    
    # Рисуем информацию об источнике тайлов в левом нижнем углу
    # Используем меньший шрифт для информационного текста
    info_font_size = 16
    info_font = None
    for font_path in font_paths:
        try:
            info_font = ImageFont.truetype(font_path, info_font_size)
            break
        except:
            continue
    if info_font is None:
        info_font = ImageFont.load_default()
    
    # Вычисляем размер текста об источнике
    info_bbox = draw.textbbox((0, 0), tile_info_text, font=info_font)
    info_width = info_bbox[2] - info_bbox[0]
    info_height = info_bbox[3] - info_bbox[1]
    
    # Рисуем фон для информационного текста
    info_padding = 8
    info_x = 10
    info_y = size_px - info_height - info_padding - 10
    draw.rectangle(
        (info_x, info_y - info_padding, info_x + info_width + info_padding * 2, info_y + info_height + info_padding),
        fill=(255, 255, 255, 200)  # Полупрозрачный белый фон
    )
    
    # Рисуем текст об источнике
    draw.text((info_x + info_padding, info_y), tile_info_text, fill=(100, 100, 100), font=info_font)

    log_time("Сохранение изображения...")
    img.save(out_path)
    log_time(f"Изображение сохранено: {out_path}")
    
    if building_found:
        return qibla, bldg_axis, wall_turn, out_path
    else:
        return qibla, 0, 0, out_path

