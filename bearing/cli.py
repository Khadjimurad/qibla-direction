"""
CLI интерфейс для запуска программы из командной строки.
"""

import argparse
from bearing.visualization import build_qibla_image


def parse_coordinate(value):
    """
    Парсит координату, поддерживая как точку, так и запятую в качестве десятичного разделителя.
    Также обрабатывает случай, когда координата передана с запятой в конце (например, "42.539388,").
    
    Args:
        value: Строка с координатой (например, "42.96914", "42,96914" или "42.539388,")
    
    Returns:
        float: Координата как число с плавающей точкой
    """
    # Убираем пробелы и запятые в конце (если координата передана как "42.539388,")
    value = str(value).strip().rstrip(',')
    # Заменяем запятую на точку для поддержки разных локалей
    return float(value.replace(',', '.'))


def main():
    """Основная функция CLI интерфейса."""
    parser = argparse.ArgumentParser(
        description="Вычисление направления на Каабу и визуализация на карте с ориентацией здания"
    )
    parser.add_argument(
        "lat",
        type=parse_coordinate,
        help="Широта точки в градусах (можно использовать точку или запятую)"
    )
    parser.add_argument(
        "lon",
        type=parse_coordinate,
        help="Долгота точки в градусах (можно использовать точку или запятую)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Путь для сохранения изображения (по умолчанию: генерируется на основе адреса или координат)"
    )
    parser.add_argument(
        "-z", "--zoom",
        type=int,
        default=19,
        help="Уровень зума карты (по умолчанию: 19)"
    )
    parser.add_argument(
        "-r", "--radius",
        type=int,
        default=150,
        help="Радиус поиска здания в метрах (по умолчанию: 150)"
    )
    parser.add_argument(
        "-s", "--size",
        type=int,
        default=900,
        help="Размер изображения в пикселях (по умолчанию: 900)"
    )
    parser.add_argument(
        "--tile-source",
        type=str,
        choices=["cartodb", "yandex"],
        default="yandex",
        help="Источник тайлов карты: yandex (по умолчанию) или cartodb"
    )

    args = parser.parse_args()

    try:
        result = build_qibla_image(
            args.lat,
            args.lon,
            out_path=args.output,
            zoom=args.zoom,
            size_px=args.size,
            radius_m=args.radius,
            tile_source=args.tile_source
        )
        qibla, axis, wall_turn, path = result
        
        from bearing.geometry import left_right_text, direction_to_cardinal, bearing_deg, smallest_turn
        
        # Вычисляем bearing всеми методами для вывода
        qibla_spherical = bearing_deg(args.lat, args.lon, method="spherical")
        qibla_vincenty = bearing_deg(args.lat, args.lon, method="vincenty")
        qibla_great_circle = bearing_deg(args.lat, args.lon, method="great_circle")
        
        # Определяем стену для вывода и вычисляем угол поворота для всех методов
        if axis > 0:
            walls = [
                axis,
                (axis + 90) % 360,
                (axis + 180) % 360,
                (axis + 270) % 360
            ]
            
            def calc_turn_for_qibla(qibla_val):
                # Выбираем стену, у которой перпендикуляр ближе всего к кибле
                best_wall = None
                min_turn_from_perp = float('inf')
                for wall_dir in walls:
                    perp1 = (wall_dir + 90) % 360
                    perp2 = (wall_dir - 90) % 360
                    turn1 = abs(smallest_turn(perp1, qibla_val))
                    turn2 = abs(smallest_turn(perp2, qibla_val))
                    min_turn = min(turn1, turn2)
                    if min_turn < min_turn_from_perp:
                        min_turn_from_perp = min_turn
                        best_wall = wall_dir
                
                # Вычисляем поворот от перпендикуляра к кибле
                perp1 = (best_wall + 90) % 360
                perp2 = (best_wall - 90) % 360
                turn1 = smallest_turn(perp1, qibla_val)
                turn2 = smallest_turn(perp2, qibla_val)
                
                if abs(turn1) < abs(turn2):
                    return turn1, best_wall  # Поворот уже правильный
                else:
                    return turn2, best_wall
            
            turn_spherical, best_wall = calc_turn_for_qibla(qibla_spherical)
            turn_vincenty, _ = calc_turn_for_qibla(qibla_vincenty)
            turn_great_circle, _ = calc_turn_for_qibla(qibla_great_circle)
            
            wall_name = direction_to_cardinal(best_wall)
        
        print(f"Сохранено: {path}")
        print(f"Кибла: {qibla:.2f}° (spherical: {qibla_spherical:.2f}°, vincenty: {qibla_vincenty:.2f}°, great_circle: {qibla_great_circle:.2f}°)")
        if axis > 0:
            print(f"Ось здания: {axis:.1f}°")
            turn_text = left_right_text(wall_turn)
            turn_text_spherical = left_right_text(turn_spherical)
            turn_text_vincenty = left_right_text(turn_vincenty)
            turn_text_great_circle = left_right_text(turn_great_circle)
            print(f"От перпендикуляра к {wall_name} стене повернись на {turn_text} (spherical: {turn_text_spherical}, vincenty: {turn_text_vincenty}, great_circle: {turn_text_great_circle})")
        else:
            print("Здание не найдено - используйте компас для ориентации")
    except Exception as e:
        print(f"Ошибка: {e}", file=__import__('sys').stderr)
        return 1

    return 0


if __name__ == "__main__":
    exit(main())

