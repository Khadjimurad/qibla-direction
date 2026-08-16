# Qibla Direction

Программа считает направление на Каабу и рисует его на карте вместе с контуром здания.

## Возможности

- Азимут двумя независимыми методами: ортодромия (`great_circle`) и Vincenty по эллипсоиду WGS84
- Контур ближайшего здания из OpenStreetMap (Overpass)
- Подсказка: от какой стены и на сколько градусов повернуться
- Имя файла из адреса (Яндекс.Геокодер, запасной вариант — Nominatim)
- Карта: официальный [Tiles API](https://yandex.com/maps-api/docs/tiles-api/request.html) Яндекса в проекции Web Mercator, при сбое — CARTO, затем OSM

## Установка

Python 3.10+.

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Ключ Яндекс.Карт можно задать в окружении (иначе используется ключ по умолчанию из кода):

```bash
export YANDEX_API_KEY="ваш-ключ"
```

Для адресов нужен ключ с доступом к Геокодеру. Если его нет, адрес берётся из Nominatim.

Шаблон: `.env.example`.

## Использование

```bash
python -m bearing <lat> <lon> [опции]
```

После `pip install -e .` доступна команда `bearing`.

### Параметры

| Параметр | Описание |
| --- | --- |
| `lat`, `lon` | Координаты (точка или запятая) |
| `-o`, `--output` | Путь к PNG |
| `-z`, `--zoom` | Зум (по умолчанию 19) |
| `-r`, `--radius` | Радиус поиска здания, м (150) |
| `-s`, `--size` | Размер картинки, px (900) |
| `--tile-source` | `yandex` (по умолчанию), `cartodb` или `osm` |
| `--method` | `great_circle` (по умолчанию) или `vincenty` |

### Примеры

```bash
python -m bearing 42.96914 47.49389
python -m bearing 42.96914 47.49389 -z 20 -r 200 --tile-source osm
python -m bearing 42,96914 47,49389 --method vincenty
```

## Структура

```
bearing/
├── bearing/
│   ├── geometry.py      # азимут, стены, ориентация полигона
│   ├── osm.py           # Overpass и геокодинг
│   ├── map.py           # тайлы карт
│   ├── visualization.py # PNG
│   └── cli.py           # командная строка
├── main.py              # пример скрипта
└── tests/
```

## Зависимости

- `requests` — HTTP
- `Pillow` — картинки

## Источники

- Карты: Яндекс Tiles API (`projection=web_mercator`), CARTO, OpenStreetMap
- Здания: Overpass API
- Адреса: Яндекс.Геокодер HTTP API v1 (запасной вариант — 1.x и Nominatim)

## Лицензия

Данные OpenStreetMap — ODbL. Код проекта можно использовать свободно.
