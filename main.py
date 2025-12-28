"""
Точка входа для использования программы как скрипта.
"""

from bearing.visualization import build_qibla_image


if __name__ == "__main__":
    # пример: подставьте свои координаты
    lat = 42.99150
    lon = 47.48374
    result = build_qibla_image(lat, lon, "qibla.png")
    if len(result) == 5:
        qibla, axis, wall_turn, wall_name, path = result
    else:
        qibla, axis, wall_turn, path = result
        wall_name = ""
    from bearing.geometry import left_right_text
    print("Saved:", path)
    print("Qibla:", qibla)
    if axis > 0:
        print("Building axis:", axis)
        if wall_name:
            print(f"From {wall_name} wall: {left_right_text(wall_turn)}")
        else:
            print("Turn from wall:", left_right_text(wall_turn))
    else:
        print("Building not found")

