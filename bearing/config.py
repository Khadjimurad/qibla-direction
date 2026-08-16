"""Общие настройки, HTTP-хелперы и логирование."""

from __future__ import annotations

import os
import sys
from datetime import datetime

import requests

APP_NAME = "Bearing-Qibla"
APP_VERSION = "1.1.0"
USER_AGENT = (
    f"{APP_NAME}/{APP_VERSION} "
    "(https://github.com/Khadjimurad/qibla-direction; Python/requests)"
)

# Ключ можно переопределить переменной окружения YANDEX_API_KEY
YANDEX_API_KEY = os.environ.get(
    "YANDEX_API_KEY",
    "242746bf-f9aa-4da3-b5fd-e9c5d9b19234",
)

HTTP_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "ru,en;q=0.8",
}

OVERPASS_SERVERS = (
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
)

DEFAULT_TIMEOUT = 20


def log_time(msg: str) -> None:
    """Пишет сообщение с временной меткой в stderr."""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {msg}", file=sys.stderr)


def http_get(url: str, **kwargs) -> requests.Response:
    headers = {**HTTP_HEADERS, **kwargs.pop("headers", {})}
    timeout = kwargs.pop("timeout", DEFAULT_TIMEOUT)
    return requests.get(url, headers=headers, timeout=timeout, **kwargs)


def http_post(url: str, **kwargs) -> requests.Response:
    headers = {**HTTP_HEADERS, **kwargs.pop("headers", {})}
    timeout = kwargs.pop("timeout", DEFAULT_TIMEOUT)
    return requests.post(url, headers=headers, timeout=timeout, **kwargs)
