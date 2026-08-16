"""Пример запуска как скрипта. Основной способ: python -m bearing <lat> <lon>"""

from bearing.geometry import left_right_text
from bearing.visualization import build_qibla_image

if __name__ == "__main__":
    lat = 42.99150
    lon = 47.48374
    result = build_qibla_image(lat, lon)
    print("Saved:", result.path)
    print("Qibla:", result.qibla)
    if result.building_found:
        print("Building axis:", result.building_axis)
        print(f"From {result.wall_name} wall: {left_right_text(result.wall_turn)}")
    else:
        print("Building not found")
